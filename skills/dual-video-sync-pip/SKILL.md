---
name: dual-video-sync-pip
description: For video tutorials in DaVinci Resolve Studio 21+ - syncs the camera with the screen recording by sound (Resolve's waveform auto-align), then lays the screen recording on the Screen track under the already cut A-roll and a picture-in-picture camera on the PiP track, switching camera / screen / PiP by the user's Purple markers. PiP is built with clip transform properties; MotionVFX placeholders are offered as an optional manual finish.
when_to_use: Tutorial or screencast with a separate screen recording and a camera; user wants them synced, switching between face and screen, or a face-in-corner PiP; stage B of edit-episode after text-based-cut; Purple markers. Triggers - "синхронізуй екран і камеру", "запис екрану", "картинка в картинці", "PiP", "обличчя в кутку", "перемикай камеру й екран".
argument-hint: "[timeline] [corner-br|corner-bl|corner-tr|corner-tl] [pip size 0.15-0.4]"
arguments: [timeline, layout, size]
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *pip_plan.py *)"
  - "Bash(python3 *catalog.py *)"
  - "Bash(python3 *tc.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Camera + screen sync and PiP

Follow `resolve-core` first. Timeline: `$timeline` (default: the newest `rough cut` timeline). Layout: `$layout` (default `${user_config.pip_layout}`), size `$size` (default `${user_config.pip_size}`, share of frame width).

Script: `${CLAUDE_SKILL_DIR}/scripts/pip_plan.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/pip_plan.py selftest`).

## Track model

Tracks bottom → top: Backgrounds, **A-roll** (camera, as cut), **Screen** (screen recording), **PiP** (camera copy, small), B-roll, Effects, Titles. A-roll is never changed: it stays under everything as the continuous camera, so the cut and its grades are untouched. Screen covers it where the screen should show; PiP puts the face back on top in PiP sections. Voice keeps the camera audio; the screen recording's own audio is not placed unless the user wants system sounds (then on a muted `Screen audio` track).

Section modes (Purple markers, name = mode; note may say more):

| Marker name | Mode | Screen track | PiP track |
|---|---|---|---|
| `камера` / `camera` | camera | empty | empty |
| `екран` / `screen` | screen | screen recording | empty |
| `pip` | pip | screen recording | camera, scaled to the corner |

A point marker starts a mode that lasts until the next Purple marker; a marker with duration sets the mode only for that range (the previous mode resumes after it). No Purple markers → ask for a default (tutorials: usually `pip` all the way, camera-only for intro/outro).

## 1. Pair the recordings

