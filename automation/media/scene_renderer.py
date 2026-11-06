import os
import random
import time
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from moviepy.editor import VideoClip, ImageClip, VideoFileClip

from .caption_style import PORTRAIT_CAPTION_Y_FRACTION, LANDSCAPE_CAPTION_Y_FRACTION

# Size constants will be handled by SceneRenderer instance

def get_font_path(style="bold") -> str:
    """
    Finds and returns the path to a valid font.
    Fallback chain:
    1. Barlow fonts downloaded to automation/fonts/
    2. /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf (guaranteed on Ubuntu 22.04+)
    3. Raise explicit error before rendering.
    """
    mapping = {
        "condensed_bold": "Barlow-CondensedBold.ttf",
        "bold": "Barlow-Bold.ttf",
        "regular": "Barlow-Regular.ttf"
    }
    font_file = mapping.get(style, "Barlow-Bold.ttf")
    local_path = os.path.join("automation", "fonts", font_file)
    if os.path.exists(local_path):
        return local_path
    
    # Fallback to DejaVuSans-Bold
    system_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if os.path.exists(system_path):
        return system_path
        
    # Strict fail-fast mandate (Prevents blank box Devanagari errors)
    raise RuntimeError(
        f"CRITICAL FONT ERROR: Barlow fonts in 'automation/fonts/' and system fallback "
        f"'{system_path}' are BOTH missing! Render aborted."
    )

def wrap_text(text, font, max_width):
    """Wraps text into multiple lines for drawing."""
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        test_line = " ".join(current_line)
        try:
            bbox = font.getbbox(test_line)
            w = bbox[2] - bbox[0]
        except AttributeError:
            w = font.getsize(test_line)[0]
            
        if w > max_width:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines

def apply_cinematic_grade(pil_img):
    """Applies a premium cinematic color grade, vignette, and contrast boost."""
    # Contrast and color saturation boost
    pil_img = ImageEnhance.Contrast(pil_img).enhance(1.03)
    pil_img = ImageEnhance.Color(pil_img).enhance(1.0)
    
    # Create smooth radial vignette using numpy
    w, h = pil_img.size
    x = np.linspace(-1.1, 1.1, w)
    y = np.linspace(-1.1, 1.1, h)
    xx, yy = np.meshgrid(x, y)
    r = np.sqrt(xx**2 + yy**2)
    
    # Smooth roll-off: vignette starts at r=0.45, reaches max opacity 140 at r=1.4
    alpha = np.clip((r - 0.45) / 0.95 * 35, 0, 35).astype(np.uint8)
    
    v_arr = np.zeros((h, w, 4), dtype=np.uint8)
    v_arr[:, :, 3] = alpha
    v_img = Image.fromarray(v_arr, mode="RGBA")
    
    graded = Image.alpha_composite(pil_img.convert("RGBA"), v_img)
    return graded.convert("RGB")

