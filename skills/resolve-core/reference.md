# Resolve 21.1.1 API reference for davinci-editor

Checked against the MCP server's stubs for 21.1.1. When in doubt, re-check with `search_scripting_api`.

## Signatures that differ from older docs and blog posts

| Need | Correct call (21.x) | Common wrong guess |
|---|---|---|
| Project / timeline settings | `project.GetSettings()[key]`, `project.SetSettings({key: value})`; same on `Timeline` | `GetSetting(key)` / `SetSetting(key, value)` (deprecated) |
| Clip properties | `clip.GetClipProperty()[key]` to read; `clip.SetClipProperty(key, value)` to write | `GetClipProperty(key)` (deprecated) |
| Timeline item properties (volume, zoom, crop…) | `item.SetProperties({...})`, `item.GetProperties()` | `SetProperty(key, value)` |
| Clip volume | `item.SetProperties({"AudioVolumeEnabled": True, "AudioVolume": -6.0})`, range -100…+30 dB | `SetClipProperty("Volume")` |
| Voice isolation, item | `item.SetVoiceIsolationState({"isEnabled": True, "amount": 60})` | |
| Voice isolation, track | `tl.SetVoiceIsolationState(track_index, {"isEnabled": True, "amount": 60})` | |
| Transcribe | `mp_item.TranscribeAudio(useSpeakerDetection=None, transcribeAsNestedClip=False)`, `folder.TranscribeAudio(...)` | timeline transcription |
| Transcription progress | `project.GetTranscribeAudioStatus()` → `JobStatus` (`Initializing`, `Analyzing`, `Complete`, `Cancelled`), `CompletionPercentage`, `Error` | sleeping inside the script |
| Transcript data | `mp_item.GetTranscription()` → `{language, segments:[{start, end, text, speaker, words:[{start, end, text}]}]}`; times are clip timecode strings; text `(...)` marks silence | frames |
| Transcription language | project setting `transcriptionLanguage` (code, e.g. `en`); `speakerDetection` `'0'/'1'` | |
| Grade versions | `AddVersion(name, 1)`, `LoadVersionByName(name, 1)`, `GetVersionNameList(1)`, `GetCurrentVersion()`; `1` = remote, `0` = local | |
| Apply template | `item.GetNodeGraph().ApplyGradeFromDRX(path, gradeMode, applyToAllLayers=False)`; gradeMode 0 = no keyframes | `item.ApplyGradeFromDRX` (not on TimelineItem) |
| LUT on node | `graph.SetLUT(node_index, path)`, `graph.GetLUT(node_index)` (path relative to the LUT root) | |
| CDL | `item.SetCDL({"NodeIndex": 3, "Slope": "1 1 1", "Offset": "0 0 0", "Power": "1 1 1", "Saturation": 1.0})` | numbers instead of strings |
| Node info | `graph.GetNumNodes()`, `GetNodeLabel(i)`, `GetToolsInNode(i)`, `SetNodeEnabled(i, bool)` (1-based) | creating nodes (impossible) |
| Color groups | `project.AddColorGroup(name)`, `project.GetColorGroupsList()`, `item.AssignToColorGroup(group)`, `group.GetPreClipNodeGraph()` | |
| Copy grade | `src_item.CopyGrades([dst_items])` | |
| Still for analysis | `project.ExportCurrentFrameAsStill(path)` (format from extension; use `.tif`) | `tl.ExportCurrentFrameAsStill` |
| Template capture | `tl.GrabStill()` → `GalleryStill`; `project.GetGallery().GetCurrentStillAlbum().ExportStills([still], folder, prefix, "drx")` | |
| Build timeline | `mp.CreateEmptyTimeline(name)` then `mp.AppendToTimeline([{"mediaPoolItem", "startFrame", "endFrame", "mediaType", "trackIndex", "recordFrame"}])`; `mediaType` 1 = video only, 2 = audio only | |
| Remove from timeline | `tl.DeleteClips(items, rippleDelete=False)` | |
| Markers | `obj.AddMarker(frameId, color, name, note, duration, customData)`; timeline markers use frames relative to timeline start, clip markers relative to clip start | |
| Selection | `tl.GetSelectedClips()` (21.0.4+), `mp.GetSelectedClips()` | |
| Fairlight presets | `resolve.GetFairlightPresets()`, `project.ApplyFairlightPresetToCurrentTimeline(name)` | |
| Background tasks | `resolve.DisableBackgroundTasksForCurrentResolveSession()` | |
| Read a CDL back | not possible: there is no `GetCDL`; verify a CDL by exporting a still and measuring it | trusting `SetCDL`'s `True` |
| Enable / disable node | `graph.SetNodeEnabled(i, bool)`; there is no getter, so record what you set | |
| Color group graphs | `group.GetPreClipNodeGraph()`, `group.GetPostClipNodeGraph()`, `group.GetClipsInTimeline(tl)`, `item.GetColorGroup()` | |
| New project | `pm.CreateProject(name, mediaLocationPath=None)` (switches the open project; `None` if the name exists), `pm.SaveProject()` | |
| Bins, import | `mp.AddSubFolder(parent, name)`, `mp.SetCurrentFolder(f)`, `mp.ImportMedia([{"FilePath": p}])` or `mp.ImportMedia([path, …])` → items in the current folder | |
| Proxies | project settings `perfProxyMediaMode`, `perfProxyResolutionRatio`; `clip.LinkProxyMedia(path)`; **no API to generate proxies** | |
| Sync two clips by sound | `tl.AutoAlignClips(items, {"SyncUsing": resolve.AUTO_ALIGN_CLIPS_USING_WAVEFORM})` on a timeline; `mp.AutoSyncAudio(items, {"syncMode": resolve.AUDIO_SYNC_WAVEFORM})` merges separate audio into a video clip | own cross-correlation |
| Transform / PiP | `item.SetProperties({"ZoomX", "ZoomY", "Pan", "Tilt", "CropLeft", "CropRight", "CropTop", "CropBottom", "CropSoftness", "Opacity"})`, re-read `GetProperties()` | |
| Fades | `item.SetFades({"FadeIn": frames, "FadeOut": frames})`, `GetFades()` (video or audio fader) | volume keyframes: **no API** |
| Loudness | `tl.GetNormalizeAudioModes()`, `tl.NormalizeAudioLevel(items, {"normalizationMode": m, "targetLoudness": -14.0, "setLevelMode": resolve.NORMALIZE_AUDIO_SET_LEVEL_INDEPENDENT})` | |
| Dialogue leveler | item properties `AudioDialogueLevelerEnabled`, `AudioDialogueLevelerMode` (`resolve.DIALOGUE_LEVELER_MODE_*`), `…ReduceLoudDialogue`, `…LiftSoftDialogue`, `…BackgroundReduction`, `…OutputGain` 0–6; active timeline only | |
| Titles / generators | `tl.InsertFusionTitleIntoTimeline(name)`, `tl.InsertTitleIntoTimeline(name)`, `tl.InsertFusionGeneratorIntoTimeline(name)` (at the playhead) | |
| Fusion inputs | `comp = item.GetFusionCompByIndex(1)`, `tool = comp.FindTool(name)` or `comp.GetToolList()`, `tool.GetInputList()`, `tool.SetInput(id, value, time)` | |
| Audio-only mixdown | `project.SetCurrentRenderFormatAndCodec(fmt, codec)` (discover with `GetRenderFormats()`, `GetRenderCodecs(ext)`), `SetRenderSettings({"ExportVideo": False, "ExportAudio": True, "TargetDir": d, "CustomName": n, "SelectAllFrames": True})`, `AddRenderJob()`, `StartRendering([job])`, poll `IsRenderingInProgress()`, `GetRenderJobStatus(job)` | |

