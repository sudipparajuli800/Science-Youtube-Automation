# Add moving science visuals

## Activate hosted video generation

1. Create a provider account and inspect its current balance, trial terms and model price:
   [Kie](https://kie.ai/market/text-to-video) or [fal](https://fal.ai/).
2. In this repository's **Settings -> Secrets and variables -> Actions -> Secrets**,
   add **KIE_API_KEY** for Kie, or **FAL_KEY** for fal. Keep the key out of chat and git.
3. Start a **new** manual workflow, choose `science`, and set `is_test=true`.
   Review the video before enabling publishing.

No extra Python SDK is needed. With a configured key, `auto` selects Kie first,
otherwise fal. Repository variables can override:

| Variable | Default | Meaning |
| --- | --- | --- |
| VIDEO_GEN_PROVIDER | auto | auto, kie, fal, or none |
| VIDEO_GEN_MAX_CLIPS | 1 | New task submissions per video job, including failures |
| VIDEO_GEN_DAILY_LIMIT | 2 | New task submissions per UTC day, persisted in state |

Increase these only after checking the actual provider cost. Limits count requests,
not dollars, and cannot distinguish free credits from a paid credit balance. There
is no auto-top-up code. For a strictly free trial, keep your provider's billing and
auto-recharge disabled. A free API key is not a promise of free inference forever.

Supported adapters use [Kie Wan 2.6](https://docs.kie.ai/market/wan/2-6-text-to-video)
(five seconds, 720p) and
[fal Wan 2.2](https://fal.ai/models/fal-ai/wan/v2.2-a14b/text-to-video/api)
(81 frames, 16 fps, 720p, native portrait/landscape).
Kie's adapter does not send an undocumented aspect-ratio field; the renderer cover-crops
its result, so keep the main subject centered. Model routes are intentionally pinned
to their adapter schemas rather than accepting arbitrary incompatible model names.

## Visual behavior and recovery

The director can request up to two specific illustrative shots, specifying subject,
action and camera. Genuine stock footage remains preferred for evidence, named
people and historical events. If stock verification runs out of quota, hosted
generation and reviewed-bank clips are tried before explanation cards.

Generated clips carry a visible **AI-generated illustration** label and source metadata.
Their original soundtrack is removed. Prompts constrain the shot to the script;
this is not an independent check of scientific correctness, so review the result.
Science videos with no moving footage are held before automatic publishing. Test
runs can still render previews. One moving shot is a minimum safeguard, not a claim
that a mostly-card video meets the desired editorial standard.

Task IDs are saved to `automation/storage/video_generation_jobs.json` before/after
submission. Polling timeouts preserve pending tasks for resumption. Ambiguous POST
failures are never automatically repurchased. Check the provider dashboard before
manually clearing a failed/submitting entry. Generation can finish after the local
polling timeout and may still consume provider credits. Expired result URLs may
require manual recovery; the client will not buy the same shot again automatically.

Downloaded clips use GitHub Actions cache; available results are reused by prompt,
model and aspect ratio. Cache retention is not guaranteed. Workflow artifacts include
scene manifests and the task ledger for inspection. This code does not purchase
credits, create accounts, or configure account API keys on your behalf.

## Free cloud GPU option

Open [the Colab notebook](https://colab.research.google.com/github/sudipparajuli800/Science-Youtube-Automation/blob/main/notebooks/generate_visual_bank.ipynb).
It uses published **Wan 2.1 1.3B** weights, a smaller starting point for limited GPU
memory than larger Wan 2.2/Mochi checkpoints. Select a GPU runtime, generate a small
batch, inspect every clip, mark only reviewed entries `approved: true`, then export
the ZIP. The notebook has not been executed on a GPU by this change.

Upload the ZIP as a public GitHub Release asset and set repository variable
**VISUAL_BANK_URL** to its download URL. The workflow imports the bank and matches
reviewed tags against each scene's visual query. Tags must describe the actual shot;
weak matches and unapproved clips are ignored. Reusable bank clips do not consume
hosted-generation credits. A manually supplied local bank can instead be selected
with `VISUAL_BANK_MANIFEST`.

[Colab's FAQ](https://research.google.com/colaboratory/faq.html) says free resources
and GPU availability are limited and variable. Use the notebook interactively;
it is not an unattended GitHub Actions inference server. No account rotation,
keep-alive tricks or attempts to bypass GPU limits are included. If memory runs
out, reduce frame count or try a later GPU session; a larger model is not a fix.

## Provider findings checked 4 November 2026

- [Kie](https://kie.ai/market/text-to-video) advertises new-user testing credits;
  ongoing generation uses credits and depends on the selected model and settings.
- [fal pricing](https://fal.ai/docs/documentation/model-apis/pricing) describes
  prepaid usage billing. This integration does not assume recurring free credits.
- [JSON2Video](https://json2video.com/get-api-key/) lists a 600-second free rendering
  allowance with a 60-second movie limit. That allowance assembles/renders videos;
  it does not establish a free Wan/Mochi footage allowance, so it is not used as
  a generative-footage backend here.
- Self-hosting open model weights avoids a hosted-model subscription; it still
  requires suitable compute and published weights for that exact model. A Wan 2.6
  API listing is not itself a self-hosting checkpoint.

Validation covers provider payloads, successful retrieval, cached reuse, quota and
failure limits, pending-task resumption, API credential origin checks, reviewed-bank
matching, and existing editorial/vision fallbacks. Live generation needs your account
key and credits; no hosted model was called during implementation.

## CPU stock matching and early holds

The workflow now installs CPU PyTorch and Transformers for a local CLIP fallback
when both remote vision providers are unavailable. Its model is downloaded once
and cached; it requires no GPU or inference API key. Matching is a conservative
similarity heuristic, not a scientific verifier. A genuine remote NO is never
overridden. Model download or dependency failure does not approve an asset.

If the scene plan still has zero video clips, production stops before narration,
rendering or thumbnail generation. The Actions summary says "Video held: no moving
footage" and the `visual_quality_report.json` artifact lists counts and whether
Kie/fal credentials were configured, without exposing their values. This is a held
production run, not a successful publication. Test mode still permits previews.
The published-video safeguard remains in place.
