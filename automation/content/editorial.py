"""Deterministic editorial checks shared by both video formats."""
import re
from ..media.motion_graphics import validate_animation, infer_animation

DIRECTOR_BRIEF = """
EDITORIAL OVERRIDE (takes precedence over legacy style/mix instructions below):
Create an observational science documentary, with real, specific subjects on screen.
Keep narration VERBATIM, in order, covering the ENTIRE supplied script exactly once.
Each shot should cover one idea, normally 8-18 spoken words. No fixed scene count.
Prioritize a specific real subject in each shot. Use animation to explain mechanisms
and relationships alongside real imagery. For an animation that benefits from a
real subject, set media_context=true and supply a concrete image_cue. The editor
will layer the diagram above a softly blurred photo or video, with a clear subject
window. Use standalone diagrams when no authentic subject image adds meaning.
Prefer images for identifying subjects and video for an actual relevant action.
A new shot must add explanatory information, not repeat the previous label.
Text is for short labels, captions or a useful number, not a wall of narration.
Animation data must use one of: flow, transport, comparison, bars, orbit, refraction,
photo. Use 2-4 short nodes for flow/transport; exactly two for comparison/orbit.
Each node has label (1-4 words taken from this scene) and icon (particle, leaf, water,
ocean, rock, sun, planet, cell, dna, atom, brain, magnet, telescope, microbe). Give the animation a concise title. Flow arrows must
follow a relationship actually explained in the narration. Bars need spoken values
and one shared unit. Refraction illustrates air-to-water light bending only. Photo
uses a verified image and short subject labels. Do not use animations as measured
simulations or add numerical claims that are absent from the script. No mandatory hook_question, typewriter, chart, or AI-video quota.
Use kinetic_stat only for a value explicitly spoken; data_bars only when ALL values
are spoken, comparable, and share units. Never invent comparison data.
Prefer real footage/photos for named people, discoveries and historical events.
Use ai_video for 1-2 useful illustrative shots that stock cannot show, such as a
hypothetical exoplanet environment. Describe a specific subject, action and camera
in ai_video_prompt. These shots are labeled illustrations, never evidence or data.
Do not invent detailed molecular structures or simulate measurements as footage.
image_cue: 3-7 concrete search words identifying the actual subject and action.
Avoid cinematic, 4k, wallpaper, abstract background, and unrelated space imagery.
"""


def _words(text):
    return re.findall(r"\w+", str(text).replace('*', '').lower())


def prepare_scenes(scenes, script, topic):
    """Repair omitted/reordered narration and remove unsupported graphic treatments."""
    scenes = [dict(s) for s in scenes if isinstance(s, dict) and s.get('narration')]
    actual = _words(' '.join(s['narration'] for s in scenes))
    if actual != _words(script):
        # Sentence boundaries preserve decimals, unlike split('.'). Never lose the ending.
        scenes = [{'narration': s, 'visual_type': 'image', 'image_cue': topic}
                  for s in re.split(r'(?<=[.!?])\s+', script.strip()) if s]
    result = []
    ai_count = 0
    for scene in scenes:
        text = scene['narration']
        kind = scene.get('visual_type', 'image')
        numbers = re.findall(r'\d+(?:[.,]\d+)*', text)
        animation = validate_animation(scene.get('animation'), text, topic)
        if not animation and kind == 'image':
            animation = infer_animation(text, topic)
        if kind == 'animation' and not animation:
            kind = 'image'
        elif animation and kind in ('image', 'animation'):
            kind = 'animation'
            scene['animation'] = animation
        if kind == 'kinetic_stat':
            stat = scene.get('stat_data') or {}
            value = str(stat.get('value', ''))
            if not value or value not in numbers:
                kind = 'image'
        if kind == 'data_bars':
            bars = scene.get('bar_data') or []
            if len(bars) < 3 or any(str(b.get('value')) not in numbers for b in bars):
                kind = 'image'
        if kind == 'ai_video':
            if not scene.get('ai_video_prompt') or ai_count >= 2:
                kind = 'image'
            else:
                ai_count += 1
        if kind in ('hook_question', 'typewriter_text'):
            kind = 'image'
        # Split long static holds at phrase boundaries. All words remain in order.
        words = text.split()
        chunks = [words[i:i + 18] for i in range(0, len(words), 18)] if (kind == 'image' or len(words) > 30) else [words]
        for chunk in chunks:
            chunk_text = ' '.join(chunk)
            chunk_kind = kind
            if kind == 'animation' and not validate_animation(scene.get('animation'), chunk_text, topic):
                chunk_kind = 'image'
            result.append({**scene, 'narration': chunk_text, 'visual_type': chunk_kind})
    if not result:
        raise ValueError('Cannot render an empty scene plan')
    return result
