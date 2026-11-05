import os
import json
import asyncio
import random
from .base_pipeline import BasePipeline
from ..content.science_topic_generator import ScienceTopicGenerator
from ..content.script_writer import ScriptWriter
from ..media.image_fetcher import ImageFetcher
from ..media.video_fetcher import VideoFetcher
from ..media.tts import TTSEngine
from ..media.video_shorts import VideoShortsGenerator
from ..media.nasa_fetcher import NASAFetcher
from ..youtube.uploader import YouTubeUploader
from ..youtube.auth import YouTubeAuth
from ..media.srt_generator import generate_srt
from ..media.visual_quality import check_visual_quality

class SciencePipeline(BasePipeline):
    def __init__(self, config):
        super().__init__(config)
        self.script_writer = ScriptWriter(os.getenv("GEMINI_API_KEY"))
        self.topic_gen = ScienceTopicGenerator(
            config['storage']['posted_science'],
            config['topics']
        )
        self.image_fetcher = ImageFetcher()
        self.video_fetcher = VideoFetcher()
        t_v = config.get('tts_voice', {})
        self.tts = TTSEngine(
            voice_map=t_v, 
            rate=t_v.get('rate', "-5%"),
            pitch=t_v.get('pitch', "+0Hz"),
            allow_elevenlabs=False
        )
        self.vgen = VideoShortsGenerator()
        # Default science music volume to 0.04 as requested
        self.music_volume = config.get('branding', {}).get('music_volume', 0.04)
        self.nasa_fetcher = NASAFetcher()
        self.uploader = None # Initialized in run()
        self._video_asset_types = None

    def _get_punchy_title(self, hook_phrase: str, script: str, topic: str) -> str:
        """Generates a punchy YouTube title from the hook phrase and script's opening question."""
        import re
        # Find all sentences in script
        sentences = re.split(r'(?<=[.!?])\s+', script)
        question = ""
        for s in sentences:
            if '?' in s:
                question = s.strip()
                break
        if not question and sentences:
            question = sentences[0].strip()

        # Clean punctuation
        question = re.sub(r'[.!?]$', '', question).strip()
        words = question.split()
        
        # We need a 4-6 word hook
        hook_words = words[:6]
        one_sentence_hook = " ".join(hook_words)

        title_hook = str(hook_phrase).strip().title()
        title = f"{title_hook}: {one_sentence_hook}"

        # Cap at 60 characters
        if len(title) > 60:
            # Fall back to 4 words
            one_sentence_hook_short = " ".join(words[:4])
            title = f"{title_hook}: {one_sentence_hook_short}"
            if len(title) > 60:
                # Hard truncate
                title = title[:57] + "..."
        return title

    async def run(self, mode="shorts", is_test=False):
        print(f"--- Starting Science Pipeline [{mode}] for {self.config.get('channel_id')} ---")

        if mode == "shorts":
            topic = self.topic_gen.get_next_topic(self.script_writer)
            print(f"Topic: {topic}")
            await self._run_shorts(topic, is_test)
        elif mode == "daily":
            topic = self.topic_gen.get_next_topic(self.script_writer)
            print(f"Topic: {topic}")
            await self._run_daily(topic, is_test)
        elif mode == "social_post":
            # Doesn't use the video topic generator — Facebook/Instagram posts rotate
            # through their own content types (see _next_social_post_type below).
            await self._run_social_post(is_test)

        # Cleanup temporary files
        self.cleanup_storage()
        print(f"--- Science Pipeline [{mode}] Completed ---")

    async def _run_shorts(self, topic: str, is_test: bool):
        # 2. Generate Script
        categories = ["General", "Did You Know?", "What If?"]
        category = random.choice(categories)
        print(f"Selected Category: {category}")
        
        prompt_topic = topic
        if category == "Did You Know?":
            prompt_topic = f"Did you know {topic}?"
        elif category == "What If?":
            prompt_topic = f"What if {topic}?"
            
        script = self.script_writer.generate_science_facts(prompt_topic)
        print(f"Short Script generated ({category}).")

        # 3. Generate Visual Scene Manifest for Shorts
        print("Generating Shorts visual scene manifest...")
        visual_scenes = self.script_writer.generate_shorts_visual_scenes(prompt_topic, script)
        if not isinstance(visual_scenes, list):
            visual_scenes = []
        print(f"Visual scenes: {len(visual_scenes)} scenes generated.")

        # 4. Fetch All Assets via Orchestrator (Portrait Mode)
        asset_manifest = None
        if visual_scenes:
            from ..media.asset_orchestrator import AssetOrchestrator
            orchestrator = AssetOrchestrator(hf_token=os.getenv("HF_TOKEN", ""))
            asset_manifest = orchestrator.fetch_all(visual_scenes, prompt_topic, aspect_ratio="9:16")
            self._video_asset_types = [s.get("asset_type") for s in asset_manifest["scenes"]]
            check_visual_quality(asset_manifest, is_test=is_test)
            print(f"Asset manifest ready: job_id={asset_manifest.get('job_id')}, "
                  f"{len(asset_manifest.get('scenes', []))} scenes.")
        else:
            print("WARNING: No visual scenes generated. Cannot proceed with premium Shorts render.")
            # Fallback legacy path
            media_paths = await self._fetch_media(prompt_topic, script)

        # 5. Generate Audio
        male_voice = self.config.get('tts_voice', {}).get('male', "en-US-GuyNeural")
        audio_path = "automation/storage/science_shorts_temp.mp3"
        _, word_offsets = await self.tts.generate_audio(script, audio_path, voice=male_voice)

        # 6. Create Video
        video_path = "automation/storage/science_shorts_final.mp4"
        try:
            if asset_manifest:
                print(f"DEBUG: Rendering Shorts via visual scene manifest ({len(asset_manifest['scenes'])} scenes).")
                self.vgen.create_shorts_from_scenes(
                    asset_manifest=asset_manifest,
                    audio_path=audio_path,
                    output_path=video_path,
                    word_offsets=word_offsets,
                    branding=self.config.get('branding'),
                    topic=prompt_topic,
                )
            else:
                print(f"DEBUG: Rendering Shorts via legacy path with {len(media_paths)} media items.")
                self.vgen.create_shorts(
                    script,
                    audio_path,
                    video_path,
                    word_offsets=word_offsets,
                    media_paths=media_paths,
                    branding=self.config.get('branding'),
                )

            if os.path.exists(video_path):
                print(f"DEBUG: Science Shorts created successfully at {video_path}")
            else:
                print(f"CRITICAL: Science Shorts creation executed but file missing: {video_path}")
        except Exception as e:
            print(f"CRITICAL ERROR in create_shorts: {e}")
            import traceback
            traceback.print_exc()
            raise e

        # 7. Generate Portrait Thumbnail
        print("Generating portrait (1080×1920) thumbnail for Shorts...")
        thumb_path = None
        thumb_info = {}
        try:
            from ..media.thumbnail_generator import ThumbnailGenerator
            thumb_gen = ThumbnailGenerator(size=(1080, 1920))
            # generate_thumbnail_info reads self.last_thumbnail_data cached by generate_shorts_visual_scenes
            thumb_info = self.script_writer.generate_thumbnail_info(prompt_topic, script)
            
            first_asset_path = None
            if asset_manifest and asset_manifest.get('scenes'):
                first_asset_path = asset_manifest['scenes'][0].get('asset_path')
                
            thumb_path = thumb_gen.generate_thumbnail(thumb_info, first_asset_path=first_asset_path)
            print(f"Portrait thumbnail generated: {thumb_path}")
        except Exception as te:
            print(f"WARNING: Thumbnail generation failed: {te}")

        # 8. Build punchy title from thumbnail hook phrase
        hook_phrase = thumb_info.get('hook_phrase', '') if isinstance(thumb_info, dict) else ''
        if hook_phrase:
            yt_title = self._get_punchy_title(hook_phrase, script, topic)
        else:
            yt_title = f"{topic} #Shorts"
        print(f"YouTube Shorts title: {yt_title}")

        # 9. Upload
        video_id = await self._upload(video_path, yt_title, script, topic, is_test=is_test)

        # Meta Upload
        if not is_test:
            print("Triggering Meta Reels cross-posting...")
            try:
                from ..meta.uploader import MetaUploader
                meta_uploader = MetaUploader()
                meta_uploader.upload_video(video_path, yt_title, script, tags=["shorts"])
            except Exception as me:
                print(f"WARNING: Meta Reel cross-posting failed: {me}")

        # 10. Upload Thumbnail
        if video_id and thumb_path and os.path.exists(thumb_path) and not is_test:
            print(f"Uploading portrait thumbnail for video {video_id}...")
            try:
                self.uploader.upload_thumbnail(video_id, thumb_path)
            except Exception as ute:
                print(f"WARNING: Thumbnail upload failed: {ute}")


    def _build_chapters(self, scene_timings: list, scenes: list) -> str:
        """
        Builds a YouTube-compliant chapter list ("00:00 Title" per line) from the
        rendered scene timings. Chapters give viewers a visible roadmap in the
        progress bar/description, which reduces "is this worth my time" drop-off
        early in long-form videos. YouTube requires: first chapter at 0:00, at
        least 3 chapters, each >= 10s.
        """
        if not scene_timings or not scenes or len(scene_timings) != len(scenes):
            return ""

        def fmt(t):
            t = max(0, int(t))
            h, rem = divmod(t, 3600)
            m, s = divmod(rem, 60)
            return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

        def title_for(scene):
            for key in ("emphasis_phrase", "question_text", "named_entity"):
                val = scene.get(key)
                if val:
                    words = str(val).replace("*", "").strip().split()
                    if words:
                        return " ".join(w.capitalize() for w in words[:6])
            narration = str(scene.get("narration", "")).replace("*", "").strip()
            words = narration.split()
            return " ".join(words[:6]).capitalize() if words else "Deep Dive"

        chapters = []
        last_start = -100
        for scene, timing in zip(scenes, scene_timings):
            start = timing.get("start", 0)
            if start - last_start < 10 and chapters:
                continue  # merge into previous chapter, YouTube requires >=10s spacing
            chapters.append((start, title_for(scene)))
            last_start = start

        if len(chapters) < 3:
            return ""

        chapters[0] = (0, chapters[0][1])
        lines = [f"{fmt(t)} {title}" for t, title in chapters]
        return "\n".join(lines)

    async def _run_daily(self, topic: str, is_test: bool):
        # 2. Generate Expanded Script (plain text for TTS — unchanged)
        script = self.script_writer.expand_science_script(topic)
        print(f"Expanded Script generated (~{len(script.split())} words).")

        # 3. Generate Visual Scenes (structured JSON for visual routing)
        print("Generating visual scene classification...")
        scenes_data = self.script_writer.generate_visual_scenes(topic, script)

        # 4. Fetch All Assets via Orchestrator
        asset_manifest = None
        if scenes_data:
            from ..media.asset_orchestrator import AssetOrchestrator
            orchestrator = AssetOrchestrator(hf_token=os.getenv("HF_TOKEN", ""))
            asset_manifest = orchestrator.fetch_all(scenes_data, topic)
            self._video_asset_types = [s.get("asset_type") for s in asset_manifest["scenes"]]
            check_visual_quality(asset_manifest, is_test=is_test)
            print(f"Asset manifest ready: job_id={asset_manifest.get('job_id')}, "
                  f"{len(asset_manifest.get('scenes', []))} scenes.")
        else:
            print("WARNING: No visual scenes generated. Falling back to image-only pipeline.")

        # 5. Fetch fallback media_paths (used if asset_manifest failed entirely)
        media_paths = None
        if not asset_manifest:
            media_paths = await self._fetch_media(topic, script, count_per_kw=2, is_long_form=True)

        # 6. Generate Audio
        male_voice = self.config.get('tts_voice', {}).get('male', "en-US-GuyNeural")
        audio_path = "automation/storage/science_long_temp.mp3"
        _, word_offsets = await self.tts.generate_audio(script, audio_path, voice=male_voice)

        # 7. Create Long Video
        segments = [{"type": "science", "text": script, "topic": topic}]
        video_path = "automation/storage/science_long_final.mp4"

        from ..media.video_long import VideoLongGenerator
        vgen_long = VideoLongGenerator()
        vgen_long.create_daily_summary(
            segments,
            audio_path,
            video_path,
            word_offsets,
            media_paths=media_paths,
            asset_manifest=asset_manifest,
            # Burn captions directly into the frame. Most viewers watch muted/on mobile
            # and never toggle CC — an uploaded SRT alone was invisible to ~99% of viewers,
            # which was silently killing retention on the long-form videos.
            burn_captions=True,
        )

        # Retain the job manifest/assets for thumbnail extraction and workflow review.
        # Generated provider clips live in their separate reusable cache.

        # 9. Generate SRT captions
        srt_path = "automation/storage/science_long.srt"
        generate_srt(word_offsets, srt_path)

        # 10. Generate Thumbnail
        print("Generating automated thumbnail...")
        from ..media.thumbnail_generator import ThumbnailGenerator
        thumb_gen = ThumbnailGenerator()
        thumb_info = scenes_data if scenes_data and 'thumbnail_data' in scenes_data else self.script_writer.generate_thumbnail_info(topic, script)
        
        first_asset_path = None
        if asset_manifest and asset_manifest.get('scenes'):
            first_asset_path = asset_manifest['scenes'][0].get('asset_path')
            
        thumb_path = thumb_gen.generate_thumbnail(thumb_info, first_asset_path=first_asset_path)

        # 11. Build punchy title from thumbnail hook phrase
        daily_hook_phrase = ''
        if isinstance(thumb_info, dict):
            daily_hook_phrase = thumb_info.get('hook_phrase', '')
        if daily_hook_phrase:
            yt_title_daily = self._get_punchy_title(daily_hook_phrase, script, topic)
        else:
            yt_title_daily = f"The Science of {topic}: Explained"
        print(f"YouTube Daily title: {yt_title_daily}")

        # 12. Upload (with chapters built from the actual rendered scene timings —
        # gives viewers a visible roadmap and reduces early "is this worth it" drop-off)
        chapters = ""
        if hasattr(vgen_long, "scene_timings") and hasattr(vgen_long, "scenes"):
            chapters = self._build_chapters(vgen_long.scene_timings, vgen_long.scenes)

        if True:
            video_id = await self._upload(
                video_path,
                yt_title_daily,
                script, topic,
                is_test=is_test, is_shorts=False, srt_path=srt_path,
                chapters=chapters,
            )

            # Meta Upload
            if not is_test:
                print("Triggering Meta video cross-posting...")
                try:
                    from ..meta.uploader import MetaUploader
                    meta_uploader = MetaUploader()
                    meta_uploader.upload_video(video_path, yt_title_daily, script, tags=["science"])
                except Exception as me:
                    print(f"WARNING: Meta video cross-posting failed: {me}")

            # 13. Upload Thumbnail if video succeeded
            if video_id and thumb_path and os.path.exists(thumb_path) and not is_test:
                print(f"Uploading thumbnail for video {video_id}...")
                self.uploader.upload_thumbnail(video_id, thumb_path)



    _SOCIAL_POST_TYPES = ["discovery", "breaking_news", "myth_bust", "fun_fact"]
    _SOCIAL_QUEUE_PATH = "automation/storage/social_post_queue.json"
    _SOCIAL_HISTORY_PATH = "automation/storage/posted_social.json"

    def _next_social_post_type(self) -> str:
        """Round-robin through the 4 post types (same pattern as
        ScienceTopicGenerator's category rotation) so every type gets equal air time
        across the day's 4 posts instead of drifting toward whatever random.choice()
        happens to favor."""
        queue = []
        if os.path.exists(self._SOCIAL_QUEUE_PATH):
            try:
                with open(self._SOCIAL_QUEUE_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, list) and loaded and all(t in self._SOCIAL_POST_TYPES for t in loaded):
                    queue = loaded
            except Exception:
                pass
        if not queue:
            queue = list(self._SOCIAL_POST_TYPES)
            random.shuffle(queue)
        post_type = queue.pop(0)
        os.makedirs(os.path.dirname(self._SOCIAL_QUEUE_PATH), exist_ok=True)
        with open(self._SOCIAL_QUEUE_PATH, "w", encoding="utf-8") as f:
            json.dump(queue, f)
        return post_type

    def _load_social_history(self) -> list:
        if os.path.exists(self._SOCIAL_HISTORY_PATH):
            try:
                with open(self._SOCIAL_HISTORY_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_social_history(self, topic: str):
        history = self._load_social_history()
        history.append(topic)
        os.makedirs(os.path.dirname(self._SOCIAL_HISTORY_PATH), exist_ok=True)
        with open(self._SOCIAL_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    async def _run_social_post(self, is_test: bool):
        """Generates and posts one text+photo update to Facebook/Instagram: a science
        discovery, real breaking news, a myth-bust, or a fun fact (rotating daily)."""
        from ..content.news_fetcher import fetch_recent_headlines
        from ..media.watermark import add_watermark
        from ..media.visual_relevance import is_visually_relevant

        post_type = self._next_social_post_type()
        print(f"Social post type: {post_type}")

        # Ground breaking_news / myth_bust in real, recent headlines (Google News RSS —
        # free, no key). Can't detect "what's trending on social media right now"
        # specifically without a paid trends API, but this keeps both categories
        # anchored to real current coverage instead of pure LLM invention.
        headlines = []
        if post_type == "breaking_news":
            headlines = fetch_recent_headlines("science discovery breakthrough research", count=6)
        elif post_type == "myth_bust":
            headlines = fetch_recent_headlines("science myth debunked fact check", count=6, when="7d")

        recent_history = self._load_social_history()
        content = self.script_writer.generate_social_post(
            post_type, headlines=headlines, recent_history=recent_history
        )
        caption = content.get("caption", "")
        if not caption:
            print("Social post generation failed on all providers — skipping this run without posting.")
            return

        image_query = content.get("image_query") or "science abstract background"
        topic_label = content.get("topic") or post_type
        print(f"Post topic: {topic_label}")
        print(f"Caption:\n{caption}")

        # Real photo first (NASA/Pexels/Pixabay/DDG, same fallback chain the video
        # pipeline uses), AI-generated only if nothing relevant turns up.
        candidates = self.image_fetcher.fetch_multi_images(
            [f"{image_query} cinematic 4k", f"{image_query} photo"],
            base_filename="social_post",
            topic_context=image_query,
        )
        chosen_image = None
        for path in candidates[:3]:
            if is_visually_relevant(path, caption):
                chosen_image = path
                break
        if not chosen_image and candidates:
            print("None of the fetched images passed the relevance check — using the best available anyway "
                  "rather than posting nothing.")
            chosen_image = candidates[0]
        if not chosen_image:
            print("No image could be fetched or generated for this post — skipping.")
            return

        watermarked_path = add_watermark(chosen_image, "@dailydeepspace")

        if is_test:
            print(f"TEST MODE: Skipping Meta post. Image: {watermarked_path}")
        else:
            from ..meta.uploader import MetaUploader
            meta_uploader = MetaUploader()
            meta_uploader.upload_photo_post(watermarked_path, caption)

        self._save_social_history(topic_label)

    async def _fetch_media(self, topic, script, count_per_kw=1, is_long_form=False):
        print(f"Fetching multi-segment media (long_form={is_long_form})...")
        keywords_list = self.script_writer.generate_image_keywords(script, extra_context=topic, is_long_form=is_long_form)
        media_paths = []
        
        # Fetching images for all keywords
        # Generating a mix of "cinematic", "macro", "detailed" searches
        combined_keywords = []
        for kw in keywords_list:
            # Variety of search modifiers
            combined_keywords.append(f"{kw} cinematic 4k")
            if is_long_form:
                combined_keywords.append(f"{kw} close up macro")
            
        print(f"Fetching {len(combined_keywords)} potential images for Science content...")
        img_paths = self.image_fetcher.fetch_multi_images(combined_keywords, "science_temp", topic_context=topic)
        media_paths.extend(img_paths)
        
        return media_paths

    async def _upload(self, video_path, title, script, topic, is_test=False, is_shorts=True, srt_path=None, chapters=""):
        if is_test:
            print(f"TEST MODE: Skipping upload for {title}")
            print(f"--- Science Pipeline Completed ---")
            return "test_video_id"

        if self._video_asset_types is not None and not any(
                kind in ('video', 'ai_video') for kind in self._video_asset_types):
            raise RuntimeError('Visual quality hold: no moving footage in this render. '
                               'Configure video generation or add reviewed visual-bank clips before publishing.')

        print("Initializing YouTube service...")
        youtube_service = YouTubeAuth.get_service(os.getenv("YOUTUBE_TOKEN_BASE64"))
        self.uploader = YouTubeUploader(youtube_service)

        hashtags = self.config.get('hashtags', "#science #facts #universe")
        cta = "\n\n🔔 Subscribe for more mind-bending science, twice a week.\n👍 If this blew your mind, drop a like — it tells YouTube to show it to more people."
        description_parts = [script, cta]
        if chapters:
            description_parts.append(f"\n\nCHAPTERS:\n{chapters}")
        description_parts.append(f"\n\n#Science #Education {hashtags}")
        description = "".join(description_parts)
        tags = ["science", "facts", "universe", "space", "educational"]
        if is_shorts: tags.append("shorts")
        
        video_id = None
        print(f"Uploading: {title}")
        video_id = self.uploader.upload_video(video_path, title, description, tags)
        
        # If we have an SRT file, upload it as captions
        if video_id and srt_path and os.path.exists(srt_path):
            print(f"Uploading captions from {srt_path}...")
            try:
                self.uploader.upload_caption(video_id, srt_path)
            except Exception as e:
                print(f"WARNING: Caption upload failed: {e}")
                print("This might be due to insufficient authentication scopes (youtube.force-ssl required).")
        
        print(f"--- Science Pipeline Completed ---")
        return video_id