def apply_lens_flare(pil_img, t: float = 0.0, intensity: float = 0.4):
    """
    Adds a subtle animated lens flare streak across the image.
    The flare position slowly drifts over time for a premium cinematic feel.
    """
    return pil_img  # Preserve documentary source imagery without synthetic flare.
    w, h = pil_img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # Flare center drifts from upper-left to upper-right over time
    cx = int(w * (0.15 + 0.7 * (math.sin(t * 0.3 + 1.0) * 0.5 + 0.5)))
    cy = int(h * 0.18)
    # Main flare disc
    r = int(min(w, h) * 0.04)
    alpha_main = int(120 * intensity)
    d.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(255, 240, 180, alpha_main))
    # Flare halo ring
    r2 = r * 3
    alpha_halo = int(30 * intensity)
    d.ellipse([(cx - r2, cy - r2), (cx + r2, cy + r2)], outline=(255, 255, 200, alpha_halo), width=2)
    # Streak line
    streak_alpha = int(60 * intensity)
    d.line([(0, cy + r // 2), (w, cy - r // 2)], fill=(255, 240, 200, streak_alpha), width=2)
    return Image.alpha_composite(pil_img.convert("RGBA"), overlay).convert("RGB")

def draw_starfield_overlay(draw, width, height, t: float, star_count: int = 80,
                           seed: int = 42, twinkle: bool = True):
    """
    Draws animated stars onto the given ImageDraw canvas.
    Stars slowly drift and twinkle over time.
    """
    return  # Decorative star fields misrepresent non-astronomy subjects.
    rng = random.Random(seed)
    for _ in range(star_count):
        sx = rng.randint(0, width)
        sy = rng.randint(0, height)
        # Small drift
        sx = (sx + int(t * rng.uniform(0.1, 0.5))) % width
        base_brightness = rng.randint(140, 255)
        if twinkle:
            twinkle_factor = 0.75 + 0.25 * math.sin(t * rng.uniform(1.5, 4.5) + rng.random() * 6.28)
        else:
            twinkle_factor = 1.0
        brightness = int(base_brightness * twinkle_factor)
        r = rng.randint(1, 2)
        draw.ellipse([(sx - r, sy - r), (sx + r, sy + r)],
                     fill=(brightness, brightness, min(255, brightness + 30), 200))

def draw_scan_lines(img_array: np.ndarray, opacity: float = 0.06) -> np.ndarray:
    """
    Overlays subtle horizontal scan-line darkening for a sci-fi monitor effect.
    """
    return img_array
    h, w = img_array.shape[:2]
    mask = np.ones((h, w, 3), dtype=np.float32)
    # Darken every other 2px band
    mask[::2, :, :] *= (1.0 - opacity)
    result = (img_array.astype(np.float32) * mask).clip(0, 255).astype(np.uint8)
    return result

def draw_data_hud(draw, width, height, t: float, mode='landscape',
                  color=(0, 240, 255), label: str = "SCIENCE"):
    """
    Draws a minimalist HUD corner decoration — corner brackets + animated blinking dot.
    Gives images a premium futuristic science-channel look.
    """
    return  # No fictional instrument/HUD markings on scientific footage.
    margin = 28 if mode == 'landscape' else 20
    bar_len = 50 if mode == 'landscape' else 35
    thick = 3
    alpha = 200
    c = (*color, alpha)
    # Top-left corner bracket
    draw.line([(margin, margin), (margin + bar_len, margin)], fill=c, width=thick)
    draw.line([(margin, margin), (margin, margin + bar_len)], fill=c, width=thick)
    # Top-right corner bracket
    draw.line([(width - margin, margin), (width - margin - bar_len, margin)], fill=c, width=thick)
    draw.line([(width - margin, margin), (width - margin, margin + bar_len)], fill=c, width=thick)
    # Bottom-left corner bracket
    draw.line([(margin, height - margin), (margin + bar_len, height - margin)], fill=c, width=thick)
    draw.line([(margin, height - margin), (margin, height - margin - bar_len)], fill=c, width=thick)
    # Bottom-right corner bracket
    draw.line([(width - margin, height - margin), (width - margin - bar_len, height - margin)], fill=c, width=thick)
    draw.line([(width - margin, height - margin), (width - margin, height - margin - bar_len)], fill=c, width=thick)
    # Blinking status dot (top-left)
    if int(t * 2) % 2 == 0:
        dot_x, dot_y = margin + 12, margin + bar_len + 14
        draw.ellipse([(dot_x - 5, dot_y - 5), (dot_x + 5, dot_y + 5)], fill=(*color, 230))

def render_lower_third(draw, named_entity, font_bold, font_regular, width, height, mode='landscape'):
    """Draws a premium banner for named entities (top-left for portrait, bottom-left for landscape)."""
    banner_w = 550
    banner_h = 90
    banner_x = 80
    
    if mode == 'portrait':
        # Top-left placement for portrait (Shorts) to avoid overlaps
        banner_y = 120
    else:
        # Bottom-left placement for landscape (Longform)
        banner_y = height - 180
        
    # Soft black/blue pill background
    pill_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(pill_overlay)
    
    # Semi-transparent dark navy pill
    p_draw.rounded_rectangle(
        [(banner_x, banner_y), (banner_x + banner_w, banner_y + banner_h)],
        radius=12,
        fill=(10, 22, 40, 210)
    )
    # Bright cyan left border bar
    p_draw.rectangle(
        [(banner_x, banner_y + 10), (banner_x + 6, banner_y + banner_h - 10)],
        fill=(0, 240, 255, 255)
    )
    
    return pill_overlay, banner_x, banner_y

class SceneRenderer:
    """
    Renders the 6 custom science channel visual scene styles.
    Uses MoviePy 1.x-compatible methods (e.g. set_duration, set_position).
    """
    def __init__(self, mode='landscape'):
        self.mode = mode
        if mode == 'portrait':
            self.WIDTH, self.HEIGHT = 1080, 1920
        else:
            self.WIDTH, self.HEIGHT = 1920, 1080
        self.image_scene_count = 0

    def render_typewriter(self, bg_path: str, text: str, duration: float, typewriter_words: list = None, word_offsets: list = None, start_time: float = 0.0) -> VideoClip:
        """
        Types words sequentially with a blinking cursor at the narration end time.
        Uses a solid dark premium background and kinetic typography (highlighted words are larger/colored).
        """
        font_path_bold = get_font_path("bold")
        font_path_reg = get_font_path("regular")
        
        # Determine display text: use typewriter_words if provided, or cap narration
        max_words = 4 if self.mode == 'portrait' else 8
        if typewriter_words and isinstance(typewriter_words, list):
            processed_words = []
            for w in typewriter_words:
                if isinstance(w, dict):
                    word_str = str(w.get("word", "")).strip()
                    weight = str(w.get("weight", "")).strip().lower()
                    if weight in ("bold", "lg", "large", "highlight"):
                        processed_words.append(f"*{word_str}*")
                    else:
                        processed_words.append(word_str)
                else:
                    processed_words.append(str(w).strip())
            display_text = " ".join(processed_words)
        else:
            words_list = text.split()
            display_text = " ".join(words_list[:max_words])
            if len(words_list) > max_words:
                display_text += "..."

        # Parse highlighted words marked with asterisks
        tokens = []
        in_highlight = False
        for word in display_text.split():
            clean_word = word
            if clean_word.startswith('*'):
                in_highlight = True
                clean_word = clean_word[1:]
            
            was_highlight = in_highlight
            
            if clean_word.endswith('*'):
                clean_word = clean_word[:-1]
                in_highlight = False
                
            tokens.append({"word": clean_word, "highlight": was_highlight})
            
        is_port = self.mode == 'portrait'
        f_bold_sz = int(80 * 1.2) if is_port else 110
        f_reg_sz = int(50 * 1.2) if is_port else 70
        line_spacing = int(105 * 1.2) if is_port else 140
        text_baseline_offset = int(80 * 1.2) if is_port else 110
        
        font_bold = ImageFont.truetype(font_path_bold, f_bold_sz)
        font_reg = ImageFont.truetype(font_path_reg, f_reg_sz)
        
        # White/gold matches the color language used everywhere else on-screen (captions,
        # the hook_question opener) — previously this randomly picked cyan/orange/green
        # per render, which was one more inconsistent "look" scattered through a video.
        COLOR_NORMAL = (255, 255, 255)
        COLOR_HIGHLIGHT = (255, 199, 40)
        
        # Calculate line wrapping
        lines = []
        current_line = []
        current_width = 0
        max_line_width = self.WIDTH - 150 if is_port else self.WIDTH - 300
        
        for token in tokens:
            font = font_bold if token['highlight'] else font_reg
            space_w = font.getlength(" ")
            word_w = font.getlength(token['word'])
            
            item_w = word_w if not current_line else word_w + space_w
            
            if current_width + item_w > max_line_width and current_line:
                lines.append(current_line)
                current_line = [{"word": token['word'], "highlight": token['highlight'], "font": font, "w": word_w}]
                current_width = word_w
            else:
                current_line.append({"word": token['word'], "highlight": token['highlight'], "font": font, "w": word_w, "space_w": space_w if current_line else 0})
                current_width += item_w
        if current_line:
            lines.append(current_line)
            
        total_chars = sum(len(item['word']) for line in lines for item in line)
        
        total_h = len(lines) * line_spacing
        # Same vertical anchor as every other caption in the video (pop-up captions,
        # hook_question) instead of this scene's own dead-center position — previously
        # typewriter_text was yet another place text jumped to a different spot.
        caption_frac = PORTRAIT_CAPTION_Y_FRACTION if self.mode == 'portrait' else LANDSCAPE_CAPTION_Y_FRACTION
        start_y = int(self.HEIGHT * caption_frac) - total_h // 2
        
        def make_frame(t):
            # Plane blank page with a sleek premium dark gray color
            img = Image.new("RGB", (self.WIDTH, self.HEIGHT), (15, 18, 22))
            draw = ImageDraw.Draw(img)
            
            # ── Animated starfield background ────────────────────────────────
            draw_starfield_overlay(draw, self.WIDTH, self.HEIGHT, t, star_count=60, seed=7331)
            
            typing_duration = min(3.5, duration)
            if word_offsets and start_time is not None:
                scene_words = [item for item in word_offsets if start_time - 0.05 <= item['start'] <= start_time + duration + 0.05]
                if scene_words:
                    words_dur = scene_words[-1]['start'] + scene_words[-1]['duration'] - scene_words[0]['start']
                    words_dur = max(0.5, min(4.5, words_dur))
                    ratio = min(1.0, t / words_dur)
                    visible_chars = int(ratio * total_chars)
                else:
                    visible_chars = int(min(t / max(0.01, typing_duration), 1.0) * total_chars)
            else:
                visible_chars = int(min(t / max(0.01, typing_duration), 1.0) * total_chars)
                
            chars_drawn = 0
            
            y = start_y
            last_x, last_y = 0, 0
            cursor_drawn = False
            
            for line in lines:
                line_width = sum(item['w'] + item.get('space_w', 0) for item in line)
                x = (self.WIDTH - line_width) // 2
                
                for item in line:
                    x += item.get('space_w', 0)
                    word = item['word']
                    font = item['font']
                    color = COLOR_HIGHLIGHT if item['highlight'] else COLOR_NORMAL
                    
                    word_len = len(word)
                    
                    if chars_drawn + word_len <= visible_chars:
                        # Draw neon glow for highlighted words
                        if item['highlight']:
                            for glow_r in range(1, 4):
                                draw.text((x, y + text_baseline_offset), word, font=font,
                                          fill=(COLOR_HIGHLIGHT[0], COLOR_HIGHLIGHT[1], COLOR_HIGHLIGHT[2], 60 // glow_r),
                                          stroke_width=glow_r, anchor="ls")
                        draw.text((x, y + text_baseline_offset), word, fill=color, font=font, anchor="ls")
                        chars_drawn += word_len
                        x += item['w']
                        last_x, last_y = x, y
                    elif chars_drawn < visible_chars:
                        part_len = visible_chars - chars_drawn
                        part_word = word[:part_len]
                        draw.text((x, y + text_baseline_offset), part_word, fill=color, font=font, anchor="ls")
                        
                        part_w = font.getlength(part_word)
                        cursor_x = x + part_w + 5
                        draw.rectangle([(cursor_x, y + 15), (cursor_x + 6, y + text_baseline_offset + 5)], fill=COLOR_HIGHLIGHT)
                        cursor_drawn = True
                        
                        chars_drawn += word_len
                        x += item['w']
                    else:
                        x += item['w']
                        
                y += line_spacing
                
            if not cursor_drawn and chars_drawn >= total_chars:
                if int(t * 3.5) % 2 == 0:
                    draw.rectangle([(last_x + 8, last_y + 15), (last_x + 14, last_y + text_baseline_offset + 5)], fill=COLOR_HIGHLIGHT)

            # ── HUD corner brackets ──────────────────────────────────────────
            draw_data_hud(draw, self.WIDTH, self.HEIGHT, t, mode=self.mode,
                          color=COLOR_HIGHLIGHT, label="SCIENCE")
            img_arr = np.array(img)
            # Subtle scan-lines for screen aesthetic
            img_arr = draw_scan_lines(img_arr, opacity=0.04)
            return img_arr

        clip = VideoClip(make_frame, duration=duration)
        return clip.set_fps(30)

    def render_kinetic_stat(self, bg_path: str, text: str, duration: float, stat_data: dict) -> VideoClip:
        """
        Renders a large statistical number counting up dynamically.
        """
        font_path_bold = get_font_path("condensed_bold")
        font_path_reg = get_font_path("regular")

        bg_path = self._ensure_background_image(bg_path, scene_idx=1)
        bg_img = Image.open(bg_path).convert("RGB")
        bg_graded = apply_cinematic_grade(self._cover_image(bg_img))

        val_str = str(stat_data.get("value", "0"))
        unit = str(stat_data.get("unit", ""))
        label = str(stat_data.get("label", "Key Statistic")).upper()

        digits = "".join(c for c in val_str if c.isdigit())
        final_val = int(digits) if digits else 0
        non_digits = "".join(c for c in val_str if not c.isdigit())

        def make_frame(t):
            anim_dur = min(1.6, duration)
            if t < anim_dur:
                fraction = 1.0 - (1.0 - t / anim_dur) ** 3
                cur_val = int(fraction * final_val)
            else:
                cur_val = final_val

            display_val = f"{cur_val:,}" + non_digits
            if unit:
                display_val += " " + unit

            motion = 1.0 + 0.08 * (t / max(duration, 0.001))
            cw = int(self.WIDTH / motion)
            ch = int(self.HEIGHT / motion)
            x = max(0, (self.WIDTH - cw) // 2)
            y = max(0, (self.HEIGHT - ch) // 2)
            img = bg_graded.crop((x, y, x + cw, y + ch)).resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS).convert("RGBA")

            overlay = Image.new("RGBA", (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
            o_draw = ImageDraw.Draw(overlay)
            panel_margin = 70 if self.mode == "portrait" else 150
            o_draw.rounded_rectangle(
                [(panel_margin, self.HEIGHT // 2 - (260 if self.mode == "portrait" else 210)),
                 (self.WIDTH - panel_margin, self.HEIGHT // 2 + (260 if self.mode == "portrait" else 210))],
                radius=28,
                fill=(5, 10, 25, 185),
            )
            o_draw.rectangle([(70 if self.mode == "portrait" else 120, 0), (82 if self.mode == "portrait" else 132, self.HEIGHT)], fill=(0, 240, 255, 255))
            draw_starfield_overlay(o_draw, self.WIDTH, self.HEIGHT, t, star_count=55, seed=1234, twinkle=True)
            img = Image.alpha_composite(img, overlay).convert("RGB")
            draw = ImageDraw.Draw(img)

            pulse = 1.0 + 0.08 * math.sin(t * 5.0)
            stat_font_size = int(175 * (1.18 if self.mode == "portrait" else 1.0) * pulse)
            stat_font = ImageFont.truetype(font_path_bold, stat_font_size)
            try:
                vw = stat_font.getbbox(display_val)[2] - stat_font.getbbox(display_val)[0]
                vh = stat_font.getbbox(display_val)[3] - stat_font.getbbox(display_val)[1]
            except AttributeError:
                vw = draw.textlength(display_val, font=stat_font)
                vh = stat_font_size
            vx = (self.WIDTH - vw) // 2
            vy = self.HEIGHT // 2 - vh // 2 - 35

            for r in range(8, 0, -1):
                draw.text((vx, vy), display_val, font=stat_font, fill=(0, 240, 255, int(55 / r)), stroke_width=r * 2)
            draw.text((vx + 3, vy + 3), display_val, font=stat_font, fill=(0, 0, 0, 160), stroke_width=4, stroke_fill=(0, 0, 0, 180))
            draw.text((vx, vy), display_val, font=stat_font, fill=(0, 240, 255), stroke_width=3, stroke_fill=(0, 0, 0, 180))

            label_font = ImageFont.truetype(font_path_reg, int(44 * (1.18 if self.mode == "portrait" else 1.0)))
            try:
                lw = label_font.getbbox(label)[2] - label_font.getbbox(label)[0]
            except AttributeError:
                lw = draw.textlength(label, font=label_font)
            draw.text(((self.WIDTH - lw) // 2, vy + vh + 45), label, fill=(255, 255, 255), font=label_font)

            narration_font = ImageFont.truetype(font_path_reg, int(30 * (1.18 if self.mode == "portrait" else 1.0)))
            lines = wrap_text(text, narration_font, self.WIDTH - 260)
            ny = self.HEIGHT // 2 + (210 if self.mode == "portrait" else 145)
            for line in lines[:3]:
                try:
                    line_w = narration_font.getbbox(line)[2] - narration_font.getbbox(line)[0]
                except AttributeError:
                    line_w = draw.textlength(line, font=narration_font)
                draw.text(((self.WIDTH - line_w) // 2, ny), line, fill=(210, 220, 235), font=narration_font)
                ny += int(40 * (1.18 if self.mode == "portrait" else 1.0))

            draw_data_hud(draw, self.WIDTH, self.HEIGHT, t, mode=self.mode, color=(0, 240, 255), label="STAT")
            img_arr = np.array(img)
            img_arr = draw_scan_lines(img_arr, opacity=0.06)
            return img_arr

        clip = VideoClip(make_frame, duration=duration)
        return clip.set_fps(30)

    def _build_lower_third_overlay(self, named_entity: str):
        """Shared by render_image()'s photo and video paths — builds the same named-entity
        pill overlay once so both backgrounds get identical treatment."""
        font_path_bold = get_font_path("bold")
        font_path_reg = get_font_path("regular")
        dummy = Image.new("RGBA", (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dummy)
        lt_overlay, bx, by = render_lower_third(
            draw, named_entity,
            ImageFont.truetype(font_path_bold, int(36 * (1.2 if self.mode == 'portrait' else 1.0))),
            ImageFont.truetype(font_path_reg, int(24 * (1.2 if self.mode == 'portrait' else 1.0))),
            self.WIDTH, self.HEIGHT,
            self.mode
        )
        t_draw = ImageDraw.Draw(lt_overlay)
        t_draw.text((bx + 30, by + 15), named_entity.upper(), fill=(0, 240, 255, 255), font=ImageFont.truetype(font_path_bold, int(32 * (1.1 if self.mode == 'portrait' else 1.0))))
        t_draw.text((bx + 30, by + 50), "SCIENTIFIC EVIDENCE", fill=(200, 200, 200, 255), font=ImageFont.truetype(font_path_reg, int(18 * (1.1 if self.mode == 'portrait' else 1.0))))
        return lt_overlay

    def _render_image_scene_video_bg(self, video_path: str, duration: float, named_entity: str = None) -> VideoClip:
        """Real stock-video b-roll used for an 'image'-type scene (see asset_orchestrator.py
        — Pexels/Pixabay video search). Gives it the same cinematic grade / HUD / lower-third
        treatment as a static photo background instead of playing the raw clip unstyled."""
        vc = VideoFileClip(video_path)
        if vc.duration < duration:
            from moviepy.video.fx.all import loop
            vc = loop(vc, duration=duration)
        else:
            vc = vc.subclip(0, duration)

        lt_overlay = self._build_lower_third_overlay(named_entity) if named_entity else None

        def process(frame, t):
            pil_frm = Image.fromarray(frame).convert("RGB")
            graded = apply_cinematic_grade(self._cover_image(pil_frm))
            if self.mode != 'portrait':
                graded = apply_lens_flare(graded, t=t, intensity=0.2)

            graded_rgba = graded.convert("RGBA")
            hud_overlay = Image.new("RGBA", (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
            hud_draw = ImageDraw.Draw(hud_overlay)
            draw_data_hud(hud_draw, self.WIDTH, self.HEIGHT, t, mode=self.mode,
                          color=(0, 240, 255), label="SCIENCE")
            graded_rgba = Image.alpha_composite(graded_rgba, hud_overlay)
            if lt_overlay:
                graded_rgba = Image.alpha_composite(graded_rgba, lt_overlay)
            return np.array(graded_rgba.convert("RGB"))

        return vc.fl(lambda gf, t: process(gf(t), t)).set_fps(30)

    def render_image(self, bg_path: str, text: str, duration: float, named_entity: str = None) -> VideoClip:
        """
        Applies a Ken Burns zoom/pan, cinematic grades, and adds lower thirds if named_entity exists.
        Transparently delegates to a video-background path when bg_path is a real video clip
        (e.g. Pexels/Pixabay stock-video b-roll routed here for an 'image'-type scene).
        """
        if str(bg_path).lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
            return self._render_image_scene_video_bg(bg_path, duration, named_entity)

        pil_img = Image.open(bg_path).convert("RGB")
        img_w, img_h = pil_img.size

        # Setup lower third pill once if present
        lt_overlay = self._build_lower_third_overlay(named_entity) if named_entity else None

        self.image_scene_count += 1
        pan_type = self.image_scene_count % 3

        def make_frame(t):
            # Ken Burns effect
            if self.mode == 'portrait':
                scale = 1.0 + 0.035 * (t / duration)
                cw, ch = int(self.WIDTH / scale), int(self.HEIGHT / scale)
                
                if pan_type == 0:
                    # zoom-in-center
                    x_start = (img_w - cw) // 2
                    y_start = (img_h - ch) // 2
                elif pan_type == 1:
                    # zoom-in-top-right
                    x_start = img_w - cw
                    y_start = 0
                else:
                    # pan-left-to-right (no zoom, or slight zoom to allow pan)
                    cw, ch = int(self.WIDTH / 1.035), int(self.HEIGHT / 1.035)
                    max_x = img_w - cw
                    x_start = int(max_x * (t / duration))
                    y_start = (img_h - ch) // 2
            else:
                # Landscape: alternate between 3 Ken Burns moves
                if pan_type == 0:
                    # Zoom in from center
                    scale = 1.0 + 0.08 * (t / duration)
                    cw, ch = int(self.WIDTH / scale), int(self.HEIGHT / scale)
                    x_start = (img_w - cw) // 2
                    y_start = (img_h - ch) // 2
                elif pan_type == 1:
                    # Pan right while zooming in slightly
                    scale = 1.0 + 0.06 * (t / duration)
                    cw, ch = int(self.WIDTH / scale), int(self.HEIGHT / scale)
                    max_x = max(0, img_w - cw)
                    x_start = int(max_x * (t / duration))
                    y_start = (img_h - ch) // 2
                else:
                    # Zoom out (pull back)
                    scale = 1.08 - 0.08 * (t / duration)
                    cw, ch = int(self.WIDTH / scale), int(self.HEIGHT / scale)
                    x_start = max(0, (img_w - cw) // 2)
                    y_start = max(0, (img_h - ch) // 2)

            x_start = max(0, min(x_start, max(0, img_w - cw)))
            y_start = max(0, min(y_start, max(0, img_h - ch)))
            cropped = pil_img.crop((x_start, y_start, x_start + cw, y_start + ch))
            
            resized = cropped.resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)
            graded = apply_cinematic_grade(resized)
            
            # ── Lens flare effect (landscape only for max visual impact) ──────
            if self.mode != 'portrait':
                graded = apply_lens_flare(graded, t=t, intensity=0.25)

            # ── HUD corner brackets overlay ──────────────────────────────────
            graded_rgba = graded.convert("RGBA")
            hud_overlay = Image.new("RGBA", (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
            hud_draw = ImageDraw.Draw(hud_overlay)
            draw_data_hud(hud_draw, self.WIDTH, self.HEIGHT, t, mode=self.mode,
                          color=(0, 240, 255), label="SCIENCE")
            graded_rgba = Image.alpha_composite(graded_rgba, hud_overlay)

            # ── Composite named entity pill if present ───────────────────────
            if lt_overlay:
                graded_rgba = Image.alpha_composite(graded_rgba, lt_overlay)
                
            return np.array(graded_rgba.convert("RGB"))

        clip = VideoClip(make_frame, duration=duration)
        return clip.set_fps(30)

    def render_ai_video(self, video_path: str, duration: float) -> VideoClip:
        """
        Loads, loops, and cover-crops an AI video clip without stretching.
        """
        vc = VideoFileClip(video_path).without_audio()
        if vc.duration < duration:
            from moviepy.video.fx.all import loop
            vc = loop(vc, duration=duration)
        else:
            vc = vc.subclip(0, duration)

        def cover_grade(frame):
            pil_frm = Image.fromarray(frame).convert("RGB")
            frame = apply_cinematic_grade(self._cover_image(pil_frm)).convert('RGBA')
            draw = ImageDraw.Draw(frame)
            font = ImageFont.truetype(get_font_path('regular'), 28)
            text = 'AI-generated illustration'
            box = draw.textbbox((0, 0), text, font=font)
            x, y = 48, 100
            draw.rounded_rectangle((x-14, y-10, x+box[2]+14, y+box[3]+10), radius=8, fill=(8, 13, 24, 220))
            draw.text((x, y), text, font=font, fill=(225, 236, 239, 255))
            return np.array(frame.convert('RGB'))

        return vc.fl_image(cover_grade).set_fps(30)

    def _cover_image(self, img: Image.Image) -> Image.Image:
        """Resize an image to cover the full scene without distortion.

        BUGFIX: the two branches below were previously swapped — when the source was
        proportionally WIDER than the target (iw/ih > target_ratio), it computed a crop
        HEIGHT of `iw / target_ratio`, which for a wide image is always taller than the
        image itself (e.g. a 1280x720 photo into a 1080x1920 portrait target computed a
        2275px crop height from a 720px-tall source). PIL's crop() doesn't clamp an
        out-of-bounds box — it pads the overflow with solid black — so this silently
        rendered a large black void over most of the frame for any background whose
        aspect ratio didn't already closely match the target. Long-form (16:9) was hit
        hardest since, unlike Shorts, there's no pre-crop step normalizing fetched
        images before they reach this function.
        The fix: when the source is wider than target, crop WIDTH (keep full height);
        when it's narrower/taller than target, crop HEIGHT (keep full width).
        """
        iw, ih = img.size
        target_ratio = self.WIDTH / self.HEIGHT
        if iw / ih > target_ratio:
            new_w = int(ih * target_ratio)
            x = max(0, (iw - new_w) // 2)
            img = img.crop((x, 0, x + new_w, ih))
        else:
            new_h = int(iw / target_ratio)
            y = max(0, (ih - new_h) // 2)
            img = img.crop((0, y, iw, y + new_h))
        return img.resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)

    def _ensure_background_image(self, bg_path: str, scene_idx: int = 0) -> str:
        if bg_path and os.path.exists(bg_path):
            return bg_path

        from PIL import Image as PilImage, ImageDraw
        fallback_dir = os.path.dirname(bg_path) if bg_path else "automation/storage"
        os.makedirs(fallback_dir or "automation/storage", exist_ok=True)
        palettes = [
            ((4, 0, 28), (0, 45, 95), (0, 120, 180)),
            ((10, 0, 45), (45, 0, 90), (110, 20, 130)),
            ((0, 18, 35), (0, 80, 100), (0, 130, 130)),
        ]
        top, mid, bot = palettes[scene_idx % len(palettes)]
        img = PilImage.new("RGB", (self.WIDTH, self.HEIGHT))
        draw = ImageDraw.Draw(img)
        for y in range(self.HEIGHT):
            t = y / max(1, self.HEIGHT - 1)
            if t < 0.5:
                s = t / 0.5
                r = int(top[0] + (mid[0] - top[0]) * s)
                g = int(top[1] + (mid[1] - top[1]) * s)
                b = int(top[2] + (mid[2] - top[2]) * s)
            else:
                s = (t - 0.5) / 0.5
                r = int(mid[0] + (bot[0] - mid[0]) * s)
                g = int(mid[1] + (bot[1] - mid[1]) * s)
                b = int(mid[2] + (bot[2] - mid[2]) * s)
            draw.line([(0, y), (self.WIDTH - 1, y)], fill=(r, g, b))
        draw_starfield_overlay(draw, self.WIDTH, self.HEIGHT, scene_idx, star_count=90, twinkle=False)
        fallback_path = bg_path or os.path.join("automation", "storage", f"fallback_scene_{scene_idx}.jpg")
        img.save(fallback_path, "JPEG", quality=90)
        return fallback_path

    def _draw_glow_text(self, draw, text, xy, font, fill, stroke=2, glow=5):
        for r in range(glow, 0, -1):
            draw.text(
                xy, text,
                font=font,
                fill=(fill[0], fill[1], fill[2], max(20, int(70 / r))),
                stroke_width=r,
            )
        draw.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0, 180))

    def render_hook_question(self, bg_path: str, text: str, duration: float, question_text: str, emphasis_phrase: str = None, word_offsets: list = None, start_time: float = 0.0, topic: str = "") -> VideoClip:
        """
        Renders a visual-first rhetorical question opening scene.
        The hook is broken into 3-5 word bursts with animated background motion,
        neon text, and a progress pulse so the first scene never feels static.
        """
        import re
        from PIL import Image as PilImage

        font_path_bold = get_font_path("bold")
        font_path_reg = get_font_path("regular")

        bg_path = self._ensure_background_image(bg_path, scene_idx=0)
        is_video_bg = bg_path.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm"))
        video_clip = None
        if is_video_bg:
            video_clip = VideoFileClip(bg_path)

        try:
            if is_video_bg:
                base_img = Image.fromarray(video_clip.get_frame(0)).convert("RGB")
            else:
                base_img = Image.open(bg_path).convert("RGB")
            base_img = self._cover_image(base_img)
        except Exception:
            base_img = PilImage.new("RGB", (self.WIDTH, self.HEIGHT), (5, 10, 28))
            base_img = self._cover_image(base_img)

        raw_text_source = (question_text or text).strip().upper()
        raw_text_source = re.sub(r"\s+", " ", raw_text_source.replace("*", "")).strip()
        if not raw_text_source:
            raw_text_source = f"WHAT IS {topic.strip().upper()} REALLY DOING?"

        is_port = self.mode == "portrait"
        chunk_size = 4 if is_port else 6
        words = raw_text_source.replace("\n", " ").split()

        def build_chunks_from_offsets():
            chunks = []
            cur = []
            if word_offsets and start_time is not None:
                scene_words = [
                    w for w in word_offsets
                    if start_time - 0.05 <= w.get("start", 0) <= start_time + duration + 0.05
                ]
                for w in scene_words:
                    clean = re.sub(r"\[.*?\]", "", str(w.get("word", ""))).replace("*", "").strip()
                    if not clean:
                        continue
                    cur.append({"word": clean, "start": max(0.0, w.get("start", 0) - start_time), "duration": w.get("duration", 0.2)})
                    if len(cur) >= chunk_size or clean.endswith((".", "?", "!")):
                        chunks.append(cur)
                        cur = []
                if cur:
                    chunks.append(cur)
            return chunks

        chunks = []
        for group in build_chunks_from_offsets():
            if not group:
                continue
            chunk_text = " ".join(item["word"] for item in group)
            chunk_start = group[0]["start"]
            chunk_end = group[-1]["start"] + group[-1]["duration"]
            chunks.append({"text": chunk_text, "start": chunk_start, "end": min(duration, chunk_end)})

        if not chunks:
            cur = []
            for word in words:
                cur.append(word)
                if len(cur) >= chunk_size or word.endswith((".", "?", "!")):
                    chunks.append({"text": " ".join(cur), "start": 0.0, "end": 0.0})
                    cur = []
            if cur:
                chunks.append({"text": " ".join(cur), "start": 0.0, "end": 0.0})

        if not chunks:
            chunks = [{"text": raw_text_source, "start": 0.0, "end": duration}]

        if word_offsets and start_time is not None:
            equal_step = duration / max(1, len(chunks))
            for idx, chunk in enumerate(chunks):
                if chunk["end"] <= chunk["start"]:
                    chunk["start"] = idx * equal_step
                    chunk["end"] = min(duration, (idx + 1) * equal_step)
        else:
            equal_step = duration / max(1, len(chunks))
            for idx, chunk in enumerate(chunks):
                chunk["start"] = idx * equal_step
                chunk["end"] = min(duration, (idx + 1) * equal_step)

        for idx in range(1, len(chunks)):
            if chunks[idx]["start"] <= chunks[idx - 1]["end"]:
                chunks[idx]["start"] = min(duration - 0.05, chunks[idx - 1]["end"] + 0.02)
            if chunks[idx]["end"] <= chunks[idx]["start"]:
                chunks[idx]["end"] = min(duration, chunks[idx]["start"] + 0.8)
        chunks[-1]["end"] = duration

        emp_clean = (emphasis_phrase or "").strip().upper().replace("*", "")
        # Reduced from 96/113pt (landscape/portrait) — at the old size, a 4-6 word hook
        # chunk with the new pill backdrop dominated the frame. Now close to (rather
        # than well above) the regular pop-caption size for a consistent scale.
        f_chunk = int(70 * (1.18 if is_port else 1.0))
        f_small = int(44 * (1.18 if is_port else 1.0))
        font_chunk = ImageFont.truetype(font_path_bold, f_chunk)
        font_small = ImageFont.truetype(font_path_reg, f_small)

        COLOR_CYAN = (0, 240, 255)
        COLOR_GOLD = (255, 210, 40)
        COLOR_WHITE = (255, 255, 255)

        def active_chunk_for_t(t):
            for idx, chunk in enumerate(chunks):
                if t < chunk["start"]:
                    return max(0, idx - 1), 0.0
                if t < chunk["end"]:
                    local = max(0.0, min(1.0, (t - chunk["start"]) / max(0.001, chunk["end"] - chunk["start"])))
                    return idx, local
            return len(chunks) - 1, 1.0

        def draw_line(draw, line, x, y, color, font, scale=1.0, alpha=255, underline=False):
            try:
                line_w = font.getbbox(line)[2] - font.getbbox(line)[0]
            except AttributeError:
                line_w = draw.textlength(line, font=font)
            scaled_x = x - line_w // 2
            # BUGFIX: this used to be `y*scale + (f_chunk*(1-scale))/2`, which scales the
            # RAW absolute Y pixel coordinate. That's only a subtle few-pixel drift when y
            # is small (text near the old vertical-center position), but once the caption
            # position moved lower on screen (much larger y), the same formula produced a
            # 100+ pixel jump during the pop-in — visibly detaching the text from the
            # pill backdrop drawn at the (unscaled) target position. A small, fixed-size
            # rise that's independent of y's absolute value gives the same "pop up into
            # place" feel without moving the text away from its backdrop.
            pop_rise = int(max(0.0, 1.0 - scale) * 40)
            draw_y = y + pop_rise
            glow_color = (color[0], color[1], color[2], int(alpha * 0.35))
            for r in range(6, 0, -1):
                draw.text(
                    (scaled_x, draw_y),
                    line,
                    font=font,
                    fill=(glow_color[0], glow_color[1], glow_color[2], max(12, int(glow_color[3] / r))),
                    stroke_width=r,
                )
            draw.text(
                (scaled_x, draw_y),
                line,
                font=font,
                fill=(color[0], color[1], color[2], alpha),
                stroke_width=3,
                stroke_fill=(0, 0, 0, int(alpha * 0.75)),
            )
            if underline:
                base_y = draw_y + f_chunk + 12
                for r in range(3, 0, -1):
                    draw.line(
                        [(scaled_x, base_y), (scaled_x + line_w, base_y)],
                        fill=(color[0], color[1], color[2], int(alpha * (0.45 / r))),
                        width=r * 2,
                    )

        def make_frame(t):
            if is_video_bg and video_clip is not None:
                frame_t = t % max(video_clip.duration, 0.001)
                bg_img = Image.fromarray(video_clip.get_frame(frame_t)).convert("RGB")
            else:
                bg_img = base_img.copy()
            bg_img = apply_cinematic_grade(self._cover_image(bg_img))

            motion = 1.0 + 0.13 * (t / max(duration, 0.001))
            cw = int(self.WIDTH / motion)
            ch = int(self.HEIGHT / motion)
            x = max(0, (self.WIDTH - cw) // 2)
            y = max(0, (self.HEIGHT - ch) // 2)
            bg_img = bg_img.crop((x, y, x + cw, y + ch)).resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)

            img = bg_img.convert("RGBA")
            overlay = Image.new("RGBA", (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
            o_draw = ImageDraw.Draw(overlay)
            for yy in range(self.HEIGHT):
                ratio = yy / max(1, self.HEIGHT - 1)
                alpha = int(125 + 95 * abs(ratio - 0.5) * 2)
                o_draw.line([(0, yy), (self.WIDTH, yy)], fill=(3, 6, 18, alpha))
            draw_starfield_overlay(o_draw, self.WIDTH, self.HEIGHT, t, star_count=70, seed=917, twinkle=True)
            img = Image.alpha_composite(img, overlay).convert("RGB")
            draw = ImageDraw.Draw(img)

            active_idx, local = active_chunk_for_t(t)
            chunk = chunks[active_idx]
            chunk_text = chunk["text"]
            # BUGFIX: this used to compare emp_clean (always uppercased) against
            # chunk_text in its ORIGINAL narration case (chunks built from word_offsets
            # keep normal sentence casing, not ALL CAPS) — a case-sensitive `in` check
            # between an uppercase phrase and mixed-case text essentially never matched
            # in real usage, so the gold emphasis highlight almost never actually fired.
            is_emphasis = bool(emp_clean and emp_clean in chunk_text.upper())
            # Text color now matches the rest of the video's caption language (white /
            # gold-for-emphasis) instead of its own cyan/gold scheme — previously this
            # opening hook was the one place that still looked like a distinct, older
            # style. The cyan sci-fi accent is kept, but only for the HUD/progress-bar
            # chrome below, not the words themselves.
            text_color = COLOR_GOLD if is_emphasis else COLOR_WHITE
            accent_color = COLOR_GOLD if is_emphasis else COLOR_CYAN

            ease = 1.0 - (1.0 - local) ** 3
            scale = 0.84 + 0.16 * ease + 0.025 * math.sin(local * math.pi * 2)
            alpha = int(255 * min(1.0, local / 0.22))
            if local > 0.72:
                alpha = int(alpha * (1.0 - (local - 0.72) / 0.28 * 0.18))

            lines = wrap_text(chunk_text, font_chunk, self.WIDTH - 170)
            total_h = len(lines) * int(f_chunk * 1.15)
            # Same vertical anchor as every other caption (pop-up captions,
            # typewriter_text) instead of this scene's own dead-center position —
            # previously the opening hook was the one place captions still sat in the
            # middle of the frame, right over the main subject.
            caption_frac = PORTRAIT_CAPTION_Y_FRACTION if is_port else LANDSCAPE_CAPTION_Y_FRACTION
            y_start_orig = max(160 if is_port else 130, int(self.HEIGHT * caption_frac) - total_h // 2)

            # Pill backdrop behind the hook text, matching the caption pill used
            # everywhere else in the video (see caption_style.py) instead of floating
            # text directly over the b-roll.
            line_widths = []
            for line in lines:
                try:
                    bbox = font_chunk.getbbox(line)
                    line_widths.append(bbox[2] - bbox[0])
                except AttributeError:
                    line_widths.append(draw.textlength(line, font=font_chunk))
            max_line_w = max(line_widths) if line_widths else 0
            pill_pad_x, pill_pad_y = 50, 32
            pill_w = int((max_line_w + pill_pad_x * 2) * scale)
            pill_h = int((total_h + pill_pad_y * 2) * scale)
            pill_cx = self.WIDTH // 2
            pill_cy = y_start_orig + total_h // 2 - int(f_chunk * 0.12)
            # Fixed opacity rather than tied to `alpha` above: `alpha` is meant to fade
            # the text in/out at chunk boundaries, but PIL's ImageDraw.text() ignores
            # the alpha channel of an RGBA fill when drawing onto an RGB-mode image (the
            # text below is always fully opaque regardless of `alpha`) — pill_overlay,
            # drawn separately and alpha_composited in properly, DOES honor alpha, so
            # tying it to the same variable made the pill visibly fade in/out under text
            # that wasn't fading at all. Matches caption_style.PILL_FILL's opacity.
            pill_overlay = Image.new("RGBA", (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
            p_draw = ImageDraw.Draw(pill_overlay)
            p_draw.rounded_rectangle(
                [(pill_cx - pill_w // 2, pill_cy - pill_h // 2),
                 (pill_cx + pill_w // 2, pill_cy + pill_h // 2)],
                radius=32, fill=(8, 13, 24, 232),
            )
            img = Image.alpha_composite(img.convert("RGBA"), pill_overlay).convert("RGB")
            draw = ImageDraw.Draw(img)

            y_start = y_start_orig
            for line in lines:
                draw_line(draw, line, self.WIDTH // 2, y_start, text_color, font_chunk, scale=scale, alpha=alpha, underline=is_emphasis)
                y_start += int(f_chunk * 1.15)

            progress = local
            bar_y = self.HEIGHT - (130 if is_port else 90)
            bar_x = 90 if is_port else 260
            bar_w = self.WIDTH - (180 if is_port else 520)
            bar_h = 8 if is_port else 6
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h)], radius=8, fill=(255, 255, 255, 55))
            draw.rounded_rectangle(
                [(bar_x, bar_y), (bar_x + int(bar_w * progress), bar_y + bar_h)],
                radius=8,
                fill=accent_color + (245,),
            )

            draw_data_hud(draw, self.WIDTH, self.HEIGHT, t, mode=self.mode, color=accent_color, label="HOOK")
            img_arr = np.array(img)
            img_arr = draw_scan_lines(img_arr, opacity=0.05)
            return img_arr

        clip = VideoClip(make_frame, duration=duration)
        if video_clip is not None:
            clip.on_closed(lambda: video_clip.close())
        return clip.set_fps(30)

    def render_subscribe_badge(self, duration: float, main_text: str = "SUBSCRIBE",
                                sub_text: str = "for more mind-bending science") -> VideoClip:
        """
        Renders a small pulsing 'Subscribe' pill + bell icon meant to be composited
        as a transparent overlay on top of the final seconds of a video, rather than
        replacing the visual. Uses color-keying (a near-black key unlikely to occur
        naturally) so it can be layered without needing a real alpha-supporting
        VideoClip pipeline.
        """
        KEY_COLOR = (1, 2, 3)
        font_path_bold = get_font_path("bold")
        font_path_reg = get_font_path("regular")
        is_port = self.mode == 'portrait'

        main_font = ImageFont.truetype(font_path_bold, int(56 if is_port else 42))
        sub_font = ImageFont.truetype(font_path_reg, int(28 if is_port else 22))

        cx = self.WIDTH // 2
        cy = self.HEIGHT - (300 if is_port else 170)

        # ── Measure text once so the pill always fits it, at any scale ─────────
        dummy = Image.new("RGB", (1, 1))
        dd = ImageDraw.Draw(dummy)
        text_bbox = dd.textbbox((0, 0), main_text, font=main_font)
        text_w = text_bbox[2] - text_bbox[0]

        bell_r_base = 20
        pad_left = 30       # left edge -> bell center
        bell_to_text = 34   # bell edge -> text start
        pad_right = 36       # text end -> right edge

        base_pill_w = pad_left + bell_r_base + bell_to_text + text_w + pad_right
        base_pill_h = 96 if not is_port else 108
        bell_cx_offset = -(base_pill_w // 2) + pad_left  # relative to cx
        text_x_offset = bell_cx_offset + bell_r_base + bell_to_text  # relative to cx

        def make_frame(t):
            img = Image.new("RGB", (self.WIDTH, self.HEIGHT), KEY_COLOR)
            draw = ImageDraw.Draw(img)

            # Entrance: pop in over the first 0.35s, then a gentle continuous pulse
            entrance = min(1.0, t / 0.35)
            ease = 1.0 - (1.0 - entrance) ** 3
            pulse = 1.0 + 0.05 * math.sin(max(0.0, t - 0.35) * 3.2)
            scale = ease * pulse

            pill_w, pill_h = int(base_pill_w * scale), int(base_pill_h * scale)
            if pill_w <= 0 or pill_h <= 0:
                return np.array(img)

            # Soft glow ring
            glow_r = int(14 * (0.6 + 0.4 * math.sin(t * 3.2)))
            draw.rounded_rectangle(
                [(cx - pill_w // 2 - glow_r, cy - pill_h // 2 - glow_r),
                 (cx + pill_w // 2 + glow_r, cy + pill_h // 2 + glow_r)],
                radius=(pill_h // 2 + glow_r), fill=(255, 30, 60)
            )
            # Main red pill (YouTube-subscribe red)
            draw.rounded_rectangle(
                [(cx - pill_w // 2, cy - pill_h // 2), (cx + pill_w // 2, cy + pill_h // 2)],
                radius=pill_h // 2, fill=(230, 20, 40)
            )
            # Bell icon (simple geometric bell, left of text)
            bell_cx = cx + int(bell_cx_offset * scale)
            bell_cy = cy
            bell_r = int(bell_r_base * scale)
            if bell_r > 1:
                wobble = math.sin(t * 6.0) * 6 if t < 1.2 else 0
                draw.arc(
                    [(bell_cx - bell_r, bell_cy - bell_r), (bell_cx + bell_r, bell_cy + bell_r)],
                    start=200 + wobble, end=340 + wobble, fill=(255, 255, 255), width=max(2, int(4 * scale))
                )
                draw.ellipse(
                    [(bell_cx - 3, bell_cy + bell_r - 4), (bell_cx + 3, bell_cy + bell_r + 2)],
                    fill=(255, 255, 255)
                )

            if entrance > 0.5:
                text_alpha_scale = min(1.0, (entrance - 0.5) / 0.5)
                text_x = cx + int(text_x_offset * scale)
                if text_alpha_scale > 0.3:
                    draw.text((text_x, cy), main_text, font=main_font, fill=(255, 255, 255), anchor="lm")

            if entrance >= 1.0:
                draw.text((cx, cy + pill_h // 2 + 34), sub_text, font=sub_font, fill=(225, 225, 235), anchor="mm")

            return np.array(img)

        clip = VideoClip(make_frame, duration=duration).set_fps(30)
        from moviepy.video.fx.all import mask_color
        clip = mask_color(clip, color=KEY_COLOR, thr=6, s=6)
        return clip

    def render_data_bars(self, bg_path: str, text: str, duration: float, bar_data: list) -> VideoClip:
        """
        Compares multiple values using animated 3D-styled data bars.
        """
        font_path_bold = get_font_path("condensed_bold")
        font_path_reg = get_font_path("regular")

        bg_path = self._ensure_background_image(bg_path, scene_idx=3)
        bg_img = Image.open(bg_path).convert("RGB")
        bg_graded = apply_cinematic_grade(self._cover_image(bg_img))

        if not bar_data or not isinstance(bar_data, list):
            raise ValueError("Chart data is required; refusing to invent comparison values.")

        values = [float(b.get("value", 0)) for b in bar_data]
        max_val = max(values) if max(values) > 0 else 1.0

        is_port = self.mode == "portrait"
        bar_count = len(bar_data)
        chart_w = (self.WIDTH - 170) if is_port else 1200
        chart_h = (self.HEIGHT // 3) if is_port else 500
        chart_x = (self.WIDTH - chart_w) // 2
        chart_y = (self.HEIGHT - chart_h) // 2 - (35 if is_port else 0)

        bar_gap = 30 if is_port else 60
        total_gaps_w = bar_gap * max(bar_count - 1, 0)
        bar_w = (chart_w - total_gaps_w) // max(bar_count, 1)
        colors = [(0, 240, 255), (255, 0, 180), (150, 0, 255), (255, 150, 0)]

        def make_frame(t):
            motion = 1.0 + 0.07 * (t / max(duration, 0.001))
            cw = int(self.WIDTH / motion)
            ch = int(self.HEIGHT / motion)
            x = max(0, (self.WIDTH - cw) // 2)
            y = max(0, (self.HEIGHT - ch) // 2)
            img = bg_graded.crop((x, y, x + cw, y + ch)).resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)

            overlay = Image.new("RGBA", (self.WIDTH, self.HEIGHT), (0, 0, 0, 0))
            o_draw = ImageDraw.Draw(overlay)
            panel_pad_x = 30 if is_port else 70
            panel_pad_top = 95 if is_port else 95
            panel_pad_bot = 120 if is_port else 125
            o_draw.rounded_rectangle(
                [(chart_x - panel_pad_x, chart_y - panel_pad_top),
                 (chart_x + chart_w + panel_pad_x, chart_y + chart_h + panel_pad_bot)],
                radius=24,
                fill=(7, 14, 32, 215),
            )
            o_draw.rectangle(
                [(chart_x, chart_y + chart_h + 12), (chart_x + chart_w, chart_y + chart_h + 18)],
                fill=(0, 240, 255, 255),
            )
            draw_starfield_overlay(o_draw, self.WIDTH, self.HEIGHT, t, star_count=60, seed=4321, twinkle=True)
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(img)

            title_font = ImageFont.truetype(font_path_bold, 30 if is_port else 42)
            title = "COMPARATIVE SCIENTIFIC ANALYSIS"
            try:
                tw = title_font.getbbox(title)[2] - title_font.getbbox(title)[0]
            except AttributeError:
                tw = draw.textlength(title, font=title_font)
            draw.text(((self.WIDTH - tw) // 2, chart_y - (65 if is_port else 58)), title, fill=(0, 240, 255), font=title_font)

            anim_dur = min(1.45, duration)
            fraction = 1.0 if t >= anim_dur else 1.0 - (1.0 - t / anim_dur) ** 3

            label_font = ImageFont.truetype(font_path_reg, 18 if is_port else 24)
            val_font = ImageFont.truetype(font_path_bold, 22 if is_port else 32)

            for i, item in enumerate(bar_data):
                lbl = str(item.get("label", "")).upper()
                val = float(item.get("value", 0))
                pct = val / max_val
                target_bar_h = int(pct * chart_h)
                delay = min(0.35, duration * 0.08 * i)
                local_t = max(0.0, min(1.0, (t - delay) / max(0.001, anim_dur - delay)))
                bar_fraction = 1.0 if local_t >= 1.0 else 1.0 - (1.0 - local_t) ** 3
                current_bar_h = int(target_bar_h * bar_fraction * fraction)

                bx1 = chart_x + i * (bar_w + bar_gap)
                by1 = chart_y + chart_h - current_bar_h
                bx2 = bx1 + bar_w
                by2 = chart_y + chart_h

                bar_color = colors[i % len(colors)]
                is_highest = abs(val - max_val) < 0.0001 and bar_fraction > 0.9
                if is_highest:
                    glow_radius = int(18 + 8 * math.sin(t * 5.0))
                    o_draw.ellipse([(bx1 - glow_radius, by1 - glow_radius), (bx2 + glow_radius, by2 + glow_radius)], fill=(255, 215, 0, 45))

                draw.rectangle([(bx1, by1), (bx2, by2)], fill=bar_color)
                edge_w = 5 if is_port else 10
                draw.rectangle([(bx2 - edge_w, by1), (bx2, by2)], fill=(max(0, bar_color[0] - 50), max(0, bar_color[1] - 50), max(0, bar_color[2] - 50)))
                draw.rectangle([(bx1, by1), (bx1 + 8, by2)], fill=(255, 255, 255, 45))

                val_text = f"{val:g}"
                try:
                    vw = val_font.getbbox(val_text)[2] - val_font.getbbox(val_text)[0]
                except AttributeError:
                    vw = val_font.getsize(val_text)[0]
                vx = bx1 + (bar_w - vw) // 2
                vy = by1 - (38 if is_port else 48)
                if current_bar_h > 20 or t >= anim_dur:
                    draw.text((vx, vy), val_text, fill=(255, 255, 255), font=val_font)
                    if is_highest:
                        draw.text((vx, vy), val_text, fill=(255, 215, 0, 120), font=val_font, stroke_width=2)

                try:
                    lw = label_font.getbbox(lbl)[2] - label_font.getbbox(lbl)[0]
                except AttributeError:
                    lw = label_font.getsize(lbl)[0]
                lx = bx1 + (bar_w - lw) // 2
                draw.text((lx, by2 + (16 if is_port else 24)), lbl, fill=(210, 220, 235), font=label_font)

            draw_data_hud(draw, self.WIDTH, self.HEIGHT, t, mode=self.mode, color=(0, 240, 255), label="DATA")
            img_arr = np.array(img)
            img_arr = draw_scan_lines(img_arr, opacity=0.05)
            return img_arr

        clip = VideoClip(make_frame, duration=duration)
        return clip.set_fps(30)
