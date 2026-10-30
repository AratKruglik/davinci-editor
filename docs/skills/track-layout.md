# `track-layout`: role-based tracks on the timeline

[← All skills](README.md)

## What it does

Sets up and maintains the standard track structure of a timeline:

- **video:** Backgrounds, A-roll, B-roll, Effects, Titles;
- **audio:** Voice, SFX, Music;
- **on demand:** Screen, PiP, B-roll 2, Titles 2, Voice 2, Ambience, Subtitles UA.

It names the tracks, colors clips by role, locks tracks for a stage, unlocks them when it ends, and removes empty tracks after your confirmation.

Every other skill finds tracks **by role name** through it, never by number. That's why the numbering can change without breaking anything. In the standard layout V1 is Backgrounds, not A-roll.

Design note: [track-layout.md](../track-layout.md) (in Ukrainian).

## When it triggers

Automatically when a new or rough-cut timeline needs the standard track structure, when a track for a role is missing, when clips need recoloring by role, when tracks should be locked for a stage, or when empty tracks should be cleaned up before render. Ukrainian trigger phrases: «розклади доріжки», «структура доріжок», «додай доріжку B-roll», «прибери порожні доріжки», «перефарбуй кліпи по ролях». English one: "track layout". Other skills also call it: `text-based-cut` runs `setup` on its new timeline and `recolor` after assembly. In `edit-episode` it is stage B, step 2, plus `lock` in stages C and D and `cleanup` before QC.

Explicit call:

```
/davinci-editor:track-layout [setup|add <role>|recolor|lock <stage>|unlock <stage>|cleanup]
```

| Argument | Meaning | Default |
|---|---|---|
| `action` | `setup`, `add`, `recolor`, `lock`, `unlock` or `cleanup` (below) | `setup` |
| `target` | for `add`: the role to add, a base or on-demand role (anything else → Claude asks); for `lock` / `unlock`: the stage, `sound` or `graphics` | none; `lock` asks, `unlock` takes both stages |

Actions:

| Action | What it does |
|---|---|
| `setup` | builds the layout from the `.drt` template or on an empty timeline. On a timeline with clips it renames only tracks that clearly match a role. Also creates the on-demand tracks this episode will need |
| `add <role>` | adds one role track. On top of its kind it adds it itself. In the middle it tells you where to add it by hand, then names and recolors it |
| `recolor` | sets every clip's color to its track's role color; run after any skill that placed clips |
| `lock <stage>` | `sound` stage: locks Voice and A-roll. `graphics` stage: locks A-roll, B-roll and Voice. Tracks you had already locked stay as they are |
| `unlock <stage>` | unlocks that stage's tracks (no stage: both stages' tracks), except the ones you had locked before `lock` ran |
| `cleanup` | lists the empty tracks except protected roles and deletes them after an explicit yes |

## Before you start

- For `setup`, an **empty** timeline gets the full layout. On a timeline that already has clips, only clearly matching tracks are renamed, and the rest is listed for you.
- Optional: a `.drt` template in `track_template`. You export it once from an empty timeline you styled yourself: names, header colors, order. New timelines are then created from it.

## Markers it reads

Only in `setup`, as a look-ahead: the markers and the transcript tell which on-demand tracks this episode needs, so they're created before any content is placed.

| Hint | Track created |
|---|---|
| **Purple** markers | Screen and PiP |
| overlapping **Fuchsia** markers | B-roll 2 |
| **Lavender** / **Sky** with room tone | Ambience |
| two speakers in the transcript | Voice 2 |

Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).


## The layout

Video, bottom to top: order matters, higher tracks cover lower ones. Audio: first = A1. Colors are clip colors.

| Track | Kind | Clip color | Why here |
|---|---|---|---|
| Backgrounds | video | Tan | under everything (PiP plates) |
| A-roll | video | Blue | the base |
| B-roll | video | Teal | covers A-roll |
| Effects | video | Orange | adjustment clips affect the picture but not titles |
| Titles | video | Pink | always on top |
| Voice | audio | Green | `mono` for a single mic, otherwise matches the source |
| SFX | audio | Yellow | |
| Music | audio | Purple | |

On-demand roles:

| Role | Where | Clip color |
|---|---|---|
| Screen | above A-roll | Navy |
| PiP | above Screen | Violet |
| B-roll 2 / Titles 2 | above their base role | same as the base role |
| Voice 2 | audio, under SFX | Lime |
| Ambience | audio, on top | Olive |
| Subtitles UA | subtitle track | none |

A-roll and Voice are never deleted, even when empty (`protected_tracks`).

## What the API can't do

| Need | Possible? | What happens instead |
|---|---|---|
| Name a track | yes | |
| Color the track header | no | `.drt` template; clip colors are kept in sync instead |
| Insert a track at a position | no, new tracks go on top | tracks are planned before clips are placed; for a middle track Claude asks you to add it (right-click the track header → Add Track → position), then names it |
| Move a clip between tracks | no | never deleted and re-added: that would lose effects, grades and keyframes |
| Lock / enable a track | yes | |

## Settings

