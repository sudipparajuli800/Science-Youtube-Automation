from google import genai
from google.genai import errors, types
import os
import time
import random
import json
import re
from typing import List, Dict
from .editorial import DIRECTOR_BRIEF, prepare_scenes
from .public_text import plain_public_text

# Sentinel returned by _call_with_retry when every Gemini key AND every Groq fallback
# has failed. Callers that use this directly as content (not through one of the
# methods below that already check for it) MUST check for this before using the
# result — a past incident let this literal string get published as a video's topic/
# narration when Gemini's model was deprecated and Groq's fallback model was retired
# in the same window, so every LLM call failed and nothing caught it before upload.
LLM_FAILURE_SENTINEL = "Error: Maximum retries reached for all LLM keys and fallbacks."


def is_llm_failure(text: str) -> bool:
    """True if `text` is (or starts with) the _call_with_retry failure sentinel."""
    return bool(text) and text.strip().startswith("Error: Maximum retries reached")


def _sentence_to_image_cue(sentence: str, topic: str, max_words: int = 8) -> str:
    """
    Builds a search-friendly image cue from one script sentence, for the bare-fallback
    scene builder used only when the LLM completely fails to return a structured scene
    list. Previously every fallback scene reused the exact same
    f"{topic} space background" query regardless of the sentence's actual content — so
    a fallback-generated video fetched the same handful of loosely-related (and
    space-biased regardless of topic) photos for every single scene, no matter what
    the narration was actually about.
    """
    clean = re.sub(r'\*', '', sentence)
    clean = re.sub(r'[^a-zA-Z0-9 ]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    words = [w for w in clean.split() if len(w) > 2][:max_words]
    if words:
        return " ".join(words)
    # Sentence was too short/empty — fall back to a cleaned topic (strip a "What if"/
    # "Did you know" wrapper and the trailing "?" so it reads as a plain search phrase
    # instead of a literal question).
    cleaned_topic = re.sub(r'^(what if|did you know)\s+', '', topic.strip(), flags=re.IGNORECASE)
    cleaned_topic = cleaned_topic.rstrip('?').strip()
    return cleaned_topic or "science"


class ScriptWriter:
    def __init__(self, api_key: str = None):
        # Gather all Gemini keys from env
        self.api_keys = [
            os.getenv("GEMINI_API_KEY"),
            os.getenv("GEMINI_API_KEY2"),
            os.getenv("GEMINI_API_KEY3")
        ]
        # Filter out empty/None keys
        self.api_keys = [k for k in self.api_keys if k]
        
        # If no key found in env, but one was passed to init, use it
        if not self.api_keys and api_key:
            self.api_keys = [api_key]
            
        def patch_gemini_client(client):
            original_generate_content = client.models.generate_content
            def patched_generate_content(*args, **kwargs):
                safety_settings = kwargs.pop('safety_settings', None)
                config = kwargs.get('config', None)
                if safety_settings:
                    if config is None:
                        config = types.GenerateContentConfig(safety_settings=safety_settings)
                    elif isinstance(config, types.GenerateContentConfig):
                        config.safety_settings = safety_settings
                    elif isinstance(config, dict):
                        config['safety_settings'] = safety_settings
                    kwargs['config'] = config
                return original_generate_content(*args, **kwargs)
            client.models.generate_content = patched_generate_content
            return client

        self.clients = [patch_gemini_client(genai.Client(api_key=k)) for k in self.api_keys]
        self.client = self.clients[0] if self.clients else None
        # Ordered by preference. "gemini-flash-latest" is Google's stable alias that
        # always points at their current-generation Flash model — using it (instead of a
        # pinned dated ID like the old "gemini-2.0-flash") is what actually prevents this
        # from breaking again next time Google retires a specific version. The pinned IDs
        # after it are just a safety net in case the alias itself is ever unavailable.
        self.model_candidates = list(dict.fromkeys([os.getenv('GEMINI_MODEL', 'gemini-flash-latest'), 'gemini-3.8-flash']))
        self.model_id = self.model_candidates[0]
        self.groq_api_keys = [
            os.getenv("GROQ_API_KEY"),
            os.getenv("GROQ_API_KEY2"),
            os.getenv("GROQ_API_KEY3")
        ]
        self.groq_api_keys = [k for k in self.groq_api_keys if k]
        self.groq_clients = []
        if self.groq_api_keys:
            try:
                from groq import Groq
                for k in self.groq_api_keys:
                    gc = Groq(api_key=k)
                    class MockModerations:
                        def create(self, *args, **kwargs):
                            pass
                    gc.moderations = MockModerations()
                    self.groq_clients.append(gc)
            except ImportError:
                pass
        self.groq_client = self.groq_clients[0] if self.groq_clients else None
        # Same idea as model_candidates above: Groq retired llama-3.3-70b-versatile in
        # June 2026, which — combined with the Gemini model deprecation — meant BOTH the
        # primary provider and its fallback failed simultaneously and broke production.
        # openai/gpt-oss-120b is Groq's own recommended replacement.
        self.groq_model_candidates = ['openai/gpt-oss-120b', 'qwen/qwen3.6-27b', 'llama-3.3-70b-versatile']
        self.groq_model_id = self.groq_model_candidates[0]

    @staticmethod
    def _is_model_not_found(err_msg_lower: str) -> bool:
        """Detects 'this model id doesn't exist / was retired' errors specifically, as
        opposed to transient errors — so we can skip straight to the next candidate model
        instead of burning the whole retry budget re-trying a model that will never work."""
        return (
            "404" in err_msg_lower
            and ("model" in err_msg_lower or "not_found" in err_msg_lower)
        ) or "no longer available" in err_msg_lower or "decommissioned" in err_msg_lower

    def _call_with_retry(self, prompt: str, max_retries: int = 5) -> str:
        """Calls Gemini rotating through keys, falling back to Groq only if all fail or hit quota."""
        if not self.clients:
            print("WARNING: No Gemini clients available. Trying Groq immediately...")

        # Try each Gemini client sequentially
        for client_idx, client in enumerate(self.clients):
            model_idx = self.model_candidates.index(self.model_id) if self.model_id in self.model_candidates else 0
            attempt = 0
            while attempt < max_retries:
                model_id = self.model_candidates[model_idx]
                try:
                    response = client.models.generate_content(
                        model=model_id,
                        contents=prompt,
                        safety_settings=[
                            types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
                            types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
                            types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
                            types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
                        ]
                    )
                    self.model_id = model_id  # remember what worked, start there next call
                    return response.text.strip()
                except Exception as e:
                    err_msg = str(e).lower()
                    is_quota_error = "quota" in err_msg or "429" in err_msg or "exhausted" in err_msg

                    if self._is_model_not_found(err_msg) and model_idx < len(self.model_candidates) - 1:
                        model_idx += 1
                        print(f"Gemini model '{model_id}' unavailable, trying '{self.model_candidates[model_idx]}'...")
                        continue  # doesn't consume retry budget — this model will never succeed

                    if self._is_model_not_found(err_msg):
                        print(f"Gemini model '{model_id}' unavailable; skipping this key.")
                        break

                    if is_quota_error:
                        print(f"Gemini Key {client_idx+1} Quota Exceeded/429. Trying next key...")
                        break  # Break out of attempts loop for this key, move to next key

                    # For non-quota errors, retry with exponential backoff on the current key
                    attempt += 1
                    if attempt < max_retries:
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        print(f"LLM Error on Key {client_idx+1}: {e}. Retrying in {wait_time:.2f} seconds... (Attempt {attempt}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        print(f"LLM Key {client_idx+1} failed after {max_retries} attempts. Trying next key...")
                        break

        # If all Gemini keys fail or are exhausted, try Groq fallback
        if self.groq_clients:
            print("All Gemini keys exhausted. Trying Groq fallback...")
            for client_idx, groq_client in enumerate(self.groq_clients):
                model_idx = (self.groq_model_candidates.index(self.groq_model_id)
                             if self.groq_model_id in self.groq_model_candidates else 0)
                attempt = 0
                while attempt < max_retries:
                    model_id = self.groq_model_candidates[model_idx]
                    try:
                        groq_client.moderations.create(input=prompt)
                        chat_completion = groq_client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model=model_id,
                            max_tokens=4096,
                            user="science-automation",
                        )
                        msg = chat_completion.choices[0].message
                        refusal = getattr(msg, 'refusal', None)
                        if refusal:
                            print(f"Groq Key {client_idx+1} refused: {refusal}")
                            break
                        result = (msg.content or "").strip()
                        if result:
                            self.groq_model_id = model_id
                            return result
                    except Exception as groq_err:
                        err_msg = str(groq_err).lower()
                        is_quota_error = "quota" in err_msg or "429" in err_msg or "exhausted" in err_msg

                        if self._is_model_not_found(err_msg) and model_idx < len(self.groq_model_candidates) - 1:
                            model_idx += 1
                            print(f"Groq model '{model_id}' unavailable, trying '{self.groq_model_candidates[model_idx]}'...")
                            continue

                        if self._is_model_not_found(err_msg):
                            print(f"Groq model '{model_id}' unavailable; skipping this key.")
                            break

                        if is_quota_error:
                            print(f"Groq Key {client_idx+1} Quota Exceeded/429. Trying next key...")
                            break

                        attempt += 1
                        print(f"Groq fallback Key {client_idx+1} attempt {attempt} failed: {groq_err}")
                        if attempt < max_retries:
                            time.sleep((2 ** attempt) + 1)

        return LLM_FAILURE_SENTINEL

    def _dummy_placeholder(self):
        pass

    def generate_science_facts(self, topic: str) -> str:
        prompt = f"""Write an original science narration about "{topic}".
Explain one concrete question through a causal mechanism, a concrete example,
and a clear answer at the end. Length: 80-105 words, approximately 35-45 seconds.
Use plain spoken English, varied sentence lengths, and a curious, measured voice.
Distinguish observations, hypotheses, analogies, and unresolved questions.
No fabricated names, dates, quotes, discoveries, or numerical comparisons.
No suspense filler, cosmic platitudes, imitation of creators, or engagement requests.
Open with a specific observation that the explanation will resolve.
Return only speech text, without markup, directions, headings, or image cues.
"""
        script = self._call_with_retry(prompt)
        if is_llm_failure(script) or not script.strip():
            raise RuntimeError("Script generation failed; refusing to narrate generic filler.")
        return self.clean_script(script)
    def expand_science_script(self, topic: str) -> str:
        """
        Generates a master-class 900-word documentary script with expanded styles.
        """
        hooks = [
            ("paradox", "Open with an unexplained observation or paradox. Make the viewer feel that something is wrong with how they understand reality."),
            ("mystery", "Open with a genuine scientific mystery — something we only recently realized we don't understand."),
            ("scale", "Open by describing the mind-blowing scale or numbers involved (extreme sizes, temperatures, or speeds)."),
            ("counterintuitive", "Open with a counterintuitive fact that goes against common sense."),
            ("history", "Open by narrating the specific moment of discovery. Use names, dates, and sensory details of the lab or field site."),
            ("question", "Start with a direct, challenging question to the viewer that reframes a common object or idea.")
        ]
        tones = [
            ("awe", "Awe and wonder (Style: Kurzgesagt) — Treat science as magic that actually works."),
            ("conversational", "Conversational and curious (Style: Veritasium) — Build the logic from the ground up."),
            ("journalistic", "Journalistic deep-dive — Serious, factual, and investigative."),
            ("dramatic", "Dramatic narration — Build tension and release like a cinematic thriller.")
        ]
        
        hook_name, hook_instr = random.choice(hooks)
        tone_name, tone_instr = random.choice(tones)

        prompt = f"""Write an original science narration about "{topic}".
Explain one concrete question through a causal mechanism, a concrete example,
and a clear answer at the end. Length: 750-900 words, approximately 5-6 minutes.
Use plain spoken English, varied sentence lengths, and a curious, measured voice.
Distinguish observations, hypotheses, analogies, and unresolved questions.
No fabricated names, dates, quotes, discoveries, or numerical comparisons.
No suspense filler, cosmic platitudes, imitation of creators, or engagement requests.
Open with a specific observation that the explanation will resolve.
Return only speech text, without markup, directions, headings, or image cues.
"""
        script = self._call_with_retry(prompt)
        if is_llm_failure(script) or not script.strip():
            raise RuntimeError("Script generation failed; refusing to narrate generic filler.")
        return self.clean_script(script)

    def clean_script(self, text: str) -> str:
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        text = re.sub(r'^(Anchor|Narrator|Voiceover|Anchorperson|Speaker):\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
        text = re.sub(r'#\w+', '', text)
        return plain_public_text(text)

    def clean_json_response(self, text: str) -> str:
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match: return match.group(1).strip()
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match: return match.group(1).strip()
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end != -1: return text[start:end+1].strip()
        return text.strip()

    def generate_image_keywords(self, text: str, extra_context: str = "Science", is_long_form: bool = False) -> List[str]:
        """
        Generates a list of specific visual search terms for the script.
        Uses the LLM to analyze the entire text and produce timed visual cues.
        """
        count = 35 if is_long_form else 12
        prompt = f"""
        Analyze this science script and generate {count} SPECIFIC, VIVID, and CONCRETE visual search terms for Pexels/Storyblocks/NASA.
        
        Script: "{text[:3000]}..." 
        Context: {extra_context}

        Requirements:
        1. Terms must be ready-to-search queries (e.g. "Hubble telescope nebula deep space", "close up macro leaf cells", "MRI scan of human brain", "chimpanzee troop rainforest").
        2. Prefer real photography over illustrations: no cartoons, memes, movie stills, screenshots, or text-heavy graphics. Real people or animals are welcome WHEN the script's topic is actually about them (anatomy, animal behavior, a named scientist, a historical discovery) — do not force every query toward abstract space/nebula imagery if the topic is biology, chemistry, or another non-space field.
        3. For each segment of the script (Intro, Body sections, Conclusion), provide diverse queries.
        4. Prioritize cinematic, 4k, macro, or documentary styles relevant to the actual subject matter.
        5. Return ONLY the search terms, one per line. No numbers or bullet points.
        """
        
        try:
            response = self._call_with_retry(prompt)
            keywords = []
            for line in response.split('\n'):
                line = line.strip()
                if not line or line.lower().startswith(("here", "sure", "ok", "based")): continue
                # Strip leading numbers like "1. ", "1) ", " - ", " * "
                line = re.sub(r'^(\d+[\.\)]\s*|[-\*\u2022]\s*)', '', line)
                line = line.replace('"', '').strip()
                if line: keywords.append(line)
            
            # Fallback if LLM fails
            if not keywords:
                keywords = [f"{extra_context} cinematic 4k"] * 10
                
            return keywords[:count + 5] 
        except Exception as e:
            print(f"Keyword Gen Error: {e}")
            return [f"{extra_context} science background"] * 10

    def generate_visual_scenes(self, topic: str, script: str) -> List[Dict]:
        self.last_thumbnail_data = {
            "hook_phrase": topic[:40], "supporting_fact": "",
            "thumbnail_bg_query": topic, "thumbnail_subject_query": topic,
        }
        prompt = f"""Plan footage for a science video about {topic}.
Return JSON only: an object with scenes and thumbnail_data.
Each scene needs narration (verbatim), visual_type (animation, image, ai_video, kinetic_stat, data_bars),
image_cue (concrete subject and action), ai_video_prompt (subject/action/camera for illustrations),
named_entity (optional short label),
stat_data (null or value/unit/label), bar_data (null or label/value objects).
Use animation for causal processes, transport, comparisons, orbits and diagrams.
Each animation scene needs animation: {{"template":"flow","title":"Short title",
"nodes":[{{"label":"A subject from narration","icon":"water"}},{{"label":"Another subject","icon":"leaf"}}]}}.
For bars use items [{{"label":"subject","value":2}}] and a unit, all stated in narration.
For refraction only template/title are needed. Photo needs nodes plus image_cue.
Most mechanisms should be explained visually; mix in real images when useful.
No arbitrary statistics, decorative full-screen narration, or fabricated simulations.
thumbnail_data needs hook_phrase (up to 4 accurate words), supporting_fact,
thumbnail_bg_query and thumbnail_subject_query. Match the actual topic.
Script: {script}
"""
        for attempt in range(2):
            raw = self._call_with_retry(DIRECTOR_BRIEF + prompt)
            try:
                data = json.loads(self.clean_json_response(raw))
                if isinstance(data, dict) and isinstance(data.get("scenes"), list):
                    thumbnail = data.get("thumbnail_data")
                    if isinstance(thumbnail, dict):
                        self.last_thumbnail_data.update(thumbnail)
                    return prepare_scenes(data["scenes"], script, topic)
            except (ValueError, TypeError):
                pass
        # Preserve complete narration even if the director returns malformed JSON.
        return prepare_scenes([], script, topic)

    def generate_shorts_visual_scenes(self, topic: str, script: str) -> List[Dict]:
        return self.generate_visual_scenes(topic, script)

    def generate_thumbnail_info(self, topic: str, script: str) -> Dict[str, str]:
        """Generates catchy thumbnail metadata, leveraging cached last_thumbnail_data from generate_visual_scenes."""
        if hasattr(self, 'last_thumbnail_data') and self.last_thumbnail_data:
            thumb = self.last_thumbnail_data
            # Enforce hook phrase formatting: max 4 words, ALL CAPS
            hook = str(thumb.get("hook_phrase", "")).strip().upper()
            words = hook.split()
            if len(words) > 4:
                hook = " ".join(words[:4])
            
            return {
                "text": hook or topic[:25].upper(),
                "image_prompt": thumb.get("thumbnail_bg_query", f"cinematic 4k photo of {topic}, scientific documentary style"),
                "hook_phrase": hook or topic[:25].upper(),
                "supporting_fact": thumb.get("supporting_fact", "A scientific revelation."),
                "thumbnail_bg_query": thumb.get("thumbnail_bg_query", f"cinematic 4k photo of {topic}, scientific documentary style"),
                "thumbnail_subject_query": thumb.get("thumbnail_subject_query", "")
            }
        
        # Generic fallback
        return {
            "text": topic[:25].upper(),
            "image_prompt": f"cinematic 4k photo of {topic}, scientific documentary style",
            "hook_phrase": topic[:25].upper(),
            "supporting_fact": "A scientific revelation.",
            "thumbnail_bg_query": f"cinematic 4k photo of {topic}, scientific documentary style",
            "thumbnail_subject_query": ""
        }

    def generate_social_post(self, post_type: str, headlines: List[Dict] = None,
                              recent_history: List[str] = None) -> Dict[str, str]:
        """
        Generates a Facebook/Instagram text+photo post. `post_type` is one of
        "discovery", "breaking_news", "myth_bust", "fun_fact". `headlines` (from
        news_fetcher.fetch_recent_headlines) grounds breaking_news/myth_bust in real,
        recent coverage instead of pure invention. Returns:
          {"topic": str, "caption": str, "image_query": str}
        """
        headlines = headlines or []
        recent_history = recent_history or []

        headlines_block = ""
        if headlines:
            lines = [f"- {h['title']}" + (f" ({h['source']})" if h.get('source') else "")
                     for h in headlines[:6]]
            headlines_block = (
                "Here are real, recent science-related headlines you can draw from "
                "(optional — skip them if none genuinely fit):\n" + "\n".join(lines)
            )

        type_instructions = {
            "discovery": (
                "Write about a genuinely fascinating, true, and SPECIFIC scientific discovery or "
                "phenomenon (a landmark historical discovery, or something from real research). Make it "
                "read like a surprising story, not a textbook fact."
            ),
            "breaking_news": (
                "Write about real, current science news.\n" + headlines_block + "\n"
                "Pick the single most interesting item and explain what actually happened and why it "
                "matters, in plain language — don't just restate the headline."
            ),
            "myth_bust": (
                "Pick ONE specific, widely-believed science myth or piece of misinformation and debunk "
                "it clearly.\n" + headlines_block + "\n"
                "Structure: state the myth people believe, then the actual fact, then briefly explain why "
                "the myth took hold or what the real explanation is. Genuinely educational, never "
                "condescending toward people who believed it."
            ),
            "fun_fact": (
                "Share one punchy, mind-blowing, TRUE science fact — the kind that makes someone stop "
                "scrolling and say 'wait, really?!'"
            ),
        }
        instruction = type_instructions.get(post_type, type_instructions["discovery"])

        avoid_block = ""
        if recent_history:
            avoid_block = "Avoid repeating these recent post topics:\n" + "\n".join(
                f"- {h}" for h in recent_history[-15:]
            )

        prompt = f"""
        You are writing a Facebook/Instagram post for a science education page called
        "Daily Deep Space" (@dailydeepspace).

        {instruction}

        {avoid_block}

        Requirements:
        - Caption length: 60-120 words. The first line is a punchy hook (it's the only part
          shown before "See more", so it must work standalone).
        - Tone: curious, awe-driven, accessible. Never dry, never textbook-like.
        - Use 1-3 well-placed emoji, not more.
        - End with a short, genuine question inviting comments — not generic "comment below!!" spam.
        - Add a final line with 6-10 relevant hashtags (mix broad: #Science #Space with
          specific-to-this-topic tags). Always include #DailyDeepSpace.
        - Be scientifically accurate. Never exaggerate or make unverifiable claims.
        - Use plain text, without Markdown or asterisks around words.
        - Provide overlay_headline: 3-7 words for the image. Make a specific, honest
          curiosity hook that the caption answers. No hashtags, emoji, exaggerated
          claims, fabricated numbers, or generic shock phrases.

        Also provide a short (4-8 word) plain-English image search phrase describing what photo
        would best illustrate this specific post (e.g. "Hubble telescope deep field galaxies",
        "human brain neurons illustration", "great white shark underwater").

        Return ONLY valid JSON:
        {{
          "topic": "3-6 word summary of what this post is about (internal tracking only)",
          "caption": "the full caption text, ready to post, including the hashtag line",
          "overlay_headline": "a short accurate curiosity hook for the image",
          "image_query": "the image search phrase"
        }}
        """

        raw = self._call_with_retry(prompt)
        if is_llm_failure(raw):
            print("[ScriptWriter] Social post generation failed on all providers.")
            return {
                "topic": post_type,
                "caption": "",
                "image_query": "",
            }

        try:
            cleaned = self.clean_json_response(raw)
            data = json.loads(cleaned)
            if isinstance(data, dict) and str(data.get("caption", "")).strip():
                return {
                    "topic": str(data.get("topic", post_type)).strip() or post_type,
                    "caption": plain_public_text(data.get("caption", "")),
                    "overlay_headline": plain_public_text(data.get("overlay_headline", "")),
                    "image_query": str(data.get("image_query", "")).strip() or "science abstract background",
                }
        except Exception as e:
            print(f"[ScriptWriter] Social post JSON parse error: {e}")

        # Plain prose can still be useful; malformed JSON must never be a caption.
        fallback_caption = plain_public_text(raw)[:600]
        if self.clean_json_response(raw).lstrip().startswith(('{', '[')):
            fallback_caption = ''
        return {
            "topic": post_type,
            "caption": fallback_caption,
            "image_query": "science abstract background",
        }
