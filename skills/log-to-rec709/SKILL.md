---
name: log-to-rec709
description: Converts iPhone Apple Log and Apple Log 2 footage to Rec.709 in DaVinci Resolve Studio 21+ with an explicit Color Space Transform node from a DRX template, applied as a remote grade version so it survives the edit. Detects log vs HLG/Dolby Vision per clip and never mixes Apple Log with Apple Log 2.
when_to_use: User wants to convert, normalize or "develop" Apple Log / iPhone log footage, set up the CST node, or prepare footage for grading. Triggers - "Apple Log у Rec.709", "конвертуй лог", "переведи в 709", "зроби нормальну картинку з лог", "CST для айфона", "convert log footage".
argument-hint: "[bin path or timeline name] [gamma 2.4|2.2]"
arguments: [scope, gamma]
allowed-tools:
  - "mcp__DaVinci_Resolve__get_resolve_status"
  - "mcp__DaVinci_Resolve__search_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_api"
  - "mcp__DaVinci_Resolve__get_scripting_docs"
  - "mcp__DaVinci_Resolve__get_whats_new"
hooks:
  PreToolUse:
    - matcher: "mcp__DaVinci_Resolve__run_script.*"
      hooks:
        - type: command
          command: "python3 \"${CLAUDE_PLUGIN_ROOT}/skills/resolve-core/scripts/guard.py\" || true"
---

# Apple Log / Apple Log 2 → Rec.709

Follow the `resolve-core` skill first (connection, backups, node labels, remote versions).

Scope: `$scope` (default: bin `${user_config.footage_bin}`). Output gamma: `$gamma` (default `${user_config.output_gamma}`).

## Why explicit nodes, not Resolve Color Management

The plugin's pipeline is `CHART (log/linear) → CST log→Rec.709 → PRIMARY → DEPTH → LOOK`. Chart matching has to measure the camera signal in a known space; with RCM the working space is hidden from the node tree. So the default route is a CST node from a template. RCM is an opt-in alternative (section 6) for users who do not need chart matching.

## Facts to get right

| Source | Gamut | Transfer | Cameras |
|---|---|---|---|
| Apple Log | Rec.2020 | Apple Log | iPhone 15 Pro and newer Pro models |
| Apple Log 2 | Apple Wide Gamut | Apple Log 2 | newer Pro iPhones that offer Apple Log 2 |

- Never apply an Apple Log transform to Apple Log 2 or the reverse: wrong gamut gives oversaturated, hue-shifted images. Keep one template per log version.
- iPhone HEVC is often **not log**: HDR video is HLG or Dolby Vision (PQ). Those need an HLG/PQ → Rec.709 transform instead. Never infer log from the codec.
- CST settings for Rec.709 delivery: Tone Mapping `DaVinci`, Gamut Mapping `Saturation Compression`, Apply Forward OOTF on, Use White Point Adaptation on, output Rec.709 / `$gamma` (Gamma 2.4 for YouTube/TV mastering on a calibrated monitor; Gamma 2.2 only if the user grades for computer screens and asks for it).
- Whether this build lists **Apple Log 2** in the CST is not confirmed for every 21.x build. If the user can't find it, use Apple's official Apple Log 2 → Rec.709 LUT on the `CST` node instead (user downloads it from Apple; do not download without permission).

## 1. Detect what each clip is

Per clip, collect Resolve properties with `run_script`:

```python
mp = project.GetMediaPool()
def folder(path):
    f = mp.GetRootFolder()
    for part in [p for p in path.split("/") if p]:
        f = next(s for s in f.GetSubFolderList() if s.GetName() == part)
    return f
keys = ("Clip Name", "File Path", "Type", "Video Codec", "Bit Depth", "FPS", "Resolution", "Input Color Space", "Format")
props = [c.GetClipProperty() for c in folder(SCOPE).GetClipList()]
result = [{k: p.get(k) for k in keys} for p in props if p.get("Type") in ("Video", "Video + Audio")]
```

If properties are inconclusive, probe the file with `run_script_unsafe`: read the first and last 32 MB, look for `colrnclx` (bytes after it: primaries, transfer, matrix as big-endian uint16) and for the strings `Apple Log 2` / `Apple Log`.

- transfer 18 = HLG, 16 = PQ → not log. Stop for these clips and offer HLG/PQ → Rec.709 instead.
- transfer 1 + primaries 1 → already Rec.709 SDR, nothing to do.
- `Apple Log 2` marker → Apple Log 2. `Apple Log` marker without `2` → Apple Log.
- Still ambiguous → ask the user (or ask which iPhone model and capture setting). Never guess between versions.

Show the table: clip → detected format → confidence (`metadata` / `file probe` / `user`). Get a go-ahead.

## 2. Get the template

