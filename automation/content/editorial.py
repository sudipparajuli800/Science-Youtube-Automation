"""Deterministic editorial checks shared by both video formats."""
import re

DIRECTOR_BRIEF = """
EDITORIAL OVERRIDE (takes precedence over legacy style/mix instructions below):
Create an observational science documentary, with real, specific subjects on screen.
Keep narration VERBATIM, in order, covering the ENTIRE supplied script exactly once.
Each shot should cover one idea, normally 8-18 spoken words. No fixed scene count.
Use image for most shots. Text is for a short label or a useful number, not a wall
of narration. No mandatory hook_question, typewriter, chart, or AI-video quota.
Use kinetic_stat only for a value explicitly spoken; data_bars only when ALL values
are spoken, comparable, and share units. Never invent comparison data.
Prefer real footage/photos; do not request AI video of scientific mechanisms.
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
        scenes = [{'narration': s, 'visual_type': 'image', 'image_cue': ' '.join(re.findall(r'[A-Za-z]{3,}', s)[:7]) or topic}
                  for s in re.split(r'(?<=[.!?])\s+', script.strip()) if s]
    result = []
    for scene in scenes:
        text = scene['narration']
        kind = scene.get('visual_type', 'image')
        numbers = re.findall(r'\d+(?:[.,]\d+)*', text)
        if kind == 'kinetic_stat':
            stat = scene.get('stat_data') or {}
            value = str(stat.get('value', ''))
            if not value or value not in numbers:
                kind = 'image'
        if kind == 'data_bars':
            bars = scene.get('bar_data') or []
            if len(bars) < 3 or any(str(b.get('value')) not in numbers for b in bars):
                kind = 'image'
        if kind in ('ai_video', 'hook_question', 'typewriter_text'):
            kind = 'image'
        # Split long static holds at phrase boundaries. All words remain in order.
        words = text.split()
        chunks = [words[i:i + 18] for i in range(0, len(words), 18)] if kind == 'image' else [words]
        for chunk in chunks:
            result.append({**scene, 'narration': ' '.join(chunk), 'visual_type': kind})
    if not result:
        raise ValueError('Cannot render an empty scene plan')
    return result