## Extras downloads

Some calls silently fall back when the Extras package is missing (Resolve menu → Extras Download Manager): extended transcription language models, AI IntelliSearch, AI Slate ID, AI Speech Generator. Always verify the result (e.g. the `language` field of the transcript), not just the return value.

## Append calibration

Run once per session before building a timeline from frame ranges. It answers: is `endFrame` inclusive, and do source frames start at 0?

```python
mp = project.GetMediaPool()
clip = <a video media pool item, e.g. the first clip in the footage bin>
tl = mp.CreateEmptyTimeline("claude-calibration")
project.SetCurrentTimeline(tl)
items = mp.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": 10, "endFrame": 20, "mediaType": 1, "trackIndex": 1, "recordFrame": tl.GetStartFrame()}])
it = items[0]
result = {"duration": it.GetDuration(), "source_start": it.GetSourceStartFrame(), "source_end": it.GetSourceEndFrame(), "start": it.GetStart(), "tl_start": tl.GetStartFrame()}
```

- `duration == 11` → `endFrame` is inclusive: pass `end_exclusive - 1`.
- `duration == 10` → exclusive: pass `end_exclusive`.
- `source_start != 10` → there is an offset; add `10 - source_start` to every `startFrame`/`endFrame`.

Then delete only that scratch timeline (`mp.DeleteTimelines([tl])`) and switch back to the user's timeline. Remember the result for the rest of the session.

## Settings that need runtime discovery

These values are not documented for 21.1.1; discover them on the running app, never hard-code a guess:

