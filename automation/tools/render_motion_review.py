"""Offline review of real renderer output; no APIs, narration generation or publishing.

python -m automation.tools.render_motion_review --output /path/to/review
"""
import argparse
import base64
import json
from io import BytesIO
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw
from automation.media.motion_graphics import ROOT, validate_animation


EXAMPLES = {
    'cycle': ('Water evaporates, vapor condenses into clouds, and rain returns water in a repeating cycle.',
              {'title': 'Water returns', 'treatment': 'draw', 'nodes': [
                  {'label': 'Water', 'icon': 'water'}, {'label': 'clouds', 'icon': 'cloud'},
                  {'label': 'rain', 'icon': 'rain'}]}),
    'layers': ('The Earth has layers: crust, mantle and core.',
               {'title': 'Beneath the surface', 'treatment': 'draw', 'nodes': [
                   {'label': 'crust', 'icon': 'rock'}, {'label': 'mantle', 'icon': 'rock'},
                   {'label': 'core', 'icon': 'planet'}]}),
    'transport': ('Saharan dust travels across the Atlantic and reaches the Amazon.',
                  {'title': 'A journey across the ocean', 'treatment': 'assemble', 'nodes': [
                      {'label': 'Saharan dust', 'icon': 'particle'},
                      {'label': 'Atlantic', 'icon': 'ocean'}, {'label': 'Amazon', 'icon': 'leaf'}]}),
    'comparison': ('Mercury and Earth follow different orbits.',
                   {'title': 'Two worlds', 'treatment': 'focus', 'nodes': [
                       {'label': 'Mercury', 'icon': 'planet'}, {'label': 'Earth', 'icon': 'planet'}]}),
    'photo': ('Water covers much of the Earth.',
              {'title': 'Our water world', 'treatment': 'assemble', 'nodes': [
                  {'label': 'Water', 'icon': 'water'}, {'label': 'Earth', 'icon': 'planet'}]}),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--templates', default='cycle,layers,transport,comparison')
    parser.add_argument('--formats', default='long,short')
    parser.add_argument('--image', type=Path, help='Local licensed Earth image for the photo example')
    args = parser.parse_args()
    names, formats = args.templates.split(','), args.formats.split(',')
    if any(n not in EXAMPLES for n in names) or any(f not in ('long', 'short') for f in formats):
        parser.error('Unknown template or format')
    if 'photo' in names and (not args.image or not args.image.is_file()):
        parser.error('photo requires --image pointing to a local licensed Earth image')
    node = shutil.which('node')
    if not node:
        parser.error('Node is required; prepare the renderer as documented in README.md')
    args.output.mkdir(parents=True, exist_ok=True)
    review = []
    for name in names:
        narration, raw = EXAMPLES[name]
        spec = validate_animation({'template': name, **raw}, narration, 'Science preview')
        if not spec:
            raise ValueError(f'Preview fixture failed editorial validation: {name}')
        for format_name in formats:
            width, height = (1920, 1080) if format_name == 'long' else (1080, 1920)
            props = {'spec': spec, 'frames': 90, 'width': width, 'height': height,
                     'cues': [i * 22 for i in range(len(spec['nodes']))],
                     'centered': format_name == 'long'}
            if name == 'photo':
                with Image.open(args.image) as source:
                    source = source.convert('RGB')
                    source.thumbnail((1920, 1920))
                    encoded = BytesIO()
                    source.save(encoded, format='JPEG', quality=92)
                props['image'] = 'data:image/jpeg;base64,' + base64.b64encode(encoded.getvalue()).decode()
            stem = args.output / f'{name}-{format_name}'
            props_path = stem.with_suffix('.json')
            props_path.write_text(json.dumps(props), encoding='utf-8')
            video = stem.with_suffix('.mp4')
            subprocess.run([node, str(ROOT / 'motion/render.mjs'), str(props_path.resolve()),
                            str(video.resolve()), '--review'], cwd=ROOT, check=True, timeout=900)
            metadata = json.loads(Path(str(video) + '.review.json').read_text())
            thumb_w, thumb_h = ((480, 270) if format_name == 'long' else (270, 480))
            sheet = Image.new('RGB', (thumb_w * 3, thumb_h + 42), '#101c28')
            draw = ImageDraw.Draw(sheet)
            for index, item in enumerate(metadata['stills']):
                with Image.open(item['path']) as frame:
                    sheet.paste(frame.resize((thumb_w, thumb_h)), (index * thumb_w, 42))
                draw.text((index * thumb_w + 12, 14),
                          f'{name} / {format_name} / frame {item["frame"]} / MOTION PREVIEW', fill='white')
            contact = stem.with_suffix('.contact.jpg')
            sheet.save(contact, quality=93)
            review.append({'template': name, 'format': format_name, 'video': str(video.resolve()),
                           'contact_sheet': str(contact.resolve()), 'narration_reference': narration})
    (args.output / 'review.json').write_text(json.dumps(review, indent=2), encoding='utf-8')
    print(f'Review files: {args.output.resolve()}')


if __name__ == '__main__':
    main()
