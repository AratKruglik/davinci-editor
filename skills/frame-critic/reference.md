# frame-critic reference

Scripts for `run_script` (sandboxed: no files, no `os`). Resolve objects don't survive between calls, so each script fetches the timeline again by its unique id. Upper-case names are values you fill in.

## Make the checked timeline current

`get_image`, `get_thumbnails` and the timeline dump only see the current timeline. Remember the user's one and switch:

```python
project = resolve.GetProjectManager().GetCurrentProject()
previous = project.GetCurrentTimeline()
timelines = [project.GetTimelineByIndex(i) for i in range(1, project.GetTimelineCount() + 1)]
target = next((t for t in timelines if t.GetName() == TIMELINE_NAME), None)
if target is not None and target.GetUniqueId() != previous.GetUniqueId():
    project.SetCurrentTimeline(target)
current = project.GetCurrentTimeline()
result = {"previous": previous.GetName(), "previous_id": previous.GetUniqueId(),
          "current": current.GetName(), "current_id": current.GetUniqueId(), "found": target is not None}
```

At the end (also when you stop early) switch back the same way to `previous_id` and re-read `GetCurrentTimeline().GetUniqueId()`.

## Measure one element

One script per element, at the element's `full` frame (absolute). It records the enabled state of every video track, renders the full composite, disables only the element's track, renders again, and restores the recorded state in `finally`, then reads it back. Never split this into two calls: a failure between them would leave the user's track disabled.

```python
TIMELINE_ID = "<timeline_id from the dump>"
FRAME = 0          # element "full", absolute timeline frame
TRACK = 0          # video track index of the element (from the dump, by its track name)
ON = "<mac work>/critic/<item_id>-on.tif"
OFF = "<mac work>/critic/<item_id>-off.tif"

project = resolve.GetProjectManager().GetCurrentProject()
tl = project.GetCurrentTimeline()
if tl.GetUniqueId() != TIMELINE_ID:
    result = {"error": "the checked timeline is not current", "current": tl.GetName()}
else:
    tracks = range(1, tl.GetTrackCount("video") + 1)
    before = {i: bool(tl.GetIsTrackEnabled("video", i)) for i in tracks}
    offset = FRAME - tl.GetStartFrame()
    on = off = None
    try:
        on = tl.ExportFrame(offset, {"outputType": "file", "filePath": ON, "maxDimension": 0})
        tl.SetTrackEnable("video", TRACK, False)
        off = tl.ExportFrame(offset, {"outputType": "file", "filePath": OFF, "maxDimension": 0})
    finally:
        for i, enabled in before.items():
            tl.SetTrackEnable("video", i, enabled)
    after = {i: bool(tl.GetIsTrackEnabled("video", i)) for i in tracks}
    result = {"on": on, "off": off, "before": before, "after": after,
              "restored": all(after[i] == before[i] for i in tracks)}
```

Check `on["success"]`, `off["success"]` and `restored`. `ExportFrame` returns `{"success", "width", "height"}`; the TIF is RGB without alpha, which is why the bounds come from the difference of two renders and not from a transparent background. If the element's track was already disabled in `before`, the element doesn't render at all: report that instead of measuring.

`restored` false: tell the user at once which tracks differ (`before` vs `after`), set them back with `SetTrackEnable` and re-read. That is the only track change the skill may make outside this script.

Then, on the shell side:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/critic.py bbox "<sandbox work>/critic/<item_id>-on.tif" "<sandbox work>/critic/<item_id>-off.tif"
```

It prints `{"bbox": [x0, y0, x1, y1] | null, "width", "height", "kinds": [[kind, severity], ...]}` in pixels of the render: `offscreen` (touches the frame edge, error), `unsafe` (outside the 5 % action-safe margin, error), `unsafe-title` (outside the 10 % title-safe margin, warn). `null` means nothing changed between the renders: the element is invisible at that frame.

## Paths

Resolve writes the TIFs with the Mac absolute path; `critic.py` reads them with the path the shell sees. On a Mac session they are the same. In Cowork they differ: resolve the mapping once as `resolve-core` §8 says and keep `work_dir` inside the selected folder.

## Cream markers

Timeline markers take a frame relative to the timeline start; findings store absolute frames.

```python
TIMELINE_ID = "<timeline_id>"
FINDINGS = [{"frame": 0, "kind": "offscreen", "message": "..."}]   # open findings that have a frame

project = resolve.GetProjectManager().GetCurrentProject()
tl = project.GetCurrentTimeline()
placed = []
if tl.GetUniqueId() == TIMELINE_ID:
    start = tl.GetStartFrame()
    for f in FINDINGS:
        rel = f["frame"] - start
        while rel in tl.GetMarkers():
            rel += 1
        ok = tl.AddMarker(rel, "Cream", f["kind"], f["message"], 1, f"claude:critic:{f['kind']}")
        placed.append({"frame": rel, "kind": f["kind"], "ok": ok, "read_back": tl.GetMarkers().get(rel, {}).get("customData")})
result = {"placed": placed}
```

A frame already holding any marker (the user's or Claude's) moves the new one a frame later, so the user's markers are never touched.
