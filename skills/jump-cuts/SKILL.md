---
name: jump-cuts
description: Judges every jump cut of a talking-head cut in DaVinci Resolve Studio 21+ and gives each one the lightest treatment that hides it - exports the frame before and after each A-roll join, measures how far the picture jumps, looks at both for closed eyes, a mouth mid-move and a shifted pose, then decides join by join - leave it (hidden under B-roll, a source change, or a jump too small to see), roll the cut a few frames inside the removed pause without touching a word, a Smooth Cut where the pose matches, a punch-in whose scale is planned along the whole chain of segments, or a Cream marker advising cover footage where nothing fits. Shows the table for approval and applies it on a copy of the timeline.
when_to_use: User wants jump cuts hidden, softened or checked after a rough cut, punch-ins on a talking head, Smooth Cut on joins, or asks which cuts look bad; stage B of edit-episode after split-edits and before sound. Triggers - "сховай джамп-кати", "згладь склейки", "оціни склейки", "приховай склейки", "зроби punch-in", "punch in", "smooth cut", "hide the jump cuts", "jump cuts".
argument-hint: "[timeline] [all|markers]"
arguments: [timeline, scope]
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "mcp__DaVinci_Resolve__get_image"
  - "mcp__DaVinci_Resolve__get_thumbnails"
  - "Bash(python3 *jump_cuts.py *)"
  - "Bash(python3 *zooms.py *)"
  - "Bash(python3 *timeline_map.py *)"
  - "Bash(python3 *tc.py *)"
  - "Bash(python3 *memory.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Jump cuts

Follow `resolve-core` first. Timeline: `$timeline` (default: the current one). Scope: `$scope` — `all` (default) or `markers` (only joins whose Cream `cut` marker the user extended with the word `jump` in its note).

Edit memory (`resolve-core` §11): learn at the start, read this skill's rules before the plan, and take a snapshot as the last step of every write.

A jump cut is a join inside one shot: same clip, same framing, the speaker's head snaps to a new place. Most of them need nothing. The skill looks at each join and picks the lightest treatment that works, instead of punching in on every second segment.

Script: `${CLAUDE_SKILL_DIR}/scripts/jump_cuts.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/jump_cuts.py selftest`). It owns `<work>/jump/joins.json`: every decision and every scale comes from it, never from a hand edit of the JSON. Resolve scripts: [reference.md](reference.md). Settings: threshold `${user_config.jump_diff_threshold}`, punch-in scale `${user_config.punch_in_scale}`.

## The ladder

The first rule that fits decides.

| # | When | Decision |
|---|---|---|
| 1 | the join is under a B-roll / Screen item | `hidden` — nothing |
| 2 | the clip changes, or the source goes backwards (another take) | `source-change` — nothing; that is `split-edits` work |
| 3 | frame difference below the threshold | `leave` |
| 4 | the last frame before or the first after has closed eyes or a mouth mid-move, and the cut can move inside the removed pause | `roll` by k frames |
| 5 | difference below 3 × threshold, same pose, still background, ≥ 3 frames of media beyond both edges | `smooth-cut`, 6 frames |
| 6 | a visible jump and both neighbours may change scale | `punch` |
| 7 | anything else | `cover` — a Cream marker advising B-roll or the screen |

