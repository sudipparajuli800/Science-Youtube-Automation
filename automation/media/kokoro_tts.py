"""Optional local narration: no hosted API quota; align captions to actual audio."""
import os
import tempfile


def generate_audio(text, output_path):
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    from faster_whisper import WhisperModel
    from moviepy.editor import AudioFileClip

    pipeline = KPipeline(lang_code='a')
    parts = [audio for _, _, audio in pipeline(
        text.replace('*', ''), voice=os.getenv('KOKORO_VOICE', 'af_heart'),
        speed=float(os.getenv('KOKORO_SPEED', '1.0')))]
    if not parts:
        raise RuntimeError('Kokoro produced no audio')
    with tempfile.TemporaryDirectory() as temp_dir:
        wav = os.path.join(temp_dir, 'narration.wav')
        sf.write(wav, np.concatenate(parts), 24000)
        aligner = WhisperModel(os.getenv('WHISPER_MODEL', 'base.en'),
                               device='cpu', compute_type='int8')
        segments, _ = aligner.transcribe(wav, language='en', word_timestamps=True,
                                         initial_prompt=text.replace('*', ''))
        offsets = [{'word': w.word.strip(), 'start': w.start,
                    'duration': w.end - w.start}
                   for segment in segments for w in (segment.words or [])]
        if not offsets:
            raise RuntimeError('No caption alignment returned')
        with AudioFileClip(wav) as clip:
            clip.write_audiofile(output_path, codec='libmp3lame', logger=None)
    return output_path, offsets
