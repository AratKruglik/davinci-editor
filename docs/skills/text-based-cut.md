# `text-based-cut`: rough cut ("fish") from the transcript

[← All skills](README.md)

## What it does

Builds the rough cut of a talking-head video, tutorial or podcast from word-level transcripts. It finds failed takes, false starts, repeats, filler sounds, long pauses and dead head/tail, shows you the cut list for approval, then assembles a **new** timeline from the kept ranges on the A-roll and Voice tracks. The source timeline and media are never modified.

Principle: the script proposes, the editor decides. Nothing is cut without your approval.

## When it triggers

Automatically when you ask for a rough cut, the "fish", to remove pauses, filler words or failed takes, or to cut from the transcript. Ukrainian trigger phrases: «зроби рибу», «чорновий монтаж», «виріж паузи і дублі», «прибери слова-паразити», «монтаж за текстом». In `edit-episode` it is stage B, step 3.

Explicit call:

```
/davinci-editor:text-based-cut [bin path] [gentle|normal|tight]
```

| Argument | Meaning | Default |
|---|---|---|
| `scope` | Media Pool bin with the clips, `/`-separated from the root | `footage_bin` (`01_Footage/A-Roll`) |
| `pace` | `gentle`, `normal` or `tight` | `normal` |

Pace presets (pause threshold / handle kept on each side of a cut):

| Pace | Pause threshold | Handle | Use for |
|---|---|---|---|
| `gentle` | 1200 ms | 200 ms | calm lessons, interviews where pauses carry meaning |
| `normal` | `pause_threshold_ms` (700) | `cut_handle_ms` (150) | a regular tutorial |
| `tight` | 450 ms | 80 ms | Shorts and fast videos; too dense for lessons |

A cut pause that follows the end of a sentence keeps 400 ms instead of two handles, so a finished thought still gets its beat. A hard filler glued to words on both sides is not cut automatically: it comes to you as a review item, because there is no pause to cut in.

## Before you start

- Transcripts in `<work_dir>/<project>/transcripts/*.json` in the `uk-transcribe` format. Missing or stale, the skill runs `uk-transcribe` first.
- Optional: your Red / Green / Yellow markers on the Media Pool clips (below).
- With more than one clip, the skill asks the assembly order: by file name (default), by Start TC, or your own list.

## Markers it reads

Your markers outrank every automatic suggestion. Colors come from `marker_colors`.

| Color | Task | Effect |
|---|---|---|
| **Red** | `cut` | a point marker cuts the phrase or take around it (bounds from the transcript); a marker with duration cuts exactly that range |
| **Green** | `keep` | protects the phrase or range; among repeats of a phrase, the Green take wins |
| **Yellow** | `doubt` | Claude proposes options and asks; never decides alone |

Markers are read from the Media Pool clips, or from timeline items if the source is already a timeline. Markers whose `customData` is `claude:done:*` are skipped. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## What it looks for

| Type | What | Default decision |
|---|---|---|
| `head` / `tail` | silence before the first / after the last word | cut |
| `pause` | silence longer than the threshold; handles stay on both sides | cut |
| `filler` | hard fillers from `filler_words` (е, ем, мм…) | cut |
| `soft_filler` | soft fillers from `soft_filler_words` (ну, типу, коротше…) | your review |
| `repeat` | immediately repeated 2–4 words | cut; a single word: review |
| `marker` | your Red or Yellow; Green turns overlapping candidates into `keep` | as marked |
| `retake` | a segment whose opening matches a later one within 45 s (the earlier take); the end of a clip that restarts at the start of the next | review |
| `editorial` | what only Claude sees: an abandoned sentence, "oops, again", talk to the crew, counting in, coughs, laughter breaks | review |

Between two takes, the **last** complete one is kept by default: presenters usually improve.

## Settings

| Key | Default | Effect |
|---|---|---|
| `footage_bin` | `01_Footage/A-Roll` | bin used when `scope` is not given |
| `work_dir` | `resolve-work` | where markers, candidates and the plan are written |
| `marker_colors` | `Red=cut,Green=keep,Yellow=doubt,…` | which colors mean cut / keep / doubt |
| `filler_words` | `е,ее,еее,ем,…` | hard fillers, always proposed for cutting |
| `soft_filler_words` | `ну,типу,коротше,…` | soft fillers, only flagged |
| `pause_threshold_ms` | `700` | pause threshold of the `normal` pace |
| `cut_handle_ms` | `150` | handle of the `normal` pace |
| `split_j_lead_frames`, `split_l_tail_frames`, `split_max_frames`, `split_fade_frames`, `split_max_in_row` | `12`, `12`, `50`, `4`, `3` | J/L cuts at joins between different clips (`split-edits` mode 1) |