- the code Resolve expects in `transcriptionLanguage` for Ukrainian: set the configured code, read it back, transcribe a short clip and check `GetTranscription()["language"]`;
- the exact `Input Color Space` strings for Apple Log / Apple Log 2: read `GetClipProperty()["Input Color Space"]` from a clip the user already set in the UI;
- whether a transcript word's `end` timecode is its last frame or the first frame after it (`text-based-cut` assumes last frame; check one word against the waveform);
- valid `colorScienceMode` / `colorSpace*` strings: read current values with `project.GetSettings()[key]` before writing.
- units and signs of `Pan`/`Tilt` (pixels from center; is positive Tilt up?) and whether `ZoomX` 1.0 = 100 %: set one item, export a still, check it before laying out the rest;
- the track `InsertFusionTitleIntoTimeline` uses (expected: the highest enabled video track at the playhead) and whether it accepts the template's file name as shown in the Effects library;
- whether `ApplyFairlightPresetToCurrentTimeline` replaces the timeline's tracks and busses (apply it on a duplicate timeline first);
- the `normalizationMode` string for integrated loudness in `GetNormalizeAudioModes()` (expected to mention BS.1770 / LUFS);
- whether timeline items built by `AppendToTimeline` keep the media pool clip's color group;
- Fusion: the comp frame that matches a timeline item's first frame (`comp.GetAttrs()["COMPN_RenderStart"]`, `["COMPN_GlobalStart"]`), the input ids of `TextPlus`, `Background`, `Transform`, `Merge` (`tool.GetInputList()`), and whether `SetInput(id, value, time)` keys an input only after `tool.AddModifier(id, "BezierSpline")` (`"XYPath"` for point inputs such as `Center`; the builder's `mismatches` shows it);
- the track `InsertFusionCompositionIntoTimeline()` uses and the length of the item it creates (the user preference *Standard generator duration*; there is no API to trim an item);
- how `mp.ImportMedia([srt])` + `AppendToTimeline` places an SRT on a subtitle track, and whether SRT time 0 lands on the timeline start or on 00:00:00:00;
- the H.265 codec key from `GetRenderCodecs("mp4")` (hardware vs software encoder names) and the unit of `VideoQuality` when it is an integer (kbit/s expected);
- which items `SmartReframe()` accepts (expected: video items on a timeline whose aspect differs from the source) and how long `GetSmartReframeStatus()` takes per minute.

## Timeline dump

Stage-3 skills read the cut timeline through one JSON dump, written with `run_script_unsafe` to `<work>/timeline-<timeline name>.json`, and pass it to `scripts/timeline_map.py` (words ↔ timeline frames), `pre-delivery-qc` and `shorts-cutdown`. Dump again after any edit: item positions change.

```python
import json, os
tl = project.GetCurrentTimeline()
s = tl.GetSettings()

def items(kind, i):
    rows = []
    for it in tl.GetItemListInTrack(kind, i) or []:
        mpi = it.GetMediaPoolItem()
        p = mpi.GetClipProperty() if mpi else {}
        rows.append({"name": it.GetName(), "clip_id": mpi.GetUniqueId() if mpi else None,
                     "start": it.GetStart(), "end": it.GetEnd(),
                     "source_start": it.GetSourceStartFrame(), "source_end": it.GetSourceEndFrame(),
                     "enabled": it.GetClipEnabled(), "speed": (it.GetSpeed() or {}).get("Percentage", 100.0),
                     "online": p.get("Online Status"), "file": p.get("File Path"), "fps": p.get("FPS"),
                     "resolution": p.get("Resolution"), "color": it.GetClipColor(),
                     "fusion_comps": it.GetFusionCompCount() if kind == "video" else 0})
    return rows

dump = {"name": tl.GetName(), "fps": float(s["timelineFrameRate"]), "drop_frame": s.get("timelineDropFrameTimecode") == "1",
        "width": int(s["timelineResolutionWidth"]), "height": int(s["timelineResolutionHeight"]),
        "start_frame": tl.GetStartFrame(), "end_frame": tl.GetEndFrame(), "start_tc": tl.GetStartTimecode(),
        "markers": {str(f): m for f, m in tl.GetMarkers().items()},
        "tracks": {k: [{"index": i, "name": tl.GetTrackName(k, i), "enabled": tl.GetIsTrackEnabled(k, i),
                        "locked": tl.GetIsTrackLocked(k, i), "items": items(k, i)}
                       for i in range(1, tl.GetTrackCount(k) + 1)] for k in ("video", "audio", "subtitle")}}
os.makedirs(WORK, exist_ok=True)
path = os.path.join(WORK, f"timeline-{tl.GetName()}.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(dump, f, ensure_ascii=False, indent=1)
result = {"path": path, "items": {k: sum(len(t["items"]) for t in v) for k, v in dump["tracks"].items()}}
```

