---
name: edit-episode
description: Orchestrates a full episode edit in DaVinci Resolve Studio 21+ in a fixed order with an approval stop after every step - A) project and color before the cut (project-bootstrap, log-to-rec709, chart-match, natural-skin-grade, depth-background-blur), B) transcript, track layout, text-based rough cut and camera + screen PiP, C) sound (voice-isolation, sound-design, audio-finish); each stage starts from the user's colored markers and the progress is kept in episode.md so a later session can resume.
when_to_use: User invokes /edit-episode to run the whole pipeline on a new shoot or to resume it.
argument-hint: "[episode name] [from-stage A|B|C]"
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

Run the steps in order, starting from `$from_stage` (default: the first unfinished step in `episode.md`, else A). Each step is a separate skill: invoke it, let it finish with its own verification, then **stop and ask the user to approve** before the next. Never chain two steps without an explicit "далі"/"go". The user may skip any step ("без chart-match"); record the skip and why.

Start: follow `resolve-core` §1–3 (connect, confirm project, save). Keep a running checklist in `${user_config.work_dir}/<project>/episode.md` (step, status `done|skipped|failed`, date, timeline names, notes) and update it after every step, so a later session resumes from it.

Every stage starts with `marker-edit` limited to that stage's colors (A: Sand; B: Red, Green, Yellow, Purple, Fuchsia, Cocoa; C: Lavender, Sky, Rose): the user's markers are the brief for the stage. Colors whose skill belongs to stage 3 (Blue, Cyan, Pink, Mint, Lemon) are listed as waiting.

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

Approval: the user watches the rough cut using the Cream `cut` markers.

## Stage C — sound

1. `voice-isolation` on the cut timeline's Voice track (and Rose markers about noise). Then lock A-roll and Voice with `track-layout lock` for the rest of the stage.
2. `sound-design` with the Lavender/Sky markers (its own cue-sheet approval and license check).
3. `audio-finish` — Rose markers, dialogue leveling, measured loudness to the target. Unlock the tracks after it.

## Finish

Offer `track-layout cleanup` (empty tracks, after confirmation). Save the project, update `episode.md`, and summarize: timelines created, durations, loudness measured, what was skipped and why, what the user should check by eye/ear. Next (stage 3, when available): graphics, subtitles, Shorts, QC and delivery.
