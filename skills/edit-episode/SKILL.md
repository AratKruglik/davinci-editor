---
name: edit-episode
description: Orchestrates a full episode edit in DaVinci Resolve Studio 21+ in a fixed order with an approval stop after every step - A) project and color before the cut (project-bootstrap, log-to-rec709, chart-match, natural-skin-grade, depth-background-blur), B) transcript, track layout, text-based rough cut, camera + screen PiP and J/L split edits (split-edits), C) sound (voice-isolation, sound-design, audio-finish), D) graphics, zooms, subtitles, chapters, Shorts, thumbnails, QC and delivery (fusion-motion-graphics, tutorial-zooms, subtitles-uk, chapters-markers, shorts-cutdown, thumbnail-frames, pre-delivery-qc, deliver); each stage starts from the user's colored markers and the progress is kept in episode.md so a later session can resume.
when_to_use: User invokes /edit-episode to run the whole pipeline on a new shoot or to resume it.
argument-hint: "[episode name] [from-stage A|B|C|D]"
arguments: [episode, from_stage]
disable-model-invocation: true
effort: high
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(python3 *show.py *)"
  - "Read"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Edit episode `$episode`

Progress saved so far: !`python3 ${CLAUDE_SKILL_DIR}/../resolve-core/scripts/show.py '${user_config.work_dir}/*/episode.md' 40 'no episode.md yet'`

`$episode` alone and a single letter A–D (`/edit-episode C`) means the stage, not the episode name. Run the steps in order, starting from `$from_stage` (default: the first unfinished step in `episode.md`, else A). Each step is a separate skill: invoke it, let it finish with its own verification, then **stop and ask the user to approve** before the next. Never chain two steps without an explicit "далі"/"go". The user may skip any step ("без chart-match"); record the skip and why.

Start: follow `resolve-core` §1–3 (connect, confirm project, save). Keep a running checklist in `${user_config.work_dir}/<project>/episode.md` (step, status `done|skipped|failed`, date, timeline names, notes) and update it after every step, so a later session resumes from it.

Every stage starts with `marker-edit` limited to that stage's colors (A: Sand; B: Red, Green, Yellow, Purple, Fuchsia, Cocoa; C: Lavender, Sky, Rose; D: Cyan, Pink, Blue, Mint, Lemon): the user's markers are the brief for the stage.

## Stage A — project and color before the cut

Grade all footage before cutting, in remote versions, so the grade follows every clip into the rough cut.

1. `project-bootstrap` — new project, bins, import, selects timeline. Skip if the project already exists and is sorted (offer its open-project mode if the media pool is messy).
2. `log-to-rec709` — applies the base template (`CHART` → `CST` → `PRIMARY` → `SKIN` → `DEPTH` → `LOOK`). An old template without `SKIN`/`DEPTH` → template upgrade (`resolve-core` §6) before step 4.
3. `chart-match` — only if a chart was shot (Sand markers or ask).
4. `natural-skin-grade` — per scene.
5. `depth-background-blur` — per scene, only for talking-head shots; ask whether the user wants it at all for this episode.

Approval: the user looks at 2–3 clips per scene in the viewer.

## Stage B — "fish" and rough cut

1. `uk-transcribe`.
2. `track-layout` — plan the tracks this episode needs (Screen + PiP for screen recordings / Purple markers, Voice 2 for a second speaker, B-roll 2 for overlapping Fuchsia); the new timeline gets them in `text-based-cut`.
3. `text-based-cut` with the Red/Green/Yellow markers (it has its own approval of the cut list) — builds the new timeline on A-roll + Voice.
4. Control: on the new timeline every video item has the remote `claude` version loaded (`GetCurrentVersion()`); fix per `resolve-core` §7. Check that the Color Group of a few items survived (unverified in 21.1.1); reassign from the source clips if not, because the `light`/`strong` depth blur lives on the group.
5. `dual-video-sync-pip` — tutorials with a screen recording only.
6. `marker-edit` for Fuchsia (B-roll inserts) and Cocoa (transitions) on the cut timeline.
7. `split-edits` — J/L cuts where the picture source changes and Cocoa markers with `J` / `L` / `split`. Clip changes were already offered in step 3 and camera ↔ screen switches in step 5 (mode 1); this step does the rest on a copy of the timeline. Before sound: `sound-design` and `audio-finish` build on the final audio boundaries.

Approval: the user watches the rough cut using the Cream `cut` markers.

## Stage C — sound

1. `voice-isolation` on the cut timeline's Voice track (and Rose markers about noise). Then lock A-roll and Voice with `track-layout lock sound` for the rest of the stage.
2. `sound-design` with the Lavender/Sky markers (its own cue-sheet approval and license check). Only if the user asks for live-sounding music, room on SFX, pan sweeps or vocals out of a song: `audio-effects` after it.
3. `audio-finish` — Rose markers, dialogue leveling, measured loudness to the target. Unlock them after it (`track-layout unlock sound`).

## Stage D — graphics, derivatives and delivery

Picture and sound of the episode are locked now: lock A-roll, B-roll and Voice (`track-layout lock graphics`) and keep them locked until `deliver`. Steps 2–6 need the words on the cut (`resolve-core` timeline dump): take one dump at the start of the stage and a fresh one after any step that changes items.

1. `fusion-motion-graphics` — Cyan markers, name plates, callouts; chapter cards only if the user wants them (after step 4, from its titles).
2. `tutorial-zooms` — Pink markers on the screen recording; `punch-in` for jump cuts in talking-head parts if the user wants it (it changes A-roll item transforms: unlock A-roll with `SetTrackLock` for this step only, lock it again after).
3. `subtitles-uk` — YouTube SRT (and the `Subtitles UA` track if wanted).
4. `chapters-markers` — Blue markers → `chapters.txt`.
5. `shorts-cutdown` — Mint markers / proposals → vertical timelines; each Short gets `audio-finish` and `subtitles-uk shorts`.
6. `thumbnail-frames` — Lemon markers → `thumbnail-brief.md`.
7. `track-layout cleanup` (empty tracks, after confirmation), then `pre-delivery-qc` on the episode and on every Short. Errors go back to the step that owns them.
8. `deliver all`.

Approval: the user watches the graphics and zooms in context, reads the chapter list, and picks the Shorts and thumbnail before rendering.

## Finish

Unlock the tracks (`track-layout unlock graphics`). Save the project, update `episode.md`, and summarize: timelines created, durations, loudness measured, QC verdicts, rendered files with their checks, the upload package (video, SRT, chapters, thumbnails, Shorts), what was skipped and why, what the user should check by eye/ear.
