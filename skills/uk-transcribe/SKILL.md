---
name: uk-transcribe
description: Transcribes clips with DaVinci Resolve 21+ built-in AI transcription in Ukrainian (or the configured language), optionally with speaker detection, waits for the background job, verifies the language actually used, and exports word-level timecodes to JSON, SRT and plain text for text-based editing, subtitles and chapters.
when_to_use: User needs a transcript, word timings, subtitles source or a "fish" text of the footage; also the first step before text-based-cut. Triggers - "транскрибуй", "розшифруй відео", "зроби транскрипт", "текст з відео", "transcribe", "speaker detection".
argument-hint: "[bin path | selected] [--speakers]"
arguments: [scope, speakers]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_docs"
  - "Bash(python3 *transcript_export.py *)"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Transcription in DaVinci Resolve

Follow `resolve-core` first. Scope: `$scope` (default bin `${user_config.footage_bin}`). Language: `${user_config.transcription_language}`. Speaker detection: `$speakers` or `${user_config.speaker_detection}`.

## 1. Language setup (verify, don't trust)

1. Read `s = project.GetSettings()`; note `s["transcriptionLanguage"]` and `s["speakerDetection"]`.
2. `project.SetSettings({"transcriptionLanguage": CODE})` and re-read with `GetSettings()`. If the value did not stick, find the accepted code: ask the user to pick the language once in Resolve (Project Settings → General Options → transcription language, or the transcription dialog) and read it back with `GetSettings()`. Tell the user to put that code in the plugin config.
3. Ukrainian may need the **extended** language models (Resolve menu → Extras Download Manager). Without them Resolve silently falls back to a built-in model — this is why step 4.3 checks the result language.
4. Speaker detection: `project.SetSettings({"speakerDetection": "1"})` if requested; also pass `useSpeakerDetection=True` below.

## 2. Choose clips

Video/audio media pool items in scope. Skip clips that already have a transcript in this language (`GetTranscription()` non-empty and `language` matches) unless the user asks to redo — re-transcribing destroys manual corrections made in Resolve; ask before `ClearTranscription()`.

## 3. Run

- Whole bin: `folder.TranscribeAudio(useSpeakerDetection)`; selected clips: `clip.TranscribeAudio(useSpeakerDetection)` for each.
- It runs as a background job. Poll with **separate short calls**: `project.GetTranscribeAudioStatus()` → `JobStatus`, `CompletionPercentage`, `CurrentClipIndex/TotalClips`, `EstimatedTimeRemaining`, `Error`. Don't sleep inside scripts; between polls tell the user the progress. Expect roughly real-time / 5–10 on Apple Silicon.
- `Cancelled` or `Error` → report and stop.

## 4. Export

With `run_script_unsafe`, for each clip write `work/transcripts/<clip name>.json` (`work` = `${user_config.work_dir}/<project name>`):

```python
import json, os
os.makedirs(OUT, exist_ok=True)
for c in clips:
    t, p = c.GetTranscription(), c.GetClipProperty()
    data = {"clip_name": c.GetName(), "clip_id": c.GetUniqueId(), "file_path": p["File Path"],
            "fps": float(p["FPS"]), "start_tc": p["Start TC"], "drop_frame": p.get("Drop frame") == "1", "transcription": t}
    with open(os.path.join(OUT, c.GetName() + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
```

Then build readable outputs locally:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/transcript_export.py "<work>/transcripts"
```

It writes `<clip>.srt` (segment-level, max 42 chars/line, 2 lines) and `<clip>.txt` (timecoded paragraphs, speakers if present) next to each JSON and prints a summary with the detected language per clip.

## 5. Check quality

1. The `language` field must match the configured language for every clip. If not, extended models are missing: tell the user what to download and stop.
2. Read 2–3 paragraphs of the `.txt` and flag systematic errors: technical terms, names, English words in Ukrainian speech. If errors are frequent on key terms, tell the user; the plan's fallback is Whisper, but don't install anything without asking.
3. Words like `(...)` are Resolve's silence markers, not errors.

## 6. Report

Clips transcribed, language detected, total duration, speakers found, output folder, notable recognition problems. Next step: `text-based-cut`.