Timeline markers in the dump are relative to `start_frame` (add it to get absolute frames). Words on the timeline:

```bash
python3 <plugin>/skills/resolve-core/scripts/timeline_map.py words "<work>/timeline-<name>.json" "<work>/transcripts" \
  --track Voice --source-offset <calibration offset> --out "<work>/words-<name>.json"
```

Items with a speed change or disabled are skipped with a warning; report those warnings, don't drop them silently.

## Fusion builds from a spec

`fusion-motion-graphics` and `tutorial-zooms` don't type Fusion node code by hand each time: their scripts write a spec JSON (`{"tools": [{"name", "id", "inputs": {id: value}, "keys": {id: {frame: value}}, "connect": {input: "Tool.Output"}}]}`), and one builder applies it in a Fusion comp:

```python
def fix(v):
    """JSON turns {1: x, 2: y} into {"1": x, "2": y}; Fusion wants number keys."""
    return {int(k): x for k, x in v.items()} if isinstance(v, dict) else v

spec = json.load(open(SPEC, encoding="utf-8"))
comp = item.GetFusionCompByIndex(1) or item.AddFusionComp()
comp.Lock()
made = {}
for t in spec["tools"]:
    tool = comp.FindTool(t["name"]) or comp.AddTool(t["id"], -32768, -32768)
    tool.SetAttrs({"TOOLS_Name": t["name"]})
    made[t["name"]] = tool
for t in spec["tools"]:
    tool = made[t["name"]]
    for k, v in t.get("inputs", {}).items():
        tool.SetInput(k, fix(v))
    for k, frames in t.get("keys", {}).items():
        point = isinstance(next(iter(frames.values())), dict)
        tool.AddModifier(k, "XYPath" if point else "BezierSpline")   # point inputs animate on a path
        for f, v in frames.items():
            tool.SetInput(k, fix(v), float(f))
    for k, src in t.get("connect", {}).items():
        name, out = src.split(".")
        target = made.get(name) or comp.FindTool(name)
        tool.ConnectInput(k, target)
    for k, expr in t.get("expressions", {}).items():
        inp = next(i for i in tool.GetInputList().values() if i.GetAttrs()["INPS_ID"] == k)
        inp.SetExpression(expr)
comp.Unlock()
result, bad = {}, []
for t in spec["tools"]:
    tool = made[t["name"]]
    result[t["name"]] = {k: tool.GetInput(k) for k in t.get("inputs", {})}
    for k, frames in t.get("keys", {}).items():
        # first, middle, last key: ends are often the rest state, only the middle proves the keys landed
        order = sorted(frames, key=float)
        probe = [order[0], order[len(order) // 2], order[-1]]
        got = [tool.GetInput(k, float(f)) for f in probe]
        result[t["name"]][k] = dict(zip(probe, got))
        want = fix(frames[probe[1]])
        mid = got[1]
        same = (abs(mid[1] - want[1]) < 1e-3 and abs(mid[2] - want[2]) < 1e-3) if isinstance(want, dict) and mid \
            else (mid is not None and abs(mid - want) < 1e-3)
        if not same:
            bad.append(f"{t['name']}.{k} @ {probe[1]}: got {mid}, want {want}")
result["mismatches"] = bad
```

Vector inputs (`Center`, `Pivot`) take `{1: x, 2: y}` tables in Python and are animated with an `XYPath` modifier; numbers use `BezierSpline`. A non-empty `mismatches` means keys didn't land: stop and report, don't continue to the next item. `MediaIn1`/`MediaOut1` already exist in a clip's comp; connect the last tool to `MediaOut1.Input`. Use `comp.Lock()`/`Unlock()` so Fusion doesn't open dialogs mid-build.

## Upgrading a stage-1 template

```python
for item in items:                                   # remote "claude" version loaded
    g = item.GetNodeGraph()
    chart = next(i for i in range(1, g.GetNumNodes() + 1) if g.GetNodeLabel(i) == "CHART")
    lut = g.GetLUT(chart)
    ok = g.ApplyGradeFromDRX(NEW_TEMPLATE, 0)
    chart = next(i for i in range(1, g.GetNumNodes() + 1) if g.GetNodeLabel(i) == "CHART")
    if lut:
        g.SetLUT(chart, lut)
    rows.append({"clip": item.GetName(), "ok": ok, "lut": g.GetLUT(chart), "labels": [g.GetNodeLabel(i) for i in range(1, g.GetNumNodes() + 1)]})
result = rows
```
