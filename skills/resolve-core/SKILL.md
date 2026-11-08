---
name: resolve-core
description: Shared rules for every davinci-editor skill that drives DaVinci Resolve Studio 21+ through the DaVinci Resolve MCP server - connection check, safe script execution, timeline backup before edits, timecode/frame math, finding tracks by role, marker etiquette, node-label conventions, edit memory (learn, rules, handoff snapshots) and verified API gotchas. Load before any run_script call against Resolve.
when_to_use: Any task that reads or changes a DaVinci Resolve project, timeline, media pool, grade or Fairlight setting; also when another davinci-editor skill says "follow resolve-core".
user-invocable: false
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_docs"
  - "mcp__DaVinci_Resolve__get_whats_new"
  - "Bash(python3 *tc.py *)"
  - "Bash(python3 *timeline_map.py *)"
  - "Bash(python3 *memory.py *)"
---

# Resolve core conventions

Every davinci-editor skill follows these rules. They exist because a wrong edit in Resolve is costly: hours of grading or cutting can be lost, and the API reports success on calls that silently did nothing.

## 1. Connect

1. `get_resolve_status`. If Resolve is not running, ask the user before calling `launch_resolve` (it opens the app and may load the last project).
2. Read the version once: `resolve.GetVersionString()`. These skills target 21.0+. On older versions, warn that some calls (voice isolation, speaker detection, version API) may be missing. Editing calls added in 21.1.2 (trims, effects, frame export…) follow the version gate in §10.
3. Read the project and timeline you will touch and say their names back to the user before any change. Never assume "current project" is the right one.
4. Unknown function or key? Use `search_scripting_api` (e.g. pattern `Transcri`) before guessing. Resolve adds API often; `get_whats_new` with the last version you know lists additions.

## 2. Running scripts safely

- `run_script` is sandboxed (no `os`, files or network). Use it by default. `run_script_unsafe` only when the script's own Python must read or write files (dumping a transcript to JSON, reading a DRX folder). Resolve calls that write files themselves (`ExportFrame`, `ExportStills`, `Export`) work from `run_script`.
- One step per call, short scripts, default timeout. Long loops over hundreds of clips: batch them (e.g. 50 items per call) and return progress.
- Always set `result` to structured data (dict/list), never only `print`.
- After every `Set*`/`Apply*`/`Add*` call, read the state back with the matching `Get*` and report the re-read value, not the boolean. Many setters return `True` and change nothing when a value string is spelled differently than this build expects.
- A call that hangs > 60 s: ask the user to look at Resolve for a modal dialog. Never blindly re-run a state-changing script.
- Objects (`Timeline`, `TimelineItem`, `MediaPoolItem`) do not survive between calls. Re-fetch them by name or `GetUniqueId()` in each script.

## 3. Protect the user's work

- `resolve.GetProjectManager().SaveProject()` before the first change and after each completed stage.
- Structural edits (adding, removing, moving or trimming clips; deleting tracks): first `tl.DuplicateTimeline(f"{tl.GetName()} - backup {YYYY-MM-DD HH-MM}")`, then `project.SetCurrentTimeline(original)` and edit the original; for cuts, build a *new* timeline instead and never modify the source one.
- Reversible toggles (voice isolation, track lock/enable, clip color, a new local/remote grade version) don't need a timeline copy: save the project before and record the previous value so you can restore it.
- Never delete clips, timelines, bins, grades, LUTs or DCTLs unless the user asked for that exact deletion. `DeleteClips`, `DeleteTimelines`, `ResetAllGrades`, `delete_lut`, `delete_dctl` require explicit confirmation naming the objects.
- Skills that change the project carry a `PreToolUse` hook (`scripts/guard.py`) that turns any `run_script*` call with a delete/reset/clear API into a permission prompt. A prompt from it is not an error: say what the script deletes and why, then let the user decide. Never split or rename calls to slip past it.
- Changing project-wide color science or color management on a project with existing grades/titles needs an explicit yes after warning that everything may re-render differently.