| Key | Default | Effect |
|---|---|---|
| `video_tracks` | `Backgrounds:Tan,A-roll:Blue,B-roll:Teal,Effects:Orange,Titles:Pink` | base video tracks, `Name:ClipColor`, lowest first |
| `audio_tracks` | `Voice:Green,SFX:Yellow,Music:Purple` | base audio tracks, `Name:ClipColor`, first = A1 |
| `protected_tracks` | `A-roll,Voice` | roles `cleanup` never removes, even when empty |
| `track_template` | empty | optional `.drt` that new timelines are created from |

Any setting can be overridden in the prompt: "keep the empty SFX track too", "use my template `~/Templates/youtube.drt`".

## Files

No working files. The only file it reads is the optional `.drt` from `track_template`.

## Workflow and approval stops

**setup**

1. With `track_template` set, it creates the timeline from the `.drt` and renames it. Whether `.drt` keeps header colors is unverified: Claude checks once and tells you.
2. Otherwise, on an empty timeline, it adds tracks up to the configured count and names them in order. On a timeline with clips it renames only tracks whose content clearly matches a role (**asks when unsure**). It adds missing roles on top only if their place is on top, and lists the rest for you to add by hand.
3. Creates the on-demand tracks from the look-ahead (above), in order.
4. Reads back every track name and reports the layout table: index, type, name, clip count.

**add**

- Already there → reports its index.
- Its place is on top of its kind (Titles 2, B-roll 2 with nothing above, Ambience, Subtitles UA, or any role on an empty timeline) → adds and names it, then recolors that track. Claude re-reads the names to confirm the track really landed on top; that is unverified in 21.1.1.
- Its place is in the middle (Screen, PiP, Voice 2 under SFX…) → **tells you exactly where to add it by hand and waits.** Then it finds the new unnamed track, names it and recolors it.

**recolor**

Sets each clip on a track with a known role to the role color, skipping clips already that color.

**lock**

Locks the tracks for the stage and reports which tracks are locked. It reads each track's lock first: tracks you had already locked stay as they are and are named in the report. **Asks before changing locks you set yourself.**

**unlock**

Unlocks the stage's tracks, except the ones you had locked before `lock` ran (from its report, or it asks), and reports which tracks are unlocked.

**cleanup**

1. Lists empty tracks, excluding protected roles.
2. **Shows the list and waits for an explicit yes.**
3. Deletes from the highest index down, so lower indices don't shift mid-operation. Then it re-reads the layout and reports.

Typical moments: after the rough cut and before render. Deleting tracks becomes a permission prompt (the `guard.py` hook), so read what you approve.

## What it never does

- Delete and re-add a clip to move it between tracks: that loses effects, grades and keyframes.
- Remove a protected track (`protected_tracks`), even when empty.
- Delete tracks without showing the list and getting an explicit yes.
- Change locks you set without asking.
- Find a track by number instead of by role.

## Place in the workflow

`uk-transcribe` → **`track-layout`** → `text-based-cut` → `dual-video-sync-pip` → `marker-edit` (Fuchsia, Cocoa) → `split-edits`

Later in `edit-episode`:

- `lock sound` after `voice-isolation`, `unlock sound` after `audio-finish`;
- `lock graphics` for stage D, `unlock graphics` after delivery;
- `cleanup` before `pre-delivery-qc`.

## Example prompts

**Minimal:**

> Set up the tracks on this timeline.

**With arguments, one per action:**

```
/davinci-editor:track-layout setup
/davinci-editor:track-layout add B-roll 2
/davinci-editor:track-layout recolor
/davinci-editor:track-layout lock sound
/davinci-editor:track-layout unlock sound
/davinci-editor:track-layout cleanup
```

**Overriding a setting:**

> Clean up the empty tracks, but treat Music as protected too this time: the music goes in after review.

**Professional brief:**

> Plan the tracks for the router lesson before the rough cut. There's a screen recording and I've put Purple markers for camera / screen / PiP, and a few overlapping Fuchsia B-roll markers in the setup part. It's just me, one lav mic. Create everything this episode needs in the right order. If a track has to go in the middle, tell me exactly where to add it and wait. Show me the final table with index, name and clip count.

**Per action:**

| Action | Prompt |
|---|---|
| `add` | "Add an Ambience track for the B-roll live sound." |
| `recolor` | "Recolor the clips by role, I've just dropped B-roll in." |
| `lock` | "Lock the tracks for the graphics stage." |
| `unlock` | "Sound is done, unlock the sound-stage tracks." |
| `cleanup` | "Remove the empty tracks before render, show me the list first." |

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Fix the tracks" | "Run setup on the new rough cut timeline: it's empty above A-roll, there's a screen recording with Purple markers, so I need Screen and PiP right above A-roll. Report the layout." |

The strong prompt names the timeline, the action and what the episode contains, so the right on-demand tracks land in the right order before any clip is placed.

## What to check afterwards

- The reported layout table matches what you see in the track headers.
- Header colors: they come only from the `.drt` template. Check once whether yours kept them.
- A track added with `add` really sits where its role belongs (adding on top is unverified in 21.1.1).
- After `lock`: run `unlock` when the stage ends, and check your own locks are still in place.
- After `cleanup`: protected tracks are still there.
