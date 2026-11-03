"""Offline typography/illustration preview; no generated footage or narration."""
import math
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from moviepy.editor import VideoClip
from automation.media.caption_style import get_pop_font, render_caption_pill


def render(t):
    img = Image.new('RGB', (1080, 1920), '#101c28')
    d = ImageDraw.Draw(img)
    d.text((90, 125), 'FIELD NOTES  /  01', font=get_pop_font(30), fill='#8edae0')
    d.text((90, 215), 'Why light bends', font=get_pop_font(82), fill='#f4f6f5')
    d.text((90, 325), 'A change of medium. A change of direction.', font=get_pop_font(34), fill='#b5c4cb')
    d.rectangle((0, 900, 1080, 1550), fill='#183e51')
    d.line((90, 900, 990, 900), fill='#8edae0', width=3)
    d.line((540, 500, 540, 1330), fill='#627a88', width=2)
    d.text((90, 810), 'AIR', font=get_pop_font(32), fill='#b5c4cb')
    d.text((90, 950), 'WATER', font=get_pop_font(32), fill='#b5c4cb')
    # Snell's law: 45 degrees in air -> about 32 degrees in water.
    path = [(240, 600), (540, 900), (727, 1200)]
    d.line(path, fill='#f4d49b', width=7)
    progress = min(t / 4, 1)
    if progress < .5:
        x, y = 240 + 600 * progress, 600 + 600 * progress
    else:
        x, y = 540 + 374 * (progress - .5), 900 + 600 * (progress - .5)
    d.ellipse((x-10, y-10, x+10, y+10), fill='#ffffff')
    words = ['Light', 'slows', 'down', 'in', 'water.']
    pill = render_caption_pill(words, [i == min(4, int(t / .8)) for i in range(5)], get_pop_font(64), max_w=820)
    img.paste(pill, ((1080-pill.width)//2, 1370), pill)
    d.text((90, 1730), 'STYLE PREVIEW / authored illustration / no narration', font=get_pop_font(26), fill='#93aab7')
    return np.array(img.resize((540, 960), Image.Resampling.LANCZOS))


if __name__ == '__main__':
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(render(1.6)).save(out / 'style-preview.png')
    clip = VideoClip(render, duration=4)
    clip.write_videofile(str(out / 'style-preview.mp4'), fps=24, codec='libx264', audio=False, logger=None)
    clip.close()
