# Visual storytelling tools

Reviewed on 17 November 2026. The channel uses original React/SVG templates in
the existing CPU renderer. The upstream projects below were reviewed as references;
their runtimes, skills, assets and demo films have not been bundled or installed.
This keeps the channel's automated production independent of another coding agent,
a commercial-use license purchase or a new video-generation API.

| Project | Useful capability | Integration decision |
| --- | --- | --- |
| [Hyperframes](https://github.com/heygen-com/hyperframes) | Seekable HTML video and rendered-frame review; Apache-2.0 framework | Keep the current renderer and add deterministic motion plus contact-sheet review. Hyperframes remains an option for a future HTML workflow, rather than a second mandatory runtime. |
| [onetake](https://github.com/feitangyuan/onetake) | Continuous-camera product films | No bundled code or skill: its free PolyForm license is noncommercial. The channel may be monetized. |
| [gbro-collage-broll](https://github.com/pyang5166/gbro-collage-broll) | Paper-collage assembly clips | No generated-video dependency: its documented Gemini video path is paid. Original assembly motion runs locally instead. |
| [ClaudeAnimationBase](https://github.com/JohnHeibel/ClaudeAnimationBase) | Character animation and contact-sheet inspection | No character or brush renderer dependency. The README warns that watercolor fills can take seconds per frame without a GPU. |
| [Lemo-Opuscar](https://github.com/lemomo-ai/lemo-opuscar) | Code-driven film styles | No copied style guides or demos. Its code is MIT, docs have separate CC BY-NC terms and additional permissions, and assets have their own terms. Read the upstream LICENSE before importing a specific file. |

## What production now uses

- `cycle`: a 3–4-stage repeated process with a closing connection. Narration must
  identify a loop; one-way processes do not qualify.
- `layers`: 2–4 conceptual structural bands with source-grounded labels. The
  director must preserve any stated outer-to-inner order. Bands have no measured
  thickness, so these are conceptual schematics.
- `animation.treatment`: `draw`, `assemble` or `focus`. Spoken word cues control
  entrances; the final graphic remains available to read. Unknown treatments are
  discarded, not executed.
- Verified `photo` scenes use one continuous photographic canvas and short
  assembly labels, rather than a separate image card over another background.

Both Shorts and long-form scene planning receive these options. Existing contextual
media and quality thresholds are unchanged. These checks cannot independently
verify the science or guarantee that every generated shot is well directed.

## Offline review

After the existing renderer setup (`npm ci --prefix motion` and
`node motion/ensure-browser.mjs`), run from the repository root:

```powershell
python -m automation.tools.render_motion_review --output automation/storage/motion-review --templates cycle,layers,transport,comparison --formats long,short
```

The manual **Visual review (no publishing)** GitHub Actions workflow runs the same
review and uploads the results as artifacts, without any media or upload credentials.

This writes actual MP4s, three sampled PNG frames per clip, contact sheets, scene
props and `review.json`. It does not call writing/media/voice APIs or publish.
Add `--templates photo --image /absolute/path/to/licensed-earth.jpg` to review the
photo example. Use an Earth image because its labels are Earth-specific.

These are short silent motion fixtures with synthetic cue timings, not completed
science videos. For a real scene, feed its props to
`node motion/render.mjs props.json output.mp4 --review`, then check its actual
narration timing, contextual media and captions in the composed video too.

The reusable project skill is at
[.agents/skills/science-video-production/SKILL.md](.agents/skills/science-video-production/SKILL.md).
It is authoring guidance; GitHub Actions uses the production director prompt and
renderer code directly and does not require a skill-enabled coding agent.
