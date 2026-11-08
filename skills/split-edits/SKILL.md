---
name: split-edits
description: J-cuts and L-cuts (split edits) in DaVinci Resolve Studio 21+ - finds joins where the picture source really changes (another clip or take on A-roll, camera / screen / PiP switches, B-roll with live sound), proposes J or L with a shift in frames, rejects every proposal that would let cut-out words be heard, leave a mouth moving without sound, clip a word or run past the media, and after approval builds it without touching video items (audio laid with the split while assembling, or trimmed / relaid on a copy of the cut timeline). Handles the user's Cocoa markers with the note J / L / split.
when_to_use: User wants J/L cuts, split edits, sound leading or trailing the picture, smoother joins between takes or between camera and screen, live sound of B-roll before / after the insert; stage B of edit-episode after text-based-cut and dual-video-sync-pip; Cocoa markers whose note says J, L or split. Triggers - "зроби J-кати", "L-кат", "розділені склейки", "split edit", "хай звук іде раніше картинки", "звук наступного плану заходить раніше", "згладь склейки між дублями", "J/L cuts".
argument-hint: "[timeline] [auto|markers]"
arguments: [timeline, scope]
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *split_edits.py *)"
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

# Split edits (J and L)

Follow `resolve-core` first. Timeline: `$timeline` (default: the current one). Scope: `$scope` — `auto` (default: candidates + the user's markers) or `markers` (only the user's Cocoa J/L/split markers).

Edit memory (`resolve-core` §11): learn at the start, read this skill's rules before the plan, and take a snapshot as the last step of every write.

A **J-cut**: the next shot's sound starts before its picture, so the change feels expected. An **L-cut**: the picture has changed, the previous sound runs on under it, so a thought ends without being chopped. Same mechanics, opposite direction — one skill.

Script: `${CLAUDE_SKILL_DIR}/scripts/split_edits.py` (selftest: `python3 ${CLAUDE_SKILL_DIR}/scripts/split_edits.py selftest`). All frame math lives there; don't redo it by hand.

## Only where the picture source changes

The plugin's footage is mostly one camera, one voice, cut by text. Shift the sound at a jump cut inside one clip and one of three things happens: words that `text-based-cut` removed come back ("стоп, ще раз"), the first word of the next segment is clipped, or the same face moves its mouth with no sound. So:

