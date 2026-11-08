# Resolve 21.1.2 API reference for davinci-editor

Checked against the MCP server's stubs for 21.1.2 and live on 21.1.2.10 (see `docs/resolve-21.1.2-api-audit.md`). When in doubt, re-check with `search_scripting_api`. `get_whats_new` stops at 21.0.4; API changes per version are in `/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/CHANGELOG.md`.

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
| Transcription progress | `project.GetTranscribeAudioStatus()` → `JobStatus` (`Initializing`, `Analyzing`, `Complete`, `Cancelled`), `CompletionPercentage`, `Error`. Non-blocking since 21.1.1: poll in separate calls; a short `time.sleep` loop inside one call works but must end well before the 60 s timeout | one long sleep waiting for a whole folder |
| Transcript data | `mp_item.GetTranscription()` → `{language, segments:[{start, end, text, speaker, words:[{start, end, text}]}]}`; times are clip timecode strings; text `(...)` marks silence | frames |
| Transcription language | project setting `transcriptionLanguage` (code, e.g. `en`); `speakerDetection` `'0'/'1'`. Ukrainian: `SetSettings({"transcriptionExtendedLanguageSupport": "1"})` first, then `{"transcriptionLanguage": "uk"}`; with extended `"0"`, `"uk"` returns `False`. Changing extended resets the language to `auto` | `uk` without extended; `auto` on short clips (2 s of Ukrainian came back as `es`) |
| Correct a transcript | `mp_item.SetTranscription({"language", "segments": [{"start", "end", "speaker", "words": [{"text", "start", "end"}]}]})` (21.1.2, Studio). Words without times are interpolated; `(...)` silence is derived; unknown speakers are added to the project. Give words a leading space like Resolve's own (`" слово"`): `segment.text` is the plain concatenation of the words | building text from `segment.text` |
| Grade versions | `AddVersion(name, 1)`, `LoadVersionByName(name, 1)`, `GetVersionNameList(1)`, `GetCurrentVersion()`; `1` = remote, `0` = local | |
| Apply template | `item.GetNodeGraph().ApplyGradeFromDRX(path, gradeMode, applyToAllLayers=False)`; gradeMode 0 = no keyframes | `item.ApplyGradeFromDRX` (not on TimelineItem) |
| LUT on node | `graph.SetLUT(node_index, path)`, `graph.GetLUT(node_index)` (path relative to the LUT root) | |
| CDL | `item.SetCDL({"NodeIndex": 3, "Slope": "1 1 1", "Offset": "0 0 0", "Power": "1 1 1", "Saturation": 1.0})` | numbers instead of strings |
| Node info | `graph.GetNumNodes()`, `GetNodeLabel(i)`, `GetToolsInNode(i)`, `SetNodeEnabled(i, bool)` (1-based) | creating nodes (impossible) |
| Color groups | `project.AddColorGroup(name)`, `project.GetColorGroupsList()`, `item.AssignToColorGroup(group)`, `group.GetPreClipNodeGraph()` | |
| Copy grade | `src_item.CopyGrades([dst_items])` | |
| Still for analysis | 21.1.2: `tl.ExportFrame(offset_from_tl_start, {"outputType": "file", "filePath": p, "maxDimension": 0})` or `item.ExportFrame(offset_from_item_start, {...})` → `{"success", "error"}`; finished frame (grade, all tracks, titles), `.tif` = 16-bit, no playhead move, works in `run_script`. Older: playhead + `project.ExportCurrentFrameAsStill(path)` (renders wherever the playhead is) | `tl.ExportCurrentFrameAsStill`; `item.ExportFrame` on a generator ("not a media item") |
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
| Clip EQ / audio effects | 21.1.2: `item.AddEffect("audio", "Audio FX/Fairlight FX/Reverb")` (ids from `resolve.GetEffectsList("audio")`), `item.GetEffects("audio")`, `item.DeleteEffects([...])`: adds/removes the plugin with default settings, **no parameter API**. Parameters: `src.CopyAttributes([targets], {"audioEqualizer": True, "audioPlugins": True})` (Paste Attributes) from a set-up reference item. No API for Music Remixer or track Dynamics | `allAudioAttributes` (also pastes volume) |
| Video effects | 21.1.2: `resolve.GetEffectsList("video")` → `[{"category": "fusion"/"ofx", "id", "name"}]` (MotionVFX Fusion effects included); `item.AddEffect(cat, id)` → `Effect` or `None` (generators don't take effects); `Effect.GetInfo()`, `Get/SetIsEnabled`, `Get/SetIndex` (order); Fusion effect parameters via `effect.GetFusionComp().FindTool(<macro name>).SetInput(id, v)`; OFX: `GetFusionComp()` is `None`, parameters only in the Inspector | OFX parameters by script |
| Clip pan | `item.SetProperties({"AudioPanEnabled": True, "AudioPan": -100…100})`, re-read `GetProperties()` | pan keyframes: **no API** |
| Measure loudness, no render | 21.1.2: `item.AnalyzeAudioLevels(mode)` → `{"Integrated": LUFS, "TruePeak": dBTP}` per item (`-100.0` = nothing measured); `mode` from `GetNormalizeAudioModes()` except the peak-only two. All 12 standards gave identical numbers on a test tone, so don't expect different values per mode. Per item only: the mix still needs a mixdown render | summing items into a mix value |
| Loudness | `tl.GetNormalizeAudioModes()` (21.1.2: `Sample Peak Program`, `True Peak`, `ITU-R BS.1770-1`, `ITU-R BS.1770-4`, `ATSC A/85`, `EBU R128`, `OP-59`, `TR-B32`, `AGCOM 219/09/CSP`, `Netflix`, `YouTube`, `Disney - 2.0`, `Disney - 5.1+`, `TencentVideo`), `tl.NormalizeAudioLevel(items, {"normalizationMode": m, "targetLoudness": -14.0, "setLevelMode": resolve.NORMALIZE_AUDIO_SET_LEVEL_INDEPENDENT})` | |
| Dialogue leveler | item properties `AudioDialogueLevelerEnabled`, `AudioDialogueLevelerMode` (`resolve.DIALOGUE_LEVELER_MODE_*`), `…ReduceLoudDialogue`, `…LiftSoftDialogue`, `…BackgroundReduction`, `…OutputGain` 0–6; active timeline only | |
| Titles / generators | `tl.InsertFusionTitleIntoTimeline(name)`, `tl.InsertTitleIntoTimeline(name)`, `tl.InsertFusionGeneratorIntoTimeline(name)` (at the playhead) | |
| Fusion inputs | `comp = item.GetFusionCompByIndex(1)`, `tool = comp.FindTool(name)` or `comp.GetToolList()`, `tool.GetInputList()`, `tool.SetInput(id, value, time)` | |
| Audio-only mixdown | `project.SetCurrentRenderFormatAndCodec(fmt, codec)` (discover with `GetRenderFormats()`, `GetRenderCodecs(ext)`), `SetRenderSettings({"ExportVideo": False, "ExportAudio": True, "TargetDir": d, "CustomName": n, "SelectAllFrames": True})`, `AddRenderJob()`, `StartRendering([job])`, poll `IsRenderingInProgress()`, `GetRenderJobStatus(job)` | |

## Resolve 21.1.2 editing calls

All verified live on 21.1.2.10 (`docs/resolve-21.1.2-api-audit.md` §3). Gate them as in `resolve-core` §10.

```python
GATE = resolve.GetVersion()[:3] >= [21, 1, 2]
```

**Frame export** (replaces playhead + `ExportCurrentFrameAsStill`):

```python
r = tl.ExportFrame(frame - tl.GetStartFrame(), {"outputType": "file", "filePath": f"{WORK}/stills/x.tif"})
# or, relative to the item's first frame: item.ExportFrame(frame - item.GetStart(), {...})
# previews: add "maxDimension": 1280 (the longer edge); values stay the same, only fewer pixels
assert r["success"], r.get("error")
```

The frame is the finished picture: grade, every enabled track, Fusion titles. `.tif` is 16-bit RGB at timeline resolution, `.png`/`.jpg` 8-bit. `"outputType": "encodedString"` returns base64 in `r["data"]` (no file, but nothing in the sandbox can decode it, so use files). Paths are Mac paths (Resolve writes them), so in Cowork apply the `resolve-core` §8 mapping.

**Trims and roll edits.** `n` is the handle that stays beyond the edge after the call:

```python
lo, ro = item.GetLeftOffset(), item.GetRightOffset()
item.SetRightOffset(ro + k, False, False)   # end k frames earlier (trim), gap left behind, no ripple
item.SetRightOffset(ro - k, False, False)   # end k frames later; overwrites the next item's head on the same track
item.SetLeftOffset(lo + k, False, False)    # start k frames later
```

- An L-cut (A's sound under B's picture) is `A_audio.SetRightOffset(ro - k, False, False)`; a J-cut is `B_audio.SetLeftOffset(lo - k, False, False)`. One call each; the neighbour's audio edge is overwritten and comes back with the inverse call (verified).
- `updateLinkedItems=True` (the default) gives linked items the same offset **value**: a linked still jumped to frame 3 384 281. Always `False`; trim the video yourself if it must follow.
- `k` can't exceed the handle (`ro`/`lo`). Generators, titles, Fusion compositions: no handles, `False`.
- After a trim, re-read `GetStart()`, `GetEnd()`, both offsets, and the neighbours.

**Placement:** `item.SetPosition({"trackIndex": t, "startFrame": f}, False)`; `tl.MoveItems(items, {"trackIndex": t, "startFrame": f}, False)` moves the leftmost item there and the rest keep their spacing; fails as a whole if any item can't land. `tl.DeleteGaps()` closes every gap on the timeline (guarded).

**Silence:** `item.RippleDeleteSilence({"threshold": -25.0, "preHead": 2, "postTail": 4, "minimumToStrip": fps})` on an audio item. It ripples **every unlocked track**, linked or not; a locked track is left as it was (verified). Guarded by `guard.py`. Duplicate the timeline first.

**Effects:**

```python
ids = {e["name"]: e["id"] for e in resolve.GetEffectsList("video")}
fx = item.AddEffect("fusion", ids["mHowTo Zoom"])            # None on generators / titles
macro = fx.GetFusionComp().FindTool("mHowTo_Zoom")          # the macro tool; list with comp.GetToolList(False)
macro.SetInput("Input4", 1.8)                                 # ids from macro.GetInputList(): INPS_ID → INPS_Name
fx.SetIsEnabled(False); fx.SetIndex(1)                        # order among effects of the same category
item.DeleteEffects(item.GetEffects("ofx"))                    # guarded
```

Verified `mHowTo Zoom` inputs: `Input2` Reverse, `Input3` Movement Target (`{1: x, 2: y}`), `Input4` Zoom Scale (default 0.3), `Input5`/`Input6` Movement Ease In/Out, `Input7`/`Input8` Grid / Grid Opacity, `Input9` Color Split Amount. Other macros: read `GetInputList()` first, never guess ids.

**Generated speech:** `project.GenerateSpeech({"TextInput": ≤350 chars, "VoiceModel": "Female 1", "Filename": n})` needs the AI Speech Generator Extra and writes the WAV into the **project's media location** (`…/Audio Files/SpeechGenerator/`), not into `work_dir`. `Female 1` does not pronounce Ukrainian (a Ukrainian line came back from transcription as nonsense); English only, as a placeholder.

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

Observed on 21.1.2.10 (audio clip, 60 fps): `startFrame` 0, `endFrame` 99 gave 99 frames from source 0, i.e. exclusive with no offset. Still run the calibration each session; for stills the range is ignored (they take the *Standard still duration*).

- `duration == 11` → `endFrame` is inclusive: pass `end_exclusive - 1`.
- `duration == 10` → exclusive: pass `end_exclusive`.
- `source_start != 10` → there is an offset; add `10 - source_start` to every `startFrame`/`endFrame`.

Then delete only that scratch timeline (`mp.DeleteTimelines([tl])`) and switch back to the user's timeline. Remember the result for the rest of the session.

## Settings that need runtime discovery

These values are not documented for 21.1.x; discover them on the running app, never hard-code a guess:

- the Ukrainian transcription code is settled (`uk` with the extended model on, see the table); still check `GetTranscription()["language"]` after transcribing, since a missing Extras package falls back silently;
- the exact `Input Color Space` strings for Apple Log / Apple Log 2: read `GetClipProperty()["Input Color Space"]` from a clip the user already set in the UI;
- whether a transcript word's `end` timecode is its last frame or the first frame after it (`text-based-cut` assumes last frame; check one word against the waveform);
- valid `colorScienceMode` / `colorSpace*` strings: read current values with `project.GetSettings()[key]` before writing.
- units and signs of `Pan`/`Tilt` (pixels from center; is positive Tilt up?) and whether `ZoomX` 1.0 = 100 %: set one item, export a still, check it before laying out the rest;
- whether `InsertFusionTitleIntoTimeline` accepts the template's file name as shown in the Effects library (the track is settled: it ripple-inserts on the lowest video track at the playhead, verified with `Text+` and V2 present);
- whether `ApplyFairlightPresetToCurrentTimeline` replaces the timeline's tracks and busses (apply it on a duplicate timeline first);
- whether timeline items built by `AppendToTimeline` keep the media pool clip's color group;
- `CopyAttributes` (`audio-effects`): whether a source item on another timeline works, whether pasted plugins replace or stack on existing ones, whether it carries Music Remixer state; which `AudioPan` sign is left; whether `GetProperties()` on a music item shows any Remixer/stem key;
- Fusion: the comp frame that matches a timeline item's first frame (`comp.GetAttrs()["COMPN_RenderStart"]`, `["COMPN_GlobalStart"]`), the input ids of `TextPlus`, `Background`, `Transform`, `Merge` (`tool.GetInputList()`), and whether `SetInput(id, value, time)` keys an input only after `tool.AddModifier(id, "BezierSpline")` (`"XYPath"` for point inputs such as `Center`; the builder's `mismatches` shows it);
- the track `InsertFusionCompositionIntoTimeline()` uses and the length of the item it creates (the user preference *Standard generator duration*; Fusion compositions and generators have no handles, so `SetRightOffset` returns `False` on them);
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
        rows.append({"name": it.GetName(), "item_id": it.GetUniqueId(), "clip_id": mpi.GetUniqueId() if mpi else None,
                     "start": it.GetStart(), "end": it.GetEnd(),
                     "source_start": it.GetSourceStartFrame(), "source_end": it.GetSourceEndFrame(),
                     "left_offset": it.GetLeftOffset(), "right_offset": it.GetRightOffset(),
                     "enabled": it.GetClipEnabled(), "speed": (it.GetSpeed() or {}).get("Percentage", 100.0),
                     "online": p.get("Online Status"), "file": p.get("File Path"), "fps": p.get("FPS"),
                     "resolution": p.get("Resolution"), "color": it.GetClipColor(),
                     "fusion_comps": it.GetFusionCompCount() if kind == "video" else 0})
    return rows

