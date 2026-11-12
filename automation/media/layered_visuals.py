"""Layer validated explanatory diagrams over contextual documentary media."""
import os
import numpy as np
from PIL import Image
from moviepy.editor import CompositeVideoClip, ImageClip, VideoFileClip, vfx
from .motion_graphics import render_animation


def _fill(clip, size):
    width, height = size
    scaled = clip.resize(max(width / clip.w, height / clip.h))
    return scaled.crop(x_center=scaled.w / 2, y_center=scaled.h / 2,
                       width=width, height=height)


def render_explainer(scene, duration, size, word_offsets, start):
    context = scene.get('context_path')
    if not context or not os.path.isfile(context):
        path = render_animation(scene['animation'], duration, *size, scene.get('asset_path'),
                                word_offsets=word_offsets, scene_start=start)
        scene['rendered_asset_path'] = path
        return VideoFileClip(path).without_audio().set_duration(duration)

    portrait = size[1] > size[0]
    panel_size = (1080, 960) if portrait else (900, 900)
    path = render_animation(scene['animation'], duration, *panel_size,
                            word_offsets=word_offsets, scene_start=start, overlay=True, centered=not portrait)
    scene['rendered_asset_path'] = context
    if context.lower().endswith(('.mp4', '.mov', '.webm', '.mkv', '.avi')):
        source = VideoFileClip(context).without_audio()
        source = source.fx(vfx.loop, duration=duration) if source.duration < duration else source.subclip(0, duration)
    else:
        source = ImageClip(context).set_duration(duration)

    # One documentary background, with a continuous shade only where labels sit.
    width, height = size
    axis = np.arange(height) / height if portrait else np.arange(width) / width
    opacity = np.interp(axis, [.25, .55, 1], [0, 175, 205]).astype(np.uint8)
    gradient = np.broadcast_to(opacity[:, None] if portrait else opacity[None, :],
                               (height, width)).copy()
    shade = Image.fromarray(gradient, 'L')
    black = Image.new('RGB', size)

    def shade_frame(frame):
        return np.array(Image.composite(black, Image.fromarray(frame), shade))

    background = _fill(source, size).fl_image(shade_frame)
    panel = VideoFileClip(path).without_audio().set_duration(duration)
    panel = panel.crop(y2=int(panel.h * .78))
    panel = panel.resize(width=1020 if portrait else 820)
    panel = panel.fx(vfx.mask_color, color=[0, 0, 0], thr=18, s=2)
    panel = panel.set_position((30, 650) if portrait else ((width-panel.w)/2, (height-panel.h)/2))
    result = CompositeVideoClip([background, panel], size=size).set_duration(duration)
    close_composite = result.close

    def close():
        close_composite()
        panel.close()
        source.close()

    result.close = close
    return result
