"""Shared timed captions with an outlined type treatment over documentary media."""
import os
import re
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Single source of truth for WHERE caption-style text sits, shared by the pop-up word
# captions here AND scene_renderer.py's hook_question/typewriter hero text — previously
# each had its own position (pop captions at 60% down, hook_question dead-center via
# (HEIGHT - text_h)//2), so the opening hook visibly jumped to a different spot than
# every other caption in the video. 0.70 sits below center (clear of the main subject)
# but above YouTube's bottom ~15-20% title/description/engagement-rail safe zone.
PORTRAIT_CAPTION_Y_FRACTION = 0.70
LANDSCAPE_CAPTION_Y_FRACTION = 0.78

# Caption-specific accent — deliberately distinct from the cyan HUD/lower-third accent
# so highlighted words pop against both the pill and the cyan sci-fi overlay elements.
HIGHLIGHT_COLOR = (142, 218, 224)
NORMAL_COLOR = (255, 255, 255)

_FONT_PATHS = [
    "automation/fonts/Barlow-Bold.ttf",
    "automation/fonts/Barlow-Regular.ttf",
    "automation/media/assets/Montserrat-Black.ttf",
    "automation/media/assets/Montserrat-ExtraBold.ttf",
    "C:\\Windows\\Fonts\\ariblk.ttf",
    "C:\\Windows\\Fonts\\impact.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
]

def get_pop_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def build_pop_chunks(word_offsets: list, max_words: int = 5) -> list:
    """Group timed words into short chunks, flushing on sentence punctuation."""
    chunks = []
    cur_chunk, cur_len = [], 0
    for w in word_offsets:
        wclean = re.sub(r'\[.*?\]', '', str(w.get('word', '')).replace('*', '')).strip()
        if not wclean:
            continue
        if cur_len >= max_words or (cur_len >= 2 and wclean.endswith(('.', '?', '!', ','))):
            chunks.append(cur_chunk)
            cur_chunk, cur_len = [], 0
        cur_chunk.append({**w, 'display': wclean})
        cur_len += 1
        if wclean.endswith(('.', '?', '!')):
            chunks.append(cur_chunk)
            cur_chunk, cur_len = [], 0
    if cur_chunk:
        chunks.append(cur_chunk)
    return chunks


def render_caption_pill(words_display: list, highlight_mask: list, font, max_w: int = 900) -> Image.Image:
    """Render a transparent caption with a fine outline and a timed accent."""
    STROKE, SHADOW = 2, 2
    HP, VP = 26, 18        # text padding inside the pill
    MARGIN = 16             # room around the pill for stroke/shadow overflow

    dummy = Image.new('RGB', (1, 1))
    dd = ImageDraw.Draw(dummy)
    sp_bbox = dd.textbbox((0, 0), " ", font=font)
    sp_w = max(sp_bbox[2] - sp_bbox[0], 10)

    lines, current_line, current_w, max_h = [], [], 0, 0
    for idx, wrd in enumerate(words_display):
        bb = dd.textbbox((0, 0), wrd, font=font)
        ww, wh = bb[2] - bb[0], bb[3] - bb[1]
        max_h = max(max_h, wh)
        if current_line and current_w + ww + sp_w > max_w:
            lines.append(current_line)
            current_line, current_w = [], 0
        current_line.append((idx, wrd, ww, wh))
        current_w += ww + (sp_w if len(current_line) > 1 else 0)
    if current_line:
        lines.append(current_line)

    line_widths = [sum(w[2] for w in ln) + sp_w * max(len(ln) - 1, 0) for ln in lines]
    text_w = max(line_widths) if line_widths else 0
    line_gap = 12
    text_h = len(lines) * max_h + max(len(lines) - 1, 0) * line_gap

    pill_w = text_w + HP * 2
    pill_h = text_h + VP * 2
    img_w = int(pill_w + MARGIN * 2)
    img_h = int(pill_h + MARGIN * 2)

    img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    y = MARGIN + VP
    for line_idx, line in enumerate(lines):
        line_w = line_widths[line_idx]
        x = MARGIN + (pill_w - line_w) // 2
        for idx, wrd, ww, _ in line:
            color = HIGHLIGHT_COLOR if highlight_mask[idx] else NORMAL_COLOR
            d.text((x + SHADOW, y + SHADOW), wrd, font=font, fill=(0, 0, 0, 150))
            d.text((x, y), wrd, font=font, fill=color,
                   stroke_width=STROKE, stroke_fill=(0, 0, 0, 220))
            x += ww + sp_w
        y += max_h + line_gap

    return img


def make_pop_caption_clip(chunk: list, chunk_dur: float, font, max_w: int = 900, caption_y: int = 0):
    """Builds a fully positioned, ready-to-append clip for one caption chunk (already
    `.set_start()`'d from the chunk's absolute timing), with a quick rise + fade pop-in.

    Internally this is a short sequence of transparent caption images — one per word in the
    chunk, each with only that word gold — stitched back to back at the word's own TTS
    timing, so the highlight visibly tracks the narration instead of highlighting
    "long words" for the whole chunk regardless of which one is playing.

    Fade and position preserve soft RGBA edges on MoviePy 1.x.
    """
    from moviepy.editor import ImageClip, CompositeVideoClip

    words_display = [c['display'] for c in chunk]
    n = len(chunk)
    chunk_start = chunk[0]['start']

    # Chunk-relative start time for each word, clamped to stay within [0, chunk_dur)
    # and monotonically increasing even if upstream timestamps have tiny overlaps.
    local_starts = []
    prev = 0.0
    for w in chunk:
        s = max(prev, min(chunk_dur - 0.02, w['start'] - chunk_start))
        local_starts.append(max(0.0, s))
        prev = s

    word_clips = []
    base_size = None
    for i in range(n):
        hi_mask = [j == i for j in range(n)]
        pil_img = render_caption_pill(words_display, hi_mask, font, max_w=max_w)
        base_size = base_size or pil_img.size
        word_dur = (local_starts[i + 1] if i + 1 < n else chunk_dur) - local_starts[i]
        word_clips.append(
            ImageClip(np.array(pil_img)).set_start(local_starts[i]).set_duration(max(0.05, word_dur))
        )

    combined = CompositeVideoClip(word_clips, size=base_size).set_duration(chunk_dur)

    anim_dur = min(0.15, chunk_dur * 0.4)
    try:
        combined = combined.fadein(anim_dur)
    except Exception:
        pass
    rise_px = 0
    combined = combined.set_position(
        lambda t, ad=anim_dur, y=caption_y: ('center', y + int(rise_px * (1.0 - min(1.0, t / max(ad, 0.001)))))
    )
    combined = combined.set_start(chunk_start)
    return combined
