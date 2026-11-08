# `edit-memory`: learns from your own edits

[← All skills](README.md)

## What it does

When you fix something by hand after Claude placed it (a lower third held longer, a zoom pulled back, a caption moved), that edit says something about your taste. `edit-memory` notices those edits, keeps them in one log across all your projects, and when the same edit shows up twice or more in the same direction it proposes a rule:

> 4 of 6 lower thirds in 2 episodes lengthened, median +1.0 s → *Hold lower thirds 1 s longer*, `fusion-motion-graphics.hold_extra_s = 1.0`

You approve each rule separately and can reword it. From then on the skill that owns that kind of element reads the rule before its plan, lists it in the plan table, and `frame-critic` checks the numeric ones. A direct request from you or a marker note still wins over a rule.

Principle: nothing becomes a rule without your yes, and a single edit is a decision about one frame, not a taste. One-off edits are shown, unchecked, and stay in the log until they repeat.

## How it sees your edits

Every time Claude finishes writing to a timeline (the end of a skill, each critic fix round, Cream markers, an `edit-episode` stop) it saves a **handoff snapshot**: every item with its position, length, source range, scale, position, opacity, volume, fades and, for titles, the text, position and size. The next skill that writes to that timeline first compares a fresh snapshot with that one and logs what changed: moved, lengthened or shortened, deleted, added by you, text changed, scale / position / opacity changed, volume changed, moved to another track, a cut on A-roll or Screen changed.

Shifts are not edits: when you cut two seconds out of the A-roll, everything after it moves left, and that ripple is subtracted before anything counts as "moved". Claude's own markers (`claude:` in their data) are ignored.

This learning step at a skill's start never asks you anything. Candidates are shown in a batch: at an `edit-episode` stop, at the end of a skill when it found new ones, or when you ask.

## When it triggers

Ukrainian trigger phrases: «чого ти навчився», «запам'ятай мої правки», «мої правила», «забудь правило». Explicit call:

```
/davinci-editor:edit-memory [learn|show|forget <id>]
```

| Command | What it does |
|---|---|
| `learn` (default) | compares the current timeline with its last snapshot, then shows every candidate from the whole log with evidence and asks which to write |
| `show` | lists the approved rules and the open candidates; changes nothing |
| `forget <id>` | removes one rule after showing it and asking |

## Before you start

- Snapshots exist only from the first run of a skill after this one was installed. Edits made before that, or on a timeline Claude never handed off, can't be compared.
- Edits count only on elements a skill recorded when it placed them (`placed-<timeline>.json`): titles, callouts, counters, zooms, Shorts captions, PiP. Your edits to your own clips and titles are logged but never turned into rules.

## What it doesn't see

- Volume keyframes (Resolve has no API for them) and grades.
- Keyframes inside Fusion comps (the moves of screen zooms included) and Fusion tools other than a title's first Text+.
- Cut decisions of `text-based-cut`, `split-edits` and `sound-design`: they don't record what they place, so a changed cut is logged as yours and not learned.
- Items whose Resolve id changed (after a restart, or a blade in the UI: unverified) are matched by content instead, which can miss an edit or read it as delete + add.

Every `learn` report repeats this list.

## Repeats and conflicts

- The same edit again in the same direction as an approved rule: no second rule; the row reads "confirms rule N" and raises that rule's confirmation count.
- An edit in the opposite direction: the candidate is shown next to the rule. You keep the rule, replace it, or leave both open.

## Settings

| Key | Default | Effect |
|---|---|---|
| `edit_memory_file` | empty = `<work_dir>/edit-memory.json` | the rules file, shared by all projects; the event log `edit-memory-events.jsonl` sits next to it |
| `work_dir` | `resolve-work` | snapshots go to `<work_dir>/<project>/handoff/` |

## Files

| File | Contents |
|---|---|
| `edit-memory.json` | approved rules: text, skill / kind / format, numeric param, evidence (project, timeline, TCs), confirmations |
| `edit-memory-events.jsonl` | one line per logged edit: project, timeline, date, owner skill, kind, type, value, TC, and the rule it went into |
| `<project>/handoff/<timeline id>-<date-time>.json` | handoff snapshots; the newest is the starting point of the next comparison |
| `<project>/handoff/events.json` | the edits found by the last comparison |

Only the `memory.py` script writes the rules and the log; don't edit them by hand.

## Workflow and approval stops

1. Snapshot of the current timeline, compared with the last one; new edits go into the log.
2. Candidates from the whole log, each sorted as new, repeat, conflict or one-off.
3. **Question: which rules to write?** A table with evidence and proposed wording; new rules and repeats pre-checked, one-offs unchecked, conflicts undecided. Nothing is written before your answer, and "later" leaves everything open.
4. Writes what you approved and reports it. A rule you decline is marked so it isn't proposed again.

## Example prompts

**Minimal:**

> What did you learn from my edits?

**Look, don't write yet:**

> Show me what you picked up from my fixes in the last two episodes. Don't save anything yet, I'll decide later.

**Forget a rule:**

```
/davinci-editor:edit-memory forget 3
```

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Remember how I like it." | "Learn from my edits on 'Mesh - final': I kept lengthening the lower thirds; propose a rule with the numbers." |

The weak prompt gives nothing to compare. The strong one names the timeline and the pattern, so the evidence can be checked.

## What to check afterwards

- `show` lists every rule with its evidence; a rule built on two edits in one episode may be too narrow.
- In the next skill's plan table, the rules it applied are listed by id: if one doesn't fit this video, say so in the prompt, and `forget` it if it never fits.
