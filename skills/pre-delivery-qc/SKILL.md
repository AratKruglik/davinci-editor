---
name: pre-delivery-qc
description: Read-only quality check of a timeline before rendering in DaVinci Resolve Studio 21+ - offline media, black frames and gaps in the picture, one- and two-frame flash frames, voice dropouts, disabled clips and tracks, frame-rate mismatches, timeline settings vs the delivery format, empty tracks, unhandled user markers and leftover Claude markers, missing grades, subtitles and chapters, plus measured loudness and peak of the mix; reports with timecodes, puts Cream markers on problems and fixes nothing by itself.
when_to_use: Before any final render or upload, after late edits, when the user asks "чи все готово?", or as the gate deliver runs first; QC step of edit-episode stage D. Triggers - "перевір перед рендером", "QC", "чи все ок з таймлайном", "знайди чорні кадри", "перевір дірки", "офлайн медіа", "pre-delivery check", "quality check".
argument-hint: "[timeline] [youtube|shorts]"
arguments: [timeline, target]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *qc.py *)"
  - "Bash(python3 *loudness.py *)"
  - "Bash(python3 *chapters.py *)"
  - "Bash(python3 *tc.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Pre-delivery QC

Follow `resolve-core` first. Timeline: `$timeline` (default current). Target: `$target` (default `youtube`; `shorts` for a vertical timeline).

Script: `${CLAUDE_SKILL_DIR}/scripts/qc.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/qc.py selftest`).

This skill only looks. It doesn't trim, delete, relink or move anything: every fix is an editorial decision or needs the user's eyes, and a QC that "fixes" silently can't be trusted. The only things it writes are reports, Cream markers and (for loudness) a temporary render job it removes again.

## 1. Timeline checks

1. Timeline dump (`resolve-core/reference.md#timeline-dump`).
2. Expected format: `youtube` → the episode's own settings (report them: UHD 3840×2160 or 1920×1080, fps); `shorts` → `${user_config.shorts_resolution}`, same fps.
3. ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/qc.py check "<dump>" --expect-width <w> --expect-height <h> --expect-fps <fps> --out "<work>/qc-<timeline>.json"
   ```
   It also records `verdict` and the timeline `state` (end frame, item counts) it checked. Finds: black (no picture on any enabled non-title track), audio or titles running past the last picture, items of ≤ 3 frames (flash frames), media not `Online`, disabled clips and tracks, speed changes, clips whose fps differs from the timeline, 1–2 frame holes between Voice items (clicks), empty tracks, user markers not marked done, Cream markers still on the timeline, settings that don't match the delivery.

## 2. Checks in Resolve

- **Grades:** on every A-roll / B-roll / Screen item, `GetCurrentVersion()` is the remote `claude` version (or the user's own grade). An item on `versionName` "" with no grade → finding `ungraded`.
- **Looks:** stills at 0 %, 25 %, 50 %, 75 %, the last second, and the middle of every Fusion title (`fusion_comps` > 0 in the dump): `tl.ExportFrame(frame - tl.GetStartFrame(), {"outputType": "file", "filePath": "<work>/qc/<n>.png", "maxDimension": 1280})` from `run_script` (21.1.2, `resolve-core` §10: the finished composite with grade, every track and titles; the user's playhead stays put), check `success`, Read them. Older Resolve: `tl.SetCurrentTimecode`, `project.ExportCurrentFrameAsStill("<work>/qc/<n>.tif")`. Look for: a missing font (boxes or a fallback face), text outside the safe area, a frame that is still log-flat or wildly off in color, a PiP covering a title.
- **Subtitles / chapters** (`youtube`): `<work>/subtitles/<timeline>.uk.srt` exists and is newer than the last edit (else finding `subtitles-stale`); `<work>/chapters.json` passes `python3 ${CLAUDE_SKILL_DIR}/../chapters-markers/scripts/chapters.py check …` with the current duration.
- **Loudness:** if `audio-finish` measured this timeline after the last audio change, reuse its numbers (say from when). Otherwise run its §4 measurement exactly as written there (record and restore the render format, add only your own audio-only job, delete only that job) and
  `python3 ${CLAUDE_SKILL_DIR}/../audio-finish/scripts/loudness.py measure "<work>/audio/mix-check.wav" --target ${user_config.loudness_target_lufs} --ceiling ${user_config.true_peak_db}`.
  More than ±1 LU off or a peak over the ceiling → finding `loudness` (error); the fix is `audio-finish`, not this skill. On 21.1.2, to say *which* clip is off, add `item.AnalyzeAudioLevels("YouTube")` → `{"Integrated", "TruePeak"}` of the Voice and Music items to the message (no render; per item only, never a substitute for the mix value).

Record every finding from this section in the same file, so `deliver` gates on one verdict:
`python3 ${CLAUDE_SKILL_DIR}/scripts/qc.py add "<work>/qc-<timeline>.json" --severity error|warn|info --kind <kind> --message "<text>" [--tc <TC>]`
(kinds: `ungraded`, `look`, `subtitles-stale`, `chapters`, `loudness`). Never edit the JSON by hand.

## 3. Report

Write `<work>/qc-<timeline>.md` and show it:

**Verdict:** `PASS` (no errors), `PASS WITH WARNINGS`, or `FAIL`, with counts.

| # | severity | TC | track | problem | suggested fix (who) |

Fix suggestions name the owner: black / flash frame / dropout → trim or extend in the edit (user, or `text-based-cut` again); offline → relink in the media pool (user); empty tracks → `track-layout cleanup`; open markers → the skill of that color (`marker-edit`); loudness → `audio-finish`; stale subtitles → `subtitles-uk`.

Put a Cream marker on each error with a frame (`customData` `claude:qc:<kind>`, name = kind, note = the message), offset by one frame if a user marker sits there. Remove Cream `claude:qc:*` markers from a previous QC run only after the user agrees (the guard will ask; name them).

`deliver` reads `qc-<timeline>.json` (`verdict`, `state`): it renders only after a `PASS` or after the user accepted the listed errors by name, and only while `qc.py stale` says the timeline hasn't changed.

## Never

- Change items, tracks, settings or the user's markers.
- Mark the timeline as passed while an error is open, or drop a finding because it is "probably intended" (list it as a warning instead).
- Leave the loudness render job or changed render format behind.
