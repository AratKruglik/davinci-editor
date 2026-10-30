---
name: resolve-core
description: Shared rules for every davinci-editor skill that drives DaVinci Resolve Studio 21+ through the DaVinci Resolve MCP server - connection check, safe script execution, timeline backup before edits, timecode/frame math, finding tracks by role, marker etiquette, node-label conventions and verified API gotchas. Load before any run_script call against Resolve.
when_to_use: Any task that reads or changes a DaVinci Resolve project, timeline, media pool, grade or Fairlight setting; also when another davinci-editor skill says "follow resolve-core".
user-invocable: false
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_docs"
  - "mcp__DaVinci_Resolve__get_whats_new"
  - "Bash(python3 *tc.py *)"
---

# Resolve core conventions

Every davinci-editor skill follows these rules. They exist because a wrong edit in Resolve is costly: hours of grading or cutting can be lost, and the API reports success on calls that silently did nothing.

## 1. Connect

1. `get_resolve_status`. If Resolve is not running, ask the user before calling `launch_resolve` (it opens the app and may load the last project).
2. Read the version once: `resolve.GetVersionString()`. These skills target 21.0+. On older versions, warn that some calls (voice isolation, speaker detection, version API) may be missing.
3. Read the project and timeline you will touch and say their names back to the user before any change. Never assume "current project" is the right one.
4. Unknown function or key? Use `search_scripting_api` (e.g. pattern `Transcri`) before guessing. Resolve adds API often; `get_whats_new` with the last version you know lists additions.

## 2. Running scripts safely

- `run_script` is sandboxed (no `os`, files or network). Use it by default. `run_script_unsafe` only when the step must read or write files (exporting stills, dumping a transcript to JSON, reading a DRX folder).
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
- In Cowork the shell runs in a sandbox that sees the selected folder under a different path than Resolve on the Mac does. Resolve-side scripts (`run_script_unsafe`, `ExportCurrentFrameAsStill`) need the Mac absolute path; Bash/Python scripts need the sandbox path. Resolve the mapping once (write a small file from Resolve, find it from the shell) and keep `work_dir` inside the selected folder.

## 9. Language

Talk to the user in the language they use. Keep Resolve names (pages, menus, setting values) in English exactly as Resolve shows them so the user can find them.

Detailed API notes, verified signatures and the calibration script: [reference.md](reference.md).