Any setting can be overridden in the prompt: "pause threshold 500 ms", "cut the soft fillers too".

## Files

All under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `transcripts/*.json`, `*.txt` | input from `uk-transcribe` |
| `markers.json` | your Red / Green / Yellow markers |
| `cuts.json` | every candidate with its `cut` / `keep` decision |
| `plan.json` | kept ranges in assembly order |
| `clip-frames.json`, `split-plan.json`, `split-audio.json` | only when J/L cuts at clip changes are proposed |

## Workflow and approval stops

1. Reads your markers and the transcripts, computes mechanical candidates (`cut_candidates.py analyze`).
2. Adds editorial candidates a script can't see.
3. **Approval 1: the cut list.** Your marker decisions first (already decided, shown for transparency; conflicts like Red inside Green become questions), then groups by type with counts and time saved, then every review item with its id, timecode and text in context. Answer in one message: "keep 12 and 15, cut the rest". Nothing may stay undecided.
4. Builds the plan and shows the duration before → after.
5. **Approval 2: J/L cuts**, only if neighbouring segments come from different clips or takes.
6. Creates the new timeline `<source name> - rough cut <date>` (` v2` if the name is taken), lays out the tracks with `track-layout`, puts video on A-roll and audio on Voice, and links each pair.
7. Verifies the item count, every item's length and the timeline end. Mismatches are reported with their id, never nudged silently.
8. At every join adds a **Cream** marker named `cut` with the removed text in the note (a split join gets a `J` / `L` marker instead).
9. Adds 2-frame audio crossfades at the joins against clicks, unless you said no.
10. Checks the grade (remote version `claude`) came along, marks handled markers in `customData`, recolors clips by role and saves the project.

## What it never does

- Modify or delete the source timeline or media.
- Assemble with undecided candidates or without your approval.
- Cut words you asked to keep "because the script said so".
- Change the color, name or note of your markers (it writes only the hidden `customData`).

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## Place in the workflow

`uk-transcribe` → `track-layout` → **`text-based-cut`** → `dual-video-sync-pip` → `marker-edit` (Fuchsia, Cocoa) → `split-edits`

Next: review at the Cream markers, then `voice-isolation`, sound design; [`jump-cuts`](jump-cuts.md) for the joins that show.

## Example prompts

**Minimal:**

> Make the rough cut.

**With arguments:**

```
/davinci-editor:text-based-cut 01_Footage/A-Roll gentle
```

**Overriding a setting:**

> Rough cut from the bin `Footage/Cam A`, pace normal, but pause threshold 900 ms: this lesson has a lot of on-screen demos and the pauses are needed.

**Professional brief:**

> Rough cut of the two lesson clips IMG_4127 and IMG_4128, assembled in file-name order. Pace normal. My Red and Green markers are already on the clips and they take priority. Cut the hard fillers; list "ну" and "типу" for me, they are often part of my intonation. Between takes keep the last complete one, except the DNS settings phrase: the first take is better there and has a Green marker. Don't cut the pauses after "so" and after showing the result on screen, they are beats. Add 2-frame crossfades at the joins. At the end show the duration before and after and how much was cut by type.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Cut the video" | "Rough cut from the A-Roll bin, pace gentle: it's an interview, leave pauses under a second alone. Cut coughs and talk to the camera operator, list the soft fillers for me." |

The strong prompt names the material, pace and genre, says what to protect and what you decide yourself, so the approval list comes out short and precise.

## What to check afterwards

- Step through the Cream `cut` markers: is the attack of the first word after a join intact, is the meaning intact?
- Listen to the joins on headphones for clicks (if you skipped the crossfades).
- Make sure every clip still has its grade.
- When you're done reviewing, ask Claude to remove all Cream markers at once (`DeleteMarkersByColor("Cream")`); this is Claude's own scratch work, so the delete guard lets it through without a prompt.