1. Camera clips: the media pool items under the A-roll items of the timeline. Screen recordings: bin `01_Footage/Screen` (from `project-bootstrap`), or ask.
2. Pair each camera clip with the screen recording made at the same time (file dates, durations, the user's word). Show the pairs; get a yes.

## 2. Sync by sound

For each pair, on a scratch timeline `claude-sync <camera>` that you create and later delete:

```python
tl = mp.CreateEmptyTimeline(f"claude-sync {CAM_NAME}"); project.SetCurrentTimeline(tl)
tl.AddTrack("video"); tl.AddTrack("audio", "stereo")
cam = mp.AppendToTimeline([{"mediaPoolItem": cam_clip, "trackIndex": 1, "recordFrame": tl.GetStartFrame()}])
scr = mp.AppendToTimeline([{"mediaPoolItem": scr_clip, "trackIndex": 2, "recordFrame": tl.GetStartFrame()}])
items = [i for i in cam + scr]
ok = tl.AutoAlignClips(items, {"SyncUsing": resolve.AUTO_ALIGN_CLIPS_USING_WAVEFORM})
c = next(i for i in tl.GetItemListInTrack("video", 1)); s = next(i for i in tl.GetItemListInTrack("video", 2))
fps = float(tl.GetSettings()["timelineFrameRate"])
result = {"ok": ok, "cam_start": c.GetStart(), "cam_src": c.GetSourceStartTime(), "scr_start": s.GetStart(), "scr_src": s.GetSourceStartTime(), "fps": fps}
```

`offset_s` (screen time = camera time + offset) = `(cam_start - scr_start) / fps + scr_src - cam_src`. Both recordings must contain the same sound (the screen recorder capturing the mic, or a clap). If `ok` is false or nothing moved, the screen recording has no usable audio: ask the user for one sync point (a click or clap visible on both) and compute the offset from two timecodes with `tc.py`.

Verify by ear: put the playhead on a sharp sound (keyboard click, clap) and ask the user to play it on the scratch timeline. Then delete the scratch timeline (yours; the guard will ask the user, say why).

## 3. Read the cut and the markers

From the target timeline (re-fetch it by name): A-roll items (`GetStart`, `GetDuration`, `GetSourceStartFrame`, media pool item id), Purple markers on the timeline (frames relative to `GetStartFrame()`; convert to absolute) and on camera clips (convert clip frames to record frames through the A-roll items that contain them). Timeline fps, width, height from its settings; each clip's `FPS` and frame count from clip properties.

Write `<work>/pip-input.json` in the format at the top of `pip_plan.py`. `sections` takes only start points, so expand a Purple marker **with duration** into two entries: its mode at its start and the previously active mode at its end. Then run:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/pip_plan.py "<work>/pip-input.json" > "<work>/pip-plan.json"
```

Read `warnings`: parts without screen recording stay camera; tell the user where.

## 4. Tracks

Find `Screen` and `PiP` by role (`track_index` from `track-layout`). Missing:
- if every video track above A-roll is empty (normal right after the rough cut), re-role them by renaming in order (Screen, PiP, B-roll, Effects, Titles) and add the missing ones on top;
- otherwise ask the user to add the tracks above A-roll by hand (Add Track → position) and name them; `track-layout` explains how.

Show the plan (sections with timecodes, mode, duration; layout) and get a yes. Back up the timeline first (`resolve-core` §3).

## 5. Place and lay out

1. Append calibration from `resolve-core` (once per session).
2. Screen entries → `mediaType: 1`, `trackIndex: screen`, `startFrame`/`endFrame` per calibration, `recordFrame: record`. PiP entries → same with the camera clip on `trackIndex: pip`. Batches ≤ 50.
3. PiP items: `item.SetProperties(pip_properties)` from the plan, then `GetProperties()` and compare. On the **first** item export a still and check the camera really sits in the chosen corner with the margin; if Tilt or Pan go the wrong way or zoom units differ, fix the numbers once (record it in `resolve-core/reference.md` terms for the user) and continue.
4. Screen items keep full frame; if the recording's aspect differs (16:10 Mac screens), the timeline's scaling setting handles it — mention black bars or crop to the user.
5. Load the remote `claude` grade on PiP items (`resolve-core` §7): they are the same camera clips.
6. `track-layout recolor`, save the project.

## 6. Optional: MotionVFX placeholder

If the user wants a styled frame instead of a plain corner: `python3 ${CLAUDE_SKILL_DIR}/../motionvfx-catalog/scripts/catalog.py search "<catalog>" --category Effects placeholder corner screen frame` (run `motionvfx-catalog` first if there's no catalog). Effects can't be attached through the API, so list the PiP items (timecodes) and the chosen effect name, and ask the user to drag it on (it can be copied to the rest with Paste Attributes). Resolve 21's own **Picture in Picture** Resolve FX is the built-in alternative, also manual.

## 7. Report

Pairs and offsets, sections placed per mode (count, total duration), parts without screen recording, layout values, what to check by eye (lip sync on the screen's mouse clicks, PiP not covering important UI).

## Never

- Move, trim or replace A-roll items or the Voice track.
- Guess a sync offset without sound or a confirmed sync point.
- Leave the scratch sync timelines behind.
