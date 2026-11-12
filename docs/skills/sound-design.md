# `sound-design`: music, SFX and ambience for the cut

[← All skills](README.md)

## What it does

Adds sound design to a cut timeline. It reads the transcript, the timeline structure and your Lavender (SFX) and Sky (music) markers, proposes a cue sheet (time, sound, music mood per section) for approval, picks files from **your own** indexed SFX and music library, checks that each music source is cleared for YouTube Content ID, and places the sounds on the SFX, Music and Ambience tracks with base levels and fades.

Principle: sound supports the speech, never competes with it. A tutorial with a whoosh on every jump cut sounds cheap; a well-chosen bed and a few accents sound expensive.

## When it triggers

Automatically when you want sound effects, background music, whooshes on titles and transitions, ambience or a music bed for a cut, or when there are Lavender or Sky markers. Ukrainian trigger phrases: «саунд-дизайн», «додай музику», «підбери звуки», «звуки на переходи», «фонова музика», «атмосфера». In `edit-episode` it is stage C, step 2, after `voice-isolation`.

Explicit call:

```
/davinci-editor:sound-design [timeline] [subtle|normal|rich]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | the cut timeline to work on | the current timeline |
| `density` | `subtle`, `normal` or `rich` | `normal` |

Density sets the average SFX rate (Lavender markers don't count toward it):

| Density | SFX on average |
|---|---|
| `subtle` | about 1 per 30 s |
| `normal` | about 1 per 15 s |
| `rich` | about 1 per 8 s |

## Before you start

- A sound library on disk: set `sfx_library_dir` and `music_library_dir`. If they are empty, Claude asks for the folders and suggests saving them in the plugin config. With no library at all it stops: it never downloads sounds or music without your go-ahead.
- Transcripts in `<work_dir>/<project>/transcripts/*.txt` (from `uk-transcribe`).
- Optional: your Lavender and Sky markers on the timeline or clips.

## Markers it reads

Your markers are decisions, not suggestions: their cues come first in the cue sheet.

| Color | Task | Effect |
|---|---|---|
| **Lavender** | SFX | the note says which sound; a point marker is the sound moment, a marker with duration a long sound |
| **Sky** | music | start, mood change or end; the note says the mood; Sky markers define the music sections |

It also uses Blue markers (chapters) as music sections when there are no Sky markers. Cream `cut` markers (jump cuts) are not sound moments by themselves. Handled Lavender and Sky markers are marked `claude:done:sound-design:<date>`. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## Library and licenses

**Indexing.** `sound_library.py index` scans both library folders and writes `sound-library.json`. It runs the first time, after you add sounds, or when the index is older than the library. The files themselves are never modified or copied. Tags come from folder and file names (`Whooshes/Fast/whoosh_air_01.wav` → whooshes, fast, whoosh, air), so name your folders well; tags are mostly English and Claude translates the mood itself. A `source` is the first folder under each library root (a vendor or pack), and a `LICENSE` / `README` / `terms` file found there is shown as that source's license.

**One-time license confirmation.** Music on YouTube can trigger Content ID claims even when it's licensed. So for every music source not yet in `sound-licenses.json`, Claude asks you **once** whether it's cleared for your monetized channel, showing the license file path. Your answer is stored per source (`ok`, `no` or `ask`) and shown at the start of every later run, so you are not asked again. Music from a `no` or unknown source is never placed. SFX packs are asked about only if their license file says something unusual.

## What it proposes

- **Music:** one cue per section. Sections come from Sky markers, else chapters (Blue), else intro / body / outro. Mood from what is said (calm explanation, building tension before a reveal, upbeat result, outro). Instrumental tracks without vocals under speech, steady tempo, changes only at section borders. A track shorter than its section is allowed (it ends with a fade), but Claude says so and suggests a longer one if there is.
- **SFX:** a soft whoosh or pop 2–4 frames **before** a title or callout appears; a whoosh or riser into transitions between sections; a subtle hit or shimmer on reveals and results; light clicks on UI demos only if the screen recording is silent.
- **Ambience:** only when the picture is outdoors or a B-roll place needs air (room tone under a silent B-roll).
- **Never:** SFX on dense explanation, on every jump cut, or two sounds within 1 s.

## Levels and fades

| Material | Level |
|---|---|
| music under speech | `music_bed_lufs` (-30 LUFS) |
| music without speech (intro, outro, pauses over 3 s) | `music_solo_lufs` (-20 LUFS) |
| SFX | sample peak `sfx_peak_db` (-12 dBFS) |

A music cue is measured once as a whole, then split at speech borders into separate items: the parts under speech keep that level and the parts without speech get a fixed step up (`music_solo_lufs` − `music_bed_lufs`, 10 dB by default). This is the ducking, because Resolve's API has no volume keyframes, and it keeps the track's own dynamics. Music gets a 1 s fade-in at its start and a 2 s fade-out at its end; at the internal level changes the parts are joined with an 8–12-frame crossfade, never a fade-out next to a fade-in, which would leave a hole. If this Resolve build has no LUFS normalization mode, Claude sets an estimated volume instead and tells you.

## Settings

| Key | Default | Effect |
|---|---|---|
| `sfx_library_dir` | — | sound effects folder to index |
| `music_library_dir` | — | licensed music folder to index |
| `work_dir` | `resolve-work` | where the library index, license answers and cue sheet are written |
| `music_bed_lufs` | `-30` | loudness of music under speech |
| `music_solo_lufs` | `-20` | loudness of music without speech |
| `sfx_peak_db` | `-12` | sample peak SFX are normalized to |

Any setting can be overridden in the prompt: "music under speech at -32 LUFS".

## Files

| File | Contents |
|---|---|
| `<work_dir>/sound-library.json` | the index of both libraries (shared by all projects) |
| `<work_dir>/sound-licenses.json` | your answer per music source: `ok`, `no` or `ask` (shared by all projects) |
| `<work_dir>/<project>/transcripts/*.txt` | input from `uk-transcribe` |
| `<work_dir>/<project>/cues.json` | the cue sheet: time, kind, what / mood, reason, marker or Claude, candidates, choice |

Chosen files are imported once into the `02_Sound/SFX` or `02_Sound/Music` bin; nothing is copied.

## Workflow and approval stops

1. Indexes the library if needed.
2. **License question**, once per new music source.
3. Reads the transcript, the structure (length, chapters, titles, transitions, B-roll and Screen inserts) and your markers.
4. Builds the cue sheet and picks 2–3 candidates per cue from the index.
5. **Approval: the cue sheet.** One table: `# | TC | kind | what / mood | reason | file (candidate 1) | alternatives`, your marker cues first. Answer in one round: "drop 12, take the second option for 5". Nothing is placed before your yes.
6. Places the cues: tracks by role (`SFX`, `Music`, `Ambience` if needed; an overlapping cue goes to `SFX 2` / `Music 2`), locks A-roll and Voice for the stage if `edit-episode` hasn't, sets levels and fades and reads them back, recolors by role, saves.
7. Checks that the count per track matches the approved cues and every item sits at its cue frame.
8. **Listening check:** asks you to listen to three spots (the first title whoosh, a music change, the outro) and offers ±3 dB for music and SFX as a whole.
9. Reports cues placed and skipped, files and their sources, any music shorter than its section, and what `audio-finish` does next.

## What it never does

- Place music whose source isn't cleared in `sound-licenses.json`.
- Put SFX or music on the Voice or A-roll tracks, or change Voice items.
- Download or generate sounds without asking.

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## Place in the workflow

`voice-isolation` → **`sound-design`** → `audio-finish`

Next: `audio-finish` does the final loudness, peak check and fine ducking.

## Example prompts

**Minimal:**

> Do the sound design for the rough cut: music and a few sounds, nothing over the top.

**With arguments:**

```
/davinci-editor:sound-design "Router Setup - rough cut 2026-11-02" subtle
```

**Overriding a setting:**

> Sound design, density normal, but the music under speech at -33 LUFS instead of -30: my voice is soft and the bed keeps competing with it.

**Professional brief:**

> Sound design for the router setup tutorial, density subtle. My Lavender and Sky markers are on the timeline and are fixed. Music: calm instrumental in the body, something more upbeat for the result at the end; no vocals under speech. Whooshes only on the section titles, no sounds on jump cuts. The "YouTube Audio Library" folder is cleared for my channel; anything else, ask me. If a track is shorter than its section, tell me. Report the cues with file names and sources.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Add some music" | "Sound design, subtle: one calm bed for the explanation, an upbeat change at the Sky marker before the result, a soft whoosh before each section title, nothing on jump cuts." |

The strong prompt sets density, mood per section and where accents go, so the cue sheet needs few edits.

## What to check afterwards

- Listen to the first title whoosh, a music change and the outro: is the music under the voice, are the level steps at speech borders smooth?
- Every music file's source is one you cleared.
- A-roll and Voice are untouched.
- Then run `audio-finish` for the final loudness.
