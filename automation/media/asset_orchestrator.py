import os
import json
import uuid
import datetime
import hashlib
from typing import List, Dict

from .video_generation import VideoGenerator
from .motion_graphics import engine_ready, validate_animation
from .image_fetcher import ImageFetcher
from . import stock_media
from . import visual_relevance

MAX_STOCK_VIDEO_PER_JOB = 40  # Per-video cap to keep download/render time bounded
RELEVANCE_CHECK_ENABLED = os.getenv("DISABLE_VISUAL_RELEVANCE_CHECK", "").strip().lower() not in ("1", "true", "yes")
MAX_RELEVANCE_CHECKS_PER_SCENE = 3  # bound latency/Gemini-quota usage per scene


class AssetOrchestrator:
    """
    Routes visual scenes to the correct asset generator and writes a
    job-scoped asset_manifest.json to automation/storage/temp_videos/{job_id}/.

    Supports resume: if a manifest already exists for the same topic+date,
    it re-uses it instead of re-fetching all assets.
    """

    def __init__(self, hf_token: str = None):
        self.hf_token = hf_token or os.getenv("HF_TOKEN", "")
        self.image_fetcher = ImageFetcher()
        self.video_generator = VideoGenerator()
        self._used_assets = set()
        self._verification_unavailable = False

    # ── Public API ─────────────────────────────────────────────────────────────

    def fetch_all(self, scenes: List[Dict], topic: str, aspect_ratio: str = '16:9') -> dict:
        """
        Process all scenes and return the full job manifest dict with all 6 visual types.
        """
        self._used_assets.clear()
        self._verification_unavailable = False
        today = datetime.date.today().isoformat()
        plan_hash = hashlib.sha256(json.dumps([scenes, self.video_generator.provider, self.video_generator.model, self.video_generator.limit, os.getenv("LOCAL_VISUAL_RELEVANCE", ""), "cpu-matching-v1", engine_ready(), "remotion-v1"], sort_keys=True).encode()).hexdigest()

        # ── Resume support: check for existing manifest ────────────────────────
        existing = self._find_existing_manifest(topic, today)
        if existing and existing.get("aspect_ratio") == aspect_ratio and existing.get("plan_hash") == plan_hash and len(existing.get("scenes", [])) == len(scenes):
            print(f"[AssetOrchestrator] Resuming from existing manifest: {existing['job_id']}")
            return existing

        # ── New job ────────────────────────────────────────────────────────────
        job_id = str(uuid.uuid4())[:12]
        job_dir = os.path.join("automation", "storage", "temp_videos", job_id)
        os.makedirs(job_dir, exist_ok=True)

        manifest = {
            "job_id": job_id,
            "plan_hash": plan_hash,
            "job_dir": job_dir,
            "topic": topic,
            "date": today,
            "aspect_ratio": aspect_ratio,
            "scenes": [],
        }

        ai_video_count = 0    # Per-video budget tracker
        stock_video_count = 0  # Real stock-video b-roll budget tracker

        for idx, scene in enumerate(scenes):
            visual_type = scene.get("visual_type", "image")
            narration = scene.get("narration", "")
            image_cue = scene.get("image_cue")
            if not image_cue or image_cue == "None":
                # Generic fallback — previously hardcoded "{topic} space astronomy" here, which
                # meant any scene missing an image_cue (regardless of the video's actual subject —
                # chemistry, biology, neuroscience...) silently searched for space photos instead.
                image_cue = f"{topic} science"
            
            ai_video_prompt = scene.get("ai_video_prompt", "")

            # ── Schema Defaults & Downgrades ──────────────────────────────────
            if visual_type == "kinetic_stat" and not scene.get("stat_data"):
                print(f"[AssetOrchestrator] Scene {idx}: Downgrading kinetic_stat to typewriter_text due to missing stat_data")
                visual_type = "typewriter_text"
            if visual_type == "data_bars" and not scene.get("bar_data"):
                print(f"[AssetOrchestrator] Scene {idx}: Downgrading data_bars to typewriter_text due to missing bar_data")
                visual_type = "typewriter_text"

            emphasis_phrase = scene.get("emphasis_phrase")
            if not emphasis_phrase or emphasis_phrase == "None":
                emphasis_phrase = scene.get("question_text", "")[:20] if scene.get("question_text") else ""

            typewriter_words = scene.get("typewriter_words")
            if not typewriter_words:
                typewriter_words = [{"word": w, "weight": "md"} for w in narration.split()]

            scene_entry = {
                "scene_idx": idx,
                "visual_type": visual_type,
                "asset_type": "none",
                "asset_path": None,
                "narration": narration,
                "image_cue": image_cue,
                # Store all custom fields for the 6 styles
                "typewriter_words": typewriter_words,
                "stat_data": scene.get("stat_data"),
                "named_entity": scene.get("named_entity"),
                "ai_video_prompt": ai_video_prompt,
                "question_text": scene.get("question_text"),
                "emphasis_phrase": emphasis_phrase,
                "bar_data": scene.get("bar_data"),
                "animation": scene.get("animation")
            }

            if visual_type == 'animation':
                spec = validate_animation(scene.get('animation'), narration, topic)
                if spec and engine_ready():
                    if spec['template'] == 'photo':
                        photos = stock_media.fetch_real_photos(image_cue, 3, job_dir,
                            f'animation_{idx}', portrait=(aspect_ratio == '9:16'))
                        photo = self._pick_relevant_asset(photos, narration)
                        if photo:
                            scene_entry['asset_path'] = photo
                        else:
                            spec = None
                    if spec:
                        scene_entry.update(asset_type='animation', animation=spec,
                            source={'provider': 'Remotion', 'kind': 'authored explanatory graphic'})
                        manifest['scenes'].append(scene_entry)
                        self._save_manifest(manifest)
                        continue
                print(f'[AssetOrchestrator] Scene {idx}: animation unavailable/invalid; trying media.')
                visual_type = 'image'
                scene_entry['visual_type'] = 'image'

            if self._verification_unavailable:
                self._use_explainer_card(scene_entry, topic, job_dir, aspect_ratio)
                manifest["scenes"].append(scene_entry)
                self._save_manifest(manifest)
                continue

            # Explicit planned illustrations use hosted providers; never the retired HF endpoint.
            if visual_type == 'ai_video':
                if self._use_generated_video(scene_entry, topic, aspect_ratio):
                    ai_video_count += 1
                    manifest["scenes"].append(scene_entry)
                    self._save_manifest(manifest)
                    continue
                visual_type = 'image'
                scene_entry['visual_type'] = 'image'

            # Description used for the AI relevance check and, if needed, the AI-image
            # fallback below — the actual narration is far more specific than the
            # (sometimes garbled, e.g. from the bare-fallback scene builder) search
            # query used to fetch candidates in the first place.
            relevance_desc = narration.strip() or image_cue

            # Real stock-video b-roll for plain "image" scenes — an actual moving clip
            # that matches the subject beats a static Ken-Burns photo, and Pexels/Pixabay
            # are official APIs (not scraping), so this doesn't add DDG rate-limit risk.
            # Skipped entirely (falls through to the image fetch below) when no API key
            # is configured, or once the per-job budget is used up.
            if (visual_type == "image" and stock_media.has_stock_api_keys()
                    and stock_video_count < MAX_STOCK_VIDEO_PER_JOB):
                print(f"[AssetOrchestrator] Scene {idx}: trying real stock-video b-roll for '{image_cue}'...")
                video_candidates = stock_media.fetch_real_videos(
                    image_cue, MAX_RELEVANCE_CHECKS_PER_SCENE, job_dir, f"job_{job_id}_scene{idx}",
                    portrait=(aspect_ratio == "9:16"),
                )
                chosen_video = self._pick_relevant_asset(video_candidates, relevance_desc)
                if self._verification_unavailable:
                    self._use_explainer_card(scene_entry, topic, job_dir, aspect_ratio)
                    manifest["scenes"].append(scene_entry)
                    self._save_manifest(manifest)
                    continue
                if chosen_video:
                    asset_path = chosen_video
                    if aspect_ratio == "9:16":
                        asset_path = self._crop_video_to_portrait(asset_path)
                    scene_entry["asset_type"] = "video"
                    scene_entry["asset_path"] = asset_path
                    stock_video_count += 1
                    manifest["scenes"].append(scene_entry)
                    self._save_manifest(manifest)
                    continue
                elif video_candidates:
                    print(f"[AssetOrchestrator] Scene {idx}: none of {len(video_candidates)} stock video "
                          f"candidate(s) passed the relevance check for '{relevance_desc[:60]}...' — trying images.")

            # Fetch background image for all other scene types to draw overlay styles on top of
            print(f"[AssetOrchestrator] Scene {idx}: fetching background image for type '{visual_type}'...")
            # Second query used to always append "space astronomy" regardless of topic, which
            # dragged every non-space scene (chemistry, biology, psychology...) toward irrelevant
            # deep-space b-roll. Use a topic-neutral second phrasing instead.
            queries = [
                image_cue,
                f"{image_cue} photo",
            ]
            # Sleep slightly to avoid DDG rate limits between scenes
            if idx > 0:
                import time
                time.sleep(2.5)
            # Official stock APIs preserve a clear license trail; no web-image scraping.
            paths = [] if self._verification_unavailable else stock_media.fetch_real_photos(
                image_cue, MAX_RELEVANCE_CHECKS_PER_SCENE, job_dir,
                f"job_{job_id}_scene{idx}", portrait=(aspect_ratio == "9:16"))
            chosen_image = self._pick_relevant_asset(paths, relevance_desc)
            if not chosen_image and paths:
                # Every fetched candidate failed the relevance check — generate one
                # with AI from the actual narration instead of using a real photo we
                # already determined doesn't match the script.
                print(f"[AssetOrchestrator] Scene {idx}: none of {len(paths)} image candidate(s) passed the "
                      f"relevance check for '{relevance_desc[:60]}...' — no verified stock image available.")
                chosen_image = self._generate_relevant_ai_image(relevance_desc, f"job_{job_id}_scene{idx}_ai")
            if chosen_image:
                asset_path = chosen_image
                if aspect_ratio == "9:16":
                    asset_path = self._crop_image_to_portrait(asset_path)
                scene_entry["asset_type"] = "image"
                scene_entry["asset_path"] = asset_path
            else:
                scene_entry["asset_type"] = "none"
                scene_entry["asset_path"] = None

            if not scene_entry["asset_path"]:
                self._use_explainer_card(scene_entry, topic, job_dir, aspect_ratio)
            source_path = (scene_entry.get("asset_path") or "") + ".source.json"
            if os.path.isfile(source_path):
                with open(source_path, encoding="utf-8") as credit:
                    scene_entry["source"] = json.load(credit)
            manifest["scenes"].append(scene_entry)
            self._save_manifest(manifest)

        ai_video_count = sum(s["asset_type"] == "ai_video" for s in manifest["scenes"])
        print(f"[AssetOrchestrator] Job {job_id} complete. "
              f"{ai_video_count} AI video clip(s), "
              f"{stock_video_count} real stock-video clip(s), "
              f"{sum(s['asset_type'] == 'animation' for s in manifest['scenes'])} explanatory animation(s), "
              f"{sum(1 for s in manifest['scenes'] if s['asset_type']=='image')} image background(s).")
        return manifest

    def _crop_image_to_portrait(self, img_path: str) -> str:
        try:
            from PIL import Image
            img = Image.open(img_path).convert("RGB")
            w, h = img.size
            target_w = int(h * 9 / 16)
            if target_w < w:
                x_offset = (w - target_w) // 2
                img = img.crop((x_offset, 0, x_offset + target_w, h))
            img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
            img.save(img_path)
            return img_path
        except Exception as e:
            print(f"[AssetOrchestrator] Error cropping image {img_path}: {e}")
            return img_path

    def _crop_video_to_portrait(self, vid_path: str) -> str:
        try:
            from moviepy.editor import VideoFileClip
            clip = VideoFileClip(vid_path)
            w, h = clip.size
            target_w = int(h * 9 / 16)
            if target_w < w:
                x1 = (w - target_w) // 2
                clip = clip.crop(x1=x1, y1=0, x2=x1+target_w, y2=h)
            clip = clip.resize(newsize=(1080, 1920))
            new_path = vid_path.replace(".mp4", "_portrait.mp4")
            clip.write_videofile(new_path, codec="libx264", audio=False, logger=None)
            clip.close()
            return new_path
        except Exception as e:
            print(f"[AssetOrchestrator] Error cropping video {vid_path}: {e}")
            return vid_path

    def cleanup(self, manifest: dict):
        """Delete the entire temp/{job_id}/ directory after a successful render."""
        job_dir = manifest.get("job_dir", "")
        if job_dir and os.path.isdir(job_dir):
            import shutil
            shutil.rmtree(job_dir, ignore_errors=True)
            print(f"[AssetOrchestrator] Cleaned up temp dir: {job_dir}")

    # ── Internals ──────────────────────────────────────────────────────────────

    def _pick_relevant_asset(self, candidates: List[str], description: str) -> str | None:
        """
        Returns the first candidate (image or video path) that an AI relevance check
        confirms plausibly matches `description` (the scene's actual narration —
        far more specific than the search query that fetched these candidates).
        Checks at most MAX_RELEVANCE_CHECKS_PER_SCENE candidates to bound latency and
        Gemini quota usage. Returns None if none of the checked candidates pass —
        callers should fall back to AI image generation in that case.
        """
        if not candidates:
            return None
        if not RELEVANCE_CHECK_ENABLED or not description:
            return candidates[0]
        for path in candidates[:MAX_RELEVANCE_CHECKS_PER_SCENE]:
            with open(path, "rb") as asset:
                digest = hashlib.sha256(asset.read()).hexdigest()
            if digest in self._used_assets:
                continue
            try:
                relevant = visual_relevance.is_visually_relevant(path, description, strict=True)
            except visual_relevance.VerificationUnavailable:
                self._verification_unavailable = True
                print('[AssetOrchestrator] Remote vision unavailable: using labeled script-summary cards.')
                return None
            if relevant:
                self._used_assets.add(digest)
                return path
        return None

    def _use_generated_video(self, entry, topic, aspect_ratio):
        result = self.video_generator.generate(entry, topic, aspect_ratio)
        if not result:
            return False
        entry.update(visual_type='ai_video', asset_type='ai_video', **result)
        print(f"[AssetOrchestrator] Scene {entry['scene_idx']}: hosted AI illustration ready.")
        return True

    def _use_explainer_card(self, entry, topic, job_dir, aspect_ratio):
        if entry.get('visual_type') in ('image', 'ai_video') and self._use_generated_video(entry, topic, aspect_ratio):
            return
        from .explainer_card import create_explainer_card
        path = os.path.join(job_dir, f"scene_{entry['scene_idx']}_explainer.png")
        entry.update(visual_type='explainer_card', asset_type='image',
                     asset_path=create_explainer_card(entry, topic, path, aspect_ratio == '9:16'),
                     source={'provider': 'local script summary', 'photographic_evidence': False})

    def _generate_relevant_ai_image(self, description: str, base_filename: str) -> str | None:
        """Last resort when no fetched photo/video passes the relevance check: generate
        one with Pollinations.ai using the scene's actual narration as the prompt,
        rather than falling back to a generic/possibly-irrelevant real photo."""
        if os.getenv("ALLOW_GENERATED_ILLUSTRATIONS", "").lower() != "true":
            return None
        try:
            paths = self.image_fetcher._generate_pollinations_images(description, base_filename, count=1)
            return paths[0] if paths else None
        except Exception as e:
            print(f"[AssetOrchestrator] AI relevance-fallback image generation failed: {e}")
            return None

    def _save_manifest(self, manifest: dict):
        path = os.path.join(manifest["job_dir"], "manifest.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    def _find_existing_manifest(self, topic: str, date: str) -> dict | None:
        """
        Search all existing job dirs for a manifest matching topic+date.
        Returns the manifest if found and all asset_paths still exist on disk.
        """
        base = os.path.join("automation", "storage", "temp_videos")
        if not os.path.isdir(base):
            return None
        for job_id in os.listdir(base):
            manifest_path = os.path.join(base, job_id, "manifest.json")
            if not os.path.exists(manifest_path):
                continue
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    m = json.load(f)
                if m.get("topic") == topic and m.get("date") == date:
                    # Verify all file-backed assets still exist
                    all_ok = all(
                        s["asset_path"] is None or os.path.exists(s["asset_path"])
                        for s in m.get("scenes", [])
                    )
                    if all_ok:
                        return m
            except Exception:
                continue
        return None
