from moviepy.editor import TextClip, ColorClip, CompositeVideoClip, AudioFileClip, ImageClip, VideoFileClip, afx, vfx
import os
import sys
import glob
import random
import re
from PIL import Image, ImageDraw, ImageFont
import numpy as np

class VideoShortsGenerator:
    def __init__(self, size=(1080, 1920)):
        self.size = size

    def create_shorts(self, text: str, audio_path: str, output_path: str, word_offsets: list = None, media_paths: list = None, branding: dict = None, template_mode: bool = False):

        print(f"DEBUG: START create_shorts. Output: {output_path}")
        sys.stdout.flush()
        """
        media_paths can contain both image and video file paths.
        branding: dict with keys like 'accent_color', 'bg_color', 'music_volume', 'logo_path', 'channel_name'
        """
        audio = AudioFileClip(audio_path)
        duration = audio.duration
        bg_clips = []
        
        # Branding defaults
        accent = (branding or {}).get('accent_color', 'yellow')
        bg_overlay_color = (branding or {}).get('bg_color', (0,0,0))
        # Default background music volume
        music_vol = (branding or {}).get('music_volume', 0.03)
        logo_path = (branding or {}).get('logo_path', "automation/media/assets/nepal_now_logo.png")
        channel_name = (branding or {}).get('channel_name', "Nepal Now")
        
        # Initialize SFX container
        self.sfx_clips = []

        if template_mode:

            # 1. Base Layer (Background Color)
            bg_color = (branding or {}).get('bg_color', (15, 25, 45))
            bg_clips.append(ColorClip(size=self.size, color=bg_color, duration=duration))
            
            # 2. Anchor Layer (Full Screen)
            anchor_video_path = (branding or {}).get('anchor_video_path')

            anchor_added = False
            if anchor_video_path and os.path.exists(anchor_video_path):
                print(f"Adding AI Anchor video: {anchor_video_path}")
                anchor_clip = VideoFileClip(anchor_video_path)
                anchor_clip = anchor_clip.resize(height=1920)
                anchor_clip = anchor_clip.set_position('center')
                if anchor_clip.duration < duration:
                    anchor_clip = anchor_clip.fx(vfx.loop, duration=duration)
                else:
                    anchor_clip = anchor_clip.subclip(0, duration)
                bg_clips.append(anchor_clip)
                anchor_added = True
            elif os.path.exists("automation/media/assets/anchor_nepali.png") and not "science" in str(channel_name).lower():
                print("Using static AI Anchor fallback (Full Screen).")
                anchor_img = ImageClip("automation/media/assets/anchor_nepali.png").set_duration(duration)
                anchor_img = anchor_img.resize(height=1920)
                anchor_img = anchor_img.set_position('center')
                bg_clips.append(anchor_img)
                anchor_added = True

            # 3. Branding Layer (TOP LEFT) - REMOVED as per user request (logo is in anchor image)
            # if os.path.exists(logo_path):
            #     logo = ImageClip(logo_path).set_duration(duration)
            #     logo = logo.resize(height=100) # Slightly smaller for corner
            #     logo = logo.set_position((40, 40)) # Top-Left
            #     bg_clips.append(logo)
            #     
            #     if channel_name:
            #         from PIL import Image, ImageDraw, ImageFont
            #         import numpy as np
            #         
            #         font_size = 55 # Proportionate to 100px logo
            #         header_font = None
            #         possible_fonts = [
            #             "automation/media/assets/NotoSansDevanagari-Regular.ttf",
            #             "C:\\Windows\\Fonts\\arialbd.ttf"
            #         ]
            #         for pf in possible_fonts:
            #             if os.path.exists(pf):
            #                 try:
            #                     header_font = ImageFont.truetype(pf, font_size)
            #                     break
            #                 except: continue
            #         
            #         if not header_font: header_font = ImageFont.load_default()
            #         
            #         bbox = ImageDraw.Draw(Image.new('RGBA', (1, 1))).textbbox((0, 0), channel_name, font=header_font)
            #         tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            #         name_img = Image.new('RGBA', (tw + 20, th + 20), (0,0,0,0))
            #         ImageDraw.Draw(name_img).text((10, 10), channel_name, font=header_font, fill='white', stroke_width=2, stroke_fill='black')
            #         
            #         name_clip = ImageClip(np.array(name_img)).set_duration(duration)
            #         # Position next to logo (logo height is 100, x is 40 + width + padding)
            #         logo_w = logo.size[0]
            #         name_clip = name_clip.set_position((40 + logo_w + 20, 55))
            #         bg_clips.append(name_clip)
        
        elif media_paths and len(media_paths) > 0:
            transition_time = duration / len(media_paths) if len(media_paths) > 0 else 4.0
            transition_time = max(min(transition_time, 6.0), 3.0) 
            
            # Check for Science Mode early for effects
            channel_name_str = str((branding or {}).get('channel_name', "")).lower()
            is_science_mode = "science" in channel_name_str or not template_mode

            for i, m_path in enumerate(media_paths):
                if os.path.exists(m_path):
                    try:
                        is_video = m_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))
                        start_time = i * transition_time
                        
                        if is_video:
                            clip = VideoFileClip(m_path).without_audio()
                            if clip.duration < transition_time:
                                clip = clip.fx(vfx.loop, duration=transition_time)
                            else:
                                clip = clip.subclip(0, transition_time)
                        else:
                            # Ensure image is RGB (fixes broadcast error if grayscale)
                            with Image.open(m_path) as img:
                                if img.mode != "RGB":
                                    img = img.convert("RGB")
                                clip = ImageClip(np.array(img)).set_duration(transition_time)

                        clip = clip.set_start(start_time)
                        
                        w, h = clip.size
                        target_ratio = self.size[0]/self.size[1]
                        if w/h > target_ratio: clip = clip.resize(height=self.size[1])
                        else: clip = clip.resize(width=self.size[0])
                        clip = clip.set_position('center')
                        
                        if not is_video:
                            # Apply Random Visual Effects
                            # USER REFREMENT: Science channel uses ONLY zoom-in
                            if is_science_mode:
                                effect_type = "zoom"
                            else:
                                effect_type = random.choice(["zoom", "static"])
                            
                            if effect_type == "zoom":
                                # Sniper Zoom: Rapid scale up
                                clip = self.apply_sniper_zoom(clip, transition_time)
                            else:
                                # Standard slow zoom - SLOWED DOWN (0.1 -> 0.04)
                                clip = clip.resize(lambda t: 1.0 + 0.04 * (t / transition_time))
                            
                        bg_clips.append(clip)

                        # SFX Logic
                        self._add_sfx(bg_clips, i, transition_time)

                    except Exception as e:
                        print(f"Error processing media {m_path}: {e}")
            
            if bg_clips:
                actual_bg_dur = sum([c.duration for c in bg_clips])
                if actual_bg_dur < duration:
                    bg_clips[-1] = bg_clips[-1].set_duration(duration - bg_clips[-1].start)
    



        if not bg_clips:
            bg_clips.append(ColorClip(size=self.size, color=(15, 15, 35), duration=duration))
        
        # 67-70: Removed the bottom overlay for cleaner look
        
        clips = bg_clips
        if word_offsets:
            print(f"DEBUG: Generating minimalist PILLOW-based karaoke captions for {len(word_offsets)} words...")
            # OPTIMIZED GEOMETRY (65pt for margins, smaller but cleaner)
            # MOVED TO BOTTOM (roughly 1450 for standard 1920 height)
            FONT_SIZE, LINE_HEIGHT, MAX_CHARS_PER_LINE = 65, 100, 25
            # Layout: If template_mode, move to BOTTOM. Otherwise, stay in CENTER.
            default_y = (self.size[1] - 470) if template_mode else ((self.size[1] // 2) - 100)
            START_Y = (branding or {}).get('caption_y', default_y)
            HIGHLIGHT_TEXT, NORMAL_TEXT = 'yellow', 'white'
            
            # Check content language
            line_text_sample = " ".join([w['word'] for w in word_offsets[:10]])
            is_nepali_content = any(ord(c) > 127 for c in line_text_sample)
            
            font_paths = []
            if not is_nepali_content:
                # Prioritize English-friendly fonts for Science
                if os.name == 'nt':
                    font_paths += [
                        os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'arial.ttf'),
                        os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'segoeui.ttf'),
                    ]
                else:
                    font_paths += [
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                    ]

            # Devanagari fallbacks and regular list
            font_paths += ["automation/media/assets/NotoSansDevanagari-Regular.ttf"]
            
            if os.name == 'nt':
                windir = os.environ.get('WINDIR', 'C:\\Windows')
                font_paths += [
                    os.path.join(windir, 'Fonts', 'Nirmala.ttc'),
                    os.path.join(windir, 'Fonts', 'Nirmala.ttf'),
                    os.path.join(windir, 'Fonts', 'aparaj.ttf'),
                    os.path.join(windir, 'Fonts', 'mangal.ttf'),
                    os.path.join(windir, 'Fonts', 'arialbd.ttf'), 
                ]
            else:
                font_paths += [
                    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
                    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                ]
            
            font = None
            for path in font_paths:
                if os.path.exists(path):
                    try:
                        font = ImageFont.truetype(path, FONT_SIZE, index=0)
                        break
                    except: continue
            
            if not font and os.name != 'nt':
                # Emergency search
                for root, dirs, files in os.walk("/usr/share/fonts"):
                    if font: break
                    for file in files:
                        if file.endswith(".ttf") or file.endswith(".ttc"):
                            try:
                                font = ImageFont.truetype(os.path.join(root, file), FONT_SIZE)
                                break
                            except: continue
            
            if not font: font = ImageFont.load_default()

            print("DEBUG: Using Pop-Up Word caption style (scale-in, bold, keyword highlight)")

            from .caption_style import get_pop_font, build_pop_chunks, make_pop_caption_clip, PORTRAIT_CAPTION_Y_FRACTION

            pop_font = get_pop_font(72)
            pop_chunks = build_pop_chunks(word_offsets)

            # Shared position constant — matches hook_question's text and
            # create_shorts_from_scenes below, so every caption in the video (including
            # the opening hook) sits at the same spot instead of jumping around.
            caption_y = int(self.size[1] * PORTRAIT_CAPTION_Y_FRACTION)
            badge_dur = 0.0
            badge_start = max(0.0, duration - badge_dur)

            for i, chunk in enumerate(pop_chunks):
                if not chunk:
                    continue
                chunk_start = chunk[0]['start']
                if badge_dur > 1.0 and chunk_start >= badge_start - 0.2:
                    continue  # yield the frame to the subscribe badge

                if i < len(pop_chunks) - 1 and pop_chunks[i + 1]:
                    next_start = pop_chunks[i + 1][0]['start']
                    chunk_dur = max(next_start - chunk_start, 0.1)
                else:
                    chunk_end = chunk[-1]['start'] + chunk[-1]['duration']
                    chunk_dur = max(chunk_end - chunk_start, 0.35)

                try:
                    pop_clip = make_pop_caption_clip(chunk, chunk_dur, pop_font, max_w=900, caption_y=caption_y)
                    clips.append(pop_clip)
                except Exception as e:
                    print(f"PopUp render error: {e}")
                    continue

            # Dong SFX hook
            if os.path.exists("automation/media/sfx/dong.mp3"):
                dong = AudioFileClip("automation/media/sfx/dong.mp3").set_start(0).volumex(0.8)
                if not hasattr(self, 'sfx_clips'): self.sfx_clips = []
                self.sfx_clips.insert(0, dong)

            # Subscribe badge on the final seconds — this legacy path previously had no
            # subscribe nudge at all (only create_shorts_from_scenes did).
            try:
                if badge_dur > 1.0:
                    from .scene_renderer import SceneRenderer
                    sub_renderer = SceneRenderer(mode='portrait')
                    sub_clip = sub_renderer.render_subscribe_badge(badge_dur, sub_text="for more daily deep space")
                    sub_clip = sub_clip.set_start(badge_start).set_position("center")
                    clips.append(sub_clip)
            except Exception as badge_err:
                print(f"[Shorts] Subscribe badge overlay error: {badge_err}")

        
        music_files = []
        science_music_dirs = ["automation/music/science"]
        for sdir in science_music_dirs:
            if os.path.exists(sdir):
                music_files.extend(glob.glob(os.path.join(sdir, "*.mp3")))
        print(f"Science background music found: {len(music_files)} files.")

        if music_files:
            try:
                music_path = random.choice(music_files)
                print(f"Using background music: {music_path}")
                bg_music = AudioFileClip(music_path).volumex(music_vol) # Use configured volume
                
                # Loop if too short
                if bg_music.duration < duration:
                    bg_music = bg_music.fx(afx.audio_loop, duration=duration)
                else:
                    bg_music = bg_music.subclip(0, duration)
                
                # Gentle fades (2 seconds)
                if bg_music.duration > 4:
                    bg_music = bg_music.audio_fadein(2).audio_fadeout(2)
                
                audio_components = [audio, bg_music]
                
                if hasattr(self, 'sfx_clips') and self.sfx_clips:
                    print(f"Adding {len(self.sfx_clips)} SFX clips to final audio.")
                    audio_components.extend(self.sfx_clips)

                from moviepy.audio.AudioClip import CompositeAudioClip
                # Boost Voice to 1.4x for clarity against music
                audio_components[0] = audio_components[0].volumex(1.4) 
                final_audio = CompositeAudioClip(audio_components)
            except Exception as e:
                print(f"Failed to load background music or SFX: {e}")
                final_audio = audio
        else:
            final_audio = audio
        print(f"DEBUG: Audio components: {len(audio_components) if 'audio_components' in locals() else 'N/A'}")
        

        final_video = CompositeVideoClip(clips, size=self.size).set_audio(final_audio).set_duration(duration)
        print(f"DEBUG: Writing video to {output_path} with duration {duration:.2f}s and {len(clips)} clips.")
        sys.stdout.flush()

        
        try:
            # Using logger=None to avoid progress bar buffering issues in some CI environments
            final_video.write_videofile(
                output_path, 
                fps=24, 
                codec="libx264", 
                audio_codec="aac", 
                threads=1, 
                preset='ultrafast', 
                logger=None 
            )
            print(f"DEBUG: Video written successfully to {output_path}")
            sys.stdout.flush()

            
            if not os.path.exists(output_path):
                 print(f"CRITICAL: write_videofile returned but file {output_path} is missing!")
                 sys.stdout.flush()

                 
        except Exception as e:
            print(f"CRITICAL ERROR writing video: {e}")
            import traceback
            traceback.print_exc()
            sys.stdout.flush()

            raise e

    def create_shorts_from_scenes(
        self,
        asset_manifest: dict,
        audio_path: str,
        output_path: str,
        word_offsets: list = None,
        branding: dict = None,
        topic: str = "",
    ):
        """
        Renders a Shorts video using the premium visual scene manifest from AssetOrchestrator.
        """
        import glob
        from moviepy.editor import (
            concatenate_videoclips, AudioFileClip, CompositeVideoClip,
            ImageClip, ColorClip, afx
        )
        from .scene_renderer import SceneRenderer
        from .timing_utils import match_scenes_to_timestamps

        music_vol = (branding or {}).get('music_volume', 0.04)

        try:
            audio = AudioFileClip(audio_path)
            total_duration = audio.duration

            scenes = asset_manifest.get("scenes", [])
            if not scenes:
                raise ValueError("Asset manifest contains no scenes.")

            # ── 1. Calculate Timings ─────────────────────────────
            scene_timings = match_scenes_to_timestamps(scenes, word_offsets or [], total_duration)

            # ── 2. Initialize Portrait Renderer ───────────────────────────
            renderer = SceneRenderer(mode='portrait')
            scene_clips = []

            # ── 3. Render Scenes ───────────────────────────
            for i, scene in enumerate(scenes):
                timing = scene_timings[i]
                dur = timing["duration"]
                
                scene_type = scene.get("visual_type", "image")
                narration = scene.get("narration", "")
                asset_path = scene.get("asset_path")

                # Fallback background
                if not asset_path or not os.path.exists(asset_path):
                    from PIL import Image as PilImage
                    fb = PilImage.new("RGB", (1080, 1920), (10, 18, 30))
                    asset_path = f"automation/storage/shorts_fallback_bg_{i}.jpg"
                    fb.save(asset_path)

                try:
                    if scene_type == "typewriter_text":
                        clip = renderer.render_typewriter(
                            asset_path, narration, dur, 
                            typewriter_words=scene.get("typewriter_words"),
                            word_offsets=word_offsets,
                            start_time=timing["start"]
                        )
                    elif scene_type == "kinetic_stat":
                        stat_data = scene.get("stat_data") or {"value": "0", "unit": "", "label": "Statistic"}
                        clip = renderer.render_kinetic_stat(asset_path, narration, dur, stat_data)
                    elif scene_type == "hook_question":
                        q_text = str(scene.get("question_text") or narration)
                        emp_phrase = scene.get("emphasis_phrase", "")
                        clip = renderer.render_hook_question(
                            asset_path, narration, dur, q_text, emp_phrase,
                            word_offsets=word_offsets,
                            start_time=timing["start"],
                            topic=topic
                        )
                    elif scene_type == "ai_video":
                        clip = renderer.render_ai_video(asset_path, dur)
                    elif scene_type == "data_bars":
                        bar_data = scene.get("bar_data")
                        clip = renderer.render_data_bars(asset_path, narration, dur, bar_data)
                    elif scene_type == "image":
                        named_ent = scene.get("named_entity", "")
                        clip = renderer.render_image(asset_path, narration, dur, named_ent)
                    else:
                        clip = renderer.render_typewriter(
                            asset_path, narration, dur,
                            word_offsets=word_offsets,
                            start_time=timing["start"]
                        )

                    scene_clips.append(clip)
                    print(f"[Shorts Scene {i+1}/{len(scenes)}] type={scene_type} dur={dur:.1f}s OK")

                except Exception as e:
                    print(f"[Shorts Scene {i+1}] RENDER ERROR ({scene_type}): {e}. Using fallback.")
                    raise RuntimeError(f"Scene {i+1} failed to render; refusing a blank replacement") from e

            # Cuts stay on narration boundaries; inserted flashes used to desync captions.
            final_clips = scene_clips
            self.sfx_events = []
            if total_duration > 58.0:
                raise ValueError("Short narration exceeds 58 seconds; shorten the script before rendering.")

            combined = concatenate_videoclips(final_clips, method="compose")

            # Trim or pad to match audio
            if combined.duration > total_duration:
                combined = combined.subclip(0, total_duration)
            elif combined.duration < total_duration - 0.1:
                from moviepy.editor import ColorClip as CC
                pad = CC(size=(1080, 1920), color=(10, 18, 30), duration=total_duration - combined.duration)
                combined = concatenate_videoclips([combined, pad], method="compose")

            clips = [combined]

            # Subscribe badge occupies the bottom area for the final few seconds — reserve
            # that window so late captions don't render on top of / behind it (see 5b).
            badge_dur = 0.0
            badge_start = max(0.0, total_duration - badge_dur)

            # ── 5. Overlay pop-up captions ──────────────────────────────────────
            if word_offsets:
                try:
                    from .caption_style import get_pop_font, build_pop_chunks, make_pop_caption_clip, PORTRAIT_CAPTION_Y_FRACTION

                    pop_font = get_pop_font(72)
                    pop_chunks = build_pop_chunks(word_offsets)

                    # Shared position constant — same spot as hook_question's text and the
                    # legacy create_shorts() path above, so every caption in the video sits
                    # in the same place instead of jumping around between scenes.
                    caption_y = int(1920 * PORTRAIT_CAPTION_Y_FRACTION)
                    for i, chunk in enumerate(pop_chunks):
                        if not chunk:
                            continue
                        cs = chunk[0]['start']
                        if badge_dur > 1.0 and cs >= badge_start - 0.2:
                            continue  # yield the frame to the subscribe badge

                        # Find matching scene type to suppress captions over typewriter/hook scenes
                        active_type = "image"
                        for s_idx, timing in enumerate(scene_timings):
                            if timing["start"] <= cs <= timing["end"]:
                                active_type = scenes[s_idx].get("visual_type", "image")
                                break
                        if active_type in ("hook_question", "typewriter_text", "kinetic_stat"):
                            continue
                        if i < len(pop_chunks) - 1 and pop_chunks[i + 1]:
                            cd = max(pop_chunks[i + 1][0]['start'] - cs, 0.1)
                        else:
                            cd = max(chunk[-1]['start'] + chunk[-1]['duration'] - cs, 0.35)
                        try:
                            pop_clip = make_pop_caption_clip(chunk, cd, pop_font, max_w=900, caption_y=caption_y)
                            clips.append(pop_clip)
                        except Exception as cap_e:
                            print(f"Caption chunk error: {cap_e}")

                except Exception as cap_err:
                    print(f"[Shorts] Caption overlay failed: {cap_err}")

            # ── 5b. Subscribe badge overlay on the final seconds ───────────────
            try:
                if badge_dur > 1.0:
                    sub_clip = renderer.render_subscribe_badge(badge_dur, sub_text="for more daily deep space")
                    sub_clip = sub_clip.set_start(badge_start).set_position("center")
                    clips.append(sub_clip)
            except Exception as badge_err:
                print(f"[Shorts] Subscribe badge overlay error: {badge_err}")

            # ── 6. Background music ───────────────────────────────────────────
            music_files = []
            for mdir in ["automation/music/science"]:
                if os.path.exists(mdir):
                    music_files.extend(glob.glob(os.path.join(mdir, "*.mp3")))

            # Mix music and transition SFX
            sfx_clips = []
            sfx_dir = "automation/media/sfx"
            if hasattr(self, 'sfx_events') and self.sfx_events:
                for event in self.sfx_events:
                    sfx_path = os.path.join(sfx_dir, event["file"])
                    if os.path.exists(sfx_path):
                        try:
                            sfx_clip = AudioFileClip(sfx_path).set_start(event["time"]).volumex(0.15)
                            sfx_clips.append(sfx_clip)
                        except Exception as s_err:
                            print(f"[Shorts] SFX error: {s_err}")
                            
            if music_files:
                try:
                    import random as _rand
                    bg_music = AudioFileClip(_rand.choice(music_files)).volumex(music_vol)
                    if bg_music.duration < total_duration:
                        bg_music = bg_music.fx(afx.audio_loop, duration=total_duration)
                    else:
                        bg_music = bg_music.subclip(0, total_duration)
                    if bg_music.duration > 4:
                        bg_music = bg_music.audio_fadein(2).audio_fadeout(2)
                    from moviepy.audio.AudioClip import CompositeAudioClip
                    final_audio = CompositeAudioClip([audio, bg_music] + sfx_clips)
                except Exception as me:
                    print(f"[Shorts] BG music error: {me}")
                    if sfx_clips:
                        from moviepy.audio.AudioClip import CompositeAudioClip
                        final_audio = CompositeAudioClip([audio] + sfx_clips)
                    else:
                        final_audio = audio
            else:
                if sfx_clips:
                    from moviepy.audio.AudioClip import CompositeAudioClip
                    final_audio = CompositeAudioClip([audio] + sfx_clips)
                else:
                    final_audio = audio

            # ── 7. Composite + export ─────────────────────────────────────────
            final = CompositeVideoClip(clips, size=(1080, 1920)).set_audio(final_audio).set_duration(total_duration)
            print(f"[Shorts] Writing visual-scene video -> {output_path}")
            
            # Use distinct temp audio file to prevent Windows PermissionError (WinError 32)
            temp_audio_path = os.path.join(os.path.dirname(output_path), "temp_shorts_audio.m4a")
            if os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                except:
                    pass
                    
            final.write_videofile(
                output_path, fps=30, codec="libx264",
                audio_codec="aac", threads=1, preset="ultrafast", logger=None,
                temp_audiofile=temp_audio_path, remove_temp=True
            )
            print(f"[Shorts] Visual-scene video written successfully.")
            
            # Explicitly close all clips to release file locks on Windows
            try:
                final.close()
                for c in scene_clips:
                    c.close()
                audio.close()
                if 'bg_music' in locals() and bg_music:
                    bg_music.close()
                for sfx in sfx_clips:
                    sfx.close()
            except Exception as ce:
                print(f"[Shorts] Clip closing warning: {ce}")
        except Exception as e:
            # Explicitly close all clips even on exception
            try:
                if 'final' in locals() and final: final.close()
                if 'scene_clips' in locals():
                    for c in scene_clips: c.close()
                if 'audio' in locals() and audio: audio.close()
                if 'bg_music' in locals() and bg_music: bg_music.close()
                if 'sfx_clips' in locals():
                    for sfx in sfx_clips: sfx.close()
            except:
                pass
            raise e

    def _wrap_text(self, text, width):
        words, lines, curr = text.split(), [], []
        for w in words:
            if len(" ".join(curr + [w])) <= width: curr.append(w)
            else: lines.append(" ".join(curr)); curr = [w]
        lines.append(" ".join(curr))
        return "\n".join(lines)

    def apply_sniper_zoom(self, clip, duration):
        """Rapid zoom in (Sniper effect) - SLOWED DOWN."""
        # Linear zoom from 1.0 to 1.2 over the duration
        return clip.resize(lambda t: 1.0 + (0.2 * (t / duration)))




    def _add_sfx(self, clips, index, clip_duration):
        """Adds SFXAudioClip if files exist."""
        sfx_dir = "automation/media/sfx"
        if not os.path.exists(sfx_dir): return

        if not clips: return
        current_clip = clips[-1]
        start_time = current_clip.start
        
        # Audio needs to be loaded
        loaded_sfx = None
        
        try:
            # 1. Riser/Dong at the very start (Index 0)
            if index == 0:
                # PRIORITIZE DONG for Science
                dong_path = os.path.join(sfx_dir, "dong.mp3")
                riser_path = os.path.join(sfx_dir, "riser.mp3")
                
                # Check if we are in science mode? Hard to tell here without context, 
                # but "dong" is generally good for hooks.
                if os.path.exists(dong_path):
                     loaded_sfx = AudioFileClip(dong_path).set_start(0).volumex(0.8)
                elif os.path.exists(riser_path):
                    loaded_sfx = AudioFileClip(riser_path).set_start(0).volumex(0.8)
            
            # 2. Transition SFX (Whoosh/Kick) for other clips
            elif index > 0:
                # Science: ALWAYS Whoosh/Slide for fast pace
                
                # We'll default to high frequency for now as Shorts are fast
                whoosh_path = os.path.join(sfx_dir, "whoosh.mp3")
                
                if random.random() < 0.7: # 70% chance
                    if os.path.exists(whoosh_path) and random.random() > 0.3:
                         loaded_sfx = AudioFileClip(whoosh_path).set_start(start_time).volumex(0.6)
                    else:
                        sfx_files = [f for f in os.listdir(sfx_dir) if f.endswith('.mp3') and ('kick' in f or 'slide' in f)]
                        if sfx_files:
                            chosen_sfx = random.choice(sfx_files)
                            sfx_path = os.path.join(sfx_dir, chosen_sfx)
                            loaded_sfx = AudioFileClip(sfx_path).set_start(start_time).volumex(0.6)

            if loaded_sfx:
                if not hasattr(self, 'sfx_clips'): self.sfx_clips = []
                self.sfx_clips.append(loaded_sfx)
        
        except Exception as e:
            print(f"SFX Error: {e}")
