# `tutorial-zooms`: zooms on the screen recording and punch-ins over jump cuts

[← All skills](README.md)

## What it does

Two jobs for video tutorials:

- **`screen`**: eased push-ins onto the part of a screen recording being talked about (a button, a code line, a terminal), driven by your Pink markers. The region is read off an exported still, and the zoom is keyframed in a Fusion Transform inside the clip, so the frame never shows black edges and zooms that follow each other closely pan from one spot to the next instead of bouncing out and in.
- **`punch-in`**: static punch-ins on alternate A-roll segments of a talking head to hide jump cuts.

Principle: a zoom answers "where do I look?" exactly when the speaker says it. Late, too strong or too frequent zooms make viewers seasick and hide context they need.

## When it triggers

Automatically when you ask to zoom into the screen, enlarge a detail, hide jump cuts with punch-ins, or when you have Pink markers. Ukrainian trigger phrases: «зроби зуми», «наближення на екран», «збільш код», «покажи ближче», «зум на кнопку», «наблизь на кнопку», «сховай джамп-кати». In `edit-episode` it is stage D, step 2.

Explicit call:

```
/davinci-editor:tutorial-zooms [timeline] [screen|punch-in]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | timeline to work on | the current timeline |
| `mode` | `screen`: zooms on the screen recording; `punch-in`: alternate punch-ins on talking-head A-roll to hide jump cuts | `screen` |

## Before you start

- `screen`: a cut timeline with the screen recording on the `Screen` track. In a screen-only lesson without a Screen track, the `A-roll` item is zoomed. A talking-head camera under a Pink marker is the wrong mode: the skill asks.
- `punch-in`: a talking-head cut with the Cream `cut` markers that `text-based-cut` puts at every join; the segments between them alternate.
- Optional but recommended: transcripts from `uk-transcribe`, so zooms are timed to speech.
- In `edit-episode` the A-roll track is locked in stage D; `punch-in` changes A-roll items, so it is unlocked for this step only and locked again after.

## Markers it reads

| Color | Task | Note | Point marker | Marker with duration |
|---|---|---|---|---|
| **Pink** | zoom | the area and the strength | from the marker to the end of the sentence about the spot (2–5 s) | exactly that range |

Markers are read from the timeline and its items; markers whose `customData` is `claude:done:*` are skipped. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

How to write the note so the skill finds the spot and the strength:

| Note | Result |
|---|---|
| `зум на поле Login` | default scale onto the Login field |
| `трохи, код праворуч` | gentle zoom (about 1.3) onto the code on the right |
| `сильно на термінал` | strong zoom onto the terminal, up to the maximum |
| `у 4 рази на індикатор` | capped at `zoom_max_scale`, and you are told |

Name what is on screen ("Save button", "the code on the right", "the terminal"), not a direction alone; the skill looks for it on the still and asks, with the still's path, if it can't find it.

## Zoom rules

- Region = the whole element plus a little context (a line of code, not one word).
- Strength: "трохи" ≈ 1.3, nothing ≈ `zoom_default_scale`, "сильно" up to `zoom_max_scale`. Above the max, screen text turns soft on a 4K timeline, so the skill tells you instead of exceeding it.
- Never across an edit point on that track: the zoom ends 2 frames before the cut, and you are told.
- Eased in and out over `zoom_ease_s`.
- The scaled image always covers the frame; the focus is clamped near the edges, so there are no black edges.
- Zooms closer than 1 s apart on one item are chained into a pan instead of bouncing out and in.
- No more than one zoom every ~10 s on average unless you ask; otherwise the weakest are proposed for dropping.
- Punch-ins skip segments shorter than 2 s (a size jump every second is worse than the jump cut), items under a B-roll / Screen insert (not visible), and items with a non-default Inspector transform (PiP, your reframe).
- Punch-ins enlarge the shot and keep the eyes where they were.

## Settings

| Key | Default | Effect |
|---|---|---|
| `zoom_default_scale` | `1.6` | screen zoom when the region gives no better fit |
| `zoom_max_scale` | `2.5` | strongest screen zoom |
| `zoom_ease_s` | `0.5` | duration of the zoom-in and zoom-out moves, seconds |
| `punch_in_scale` | `1.12` | scale of the alternate A-roll segments in `punch-in` |

Any setting can be overridden in the prompt: "max zoom 2 in this lesson", "ease 0.3 s".

## Files

Under `<work_dir>/<project>/` (the work folder from `resolve-core`):

| File | Contents |
|---|---|
| `zooms-before.json` | properties of every item before the change: the undo record |
| `words-<timeline>.json` | words on the cut, to time zooms to speech (when transcripts exist) |
| `stills/zoom-<n>.tif` | the still each region is read from |
| `zooms/<item>.json` | the zooms of one item (frames, regions, scales) |
| `zooms/<item>-spec.json` | the Fusion keyframe spec built from it |

## Workflow and approval stops

**`screen`:**

1. Dumps the timeline, maps the words onto the cut if transcripts exist, backs up the timeline, saves the project and records the item properties in `zooms-before.json`.
2. For each Pink marker or request: finds the item, the range and the region on an exported still, and the strength from the note.
3. **Approval: the zoom table.** `# | TC | item | region (what) | scale | duration | chained`. Nothing is built before your yes.
4. Per item, all zooms go into one Fusion comp. An item that already has your own Fusion comp is left alone and you are asked; a comp from an earlier run of this skill is rebuilt (it says so).
5. Plans the keyframes with `zooms.py plan` and reports its warnings, then builds `MediaIn1 → ZOOM (Transform) → MediaOut1`. The clip's Inspector transform (the PiP layout from `dual-video-sync-pip`) stays as it is; the PiP position is checked after the first build.
6. Verifies each zoom on stills at its middle and 1 s after its end: element centered and readable, no black edge, back to full frame afterwards. Offers Fusion output cache `Auto` for smooth playback of 4K screen recordings.

