"""Use explicitly reviewed, pre-generated cloud-notebook clips without API fees."""
import json
import os
from pathlib import Path
import re


def find_bank_clip(scene, topic, excluded=()):
    manifest = Path(os.getenv('VISUAL_BANK_MANIFEST', 'automation/storage/visual_bank/manifest.json'))
    if not manifest.exists():
        return None
    root = manifest.resolve().parent
    query = set(re.findall(r'[a-z]{3,}', (scene.get('image_cue') or topic).lower()))
    matches = []
    for clip in json.loads(manifest.read_text(encoding='utf-8')).get('clips', []):
        if clip.get('approved') is not True:
            continue
        tags = set(re.findall(r'[a-z]{3,}', ' '.join(clip.get('tags', [])).lower()))
        overlap = len(tags & query)
        if overlap < 2 or overlap / max(1, len(query)) < .5:
            continue
        path = (root / clip['file']).resolve()
        if str(path) in excluded or not path.is_relative_to(root) or not path.is_file():
            continue
        matches.append((overlap, path, clip))
    if not matches:
        return None
    _, path, clip = max(matches, key=lambda item: item[0])
    return {'asset_path': str(path), 'source': {'provider': 'reviewed visual bank',
            'generated': True, 'model': clip.get('model', 'cloud notebook'),
            'label': 'AI-generated illustration'}}


def download_bank(url, destination='automation/storage/visual_bank'):
    """Import a user-supplied public ZIP, bounding size and preventing path traversal."""
    import io
    import zipfile
    from urllib.parse import urlsplit
    import requests
    if not url:
        return
    if urlsplit(url).scheme != 'https':
        raise ValueError('VISUAL_BANK_URL requires HTTPS')
    content = bytearray()
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content) > 250 * 1024 * 1024:
                raise ValueError('Visual bank exceeds 250 MB')
    root = Path(destination).resolve()
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if sum(f.file_size for f in archive.infolist()) > 500 * 1024 * 1024:
            raise ValueError('Visual bank expands beyond 500 MB')
        for entry in archive.infolist():
            target = (root / entry.filename).resolve()
            if not target.is_relative_to(root):
                raise ValueError('Unsafe visual bank path')
            if not entry.is_dir() and target.suffix.lower() not in ('.json', '.mp4'):
                raise ValueError('Visual bank must contain only JSON and MP4 files')
        archive.extractall(root)
    print('[VisualBank] Imported reviewed-clip bank.')


if __name__ == '__main__':
    download_bank(os.getenv('VISUAL_BANK_URL', ''))
