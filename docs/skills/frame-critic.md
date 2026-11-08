# `frame-critic`: checks what the skills put on screen

[← All skills](README.md)

## What it does

Checks the elements that other skills placed on the timeline: lower thirds, callouts, kinetic phrases and counters from `fusion-motion-graphics`, zooms from `tutorial-zooms`, Shorts captions from `subtitles-uk`, PiP from `dual-video-sync-pip` and the Shorts from `shorts-cutdown`. It checks at three levels:

1. **Numbers**, without Resolve: is each text on screen long enough to read, are two titles on screen at once, is an element too close to a cut, is a zoom too strong, are captions too fast or too long.
2. **Measured bounds:** it renders the frame twice, with and without the element's track, and measures in pixels where the text and its plate actually are. That shows text cut off at the frame edge or outside the safe areas, whatever the text and plate colors.
3. **By eye:** it looks at the frame for text over a face or over the part of the demo being talked about, boxes instead of letters or the wrong font, weak contrast, and elements of one type that look different from each other.

Every finding names the skill that placed the element and a concrete change to that skill's spec. With your approval those skills re-apply the fixed elements, at most two rounds. Whatever is left gets a Cream marker and a row in the report.

Principle: the critic only looks and measures. The skill that placed an element owns it and re-applies it from its spec, so a fix is never a hand edit that the next run would undo.

## When it triggers

After `fusion-motion-graphics`, `tutorial-zooms`, `subtitles-uk` (Shorts captions), `dual-video-sync-pip` or `shorts-cutdown` placed something. In `edit-episode` it runs in stage D after each of these steps. Ukrainian trigger phrases: «перевір титри», «чи не вилазить текст», «чи встигну прочитати», «перевір графіку», «critic».

Explicit call:

```
/davinci-editor:frame-critic [timeline] [all|<owner skill>]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | the timeline to check | the current timeline |
| `scope` | `all`, or one owner skill such as `fusion-motion-graphics`: the measured and visual checks only look at that skill's elements (the numbers always cover everything, since overlaps need all elements) | `all` |

## Before you start

- Elements placed by the skills above. Each of them records what it placed in `placed-<timeline>.json`. Graphics you added yourself are not in that ledger, and the critic never judges them.
- Resolve 21.1.2 or newer for the measured bounds (frame export). On older versions that level is skipped and Claude says so.
- Optional: the transcript mapped onto the timeline (`words-<timeline>.json`) for the "covers the demo" check; without it that check is skipped.

The critic makes the checked timeline current while it works, because Resolve only renders frames of the current timeline, and switches back to your timeline at the end.

## What it checks

Severity: **error** = the viewer will notice (cut off, unreadable, covered); **warn** = probably a mistake, you decide.

| Kind | What | Severity |
|---|---|---|
| `short-hold` | text fully visible less than 0.5 s + characters / 14 per second; a lower third at least 3 s | error |
| `overlap` | two titles on screen at once (a callout over another title is allowed in time, but not where their bounds touch) | error |
| `near-cut` | an element starts or ends less than 6 frames from an A-roll / Screen cut | warn |
| `zoom-scale` | a zoom stronger than `zoom_max_scale` | error |
| `cps`, `chars` | captions faster than `subtitle_max_cps` or a line longer than `subtitle_max_chars` | warn |
| `offscreen` | measured text or plate touches the frame edge, or nothing of the element renders | error |
| `unsafe` / `unsafe-title` | outside the action-safe (5 %) / title-safe (10 %) area | error / warn |
| `covers-face` | text over a face (also a camera bubble baked into a screen recording) | set by Claude |
| `covers-demo` | text over the part of the screen being talked about | set by Claude |
| `glyph` | boxes instead of letters, or not the `brand_font` | set by Claude |
| `contrast` | text hard to read against what is behind it | set by Claude |
| `inconsistent` | elements of one type differ in position, size or motion | set by Claude |

**Verdict:** `PASS` (no errors), `PASS WITH WARNINGS`, or `FAIL`, with counts and the fix round.

## Settings

| Key | Default | Effect |
|---|---|---|
| `zoom_max_scale` | `2.5` | strongest allowed zoom |
| `subtitle_max_cps` | `17` | caption reading speed limit |
| `subtitle_max_chars` | `42` | caption line length limit |
| `brand_font` | `Montserrat` | the font titles should render in |

Any setting can be overridden in the prompt: "allow zooms up to 3x for this one".

## Markers it writes

For each finding still open after the fix rounds, a **Cream** marker on the frame: name = kind, note = the message, `customData` `claude:critic:<kind>`. If one of your markers sits on that frame, the Cream one goes a frame later. Your markers are never changed. Cream `claude:critic:*` markers from an earlier run are removed only after you agree. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## Files

All under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `timeline-<timeline>.json` | dump of the checked timeline |
| `placed-<timeline>.json` | ledger of elements the skills placed (read only) |
| `critic/elements.json` | the inventory: each element with its owner, spec, track, text and frames |
| `critic/<item>-on.tif`, `critic/<item>-off.tif` | the two renders behind each measured bound |
| `critic/faces.json` | face zones per clip, reused by later rounds |
| `critic-<timeline>.json` | every finding with its evidence and fix, the `verdict`, the round and the timeline `state`; read by `pre-delivery-qc` |
| `critic-<timeline>.md` | the report shown to you |

## Workflow and approval stops

1. Switches to the checked timeline, dumps it and builds the inventory from the ledger (`critic.py inventory`).
2. Runs the numeric checks (`critic.py check`).
3. Measures each text element from two renders (`critic.py bbox`). The script that disables the element's track restores every track's state in the same call and checks it.
4. Looks at each element's frame, and at thumbnails of all elements of one type.
5. **Question: fix now?** Lists the findings with their fixes. On yes, each owner skill changes its spec and re-applies only those elements; the critic checks the changed elements again. At most two rounds.
6. Puts Cream markers on what is left, writes and shows the report (`# | TC | element | problem | changed / left | still`), switches back to your timeline.
7. **Question: old critic markers.** Cream `claude:critic:*` markers from a previous run are removed only after you agree, named one by one.

