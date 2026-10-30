# `marker-edit`: edit by your colored markers

[← All skills](README.md)

## What it does

Reads the markers you put on footage or a timeline while watching, treats each marker's **color as the task type**, its **name as the content** (title text, chapter name) and its **note as a free instruction** in Ukrainian. It builds one action plan for approval, then hands each task to the skill that does that work. B-roll inserts (Fuchsia) and transitions (Cocoa) it does itself. Progress is written into the markers' hidden `customData`, so a re-run never does a task twice.

Markers are read the way a human assistant editor would read them: no strict syntax, and an unclear note becomes a question, not a guess.

## When it triggers

Automatically when you have put markers on footage or a timeline and want Claude to act on them, or ask what the markers say. Ukrainian trigger phrases: «зроби по маркерах», «пройдись по моїх маркерах», «що там у маркерах», «виконай маркери», «монтаж за маркерами». In `edit-episode` it opens every stage, limited to that stage's colors, and runs again in stage B, step 6, for Fuchsia and Cocoa on the cut timeline.

Explicit call:

```
/davinci-editor:marker-edit [stage A|B|C|D] [timeline name]
```

| Argument | Meaning | Default |
|---|---|---|
| `stage` | only the colors of this stage (A, B, C or D, see the table below) | empty = all active colors |
| `timeline` | timeline to read and work on | the current timeline |

## Before you start

- Markers placed in Resolve. Before the cut (stages A and B) put them on the Media Pool clips; after the cut (sound, graphics, Shorts) on the timeline. Claude reads both.
- A point marker means "Claude finds the bounds" (from the transcript for Red and Green); a marker with duration means "exactly this range".
- Point Red / Green markers get their bounds from the transcript (`uk-transcribe`). Fuchsia, Cocoa, Cyan, Pink, Blue, Mint and Lemon are done on the cut timeline, so they need the rough cut first.

## Markers it reads

All of them. It reads markers on three levels: Media Pool clips in the `footage_bin` bin (and any bins you name), the timeline itself, and the video and audio items on the timeline. Colors come from `marker_colors`. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

| Color | Task | Point marker | Marker with duration | Skill | Stage |
|---|---|---|---|---|---|
| **Red** | cut | the phrase / take around it (bounds from the transcript) | exactly this range | `text-based-cut` | B |
| **Green** | keep / best take | protects the phrase around it; among repeats this take wins | protects this range | `text-based-cut` | B |
| **Yellow** | doubt | Claude proposes options and asks, never decides | same | `text-based-cut` | B |
| **Sand** | ColorChecker frame | the frame to measure | — | `chart-match` | A |
| **Purple** | camera / screen / PiP switch (name: `камера` camera, `екран` screen or `pip`) | until the next Purple | this range | `dual-video-sync-pip` | B |
| **Fuchsia** | insert B-roll (note: what) | Claude picks the duration | insert duration | `marker-edit` itself | B |
| **Cocoa** | transition (note: type or MotionVFX name); note `J` / `L` / `split` (+ frames) = split edit | — | — | `marker-edit` itself + `motionvfx-catalog`; split notes → `split-edits` | B |
| **Blue** | chapter start (name = chapter title) | — | — | `chapters-markers` | D |
| **Cyan** | title on screen (name = text) | default duration | title duration | `fusion-motion-graphics`, `motionvfx-catalog` | D |
| **Pink** | zoom (note: area, strength) | short zoom | zoom duration | `tutorial-zooms` | D |
| **Lavender** | SFX (note: which sound) | the sound moment | a long sound | `sound-design` | C |
| **Sky** | music start / mood change / end | the change point | the music range | `sound-design` | C |
| **Rose** | audio problem (note: what) | Claude finds the bounds | this range | `audio-finish`, `voice-isolation` | C |
| **Mint** | Shorts candidate | Claude picks 30–60 s | exactly this range | `shorts-cutdown` | D |
| **Lemon** | thumbnail frame | this frame | — | `thumbnail-frames` | D |
| **Cream** | **Claude's own markers only** (suggestions, problems, questions) | | | | always |

Skipped: markers whose `customData` is already `claude:done:*`, Cream markers, and colors whose skill is not available (listed separately as "waiting for their skill").

## How tasks are dispatched

- **Red / Green / Yellow** go to `text-based-cut` as your decisions (Red = forced cut, Green = protected keep / preferred take, Yellow = must ask), in one run for all of them. Red ranges are cut even if the transcript analysis would keep them (still shown in the plan).
- **Sand** goes to `chart-match` with the marker's clip and frame as the chart frame.
- **Purple** goes to `dual-video-sync-pip`; the marker name is the mode.
- **Lavender** and **Sky** go to `sound-design` as fixed cues. **Rose** goes to `audio-finish`; notes about noise go to `voice-isolation` first.
- **Cyan** → `fusion-motion-graphics` (name = text, note = kind or MotionVFX template); **Pink** → `tutorial-zooms` (note = area, strength); **Blue** → `chapters-markers`; **Mint** → `shorts-cutdown`; **Lemon** → `thumbnail-frames`. These work on the cut timeline. Blue / Mint / Lemon markers left on Media Pool clips before the cut are mapped onto the cut; a marker whose moment was cut out is reported, not moved.
- **Cocoa** with a note starting `J`, `L` or `split` → `split-edits`, all in one run, after the transitions below.

