# `uk-transcribe`: word-level transcripts with Resolve's AI transcription

[← All skills](README.md)

## What it does

Transcribes clips with DaVinci Resolve 21+ built-in AI transcription, in Ukrainian or the configured language, optionally with speaker detection. It waits for the background job and verifies the language Resolve actually used. Then it exports word-level timecodes to JSON, SRT and plain text. These files are the input for text-based editing, subtitles and chapters. On Resolve 21.1.2 Studio it can also write the term and name fixes you approve back into Resolve's own transcript.

Principle: verify, don't trust. Without the extended language models Resolve silently falls back to a built-in model, so every clip's detected language is checked.

## When it triggers

Automatically when you need a transcript, word timings, a source for subtitles or the text of the footage for the "fish". It is also the first step before `text-based-cut`. Ukrainian trigger phrases: «транскрибуй», «розшифруй відео», «зроби транскрипт», «текст з відео». English ones: "transcribe", "speaker detection". In `edit-episode` it is stage B, step 1.

Explicit call:

```
/davinci-editor:uk-transcribe [bin path | selected] [--speakers]
```

| Argument | Meaning | Default |
|---|---|---|
| `scope` | Media Pool bin, `/`-separated from the root, or `selected` for the selected clips | `footage_bin` (`01_Footage/A-Roll`) |
| `speakers` | `--speakers` turns on speaker detection (interviews, podcasts) | `speaker_detection` (`false`) |

## Before you start

- Ukrainian exists only in Resolve's **extended** language models: Resolve menu → Extras Download Manager. Without them the extended model can't be switched on or a clip comes back in another language, and the skill stops and tells you what to download.
- Clips that already have a transcript in this language are skipped. Re-transcribing destroys manual corrections made in Resolve, so Claude asks before clearing one. To redo a clip, say so.

## Language check

1. Ukrainian on Resolve 21.1.2+: Claude first switches on the extended language model (`transcriptionExtendedLanguageSupport` = `1`), then sets the language to `uk`, and reads both back. The order matters: switching the extended model resets the language to `auto`, and `auto` misdetects short Ukrainian clips (2 s came back as Spanish). If the extended model doesn't switch on, it stops and points you to the Extras Download Manager.
2. Other languages or older Resolve: Claude sets the project's transcription language to `transcription_language` and reads it back. If the value didn't stick, it asks you to pick the language once in Resolve (Project Settings → General Options → transcription language, or the transcription dialog). It reads the accepted code back and tells you to put that code in the plugin config.
3. After the job, the `language` field of every clip must match the configured language. A mismatch means the extended models are missing: Claude names the clip, tells you what to download, and stops.
4. Claude reads 2–3 paragraphs of the `.txt` and flags systematic errors: technical terms, names, English words in Ukrainian speech. If key terms are often wrong, it tells you. The fallback is Whisper, but nothing is installed without asking.

## Settings

| Key | Default | Effect |
|---|---|---|
| `footage_bin` | `01_Footage/A-Roll` | bin used when `scope` is not given |
| `transcription_language` | `uk` | language code for Resolve's transcription (project setting) |
| `speaker_detection` | `false` | detect speakers when `--speakers` is not given |
| `work_dir` | `resolve-work` | where transcripts are written |
| `subtitle_max_chars` | `42` | line length of the review SRT |

Any setting can be overridden in the prompt: "transcribe in English", "with speaker detection, it's an interview".

## Files

All under `<work_dir>/<project>/transcripts/`, one set per clip:

| File | Contents |
|---|---|
| `<clip>.json` | the full Resolve transcription with word timecodes, plus clip name and id, file path, fps, Start TC, drop frame. This is the format `text-based-cut` and later skills read |
| `<clip>.srt` | segment-level subtitles, at most `subtitle_max_chars` characters per line (42), 2 lines; a longer segment is split into several cues |
| `<clip>.txt` | timecoded paragraphs, with speakers if detected |
| `<clip>.before-fix.json` | only after a write-back: Resolve's transcript before the fixes, to undo them |

## Workflow and approval stops

1. Reads the project's transcription language and speaker detection, sets them and reads them back (see "Language check"). If the code doesn't stick, **it stops for you to pick the language in Resolve.**
2. Chooses the video and audio clips in scope and skips the ones already transcribed in this language. **Asks before clearing** a transcript you want redone.
3. Starts the transcription for the whole bin or for each selected clip. It runs as a background job, and Claude polls it with short separate calls and tells you the progress. Expect roughly real time / 5–10 on Apple Silicon. `Cancelled` or `Error` is reported and the skill stops.
4. Exports each clip's transcription to JSON, then builds the `.srt` and `.txt` next to it (`transcript_export.py`). The script prints the detected language per clip.
5. Checks quality: language per clip, then a read of the text for systematic recognition errors.
6. **Optional write-back (21.1.2 Studio), after you approve it:** the fixes you approved for names and terms are written into Resolve's own transcript (`SetTranscription`), so Resolve's text-based editing and every later export carry them. The transcript as it was is saved first as `<clip>.before-fix.json`, then the clip is exported again.
7. Reports the clips transcribed, detected language, total duration, speakers found, output folder, notable recognition problems and fixes written back. Next step: `text-based-cut`.

Any script that deletes or resets something, such as clearing a transcript, becomes a permission prompt (the `guard.py` hook), so read what you approve.

## What it never does

- Re-transcribe, clear or overwrite a clip's existing transcript without asking: that destroys manual corrections made in Resolve.
- Continue with a clip whose detected language doesn't match the configured one.
- Install Whisper or anything else without asking.
- Write into the media folders: outputs go only to `<work_dir>/<project>/transcripts/`.

## Place in the workflow

**`uk-transcribe`** → `track-layout` → `text-based-cut` → `dual-video-sync-pip` → `marker-edit` (Fuchsia, Cocoa) → `split-edits`

Its transcripts are reused later: `text-based-cut` cuts from them, `split-edits` checks joins against them. Subtitles, chapters, Shorts and thumbnails map their words onto the cut timeline.

## Example prompts

**Minimal:**

> Transcribe the footage.

**With arguments:**

```
/davinci-editor:uk-transcribe 01_Footage/Interview --speakers
```

**Overriding a setting:**

> Transcribe the selected clips in English, language code `en`: this episode is recorded for the English channel.

**Professional brief:**

> Transcribe the A-Roll bin for the router setup lesson, Ukrainian, no speaker detection: it's just me on camera. IMG_4127 already has a transcript I corrected by hand in Resolve, so don't touch it. Export JSON, SRT and text. Then check the language of every clip, and read a few paragraphs for brand names and English terms (router models, "DHCP", "Wi-Fi 6"). Tell me which ones Resolve gets wrong systematically. Report total duration and the output folder.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Get the text" | "Transcription in Resolve has already finished. Export the transcripts to SRT and text for me and check that everything was recognized properly." |

The strong prompt says what state the job is in and asks for the language and quality check, so a clip that silently fell back to the wrong model is caught before the rough cut.

## What to check afterwards

- The report lists the same language for every clip. A clip in another language needs the extended models and a redo.
- Read a few paragraphs of the `.txt`: names and technical terms recognized?
- Words like `(...)` are Resolve's silence markers, not errors.
- With speaker detection: are the speakers in the `.txt` split where you expect?
