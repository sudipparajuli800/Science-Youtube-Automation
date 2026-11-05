import os
import base64
import requests


def get_audio_duration(filepath: str) -> float:
    """
    Get the duration of an audio file in seconds.
    Uses ffprobe first, and falls back to MoviePy if ffprobe fails or is not found.
    """
    import subprocess
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                filepath,
            ],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            val = result.stdout.strip()
            if val:
                return float(val)
    except Exception as e:
        print(f"[HumeTTS] ffprobe duration check failed: {e}")

    # Fallback to MoviePy
    try:
        from moviepy.editor import AudioFileClip
        clip = AudioFileClip(filepath)
        duration = clip.duration
        clip.close()
        return float(duration)
    except Exception as e:
        print(f"[HumeTTS] MoviePy duration check failed: {e}")

    return 0.0


class HumeTTS:
    """
    Hume AI Octave TTS integration (free tier).
    - Rotates up to 6 API keys (HUME_API_KEY, HUME_API_KEY1..HUME_API_KEY5)
      automatically when a key hits its quota/rate limit.
    - Randomly picks from available voice IDs (HUME_VOICE_ID, HUME_VOICE_ID_1)
      each call for natural variety.
    """

    BASE_URL = "https://api.hume.ai/v0/tts"

    def __init__(self, voice_id: str = None):
        import random
        self._random = random

        # Collect all available API keys in priority order
        self.api_keys = []
        for env_name in [
            "HUME_API_KEY",
            "HUME_API_KEY2",
            "HUME_API_KEY3",
            "HUME_API_KEY4",
            "HUME_API_KEY5",
        ]:
            val = os.getenv(env_name, "").strip()
            if val:
                self.api_keys.append(val)

        # Collect all available voice IDs
        self.voice_ids = []
        if voice_id:
            self.voice_ids.append(voice_id)
        for env_name in ["HUME_VOICE_ID", "HUME_VOICE_ID_1", "HUME_VOICE_ID_2", "HUME_VOICE_ID_3", "HUME_VOICE_ID_4", "HUME_VOICE_ID_5"]:
            val = os.getenv(env_name, "").strip()
            if val and val not in self.voice_ids:
                self.voice_ids.append(val)

        if not self.api_keys:
            print("HumeTTS WARNING: No HUME_API_KEY* found in environment.")
        else:
            print(f"HumeTTS: {len(self.api_keys)} API key(s) and {len(self.voice_ids)} voice ID(s) available.")

    def generate_audio(self, text: str, output_path: str):
        """
        Generate TTS audio using Hume Octave API.
        Rotates through all available API keys on quota/rate-limit errors.
        Returns (output_path, word_offsets) on success, or (None, []) on failure.
        """
        if not self.api_keys:
            print("HumeTTS: Skipping — no API keys available.")
            return None, []

        # Pick a random voice ID for this call (variety + rotation)
        chosen_voice = self._random.choice(self.voice_ids) if self.voice_ids else None
        if chosen_voice:
            print(f"HumeTTS: Using voice ID: {chosen_voice[:8]}...")

        utterance = {"text": text}
        if chosen_voice:
            utterance["voice"] = {"id": chosen_voice}

        payload = {
            "utterances": [utterance],
            "format": {"type": "mp3"},
            "num_generations": 1,
        }
        # Request real word-level timestamps (Octave 2). Without these two fields the
        # API silently omits timing data entirely — the response still has a "snippets"
        # key, just with no `timestamps` inside it, which is why this previously always
        # fell through to the WPM-based *estimate* below. That estimate assumes a
        # constant speaking rate, which drifts audibly out of sync with the actual
        # narration (pauses, emphasis, variable pacing) — invisible with the old
        # whole-chunk caption highlighting, but very visible with real per-word karaoke
        # sync. A voice is required for version "2" to return timestamps; only request
        # it when we actually have one (falls back to the WPM estimate otherwise).
        if chosen_voice:
            payload["version"] = "2"
            payload["include_timestamp_types"] = ["word"]

        # Try each key in sequence
        for attempt, api_key in enumerate(self.api_keys, start=1):
            print(f"HumeTTS: Attempting key {attempt}/{len(self.api_keys)} ...")

            headers = {
                "X-Hume-Api-Key": api_key,
                "Content-Type": "application/json",
            }

            try:
                resp = requests.post(
                    self.BASE_URL, headers=headers, json=payload, timeout=90
                )

                # Quota / auth / credit-exhaustion errors — rotate to next key.
                # Hume returns 400 (not 402) for "Exhausted credit balance".
                is_credit_error = (
                    resp.status_code in (401, 402, 403, 429)
                    or (
                        resp.status_code == 400
                        and any(kw in resp.text.lower() for kw in ("credit", "zero_credits", "exhausted"))
                    )
                )
                if is_credit_error:
                    print(
                        f"HumeTTS: Key {attempt} quota/credit exhausted "
                        f"(HTTP {resp.status_code}). Trying next key..."
                    )
                    continue

                if resp.status_code != 200:
                    print(f"HumeTTS: Key {attempt} API error {resp.status_code}: {resp.text[:200]}")
                    continue

                data = resp.json()
                generations = data.get("generations", [])
                if not generations:
                    print(f"HumeTTS: Key {attempt} — empty generations list.")
                    continue

                gen = generations[0]
                audio_b64 = gen.get("audio", "")
                if not audio_b64:
                    print(f"HumeTTS: Key {attempt} — no audio field.")
                    continue

                audio_bytes = base64.b64decode(audio_b64)

                out_dir = os.path.dirname(output_path)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)

                with open(output_path, "wb") as f:
                    f.write(audio_bytes)

                print(
                    f"HumeTTS: ✓ Key {attempt} succeeded — "
                    f"{len(audio_bytes):,} bytes → {output_path}"
                )

                word_offsets = self._extract_word_offsets(gen, text, output_path)
                print(f"HumeTTS: Extracted {len(word_offsets)} word timestamps.")
                return output_path, word_offsets

            except requests.exceptions.Timeout:
                print(f"HumeTTS: Key {attempt} timed out (90 s). Trying next key...")
            except Exception as e:
                print(f"HumeTTS: Key {attempt} unexpected error — {e}. Trying next key...")

        print("HumeTTS: All API keys exhausted — falling back to next TTS engine.")
        return None, []

    def _extract_word_offsets(self, generation: dict, text: str = "", mp3_path: str = None) -> list:
        """
        Extract word-level timing from Hume generation response.
        Handles multiple known response formats gracefully.
        Falls back to WPM-based estimation if real timestamps are empty.
        """
        import logging
        logger = logging.getLogger("HumeTTS")

        offsets = []

        # Format 1 (current, Octave 2 with include_timestamp_types=["word"]):
        # generation["snippets"] is a list of lists (one inner list per utterance), each
        # containing snippet dicts with a "timestamps" list of
        # {"text": "word", "type": "word", "time": {"begin": ms, "end": ms}}.
        raw_snippets = generation.get("snippets", [])
        flat_snippets = []
        for group in raw_snippets:
            if isinstance(group, list):
                flat_snippets.extend(group)
            elif isinstance(group, dict):
                flat_snippets.append(group)

        for snippet in flat_snippets:
            if not isinstance(snippet, dict):
                continue
            for t in snippet.get("timestamps", []) or []:
                if not isinstance(t, dict):
                    continue
                if t.get("type") not in (None, "word"):
                    continue  # skip phoneme-level entries if both types were requested
                word = str(t.get("text", "")).strip()
                if not word:
                    continue
                time_obj = t.get("time", {})
                try:
                    begin_ms = float(time_obj.get("begin", 0.0))
                    end_ms = float(time_obj.get("end", begin_ms + 300))
                    offsets.append({
                        "word": word,
                        "start": begin_ms / 1000.0,
                        "duration": max(0.05, (end_ms - begin_ms) / 1000.0),
                    })
                except Exception:
                    pass

        # Format 2 (older/alternate shape seen in earlier API versions): flat
        # snippets[].timestamps as a dict or list with begin/end directly (no "time" wrapper,
        # values already in seconds).
        if not offsets:
            for snippet in flat_snippets:
                if not isinstance(snippet, dict):
                    continue
                ts = snippet.get("timestamps", {})
                word = snippet.get("text", "").strip()
                # `ts and` matters: snippet.get("timestamps", {}) defaults to an empty
                # dict when the key is simply absent (e.g. timestamps weren't requested/
                # returned), and without this check an empty-but-still-a-dict `ts` was
                # treated as valid single-word timing — using the WHOLE snippet's text
                # (often a full sentence) as "one word" with a fabricated 0.3s duration,
                # instead of correctly falling through to the per-word WPM estimate below.
                if isinstance(ts, dict) and ts and word:
                    try:
                        b_val = ts.get("begin", ts.get("start", 0.0))
                        begin = float(b_val[0]) if isinstance(b_val, list) else float(b_val)
                        e_val = ts.get("end", begin + 0.3)
                        end = float(e_val[-1]) if isinstance(e_val, list) else float(e_val)
                        offsets.append({"word": word, "start": begin, "duration": end - begin})
                    except Exception:
                        pass
                elif isinstance(ts, list):
                    for t in ts:
                        if not isinstance(t, dict):
                            continue
                        w = t.get("word", "").strip()
                        try:
                            b_val = t.get("begin", t.get("start", 0.0))
                            begin = float(b_val[0]) if isinstance(b_val, list) else float(b_val)
                            e_val = t.get("end", begin + 0.3)
                            end = float(e_val[-1]) if isinstance(e_val, list) else float(e_val)
                            if w:
                                offsets.append({"word": w, "start": begin, "duration": end - begin})
                        except Exception:
                            pass

        if not offsets:
            # Format 3: word_timestamps[] (alternative)
            for wt in generation.get("word_timestamps", []):
                word = wt.get("word", "").strip()
                begin = float(wt.get("begin", wt.get("start", 0.0)))
                end = float(wt.get("end", begin + 0.3))
                if word:
                    offsets.append({"word": word, "start": begin, "duration": end - begin})

        # Fallback timestamp estimation if real timestamps are empty/0
        if not offsets:
            logger.debug(f"Raw TTS response keys: {list(generation.keys())}")
            logger.debug(f"Raw TTS response (first 500 chars): {str(generation)[:500]}")
            print(f"HumeTTS WARNING: Real timestamps are 0! Raw response keys: {list(generation.keys())}")
            print(f"HumeTTS WARNING: Raw response (first 500 chars): {str(generation)[:500]}")
            
            # WPM Fallback
            words_text = text or generation.get("text", "")
            words = words_text.split()
            if words:
                wpm = 165.0
                print(f"HumeTTS WARNING: Generating fallback timestamps for {len(words)} words at {wpm} WPM...")
                estimated_total = (len(words) / wpm) * 60.0
                
                # Check actual audio duration for calibration
                scale = 1.0
                actual_duration = 0.0
                if mp3_path and os.path.exists(mp3_path):
                    actual_duration = get_audio_duration(mp3_path)
                    if actual_duration > 0 and estimated_total > 0:
                        scale = actual_duration / estimated_total
                        print(f"HumeTTS: Calibrating fallback timestamps. Estimated: {estimated_total:.2f}s, Actual: {actual_duration:.2f}s, Scale: {scale:.4f}")
                
                for i, w in enumerate(words):
                    start_time = ((i / wpm) * 60.0) * scale
                    duration = ((1.0 / wpm) * 60.0) * scale
                    offsets.append({"word": w, "start": start_time, "duration": duration})

        return offsets
