---
name: project-bootstrap
description: Creates a DaVinci Resolve Studio 21+ project and its standard bin structure for an episode - horizontal or vertical timeline settings, frame rate, node-based color science for the grading pipeline, transcription language, bins 01_Footage/02_Sound/03_Assets/04_Render/05_Thumbnails/Edit, import of camera footage, screen recordings and external audio into the right bins without touching the files, proxy advice and a selects timeline for grading. Also sorts an already open project into the same bins (moves clips, no re-import). Use it whenever a new video, shoot or episode starts or the media pool needs order, even if the user only says "import the footage" or "make bins".
when_to_use: User starts a new video, episode or shoot, wants a new Resolve project, the bin structure, footage imported or an untidy media pool sorted; first step of edit-episode stage A. Triggers - "новий проєкт", "створи проєкт", "структура бінів", "створи біни", "імпортуй матеріал", "підготуй проєкт під епізод", "розклади по бінах", "наведи лад у media pool", "new project", "vertical project для Shorts".
argument-hint: "[project name] [footage folder] [horizontal|vertical]"
arguments: [name, source, format]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "Bash(ls *)"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Project bootstrap

Follow `resolve-core` §1 (connect). Project: `$name`. Footage folder: `$source` (ask if empty). Format: `$format` (default `${user_config.timeline_format}`).

Settings that can't change later (frame rate once a timeline exists, resolution of existing timelines) are set **before** importing or creating timelines. That's why this skill runs first.

## 0. New project or the open one?

- **New** (default when the user names a new episode or project): steps 1–6.
- **Open project** (the user says "тут", "у поточному проєкті", "розклади по бінах" without asking for a new project, or the open project already holds this episode's clips): skip `CreateProject`. Read `project.GetTimelineCount()`: with timelines present, don't touch frame rate or resolution (it would retime existing edits); only report mismatches. Build the bins (step 3) and **move** clips already in the media pool with `mp.MoveClips(clips, bin)` instead of importing them again: a re-import makes duplicates that lose markers, transcripts and grades. Import only files that aren't in the pool yet (compare `File Path`).

Running the skill twice must not duplicate anything: reuse bins that exist (match by name under the same parent), skip files already imported.

## 1. Plan and confirm

1. `pm = resolve.GetProjectManager()`. Read the open project name; if it has unsaved changes, `pm.SaveProject()` (say so). `CreateProject` switches the open project.
2. List the footage folder (`ls`, or `run_script_unsafe` if the shell can't see it, e.g. in Cowork) and sort files into bins:

| Bin | What goes there | How to tell |
|---|---|---|
| `01_Footage/A-Roll` (= `${user_config.footage_bin}`) | camera takes of the presenter | video from the camera (iPhone: `IMG_*.MOV`, Apple metadata) |
| `01_Footage/B-Roll` | cutaways | a subfolder or names the user points out |
| `01_Footage/Screen` | screen recordings | names like `Screen Recording`, `Запис екрана`, `CleanShot`, OBS; computer resolutions (2880×1800, 3024×1964…); no camera metadata |
| `02_Sound/Voice` | external mic / recorder audio | `.wav`/`.m4a` next to the takes |
| `02_Sound/SFX`, `02_Sound/Music` | filled later by `sound-design` | — |
| `03_Assets/Graphics`, `03_Assets/Templates` | logos, images, DRX/DRT | images, `.drx`, `.drt` |
| `04_Render`, `05_Thumbnails`, `Edit` | empty | — |

3. Timeline settings from the format, at `${user_config.timeline_fps}` fps:
   - `horizontal`: `${user_config.timeline_resolution}` (default 3840×2160);
   - `vertical`: the same swapped (2160×3840) — Shorts/Reels; mention that `shorts-cutdown` will later make vertical timelines from a horizontal project, so a vertical *project* is only for vertical-first shoots.
   Read the camera clips' frame rate from the file names/metadata if possible; if it differs from the configured fps, ask which wins (mixed rates get retimed).
4. Show the plan (project name, settings, file → bin table, counts) and get a yes.

## 2. Create and configure

```python
pm = resolve.GetProjectManager()
project = pm.CreateProject(NAME)           # None → name taken: ask for another name or to open the existing one
ok = project.SetSettings({
    "timelineResolutionWidth": W, "timelineResolutionHeight": H, "timelineFrameRate": FPS,
    "colorScienceMode": "davinciYRGB",     # node-based: the grading skills need an explicit CST, not RCM
})
if LANG == "uk" and resolve.GetVersion()[:3] >= [21, 1, 2]:
    project.SetSettings({"transcriptionExtendedLanguageSupport": "1"})   # first: uk exists only in the extended model
project.SetSettings({"transcriptionLanguage": LANG})                    # separate call: changing extended resets it to auto
s = project.GetSettings()
result = {k: s.get(k) for k in ("timelineResolutionWidth", "timelineResolutionHeight", "timelineFrameRate", "colorScienceMode",
                                 "transcriptionExtendedLanguageSupport", "transcriptionLanguage")}
```

`LANG` = `${user_config.transcription_language}`. Re-read every key; a key that didn't stick → report it with the value Resolve kept (for `transcriptionLanguage`, `uk-transcribe` §1 has the order and the Extras check: extended not reading back `"1"` means the extended models aren't installed). Don't loop on it.

## 3. Bins and import

Create bins with `mp.AddSubFolder(parent, name)` (reuse a bin if it exists), then per bin `mp.SetCurrentFolder(bin)` and `mp.ImportMedia([paths])`. Re-read: number of items per bin == planned. Files are referenced in place: never copy, move or rename media.

If Resolve can't read a file (e.g. VFR screen recording from some apps), list it and suggest converting it to constant frame rate before editing; don't import a transcoded copy without asking.

## 4. Proxies

There is no API to generate proxies. For 4K HEVC from an iPhone on a laptop, tell the user: Media Pool → select `A-Roll` and `Screen` → right-click → **Generate Proxy Media**; Playback → **Use Proxy Media if Available**. Rendering always uses the originals.

## 5. Selects timeline and tracks

1. `mp.CreateTimelineFromClips(f"{NAME} - selects", [{"mediaPoolItem": c} for c in a_roll])` in the `Edit` bin: the grading timeline for stage A (`log-to-rec709` works on it). Re-read its settings match step 2.
2. Don't build the edit timeline here: `text-based-cut` creates it with the `track-layout` structure.
3. Save the project.

## 6. Report

Project name and settings (re-read values), bins with item counts, files not imported and why, proxy instructions, next step: `log-to-rec709` on the selects timeline.

## Never

- Overwrite or open over an existing project with the same name without asking.
- Turn on Resolve Color Management (the grading pipeline needs explicit nodes; see `log-to-rec709`).
- Write into the footage folder.
