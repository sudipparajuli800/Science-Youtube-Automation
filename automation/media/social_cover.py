"""Readable feed cover with a short headline and the complete source image."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import numpy as np
from ..content.public_text import plain_public_text


def _font(size, bold=False):
    path = Path(__file__).resolve().parents[1] / 'fonts' / ('Barlow-Bold.ttf' if bold else 'Barlow-Regular.ttf')
    return ImageFont.truetype(str(path), size)


def _layout(text, width):
    dummy = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    for size in range(94, 49, -2):
        font = _font(size, True)
        lines, line = [], ''
        for word in text.split():
            trial = (line + ' ' + word).strip()
            if line and dummy.textlength(trial, font=font) > width:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        if len(lines) <= 3 and all(dummy.textlength(x, font=font) <= width for x in lines):
            return font, lines, int(size * 1.13)
    raise ValueError('Social headline is too long for the cover')


def create_social_cover(image_path, headline, output_path=None):
    headline = plain_public_text(headline)
    if not headline:
        raise ValueError('Social cover requires a headline')
    with Image.open(image_path) as original:
        source = ImageOps.exif_transpose(original).convert('RGB')
    width, height = 1080, 1350
    backdrop = ImageOps.fit(source, (width, height), method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(35))
    # Keep the whole scientific subject rather than cropping away important features.
    photo = ImageOps.contain(source, (width, 1020), method=Image.Resampling.LANCZOS)
    x = np.arange(photo.width)
    y = np.arange(photo.height)
    horizontal = np.clip(np.minimum(x, photo.width-1-x) / 22, 0, 1)
    vertical = np.minimum(np.clip(y / 12, 0, 1), np.clip((photo.height-1-y) / 150, 0, 1))
    mask = Image.fromarray((255 * vertical[:, None] * horizontal[None, :]).astype(np.uint8), 'L')
    backdrop.paste(photo, ((width-photo.width)//2, (1020-photo.height)//2), mask)
    gradient = np.zeros((height, width, 4), dtype=np.uint8)
    gradient[:, :, :3] = (7, 18, 28)
    gradient[:, :, 3] = np.interp(np.arange(height), [0, 500, 850, 1100, height], [25, 0, 165, 240, 255]).astype(np.uint8)[:, None]
    image = Image.alpha_composite(backdrop.convert('RGBA'), Image.fromarray(gradient, 'RGBA'))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((64, 54, 354, 104), radius=10, fill=(7, 18, 28, 195))
    draw.text((82, 64), 'DAILY DEEP SPACE', font=_font(27, True), fill='#edf3f0')
    font, lines, spacing = _layout(headline, width-140)
    y = height - 230 - len(lines)*spacing
    draw.rectangle((70, y-27, 142, y-20), fill='#8edae0')
    for line in lines:
        draw.text((70, y), line, font=font, fill='#f5f7f4', stroke_width=1, stroke_fill='#101c28')
        y += spacing
    draw.text((70, height-145), 'Read the full explanation below', font=_font(30), fill='#8edae0')
    draw.text((70, height-82), '@dailydeepspace', font=_font(27), fill='#b6c8ce')
    destination = Path(output_path) if output_path else Path(image_path).with_name(Path(image_path).stem + '_cover.jpg')
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.convert('RGB').save(destination, 'JPEG', quality=94)
    return str(destination)