dump = {"name": tl.GetName(), "timeline_id": tl.GetUniqueId(), "fps": float(s["timelineFrameRate"]), "drop_frame": s.get("timelineDropFrameTimecode") == "1",
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

Timeline markers in the dump are relative to `start_frame` (add it to get absolute frames). `left_offset` / `right_offset` are the media handles (frames the item can be extended by on each side); verified on 21.1.2: a 360-frame clip placed as source 0..99 reads `left_offset` 0, `right_offset` 261. Generators and stills return `None` / very large handles. `source_end` is not consistently exclusive: 99 for a 99-frame item from source 0, but 359 for the full 360-frame clip; take lengths from `end - start`, not from source frames. Words on the timeline:

```bash
python3 <plugin>/skills/resolve-core/scripts/timeline_map.py words "<work>/timeline-<name>.json" "<work>/transcripts" \
  --track Voice --source-offset <calibration offset> --out "<work>/words-<name>.json"
```

Items with a speed change or disabled are skipped with a warning; report those warnings, don't drop them silently.

## Handoff snapshot

The last step of every Claude write to the timeline (end of a skill, each critic fix round, critic and QC Cream markers, an `edit-episode` stop) is a snapshot: the timeline dump above plus what `edit-memory` compares. Run the dump code, then this in the same `run_script_unsafe` call:

```python
import datetime
PROPS = ("ZoomX", "ZoomY", "Pan", "Tilt", "Opacity", "AudioVolume")

def fusion_of(it):
    comp = it.GetFusionCompByIndex(1) if it.GetFusionCompCount() else None
    tools = comp.GetToolList(False, "TextPlus") if comp else {}
    if not tools:
        return None
    text = sorted(tools.values(), key=lambda t: t.GetAttrs()["TOOLS_Name"])[0]
    center = text.GetInput("Center") or {}
    return {"text": text.GetInput("StyledText"), "center": [center.get(1), center.get(2)], "size": text.GetInput("Size")}

for kind, tracks in dump["tracks"].items():
    for t in tracks:
        for row, it in zip(t["items"], tl.GetItemListInTrack(kind, t["index"]) or []):
            row["props"] = {k: it.GetProperty(k) for k in PROPS}
            row["fades"] = it.GetFades() if kind != "subtitle" else None
            row["fusion"] = fusion_of(it) if kind == "video" else None
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
path = os.path.join(WORK, "handoff", f"{dump['timeline_id']}-{stamp}.json")
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as f:
    json.dump(dump, f, ensure_ascii=False, indent=1)
result = {"path": path}
```

The time stamp lives only in the file name: `memory.py changed` compares the JSON, so a field with the time would make every snapshot differ. The fresh state passed to `changed` and `diff` is made with the same script (written to a scratch path, not to `handoff/`); a plain dump lacks `props` / `fades` / `fusion`, and `changed` then compares only the fields both files carry. `owner` and `kind` come from the `placed` ledger, not from the snapshot. The first Text+ by tool name stands for a comp's text; other text tools, keyframes inside Fusion beyond these inputs, volume keyframes (no API) and grades are not compared. Markers whose `customData` starts with `claude:` are ignored by both `changed` and `diff`.

```bash
python3 <plugin>/skills/edit-memory/scripts/memory.py changed "<last handoff>.json" "<fresh>.json"    # exit 1 = changed
python3 <plugin>/skills/edit-memory/scripts/memory.py diff "<last handoff>.json" "<fresh>.json" --ledger "<work>/placed-<timeline>.json" --out "<work>/handoff/events.json"
```

Events: `moved` (start off by more than 1 frame after ripple compensation: each old frame takes the observed start change of the A-roll / Screen piece over it, or of the next piece after a gap, so cuts, inserts and lifts on those tracks are not moves), `retimed` (length change on other tracks, in frames), `cut_changed` (length change or removal of an A-roll / Screen item), `deleted`, `added_by_user`, `text_changed`, `property_changed` (one event per property, with `property` and a numeric delta: `ZoomX`, `Pan`, `Opacity`, `FadeIn`, `Center.x`, `Size`, ...), `volume_changed` (`AudioVolume` delta), `track_changed` (by track name, so an inserted track is not a change). Items match by `item_id`, then media by track role + `clip_id` + overlapping source range, then Fusion items by role + text + nearest start after the shift.

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
    for k, m in t.get("modifiers", {}).items():
        tool.AddModifier(k, m["id"])   # the input's current value (e.g. the text) moves into the modifier
        mod = getattr(tool, k).GetConnectedOutput().GetTool()
        made[f"{t['name']}.{k}"] = mod
        for mk, v in m.get("inputs", {}).items():
            mod.SetInput(mk, fix(v))
    for target, keys in [(tool, t.get("keys", {}))] + \
            [(made[f"{t['name']}.{k}"], m.get("keys", {})) for k, m in t.get("modifiers", {}).items()]:
        for k, frames in keys.items():
            point = isinstance(next(iter(frames.values())), dict)
            target.AddModifier(k, "XYPath" if point else "BezierSpline")   # point inputs animate on a path
            for f, v in frames.items():
                target.SetInput(k, fix(v), float(f))
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
    keyed = [(tool, k, f) for k, f in t.get("keys", {}).items()] + \
        [(made[f"{t['name']}.{mk}"], k, f) for mk, m in t.get("modifiers", {}).items() for k, f in m.get("keys", {}).items()]
    for tool, k, frames in keyed:
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

Vector inputs (`Center`, `Pivot`) take `{1: x, 2: y}` tables in Python and are animated with an `XYPath` modifier; numbers use `BezierSpline`. A non-empty `mismatches` means keys didn't land: stop and report, don't continue to the next item. `MediaIn1`/`MediaOut1` already exist in a clip's comp; connect the last tool to `MediaOut1.Input`. Use `comp.Lock()`/`Unlock()` so Fusion doesn't open dialogs mid-build. Verified in 21.1.1: a spec's `modifiers` (`TextScramble`, `StyledTextFollower` on `StyledText`) take the text along into their own `InputText` / `Text`, and keys on modifier inputs land like tool keys; Text+ and Follower `SelectTransform` is 0 characters / 1 words / 2 lines, Follower `Order` 1 = left to right. Not yet confirmed on a render: that a `RectangleMask`'s `Width` / `Height` / `SoftEdge` are frame-width units (`fade-reveal` assumes it; the first stills show it).

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
