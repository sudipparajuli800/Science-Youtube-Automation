# Explanatory animation with Remotion

The science editor can now render structured diagrams, shapes, charts, labels and
verified photographs using React/SVG and Remotion. Rendering runs on the CPU and
does not use a video-generation API key. Existing stock and hosted video remain
available when they suit a scene.

## Supported templates

| Template | Purpose | Required data |
| --- | --- | --- |
| flow | Reveal an explained process with connected stages | 2–4 labeled nodes |
| transport | Show particles moving between source and destination | 2–4 labeled nodes |
| comparison | Contrast two subjects without invented measurements | Exactly two nodes |
| bars | Reveal comparable numerical values | 2–5 labeled values and a shared unit |
| orbit | Show a conceptual orbit around a named body | Center and orbiting body |
| refraction | Illustrate a ray bending from air into water | Title; matching narration |
| photo | Animate a verified photo with short subject labels | 1–3 labels and image cue |

Nodes have `label` and `icon`. Icons are `particle`, `leaf`, `water`, `ocean`,
`rock`, `sun`, `planet`, `cell`, `dna`, `atom`, `brain`, `microbe`,
`magnet` or `telescope`. The scene writer selects a template and provides
data; it cannot supply JavaScript, HTML, arbitrary file paths or executable hooks.

For example, this can illustrate a scene narrating that Saharan dust travels across
the Atlantic to the Amazon:

```json
{
  "visual_type": "animation",
  "narration": "Saharan dust travels across the Atlantic and reaches the Amazon.",
  "animation": {
    "template": "transport",
    "title": "Dust delivers nutrients",
    "nodes": [
      {"label": "Saharan dust", "icon": "particle"},
      {"label": "Atlantic", "icon": "ocean"},
      {"label": "Amazon", "icon": "leaf"}
    ]
  }
}
```

## Contextual media layers

Set `media_context: true` on an animation scene and provide `image_cue`.
The orchestrator checks one video and, if needed, one photo against the narration.
Verified media appears in a clear subject window over a blurred background, with
the diagram in a separate readable panel. The same layout supports still photos
and looping footage. If no verified context is available, the diagram stands alone.
Context media provenance is stored as `context_source` in the manifest.

Ordinary subject shots mix photos and moving footage. Their processing uses
restrained motion and short labels. The editor removes decorative HUDs, scan lines
and flare effects from these documentary shots.

## Timing and editorial checks

Each animation is rendered after narration timing is known, at 30 fps and the exact
scene duration. Node/chart reveals use matching word timestamps; unmatched labels
use staged timings within the scene. Captions remain in their lower safe area.
Portrait and landscape layouts use the same scene data. Finished animation frames
are also available to thumbnail generation.

Labels must refer to words in the narration/topic. Charts reject absent values,
unsupported units, negative/nonfinite values and empty data. The old renderer no
longer fabricates example chart values when data is missing. These checks enforce
script consistency, not independent scientific accuracy. Review causal arrows,
labels, comparisons and the script's scientific claims before publishing.

Diagrams are labeled schematic and are not numerical simulations. The orbit and
air/water refraction templates are qualitative explanations, not measured data or
general physics solvers. Arbitrary narration is not automatically converted into
a fake process. Limited transport/refraction fallbacks recognize explicit matching
sentences when the scene writer's JSON is unavailable.

A validated animation with a prepared renderer counts toward the visual quality
gate. A video can therefore publish with useful animations even when it has no stock
footage. Cards and invalid/unrenderable animation specifications do not qualify.
Renderer errors stop the render instead of silently replacing diagrams with blanks.
Production holds videos when more than 25% of the scene plan uses fallback cards.
For plans with four or more scenes, at least one third must include contextual
imagery or footage, either as the main shot or behind a diagram.

Shorts measure narration before sourcing assets. Overlong speech is rewritten and
remeasured up to three times, preserving complete sentences and the explanation.
Scenes align against the complete narration rather than searching far ahead for
each individual word. Long-form scene plans are generated in bounded batches.

Long-form uploads run Monday and Thursday at 18:00 Nepal time, alongside the
existing manual `science_long` option. Both video formats retain the visual quality
gate before publication.

## Setup

GitHub Actions prepares Node 22, the locked dependencies, and Chrome Headless Shell
for Shorts/long-form jobs. Social posts and comment replies skip these steps. If
optional animation setup fails, media sourcing still runs and the quality gate
reports whether there are usable visuals.

For local development:

```powershell
npm ci --prefix motion
node motion/ensure-browser.mjs
node motion/render.mjs motion/examples/transport.json automation/storage/motion-demo.mp4
```

Examples under `motion/examples/` can be rendered without any writing, narration,
stock-media or video-generation keys. `ANIMATION_ENABLED=false` disables animation
routing. Rendered scenes are cached by specification, timing, dimensions, image
content and renderer source, so changed scripts or templates get fresh renders.

Remotion is pinned to 4.0.541 across its packages. Consult its
[license](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) for free-use
eligibility and company licensing. CPU runner time, downloads and storage still
apply. The animation code uses [Remotion's renderer](https://www.remotion.dev/docs/renderer/render-media)
and does not require a GPU inference service.