## B-roll inserts and transitions (done here)

Done after the rough cut, on the cut timeline, after a backup of it.

- **Fuchsia (B-roll insert):** finds the clip from the note in `01_Footage/B-Roll` (by file name, or by matching the description against clip names and, if transcribed, their transcripts). Several candidates or none: it asks. The clip goes on the `B-roll` track at the marker frame (a second overlapping insert goes to `B-roll 2`), video only, so the voice continues underneath. Length: the marker duration, or 3–5 s for a point marker, ending in a speech pause if possible.
- **Cocoa (transition):** on the cut nearest the marker on A-roll / B-roll / Screen. The transition name from the note is looked up in the MotionVFX catalog (no catalog yet: `motionvfx-catalog` runs first); no name means `Cross Dissolve`. Length 10–20 frames, on the outgoing clip. If a clip has too little handle, it tells you and never trims clips to make room.

## Settings

| Key | Default | Effect |
|---|---|---|
| `marker_colors` | `Red=cut,Green=keep,Yellow=doubt,Sand=chart,…,Cream=claude` | which color means which task |
| `footage_bin` | `01_Footage/A-Roll` | the Media Pool bin whose clip markers are read |

Any setting can be overridden in the prompt: "also read the markers in the `Footage/Cam B` bin".

## Files

It writes no files of its own. Progress lives in each handled marker's `customData` (`claude:done:<skill>:<date>` or `claude:skipped:<reason>`); the dispatched skills write their usual files.

## Workflow and approval stops

1. Reads markers on all three levels and converts their frames to timecode so you can find them.
2. Drops done, Cream and not-yet-supported markers.
3. Resolves point-marker bounds that depend on the transcript (Red / Green: the sentence or take around the frame, with the words shown) and flags conflicts: Red inside Green, two Greens on different takes of the same phrase, a Sand marker on a clip that isn't Apple Log.
4. **Approval: the action plan.** One table, grouped by skill, in time order: `# | Where (clip/timeline @ TC) | Color | Name / note | What Claude will do | Skill`. Approve it as a whole or exclude rows by number: "everything except 4 and 9".
5. Dispatches the approved rows to their skills (each with its own approvals) and does the Fuchsia and Cocoa rows itself. Work happens on a copy or new timeline per those skills; the original timeline stays untouched.
6. After each skill reports success, writes `claude:done:<skill>:<date>` to the handled markers and re-reads it. Adds Cream markers wherever something needs your eye, with the reason in the note.
7. Reports: handled per color, skipped and why, waiting for future skills, open questions.

## What it never does

- Change the color, name, note, position or duration of your markers, or delete one. The only field it writes is `customData`, and only when it is empty or already starts with `claude:`.
- Do a task twice: `claude:done:*` markers are skipped.
- Use any color but Cream for its own markers, or put a Cream marker where it hides one of yours at the same frame (it moves one frame instead).
- Cut a Green range.
- Guess an unclear note: it asks.

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## Place in the workflow

The dispatcher of the whole pipeline. In `edit-episode` it opens each stage with that stage's colors:

A (Sand) → B (Red, Green, Yellow, Purple, Fuchsia, Cocoa) → C (Lavender, Sky, Rose) → D (Cyan, Pink, Blue, Mint, Lemon)

Within stage B it runs twice: before `text-based-cut` for the cut decisions, and after the cut for Fuchsia and Cocoa, before `split-edits`.

## Example prompts

**Minimal:**

> Go through my markers.

**With arguments:**

```
/davinci-editor:marker-edit C "Router Setup - rough cut 2026-11-02"
```

**Overriding a setting:**

> Do the markers, but in my project Lemon means a Shorts candidate and Mint means a thumbnail frame. Also read the clip markers in the `Footage/Cam B` bin, not only A-Roll.

**Professional brief:**

> Stage B markers on the current rough cut timeline only: Fuchsia and Cocoa. The B-roll is in `01_Footage/B-Roll`; for the Fuchsia "router close-up" there are two candidate clips, show me both before inserting. Cocoa markers with a MotionVFX name: use that transition; the rest Cross Dissolve. If any clip lacks handle for a transition, list it, don't trim anything. Leave the Cocoa `J`/`L` markers for `split-edits`. Report what was done per color and every Cream marker you added.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Do something with the markers" | "Stage D markers on timeline `Episode 12 - rough cut`: show the plan first, I'll exclude rows. Cyan names are the exact title text; Pink notes say the screen area." |

The strong prompt limits the colors to one stage, names the timeline and tells how to read names and notes, so the plan comes out short and nothing is dispatched by mistake.

## What to check afterwards

- Read the report's "skipped" and "waiting" lists: those markers did nothing.
- Step through the new Cream markers: each one is a question or a problem with its reason in the note.
- Watch every inserted B-roll and every transition in context.
- Your markers keep their color, name and note; only the hidden `customData` changed. All Cream markers can be removed at once with `DeleteMarkersByColor("Cream")` (Claude asks permission).
