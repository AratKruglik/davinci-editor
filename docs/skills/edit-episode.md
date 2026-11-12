# `edit-episode`: the whole episode, step by step, with approval stops

[← All skills](README.md)

## What it does

Runs the full edit of an episode in a fixed order: project and color before the cut (A), transcript and rough cut (B), sound (C), graphics, derivatives and delivery (D). Each step is a separate skill of the plugin: `edit-episode` invokes it, lets it finish with its own verification, then **stops and waits for your go-ahead** before the next one. Every stage starts from your colored markers for that stage. Progress is kept in `episode.md`, so a later session resumes where you stopped.

## When it triggers

**Only by slash command.** It never starts from plain language (`disable-model-invocation`), because it runs the whole pipeline.

```
/davinci-editor:edit-episode [episode name] [from-stage A|B|C|D]
```

| Argument | Meaning | Default |
|---|---|---|
| `episode` | episode name, used as the title of the run | — |
| `from_stage` | stage to start from: `A`, `B`, `C` or `D` | the first unfinished step in `episode.md`, else `A` |

A single letter alone (`/davinci-editor:edit-episode C`) is read as the stage, not as the episode name.

## Before you start

- DaVinci Resolve Studio 21+ running with the MCP server on. At the start Claude connects, says the project name back to you for confirmation, and saves the project.
- Your markers for the stage you start (below). They are the brief for that stage.
- The individual skills have their own prerequisites (grade templates, sound library, MotionVFX catalog…); see their pages.

## Markers it reads

Every stage starts with [`marker-edit`](marker-edit.md) limited to that stage's colors. Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

| Stage | Colors |
|---|---|
| A | Sand |
| B | Red, Green, Yellow, Purple, Fuchsia, Cocoa |
| C | Lavender, Sky, Rose |
| D | Cyan, Pink, Blue, Mint, Lemon |

## The stages

### Stage A: project and color before the cut

All footage is graded before cutting, in remote versions, so the grade follows every clip into the rough cut.

1. `project-bootstrap`: new project, bins, import, selects timeline. Skipped if the project already exists and is sorted (its open-project mode is offered if the Media Pool is messy).
2. `log-to-rec709`: applies the base template (`CHART` → `CST` → `PRIMARY` → `SKIN` → `DEPTH` → `LOOK`). An old template without `SKIN` / `DEPTH` gets a template upgrade before step 4.
3. `chart-match`: only if a chart was shot (Sand markers, or Claude asks).
4. `natural-skin-grade`: per scene.
5. `depth-background-blur`: per scene, talking-head shots only; Claude asks whether you want it at all for this episode.

**Review:** look at 2–3 clips per scene in the viewer.

### Stage B: the "fish" and rough cut

1. `uk-transcribe`.
2. `track-layout`: plans the tracks this episode needs (Screen + PiP for screen recordings or Purple markers, Voice 2 for a second speaker, B-roll 2 for overlapping Fuchsia inserts); the new timeline gets them in step 3.
3. `text-based-cut` with your Red / Green / Yellow markers (it has its own cut-list approval); builds the new timeline on A-roll + Voice.
4. Control: every video item on the new timeline has the remote `claude` grade version loaded, and the Color Group of a few items survived (reassigned from the source clips if not, because the `light` / `strong` depth blur lives on the group).
5. `dual-video-sync-pip`: tutorials with a screen recording only.
6. `marker-edit` for Fuchsia (B-roll inserts) and Cocoa (transitions) on the cut timeline.
7. `split-edits`: J/L cuts where the picture source changes, and Cocoa markers with `J` / `L` / `split`. Clip changes were already offered in step 3 and camera ↔ screen switches in step 5; this step does the rest on a copy of the timeline. It comes before sound, because `sound-design` and `audio-finish` build on the final audio boundaries. Design note: [split-edits.md](../split-edits.md) (in Ukrainian).
8. [`jump-cuts`](jump-cuts.md): talking-head parts only, if you want the jump cuts treated. Every join inside one shot is judged from its two frames and left alone, rolled a few frames, given a Smooth Cut, punched in or marked for cover footage (its own approval table; works on a copy). It comes after `split-edits` and before sound, because a rolled cut moves the Voice edges too.

**Review:** watch the rough cut using the Cream `cut` markers.

### Stage C: sound

1. `voice-isolation` on the cut timeline's Voice track (and Rose markers about noise). Then A-roll and Voice are locked (`track-layout lock sound`) for the rest of the stage.
2. `sound-design` with your Lavender / Sky markers (its own cue-sheet approval and license check). If you ask for live-sounding music, room on SFX, pan sweeps or vocals out of a song, [`audio-effects`](audio-effects.md) runs after it.
3. `audio-finish`: Rose markers, dialogue leveling, measured loudness to the target. The tracks are unlocked after it (`track-layout unlock sound`).

### Stage D: graphics, derivatives and delivery

Picture and sound are locked now: A-roll, B-roll and Voice are locked (`track-layout lock graphics`) until `deliver`. Steps 2–6 need the words on the cut, so Claude takes a timeline dump at the start of the stage and a fresh one after any step that changes items.

