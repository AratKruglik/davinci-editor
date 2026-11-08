---
name: edit-memory
description: Learns from the user's own edits in DaVinci Resolve Studio 21+ between Claude's runs - compares handoff snapshots of the timeline (moves, retimes, deletions, text, scale / position / opacity, volume, cut changes; shifts caused by a ripple on A-roll / Screen are not edits), keeps one event log across all projects, and turns repeated edits in one direction into rules the user approves one by one ("hold lower thirds 1 s longer", fusion-motion-graphics.hold_extra_s = 1.0). Owner skills and frame-critic read the approved rules before their plan. Commands learn, show, forget.
when_to_use: User asks what Claude learned from their edits, wants to review, approve or remove learned rules, or a skill / edit-episode stop offers new candidates. Triggers - "чого ти навчився", "запам'ятай мої правки", "мої правила", "забудь правило", "що ти помітив у моїх правках", "edit memory", "learn from my edits", "what did you learn".
argument-hint: "[learn|show|forget <id>]"
arguments: [command, id]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *memory.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Edit memory

Follow `resolve-core` first: its §11 has the memory file `M`, the snapshot folder and the start step every skill that writes to a timeline runs. Command: `$command` (default `learn`; `forget` takes the rule id `$id`).

Script: `${CLAUDE_SKILL_DIR}/scripts/memory.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/memory.py selftest`). Snapshot code and event types: `resolve-core/reference.md#handoff-snapshot`.

Principle: Claude learns only from what the user changed by hand in elements a skill placed, and nothing becomes a rule without the user's yes for that rule. A single edit is a decision about one frame, not a taste: it is shown and kept in the log, and counts once it repeats.

## 1. learn: collect

1. On the current timeline (`resolve-core` §1) run the start step of `resolve-core` §11: snapshot, `changed`, and on a change `diff` + `log`. Resolve not running: skip it, say so, and work from the event log alone.
2. `python3 ${CLAUDE_SKILL_DIR}/scripts/memory.py lessons --memory "<M>"` and `memory.py rules --memory "<M>"`. Read `edit-memory-events.jsonl` next to `M`: the events each candidate names (project, timeline, TC, value) and the events each rule consumed (their `rule_id`).
3. Sort every candidate:
   - **Repeat**: an existing rule whose consumed events have the same `group` and `property`, with a median of the same sign. It confirms that rule; never propose it as a second rule.
   - **Conflict**: `conflicts_with` names a rule (the same group, the opposite direction). Shown next to that rule.
   - **New**: not `one_off`, neither of the above.
   - **One-off**: `one_off` true.
   `ZoomX` and `ZoomY` (or `Center.x` and `Center.y`) of one item at one TC are one edit: one row, and later one candidate with the events of both.
4. Units: `retimed`, `moved` and `cut_changed` values are frames; divide by the fps of that timeline (from its snapshot) for seconds. `property_changed` values are deltas in the property's own units.

## 2. learn: show

One table in the user's language (Resolve names in English):

| ✓ | # | skill / kind | what you did | evidence | rule | param |

- **Evidence**: count, out of how many elements of that kind in those timelines' ledgers (`<work>/placed-<timeline>.json`) when they are at hand, median and direction, then each project / timeline with its TCs. Example: "4 of 6 lower thirds in 2 episodes lengthened, median +1.0 s → *Hold lower thirds 1 s longer*, `fusion-motion-graphics.hold_extra_s = 1.0`".
- **Param**, only where a skill reads it: `hold_extra_s` (`fusion-motion-graphics`, seconds added to the hold: median of `retimed` + in frames / fps, rounded to 0.1 s) and `max_scale` (`tutorial-zooms`, the scale the user ended at, read from the newest snapshot). Other candidates get a rule in words without a param.
- **✓**: new candidates and repeats are pre-checked; a repeat reads "confirms rule N". One-offs are listed unchecked. A conflict shows the rule and the candidate side by side, nothing chosen.

Below the table, what wasn't compared (§5). Then ask which rows to write and whether to change any wording. Nothing is written before that answer; "later" ends here, and the candidates stay open in the log.

## 3. learn: write the answers

Row by row, only what the user approved:

- **New**: `memory.py approve --candidate '<the candidate JSON from lessons>' --text "<the user's wording>" [--param name=value] [--format youtube|shorts] --memory "<M>"`. `--format` follows the timelines in the evidence: all vertical → `shorts`, all horizontal → `youtube`, mixed → leave it out.
- **Repeat**: `memory.py confirm <rule id> --memory "<M>"`, then `memory.py reject <its event ids> --memory "<M>"`. memory.py can't attach events to an existing rule, so this marks them used; say "folded into rule N" so the reject isn't read as a refusal.
- **Conflict**, as the user chooses: keep the rule → `reject` the candidate's events; replace it → `forget <old id>`, then `approve` the candidate; undecided → nothing.
- **Declined** ("no, don't learn that"): `reject <event ids>`, so it isn't offered again. Unchecked and skipped rows: nothing; they stay in the log.
- `approve` exits 2 with "candidate is stale" (its events were used meanwhile): run `lessons` again and redo that row.

Report what was written: new rules (id, text, param), confirmations, rejected events.

## 4. show and forget

- `show`: `memory.py show --memory "<M>"` → the rules (id, text, skill / kind / format, param, confirmed, created, evidence) and the open candidates. Writes nothing.
- `forget $id`: show that rule (text, param, evidence) and ask; after the yes, `memory.py forget $id --memory "<M>"`. Its events keep their `rule_id`, so they aren't proposed again. Unknown id: say so and list the rules.

## 5. What it doesn't see

Every `learn` report lists it:

- Volume keyframes (no API), grades, keyframes of Transform and other inputs inside Fusion comps (the moves of screen zooms included), and Fusion tools other than the first Text+ (its text, `Center` and `Size` are compared).
- Edits to items no skill recorded in a ledger: cuts on A-roll, B-roll, music, the user's own titles. They are logged as owner `user` and never become rules, so cut decisions of `text-based-cut`, `split-edits` and `sound-design` aren't learned. The same holds for every `cut_changed` and for moving or trimming a media item (A-roll, Screen, B-roll, PiP footage) even when a skill recorded it (the zooms on a screen recording, a PiP): where footage sits is the user's cut; only Fusion comps and generators keep their skill as owner for timing, and property changes keep it on any item.
- Edits on a timeline without an earlier snapshot (from before this skill, or a copy Claude never handed off).
- Items that lost their id (Resolve restart, blade in the UI: unverified) are matched by content, which can miss an edit or read one as delete + add.

## Never

- Write, confirm, reject or forget a rule without the user's answer for that row, or edit `edit-memory.json` or the event log by hand.
- Show candidates at the start of a skill: only at a skill's end, an `edit-episode` stop or `learn`.
- Turn owner `user` events, or shifts that a cut rippled into, into rules.
