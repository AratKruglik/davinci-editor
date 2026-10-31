---
name: tutorial-zooms
description: Zooms for video tutorials in DaVinci Resolve Studio 21+ - eased push-ins onto the part of a screen recording being talked about (a button, a code line, a terminal), driven by the user's Pink markers (note = area and strength), with the region read off an exported still, keyframed in a Fusion Transform so the frame never shows black edges and close zooms pan from one spot to the next instead of bouncing out and in; plus static punch-ins on alternate A-roll segments to hide jump cuts.
when_to_use: User wants to zoom into the screen, enlarge a detail, "наблизь на кнопку", has Pink markers, or wants jump cuts in a talking-head cut hidden with punch-ins; the zoom step of edit-episode stage D. Triggers - "зроби зуми", "наближення на екран", "збільш код", "покажи ближче", "зум на кнопку", "punch in", "сховай джамп-кати", "tutorial zooms".
argument-hint: "[timeline] [screen|punch-in]"
arguments: [timeline, mode]
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *zooms.py *)"
  - "Bash(python3 *tc.py *)"
  - "Bash(python3 *timeline_map.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Tutorial zooms

Follow `resolve-core` first. Timeline: `$timeline` (default current). Mode: `$mode` (default `screen`; `punch-in` for jump cuts).

Script: `${CLAUDE_SKILL_DIR}/scripts/zooms.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/zooms.py selftest`). Settings: default scale `${user_config.zoom_default_scale}`, max `${user_config.zoom_max_scale}`, ease `${user_config.zoom_ease_s}` s, punch-in `${user_config.punch_in_scale}`.

Principle: a zoom answers "where do I look?" exactly when the speaker says it. Late, too strong or too frequent zooms make viewers seasick and hide context they need.

## 0. Prepare

1. Timeline dump (`resolve-core/reference.md#timeline-dump`) and, if transcripts exist, words on the timeline (`timeline_map.py words`) to time zooms to speech.
2. Backup the timeline (`resolve-core` §3). Save the project. Record `GetProperties()` of every item you will touch in `<work>/zooms-before.json`.

## 1. Screen zooms (`screen`)

Targets: **Pink** markers (timeline and items, `marker-edit` rules, skip `claude:done:*`); requests from the user. Each target needs:
- **The item**: the `Screen` track item under the marker; no Screen track (screen-only lesson) → the `A-roll` item. Talking-head camera → wrong mode, ask.
- **Range**: marker with duration → exactly that; point marker → from the marker to the end of the sentence that talks about the spot (words file), 2–5 s; never across an edit point on that track: end 2 frames before the cut and say so.
- **Region**: still at the marker: `tl.ExportFrame(frame - tl.GetStartFrame(), {"outputType": "file", "filePath": "<work>/stills/zoom-<n>.png", "maxDimension": 1920})` (Resolve 21.1.2+, `resolve-core` §10; no playhead move; Mac path, `resolve-core` §8). Older: playhead to the marker, `project.ExportCurrentFrameAsStill("<work>/stills/zoom-<n>.tif")`. Read the image, and find what the note names ("кнопка Save", "код праворуч", "термінал"). Write the box as `[x, y, w, h]`, 0..1 from the top-left, around the whole element plus a little context (a line of code, not one word). Can't find it on the still → ask, with the still's path.
- **Strength** from the note: "трохи" ≈ 1.3, nothing ≈ default, "сильно" up to the max. Above the max, screen text turns soft on a 4K timeline; tell the user instead of exceeding it.

Show the table before building: `# | TC | item | region (what) | scale | duration | chained`. Wait for the yes.

Build, per item (all zooms on one item go into one comp):
1. `item.GetFusionCompCount()` > 0 and the comp has no `ZOOM` tool → it's the user's Fusion work: stop for that item and ask. A comp with `ZOOM` from an earlier run → rebuild its keys (say so).
2. `zooms.json` with `fps`, `item_start` = `item.GetStart()`, `comp_start` (discover once per session, `resolve-core/reference.md` runtime discovery), the zooms and settings from config; then
   `python3 ${CLAUDE_SKILL_DIR}/scripts/zooms.py plan "<work>/zooms/<item>.json" --out "<work>/zooms/<item>-spec.json"`.
   It eases in and out (`inout` cubic), keeps the scaled image covering the frame (focus clamped near edges), and chains zooms closer than 1 s into a pan. Report its warnings.
