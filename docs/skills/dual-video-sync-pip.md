# `dual-video-sync-pip`: camera + screen recording, synced, with PiP

[← All skills](README.md)

## What it does

For video tutorials:

1. Syncs the camera with the screen recording by sound, using Resolve's waveform auto-align.
2. Lays the screen recording on the **Screen** track under the already cut A-roll.
3. Puts a picture-in-picture camera on the **PiP** track.
4. Switches between camera, screen and PiP by your Purple markers.

PiP is built with clip transform properties (zoom, pan, tilt). A MotionVFX placeholder frame is offered as an optional manual finish.

Principle: A-roll is never changed. It stays under everything as the continuous camera, so the cut and its grades are untouched. Screen covers it where the screen should show, and PiP puts the face back on top in PiP sections. Voice keeps the camera audio.

## When it triggers

Automatically for a tutorial or screencast with a separate screen recording and a camera, when you want them synced, switching between face and screen, or a face-in-corner PiP, and on Purple markers. Ukrainian trigger phrases: «синхронізуй екран і камеру», «запис екрану», «картинка в картинці», «обличчя в кутку», «перемикай камеру й екран». English one: "PiP". In `edit-episode` it is stage B, step 5, after `text-based-cut`, and only for tutorials with a screen recording.

Explicit call:

