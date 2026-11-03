"""Script-derived typography fallback. Never presented as photographic evidence."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def _fit(draw, text, font_path, width, height, initial):
    for size in range(initial, 21, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines, line = [], ''
        for word in text.split():
            candidate = (line + ' ' + word).strip()
            if draw.textlength(candidate, font=font) > width and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        if len(lines) * int(size * 1.4) <= height and all(
                draw.textlength(line, font=font) <= width for line in lines):
            return font, lines, int(size * 1.4)
    raise ValueError('Explanation card text exceeds safe layout')


def create_explainer_card(scene, topic, path, portrait=False):
    size = (1080, 1920) if portrait else (1920, 1080)
    w, h = size
    image = Image.new('RGB', size, '#101c28')
    draw = ImageDraw.Draw(image)
    fonts = Path(__file__).resolve().parents[1] / 'fonts'
    regular = fonts / 'Barlow-Regular.ttf'
    bold = fonts / 'Barlow-Bold.ttf'
    margin = int(w * .09)
    label = ImageFont.truetype(str(regular), 30)
    draw.text((margin, int(h * .10)), 'EXPLAINER / CONCEPT SUMMARY', font=label, fill='#8edae0')
    title, lines, spacing = _fit(draw, topic.replace('*', ''), bold, w - 2*margin,
                                int(h * .18), 64)
    for i, line in enumerate(lines):
        draw.text((margin, int(h*.19) + i*spacing), line, font=title, fill='#93aab7')
    draw.line((margin, int(h*.42), w-margin, int(h*.42)), fill='#8edae0', width=3)
    text = scene.get('narration', '').replace('*', '').strip()
    font, lines, spacing = _fit(draw, text, regular, w - 2*margin, int(h*.34), 78)
    for i, line in enumerate(lines):
        draw.text((margin, int(h*.48) + i*spacing), line, font=font, fill='#f4f6f5')
    draw.text((margin, int(h*.88)), 'Script summary / no source footage', font=label, fill='#93aab7')
    image.save(path)
    return str(path)
