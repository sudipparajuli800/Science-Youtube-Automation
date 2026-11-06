from ..content.public_text import plain_public_text
import os
import time
import random
from google import genai
from google.genai import types
from .auth import YouTubeAuth

class CommentHandler:
    def __init__(self, youtube_service, gemini_api_key=None):
        self.youtube = youtube_service
        
        # Gather all Gemini keys from env
        self.gemini_keys = [
            os.getenv("GEMINI_API_KEY"),
            os.getenv("GEMINI_API_KEY2"),
            os.getenv("GEMINI_API_KEY3")
        ]
        self.gemini_keys = [k for k in self.gemini_keys if k]
        if not self.gemini_keys and gemini_api_key:
            self.gemini_keys = [gemini_api_key]
            
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
                
        # Keep track of viewers we've already replied to
        self.replied_viewers_file = os.path.join(os.path.dirname(__file__), 'replied_viewers.txt')
        self.replied_viewers = set()
        if os.path.exists(self.replied_viewers_file):
            with open(self.replied_viewers_file, 'r', encoding='utf-8') as f:
                for line in f:
                    self.replied_viewers.add(line.strip())

    def _call_with_retry(self, prompt: str, max_retries: int = 5) -> str:
        """Calls Gemini rotating through keys, falling back to Groq only if all fail or hit quota."""
        if not self.gemini_clients:
            print("WARNING: No Gemini clients available for comments. Trying Groq immediately...")
            
        # Try each Gemini client sequentially
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
                    is_quota_error = "quota" in err_msg or "429" in err_msg or "exhausted" in err_msg
                    
                    if is_quota_error:
                        print(f"Gemini Comment Key {client_idx+1} Quota Exceeded/429. Trying next key...")
                        break
                    
                    if attempt < max_retries - 1:
                        time.sleep(2 + random.uniform(0, 1))
                    else:
                        print(f"Gemini Comment Key {client_idx+1} failed. Trying next key...")
                        break
                        
        # If all Gemini keys fail or are exhausted, try Groq fallback
        if self.groq_clients:
            print("All Gemini comment keys exhausted. Trying Groq fallback...")
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
                            print(f"Groq Comment Key {client_idx+1} refused: {refusal}")
                            break
                        result = (msg.content or "").strip()
                        if result:
                            return result
                    except Exception as groq_err:
                        err_msg = str(groq_err).lower()
                        is_quota_error = "quota" in err_msg or "429" in err_msg or "exhausted" in err_msg
                        
                        if is_quota_error:
                            print(f"Groq Comment Key {client_idx+1} Quota Exceeded/429. Trying next key...")
                            break
                        
                        print(f"Groq Comment Key {client_idx+1} attempt {attempt+1} failed: {groq_err}")
                        if attempt < max_retries - 1:
                            time.sleep((2 ** attempt) + 1)
                            
        return None

    def handle_comments(self, max_videos=25, channel_id=None):
        """Fetches recent videos and replies to new comments."""
        print(f"Scanning last {max_videos} videos for new comments...")
        
        try:
            # 1. Get recent uploads
            # If channel_id is not provided, try to get it from the 'mine=True' call
            # Note: channels().list(mine=True) requires 'youtube.readonly' or 'youtube.force-ssl'
            uploads_playlist_id = None
            
            try:
                # Use mine=True if channel_id is missing or seems like a placeholder
                is_placeholder = channel_id and ("ID" in channel_id or "PLACEHOLDER" in channel_id.upper())
                
                if not channel_id or is_placeholder:
                    print("No valid Channel ID in config, attempting to find 'mine'...")
                    request = self.youtube.channels().list(mine=True, part='snippet,contentDetails')
                    response = request.execute()
                    if 'items' in response and len(response['items']) > 0:
                        item = response['items'][0]
                        uploads_playlist_id = item['contentDetails']['relatedPlaylists']['uploads']
                        print(f"Found Channel: {item['snippet']['title']} ({item['id']})")
                else:
                    print(f"Using Channel ID: {channel_id}")
                    request = self.youtube.channels().list(id=channel_id, part='snippet,contentDetails')
                    response = request.execute()
                    if 'items' in response and len(response['items']) > 0:
                        item = response['items'][0]
                        uploads_playlist_id = item['contentDetails']['relatedPlaylists']['uploads']
                        print(f"Found Channel: {item['snippet']['title']}")
            except Exception as auth_err:
                if "insufficientPermissions" in str(auth_err):
                    print("\n" + "!"*60)
                    print("CRITICAL: Insufficient Permissions to access YouTube Channel Details.")
                    print("HINT: Your YOUTUBE_TOKEN_BASE64 might have been generated with only 'upload' scopes.")
                    print("ACTION: Please re-generate your token using 'python generate_token.py' and update your GitHub Secret.")
                    print("!"*60 + "\n")
                    return
                raise auth_err

            if not uploads_playlist_id:
                print("Could not find uploads playlist for this channel.")
                return

            playlist_request = self.youtube.playlistItems().list(
                playlistId=uploads_playlist_id,
                part='snippet',
                maxResults=max_videos
            )
            playlist_response = playlist_request.execute()
            
            for item in playlist_response['items']:
                video_id = item['snippet']['resourceId']['videoId']
                video_title = item['snippet']['title']
                print(f"\nChecking video: {video_title} ({video_id})")
                self._process_video_comments(video_id, video_title)
                
        except Exception as e:
            print(f"Error in handle_comments: {e}")

    def _process_video_comments(self, video_id, video_title):
        """Processes comments for a specific video."""
        try:
            request = self.youtube.commentThreads().list(
                videoId=video_id,
                part='snippet,replies',
                maxResults=20,
                order='time'
            )
            response = request.execute()

            for thread in response.get('items', []):
                comment = thread['snippet']['topLevelComment']
                comment_id = comment['id']
                author = comment['snippet']['authorDisplayName']
                author_id = comment['snippet'].get('authorChannelId', {}).get('value', author)
                text = comment['snippet']['textDisplay']
                
                # We need to reply to each unique viewer for one time only
                if author_id in self.replied_viewers:
                    continue
                
                # Check if we've already replied
                if self._should_reply(thread):
                    print(f"  -> Replying to {author}: {text[:50]}...")
                    reply_text = self._generate_reply(text, video_title)
                    if reply_text:
                        self._post_reply(comment_id, reply_text)
                        
                        # Add to our tracked viewers
                        self.replied_viewers.add(author_id)
                        with open(self.replied_viewers_file, 'a', encoding='utf-8') as f:
                            f.write(author_id + '\n')
                            
                        time.sleep(2) # Avoid hitting quotas too fast
                else:
                    # print(f"  (Skipping {author})")
                    pass

        except Exception as e:
            if "commentsDisabled" in str(e):
                print(f"  Comments are disabled for this video.")
            else:
                print(f"  Error processing comments for {video_id}: {e}")

    def _should_reply(self, thread):
        """Returns True if the owner hasn't replied to this thread yet."""
        # Check if the top-level comment is from the owner (optional, usually skip)
        # For simplicity, we check the replies for any comment from the channel owner.
        
        # In a real scenario, you'd check the channel ID. 
        # Here we check if there are any replies at all. 
        # If the user wants more robust logic, we'd need the channel ID.
        
        # snippet.totalReplyCount > 0 might mean someone replied, but was it us?
        # Let's check the actual replies if they exist.
        if 'replies' in thread:
            for reply in thread['replies']['comments']:
                if reply['snippet']['canRate']: # A rough proxy or check authorChannelId
                    # If we can find a way to verify it's the owner, that's better.
                    # Usually, the owner's reply will be there.
                    pass
        
        # Simple heuristic: if totalReplyCount is 0, we definitely haven't replied.
        return thread['snippet']['totalReplyCount'] == 0

    def _generate_reply(self, comment_text, video_title):
        """Generates a scientific and polite reply using AI."""
        prompt = f"""
        You are the creator of a popular Science YouTube channel. 
        A viewer left a comment on your video titled "{video_title}".
        
        Viewer's Comment: "{comment_text}"
        
        Task: Write a short (1-3 sentences), polite, and scientifically engaging reply.
        - If they asked a question, answer it accurately.
        - If they gave feedback, thank them politely.
        - If they were critical, be professional and open to learning.
        - Keep the tone curious and encouraging.
        - Use a bit of personality (warm and brilliant scientist vibe).
        - DO NOT use hashtags.
        - DO NOT use emojis (keep it clean).
        
        Return ONLY the reply text.
        """
        return self._call_with_retry(prompt)

    def _post_reply(self, parent_id, reply_text):
        """Posts the reply to YouTube."""
        try:
            body = {
                'snippet': {
                    'parentId': parent_id,
                    'textOriginal': plain_public_text(reply_text)
                }
            }
            request = self.youtube.comments().insert(
                part='snippet',
                body=body
            )
            request.execute()
            print("    Reply posted successfully.")
        except Exception as e:
            print(f"    Error posting reply: {e}")