## What it never does

- Move, trim, delete, re-insert or restyle an element, or edit a spec: the owner skill does that.
- Judge taste, pacing or whether a graphic belongs at all.
- Leave a track disabled: disabling, restoring and checking happen in one script.
- Judge graphics you placed yourself.
- Run more than two fix rounds, edit its result file by hand, or change your markers.

Any script that deletes something, such as removing the previous run's Cream markers, becomes a permission prompt (the `guard.py` hook), so read what you approve.

## Place in the workflow

`fusion-motion-graphics` / `tutorial-zooms` / `subtitles-uk` (Shorts) / `dual-video-sync-pip` / `shorts-cutdown` → **`frame-critic`** → … → `pre-delivery-qc` → `deliver`

`pre-delivery-qc` reads `critic-<timeline>.json`; after a later edit the critic's verdict counts as outdated, so run it again.

## Example prompts

**Minimal:**

> Check the titles: is anything cut off?

**With arguments:**

```
/davinci-editor:frame-critic "Router Setup - final" fusion-motion-graphics
```

**Report only:**

> Check the graphics on "Router - final 2026-11-08", is any text cut off and can everything be read in time? Report only for now, we fix later.

**Professional brief:**

> Critic pass on "Router Setup - final" after the graphics and zooms. I care most about the lower thirds near the right edge and the speed-test kinetic phrases: are they on screen long enough? Callouts over the screen recording may sit on top of other titles in time, just not on them. Fix what you can through the skills that placed them, two rounds at most, then mark the rest.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Do the titles look good?" | "Frame critic on the final cut: cut-off text, reading time and covered faces; report only." |

"Look good" asks for taste, which is not this skill's job. The strong prompt names the checks and says whether fixes may run.

## What to check afterwards

- Read the report top-down: errors first, each with its timecode, owner and fix.
- Jump to the Cream `claude:critic:*` markers and look at each problem in context.
- Warnings are your call: an element close to a cut may be intended, but decide it by name.
- After a later edit, run the critic again before `pre-delivery-qc`.