**`punch-in`:**

1. Lists the A-roll items in order and skips the ones the rules exclude.
2. Reads the point between the eyes off a still of each shot setup and computes the punch-in with `zooms.py punch`.
3. **Approval: the list of items that change.** Applied after your yes, to every second item; the first one is checked on a still before the rest.

**Finish:** marks handled Pink markers in `customData`, saves, and reports zooms built (TC, what, scale), items skipped and why, punch-in items, stills to look at and how to undo (`zooms-before.json`, the Fusion comps named in the report).

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## What it never does

- Zoom beyond `zoom_max_scale`, across an edit point, or with a black edge in frame.
- Change an item's existing Fusion comp that isn't its own `ZOOM`.
- Change an item's Inspector transform in `screen` mode.
- Zoom more often than every ~10 s on average without your request.
- Change the color, name or note of your markers (it writes only the hidden `customData`).

## Place in the workflow

Stage D: `fusion-motion-graphics` → **`tutorial-zooms`** → `subtitles-uk` → `chapters-markers` → `shorts-cutdown` → `thumbnail-frames` → `pre-delivery-qc` → `deliver`

`punch-in` builds on the Cream `cut` markers of `text-based-cut`. A soft whoosh on big zooms is suggested only if `sound-design` runs again, never on every zoom.

## Example prompts

**Minimal:**

> Make the zooms from the Pink markers on the screen recording.

**With arguments, screen mode:**

```
/davinci-editor:tutorial-zooms "Router - rough cut" screen
```

**With arguments, punch-in mode:**

```
/davinci-editor:tutorial-zooms "Router - rough cut" punch-in
```

**Overriding a setting:**

> Zooms from my Pink markers, but max scale 2.0: this screen recording is 1080p and gets soft quickly.

**Professional brief:**

> Zooms on the screen recording of "Router - rough cut" from my Pink markers. The Login field and Save button markers are back to back, pan between them rather than zooming out. The marker on the status indicator asks for 4x, cap it and tell me. Item 3 already has my own Fusion comp with a blur, don't touch it, just tell me. Keep the PiP camera where it is. Show me the table first; afterwards list the stills to check and how to undo.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Zoom in where needed" | "Zoom on the screen recording at my Pink markers; notes name the element, gentle by default, chain close ones into a pan, don't cross cuts." |

The strong prompt points to your markers and names the elements, so regions come off the stills without guesswork and the table needs few corrections.

## What to check afterwards

- Watch every zoom in context: does it arrive when the speaker names the spot, is the element readable?
- No black edge at any frame of a zoom; back to full frame after it.
- The PiP camera still sits right on zoomed Screen items.
- In `punch-in`: the jumps look intentional, the eyes stay in place.
- Undo: `zooms-before.json` and the Fusion comps named in the report.
