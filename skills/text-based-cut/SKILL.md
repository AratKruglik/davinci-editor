---
name: text-based-cut
description: Builds a rough cut in DaVinci Resolve Studio 21+ from word-level transcripts - finds failed takes, false starts, repeats, filler sounds, long pauses and dead head/tail, shows the cut list for approval, then assembles a NEW timeline from the kept ranges (source timeline is never modified) with review markers at every join.
when_to_use: User wants the "fish" / rough cut of a talking-head video, tutorial or podcast, or to remove pauses, filler words and failed takes; also stage B of edit-episode. Triggers - "зроби рибу", "чорновий монтаж", "виріж паузи і дублі", "прибери слова-паразити", "монтаж за текстом", "rough cut from transcript".
argument-hint: "[bin path] [gentle|normal|tight]"
arguments: [scope, pace]
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_docs"
  - "Bash(python3 *cut_candidates.py *)"
  - "Bash(python3 *tc.py *)"
  - "Bash(python3 *split_edits.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Text-based rough cut

Follow `resolve-core` first. Scope: `$scope` (default `${user_config.footage_bin}`). Pace: `$pace` (default `normal`).

Principle: the script proposes, the editor decides. Nothing is cut without the user's approval, and the result is a new timeline next to the untouched source.

## 0. Inputs

`work` = `${user_config.work_dir}/<project name>`. Transcripts must exist in `<work>/transcripts/*.json` (format from `uk-transcribe`). Missing or stale → run the `uk-transcribe` skill first.

Ask the clip order if more than one clip: by file name (default), by Start TC, or a user list. Write it down; assembly follows it.

## 1. The user's markers

The user's own markers outrank every automatic suggestion (color map in `${user_config.marker_colors}`):
- **Red** = cut: a point marker cuts the phrase/take around it (bounds from the transcript), a marker with duration cuts exactly that range;
- **Green** = keep / best take: protects the phrase or range; among repeats of a phrase, the Green take wins;
- **Yellow** = doubt: Claude proposes options and asks; never decides alone.

Read them from the media pool clips (`clip.GetMarkers()`, frames from clip start — the normal place before the cut) and, if the source is already a timeline, from its items (convert to source frames: `item.GetSourceStartFrame()` + offset). Skip markers whose `customData` is `claude:done:*`. Write them to `<work>/markers.json` as `[{"id": "<clip>@<frame>", "clip", "frame", "duration", "color", "task": "cut|keep|doubt", "note"}]`.

## 2. Mechanical candidates

Pace presets (pause threshold / handle): `gentle` 1200 / 200 ms, `normal` ${user_config.pause_threshold_ms} / ${user_config.cut_handle_ms} ms, `tight` 450 / 80 ms.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/cut_candidates.py analyze "<work>/transcripts" --out "<work>/cuts.json" \
  --fillers "${user_config.filler_words}" --soft-fillers "${user_config.soft_filler_words}" --pause-ms <ms> --handle-ms <ms> \
  --markers "<work>/markers.json"