3. Apply the spec with the Fusion builder (`resolve-core/reference.md#fusion-builds-from-a-spec`): `MediaIn1 → ZOOM (Transform) → MediaOut1`. The zoom lives inside the comp, so the clip's Inspector transform (PiP layout from `dual-video-sync-pip`) stays as it is; check the PiP still sits right after the first build.
4. Verify each zoom: stills (same `tl.ExportFrame` call) at its middle and 1 s after its end, Read them: the element is centered and readable, no black edge, back to full frame afterwards. Fusion on 4K screen recordings is heavy: offer `item.SetFusionOutputCache("Auto")` for smooth playback.

**MotionVFX zoom (only when the user asks for it, Resolve 21.1.2+).** The `mHowTo Zoom` effect instead of the Transform route, on a media item only:
1. Id from `resolve.GetEffectsList("video")` (name `mHowTo Zoom`); not installed → say so and use the Transform route. An item whose `GetEffects("fusion")` comps already have `FindTool("mHowTo_Zoom")` → from an earlier run: set its inputs, don't add a second one.
2. `fx = item.AddEffect("fusion", id)`, `macro = fx.GetFusionComp().FindTool("mHowTo_Zoom")`. Inputs (verified, `resolve-core/reference.md`): `Input4` Zoom Scale, `Input3` Movement Target `{1: x, 2: y}`, `Input5`/`Input6` ease in/out. `SetInput`, re-read `GetInput`.
3. Unverified, so probe on the first zoom: the unit of Zoom Scale (default 0.3, not the skill's scale factor, so `zoom_max_scale` can't be applied as a number), the origin of Movement Target, and the timing (the effect sits on the whole item, so the move follows the macro, not the zoom range or chaining). Export stills at the item's start, middle and end, show them, and do the rest only after the yes.
4. Undo: `item.DeleteEffects([fx])` (guarded). Record the item's effects before the change in `zooms-before.json`.

## 2. Punch-ins (`punch-in`)

Hides jump cuts in a talking head: segments between the Cream `cut` markers of `text-based-cut` alternate between 100 % and `${user_config.punch_in_scale}`.
1. A-roll items in order; skip items under a B-roll / Screen insert (not visible), items with a non-default Inspector transform (PiP, user's reframe), and segments shorter than 2 s (a size jump every second is worse than the jump cut).
2. Face position: still from the middle of the first item of each shot setup, Read it, take the point between the eyes as `X Y` (0..1 from the top-left).
3. `python3 ${CLAUDE_SKILL_DIR}/scripts/zooms.py punch --width <w> --height <h> --scale ${user_config.punch_in_scale} --face X Y` → `ZoomX/ZoomY/Pan/Tilt` that enlarge the shot and keep the eyes where they were.
4. Every second item: `item.SetProperties(props)`, re-read `GetProperties()`. Units of Pan/Tilt and Zoom are in the runtime-discovery list: check the first item on a still before doing the rest.

Show the list of items that change before applying; apply after the yes.

## 3. Finish

Mark handled Pink markers `claude:done:tutorial-zooms:<date>`. Save. Report: zooms built (TC, what, scale), items skipped and why, punch-in items, stills to look at, how to undo (`zooms-before.json`; Fusion comps and MotionVFX effects named in the report). Suggest a soft whoosh on big zooms only if `sound-design` runs again (never on every zoom).

## Never

- Zoom beyond `${user_config.zoom_max_scale}`, across an edit point, or with a black edge in frame.
- Change an item's existing Fusion comp that isn't Claude's `ZOOM`, or its Inspector transform in `screen` mode.
- Zoom on more than every ~10 s on average without the user asking; propose dropping the weakest instead.