A segment keeps 100 % when it is shorter than 2 s (a size jump every second is worse than the jump cut), has its own Inspector transform (PiP, the user's reframe) or lies entirely under B-roll / Screen. Punch-in is a state of a segment, not of a join: segments joined by `leave`, `roll` or `smooth-cut` share one scale, a `punch` join needs two different ones, and the script plans that along the whole chain.

## 1. Inputs

`work` = `${user_config.work_dir}/<project name>`. Remember the user's current timeline (name, `GetUniqueId()`); make `$timeline` current.

1. The A-roll track is locked → stop and say so; never unlock it (in `edit-episode` this skill runs before the sound lock).
2. Timeline dump (`resolve-core/reference.md#timeline-dump`) → `<work>/timeline-<timeline>.json`.
3. A-roll items with a non-default transform ([reference.md](reference.md#transforms)) → their ids.
4. ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/jump_cuts.py joins "<work>/timeline-<timeline>.json" --transcripts "<work>/transcripts" \
     [--fixed-transform <item id> ...] [--source-offset <append calibration offset>] --out "<work>/jump/joins.json"
   ```
   `"joins": 0` → nothing to treat; say so and stop. No transcripts → `roll` is off for every join (`roll_range` null); say so in the report and go on.
5. `$scope markers`: for every treatable join whose marker note lacks the user's `jump`, run `jump_cuts.py decide "<work>/jump/joins.json" --join <id> --decision leave --scale ${user_config.punch_in_scale}` now; those joins are not measured or looked at.

## 2. Measure and look

Only joins that are not `covered`, `source_change` or `skip` (read them with `jump_cuts.py table`).

1. Export the frame before and the frame of each join ([reference.md](reference.md#export-frames)), up to 40 joins per call, to `<work>/jump/<id>-a.tif` and `<id>-b.tif`. Needs Resolve 21.1.2 (`resolve-core` §10). Older: skip the export, look at both frames with `get_image` (`source` "timeline", the join's TC and one frame earlier), pass no `--diff`, and say in the report that nothing was measured.
2. `python3 ${CLAUDE_SKILL_DIR}/scripts/jump_cuts.py diff "<a.tif>" "<b.tif>"` → `diff` (whole frame, 0..1) and `max_cell` (the most changed of 8 × 8 cells: a small `diff` with a large `max_cell` is a head that moved on a still background).
3. Joins with `diff` ≥ `${user_config.jump_diff_threshold}`: Read both stills and note
   - `--blink left|right`: eyes closed or half closed on the last frame before (`left`) or the first after (`right`);
   - `--mouth left|right`: the mouth caught mid-move on that frame;
   - `--pose`: `same` (head and shoulders in place, only the face changed), `shifted` (the head moved), `different` (posture, hands or framing changed);
   - `--background`: `moving` when anything behind the speaker moves (a screen, people, leaves).
4. One `observe` per join, also for those under the threshold (`--pose same --background static`):
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/jump_cuts.py observe "<work>/jump/joins.json" --join <id> --diff <diff> --max-cell <max_cell> \
     [--blink left|right] [--mouth left|right] --pose same|shifted|different --background static|moving
   ```
5. First run in a project: show the user the pair with the lowest and the pair with the highest `diff` and ask whether the threshold separates "can't see it" from "jumps" for this footage. Their number goes to `--threshold` for this run; a lasting change is theirs to make in the plugin settings.

## 3. Decide

1. `python3 ${CLAUDE_SKILL_DIR}/scripts/jump_cuts.py classify "<work>/jump/joins.json" --threshold <threshold> --scale ${user_config.punch_in_scale}`
2. For every `roll`: `get_thumbnails` over the frames inside its `roll_range` around the join and pick `k` (negative = earlier) where the eyes are open and the mouth is at rest on both sides; none → `decide … --decision punch`. Record it: `jump_cuts.py decide "<work>/jump/joins.json" --join <id> --decision roll --k <k> --scale ${user_config.punch_in_scale}`.
3. `jump_cuts.py table "<work>/jump/joins.json"` → show it in the user's language: TC, what was removed, difference, decision, scale left → right, reason, and the stills of every join that changes. List the edit-memory rules applied.
4. One approval round. Each change of the user: `decide … --join <id> --decision leave|roll|smooth-cut|punch|cover`. The script refuses a `punch` it can't give two different scales and a `roll` outside the range: tell the user why instead of forcing it.

Nothing changes in Resolve before the yes.

## 4. Apply

On a duplicate ([reference.md](reference.md#duplicate)): `<name> - jump <YYYY-MM-DD>`, made current; the original stays as it was. Save the project first. Write the state before the changes (offsets, start / end and `GetProperties()` of every A-roll item, offsets of every Voice item) to `<work>/jump-before.json`. Then, in this order:

1. **`roll`** ([reference.md](reference.md#roll)): the video edge and the Voice edge move by the same `k`, each with its own call, `updateLinkedItems` False. After the **first** join re-read both items and their neighbours on both tracks: a `False`, an edge that didn't land where the script says, or a third item that moved → stop and report; the copy holds the damage. After each roll: `jump_cuts.py rolled … --join <id> --k <k>`, export the two new frames, `diff`, look, `observe`. When all are rolled, `classify` again: a rolled join is never rolled twice.
2. **`smooth-cut`** ([reference.md](reference.md#smooth-cut)): the transition's type name and category are unverified. Add it to the first join only, re-read the track for an item of type `transition` at the join with the asked duration, and look at the middle frame with `get_image`: a warped face → remove nothing, tell the user, and treat the rest as below. The API returns `None` or the look is wrong → `decide … --decision punch` for every `smooth-cut` join (`cover` where the script refuses), and list those joins in the report for a manual Smooth Cut (Edit page → Effects → Video Transitions → Smooth Cut).
3. **`punch`**: segments whose `scale` in `joins.json` is not 1.0. Face position once per shot setup: a still from the middle of its first segment, Read it, the point between the eyes as `X Y` (0..1 from the top-left). `python3 ${CLAUDE_SKILL_DIR}/../tutorial-zooms/scripts/zooms.py punch --width <w> --height <h> --scale <scale> --face X Y` → `ZoomX/ZoomY/Pan/Tilt`; `item.SetProperties(props)`, re-read `GetProperties()` ([reference.md](reference.md#punch)). Pan / Tilt units are in the runtime-discovery list of `resolve-core`: do the first segment, export a still, check that the eyes stayed where they were and no black edge shows, then the rest.
4. **`cover`** ([reference.md](reference.md#cover-marker)): Cream marker, name `jump`, note = the advice (what to put over it and for how long), `customData` `claude:jump:cover`.

Punch-ins are not recorded in the placed-items ledger: they reframe the A-roll itself, nothing is placed over the picture.

## 5. Verify

Dump the copy again and compare with the dump from §1:

- the same number of A-roll and Voice items, the same timeline end;
- every item start / end unchanged, except the two edges of each rolled join, which moved by exactly `k`;
- `python3 ${CLAUDE_SKILL_DIR}/../resolve-core/scripts/timeline_map.py words …` on the copy has the same words in the same order as before the rolls;
- every punched segment reads back its `ZoomX`, every other A-roll item its old properties.

Anything that doesn't match: report it with the join id and stop. Don't nudge it right silently; the original timeline is intact and the copy is there to look at.

## 6. Finish

Add the decision to the note of each Cream `claude:cut` marker on the copy only if the user wants it (their note text stays, the decision is appended). Snapshot (`resolve-core` §11). Save. Make the user's timeline current again unless they want to stay on the copy.

Report in the user's language (Resolve names in English): the copy's name; joins per decision; every `roll` (TC, k) and `smooth-cut`; segments punched in; `cover` joins with the advice; what was not measured or not verified; how to undo (the original timeline is untouched; `jump-before.json` holds the old values).

Next in `edit-episode`: sound (`voice-isolation`). B-roll over the `cover` markers is the user's call (Fuchsia markers, `marker-edit`).

## Never

- Change the original timeline, or apply anything before the user's yes.
- Roll a join with a `claude:split` marker, roll a cut into a word, or roll the picture without its sound.
- Punch in on a segment shorter than 2 s, on an item with its own transform, or by a scale other than `${user_config.punch_in_scale}`.
- Place B-roll or any other item: `cover` is advice.
- Edit `joins.json` by hand, unlock a track, or delete a marker that isn't Cream `claude:jump:*`.
- Leave the copy current when the user had another timeline open and didn't ask for it.
