# `jump-cuts`: every jump cut judged, the lightest treatment that hides it

[← All skills](README.md)

## What it does

After `text-based-cut` a talking-head video has dozens of joins inside one shot: same clip, same framing, the head snaps to a new place. Most need nothing. This skill looks at each join and decides:

- **leave**: the join is under B-roll or the screen, the source changes there anyway, or the jump is too small to see;
- **roll**: the cut landed on a blink or a half-open mouth, so it moves a few frames inside the pause that was removed;
- **Smooth Cut**: the pose matches and the background is still, so Resolve's Smooth Cut transition can morph across it;
- **punch-in**: a visible jump; one side is enlarged a little so the cut reads as a change of shot size;
- **cover**: nothing fits; a Cream marker advises B-roll or the screen over it.

It replaces the old `punch-in` mode of `tutorial-zooms`, which enlarged every second segment without looking at the picture.

Principle: the lightest treatment that works. A punch-in on a cut nobody would notice adds a size jump where there was none.

Design note: [superpowers/specs/2026-11-12-jump-cuts-design.md](../superpowers/specs/2026-11-12-jump-cuts-design.md) (in Ukrainian).

## When it triggers

Automatically when you ask to hide, soften or check the jump cuts, for punch-ins on a talking head, or for Smooth Cut on the joins. Ukrainian trigger phrases: «сховай джамп-кати», «згладь склейки», «оціни склейки», «приховай склейки», «зроби punch-in». In `edit-episode` it is stage B, step 8.

Explicit call:

```
/davinci-editor:jump-cuts [timeline] [all|markers]
```

| Argument | Meaning | Default |
|---|---|---|
| `timeline` | the cut timeline to work on | the current timeline |
| `scope` | `all`: every join on A-roll. `markers`: only joins whose Cream `cut` marker you extended with the word `jump` in its note | `all` |

## Before you start

- A cut timeline (normally the rough cut from `text-based-cut`, after `split-edits`).
- Transcripts in `<work_dir>/<project>/transcripts/`. Without them the skill still works, but it can't roll a cut: it has no way to know where the words are.
- The A-roll track unlocked. The skill never unlocks a track itself.
- Resolve 21.1.2+ for the measured difference. On older versions the joins are judged by eye only, and the report says so.

## Markers it reads

No color of its own. It reads Claude's own Cream markers:

| Marker | Used for |
|---|---|
| Cream `cut` (`claude:cut`, from `text-based-cut`) | what was removed at the join, shown in the table; with scope `markers`, the word `jump` you add to its note selects the join |
| Cream `J` / `L` (`claude:split`, from `split-edits`) | such a join is never rolled: its sound is already offset from its picture |

It writes Cream `jump` markers (`claude:jump:cover`) on joins it advises you to cover. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## How it decides

The first rule that fits wins.

| # | When | Decision |
|---|---|---|
| 1 | the join is under a B-roll or Screen item | hidden, nothing |
| 2 | the clip changes, or the source goes backwards (another take) | not a jump cut, nothing |
| 3 | the frame difference is below `jump_diff_threshold` | leave |
| 4 | closed eyes or a mouth mid-move on the last frame before or the first after, and the cut can move | roll by a few frames |
| 5 | difference below 3 × the threshold, same pose, still background, media beyond both edges | Smooth Cut, 6 frames |
| 6 | a visible jump and both neighbours may change scale | punch-in |
| 7 | anything else | cover advice |

The frame difference is measured on two exported stills: the last frame before the join and the first after. Joins above the threshold are also looked at for blinks, the mouth, how far the pose moved and whether the background moves.

**Rolling a cut.** Both the picture and the sound move by the same number of frames, at most 6, and never closer than 2 frames to the end of the previous word or 0.15 s to the start of the next. The timeline length and everything to the right stay where they were.

**Punch-ins are planned along the chain.** A punch-in is a state of a segment, not of a join. Segments joined by leave, roll or Smooth Cut share one scale; a punch-in join needs two different ones. A segment keeps 100 % when it is shorter than 2 s (a size jump every second is worse than the jump cut), has its own Inspector transform (PiP, your reframe) or lies under B-roll. When both sides of a join must stay at 100 %, the join gets cover advice instead.