```

Candidate types and default decision:

| type | what | default |
|---|---|---|
| `head` / `tail` | silence before the first / after the last word | cut |
| `pause` | silence longer than the threshold; handles are kept on both sides | cut |
| `filler` | hard fillers (е, ем, мм…) | cut |
| `soft_filler` | ну, типу, коротше… — often meaningful | review |
| `repeat` | immediately repeated 2–4 words ("я хочу я хочу") | cut; single word: review |
| `marker` | the user's Red (cut) or Yellow (review) marker; Green turns overlapping candidates into `keep` and, on an earlier take, proposes cutting the later repeat | as marked |
| `retake` | segment whose opening matches a later segment within 45 s → earlier take; also the end of a clip that restarts at the beginning of the next clip (file-name order) | review |

## 3. Editorial pass (your judgment)

Read `<work>/transcripts/*.txt` and the candidates. Add what a script cannot see, as candidates with `"type": "editorial"`, `"decision": "review"`, a clear `"reason"`:
- a sentence abandoned midway and restarted differently (not caught as `retake`);
- slips and corrections ("ой, не так", "стоп, ще раз", "давай заново", "вибачте"), talk to the crew, counting in;
- the weaker of two takes when the user says which matters (default: keep the **last** complete take — presenters usually improve);
- coughs, laughter-breaks, phone noise the transcript marks.

Frames for your candidates: take word `start`/`end` from the clip JSON and convert with `python3 ${CLAUDE_SKILL_DIR}/../resolve-core/scripts/tc.py to-frames <tc> --fps <fps>` minus the clip's `start_tc` frames. Cut from the first removed word's start to the next kept word's start minus the handle.

Rules of a good cut (tell the user when a proposed cut breaks one):
- Don't cut inside a word or between a word and its breath out; cut in pauses.
- Keep ≥ 0.15 s before the first word after a cut, otherwise the attack sounds clipped.
- Don't remove every pause: tutorials need beats after key points. `tight` is for Shorts, not lessons.
- Never cut the meaning: if removing a soft filler changes intonation into a non-sentence, keep it.

## 4. Approval

Present the user's marker decisions first (they are already decided, shown for transparency; conflicts like Red inside Green are questions), then a compact list grouped by type with counts and time saved, then every `review` item with its id, timecode (clip TC), text in `[brackets]` within context and reason. Ask in one round (AskUserQuestion, multiSelect per group, or free text like "keep 12, 15; cut the rest"). Set every candidate's `decision` to `cut` or `keep` in `cuts.json`. Nothing may stay `review`.

## 5. Plan

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/cut_candidates.py assemble "<work>/cuts.json" --out "<work>/plan.json"
```

It refuses while any `review` remains, drops slivers that contain no speech, and prints duration before → after. Show that to the user. Reorder `plan.json` entries if the clip order chosen in step 0 isn't file-name order.

**Split edits at clip changes** (only if neighbouring segments come from different clips or takes; `split-edits` mode 1, nothing is deleted later). Write `<work>/clip-frames.json` = `{clip_id: int(clip.GetClipProperty()["Frames"])}`, then:

```bash
python3 ${CLAUDE_SKILL_DIR}/../split-edits/scripts/split_edits.py joins --rough "<work>/plan.json" --frames "<work>/clip-frames.json" \
  --transcripts "<work>/transcripts" --cuts "<work>/cuts.json" --j-lead ${user_config.split_j_lead_frames} --l-tail ${user_config.split_l_tail_frames} \
  --max ${user_config.split_max_frames} --fade ${user_config.split_fade_frames} --max-in-row ${user_config.split_max_in_row} --out "<work>/split-plan.json"
```

Offer its proposals (J/L, frames, words around the join, reason; rejected ones with reasons) as one more approval round, as `split-edits` §3 describes; set each `decision` and run `split_edits.py audio "<work>/split-plan.json" --out "<work>/split-audio.json"`. No proposals or all `keep` → skip; Voice mirrors A-roll as usual.

## 6. Build the new timeline

1. Run the append calibration from `resolve-core` (once per session) to know `endFrame` inclusivity and source offset.
2. Map `clip_id` → media pool item by walking all folders and matching `GetUniqueId()`.
3. `mp.CreateEmptyTimeline(f"{source_name} - rough cut {YYYY-MM-DD}")` (unique name; append ` v2`… if taken). Check its settings match the source timeline (resolution, fps); if the project default differs, set `useCustomSettings` and copy them before adding clips.
4. Tracks: run `track-layout` setup on the new (empty) timeline first, then get indices by role: video `A-roll`, audio `Voice` (`track_index` from `track-layout`). Never assume V1/A1 — in the standard layout V1 is Backgrounds.
5. Append in order, contiguous, batches of ≤ 50 per call — video to A-roll and audio to Voice as two entries per segment:
   `{"mediaPoolItem": item, "startFrame": start + offset, "endFrame": end_for_api, "mediaType": 1, "trackIndex": a_roll, "recordFrame": tl.GetStartFrame() + running_total}` and the same with `"mediaType": 2, "trackIndex": voice`.
   With approved split edits, the audio entries come from `split-audio.json` instead (same order as `plan.json`): `startFrame` = `source_start` + offset, end from `source_end`, `recordFrame` = `tl.GetStartFrame()` + `record`; afterwards `SetFades` on rows with `fade_in` / `fade_out`.
   Then relink each video/audio pair with `tl.SetClipsLinked([video_item, audio_item], True)` and verify it (whether separate appends keep the link is unverified; linking explicitly is safe either way). Camera audio with several channels: check `clip.GetAudioMapping()` once and tell the user which channels landed on Voice.
6. Verify: number of video items on A-roll and audio items on Voice == plan entries; each item's `GetDuration()` equals the planned length (for Voice with split edits: `source_end - source_start` from `split-audio.json`); timeline end == start + total. Report any mismatch with the entry id — don't "fix" by nudging silently.
7. At every join add a timeline marker in **Cream** (a split join gets the `split-edits` marker instead: name `J` / `L`, `customData` = `claude:split`) (Claude's color; Blue means "chapter" for the user), name `cut`, note = removed text/type, `customData` = `claude:cut`, duration 1, so the user can review jump cuts quickly and delete them all with `DeleteMarkersByColor("Cream")`.
8. Optional (ask): 2-frame audio crossfades at joins against clicks: `item.AddTransition({"type": "Cross Fade +3 dB", "category": "audio", "position": "end", "alignment": "center", "duration": 2})`. Try on the first join, check the result, then continue; if the API refuses, tell the user (Fairlight → select all → Ctrl/Cmd+T does it manually).
9. Grades: check `GetCurrentVersion()` on a few items; load the remote `claude` version where needed (see `resolve-core` §7), or `CopyGrades` from the source timeline item.
10. Mark the user's handled markers: `clip.UpdateMarkerCustomData(frame, "claude:done:text-based-cut:<date>")`, re-read; never change their color, name or note.
11. Run `track-layout` recolor on the new timeline, then save the project.

## 7. Report

Timeline name, duration before → after, cuts by type, ids the user kept, anything that didn't verify. Suggest next steps: watch the Cream `cut` markers, then `voice-isolation`, sound design, zooms on jump cuts.

## Never

- Modify or delete the source timeline or media.
- Assemble with undecided candidates or without user approval.
- Cut words the user asked to keep because "the script said so".
