"""Layer validated explanatory diagrams over contextual documentary media."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
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

    width, height = size
    panel = VideoFileClip(path).without_audio().set_duration(duration)
    panel = panel.crop(y2=int(panel.h * .82))
    panel_width = width * .945 if portrait else min(width * .72, height * .94 / .82)
    panel = panel.resize(width=int(panel_width))
    panel = panel.fx(vfx.mask_color, color=[0, 0, 0], thr=60, s=4)
    position = ((width-panel.w)/2, height*.31) if portrait else ((width-panel.w)/2, (height-panel.h)/2)
    panel = panel.set_position(position)

    # Feathered optical separation, on the same image, with no panel-shaped edge.
    x, y = position
    feather = int(min(size) * .065)
    mask = Image.new('L', size)
    ImageDraw.Draw(mask).rounded_rectangle(
        (x-feather, y-feather, x+panel.w+feather, y+panel.h+feather),
        radius=feather*2, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather))
    alpha = np.asarray(mask, dtype=np.float32)[..., None] / 255

    def separate_explanation(frame):
        original = Image.fromarray(frame).convert('RGB')
        # Downsampled blur keeps moving backgrounds practical on CPU runners.
        blurred = original.resize((max(1,width//4), max(1,height//4)))
        blurred = blurred.filter(ImageFilter.GaussianBlur(6)).resize(size, Image.Resampling.BILINEAR)
        softened = np.asarray(blurred, dtype=np.float32) * .48
        return np.clip(np.asarray(original) * (1-alpha) + softened * alpha, 0, 255).astype(np.uint8)

    background = _fill(source, size).fl_image(separate_explanation)
    result = CompositeVideoClip([background, panel], size=size).set_duration(duration)
    close_composite = result.close

    def close():
        close_composite()
        panel.close()
        source.close()

    result.close = close
    return result
