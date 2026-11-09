import asyncio
import edge_tts
import os
import re
from typing import List, Dict

class TTSEngine:
    def __init__(self, voice_map=None, rate="+20%", pitch="+0Hz", volume="+0%", allow_elevenlabs=False, provider="auto"):
        self.voice_map = voice_map or {
            "female": "ne-NP-HemkalaNeural",
            "male": "ne-NP-SagarNeural"
        }
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.allow_elevenlabs = allow_elevenlabs
        self.provider = provider

    async def generate_multivocal_audio(self, segments: List[Dict], output_path: str):
        """
        Generates audio for multiple segments with alternating voices and merges offsets.
        Returns: (output_path, word_offsets, segment_durations)
        """
        all_offsets = []
        segment_durations = []
        cumulative_duration = 0
        temp_audio_files = []
        
        for i, seg in enumerate(segments):
            temp_path = f"automation/storage/temp_seg_{i}.mp3"
            voice = self.voice_map.get(seg.get("gender"), self.voice_map.get("female"))
            
            text_to_speak = seg.get("text", "")
            
            _, offsets = await self.generate_audio(text_to_speak, temp_path, voice)
            
            for off in offsets:
                off["start"] += cumulative_duration
                all_offsets.append(off)
            
            from moviepy.editor import AudioFileClip
            clip = AudioFileClip(temp_path)
            dur = clip.duration
            segment_durations.append(dur)
            cumulative_duration += dur
            temp_audio_files.append(temp_path)
            clip.close()

        from moviepy.editor import concatenate_audioclips, AudioFileClip
        clips = [AudioFileClip(f) for f in temp_audio_files]
        final_audio = concatenate_audioclips(clips)
        final_audio.write_audiofile(output_path, fps=44100, logger=None)
        
        for c in clips: c.close()
        for f in temp_audio_files: 
            try: os.remove(f)
            except: pass

        return output_path, all_offsets, segment_durations

    async def generate_audio(self, text: str, output_path: str, voice: str = None, rate: str = None, pitch: str = None, volume: str = None):
        text = text.strip()
        
        if not text:
            return output_path, []

        # Detection: If text contains Devanagari, apply Nepali normalization
        if re.search(r'[\u0900-\u097F]', text):
            text = re.sub(r'(\d+)\.(\d+)', r'\1 point \2', text)
            abbreviations = {
                r'डा\.': 'डाक्टर',
                r'इ\.': 'इन्जिनियर',
                r'ई\.': 'इन्जिनियर',
                r'प्रा\.': 'प्राध्यापक',
                r'प\.': 'पण्डित',
                r'वि\.सं\.': 'विक्रम सम्बत',
                r'नं\.': 'नम्बर',
                r'कि\.मी\.': 'किलोमिटर',
                r'मि\.': 'मिटर'
            }
            for abbr, full in abbreviations.items():
                text = re.sub(abbr, full, text)
            text = re.sub(r'([।.,!?])(?=[^\s])', r'\1 ', text)
        provider = (os.getenv("TTS_PROVIDER") or self.provider).lower()
        if provider in ("kokoro", "kokoro-edge"):
            from .kokoro_tts import generate_audio
            try:
                return await asyncio.to_thread(generate_audio, text, output_path)
            except Exception as exc:
                if provider == "kokoro":
                    raise
                print(f"Kokoro narration failed ({type(exc).__name__}); trying Edge.")

        word_offsets = []
        hume_generated = False
        eleven_audio_generated = False

        # ── STAGE 1: HUME AI (Primary — expressive, human-sounding) ──────────────
        # Only used for English content (science channel).
        is_english = not bool(re.search(r'[\u0900-\u097F]', text))
        _hume_available = any(
            os.getenv(k) for k in
            ["HUME_API_KEY","HUME_API_KEY2","HUME_API_KEY3","HUME_API_KEY4","HUME_API_KEY5"]
        )
        if provider == "auto" and is_english and _hume_available:
            try:
                from automation.media.hume_tts import HumeTTS
                hume_voice_id = self.voice_map.get("hume_voice_id")
                hume = HumeTTS(voice_id=hume_voice_id)
                result_path, hume_offsets = hume.generate_audio(text, output_path)
                if result_path and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    hume_generated = True
                    word_offsets = hume_offsets
                    print("DEBUG: Hume TTS generation successful.")
                else:
                    print("DEBUG: Hume TTS returned no audio. Falling back.")
            except Exception as e:
                print(f"DEBUG: Hume TTS failed: {e}. Falling back.")

        # ── STAGE 2: ELEVENLABS (Secondary fallback) ──────────────────────────────
        api_key = os.getenv("ELEVENLABS_API_KEY") or os.getenv("ELEVENLAB_API_KEY")
        use_elevenlabs = provider == "auto" and self.allow_elevenlabs and bool(api_key) and not hume_generated

        if self.allow_elevenlabs and not api_key and not hume_generated:
            print(f"DEBUG: ElevenLabs allowed but API KEY missing.")

        if use_elevenlabs:
            try:
                from automation.media.elevenlabs_tts import ElevenLabsTTS
                el_voice_id = self.voice_map.get("elevenlabs_voice_id")
                el_tts = ElevenLabsTTS(voice_id=el_voice_id)
                print(f"DEBUG: Attempting ElevenLabs generation for text: {text[:30]}...")
                result_path = el_tts.generate_audio(text, output_path)
                if result_path and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    eleven_audio_generated = True
                    print("DEBUG: ElevenLabs generation successful.")
                else:
                    print(f"DEBUG: ElevenLabs returned empty/no file. Falling back to Edge TTS.")
            except ImportError as e:
                print(f"DEBUG: ElevenLabs not installed: {e}")
            except Exception as e:
                print(f"DEBUG: ElevenLabs failed: {e}. Falling back to Edge TTS.")

        if hume_generated or eleven_audio_generated:
            # Hume/ElevenLabs succeeded — offsets already captured (or estimated below)
            pass
        else:
            # --- FALLBACK: EDGE TTS ---
            voice = voice or self.voice_map.get("female")
            # Strip emotional tags for Edge TTS as it doesn't support them
            edge_text = re.sub(r'\[.*?\]', '', text).strip()
            print(f"DEBUG: TTSEngine communicating with voice: {voice} (Rate: {rate or self.rate}, Pitch: {pitch or self.pitch})")
            MAX_RETRIES = 3
            retry_count = 0
            edge_generated = False
            
            while retry_count < MAX_RETRIES:
                try:
                    communicate = edge_tts.Communicate(edge_text, voice, rate=rate or self.rate, pitch=pitch or self.pitch, volume=volume or self.volume, boundary="WordBoundary")
                    audio_data = bytearray()
                    temp_offsets = []
                    
                    async for chunk in communicate.stream():
                        ctype = chunk.get("type") or chunk.get("Type") or "unknown"
                        if ctype == "audio":
                            audio_data.extend(chunk["data"])
                        elif ctype == "WordBoundary":
                            temp_offsets.append({
                                "word": chunk.get("text") or chunk.get("Text"),
                                "start": (chunk.get("offset", chunk.get("Offset", 0))) / 10**7,
                                "duration": (chunk.get("duration", chunk.get("Duration", 0))) / 10**7
                            })

                    if audio_data and len(audio_data) > 0:
                        with open(output_path, "wb") as f:
                            f.write(audio_data)
                        word_offsets = temp_offsets
                        edge_generated = True
                        break
                    else:
                        print(f"DEBUG: Attempt {retry_count + 1} - No audio data received for: {text[:50]}...")
                except Exception as e:
                    print(f"Error during TTS streaming (Attempt {retry_count + 1}): {e}")
                
                retry_count += 1
                if retry_count < MAX_RETRIES:
                    await asyncio.sleep(2) # Wait before retry
        
            if not edge_generated:
                return None, []

        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            print(f"CRITICAL: Failed to generate audio file at {output_path} after attempts.")
            return None, []
        
        # Word Offset Fallback (for ElevenLabs or failed EdgeTTS offsets)
        if not word_offsets and len(text.strip()) > 0:
            print("DEBUG: Calculating estimated word offsets...")
            from moviepy.editor import AudioFileClip
            try:
                temp_audio = AudioFileClip(output_path)
                total_dur = temp_audio.duration
                temp_audio.close()
            except:
                total_dur = len(text.split()) * 0.4
            
            words = text.split()
            # Calculate phonetic weights for better distribution
            weights = [self._estimate_phonetic_length(w) for w in words]
            total_weight = sum(weights) or 1.0
            
            start_time = 0
            for i, w in enumerate(words):
                # Add extra weight for punctuation pauses
                punc_pause = 0
                if w.endswith(('.', '?', '!')): punc_pause = 0.5
                elif w.endswith(','): punc_pause = 0.2
                
                w_dur = (weights[i] / total_weight) * (total_dur - (text.count('.') + text.count('?') + text.count('!'))*0.5)
                # Ensure w_dur is at least 0.2s
                w_dur = max(w_dur, 0.2)
                
                word_offsets.append({"word": w, "start": start_time, "duration": w_dur})
                start_time += w_dur + punc_pause
            
            # Normalize back to total_dur if we overshot or undershot due to punc
            actual_end = word_offsets[-1]['start'] + word_offsets[-1]['duration']
            if actual_end > 0:
                scale = total_dur / actual_end
                for off in word_offsets:
                    off['start'] *= scale
                    off['duration'] *= scale

        return output_path, word_offsets

    def _estimate_phonetic_length(self, word: str) -> float:
        """
        Estimates the 'spoken length' of a word for better timing fallback.
        Handles digits and common symbols that take longer to speak.
        """
        # Remove common punctuation for length estimation
        clean_word = re.sub(r'[।.,!?"]', '', word)
        if not clean_word: return 0.1
        
        # Devanagari detection
        is_nepali = any(ord(c) > 127 for c in clean_word)
        
        # Expansion dictionary for digits
        if not is_nepali:
            expansion = {
                '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
                '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine',
                '-': ' dash ', '.': ' point '
            }
        else:
            # Basic Nepali digit expansion
            expansion = {
                '०': 'शुन्य', '१': 'एक', '२': 'दुई', '३': 'तीन', '४': 'चार',
                '५': 'पाँच', '६': 'छ', '७': 'सात', '८': 'आठ', '९': 'नौ',
                '-': ' ड्यास ', '.': ' दशमलव '
            }

        phonetic_repr = ""
        for char in clean_word:
            if char in expansion:
                phonetic_repr += expansion[char] + " "
            else:
                phonetic_repr += char
        
        # Simple heuristic: chars + extra weight for long expansions
        # English: average syllable is ~3 chars
        # Nepali: usually 1 char = 1 syllable (mora)
        return len(phonetic_repr.strip())
