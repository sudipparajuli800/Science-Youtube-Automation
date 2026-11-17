---
name: science-video-production
description: Improve scripts, explanatory animation, media selection and editing in Science-Youtube-Automation. Use for changes to this repository's Shorts and long-form science production pipeline, including offline visual review.
---

Work in the Science-Youtube-Automation checkout. Read `MOTION_GRAPHICS.md` for
the current renderer schema and `VISUAL_STORYTELLING.md` for the reviewed tools
and offline preview command. This skill adds no permission to publish or buy media.

Treat scientific explanation and media selection as separate problems. Verify
important claims against primary sources when editing a script; template validation
only checks consistency with narration. A polished unsupported claim is still wrong.

The program owns narration and shot IDs. The director supplies bounded data,
never executable scene code. Preserve full narration, original ordering and spoken
qualifications. Source word IDs build labels. Do not invent chart values or imply
that a schematic is a measurement or real footage.

Choose imagery for visible subjects, and graphics for relationships. Retain the
subject photo or video as one continuous background when it helps. Keep the
long-form explanation centered. Avoid extra panel backgrounds behind labels,
diagrams and subtitles. Use the existing Barlow fonts and channel palette.

The templates have distinct meanings: `flow` explains a directed mechanism,
`transport` movement, `comparison` a contrast, `cycle` a repeated loop, and `layers`
an explicitly described structure. `photo` uses a verified local image. Bars need
spoken values with shared units. Avoid defaulting every technical sentence to a
chain of generic particles. Use a more specific supported icon or real subject.

Motion should help the viewer follow speech. `draw` traces a developing explanation,
`assemble` brings related elements into place, and `focus` emphasizes the current
subject while retaining the comparison. Leave time to read the completed graphic.
All visual state must be determined by frame/time; scrubbing backward must work.

After renderer changes, run the offline review command in `VISUAL_STORYTELLING.md`
for the affected templates in portrait and landscape. Inspect early, middle and
late actual rendered frames, plus overlay mode if changed. Check legibility,
clipping, label meaning, single-background composition and the final reading hold.
Preview fixtures use synthetic cue timing; they do not prove production alignment.

Run the relevant Python regressions and `node --test motion/tests/storytelling.test.mjs`
when timing logic changes. Include every new renderer source file in both the
Python scene-cache digest and Node bundle digest. Keep quality gates intact.
If remote providers fail, fix the failing stage rather than rerunning repeatedly
or weakening media relevance requirements. Verify a real video ID before claiming
publication. A green Actions run alone is insufficient.
