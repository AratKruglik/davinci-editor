---
name: frame-critic
description: Checks the on-screen elements that davinci-editor skills placed in DaVinci Resolve Studio 21+ (lower thirds, callouts, kinetic phrases, counters, zooms, Shorts captions, PiP) - reading time, two titles at once, edges too close to a cut, zoom scale and caption speed by numbers, text bounds measured from two renders against the frame edge and the safe areas, then by eye for covered faces or demo, missing glyphs, weak contrast and inconsistent styling; records findings with a concrete fix for the owning skill, runs at most two fix rounds through that skill and marks what is left with Cream markers. Never moves or edits anything itself.
when_to_use: After fusion-motion-graphics, tutorial-zooms, subtitles-uk (shorts mode), dual-video-sync-pip or shorts-cutdown placed elements; edit-episode stage D runs it after each of them. Triggers - "перевір титри", "чи не вилазить текст", "чи встигну прочитати", "critic", "перевір графіку", "check the titles", "is the text cut off", "frame critic".
argument-hint: "[timeline] [all|<owner skill>]"
arguments: [timeline, scope]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "mcp__DaVinci_Resolve__get_image"
  - "mcp__DaVinci_Resolve__get_thumbnails"
  - "Bash(python3 *critic.py *)"
  - "Bash(python3 *placed.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Frame critic

Follow `resolve-core` first. Timeline: `$timeline` (default current). Scope: `$scope` (default `all`; or one owner skill, e.g. `fusion-motion-graphics`).

Script: `${CLAUDE_SKILL_DIR}/scripts/critic.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/critic.py selftest`). Resolve scripts: [reference.md](reference.md).

The critic looks at what the skills placed and says what is wrong, with numbers and a concrete fix. It never moves, trims, deletes or restyles an element and never edits a spec: the skill that placed the element owns it and re-applies it from its own spec, so the next run reproduces the fix. It doesn't judge taste, pacing or whether a graphic belongs at all; that is the judge's job. The only things it writes are its result files, two renders per text element, and Cream markers.

## 1. Inventory and numbers

