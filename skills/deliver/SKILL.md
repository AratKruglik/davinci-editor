---
name: deliver
description: Renders the finished episode and its Shorts from DaVinci Resolve Studio 21+ - gated by a passed pre-delivery QC, uses the user's render presets or builds YouTube 4K and Shorts H.265 settings (10-bit Main10, high bitrate, AAC 48 kHz, frame size and rate from the timeline), adds only its own jobs to the render queue without touching anyone else's, renders them, and verifies each file on disk (duration, frame size, codec, audio) instead of trusting the job status; collects the upload package (video, SRT, chapters, thumbnail brief).
when_to_use: User wants to render, export or deliver the video or Shorts for YouTube, set up render presets, or queue the final renders; last step of edit-episode stage D. Triggers - "відрендер", "рендер для ютуба", "експортуй відео", "вивантаж шортс", "постав у чергу рендеру", "готовий файл", "deliver", "render".
argument-hint: "[youtube|shorts|all] [timeline]"
arguments: [target, timeline]
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *mp4_info.py *)"
  - "Bash(python3 *qc.py stale *)"
  - "Bash(python3 *tc.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Deliver

Follow `resolve-core` first. Target: `$target` (default `youtube`; `shorts` = every `… - short …` timeline; `all` = both). Timeline: `$timeline` (default current for `youtube`).

Script: `${CLAUDE_SKILL_DIR}/scripts/mp4_info.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/mp4_info.py selftest`).

Output folder: `${user_config.render_dir}` (empty → `<work>/renders`). Never inside the media folders.

## 0. Gate

For each timeline: `<work>/qc-<timeline>.json` from `pre-delivery-qc`. Take a fresh timeline dump and run `python3 ${CLAUDE_SKILL_DIR}/../pre-delivery-qc/scripts/qc.py stale "<qc json>" "<fresh dump>"`; exit 1 (changed) or a missing file → run `pre-delivery-qc` first. `verdict` FAIL → render only after the user accepts each error by name; warnings → list them in one line and go on.

## 1. Settings

The render queue and the Deliver page belong to the user. Before changing anything record `project.GetCurrentRenderFormatAndCodec()`, `project.GetCurrentRenderMode()` (set single-clip mode `1`) and the ids in `project.GetRenderJobList()`; after rendering restore the format/codec and mode, and tell the user the other settings now hold the last delivery.

**User preset first:** `${user_config.render_preset_youtube}` / `${user_config.render_preset_shorts}` set and in `project.GetRenderPresetList()` → `project.LoadRenderPreset(name)`, then only `TargetDir`, `CustomName`, `SelectAllFrames`.

**Otherwise build it:**
1. Codec: `project.GetRenderCodecs("mp4")` → the H.265 entry (prefer the hardware encoder on Apple Silicon; the key names are in the runtime-discovery list, read them, don't guess); `project.SetCurrentRenderFormatAndCodec("mp4", <key>)`, re-read.
2. `project.SetRenderSettings({...})`:

| key | YouTube | Shorts |
|---|---|---|
| `FormatWidth` / `FormatHeight` | the timeline's (UHD 3840×2160 for a 4K episode) | `${user_config.shorts_resolution}` |
| `FrameRate` | the timeline's | the timeline's |
| `VideoQuality` | `${user_config.youtube_bitrate_mbps}` Mbit/s | `${user_config.shorts_bitrate_mbps}` Mbit/s |
| `EncodingProfile` | `Main10` (no banding in skies and gradients) | `Main10` |
| `ExportAudio`, `AudioCodec`, `AudioSampleRate` | `True`, `aac`, 48000 | same |
| `ColorSpaceTag` / `GammaTag` | `Same as Project` | same |
| `SelectAllFrames` | `True` (never change the user's in/out) | `True` |
| `TargetDir`, `CustomName` | output folder, `<timeline> - YouTube` | `<timeline> - Shorts` |
| subtitles | `ExportSubtitle: True`, `SubtitleFormat: "SeparateFile"` if the timeline has a `Subtitles UA` track | off: captions are burned in from Titles |

   `VideoQuality` as an integer is a bitrate; its unit is in the runtime-discovery list (expected kbit/s → `60000` for 60 Mbit/s). After setting, check with `project.GetRenderResolutions("mp4", key)` that the size is allowed, and read back what you can.
3. Why these: YouTube re-encodes everything, so the upload should carry as much detail as possible; 10-bit H.265 at a high bitrate is a near-lossless master at a fraction of ProRes size, and the Apple Silicon encoder renders it quickly. Don't change the project color tags to "fix" QuickTime gamma; if the user mentions it, explain Rec.709-A and let them decide.
4. Offer once: `project.SaveAsNewRenderPreset("davinci-editor YouTube H.265")` (and Shorts), and suggest putting the name in the plugin config.

## 2. Queue and render

1. `project.SetCurrentTimeline(tl)`, settings as above, `job = project.AddRenderJob()`; one job per timeline. Record your job ids; never call `DeleteAllRenderJobs` or touch jobs that were there before.
2. `project.StartRendering([your ids])`; poll `project.IsRenderingInProgress()` and `GetRenderJobStatus(id)` in separate short calls, report progress and the time left (`EstimatedTimeRemainingInMs`). Don't start a second render while one runs.
3. `Failed` / `Cancelled` → report `Error` and stop; don't re-queue blindly.

## 3. Verify the files

The job list has the output path (`GetRenderJobList()` → `TargetDir`, `OutputFilename`). For each file:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/mp4_info.py check "<file>" --seconds <timeline frames / fps> --fps <fps> --width <w> --height <h> --codec hevc --audio --min-mbps <half the target bitrate>
```

Any error (short duration, wrong size, missing audio, wrong codec, a bitrate far below the target) → the render isn't delivered: say what's wrong and what to look at (the timeline's own output size, in/out marks on the timeline, the job's settings via `GetRenderJobList()`). Ask before re-rendering; don't re-queue blindly. Report the real average bitrate (`mbps`).

## 4. Package

In the output folder, next to the video: the SRT (Resolve's or `<work>/subtitles/<timeline>.uk.srt`), `chapters.txt`, `thumbnail-brief.md` and the picked PNGs if they exist. Report a checklist for the upload: video file, subtitles (upload as Ukrainian), chapters text for the description, thumbnail candidates, Shorts files. Your finished jobs stay in the queue so the user can re-render; offer to remove only those (the guard will ask; name the ids).

Update `episode.md` if `edit-episode` is running. Save the project.

## Never

- Render without a current QC, or upload / publish anything.
- Delete or change render jobs you didn't create, or change mark in/out.
- Report a delivery as done before `mp4_info.py` passed on the file.
