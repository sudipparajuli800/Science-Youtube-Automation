import os
import time
import random
import re
import requests
from google import genai
from google.genai import types
from typing import List, Dict
from ..content.public_text import plain_public_text

class MetaUploader:
    def __init__(self):
        self.access_token = os.getenv("META_ACCESS_TOKEN")
        self.page_id = os.getenv("FACEBOOK_PAGE_ID")
        self.api_version = "v19.0"
        
        # Load API keys for translation rotation
        self.gemini_keys = [
            os.getenv("GEMINI_API_KEY"),
            os.getenv("GEMINI_API_KEY2"),
            os.getenv("GEMINI_API_KEY3")
        ]
        self.gemini_keys = [k for k in self.gemini_keys if k]
        
        def patch_gemini_client(client):
            original_generate_content = client.models.generate_content
            def patched_generate_content(*args, **kwargs):
                safety_settings = kwargs.pop('safety_settings', None)
                config = kwargs.get('config', None)
                if safety_settings:
                    if config is None:
                        config = types.GenerateContentConfig(safety_settings=safety_settings)
                    elif isinstance(config, types.GenerateContentConfig):
                        config.safety_settings = safety_settings
                    elif isinstance(config, dict):
                        config['safety_settings'] = safety_settings
                    kwargs['config'] = config
                return original_generate_content(*args, **kwargs)
            client.models.generate_content = patched_generate_content
            return client

        self.gemini_clients = [patch_gemini_client(genai.Client(api_key=k)) for k in self.gemini_keys]
        self.model_id = "gemini-2.0-flash"
        
        self.groq_api_keys = [
            os.getenv("GROQ_API_KEY"),
            os.getenv("GROQ_API_KEY2"),
            os.getenv("GROQ_API_KEY3")
        ]
        self.groq_api_keys = [k for k in self.groq_api_keys if k]
        self.groq_clients = []
        if self.groq_api_keys:
            try:
                from groq import Groq
                for k in self.groq_api_keys:
                    gc = Groq(api_key=k)
                    class MockModerations:
                        def create(self, *args, **kwargs):
                            pass
                    gc.moderations = MockModerations()
                    self.groq_clients.append(gc)
            except ImportError:
                pass

    def _call_llm_with_retry(self, prompt: str, max_retries: int = 5) -> str:
        """Call LLM with full fallback and rotation for translation tasks."""
        if not self.gemini_clients:
            print("WARNING: No Gemini clients available for translation. Trying Groq...")
            
        for client_idx, client in enumerate(self.gemini_clients):
            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(
                        model=self.model_id,
                        contents=prompt,
                        safety_settings=[
                            types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
                            types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
                            types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
                            types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
                        ]
                    )
                    return response.text.strip()
                except Exception as e:
                    err_msg = str(e).lower()
                    if "quota" in err_msg or "429" in err_msg or "exhausted" in err_msg:
                        print(f"Gemini translation key {client_idx+1} quota exceeded. Trying next key...")
                        break
                    if attempt < max_retries - 1:
                        time.sleep(2 + random.uniform(0, 1))
                    else:
                        break
                        
        if self.groq_clients:
            for client_idx, groq_client in enumerate(self.groq_clients):
                for attempt in range(max_retries):
                    try:
                        groq_client.moderations.create(input=prompt)
                        chat_completion = groq_client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama-3.3-70b-versatile",
                            max_tokens=4096,
                            user="science-automation",
                        )
                        msg = chat_completion.choices[0].message
                        refusal = getattr(msg, 'refusal', None)
                        if refusal:
                            print(f"Groq translation key {client_idx+1} refused: {refusal}")
                            break
                        result = (msg.content or "").strip()
                        if result:
                            return result
                    except Exception as groq_err:
                        err_msg = str(groq_err).lower()
                        if "quota" in err_msg or "429" in err_msg or "exhausted" in err_msg:
                            break
                        if attempt < max_retries - 1:
                            time.sleep((2 ** attempt) + 1)
        return ""

    def translate_text(self, text: str, target_lang: str) -> str:
        """Translate text to the target language using rotating LLM."""
        prompt = f"""
        Translate the following text into {target_lang}.
        Maintain the exact same structure, timing elements, brackets, or numbers.
        If the text contains subtitle indexes or time codes, do not modify them.
        Provide ONLY the translated text without any explanations.
        
        Text to translate:
        "{text}"
        """
        return plain_public_text(self._call_llm_with_retry(prompt))

    def translate_srt_content(self, srt_content: str, target_lang: str) -> str:
        """Parses SRT blocks, translates subtitle texts in batch to preserve context, and reconstructs SRT."""
        # Standardize newlines and split into blocks
        blocks = srt_content.replace('\r\n', '\n').strip().split('\n\n')
        parsed_blocks = []
        
        for block in blocks:
            lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
            if len(lines) >= 3:
                idx = lines[0]
                time_code = lines[1]
                text = " ".join(lines[2:])
                parsed_blocks.append({
                    "idx": idx,
                    "time_code": time_code,
                    "text": text
                })
                
        if not parsed_blocks:
            return ""
            
        # Collect sentences
        sentences = []
        for block in parsed_blocks:
            sentences.append(f"{block['idx']}: {block['text']}")
            
        batch_prompt = f"""
        Translate the following numbered sentences from a science documentary script into {target_lang}.
        Maintain the exact sentence numbers (e.g., "1: ...", "2: ...") and order.
        Return ONLY the translated list. Do not add any introduction or signature.
        
        Sentences:
        {chr(10).join(sentences)}
        """
        translated_batch = self._call_llm_with_retry(batch_prompt)
        
        # Parse translated sentences back
        translated_map = {}
        for line in translated_batch.split('\n'):
            line = line.strip()
            item_match = re.match(r'^(\d+)[\:\.]\s*(.*)$', line)
            if item_match:
                item_idx = item_match.group(1)
                val = item_match.group(2).strip()
                translated_map[item_idx] = val
                
        # Reconstruct SRT
        reconstructed = []
        for block in parsed_blocks:
            translated_text = translated_map.get(block['idx'], block['text'])
            reconstructed.append(f"{block['idx']}\n{block['time_code']}\n{translated_text}\n")
            
        return plain_public_text("\n".join(reconstructed))

    def upload_video(self, video_path: str, title: str, description: str, tags: List[str] = None) -> str:
        """Main method to upload a video/reel to Facebook and cross-post to Instagram."""
        if not self.access_token or not self.page_id:
            print("Meta posting credentials missing. Skipping Meta upload.")
            return None

        title, description = plain_public_text(title), plain_public_text(description)

        # Detect aspect ratio to classify if it is a Reel
        is_reel = True
        try:
            # Simple duration/dimensions classifier if possible, otherwise check title/tags
            if tags and "shorts" not in tags and "Shorts" not in title:
                is_reel = False
        except Exception:
            pass

        print(f"Meta Uploading: {title} (Is Reel: {is_reel})")
        fb_video_id = None
        if is_reel:
            fb_video_id = self._upload_facebook_reel(video_path, description)
        else:
            fb_video_id = self._upload_facebook_video(video_path, title, description)

        if not fb_video_id:
            print("Facebook Page upload failed. Cannot cross-post to Instagram.")
            return None

        print(f"Facebook Video published successfully! ID: {fb_video_id}")

        # Post captions to Facebook video if SRT file is available
        # In our pipeline, long-form SRT is saved at "automation/storage/science_long.srt"
        # and shorts don't have standard separate SRT files, but we check if one exists
        srt_path = "automation/storage/science_long.srt" if not is_reel else "automation/storage/science_shorts.srt"
        if os.path.exists(srt_path):
            self.upload_facebook_captions(fb_video_id, srt_path)

        # Cross-post to Instagram Business account if linked
        self._publish_to_instagram(fb_video_id, description, video_path)
        return fb_video_id

    def _upload_facebook_reel(self, video_path: str, description: str) -> str:
        """Uploads a Facebook Reel using the 3-step Resumable Upload API."""
        try:
            # Step 1: Start Upload Session
            init_url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}/video_reels"
            params = {
                "upload_phase": "start",
                "access_token": self.access_token
            }
            res = requests.post(init_url, params=params)
            res_data = res.json()
            if "video_id" not in res_data:
                print(f"Facebook Reels initialization failed: {res.text}")
                if "error" in res_data:
                    err_msg = res_data["error"].get("message", "")
                    if "pages_manage_posts" in err_msg or "permission" in err_msg.lower() or "OAuthException" in res_data["error"].get("type", ""):
                        print("\n" + "!" * 80)
                        print("CRITICAL: Meta Access Token lacks required permissions (e.g. pages_manage_posts).")
                        print("ACTION REQUIRED TO RESOLVE:")
                        print("1. Go to your Meta Developer App -> Graph API Explorer.")
                        print("2. Ensure your token has 'pages_manage_posts', 'pages_read_engagement', and 'pages_show_list'.")
                        print("3. IMPORTANT: Make sure you use a PAGE Access Token (obtained via GET /me/accounts),")
                        print("   NOT a USER Access Token.")
                        print("4. Update your META_ACCESS_TOKEN GitHub Secret with the new Page Access Token.")
                        print("!" * 80 + "\n")
                return None
                
            video_id = res_data["video_id"]
            upload_url = res_data["upload_url"]

            # Step 2: Upload Binary Chunks to rupload.facebook.com
            file_size = os.path.getsize(video_path)
            with open(video_path, "rb") as f:
                video_data = f.read()

            headers = {
                "Authorization": f"OAuth {self.access_token}",
                "offset": "0",
                "file_size": str(file_size),
                "Content-Type": "application/octet-stream"
            }
            upload_res = requests.post(upload_url, data=video_data, headers=headers)
            if upload_res.status_code != 200:
                print(f"Facebook Reels chunk upload failed: {upload_res.text}")
                return None

            # Step 3: Finish and Publish Reel
            publish_params = {
                "video_id": video_id,
                "upload_phase": "finish",
                "video_state": "PUBLISHED",
                "description": plain_public_text(description),
                "access_token": self.access_token
            }
            finish_res = requests.post(init_url, data=publish_params)
            finish_data = finish_res.json()
            if finish_data.get("success") or "video_id" in finish_data:
                return video_id
            print(f"Facebook Reels finalize failed: {finish_res.text}")
            return None
        except Exception as e:
            print(f"Error in _upload_facebook_reel: {e}")
            return None

    def _upload_facebook_video(self, video_path: str, title: str, description: str) -> str:
        """Uploads standard long-form video using simple multipart upload."""
        try:
            url = f"https://graph-video.facebook.com/{self.api_version}/{self.page_id}/videos"
            payload = {
                "title": plain_public_text(title),
                "description": plain_public_text(description),
                "access_token": self.access_token
            }
            with open(video_path, "rb") as f:
                files = {
                    "source": f
                }
                res = requests.post(url, data=payload, files=files)
            
            res_data = res.json()
            if "id" in res_data:
                return res_data["id"]
            print(f"Facebook Video upload failed: {res.text}")
            if "error" in res_data:
                err_msg = res_data["error"].get("message", "")
                if "pages_manage_posts" in err_msg or "permission" in err_msg.lower() or "OAuthException" in res_data["error"].get("type", ""):
                    print("\n" + "!" * 80)
                    print("CRITICAL: Meta Access Token lacks required permissions (e.g. pages_manage_posts).")
                    print("ACTION REQUIRED TO RESOLVE:")
                    print("1. Go to your Meta Developer App -> Graph API Explorer.")
                    print("2. Ensure your token has 'pages_manage_posts', 'pages_read_engagement', and 'pages_show_list'.")
                    print("3. IMPORTANT: Make sure you use a PAGE Access Token (obtained via GET /me/accounts),")
                    print("   NOT a USER Access Token.")
                    print("4. Update your META_ACCESS_TOKEN GitHub Secret with the new Page Access Token.")
                    print("!" * 80 + "\n")
            return None
        except Exception as e:
            print(f"Error in _upload_facebook_video: {e}")
            return None

    def upload_facebook_captions(self, fb_video_id: str, srt_path: str):
        """Translates the SRT file to multiple languages and uploads them all as subtitles."""
        try:
            with open(srt_path, "r", encoding="utf-8") as f:
                original_srt = f.read()

            languages = [
                ("Spanish", "es_LA"),
                ("French", "fr_FR"),
                ("German", "de_DE"),
                ("Portuguese", "pt_BR"),
                ("Hindi", "hi_IN")
            ]

            # 1. Upload English Captions first
            print("Uploading English captions...")
            self._upload_single_caption(fb_video_id, original_srt, "en_US", is_default=True)

            # 2. Translate and Upload other major languages
            for lang_name, locale in languages:
                print(f"Translating captions to {lang_name} ({locale})...")
                translated_srt = self.translate_srt_content(original_srt, lang_name)
                if translated_srt:
                    print(f"Uploading {lang_name} captions...")
                    self._upload_single_caption(fb_video_id, translated_srt, locale, is_default=False)
                else:
                    print(f"Failed to translate captions to {lang_name}")
        except Exception as e:
            print(f"Error in upload_facebook_captions: {e}")

    def _upload_single_caption(self, fb_video_id: str, srt_content: str, locale: str, is_default: bool = False):
        """Posts a single locale caption SRT file to the Facebook video captions endpoint."""
        try:
            url = f"https://graph-video.facebook.com/{self.api_version}/{fb_video_id}/captions"
            payload = {
                "access_token": self.access_token,
                "default_locale": locale if is_default else ""
            }
            # The files key name must match Facebook specification, filename should incorporate the locale
            files = {
                "captions_file": (f"captions.{locale}.srt", plain_public_text(srt_content).encode("utf-8"), "application/x-subrip")
            }
            res = requests.post(url, data=payload, files=files)
            if res.json().get("success"):
                print(f"Successfully uploaded {locale} captions.")
            else:
                print(f"Failed to upload {locale} captions: {res.text}")
        except Exception as e:
            print(f"Error uploading caption for locale {locale}: {e}")

    def _publish_to_instagram(self, fb_video_id: str, caption: str, video_path: str = None):
        """Discovers the linked Instagram Business account and posts the video as an IG Reel."""
        try:
            # 1. Discover Instagram Business Account ID
            discovery_url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}"
            params = {
                "fields": "instagram_business_account",
                "access_token": self.access_token
            }
            disc_res = requests.get(discovery_url, params=params)
            ig_account_id = disc_res.json().get("instagram_business_account", {}).get("id")
            if not ig_account_id:
                print("No linked Instagram Business Account found on Facebook Page. Skipping IG cross-posting.")
                return

            print(f"Found linked Instagram Business Account ID: {ig_account_id}")

            creation_id = None

            # Try direct Resumable Binary Upload if video_path is available
            if video_path and os.path.exists(video_path):
                print(f"Attempting direct Resumable Binary Upload for Instagram Reel: {video_path}...")
                try:
                    container_url = f"https://graph.facebook.com/{self.api_version}/{ig_account_id}/media"
                    container_payload = {
                        "media_type": "REELS",
                        "upload_type": "resumable",
                        "caption": plain_public_text(caption),
                        "access_token": self.access_token
                    }
                    c_res = requests.post(container_url, data=container_payload)
                    c_data = c_res.json()
                    
                    cid = c_data.get("ig_container_id") or c_data.get("id")
                    upload_uri = c_data.get("uri") or (f"https://rupload.facebook.com/ig-api-upload/{self.api_version}/{cid}" if cid else None)
                    
                    if cid and upload_uri:
                        file_size = os.path.getsize(video_path)
                        with open(video_path, "rb") as f:
                            video_data = f.read()

                        headers = {
                            "Authorization": f"OAuth {self.access_token}",
                            "offset": "0",
                            "file_size": str(file_size),
                            "Content-Type": "application/octet-stream"
                        }
                        upload_res = requests.post(upload_uri, data=video_data, headers=headers)
                        if upload_res.status_code == 200:
                            print("Instagram Reels binary upload successful.")
                            creation_id = cid
                        else:
                            print(f"Instagram Reels binary upload failed (status {upload_res.status_code}): {upload_res.text}")
                    else:
                        print(f"Failed to initialize Instagram Reels resumable container: {c_res.text}")
                except Exception as ex:
                    print(f"Exception during Instagram Resumable Upload: {ex}")

            # Fallback to Facebook CDN URL if direct upload did not succeed
            if not creation_id:
                print("Falling back to Facebook CDN video URL for Instagram post...")
                # 2. Get Facebook Video CDN Public source URL
                # We wait up to 60 seconds (with polling) for Facebook to process the video and generate a source URL
                source_url = None
                video_url = f"https://graph.facebook.com/{self.api_version}/{fb_video_id}"
                video_params = {
                    "fields": "source",
                    "access_token": self.access_token
                }
                
                print("Waiting for Facebook to generate CDN video source URL...")
                for poll in range(12): # Poll every 10 seconds for up to 2 minutes
                    video_res = requests.get(video_url, params=video_params)
                    source_url = video_res.json().get("source")
                    if source_url:
                        break
                    time.sleep(10)

                if not source_url:
                    print("Could not retrieve Facebook video source URL. Instagram cross-posting aborted.")
                    return

                print(f"Successfully retrieved Facebook video source URL: {source_url[:60]}...")

                # 3. Create Instagram Reels Media Container (URL based)
                container_url = f"https://graph.facebook.com/{self.api_version}/{ig_account_id}/media"
                container_payload = {
                    "media_type": "REELS",
                    "video_url": source_url,
                    "caption": plain_public_text(caption),
                    "access_token": self.access_token
                }
                c_res = requests.post(container_url, data=container_payload)
                creation_id = c_res.json().get("ig_container_id") or c_res.json().get("id")
                if not creation_id:
                    print(f"Failed to create Instagram Reels container via fallback URL: {c_res.text}")
                    return

            print(f"Instagram Reels container created! ID: {creation_id}. Processing on Instagram...")

            # 4. Poll IG Container processing state until FINISHED
            status_url = f"https://graph.facebook.com/{self.api_version}/{creation_id}"
            status_params = {
                "fields": "status_code,status",
                "access_token": self.access_token
            }
            
            processing_success = False
            for poll in range(20): # Poll every 10 seconds for up to 200 seconds
                time.sleep(10)
                status_res = requests.get(status_url, params=status_params)
                res_json = status_res.json()
                status_code = res_json.get("status_code")
                status_detail = res_json.get("status")
                print(f"IG Reels Container Status: {status_code} (Detail: {status_detail})")
                if status_code == "FINISHED":
                    processing_success = True
                    break
                elif status_code in ["ERROR", "EXPIRED"]:
                    print(f"IG Reels Container processing error: {status_res.text}")
                    break

            if not processing_success:
                print("Instagram Reel processing timed out or failed.")
                return

            # 5. Publish IG Reel
            publish_url = f"https://graph.facebook.com/{self.api_version}/{ig_account_id}/media_publish"
            publish_payload = {
                "creation_id": creation_id,
                "access_token": self.access_token
            }
            pub_res = requests.post(publish_url, data=publish_payload)
            pub_data = pub_res.json()
            if "id" in pub_data:
                print(f"Instagram Reel published successfully! Media ID: {pub_data['id']}")
            else:
                print(f"Failed to publish Instagram Reel: {pub_res.text}")
        except Exception as e:
            print(f"Error in _publish_to_instagram: {e}")

    # ── Photo posts (text + image, for the daily FB/IG content) ──────────────────

    def upload_photo_post(self, image_path: str, caption: str) -> str:
        """Posts a photo+caption to the Facebook Page, then cross-posts the same
        photo to the linked Instagram Business account. Returns the Facebook photo
        ID, or None if the Facebook upload itself failed (Instagram cross-posting
        failing independently still leaves the Facebook post live)."""
        if not self.access_token or not self.page_id:
            print("Meta posting credentials missing. Skipping Meta photo post.")
            return None
        if not image_path or not os.path.exists(image_path):
            print(f"Meta photo post: image not found at {image_path}")
            return None

        caption = plain_public_text(caption)
        fb_photo_id, fb_image_url = self._upload_facebook_photo(image_path, caption)
        if not fb_photo_id:
            print("Facebook photo upload failed. Cannot cross-post to Instagram.")
            return None
        print(f"Facebook photo published successfully! ID: {fb_photo_id}")

        if fb_image_url:
            self._publish_photo_to_instagram(fb_image_url, caption)
        else:
            print("No public image URL available from Facebook — skipping Instagram photo cross-post.")

        return fb_photo_id

    def _upload_facebook_photo(self, image_path: str, caption: str):
        """Uploads a photo to the FB Page via binary multipart upload.
        Returns (photo_id, public_image_url) — either may be None on failure."""
        try:
            url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}/photos"
            payload = {"caption": plain_public_text(caption), "access_token": self.access_token}
            with open(image_path, "rb") as f:
                files = {"source": f}
                res = requests.post(url, data=payload, files=files)
            res_data = res.json()
            photo_id = res_data.get("id") or res_data.get("post_id")
            if not photo_id:
                print(f"Facebook photo upload failed: {res.text}")
                if "error" in res_data:
                    err_msg = res_data["error"].get("message", "")
                    if "pages_manage_posts" in err_msg or "permission" in err_msg.lower():
                        print("\n" + "!" * 80)
                        print("CRITICAL: Meta Access Token lacks required permissions (e.g. pages_manage_posts).")
                        print("Update your META_ACCESS_TOKEN GitHub Secret with a PAGE access token that has")
                        print("pages_manage_posts, pages_read_engagement, and pages_show_list.")
                        print("!" * 80 + "\n")
                return None, None

            # Fetch a public CDN URL for this photo so Instagram can fetch it too —
            # same pattern already used for video cross-posting (upload to Facebook
            # first, reuse its CDN URL for Instagram's URL-based media container).
            image_url = None
            try:
                info_url = f"https://graph.facebook.com/{self.api_version}/{photo_id}"
                info_res = requests.get(info_url, params={"fields": "images", "access_token": self.access_token})
                images = info_res.json().get("images", [])
                if images:
                    image_url = images[0].get("source")  # first entry is the largest resolution
            except Exception as e:
                print(f"Could not retrieve Facebook photo CDN URL: {e}")

            return photo_id, image_url
        except Exception as e:
            print(f"Error in _upload_facebook_photo: {e}")
            return None, None

    def _publish_photo_to_instagram(self, image_url: str, caption: str):
        """Discovers the linked Instagram Business account and posts a single photo."""
        try:
            discovery_url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}"
            params = {"fields": "instagram_business_account", "access_token": self.access_token}
            disc_res = requests.get(discovery_url, params=params)
            ig_account_id = disc_res.json().get("instagram_business_account", {}).get("id")
            if not ig_account_id:
                print("No linked Instagram Business Account found on Facebook Page. Skipping IG cross-posting.")
                return

            print(f"Found linked Instagram Business Account ID: {ig_account_id}")

            container_url = f"https://graph.facebook.com/{self.api_version}/{ig_account_id}/media"
            container_payload = {
                "image_url": image_url,
                "caption": plain_public_text(caption),
                "access_token": self.access_token,
            }
            c_res = requests.post(container_url, data=container_payload)
            creation_id = c_res.json().get("id")
            if not creation_id:
                print(f"Failed to create Instagram photo media container: {c_res.text}")
                return

            # Photo containers are usually ready almost immediately (unlike video/Reels,
            # which need the long processing poll above), but retry briefly in case
            # Instagram hasn't finished fetching the image yet.
            publish_url = f"https://graph.facebook.com/{self.api_version}/{ig_account_id}/media_publish"
            publish_payload = {"creation_id": creation_id, "access_token": self.access_token}
            for attempt in range(3):
                pub_res = requests.post(publish_url, data=publish_payload)
                pub_data = pub_res.json()
                if "id" in pub_data:
                    print(f"Instagram photo published successfully! Media ID: {pub_data['id']}")
                    return
                err_msg = pub_data.get("error", {}).get("message", "")
                if attempt < 2 and ("not ready" in err_msg.lower() or "media" in err_msg.lower()):
                    time.sleep(5)
                    continue
                print(f"Failed to publish Instagram photo: {pub_res.text}")
                return
        except Exception as e:
            print(f"Error in _publish_photo_to_instagram: {e}")
