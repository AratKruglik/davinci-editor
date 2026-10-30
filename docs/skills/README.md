# Skill guide

Detailed documentation for every skill of the `davinci-editor` plugin: what each one does, what it needs, which markers and settings it reads, where it stops for your approval, and example prompts from minimal to a full professional brief.

Install: [install.md](../install.md) · Settings: [settings.md](../settings.md) · Troubleshooting: [main README](../../README.md#troubleshooting).

## How to call a skill

- **Plain language.** Describe the task ("convert A-Roll from Apple Log to 709", «зроби рибу») and Claude picks the skill. Skills answer in your language; Ukrainian and English prompts both work.
- **Slash command.** `/davinci-editor:<skill> [arguments]`. With the Cowork build the prefix is `/davinci-editor-cowork:`.
- **Settings in the prompt.** Any plugin setting can be overridden for one run by saying it: "pause threshold 500 ms", "PiP corner top left", "loudness target -16 LUFS".

## Skills by stage

The order follows [`edit-episode`](edit-episode.md), which runs the whole workflow with an approval stop after every step.

### Always on

| Skill | What it does |
|---|---|
| [`resolve-core`](resolve-core.md) | hidden shared rules: connection check, backups, delete guard, timecodes, tracks by role, marker etiquette, node labels |
| [`edit-episode`](edit-episode.md) | the whole workflow, stages A–D, resumable from `episode.md`; slash command only |
| [`marker-edit`](marker-edit.md) | reads your colored markers, plans, and dispatches each color to its skill |

### Stage A: project and color before the cut

| Skill | What it does |
|---|---|
| [`project-bootstrap`](project-bootstrap.md) | new project with settings, bins and import, or sorts an open project's media pool |
| [`log-to-rec709`](log-to-rec709.md) | Apple Log / Apple Log 2 → Rec.709 from a DRX node template, in a remote grade version |
| [`chart-match`](chart-match.md) | ColorChecker 24 match in linear light → DCTL on the `CHART` node, ΔE00 report |
| [`natural-skin-grade`](natural-skin-grade.md) | measured neutral balance and skin toward the skin tone line |
| [`depth-background-blur`](depth-background-blur.md) | background blur with AI CineFocus or Depth Map, per clip or scene |

### Stage B: transcript and rough cut

| Skill | What it does |
|---|---|
| [`uk-transcribe`](uk-transcribe.md) | Resolve transcription with a language check; JSON / SRT / TXT export |
| [`track-layout`](track-layout.md) | role-based tracks, clip colors, locking, cleanup of empty tracks |
| [`text-based-cut`](text-based-cut.md) | cut list from transcript and markers → approval → new timeline |
| [`dual-video-sync-pip`](dual-video-sync-pip.md) | camera + screen recording synced by sound, PiP by Purple markers |
| [`split-edits`](split-edits.md) | J- and L-cuts where the picture source changes |

### Stage C: sound

| Skill | What it does |
|---|---|
| [`voice-isolation`](voice-isolation.md) | AI Voice Isolation on the Voice track or clips |
| [`sound-design`](sound-design.md) | cue sheet → approval → SFX, music and ambience from your library |
| [`audio-effects`](audio-effects.md) | live music, room reverb on SFX, pan sweeps, Music Remixer, Expander; EQ and effects pasted from reference clips |
| [`audio-finish`](audio-finish.md) | dialogue leveling, Rose fixes, measured loudness to the target |

### Stage D: graphics, derivatives, delivery

| Skill | What it does |
|---|---|
| [`motionvfx-catalog`](motionvfx-catalog.md) | catalog of installed MotionVFX / Fusion templates (forked helper) |
| [`fusion-motion-graphics`](fusion-motion-graphics.md) | lower thirds, callouts, kinetic phrases, counters from Cyan markers |
| [`tutorial-zooms`](tutorial-zooms.md) | eased screen zooms from Pink markers; punch-ins over jump cuts |
| [`subtitles-uk`](subtitles-uk.md) | Ukrainian SRT from the transcript; animated captions for Shorts |
| [`chapters-markers`](chapters-markers.md) | YouTube chapters from Blue markers, checked against YouTube's rules |
| [`shorts-cutdown`](shorts-cutdown.md) | 30–60 s vertical Shorts from Mint markers or the transcript |
| [`thumbnail-frames`](thumbnail-frames.md) | ranked thumbnail candidate stills from Lemon markers |
| [`pre-delivery-qc`](pre-delivery-qc.md) | read-only check before render |
| [`deliver`](deliver.md) | H.265 renders after QC, verified on disk, upload package |

## Writing prompts that get professional results

1. **Name the material.** Bin, timeline, scene or clip names: "scene kitchen", "timeline Lesson 12 - rough cut".
2. **Mark first, then ask.** Markers are the most precise brief: a Pink marker with a duration on the exact region beats "zoom where I click". The color map is in [marker-color-system.md](../marker-color-system.md) (in Ukrainian).
3. **Say what to protect.** "Keep the pauses after the demo", "don't touch the PiP section", "the first take is better here".
4. **Say what you decide yourself.** "List the soft fillers for me", "show me the cue sheet before placing anything".
5. **Ask for the report you need.** Duration before/after, ΔE per patch, measured LUFS, file sizes.
6. **One stage at a time.** Approve each step's result before the next; `edit-episode` enforces this.

Design notes (in Ukrainian): [track layout](../track-layout.md) · [marker colors](../marker-color-system.md) · [split edits](../split-edits.md) · [plan and roadmap](../davinci-plugin-skills.md).