Look in `${user_config.templates_dir}` for `base-apple-log.drx` / `base-apple-log-2.drx` (base tree with labels `CHART`, `CST`, `PRIMARY`, `SKIN`, `DEPTH`, `LOOK`, CST set as above; see `resolve-core` §6).

Missing → one-time capture, because the API cannot create nodes:
1. Ask the user to build the serial tree on one clip of that log version on the Color page and label the nodes (right-click → Node Label). Wait for "готово". Give them this checklist:
   - `CHART` empty; `CST` set as above; `PRIMARY` empty;
   - `SKIN`: HSL qualifier on skin hue (Hue only, wide soft edges, Clean Black/White ~5), no correction;
   - `DEPTH`: Resolve FX **AI CineFocus** with a moderate background blur (or Depth Map → key output into a node `DEPTH BLUR` with Lens Blur), set up with the step list in `depth-background-blur` "DEPTH node setup", then **disable the node(s)** (Ctrl/Cmd+D) — `depth-background-blur` turns them on per clip;
   - `LOOK` empty.
2. Make that clip current, then with `run_script_unsafe`:
   ```python
   tl = project.GetCurrentTimeline(); still = tl.GrabStill()
   album = project.GetGallery().GetCurrentStillAlbum()
   ok = album.ExportStills([still], TEMPLATES_DIR, "base-apple-log", "drx")
   ```
3. List the folder, rename the exported file to the exact template name if Resolve added a suffix, and confirm the file exists.

## 3. Apply as a remote version

Work on a timeline that contains the clips (create one from the bin with `mp.CreateTimelineFromClips(name, [{"mediaPoolItem": c} for c in clips])` if none exists; never rearrange the user's edit). For each video item, matching template by detected version:

```python
item.AddVersion("claude", 1)
item.LoadVersionByName("claude", 1)
g = item.GetNodeGraph()
ok = g.ApplyGradeFromDRX(DRX_PATH, 0)
labels = [g.GetNodeLabel(i) for i in range(1, g.GetNumNodes() + 1)]
```

Batch ≤ 50 items per call. Verify every item: current version is `claude`/remote, labels contain `CST`. If a clip already has a remote version named `claude` with a different grade, ask before overwriting.

Optional: group clips per scene into Color Groups (`project.AddColorGroup(scene)`, `item.AssignToColorGroup(g)`) if the user shoots several scenes; later skills grade per group.

## 4. Verify visually

1. Export a still of 2–3 representative clips with `run_script` and Read them: `item.ExportFrame(item.GetDuration() // 2, {"outputType": "file", "filePath": f"{work}/stills/{clip}-709.png", "maxDimension": 1280})` (21.1.2, `resolve-core` §10: graded frame, playhead untouched). Older Resolve: move the playhead onto the clip (`tl.SetCurrentTimecode`) and `project.ExportCurrentFrameAsStill(f"{work}/stills/{clip}-709.tif")`; if you can't view the TIFF, ask the user to look at the viewer.
2. Check for: clipped highlights, neon saturation or magenta/green shift (wrong log version), crushed blacks.
3. Titles/generators on the timeline are not affected by clip grades; mention it only if RCM was used.

## 5. Report

- table: clip → detected format → template → version applied ✔/✘;
- anything suspicious for the user's eye;
- next step: `chart-match` (works on the `CHART` node before the CST), then skin grade.

## 6. Opt-in: Resolve Color Management route

Only if the user explicitly prefers RCM. Warn first that it changes how every clip and title renders project-wide; get a yes.

1. Read current values from `project.GetSettings()`: `colorScienceMode`, `isAutoColorManage`, `separateColorSpaceAndGamma`, `colorSpaceTimeline`, `colorSpaceTimelineGamma`, `colorSpaceOutput`, `colorSpaceOutputGamma`, `colorSpaceOutputToneMapping`, `colorSpaceOutputGamutMapping`.
2. Set `colorScienceMode` = `davinciYRGBColorManagedv2`, `isAutoColorManage` = `0`, timeline DaVinci Wide Gamut / DaVinci Intermediate, output Rec.709 / `$gamma`, tone mapping DaVinci, gamut mapping saturation compression. Write with one `project.SetSettings({...})` call, then re-read each key; if a value did not stick, ask the user to read the exact dropdown label from Project Settings → Color Management and retry with it.
3. Per clip: `SetClipProperty("Input Color Space", <exact label>)`, re-read. Get the exact label by asking the user to set one clip in the UI (Media Pool → right-click → Input Color Space) and reading it back with `GetClipProperty`.

## Never

- Mix Apple Log and Apple Log 2 templates or LUTs.
- Overwrite an existing grade or remote version without asking.
- Apply a LUT on top of the CST "to be safe" — that double-converts.
