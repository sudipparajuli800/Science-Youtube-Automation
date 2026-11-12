"""Validated Remotion templates; model output is data, never executable code."""
import base64
from decimal import Decimal, InvalidOperation
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MOTION = ROOT / 'motion'
TEMPLATES = {'flow', 'transport', 'comparison', 'bars', 'orbit', 'refraction', 'photo'}
ICONS = {'particle', 'leaf', 'water', 'ocean', 'rock', 'sun', 'planet', 'cell', 'dna', 'atom', 'brain', 'magnet', 'telescope', 'microbe'}
STOP = {'the', 'a', 'an', 'of', 'and', 'in', 'to', 'from', 'with', 'on', 'for'}


def _words(text):
    return {w.rstrip('s') for w in re.findall(r'[a-z]+', text.lower()) if w not in STOP}


def _numbers(text):
    result = set()
    for n in re.findall(r'(?<!\w)[+-]?\d+(?:,\d{3})*(?:\.\d+)?(?!\w)', text):
        result.add(Decimal(n.replace(',', '')))
    return result


def validate_animation(raw, narration, topic=''):
    if not isinstance(raw, dict) or not isinstance(raw.get('template'), str) or raw['template'] not in TEMPLATES:
        return None
    kind = raw['template']
    title = str(raw.get('title') or topic).replace('*', '').strip()
    if not title or len(title) > 72 or '\n' in title:
        return None
    vocabulary = _words(narration + ' ' + topic)
    numbers = _numbers(narration)
    if not _numbers(title).issubset(numbers):
        return None
    spec = {'template': kind, 'title': title}
    if kind in ('refraction', 'orbit') and re.search(r"\b(?:not|never|doesn't|don't|cannot|can't)\s+(?:bend|refract|orbit|revolve)", narration.lower()):
        return None
    if kind == 'refraction':
        words = _words(narration)
        return spec if {'air', 'water'} <= words and words & {'light', 'refraction', 'ray'} else None
    items = raw.get('items') if kind == 'bars' else raw.get('nodes')
    minimum, maximum = (2, 5) if kind == 'bars' else (1, 3) if kind == 'photo' else (2, 4)
    if kind in ('comparison', 'orbit'):
        minimum = maximum = 2
    if not isinstance(items, list) or not minimum <= len(items) <= maximum:
        return None
    clean = []
    for item in items:
        if not isinstance(item, dict):
            return None
        label = str(item.get('label', '')).strip().replace('*', '')
        if not label or len(label) > 38 or not _words(label) or not _words(label) <= vocabulary or not _numbers(label) <= numbers:
            return None
        node = {'label': label}
        if kind == 'bars':
            value = item.get('value')
            try:
                number = Decimal(str(value))
                if isinstance(value, bool) or not number.is_finite() or number < 0 or number not in numbers or not math.isfinite(float(number)):
                    return None
                node['value'] = float(number)
            except (InvalidOperation, ValueError):
                return None
        else:
            icon = item.get('icon')
            node['icon'] = icon if isinstance(icon, str) and icon in ICONS else 'particle'
        clean.append(node)
    if kind == 'bars':
        if not any(i['value'] for i in clean):
            return None
        unit = str(raw.get('unit', '')).strip()
        if len(unit) > 22 or (unit and not _words(unit) <= _words(narration)) or (unit and not _words(unit) and unit not in narration):
            return None
        spec.update(items=clean, unit=unit)
    else:
        if kind == 'orbit' and not (_words(narration) & {'orbit', 'revolve'} and
                                   _words(narration) & {'sun', 'planet', 'earth', 'moon'}):
            return None
        spec['nodes'] = clean
    return spec


def infer_animation(narration, topic):
    """Small explicit fallbacks. Avoid pretending arbitrary text is a process."""
    text = narration.lower()
    if all(w in text for w in ('air', 'water', 'light')) and any(w in text for w in ('bend', 'refract')):
        return validate_animation({'template': 'refraction', 'title': 'Why light bends'}, narration, topic)
    # Only illustrate transport when the sentence actually describes movement.
    if ('sahara' in text or 'saharan' in text) and 'amazon' in text and any(
            w in text for w in ('wind', 'carr', 'cross', 'travel', 'transport', 'blow')):
        nodes = [{'label': 'Saharan dust' if 'saharan' in text else 'Sahara', 'icon': 'particle'}]
        if 'atlantic' in text:
            nodes.append({'label': 'Atlantic', 'icon': 'ocean'})
        nodes.append({'label': 'Amazon', 'icon': 'leaf'})
        return validate_animation({'template': 'transport', 'title': 'A journey across the ocean',
                                   'nodes': nodes}, narration, topic)
    return None


def engine_ready():
    return (os.getenv('ANIMATION_ENABLED', 'true').lower() not in ('false', '0', 'no')
            and bool(shutil.which('node')) and (MOTION / '.renderer-ready').exists()
            and (MOTION / 'node_modules/@remotion/renderer/package.json').exists())


def animation_cues(spec, offsets, scene_start, duration):
    labels = spec.get('items') if spec['template'] == 'bars' else spec.get('nodes', [])
    words = [o for o in (offsets or []) if scene_start <= o.get('start', -1) < scene_start + duration]
    tokens = [re.sub(r'[^a-z0-9]', '', str(o.get('word', '')).lower()).rstrip('s') for o in words]
    cues = []
    for index, node in enumerate(labels or []):
        label = [w.rstrip('s') for w in re.findall(r'[a-z0-9]+', node['label'].lower())]
        matches = [i for i in range(len(tokens)-len(label)+1) if tokens[i:i+len(label)] == label]
        time = words[matches[0]]['start'] - scene_start if matches else index * duration * .12
        cues.append(min(max(0, round(time*30)), max(0, math.ceil(duration*30)-1)))
    return cues


def render_animation(spec, duration, width, height, image_path=None, word_offsets=None, scene_start=0, overlay=False, centered=False):
    if not engine_ready():
        raise RuntimeError('Remotion is not ready. Run npm ci --prefix motion and node motion/ensure-browser.mjs.')
    if not 0 < duration <= 60:
        raise ValueError('Animation scenes must last 0-60 seconds; split longer narration.')
    props = {'spec': spec, 'frames': math.ceil(duration * 30), 'width': width, 'height': height,
             'cues': animation_cues(spec, word_offsets, scene_start, duration), 'overlay': overlay, 'centered': centered}
    if image_path:
        from PIL import Image
        with Image.open(image_path) as image:
            image = image.convert('RGB')
            image.thumbnail((1920, 1920))
            buffer = BytesIO()
            image.save(buffer, format='JPEG', quality=90)
            props['image'] = 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()
    digest = hashlib.sha256(json.dumps(props, sort_keys=True).encode())
    for name in ('src/index.jsx', 'src/Scene.jsx', 'render.mjs', 'package-lock.json'):
        digest.update((MOTION / name).read_bytes())
    key = digest.hexdigest()
    cache = ROOT / 'automation/storage/motion_cache'
    cache.mkdir(parents=True, exist_ok=True)
    output = cache / (key + '.mp4')
    if not output.exists():
        input_path = cache / (key + '.json')
        input_path.write_text(json.dumps(props), encoding='utf-8')
        subprocess.run([shutil.which('node'), str(MOTION / 'render.mjs'), str(input_path), str(output)],
                       cwd=ROOT, check=True, timeout=900)
    return str(output)