1. Read the current timeline (name, `GetUniqueId()`) and keep it: you restore it at the end, also when you stop early. Make `$timeline` current ([reference.md](reference.md#make-the-checked-timeline-current)): the dump, `get_image` and `get_thumbnails` only see the current timeline.
2. Timeline dump (`resolve-core/reference.md#timeline-dump`) → `<work>/timeline-<timeline>.json`.
3. Ledger `<work>/placed-<timeline>.json`, written by the owner skills with `placed.py add` when they place an element. No ledger or no items: nothing was placed by a skill, so there is nothing to judge; say so and stop. A ledger whose `timeline_id` differs from the dump's belongs to another timeline: stop and say so.
4. ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/critic.py inventory "<work>/placed-<timeline>.json" "<work>/timeline-<timeline>.json" --out "<work>/critic/elements.json"
   ```
   Each element has `id` (`<owner>/<item_id>`, or `<owner>/<item_id>#<part>` for one of several elements inside one item: the captions of a Short's comp, the zooms of one clip), `kind` (`lower-third`, `callout`, `kinetic`, `counter`, `zoom`, `caption`, `pip`), `owner`, `spec`, `track`, `text`, `scale` and absolute frames `start`, `full` (fully in), `mid`, `hold_end`, `gone`, `end`. Report its `notes` (ledger entries no longer on the timeline). Items that are not in the ledger belong to the user (`owner: user`): never measure, judge or report them.
5. ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/critic.py check "<work>/critic/elements.json" "<work>/timeline-<timeline>.json" \
     --zoom-max ${user_config.zoom_max_scale} --cps-max ${user_config.subtitle_max_cps} --chars-max ${user_config.subtitle_max_chars} \
     [--rules <numeric rules file>] [--changed <element id> ... | --scope $scope] --out "<work>/critic-<timeline>.json"
   ```
   It writes the timeline `state`, the findings and the `verdict`. A new critic run calls `check` without `--changed`: it starts at round 1 and, for `all`, drops every earlier finding. With a `$scope` other than `all` it also passes `--scope $scope`: the measured and seen findings (§2–§3) of the other owners' elements stay, since this run doesn't look at them again; their round doesn't carry over. Only the re-check after an owner fix (§4) passes `--changed`. Kinds: `short-hold` (fully visible less than 0.5 s + characters / 14, at least 3 s for a lower third), `overlap` (two text elements on screen at once; a callout may sit over another title), `near-cut` (an edge closer than 6 frames to an A-roll / Screen cut; not for zooms and PiP, whose edges are those cuts), `zoom-scale`, `cps`, `chars`. Pass `--rules` only when `edit-memory` has numeric rules (`hold_extra_s`, `max_scale`) for these owners.

The numbers always run on every element, because an overlap needs all of them. `$scope` limits §2 and §3 to that owner's elements.

## 2. Measured bounds

For every text element (`lower-third`, `callout`, `kinetic`, `counter`, `caption`) on a video track, at its `full` frame:

1. One `run_script` per element ([reference.md](reference.md#measure-one-element)): record `GetIsTrackEnabled` of every video track, `ExportFrame` the full composite to `<work>/critic/<name>-on.tif` (`<name>` = `<item_id>`, plus `-<part>` when the element has one), disable only the element's track, `ExportFrame` to `<name>-off.tif`, restore the recorded state in `finally` and read it back. Offset = frame − `tl.GetStartFrame()`; `maxDimension` 0. Resolve writes with the Mac path, the shell reads with its own (`resolve-core` §8). Check both `success` and `restored`. `ExportFrame` needs 21.1.2 (`resolve-core` §10): on older Resolve skip this level, say so, and rely on §3.
2. `python3 ${CLAUDE_SKILL_DIR}/scripts/critic.py bbox "<on.tif>" "<off.tif>"` → the bounds of what the element adds to the frame and their `kinds` (`offscreen` error: touches the frame edge; `unsafe` error: outside action-safe 5 %; `unsafe-title` warn: outside title-safe 10 %). `bbox` null: nothing of the element renders at that frame (covered by an upper track or entirely off frame); record it as `offscreen` and look at the frame in §3.
3. Compare the boxes of elements visible at the same frame (a callout over another title is allowed in time, not on top of it): intersecting boxes → `overlap` (error).

A track holds one item per frame, so the difference is that one element. If the dump shows another item of the same track overlapping that frame (a transition), report `overlap` instead of measuring.

Record each finding with the bounds as evidence and a fix for the owner (§4):
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/critic.py add "<work>/critic-<timeline>.json" --severity error|warn --kind <kind> --element "<id>" \
  --tc <TC of the frame> --frame <frame> --message "<what is wrong, in numbers>" --still "critic/<name>-on.tif" --bbox x0 y0 x1 y1 \
  --fix-skill <owner> --fix-change "<concrete spec change>"
```
Never edit the JSON by hand: only `check` and `add` write findings.

## 3. By eye

For each element in scope: `get_image` (`source` "timeline", `timecode` of `full`) of the whole frame, then with `roi_x/roi_y/roi_width/roi_height` (0..1 fractions) around the measured box plus a margin, `max_dimension` 1600. Look for:

- `covers-face`: text over a face. Find the face zone on the frame (a round camera can be baked into a screen recording, so take it from the picture, not from the PiP track) and keep it as frame fractions per clip in `<work>/critic/faces.json` so later rounds reuse it.
- `covers-demo`: text over the part of the screen the speaker is talking about at that moment, from `<work>/words-<timeline>.json` (`timeline_map.py words`, `resolve-core` §4). No transcript for this timeline: skip this check and say so.
- `glyph`: boxes instead of letters, or a face other than `${user_config.brand_font}`.
- `contrast`: text hard to read against what is behind it.
- `inconsistent`: elements of one `kind` differ in position, size or motion. `get_thumbnails` (`source` "timeline", `start`/`end` around each element, `count` up to 48) over all elements of that kind.

Record each with `critic.py add` as in §2 (severity `error` when a viewer can't read it or a face or demo is covered, else `warn`).

## 4. Fix loop

A fix changes the timeline through the owner skill, so it starts only after the user agreed (in `edit-episode`, the stage D approval counts). The user asked for a report only, or declined: every finding stays open → §5.

1. Before each hand-off: `python3 ${CLAUDE_SKILL_DIR}/scripts/critic.py next-round "<work>/critic-<timeline>.json"`. Exit 1 ("max 2 rounds") means both fix rounds are used: stop fixing; what is open goes to §5.
2. With `$scope` other than `all`, the fix loop covers only that owner's elements: only their findings are handed off, and the rounds count only for them; findings carried over from other owners' elements are reported in §5, not handed off. Hand each owner its findings: element id, kind, TC, message and `fix.change`. The owner changes its own spec and re-applies only those elements; nobody edits them in Resolve by hand, the critic least of all. An owner that can't take the fix leaves the finding open.
3. Re-check: fresh dump, `inventory`, then `check` into the same file with `--changed` listing the elements the owners re-applied. With `--changed`, an existing file of the same timeline keeps its round from step 1 and the §2–§3 findings of the untouched elements; the `state` is new, so `critic.py stale` stays right. A re-applied element that came back with a new item id counts as changed automatically, because its old id is gone from the inventory. Repeat §2–§3 only for the changed elements.

`fix.change` names the owner's own parameter and a value, never "fix it":

| Owner | Typical changes |
|---|---|
| `fusion-motion-graphics` | `--hold-s` to the needed seconds; `--at X Y` for a callout; for a lower third (placed from its text width) a shorter `--text` / `--sub` or a line break, with the pixels to win (e.g. "right edge 1919 → ≤ 1824 px") |
| `tutorial-zooms` | scale at most `zoom_max_scale`; zoom center away from the edge |
| `subtitles-uk` | words per caption, line break, caption duration |
| `dual-video-sync-pip` | PiP corner or size |
| `shorts-cutdown` | segment in / out frames |

Timing fixes on edges (`near-cut`) name the frames to move the element by.

## 5. Report and markers

1. Cream marker on each open finding that has a frame ([reference.md](reference.md#cream-markers)): name = kind, note = message, `customData` `claude:critic:<kind>`, at frame − `start_frame`, a frame later if a marker already sits there. Re-read the markers. Remove Cream `claude:critic:*` markers from a previous run only after the user agrees (the guard will ask; name them).
2. Write `<work>/critic-<timeline>.md` in the user's language (Resolve names in English, `resolve-core` §9):

   **Verdict:** `PASS`, `PASS WITH WARNINGS` or `FAIL` from `critic-<timeline>.json`, with counts and the round.

   | # | TC | element | problem | changed / left | still |

3. Make the user's timeline current again and re-read it.
4. Show the report. `critic-<timeline>.json` (`verdict`, `state`) is what `pre-delivery-qc` reads; after any later edit `critic.py stale` reports it as outdated and the check runs again.

## Never

- Move, trim, delete, re-insert or restyle an element, or edit a spec or the ledger: the owner skill re-applies from its spec.
- Judge taste, pacing or whether a graphic belongs: that is the judge's job.
- Leave a track state changed: disabling, restoring and re-reading happen in the same script.
- Judge or report items that are not in the ledger (`owner: user`).
- Edit `critic-<timeline>.json` by hand, run more than two fix rounds, or change the user's markers.
- Leave the checked timeline current when the user had another one open.