## Settings

| Key | Default | Effect |
|---|---|---|
| `jump_diff_threshold` | `0.02` | frame difference (0..1) below which a jump cut is left alone; Smooth Cut is offered below three times this |
| `punch_in_scale` | `1.12` | scale of a punched-in segment |
| `work_dir` | `resolve-work` | where the dump, stills and decisions are written |

The threshold is a starting value. On the first run in a project the skill shows you the join with the smallest and the one with the largest difference and asks whether the threshold fits this footage. Any setting can be overridden in the prompt: "threshold 0.03", "punch-in 1.08".

## Files

All under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `timeline-<name>.json` | timeline dump; a fresh one of the copy before verifying |
| `jump/joins.json` | every join with its measurements, what was seen, the decision and its reason, and the scale of every segment |
| `jump/<id>-a.tif`, `jump/<id>-b.tif` | the frame before and the frame of each join |
| `jump-before.json` | offsets and Inspector properties of every item before the changes: the undo record |

## Workflow and approval stops

1. Dumps the timeline, lists the A-roll joins and the segments that must keep their scale.
2. Exports two stills per join and measures the difference; looks at the ones above the threshold.
3. **Approval: the table.** `TC | removed | difference | decision | scale left → right | reason`, with the stills of every join that changes. You can change any decision; a punch-in that can't get two different scales and a roll outside the safe range are refused with the reason.
4. Duplicates the timeline (`<name> - jump <date>`) and applies on the copy: rolls first (each rolled join is measured and judged again), then Smooth Cuts, then punch-ins, then cover markers. The first roll, the first Smooth Cut and the first punch-in are each checked before the rest.
5. Verifies the copy: same items, same length, the same words in the same order, every property read back.
6. Reports what was done to which join and how to undo it.

Smooth Cut through the scripting API is unverified. If Resolve refuses it or the result looks warped, those joins get a punch-in instead and the report lists them so you can add Smooth Cut by hand (Edit page → Effects → Video Transitions → Smooth Cut).

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## What it never does

- Change the original timeline, or apply anything before your yes.
- Roll a cut into a word, or roll the picture without its sound.
- Punch in on a segment shorter than 2 s or on an item with its own transform.
- Place B-roll: cover is advice, the insert is yours (Fuchsia markers and `marker-edit`).
- Unlock a track or touch your markers.

## Place in the workflow

`text-based-cut` → `dual-video-sync-pip` → `marker-edit` (Fuchsia, Cocoa) → `split-edits` → **`jump-cuts`** → sound

After `split-edits`, because it must know which joins already have offset sound. Before sound, because a rolled cut moves the Voice edges that `sound-design` and `audio-finish` build on.

## Example prompts

**Minimal:**

> Hide the jump cuts on the rough cut.

**With arguments, one per scope:**

```
/davinci-editor:jump-cuts "Router - rough cut 2026-11-02" all
/davinci-editor:jump-cuts "Router - rough cut 2026-11-02" markers
```

**Overriding a setting:**

> Treat the jump cuts on the current timeline, punch-in 1.08: the framing is already tight.

**Professional brief:**

> Jump cuts on "Router - rough cut 2026-11-02". The intro up to 01:00:40 is fast on purpose, leave every join there. Prefer rolling a cut over a punch-in where I blink. No Smooth Cut where my hands are in the frame. Show the table with the stills before you change anything, and list the joins you'd cover with B-roll.

**Scope `markers`:**

> Only the joins where I added "jump" to the Cream marker note.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Add punch-ins" | "Look at each jump cut on the rough cut and hide only the ones that show; leave the intro alone and show me the table first." |

The strong prompt lets the skill leave invisible joins alone and names the part you want untouched, so the table needs few corrections.

## What to check afterwards

- Play the copy through the rolled joins on headphones: no clipped word, no breath cut in half.
- Step through the punched-in segments: the eyes stay at the same height, no black edge, and no two size jumps within a couple of seconds.
- Watch every Smooth Cut at full speed: a warped face means it should be a punch-in or a cover.
- The Cream `jump` markers are where B-roll would help most.
- Undo: the original timeline is untouched; `jump-before.json` holds the old values of the copy.
