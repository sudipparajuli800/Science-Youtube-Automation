"""Vision-based shot verification. Strict mode rejects unavailable checks.
The video orchestrator uses strict mode; legacy callers retain permissive behavior.
"""
import os
import re

_MODEL_CANDIDATES = list(dict.fromkeys([os.getenv('GEMINI_MODEL', 'gemini-flash-latest'), 'gemini-3.8-flash']))


class VerificationUnavailable(RuntimeError):
    """All vision providers are unavailable; this is not a visual rejection."""


# Per-process circuit breaker: stop hammering a failed key for every candidate.
_UNAVAILABLE_KEYS = set()


def _keys(prefix):
    return list(dict.fromkeys(os.getenv(prefix + suffix, '').strip()
                for suffix in ('', '2', '3') if os.getenv(prefix + suffix, '').strip()))


def _verdict(answer):
    answer = (answer or '').strip().upper().rstrip('.')
    return {'YES': True, 'NO': False}.get(answer)


def _check_gemini(img_bytes, prompt):
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None
    for key in _keys('GEMINI_API_KEY'):
        if ('gemini', key) in _UNAVAILABLE_KEYS:
            continue
        try:
            client = genai.Client(api_key=key)
            for model in _MODEL_CANDIDATES:
                try:
                    response = client.models.generate_content(model=model, contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'), prompt])
                    verdict = _verdict(response.text)
                    if verdict is not None:
                        return verdict
                except Exception as error:
                    if '404' in str(error):
                        continue
                    # Quota, billing and transport errors: try another key/provider.
                    break
        except Exception:
            pass
        _UNAVAILABLE_KEYS.add(('gemini', key))
        print('[VisualRelevance] Gemini key unavailable; trying next vision provider/key.')
    return None


def _check_groq(img_bytes, prompt):
    import base64
    import requests
    for key in _keys('GROQ_API_KEY'):
        if ('groq', key) in _UNAVAILABLE_KEYS:
            continue
        try:
            response = requests.post('https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': 'Bearer ' + key}, timeout=30,
                json={'model': os.getenv('GROQ_VISION_MODEL', 'qwen/qwen3.8-27b'),
                      'max_completion_tokens': 256,
                      'messages': [{'role': 'user', 'content': [
                          {'type': 'text', 'text': prompt},
                          {'type': 'image_url', 'image_url': {'url':
                              'data:image/jpeg;base64,' + base64.b64encode(img_bytes).decode()}}]}]})
            response.raise_for_status()
            verdict = _verdict(response.json()['choices'][0]['message']['content'])
            if verdict is not None:
                return verdict
        except Exception as error:
            # Status/type identify billing, model and request errors without leaking keys.
            status = getattr(getattr(error, 'response', None), 'status_code', None)
            print(f'[VisualRelevance] Groq vision failure: {type(error).__name__}, HTTP {status or "n/a"}.')
        _UNAVAILABLE_KEYS.add(('groq', key))
        print('[VisualRelevance] Groq vision key unavailable; trying next key.')
    return None


def _extract_frame_if_video(path: str) -> str:
    """Returns a still-image path to check: `path` itself for images, or a temp JPEG
    frame extracted from a video. Returns None if extraction fails."""
    if not path.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
        return path
    try:
        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(path)
        frame_path = path + "_relevance_frame.jpg"
        clip.save_frame(frame_path, t=min(0.5, max(0.0, clip.duration / 2)))
        clip.close()
        return frame_path
    except Exception as e:
        print(f"[VisualRelevance] Frame extraction failed for {path}: {e}")
        return None


def is_visually_relevant(asset_path: str, description: str, strict: bool = False) -> bool:
    """
    Returns True if the image (or video's mid-frame) plausibly depicts `description`.
    Strict mode rejects missing assets and raises when all vision providers fail.
    `strict=True` asks the model to be more skeptical — used when we already have a
    generous pool of candidates, so it's safe to be pickier about which one wins.
    """
    if not description or not description.strip():
        return not strict
    if not asset_path or not os.path.exists(asset_path):
        return not strict

    still_path = _extract_frame_if_video(asset_path)
    if not still_path or not os.path.exists(still_path):
        return not strict

    try:
        from io import BytesIO
        from PIL import Image
        with Image.open(still_path) as image:
            image = image.convert('RGB')
            image.thumbnail((1024, 1024))
            buffer = BytesIO()
            image.save(buffer, format='JPEG', quality=85)
            img_bytes = buffer.getvalue()
    except Exception:
        return not strict
    finally:
        if still_path != asset_path and os.path.exists(still_path):
            try:
                os.remove(still_path)
            except OSError:
                pass

    clean_desc = re.sub(r'\*', '', description).strip()[:300]
    strictness = (
        "Be reasonably strict — reject generic stock footage that doesn't specifically "
        "relate to the subject, not just anything vaguely in the same category."
        if strict else
        "Be lenient — accept anything plausibly related, only reject images that are "
        "clearly about something else entirely."
    )
    prompt = (
        f"A video narrator is saying: \"{clean_desc}\"\n"
        f"Does this image plausibly illustrate or relate to that? {strictness}\n"
        "Answer with exactly one word: YES or NO."
    )

    for check in (_check_gemini, _check_groq):
        verdict = check(img_bytes, prompt)
        if verdict is not None:
            return verdict
    from .local_relevance import check_local
    verdict = check_local(img_bytes, clean_desc)
    if verdict is not None:
        return verdict
    if strict:
        raise VerificationUnavailable(
            "Visual verification unavailable on all Gemini and Groq keys. "
            "Check provider quota/billing or GROQ_VISION_MODEL access, then retry. "
            "No candidate was rejected for content and no unverified asset was accepted.")
    return True
