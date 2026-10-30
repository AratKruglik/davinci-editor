# `deliver`: H.265 renders for YouTube and Shorts, verified on disk

[← All skills](README.md)

## What it does

Renders the finished episode and its Shorts, gated by a passed `pre-delivery-qc`. It uses your own render presets, or builds YouTube and Shorts H.265 settings (10-bit Main10, high bitrate, AAC 48 kHz, frame size and rate from the timeline). It adds only its own jobs to the render queue without touching anyone else's, renders them, and verifies each file on disk (duration, frame size, codec, audio) instead of trusting the job status. Then it collects the upload package: video, SRT, chapters, thumbnail brief.

Principle: a job's `Complete` status is not proof. A delivery is done only when the file that landed on disk passes the check.

## When it triggers

Automatically when you ask to render, export or deliver the video or the Shorts for YouTube, to set up render presets, or to queue the final renders. Ukrainian trigger phrases: «відрендер», «рендер для ютуба», «експортуй відео», «вивантаж шортс», «постав у чергу рендеру», «готовий файл». In `edit-episode` it is the last step of stage D (`deliver all`).

Explicit call:

```
/davinci-editor:deliver [youtube|shorts|all] [timeline]
```

| Argument | Meaning | Default |
|---|---|---|
| `target` | `youtube`, `shorts` or `all` | `youtube` |
| `timeline` | the episode timeline for `youtube` | the current timeline |

Targets:

| Target | What is rendered |
|---|---|
| `youtube` | the episode timeline |
| `shorts` | every `… - short …` timeline (the ones `shorts-cutdown` builds) |
| `all` | both |

## Before you start

- A current QC for every timeline: `qc-<timeline>.json` from `pre-delivery-qc`. Missing or stale (the timeline changed since), `pre-delivery-qc` runs first.
- Optional: your own render presets named in `render_preset_youtube` / `render_preset_shorts`.
- Optional, for the package: subtitles from `subtitles-uk`, `chapters.txt` from `chapters-markers`, `thumbnail-brief.md` and the PNGs from `thumbnail-frames`.

## The QC gate

For each timeline Claude takes a fresh dump and runs `qc.py stale` against the QC file:

| QC state | What happens |
|---|---|
| missing, or the timeline changed | `pre-delivery-qc` runs first |
| `PASS` | renders |
| `PASS WITH WARNINGS` | lists the warnings in one line and renders |
| `FAIL` | renders only after you accept each error by name |

## Render settings

**Your preset first.** If `render_preset_youtube` / `render_preset_shorts` is set and exists in the project, Claude loads it and changes only `TargetDir`, `CustomName` and `SelectAllFrames`.

**Otherwise it builds them.** Format mp4 with the H.265 codec read from the project's codec list (the hardware encoder on Apple Silicon is preferred), then:

| Setting | YouTube | Shorts |
|---|---|---|
| `FormatWidth` / `FormatHeight` | the timeline's (UHD 3840×2160 for a 4K episode) | `shorts_resolution` |
| `FrameRate` | the timeline's | the timeline's |
| `VideoQuality` | `youtube_bitrate_mbps` | `shorts_bitrate_mbps` |
| `EncodingProfile` | `Main10` (no banding in skies and gradients) | `Main10` |
| `ExportAudio`, `AudioCodec`, `AudioSampleRate` | `True`, `aac`, 48000 | same |
| `ColorSpaceTag` / `GammaTag` | `Same as Project` | same |
| `SelectAllFrames` | `True` (your in/out marks are never changed) | `True` |
| `TargetDir`, `CustomName` | the render folder, `<timeline> - YouTube` | `<timeline> - Shorts` |
| subtitles | `ExportSubtitle: True`, `SubtitleFormat: "SeparateFile"` if the timeline has a `Subtitles UA` track | off: captions are burned in from Titles |

Why: YouTube re-encodes everything, so the upload should carry as much detail as possible; 10-bit H.265 at a high bitrate is a near-lossless master at a fraction of the ProRes size, and the Apple Silicon encoder renders it quickly. Claude doesn't change the project color tags to "fix" QuickTime gamma; if you mention it, it explains Rec.709-A and lets you decide.

Once, Claude offers to save the built settings as presets (`davinci-editor YouTube H.265`, and one for Shorts) and suggests putting the names in the plugin settings.

The Deliver page belongs to you: Claude records the current render format/codec and render mode first (it renders in single-clip mode) and restores them afterwards. The other render settings keep the last delivery's values, and Claude tells you so.

## Settings