## 4. Frames and timecode

- Resolve timeline positions are absolute frames that start at `tl.GetStartFrame()` (usually 86400 = 01:00:00:00 at 24 fps). `recordFrame` in `AppendToTimeline` uses these absolute frames.
- `AppendToTimeline` `startFrame`/`endFrame` are **source** frames of the media pool clip. Transcription timecodes are clip timecodes: source frame = `tc_to_frames(word_tc) - tc_to_frames(clip "Start TC")`.
- Whether `endFrame` is inclusive is not documented. Before the first assembly in a session run the calibration in [reference.md](reference.md#append-calibration) on a scratch timeline and use its result; delete the scratch timeline afterwards (it is yours, created this session).
- Frame rate: `float(project.GetSettings()["timelineFrameRate"])`, drop-frame: `project.GetSettings()["timelineDropFrameTimecode"] == "1"`. A clip may differ from the timeline: read its `FPS` clip property.
- Do conversions with the bundled helper, not mental arithmetic:
  `python3 ${CLAUDE_SKILL_DIR}/scripts/tc.py to-frames 01:00:02:05 --fps 25`
  Other skills import it: `sys.path.insert(0, "<plugin>/skills/resolve-core/scripts"); from tc import tc_to_frames, frames_to_tc, ms_to_frames`.
- After the cut, transcript words are not at their clip timecode any more. Skills that need speech on the cut timeline (subtitles, chapters, Shorts, thumbnails, QC) take a fresh [timeline dump](reference.md#timeline-dump) and map words with `python3 ${CLAUDE_SKILL_DIR}/scripts/timeline_map.py words …`; the reverse (a timeline range → source clip ranges, to rebuild it elsewhere) is `timeline_map.py sources …`.

## 5. Tracks and markers

- Tracks are found **by role name**, never by number: use `track_index(tl, kind, role, create=False)` from the `track-layout` skill (roles from `${user_config.video_tracks}` / `${user_config.audio_tracks}`: A-roll, Voice, B-roll, SFX, Music…). If a role is missing, run `track-layout` instead of guessing a number.
- User markers are instructions (see `marker-edit`): never change or delete them. Claude writes only `customData` (`claude:done:<skill>:<date>`) and puts its own markers in Cream only.
- Marker frames: media pool clip → relative to clip start; timeline → relative to `tl.GetStartFrame()`; timeline item → relative to the item's media.

## 6. Color node convention

The API cannot create nodes or change node tools. All grading skills therefore start from one **base DRX template** whose nodes carry these labels (serial, in this order):

| # | Label | Content | Written by |
|---|---|---|---|
| 1 | `CHART` | empty, receives chart-match LUT/DCTL (works in camera log / linear) | `chart-match` (`SetLUT`) |
| 2 | `CST` | Color Space Transform camera log → Rec.709 | `log-to-rec709` (template) |
| 3 | `PRIMARY` | neutral balance / exposure | `natural-skin-grade` (`SetCDL`) |
| 4 | `SKIN` | HSL qualifier on skin tones, corrections inside it | `natural-skin-grade` (`SetCDL`) |
| 5 | `DEPTH` (+ `DEPTH BLUR`) | AI CineFocus, or Depth Map → keyed Lens Blur; **disabled** in the template | `depth-background-blur` (`SetNodeEnabled`) |
| 6 | `LOOK` | creative look | user |

Find nodes by label (`graph.GetNodeLabel(i)` for `i in 1..graph.GetNumNodes()`), never by hard index: users insert nodes. If a label is missing, stop and tell the user which node to label.

`ApplyGradeFromDRX` replaces the whole node tree of the graph it is applied to. So after the template is on a clip, skills change it **only** with per-node calls (`SetLUT`, `SetCDL`, `SetNodeEnabled`) and never re-apply a DRX to add a feature: that would wipe the chart LUT and skin CDLs.

**Template upgrade** (stage-1 templates have no `SKIN`/`DEPTH`): the user adds the missing nodes on the template clip and re-captures the template (`log-to-rec709` §2). Then, per clip on its remote `claude` version: read `GetLUT` of `CHART`, `ApplyGradeFromDRX(new_template, 0)`, `SetLUT` the same path back on `CHART`, re-read. CDLs from an earlier skin grade are not readable (no `GetCDL`), so run `natural-skin-grade` again afterwards. Ask before upgrading; show the clip list.

Templates live in `${user_config.templates_dir}`. If that setting is empty, ask the user for a folder once and suggest setting it in the plugin config.

## 7. Grades that survive the cut

Grade before cutting, in **remote** versions (stored on the media pool clip, shared by every timeline that uses it):

```python
item.AddVersion("claude", 1)            # 1 = remote
item.LoadVersionByName("claude", 1)
item.GetNodeGraph().ApplyGradeFromDRX(drx_path, 0)
```

Re-read with `item.GetCurrentVersion()` → `{"versionName": "claude", "versionType": 1}`. Resolve 21 notes that new local versions pick up remote grades on clip creation; whether a timeline built by `AppendToTimeline` loads the remote version automatically is **unverified**: after any assembly, check `GetCurrentVersion()` on a few items and `LoadVersionByName("claude", 1)` where needed.

## 8. Working files and settings

Write transcripts, cut lists, stills and reports under `${user_config.work_dir}/<project name>/` (relative to the working directory). Never write inside the user's media folders.

- If `${CLAUDE_SKILL_DIR}` reaches you unsubstituted, locate the skill's folder once (e.g. `find / -path '*/skills/<skill>/SKILL.md' 2>/dev/null`) and use that path for its `scripts/`.
- If a `${user_config.…}` placeholder reaches you unsubstituted (some surfaces, e.g. Cowork, may not fill plugin settings), use the default from the plugin's `.claude-plugin/plugin.json`, and say which defaults you used.
- In Cowork the shell runs in a sandbox that sees the selected folder under a different path than Resolve on the Mac does. Resolve-side scripts and the files Resolve writes (`run_script_unsafe`, `ExportFrame`, `ExportCurrentFrameAsStill`) need the Mac absolute path; Bash/Python scripts need the sandbox path. Resolve the mapping once (write a small file from Resolve, find it from the shell) and keep `work_dir` inside the selected folder.

## 9. Language

Talk to the user in the language they use. Keep Resolve names (pages, menus, setting values) in English exactly as Resolve shows them so the user can find them.

## 10. Resolve 21.1.2 editing calls

21.1.2 added calls that replace several manual steps. **Version gate:** use them only when `resolve.GetVersion()[:3] >= [21, 1, 2]` (or `hasattr` on the object); otherwise keep the skill's manual route and say why. Verified behaviour, details in [reference.md](reference.md#resolve-2112-editing-calls):

- **Stills:** `tl.ExportFrame(offset, {"outputType": "file", "filePath": p})` / `item.ExportFrame(...)` render the finished frame (grade, all tracks, Fusion titles) at an offset from the timeline / item start, from `run_script`, without moving the playhead. `.tif` is 16-bit full resolution. Use this instead of playhead + `ExportCurrentFrameAsStill`.
- **Trims:** `item.SetLeftOffset(n, False, False)` / `SetRightOffset(n, False, False)` set the media handle left beyond that edge, in place, no ripple. Always pass `updateLinkedItems=False` and trim each linked item yourself: with `True` the linked item gets the same *value*, not the same delta. Extending into a neighbour on the same track overwrites the neighbour's edge. Generators, titles and Fusion compositions have no handles and can't be trimmed (`False`).
- **Placement:** `item.SetPosition({"trackIndex", "startFrame"}, False)` moves one item (also across tracks), `tl.MoveItems(items, {...}, False)` a group keeping their spacing. `tl.InsertFusionTitleIntoTimeline` *inserts with ripple* on the lowest video track at the playhead, and moving the title afterwards does not undo the shift: work on a backup, lock the other tracks first (whether a lock stops this ripple is unverified), and compare later items' starts before and after.
- **Effects:** `resolve.GetEffectsList("video"|"audio")` gives installed effects with `id`s; `item.AddEffect(category, id)`, `GetEffects`, `DeleteEffects`; `Effect.Get/SetIsEnabled`, `Get/SetIndex`. Only media items accept effects. Fusion effects (MotionVFX included) expose their parameters through `effect.GetFusionComp()`; OFX and audio effects have **no parameter API**.
- **Audio:** `item.AnalyzeAudioLevels(mode)` → `{"Integrated", "TruePeak"}` per item, no render. `item.RippleDeleteSilence({...})` cuts *every unlocked track*: lock what must stay, work on a duplicate. It is guarded like a delete.
- **Transcripts:** `mp_item.SetTranscription(t)` writes a corrected transcript back (words with a leading space, as Resolve's own). Ukrainian needs `transcriptionExtendedLanguageSupport` `"1"` *before* `transcriptionLanguage` `"uk"`.

Detailed API notes, verified signatures and the calibration script: [reference.md](reference.md).

## 11. Edit memory

`edit-memory` learns from the user's hand edits between Claude's runs. Memory file `M` = `${user_config.edit_memory_file}`, empty → `${user_config.work_dir}/edit-memory.json` (one file for all projects; the event log `edit-memory-events.jsonl` sits next to it). Script `${CLAUDE_SKILL_DIR}/../edit-memory/scripts/memory.py`, always with `--memory "<M>"` where it takes one. Snapshots are `<work>/handoff/<timeline_id>-<YYYYMMDD-HHMMSS>.json` ([reference.md](reference.md#handoff-snapshot)); the newest by name is the last one.

Every skill that writes to a timeline (items, properties, Fusion comps, Cream markers) does three things on the timeline it writes to:

1. **Learn at the start**, before its first write and without questions: take the snapshot into `<work>/handoff/fresh-<timeline_id>.json` (a name no dated snapshot matches), then `memory.py changed "<previous snapshot>" "<fresh>"` and read its JSON. `{"changed": true}` → `memory.py diff "<previous>" "<fresh>" --ledger "<work>/placed-<timeline>.json" --out "<work>/handoff/events.json"`, then `memory.py log "<work>/handoff/events.json" --project "<project>" --timeline "<timeline>" --memory "<M>" --promote "<fresh>"`, and say the count in one line. `--promote` renames that fresh file to `<timeline_id>-<YYYYMMDD-HHMMSS>.json` only after the events are logged: it becomes the newest snapshot, so the same edits are never logged twice. On `{"changed": false}`, or when there is no earlier snapshot of this `timeline_id` (a new timeline: nothing to learn), `memory.py promote "<fresh>"` does the same rename. Never rename it any other way. Any error (no JSON from `changed`, `diff` or `log` failing) → the fresh file stays unrenamed, so the previous snapshot stays the starting point; tell the user. A snapshot taken without this step first would hide the user's edits since the previous one.
2. **Rules before the plan:** `memory.py rules --skill <this skill> --format youtube|shorts --memory "<M>"` (`shorts` on a vertical timeline). A numeric `param` overrides the plugin default it names (`hold_extra_s` adds seconds to the computed hold, `max_scale` caps the zoom below `zoom_max_scale`); a text rule guides the choices. A direct request of the user or a marker note beats a rule. The plan table lists the rules applied (id and text).
3. **Snapshot as the last step** of every write: the end of the skill, each critic fix round, critic and QC Cream markers, every `edit-episode` stop, and also when the skill stops early after any write (an error, the user's stop). Otherwise Claude's own changes look like the user's next time.

Candidates are never shown at a skill's start. At its end (in `edit-episode`: at the stop), when step 1 logged events and `memory.py lessons --memory "<M>"` has a candidate that is not `one_off` and holds one of them, run the approval of `edit-memory learn` (its §2–§3). Only `memory.py` writes the memory files, never a hand edit.
