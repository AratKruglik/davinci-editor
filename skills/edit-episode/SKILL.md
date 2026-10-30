---
name: edit-episode
description: Orchestrates a full episode edit in DaVinci Resolve Studio 21+ in a fixed order with an approval stop after every stage - A) color before the cut (log-to-rec709, chart-match), B) transcript, track layout and text-based rough cut, C) voice isolation; each stage starts from the user's colored markers. v1 covers stage-1 skills; later stages are listed but skipped until their skills exist.
when_to_use: User invokes /edit-episode to run the whole pipeline on a new shoot.
argument-hint: "[episode name] [from-stage A|B|C]"
arguments: [episode, from_stage]
disable-model-invocation: true
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Read"
---

# Edit episode `$episode`

Run the stages in order, starting from `$from_stage` (default A). Each step is a separate skill: invoke it, let it finish with its own verification, then **stop and ask the user to approve** before the next. Never chain two stages without an explicit "далі"/"go".

Start: follow `resolve-core` §1–3 (connect, confirm project, save). Keep a running checklist in `${user_config.work_dir}/<project>/episode.md` (stage, status, date, notes) so a later session can resume.

Every stage starts with `marker-edit` limited to that stage's colors (A: Sand; B: Red, Green, Yellow, Purple, Fuchsia, Cocoa; C: Lavender, Sky, Rose): the user's markers are the brief for the stage, and colors whose skill doesn't exist yet are listed as waiting.

## Stage A — color before the cut

Grade all footage before cutting, in remote versions, so the grade follows every clip into the rough cut.

1. `project-bootstrap` — *not available yet*; check that footage is in `${user_config.footage_bin}` and a timeline with all clips exists, else ask the user.
2. `log-to-rec709` — applies the base template (it contains the `CHART` node too).
3. `chart-match` — only if a chart was shot (ask). Runs after the template exists, but writes to `CHART`, which sits before the CST in the node tree.
4. `natural-skin-grade`, `depth-background-blur` — *stage 2 skills, not available yet*; tell the user they're skipped.

Approval: user looks at 2–3 clips in the viewer.

## Stage B — "fish" and rough cut

1. `uk-transcribe`.
2. `track-layout` — plan the tracks this episode needs (Screen for screen recordings, Voice 2 for a second speaker…); the new timeline gets them in `text-based-cut`.
3. `text-based-cut` with the Red/Green/Yellow markers (it has its own approval of the cut list) — builds the new timeline on A-roll + Voice.
4. Control: on the new timeline every video item has the remote `claude` version loaded (`GetCurrentVersion()`); fix per `resolve-core` §7.
5. `dual-video-sync-pip` — *stage 2, not available yet*.

Approval: user watches the rough cut using the Cream `cut` markers.

## Stage C — sound

1. `voice-isolation` on the rough-cut timeline's Voice track (and Rose markers about noise). Lock A-roll and Voice with `track-layout lock` for the rest of the sound stage.
2. `sound-design`, `audio-finish` — *stage 2, not available yet*.

## Finish

Offer `track-layout cleanup` (empty tracks, after confirmation). Save the project, update `episode.md`, and summarize: timelines created, durations, what was skipped and why, what the user should check by eye/ear.
