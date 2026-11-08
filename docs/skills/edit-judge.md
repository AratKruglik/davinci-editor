# `edit-judge`: an independent verdict on the finished edit

[← All skills](README.md)

## What it does

Gives a second opinion on an edit from a judge that never saw how it was made. The judge runs as a separate agent: it doesn't see the conversation, so it isn't inclined to approve what was just done. It only looks at frames of the timeline, reads the files prepared for it and runs its scripts. Two modes:

- **`gate`**: is the video ready? Numbers first (words in the first 30 s, leftover pauses, static stretches with no cut, zoom or title for more than 20 s, graphics per minute, how long the video runs after the last word), then a 1–5 score with timecode evidence for six criteria: **hook, pace, graphics, consistency, your approved edit-memory rules, ending**. The verdict is calculated, not felt: `SHIP` when no score is 2 or lower and neither `frame-critic` nor `pre-delivery-qc` has an open error, otherwise `REWORK` with a must-fix list `TC | problem | owner skill`.
- **`pick`**: which candidate is best? It ranks Shorts moments or thumbnail stills blind: candidates are shuffled and renamed A, B, C…, every pair is compared twice in both orders, and a pair that comes out differently in the two orders counts as a tie.

The rubric is tuned for programming tutorials: slides, screen recordings and a round facecam. A stretch of unchanged code while you talk counts as static; scrolling, typing or new output does not.

Principle: the judge advises. It doesn't block `deliver` (QC is the hard gate) and it never changes anything.

## When it triggers

`edit-episode` runs `gate` after `pre-delivery-qc`; `shorts-cutdown` and `thumbnail-frames` use `pick` to rank their candidates before you approve. Ukrainian trigger phrases: «оціни монтаж», «можна віддавати?», «чи готове відео», «суддя», «що з цих шортсів краще».

Explicit call:

```
/davinci-editor:edit-judge gate "<work>/timeline-<timeline>.json" [youtube|shorts]
/davinci-editor:edit-judge pick "<work>/candidates-<kind>.json"
```

| Argument | Meaning | Default |
|---|---|---|
| `mode` | `gate` or `pick` | — |
| `input` | `gate`: the fresh timeline dump; `pick`: the candidates file (`shorts` or `thumbnails`) | — |
| `format` | `youtube` or `shorts` (`gate`) | `shorts` for a vertical timeline, else `youtube` |

When you just ask in plain language, Claude prepares the inputs (below) and calls the judge for you.

## Before you start

The judge can't run Resolve scripts, so whoever calls it prepares the inputs:

- The judged timeline is made **current** in Resolve: frames render only from the current timeline. Your own timeline is switched back afterwards.
- A fresh timeline dump and the transcript mapped onto the timeline (`words-<timeline>.json`).
- Your approved edit-memory rules for that format.
- `frame-critic` and `pre-delivery-qc` results are used when they exist. A missing one is reported as "not run". One from before the last edit still counts with its open errors, and the report adds "re-run …" as information; that alone doesn't make it `REWORK`.
- For `pick`: a candidates file whose stills have neutral names, so nothing hints at a favorite.

## Isolation

The judge runs in its own agent (`agents/edit-judge.md`) with only frame viewing (`get_image`, `get_thumbnails`), file reading and a shell; Resolve scripts and file edits are switched off for the skill as well. The shell is limited by the skill's instructions, not by a hard rule: it runs the judge's scripts, and only those scripts write its result files. The judge runs in the foreground: Claude waits for it, so the timeline it looks at can't change under it.

Without Resolve frames (Resolve not reachable, or the tools missing) the judge gives no verdict: it says which ranges it needed to see.

Whether a skill can use a plugin agent this way is not verified yet. On the first run Claude checks that the judge has no Resolve scripting or file editing; if the plugin agent isn't picked up, the skill falls back to a general agent with the same tools switched off.

## The criteria

| Criterion | Question | Typical low score |
|---|---|---|
| Hook | is it clear at the start what the viewer gets? | greetings and "let's start", no result named in the first 30 s |
| Pace | pauses, stretched and static parts | 40 s of unchanged code while you talk |
| Graphics | in the right places, right density | callouts on obvious buttons, no zoom on the line being explained |
| Consistency | one style per element type | lower thirds jumping between corners |
| Rules | each approved edit-memory rule | a rule followed in some places only |
| Ending | does it stop after the last thought? | long goodbye or a silent tail |

Level descriptions 1–5 for each: [`skills/edit-judge/reference.md`](../../skills/edit-judge/reference.md).

## Settings

| Key | Default | Effect |
|---|---|---|
| `pause_threshold_ms` | `700` | gaps between words longer than this count as leftover pauses |
| `edit_memory_file` | empty | where the approved rules come from (empty = `<work_dir>/edit-memory.json`) |

## Files

All under `<work_dir>/<project>/`:

| File | Contents |
|---|---|
| `judge/rules-<timeline>.json` | the approved rules the caller passed |
| `judge/metrics-<timeline>.json` | the numbers |
| `judge-<timeline>.json` | verdict, must-fix list, re-run info, the six scores with evidence, the critic and QC status |
| `judge-<timeline>.md` | the report shown to you, written by `judge.py` from the same result |
| `judge/blind-<kind>.json`, `judge/key-<kind>.json` | `pick`: the shuffled candidates and the key the judge never reads |

## Workflow

1. The caller makes the timeline current and prepares the dump, transcript and rules.
2. The judge checks whether the critic and QC results are still current.
3. Numbers (`judge.py metrics`).
4. Frames: the opening, every static stretch as thumbnails, each placed element, the last seconds.
5. Six scores with timecodes, then the calculated verdict (`judge.py verdict`) and the report.
6. **Your call** (in `edit-episode`): on `REWORK` you see the must-fix list and decide whether to fix or ship as is.

## What it never does

- Change the project, markers, timelines or the files of other skills.
- See which candidate a skill preferred before it decides.
- Replace your decision: the verdict and the ranking are advice.

## Place in the workflow

… → `frame-critic` → `pre-delivery-qc` → **`edit-judge gate`** → `deliver`

`shorts-cutdown` / `thumbnail-frames` → **`edit-judge pick`** → your approval

## Example prompts

**Minimal:**

> Is "Lists - final" ready to ship?

**Ranking:**

> Which of these Shorts moments is the strongest? Rank them before showing me.

**Professional brief:**

> Judge pass on "Router Setup - final" for YouTube after QC. I want the six scores with timecodes and the must-fix list; don't fix anything yet.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "I tightened it, it should be fine now, right?" | "Run the judge on the final cut and show me the must-fix list." |

The judge doesn't see your remark anyway; asking for the list gets you the evidence.

## What to check afterwards

- Jump to each must-fix timecode and look at it in context.
- A low pace score names the stretch: decide whether to cut it, add a zoom, or keep it.
- After fixes, run `pre-delivery-qc` again before the judge: an outdated QC still counts, and its errors may already be fixed.
