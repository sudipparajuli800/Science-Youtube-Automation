"""Plain text at publishing boundaries, independent of model formatting."""
import re


def plain_public_text(value):
    text = '' if value is None else str(value)
    # Preserve the meaning of mathematical operators while removing emphasis stars.
    text = re.sub(r'(\d)\s*\*\*\s*(\d)', r'\1^\2', text)
    text = re.sub(r'(\d)\s*\*\s*(\d)', r'\1 × \2', text)
    text = text.replace('\\*', '').replace('*', '')
    text = re.sub(r'[ \t]+', ' ', text)
    return '\n'.join(line.rstrip() for line in text.splitlines()).strip()


def overlay_headline(value, topic, caption):
    """Prefer a concise grounded headline; safely fall back to the actual topic."""
    candidate = plain_public_text(value).strip('"\' ')
    candidate = re.sub(r'#\w+|https?://\S+', '', candidate).strip()
    numbers = set(re.findall(r'\d+(?:\.\d+)?', caption))
    if (not 2 <= len(candidate.split()) <= 8 or len(candidate) > 70 or '\n' in candidate
            or not set(re.findall(r'\d+(?:\.\d+)?', candidate)) <= numbers):
        candidate = plain_public_text(topic)
        candidate = ' '.join(candidate.split()[:8])[:70].strip()
    if any(len(word) > 32 for word in candidate.split()):
        candidate = ''
    return candidate or 'A closer look at science'