1. `fusion-motion-graphics`: Cyan markers, name plates, callouts; chapter cards only if you want them (after step 4, from its titles).
2. `tutorial-zooms`: Pink markers on the screen recording.
3. `subtitles-uk`: YouTube SRT (and the `Subtitles UA` track if wanted).
4. `chapters-markers`: Blue markers → `chapters.txt`.
5. `shorts-cutdown`: Mint markers or proposals → vertical timelines; each Short gets `audio-finish` and `subtitles-uk shorts`.
6. `thumbnail-frames`: Lemon markers → `thumbnail-brief.md`.
7. `track-layout cleanup` (empty tracks, after confirmation), then `pre-delivery-qc` on the episode and on every Short. Errors go back to the step that owns them.
8. `deliver all`.

After steps 1, 2 and 5 the skill that placed the graphics, zooms or Short captions runs `frame-critic` on them once. Its findings are part of that step's review: fixes go back to the owner skill only after your yes, and the verdict and what stayed open go into `episode.md`.

**Review:** watch the graphics and zooms in context, read the chapter list, and pick the Shorts and thumbnail before rendering.

### Finish

Tracks are unlocked (`track-layout unlock graphics`), the project is saved, `episode.md` is updated, and you get a summary: timelines created, durations, loudness measured, QC verdicts, rendered files with their checks, the upload package (video, SRT, chapters, thumbnails, Shorts), what was skipped and why, and what to check by eye and ear.

Track roles and locks: [track-layout.md](../track-layout.md) (in Ukrainian).

## Skipping steps and resuming

- **Skip** any step by saying so: "without chart-match", "skip depth-background-blur". The skip and its reason are recorded in `episode.md`.
- **Resume:** when the command starts, it shows the progress saved so far in `episode.md`. Without `from_stage` it continues from the first unfinished step.
- **Start from a stage:** give the letter, e.g. `C` to go straight to sound on an existing cut.

## Settings

| Key | Default | Effect |
|---|---|---|
| `work_dir` | `resolve-work` | where `episode.md` is kept |

Each step uses its own settings; see the page of that skill.

## Files

| File | Contents |
|---|---|
| `<work_dir>/<project>/episode.md` | running checklist: step, status `done` / `skipped` / `failed`, date, timeline names, notes; updated after every step |

The steps write their own files (transcripts, cut lists, `chapters.txt`, `thumbnail-brief.md`, renders…) as described on their pages.

## Workflow and approval stops

1. Shows the saved progress, connects to Resolve, confirms the project with you, saves it.
2. Picks the starting step: `from_stage`, else the first unfinished step in `episode.md`, else stage A.
3. Opens the stage with `marker-edit` for its colors.
4. Runs one step (skill) and lets it verify itself; the skill may have its own approvals inside.
5. **Approval after every step.** It updates `episode.md` and stops. Nothing continues until you say "go" (or «далі»).
6. At the end of stages A, B and D, the review described above.
7. Finish: summary and saved project.

## What it never does

- Chain two steps without your explicit "go" / «далі».

Any script that deletes or resets something becomes a permission prompt (the `guard.py` hook), so read what you approve.

## Place in the workflow

It is the workflow. Each step is a skill with its own page; [`marker-edit`](marker-edit.md) opens every stage.

## Example prompts

**Start a new episode:**

```
/davinci-editor:edit-episode Router-Setup
```

**Resume in a new session** (continues from the first unfinished step in `episode.md`):

```
/davinci-editor:edit-episode
```

**Start from a stage:**

```
/davinci-editor:edit-episode Router-Setup C
/davinci-editor:edit-episode C
```

**Skipping steps** (say it when the command starts, or at the stop before the step):

> No chart was shot this time: without chart-match. And no depth-background-blur for this episode.

**At an approval stop:**

| Situation | What to say |
|---|---|
| The step is fine | "Go." / «Далі.» |
| Skip the next step | "Skip dual-video-sync-pip, there's no screen recording. Go." |
| Stop for today | "Stop here." Next time run `/davinci-editor:edit-episode` and it resumes. |
| Stage D review | "Chapters are fine. Shorts: take 1 and 3. Thumbnail: the second frame. Go to deliver." |

**Professional brief** (right after the command):

> Router setup tutorial, two camera clips plus a screen recording. My Sand marker is on the chart clip; Red / Green / Yellow and Purple are on the clips. Skip depth-background-blur, it's a bright office. In stage D I don't want punch-in zooms or chapter cards. Stop after every step as usual, and at the end list everything you skipped and why.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Edit the episode" (plain language: does not start the skill) | `/davinci-editor:edit-episode Router-Setup`, then "no chart shot: without chart-match; no screen recording: skip dual-video-sync-pip" |

Only the slash command starts it, and naming the skips up front saves an approval round on steps that have nothing to do.

## What to check afterwards

- Read `episode.md`: every step `done` or `skipped` with a reason, nothing `failed`.
- The tracks are unlocked again.
- Check the final summary's "what to check by eye and ear" list, the QC verdicts and the rendered files.
- The skipped steps are really ones you didn't need.
