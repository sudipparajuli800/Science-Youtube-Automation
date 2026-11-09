"""CPU narration with word cues from Kokoro's synthesis tokens."""
import os
import re
import tempfile


def generate_audio(text, output_path):
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    from moviepy.editor import AudioFileClip
    from spacy.util import is_package

    if not is_package('en_core_web_sm'):
        raise RuntimeError('Install the English pronunciation model: python -m spacy download en_core_web_sm')

    sample_rate = 24000
    voice = os.getenv('KOKORO_VOICE', 'am_michael')
    speed = float(os.getenv('KOKORO_SPEED', '0.96'))
    pipeline = KPipeline(lang_code='b' if voice.startswith('b') else 'a', device='cpu')
    parts, offsets = [], []
    samples = 0
    for result in pipeline(text, voice=voice, speed=speed):
        if result.audio is None:
            continue
        tokens = result.tokens or []
        group = []
        for index, token in enumerate(tokens):
            group.append(token)
            if not token.whitespace and index < len(tokens) - 1:
                continue
            timed = [item for item in group
                     if item.start_ts is not None and item.end_ts is not None]
            word = ''.join(item.text for item in group).strip()
            if timed and re.search(r'\w', word):
                start = timed[0].start_ts
                end = timed[-1].end_ts
                offsets.append({'word': word, 'start': samples / sample_rate + start,
                                'duration': end - start})
            group = []
        parts.append(result.audio)
        samples += len(result.audio)

    if not parts or not offsets:
        raise RuntimeError('Kokoro produced no audio or word cues')
    with tempfile.TemporaryDirectory() as temp_dir:
        wav = os.path.join(temp_dir, 'narration.wav')
        sf.write(wav, np.concatenate(parts), sample_rate)
        with AudioFileClip(wav) as clip:
            clip.write_audiofile(output_path, codec='libmp3lame', logger=None)
    return output_path, offsets
