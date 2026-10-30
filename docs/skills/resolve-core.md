# `resolve-core`: shared rules behind every skill

[← All skills](README.md)

## What it does

Holds the rules every other skill of the plugin follows when it talks to DaVinci Resolve: how Claude connects, runs scripts safely, protects your work before an edit, does timecode math, finds tracks, treats your markers, and labels color nodes. It edits nothing by itself. It exists because a wrong edit in Resolve is costly: hours of grading or cutting can be lost, and the API reports success on calls that silently did nothing.

This page explains what you see because of these rules and what you can rely on in every skill.

## When it triggers

It is hidden (`user-invocable: false`): it has no slash command and you never call it directly. It loads by itself for any task that reads or changes a Resolve project, timeline, media pool, grade or Fairlight setting, and whenever another skill says "follow resolve-core".

## Connection check

Before the first change in a session, Claude:

1. Checks Resolve is running. If it isn't, it **asks you** before launching it (launching opens the app and may load the last project).
2. Reads the Resolve version once. The plugin targets 21.0+; on older versions it warns that some calls (voice isolation, speaker detection, the version API) may be missing.
3. Reads the project and timeline it will touch and **says their names back to you** before any change. It never assumes the current project is the right one.
4. Looks up an unknown function in Resolve's scripting API instead of guessing.

## How scripts run

- Scripts run in Resolve's sandboxed mode by default (no files or network). The unsafe mode is used only for steps that must read or write files: exporting stills, dumping a transcript to JSON, reading a DRX folder.
- One step per call. Long loops over hundreds of clips run in batches (for example 50 items per call) with progress reported.
- After every change Claude reads the value back and reports what Resolve actually holds, not the call's `True`.
- A call that hangs for more than 60 s: Claude asks you to look at Resolve for a modal dialog. It never blindly re-runs a script that changes something.

## How your work is protected

- **Saves:** the project is saved before the first change and after each completed stage.
- **Backups:** before structural edits (adding, removing, moving or trimming clips, deleting tracks) the timeline is duplicated as `<timeline name> - backup <YYYY-MM-DD HH-MM>`, and the original is edited. Cuts go further: they build a **new** timeline and never modify the source one.
- **Reversible toggles** (voice isolation, track lock / enable, clip color, a new grade version) get no timeline copy: the project is saved first and the previous value is recorded so it can be restored.
- **Deletions:** clips, timelines, bins, grades, LUTs and DCTLs are deleted only when you asked for that exact deletion, with a confirmation that names the objects.
- **Project-wide color:** changing color science or color management on a project that already has grades or titles needs your explicit yes, after a warning that everything may render differently.

## The delete guard

Every skill that changes the project declares a `PreToolUse` hook that runs `guard.py` on Resolve script calls. If a script calls any delete, clear or reset API (`Delete…`, `Clear…`, `Reset…`, `ReplaceClip`, `UnlinkProxyMedia`), you get a **permission prompt** with the reason, even when the tool is pre-approved. Scripts that build function names at run time (`getattr`, `eval` and similar) always prompt too, because they can't be checked in advance.

A prompt from the guard is not an error. Claude says what the script deletes and why; you decide. It never splits or renames calls to slip past the guard.

Two exact calls are exempt because they only clean up Claude's own scratch work: `DeleteMarkersByColor("Cream")` (Claude's markers) and deleting the temporary local grade version `claude-measure` that color skills measure on.

## Timecode and frames

- Positions are handled as Resolve's absolute frames, starting at the timeline start (usually 01:00:00:00). Frame rate and drop-frame come from the project settings; a clip with a different frame rate is read from its own `FPS` property.
- Conversions go through the bundled `tc.py` helper, not mental arithmetic.
- Before the first assembly in a session, Claude runs a short calibration on a scratch timeline `claude-calibration` to learn how Resolve counts the end frame of a range, then deletes that timeline (a timeline delete, so the guard asks you) and switches back to yours.
- After the cut, transcript words are no longer at their clip timecode. Skills that need speech on the cut timeline (subtitles, chapters, Shorts, thumbnails, QC) take a fresh dump of the timeline and map words onto it with `timeline_map.py`.

## Tracks by role

Tracks are found **by role name** (A-roll, Voice, B-roll, SFX, Music…), never by number, using the roles in `video_tracks` / `audio_tracks`. If a role is missing, Claude runs `track-layout` instead of guessing a track number. Design notes: [track-layout.md](../track-layout.md) (in Ukrainian).

## Markers

- Your markers are instructions: Claude never changes or deletes them. The only thing it writes is the hidden `customData` field, as `claude:done:<skill>:<date>`, so a handled marker isn't handled twice.
- Claude's own markers (suggestions, found problems, questions) are **Cream** only, so you can remove all of them at once.

Full color system: [marker-color-system.md](../marker-color-system.md) (in Ukrainian).

## Color node convention

The Resolve API cannot create nodes, so every grading skill starts from one **base DRX template** that you build once (see [`log-to-rec709`](log-to-rec709.md)). Its serial nodes carry these labels, in this order:

| # | Label | Content | Written by |
|---|---|---|---|
| 1 | `CHART` | empty; receives the chart-match DCTL or LUT (camera log) | `chart-match` |
| 2 | `CST` | Color Space Transform camera log → Rec.709 | `log-to-rec709` (template) |
| 3 | `PRIMARY` | neutral balance / exposure | `natural-skin-grade` |
| 4 | `SKIN` | HSL qualifier on skin tones, corrections inside it | `natural-skin-grade` |
| 5 | `DEPTH` (+ `DEPTH BLUR`) | AI CineFocus, or Depth Map → keyed Lens Blur; **disabled** in the template | `depth-background-blur` |
| 6 | `LOOK` | your creative look | you |

- Nodes are found by label, never by position, so you may insert your own nodes. If a label is missing, Claude stops and tells you which node to label.
- Once the template is on a clip, skills change it only node by node. They never re-apply a DRX to add a feature: that would wipe the chart correction and the skin CDLs.
- **Template upgrade:** a stage-1 template without `SKIN` / `DEPTH` is upgraded after you add the missing nodes on the template clip and re-capture it. Claude asks first and shows the clip list; per clip it keeps the `CHART` correction. Skin CDLs can't be read back, so `natural-skin-grade` is run again afterwards.

## Grades that survive the cut

Grading happens before the cut, in a **remote** grade version named `claude`, stored on the Media Pool clip and shared by every timeline that uses it. After an assembly Claude checks a few items still have `claude` loaded and loads it where needed (whether a new timeline picks it up automatically is unverified in Resolve 21).

## Settings

| Key | Default | Effect |
|---|---|---|
| `video_tracks` | `Backgrounds:Tan,A-roll:Blue,B-roll:Teal,Effects:Orange,Titles:Pink` | video track roles that skills look up by name |
| `audio_tracks` | `Voice:Green,SFX:Yellow,Music:Purple` | audio track roles that skills look up by name |
| `templates_dir` | empty | folder with the DRX grade templates; empty → Claude asks for a folder once and suggests setting it |
| `work_dir` | `resolve-work` | root of all working files (below) |

If a surface doesn't fill plugin settings (for example Cowork), Claude uses the defaults from `plugin.json` and says which defaults it used.

## Files

Transcripts, cut lists, stills and reports go under `<work_dir>/<project name>/`, relative to the working directory. Nothing is ever written inside your media folders.

| File | Contents |
|---|---|
| `<work_dir>/<project>/timeline-<timeline name>.json` | dump of the cut timeline that stage-3 skills read; taken again after any edit |
| `<templates_dir>/*.drx` | base grade templates |

In Cowork the shell sees your selected folder under a different path than Resolve on the Mac. Claude works out the mapping once and keeps `work_dir` inside the selected folder.

## What it never does

- Launch Resolve without asking.
- Edit before naming the project and timeline back to you.
- Delete clips, timelines, bins, grades, LUTs or DCTLs you didn't ask to delete by name.
- Modify the source timeline when cutting: the cut goes to a new one.
- Change, recolor or delete your markers.
- Re-apply a DRX over a graded clip to add a feature.
- Change project-wide color management on a graded project without your explicit yes.
- Re-run a hung script that changes something.
- Split or rename calls to get past the delete guard.

## Place in the workflow

Under everything: every step of `edit-episode` and every single skill follows these rules. It is the reason backups, saves, read-backs and the delete prompts look the same in every skill.

## Example prompts

`resolve-core` has no slash command; these prompts touch the behaviors it defines.

**Minimal:**

> Check that you can see Resolve.

**Overriding a setting:**

> My grade templates are in `~/Grades/templates`: use that folder, the plugin setting is empty.

**Professional brief:**

> Before we start: check Resolve is connected, tell me the version, the open project and the current timeline, and save the project. I'm on the timeline `Router Setup - rough cut`; any structural change goes onto it only after a backup copy. If anything wants to delete or reset, stop and tell me exactly what and why before the prompt.

**Troubleshooting:**

> You asked permission for a script that calls `DeleteTimelines`. What does it delete and why?

> The rough cut looks ungraded. Check which grade version the items on A-roll have loaded and load `claude` where it's missing.

> My template is from stage 1 and has no `SKIN` or `DEPTH`. I added the nodes on the template clip: upgrade the template and keep the chart correction on every clip.

**Weak vs strong:**

| Weak | Strong |
|---|---|
| "Is it working?" | "Check the Resolve connection, tell me the version and which project and timeline you'd touch, and save the project before anything else." |

The strong prompt asks for exactly the checks the rules define, so you see the version, the target and a saved project before the first change.

## What to check afterwards

- Read every permission prompt from the guard: it names the API that deletes or resets something.
- Backup timelines (`… - backup <date time>`) stay in the project; remove the ones you no longer need yourself.
- All Cream markers can be removed at once with `DeleteMarkersByColor("Cream")`.
- After any assembly, a few items on the new timeline should show the `claude` grade version.
