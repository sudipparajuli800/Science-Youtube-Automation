# Science video quality upgrade

The default direction is a measured, footage-led science explainer. Show the thing
being explained; keep text for captions, labels and useful data. Avoid decorative
space imagery, artificial instrument overlays, flashing transitions and constant whooshes.

## Changes

- Plain-language narration prompts explain a question through a mechanism and example.
  Provider failure raises an error instead of publishing generic cosmic filler.
- Both formats share a director prompt and deterministic scene checks. The complete
  script must appear in order. Missing narration is repaired, including long-form
  endings previously lost to character limits and the Shorts five-scene cap.
- Static holds split at 18 words. Unsupported chart/stat values become footage shots.
  This checks script consistency; it is not independent scientific fact checking.
- Video shots use official Pexels/Pixabay APIs rather than scraped web images.
  Vision checks run strictly: unavailable verification is a rejection, not approval.
  Exact duplicate asset files are skipped. Missing verified visuals stop the job.
- Pexels downloads save source URL, creator and license sidecars.
- Smaller, sentence-case Barlow captions use a muted cyan highlight and quiet backdrop.
  Source images receive a light grade and slow motion without stars, flare or HUDs.
- Narration boundaries determine hard cuts. Shorts no longer insert flashes that
  shift visuals relative to the audio. Overlong narration is rejected, not truncated.
- Neutral voice pitch, quieter music, and optional local Kokoro narration.

## Run and review

Keep existing project dependencies and FFmpeg. Add `GEMINI_API_KEY` for writing and
visual verification, and `PEXELS_API_KEY` or `PIXABAY_API_KEY` for footage.
Use the existing manual GitHub workflow with `is_test=true` for the first render.
These code changes do not change schedules or publish anything by themselves.

Local voice is optional:

```powershell
pip install -r requirements-quality.txt
$env:TTS_PROVIDER = 'kokoro'
$env:KOKORO_VOICE = 'af_heart'
```

Kokoro requires its model download and language dependencies; follow the upstream
installation instructions for your OS. Whisper downloads an alignment model too.
This backend deliberately fails if setup/alignment fails rather than silently changing
voices. Existing Edge/Hume behavior remains the default. Whisper transcription is
not forced alignment; review scientific terms and caption spelling.

Review every claim against a primary scientific source, pronunciation, crop, source
license, caption placement, and music balance before a production run. The code does
not establish factual correctness simply because an LLM generated a fluent script.
Strict verification can stop scheduled jobs when credentials or quota are unavailable.

## Free media choices checked 3 November 2026

- [Pexels API](https://www.pexels.com/api/documentation/) is free;
  [its license](https://www.pexels.com/license/) permits commercial photos/videos
  subject to restrictions. API keys and request limits still apply.
- [Kokoro model card](https://huggingface.co/hexgrad/Kokoro-82M): Apache-2.0 model
  weights, self-hosted inference without monthly service credits. Local compute,
  installation and model downloads are required.
- [YouTube Audio Library](https://support.google.com/youtube/answer/3376882): free
  music/SFX; download selected tracks manually and preserve any required attribution.
  Put cleared music in `automation/music/science/`. Existing bundled tracks have
  not been licensed or audited by this change. Do not assume they are cleared.
- [Freesound](https://freesound.org/help/faq/): use CC0 or compatible attribution
  licenses, retain credits; do not automatically use noncommercial files.
- [ElevenLabs billing](https://elevenlabs.io/docs/overview/administration/billing):
  commercial rights are associated with paid plans; do not treat a free account as
  a commercial voice license.

## Verification

`python -m unittest automation.tests.test_editorial -v` (six passing tests),
`python -m compileall -q automation`, and `git diff --check`.
No end-to-end API render or Kokoro model inference was run: credentials and optional
model packages were not available in the editing environment.

## Vision-provider recovery

Visual checks now rotate all configured Gemini keys and fall back to the existing
Groq keys using a vision-capable model. `GROQ_VISION_MODEL` overrides the default
`qwen/qwen3.8-27b`, as listed in https://console.groq.com/docs/vision . Access and
rate limits depend on the provider account. Failed keys are skipped for the rest of
the process so each candidate does not repeat a billing/quota failure.
An explicit NO remains a rejection; only unavailable/malformed responses fall back.
When all providers are unavailable, `VerificationUnavailable` identifies the quota
or configuration problem without misreporting that every downloaded asset is wrong.
The existing workflow already exposes Groq keys; no new secret is required.
PNG and other source formats are converted into small JPEGs before vision requests.
Fallback scene search uses the topic instead of fragments of spoken narration.

Validation: 11 offline tests cover provider fallback, key rotation, circuit breaking,
explicit rejection, image conversion, and editorial checks. No live provider request
was made, and no publishing workflow was triggered.