| Key | Default | Effect |
|---|---|---|
| `render_dir` | empty | render folder; empty = `<work_dir>/<project>/renders` |
| `render_preset_youtube` | empty | your Resolve render preset for the episode; empty = Claude builds H.265 settings |
| `render_preset_shorts` | empty | your Resolve render preset for Shorts; empty = Claude builds H.265 settings |
| `youtube_bitrate_mbps` | `60` | video bitrate of the episode |
| `shorts_bitrate_mbps` | `20` | video bitrate of the Shorts |
| `shorts_resolution` | `1080x1920` | frame size of the Shorts renders |

Any setting can be overridden in the prompt: "episode at 80 Mbit/s", "render into `~/Desktop/Upload`".

## Files

| File | Contents |
|---|---|
| `<work_dir>/<project>/qc-<timeline>.json` | read: the QC verdict and the state it checked |
| `<work_dir>/<project>/timeline-<timeline>.json` | fresh dump for the stale check |
| `<render folder>/<timeline> - YouTube.*`, `<timeline> - Shorts.*` | the renders |
| `<render folder>/` package | next to the video: the SRT (Resolve's or `subtitles/<timeline>.uk.srt`), `chapters.txt`, `thumbnail-brief.md` and the picked PNGs, if they exist |
| `episode.md` | updated when `edit-episode` is running |

## Workflow and approval stops

1. **The QC gate** (above). With a `FAIL`, **approval: accept each error by name** or fix it first.
2. Records the render format/codec, render mode and the existing job ids.
3. Loads your preset or builds the settings, checks the frame size is allowed and reads back what it can. Offers once to save presets.
4. Adds one job per timeline, records its id, renders only its own jobs, and reports progress and time left. One render at a time.
5. A job `Failed` or `Cancelled` → reports the error and stops.
6. Verifies every file with `mp4_info.py check`: duration against the timeline, frame size, `hevc` codec, audio present, average bitrate at least half the target. Reports the real average bitrate.
7. A file that fails is **not delivered**: Claude says what is wrong and where to look (the timeline's output size, in/out marks on the timeline, the job's settings). **Approval: re-render**, never re-queued blindly.
8. Restores the render format/codec and mode, collects the package and reports an upload checklist: video file, subtitles (upload as Ukrainian), chapters text for the description, thumbnail candidates, Shorts files.
9. **Question: remove Claude's finished jobs.** They stay in the queue so you can re-render; Claude offers to remove only those, naming the ids. Saves the project.

## What it never does

- Render without a current QC, or upload / publish anything.
- Delete or change render jobs it didn't create (it never calls `DeleteAllRenderJobs`), or change your mark in/out.
- Report a delivery as done before `mp4_info.py` passed on the file.
- Re-queue a failed render without asking.
- Write renders inside the media folders.

Any script that deletes or resets something, such as removing its own finished jobs, becomes a permission prompt (the `guard.py` hook), so read what you approve.

## Place in the workflow

`shorts-cutdown` → `thumbnail-frames` → `pre-delivery-qc` → **`deliver`**

Last step of the episode: after it, upload the package by the checklist.

## Example prompts

**Minimal:**

> Render the episode for YouTube.

**With arguments, per target:**

```
/davinci-editor:deliver youtube "Router Setup - final"
/davinci-editor:deliver shorts
/davinci-editor:deliver all
```

**Episode and Short together:**

> Render the episode and the Short for YouTube.

**Overriding a setting:**

> Render all Shorts at 30 Mbit/s into `~/Desktop/Upload`: this batch has a lot of fast screen motion.

**Using your preset:**

> Render the episode with my preset "YT 4K Master" and save Shorts settings as a preset too.

**Professional brief:**

> Deliver everything for tonight's upload: the episode "Router Setup - final" and both Shorts. QC passed this morning, but I nudged one title since, so check the QC is still current. Build the H.265 settings, the episode at 4K with the Ukrainian SRT as a separate file, Shorts with burned-in captions. My own ProRes job for the archive is in the queue: leave it alone. Verify every file on disk and give me the real bitrate of each. If anything fails the check, stop and ask before re-rendering. At the end give me the upload checklist.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Export the video" | "Deliver all: the final episode and every Short, H.265 at the default bitrates, keep my archive job in the queue untouched, verify files and give me the upload checklist." |

The strong prompt names the target, protects what is already in the queue and asks for the checks and the package, so nothing is reported done that didn't land on disk.

## What to check afterwards

- Play the start, the middle and the end of every file, including the last frames.
- Open the SRT next to the episode and check it lines up.
- Compare the reported real bitrate with the target.
- The Deliver page now holds the last delivery's settings; your format/codec and render mode are restored.
