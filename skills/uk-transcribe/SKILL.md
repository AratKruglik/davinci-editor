---
name: uk-transcribe
description: Transcribes clips with DaVinci Resolve 21+ built-in AI transcription in Ukrainian (or the configured language), optionally with speaker detection, waits for the background job, verifies the language actually used, exports word-level timecodes to JSON, SRT and plain text for text-based editing, subtitles and chapters, and (21.1.2 Studio) can write approved term fixes back into Resolve's transcript.
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

1. Read `s = project.GetSettings()`; note `s["transcriptionLanguage"]`, `s["transcriptionExtendedLanguageSupport"]` and `s["speakerDetection"]`.
2. **Ukrainian (`uk`) on 21.1.2+** (`resolve-core` §10 gate): Ukrainian exists only in the extended model, and changing the extended switch resets the language to `auto`, so the order is fixed:
   ```python
   project.SetSettings({"transcriptionExtendedLanguageSupport": "1"})
   project.SetSettings({"transcriptionLanguage": "uk"})
   s = project.GetSettings()   # both must read back: "1" and "uk"
   ```
   Extended doesn't read back `"1"` → the extended models are likely not installed: stop and tell the user to install them (Resolve menu → Extras Download Manager), then run again. Never transcribe Ukrainian on `auto`: 2 s of Ukrainian came back as `es`.
3. Other languages, or Resolve before 21.1.2: `project.SetSettings({"transcriptionLanguage": CODE})` and re-read with `GetSettings()`. If the value did not stick, find the accepted code: ask the user to pick the language once in Resolve (Project Settings → General Options → transcription language, or the transcription dialog) and read it back with `GetSettings()`. Tell the user to put that code in the plugin config.
4. Even with the settings right, a missing Extras package can make Resolve fall back silently: this is why step 5.1 checks the result language.
5. Speaker detection: `project.SetSettings({"speakerDetection": "1"})` if requested; also pass `useSpeakerDetection=True` below.

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
python3 ${CLAUDE_SKILL_DIR}/scripts/transcript_export.py "<work>/transcripts" --max-chars ${user_config.subtitle_max_chars}
```

It writes `<clip>.srt` (segment-level, max `subtitle_max_chars` per line, 2 lines; a longer segment is split into several cues) and `<clip>.txt` (timecoded paragraphs, speakers if present) next to each JSON and prints a summary with the detected language per clip.

## 5. Check quality

1. The `language` field must match the configured language for every clip. If not, extended models are missing: tell the user what to download (Extras Download Manager) and stop.
2. Read 2–3 paragraphs of the `.txt` and flag systematic errors: technical terms, names, English words in Ukrainian speech. If errors are frequent on key terms, tell the user; the plan's fallback is Whisper, but don't install anything without asking.
3. Words like `(...)` are Resolve's silence markers, not errors.

## 6. Write fixes back (optional, 21.1.2 Studio)

When the user approved fixes to recognition errors (names, terms from step 5.2), offer to write them into Resolve's own transcript, so Resolve's text-based editing and every later export carry them. Gate: `resolve-core` §10 and `hasattr(clip, "SetTranscription")`; otherwise the fixes live only in the exported files. Ask first: this replaces the clip's transcript in Resolve.

```python
FIXES = {"вайфай": "Wi-Fi"}     # the approved {recognized word: fix}
t = clip.GetTranscription()   # fresh from Resolve, not the export: the user may have corrected it since
# save t as <work>/transcripts/<clip>.before-fix.json first (run_script_unsafe)
segs = []
for seg in t["segments"]:
    words = [{"text": " " + FIXES.get(w["text"].strip(), w["text"].strip()), "start": w["start"], "end": w["end"]}
             for w in seg["words"] if w["text"].strip() != "(...)"]   # Resolve derives silence itself
    if words:
        segs.append({"start": seg["start"], "end": seg["end"], "words": words, **({"speaker": seg["speaker"]} if seg.get("speaker") else {})})
ok = clip.SetTranscription({"language": t["language"], "segments": segs})
```

Every word gets a leading space like Resolve's own (`" слово"`): Resolve builds `segment.text` by plain concatenation, so words without it run together. A fix that splits or merges words: edit that segment's `words` list; a word without `start`/`end` is interpolated. Then re-read `GetTranscription()` (language, the fixed words, segment count) and export again (step 4) so JSON, SRT and TXT match Resolve. To undo, write the `.before-fix.json` transcript back the same way.

## 7. Report

Clips transcribed, language detected, total duration, speakers found, output folder, notable recognition problems, fixes written back (if any). Next step: `text-based-cut`.