```
/davinci-editor:dual-video-sync-pip [timeline] [corner-br|corner-bl|corner-tr|corner-tl] [pip size 0.1-0.5]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | the cut timeline to work on | the newest `rough cut` timeline |
| `layout` | PiP corner: `corner-br`, `corner-bl`, `corner-tr`, `corner-tl` (bottom/top, right/left) | `pip_layout` (`corner-br`) |
| `size` | PiP camera width as a share of the frame width | `pip_size` (`0.28`) |

## Before you start

- A cut timeline with the camera on A-roll and its audio on Voice (`text-based-cut`).
- Screen recordings in the bin `01_Footage/Screen` (from `project-bootstrap`); elsewhere, Claude asks.
- Both recordings contain the same sound: the screen recorder capturing the mic, or a clap. Without it, Claude asks you for one sync point, a click or clap visible on both.
- Purple markers on the timeline or on the camera clips (below). Without them, Claude asks for a default mode.

## Markers it reads

**Purple** = switch; the marker **name** is the mode, and the note may say more.

| Marker name | Mode | Screen track | PiP track |
|---|---|---|---|
| `камера` / `camera` | camera | empty | empty |
| `екран` / `screen` | screen | screen recording | empty |
| `pip` | pip | screen recording | camera, scaled to the corner |

A point marker starts a mode that lasts until the next Purple marker. A marker with duration sets the mode only for that range, and the previous mode resumes after it. No Purple markers → Claude asks for a default. For tutorials that is usually `pip` all the way, camera only for the intro and outro.

Markers are read from the timeline and from the camera clips. Clip markers are mapped onto the timeline through the A-roll items that contain them. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## Track model

Tracks bottom → top: Backgrounds, **A-roll** (camera, as cut), **Screen** (screen recording), **PiP** (camera copy, small), B-roll, Effects, Titles.

If Screen or PiP is missing:

- **every video track above A-roll is empty** (normal right after the rough cut): Claude renames them in order (Screen, PiP, B-roll, Effects, Titles) and adds the missing ones on top;
- **otherwise:** it asks you to add the tracks above A-roll by hand (Add Track → position) and name them, as `track-layout` explains.

The screen recording's own audio is not placed, unless you want system sounds. Then it goes on a muted `Screen audio` track.

## Settings

| Key | Default | Effect |
|---|---|---|
| `pip_layout` | `corner-br` | PiP corner when `layout` is not given |
| `pip_size` | `0.28` | PiP width as a share of the frame when `size` is not given |
| `split_j_lead_frames`, `split_l_tail_frames`, `split_max_frames` | `12`, `12`, `50` | split edits on the camera ↔ screen switches (`split-edits` mode 1) |

Any setting can be overridden in the prompt: "PiP top left, size 0.2".

## Files

All under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `pip-input.json` | A-roll items, clip fps, recording pairs with offsets, sections from the markers, layout |
| `timeline-<name>.json`, `pip-input-split.json` | only when split edits on the switches are offered: timeline dump and the shifted sections |
| `pip-plan.json` | Screen and PiP segments, PiP transform values, warnings |

## Workflow and approval stops

1. **Pairs the recordings.** Each camera clip under the A-roll items is paired with the screen recording made at the same time, using file dates, durations or your word. **You confirm the pairs.**
2. **Syncs by sound** on a scratch timeline `claude-sync <camera>` per pair, with waveform auto-align. It computes the offset (screen time = camera time + offset). If auto-align fails or nothing moves, it **asks you for one sync point** and computes the offset from two timecodes. Then it **asks you to play a sharp sound** (keyboard click, clap) on the scratch timeline to confirm by ear. Afterwards it deletes the scratch timeline. That delete is a permission prompt (the `guard.py` hook), and Claude says why.
3. **Reads the cut and the markers** from the target timeline and turns them into sections. Before planning, it offers **split edits on the switches** (`split-edits` mode 1): the picture follows the phrase instead of cutting at the marker frame. You see the notes with the plan and decide.
4. **Plans** the Screen and PiP segments (`pip_plan.py`). Parts without screen recording stay camera, and Claude tells you where.
5. **Finds or re-roles the Screen and PiP tracks** (above). **Shows the plan:** sections with timecodes, mode and duration, plus the layout. **Waits for your yes**, then backs up the timeline.
6. **Places and lays out:** the screen recording on Screen and the camera copy on PiP. PiP items get their transform values, which Claude reads back and compares. On the first PiP item it exports a still and checks the camera really sits in the chosen corner with the margin. If the direction or units are off, it fixes the numbers once and continues. Screen items stay full frame. If the recording's aspect differs (16:10 Mac screens), the timeline scaling handles it, and Claude mentions black bars or crop.
7. Loads the remote `claude` grade on the PiP items (they are the same camera clips), recolors clips by role with `track-layout`, saves the project.
8. **Optional MotionVFX placeholder:** for a styled frame instead of a plain corner, Claude searches the MotionVFX catalog. Effects can't be attached through the API, so it lists the PiP items with timecodes and the chosen effect, and you drag it on (Paste Attributes copies it to the rest). Resolve 21's own **Picture in Picture** Resolve FX is the built-in alternative, also manual.
9. Reports pairs and offsets, sections per mode (count, total duration), parts without screen recording, layout values, and what to check by eye.

## What it never does

- Move, trim or replace A-roll items or the Voice track.
- Guess a sync offset without sound or a confirmed sync point.
- Leave the scratch sync timelines behind.

## Place in the workflow

`uk-transcribe` → `track-layout` → `text-based-cut` → **`dual-video-sync-pip`** → `marker-edit` (Fuchsia, Cocoa) → `split-edits`

Offer split edits on the switches here: once Screen items are placed, `split-edits` reports camera ↔ screen splits instead of building them.

## Example prompts

**Minimal:**

> Sync the camera with the screen recording on the rough cut and make PiP from my Purple markers.

**With arguments:**

```
/davinci-editor:dual-video-sync-pip "Router - rough cut 2026-11-02" corner-bl 0.25
```

**Overriding a setting:**

> Make the PiP from my Purple markers, but top right and smaller, 0.2 of the width: the router admin page has its menu in the bottom right corner.

**Professional brief:**

> Router lesson, timeline "Router - rough cut 2026-11-02". Camera IMG_4140–4142, screen recordings are in 01_Footage/Screen, recorded at the same time, and the recorder captured my mic. My Purple markers set the modes: camera for the intro, then screen, then pip to the end. PiP bottom right, default size. Offer split edits on the switches. Don't touch A-roll or Voice. Check the first PiP on a still before doing the rest. At the end give me the offsets per pair, the sections per mode, any parts without screen recording, and where to check lip sync on mouse clicks.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Add the screen" | "Sync the screen recordings with the camera by sound on the latest rough cut, follow my Purple markers, PiP bottom left at 0.25. Tell me where the screen recording runs out." |

The strong prompt names the timeline, the sync method, the source of the modes and the layout, and asks for the gaps, so the plan comes back ready to approve.

## What to check afterwards

- Lip sync and click sync: the screen's mouse clicks match the sound.
- The PiP doesn't cover important UI. If it does, ask for another corner or size.
- Parts the report lists without screen recording.
- Black bars or crop on screen recordings with a different aspect.
- The PiP items carry the grade (remote `claude` version).