| Join | What moves | Usually | How |
|---|---|---|---|
| A-roll: another clip / take | Voice boundary between the two clips | J (new take's room tone leads in) | `joins` |
| Camera ↔ Screen / PiP (tutorials) | the moment the picture switches, relative to the phrase | L into the screen (it appears once the phrase about it began); J back to camera (the voice returns first) | `sections` — before `dual-video-sync-pip` places the Screen items |
| B-roll with live sound | its own sound on `Ambience` before / after the picture | J in, L out | `ambience` |
| Chapter boundary (Blue) | music or ambience of the next chapter starts earlier | J | hand to `sound-design` as a Sky cue a few frames before the chapter |

Never: a join inside one clip from one camera. A punch-in (`tutorial-zooms`) does not change the source — still a jump cut. Two speakers on two cameras with crossfaded overlapping voices (Voice / Voice 2), volume keyframes, nested timelines and multicam are out of scope: say so if asked.

## Hard checks (the script runs them on every proposal)

A proposal that fails any of them is rejected with the reason, and the user sees the reason:

1. Nothing cut is heard: the extra sound contains no transcript words and doesn't overlap a `cut` from `cuts.json`.
2. Silent picture: where a speaker's picture plays over the other clip's sound, that speaker says nothing in those frames.
3. Media exists: the shift fits in the media handle (`GetLeftOffset` / `GetRightOffset`, in the dump as `left_offset` / `right_offset`).
4. Not mid-word: the shortened side keeps ≥ 0.15 s (`--handle-ms 150`) between the new boundary and the nearest word.
5. Sync: after the build, every Voice item sits exactly under the A-roll item of its clip (`verify`).

Craft defaults from the plugin config (starting values; the user tunes them after a few episodes): J lead `${user_config.split_j_lead_frames}`, L tail `${user_config.split_l_tail_frames}`, max shift `${user_config.split_max_frames}` (more is a scene overlap, not a cut), fade `${user_config.split_fade_frames}`, at most `${user_config.split_max_in_row}` split edits in a row. When the user asks to break a rule below, do it and say what it costs:
- J fits the start of a new thought or chapter, L the end of a thought or a reaction.
- Voice shifts stay shorter than ambience or music shifts: a voice detached from its face shows.
- No split next to a transition (Cocoa) or a zoom (Pink) within 1 s: the viewer gets two changes at once. Automatic candidates there are rejected; a user marker there is kept with a warning.

## The user's markers

No color of its own (all 16 are taken): **Cocoa** (`transition` in `${user_config.marker_colors}`) with a note:

| Note | Meaning |
|---|---|
| `J` / `L` | that type, default shift |
| `J 10`, `L 20` | type and shift in frames |
| `split` | Claude picks type and shift and explains |

The note is only that: `J`, `L` or `split`, optionally followed by frames (`J10` and `J 10` are the same). Anything else ("Light leak", "L-подібний шторка") is a transition name.

Cocoa without these words stays a MotionVFX transition (`marker-edit`). The marker belongs on a join; one more than 1 s from any A-roll join comes back as a question — ask, don't guess. A user marker overrides the automatic choice at its join but **not** the hard checks: if it fails one, explain why and offer the other type or a shorter shift.

## Two ways to build

- **Mode 1 — while placing (preferred, nothing is deleted).** `text-based-cut` asks for J/L at clip changes before it appends (it runs `joins --rough`, below, and appends Voice from the `audio` result); `dual-video-sync-pip` runs `sections` on its `pip-input.json` before `pip_plan.py`; B-roll live sound is only ever *added* on Ambience.
- **Mode 2 — on a cut timeline.** Work on a duplicate (`DuplicateTimeline`, `resolve-core` §3); the original stays as it was. Resolve 21.1.2+ (version gate, `resolve-core` §10): one edge trim per split on the Voice item whose sound is extended, in place; its neighbour's edge is overwritten, nothing is deleted. Older: per changed Voice item record its properties, unlink, delete **only that audio item** (no ripple), append it again with the new range, relink, restore. **Video items are never relaid or trimmed** — relaying would erase zooms, Fusion comps, PiP transforms and grades. That's why camera ↔ screen splits on a timeline whose Screen items are already placed are reported, not built: offer to re-run `dual-video-sync-pip` on a copy with the shifted sections, or move the edits by hand.

## 1. Connect and read

1. `resolve-core`: connection, say the project and timeline names, save the project. `work` = `${user_config.work_dir}/<project>`.
2. Append calibration (`resolve-core/reference.md#append-calibration`) once per session: `endFrame` inclusivity and the source offset.
3. Fresh timeline dump (`resolve-core/reference.md#timeline-dump`, it carries `left_offset` / `right_offset` and the timeline markers) to `<work>/timeline-<name>.json`. Transcripts in `<work>/transcripts/` (none → run `uk-transcribe`).

## 2. Candidates and checks

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/split_edits.py joins --dump "<work>/timeline-<name>.json" --transcripts "<work>/transcripts" \
  --cuts "<work>/cuts.json" --source-offset <calibration offset> --colors "${user_config.marker_colors}" \
  --previous "<work>/split-plan.json" --j-lead ${user_config.split_j_lead_frames} --l-tail ${user_config.split_l_tail_frames} \
  --max ${user_config.split_max_frames} --fade ${user_config.split_fade_frames} --max-in-row ${user_config.split_max_in_row} \
  --out "<work>/split-plan.json"
```

(`--cuts` only if it exists. `--previous` keeps joins the user already decided on in mode 1 from being asked again.) Scope `markers` → set every proposal with `"origin": "auto"` to `keep` without asking.

Also, when relevant: `sections` (with `--j-lead` / `--l-tail` / `--max`) for a tutorial whose Screen isn't placed yet (it writes a shifted copy of `pip-input.json`; hand it to `dual-video-sync-pip`), and `ambience` for B-roll inserts — keep only rows whose clip has audio (`clip.GetClipProperty()["Audio Ch"]` > 0) and that the user wants heard.

## 3. Plan for approval

One table in time order, then the rejected ones as a short list with reasons, then questions:

| # | TC | Join (clip → clip) | Type | Frames | Words around the join | Why |

Words around the join come from `timeline_map.py words` (last words before, first words after; mark which sound moves). Timecodes via `tc.py`. Approve in one round (AskUserQuestion multiSelect, or free text like "all except 3; 5 as L 8"). Write each proposal's `decision` (`split` / `keep`, and `type` / `frames` if the user changed them) into `split-plan.json`. Then:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/split_edits.py audio "<work>/split-plan.json" --out "<work>/split-audio.json"
```

It re-runs the hard checks on what the user decided, so an edited shift that no longer fits is refused — tell the user, don't force it.

## 4. Build (mode 2)

1. Duplicate the timeline (`f"{name} - split {YYYY-MM-DD}"`), make the copy current, work only on it. Dump it again: rows in `split-audio.json` find their Voice item by `current` (record start/end) and `clip_id`.
2. **Resolve 21.1.2+: trims** (`resolve-core/reference.md#resolve-2112-editing-calls`). `split-audio.json` → `trims` has one row per split: the Voice item, `edge` and `frames` (k).
   1. Get every row's item object from the copy *before* the first call (each call moves edges, so `current` stops matching later). Note any audio transition at the moved joins (a 2-frame crossfade from `text-based-cut`): how it behaves under a trim is unverified, re-read it afterwards and report anything odd.
   2. Per row, read the offset right before the call: `edge` `left` (J) → `item.SetLeftOffset(item.GetLeftOffset() - k, False, False)`; `right` (L) → `item.SetRightOffset(item.GetRightOffset() - k, False, False)`. Always `updateLinkedItems=False`: the video stays where it is.
   3. After the **first** trim re-read both Voice items and both A-roll neighbours. A video edge that moved, or a `False` back → stop, report, and build all splits with the relay below on a fresh copy.
   4. `SetFades({"FadeIn": fade_in, "FadeOut": fade_out})` from the `audio` rows on the moved ends; re-read `GetFades()`.
3. **Older Resolve: relay.** In this order — an L makes the earlier item reach into the space the next one still occupies, so nothing is appended until every changed item is gone:
   1. For every row: read and keep `GetProperties()` (`AudioVolume`, `AudioVolumeEnabled`, pan), `GetFades()`, `GetVoiceIsolationState()`, `GetClipColor()`, the linked video (`GetLinkedItems()`), and any audio transition at its ends (a 2-frame crossfade from `text-based-cut` is lost with the item).
   2. One guarded call: `tl.SetClipsLinked([video, audio], False)` for each, then `tl.DeleteClips(all_changed_audio, False)` (no ripple). The guard asks the user: say which audio items go and that they come back at once with the new ranges.
   3. Re-dump the A-roll track: item count and positions must be unchanged. If any video went with the audio, stop and report (the copy protects the original, but nothing else may run).
   4. Append every row: `mp.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": source_start, "endFrame": <per calibration>, "mediaType": 2, "trackIndex": voice, "recordFrame": record}])` (`source_*` in the file are already API frames).
   5. Relink each to its video item, restore volume, voice isolation and color, `SetFades({"FadeIn": fade_in, "FadeOut": fade_out})` on the moved ends (the old fade at the unmoved end), re-add the crossfades recorded at unmoved ends.
   6. Fades vs. crossfade: `SetFades` on the moved ends is the default. If `text-based-cut` already put 2-frame audio crossfades at joins, keep them where the join didn't move. Whether `SetFades` survives relinking is unverified — re-read `GetFades()`.
4. Ambience rows: `track_index(tl, "audio", "Ambience", create=True)` (`track-layout`; `Ambience 2` for `B-roll 2`), append `mediaType: 2` with `recordFrame: record`, fades. Only adding.

Mode 1 needs none of this: `text-based-cut` appends Voice from `split-audio.json` (`"mode": "rough"`, every segment listed, record frames relative to the timeline start).

## 5. Verify

Dump the copy again, then:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/split_edits.py verify "<work>/timeline-<copy>.json" "<work>/split-audio.json"
```

Plus by hand: item counts per track as before (Ambience added), timeline end frame unchanged, every A-roll / Voice pair linked. If something is off after trims, the copy is the safety net; to undo one split instead, set both items' recorded offsets back (the extended item first). Anything off → report the item and timecode; never nudge silently.

## 6. Mark and report

- On each split: a timeline marker in **Cream**, name `J` or `L`, note = shift and reason, `customData` = `claude:split`, duration 1 — the user can step through them and remove all Cream at once.
- Handled user markers: `customData` = `claude:done:split-edits:<YYYY-MM-DD>` (`UpdateMarkerCustomData`, re-read); never change their color, name or note.
- `track-layout` recolor, save the project.
- Report: timeline copy name, splits by type with timecodes, rejected with reasons, camera ↔ screen splits not built (and why), Ambience inserts, what to listen to (the first J and the first L).

## Never

- Change or delete the original timeline, or relay or trim a video item.
- Build a split that failed a hard check, even when a marker asks for it.
- Split a join inside one clip.
- Leave the copy with unlinked or out-of-sync A-roll / Voice pairs.
