"""Layer validated explanatory diagrams over contextual documentary media."""
import os
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
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
                            word_offsets=word_offsets, scene_start=start)
    scene['rendered_asset_path'] = context
    if context.lower().endswith(('.mp4', '.mov', '.webm', '.mkv', '.avi')):
        source = VideoFileClip(context).without_audio()
        source = source.fx(vfx.loop, duration=duration) if source.duration < duration else source.subclip(0, duration)
    else:
        source = ImageClip(context).set_duration(duration)

    def blur(frame):
        image = Image.fromarray(frame).resize((270, 480) if portrait else (480, 270))
        image = ImageEnhance.Brightness(image.filter(ImageFilter.GaussianBlur(5))).enhance(.45)
        return np.array(image.resize(size, Image.Resampling.BILINEAR))

    background = _fill(source, size).fl_image(blur)
    # Keep the authentic subject clear while the diagram explains the relationship.
    subject_size = (1000, 540) if portrait else (960, 760)
    subject = source.resize(min(subject_size[0] / source.w, subject_size[1] / source.h))
    left, top = (40, 80) if portrait else (50, 100)
    subject = subject.set_position((left + (subject_size[0]-subject.w)/2,
                                    top + (subject_size[1]-subject.h)/2))
    panel = VideoFileClip(path).without_audio().set_duration(duration)
    panel = panel.crop(y2=int(panel.h * .78))
    panel = panel.resize(width=1020 if portrait else 820)
    panel = panel.set_position((30, 650) if portrait else (1050, 100))
    result = CompositeVideoClip([background, subject, panel], size=size).set_duration(duration)
    close_composite = result.close

    def close():
        close_composite()
        panel.close()
        source.close()

    result.close = close
    return result
