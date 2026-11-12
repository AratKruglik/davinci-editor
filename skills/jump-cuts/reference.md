# jump-cuts reference

Scripts for `run_script` (sandboxed: no files, no `os`). Resolve objects don't survive between calls, so each script fetches the timeline again and finds items by `GetUniqueId()`. Upper-case names are values you fill in. Every script that changes or exports something first checks that the timeline it is about to touch is the current one.

Track indices come from the dump by track name (`A-roll`, `Voice`), never from a guess.

## Transforms

Items whose Inspector transform the user (or PiP) already set keep their scale.

```python
A_ROLL = 0   # video track index
DEFAULTS = {"ZoomX": 1.0, "ZoomY": 1.0, "Pan": 0.0, "Tilt": 0.0, "RotationAngle": 0.0,
            "CropLeft": 0.0, "CropRight": 0.0, "CropTop": 0.0, "CropBottom": 0.0, "FlipX": False, "FlipY": False}

tl = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
changed = {}
for it in tl.GetItemListInTrack("video", A_ROLL) or []:
    props = it.GetProperties() or {}
    diff = {k: props[k] for k, v in DEFAULTS.items() if k in props and props[k] != v}
    if diff:
        changed[it.GetUniqueId()] = diff
result = {"timeline_id": tl.GetUniqueId(), "changed": changed}
```

The ids in `changed` go to `jump_cuts.py joins --fixed-transform`. A key missing from `GetProperties()` on this build is not a difference.

## Export frames

`ExportFrame` takes an offset from the timeline start and writes with the Mac path; the shell reads the same files with its own path (`resolve-core` §8). 21.1.2+. The stills are only measured, never looked at, so 1280 px is enough (`jump_cuts.py diff` samples 480 columns) and keeps them small.

```python
TIMELINE_ID = "<timeline_id from the dump>"
OUT = "<mac work>/jump"
JOINS = [{"id": "j1", "frame": 0}]   # absolute frame of the join, up to 40 per call

tl = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
if tl.GetUniqueId() != TIMELINE_ID:
    result = {"error": "the judged timeline is not current", "current": tl.GetName()}
else:
    start, done = tl.GetStartFrame(), {}
    for j in JOINS:
        a = tl.ExportFrame(j["frame"] - 1 - start, {"outputType": "file", "filePath": f"{OUT}/{j['id']}-a.tif", "maxDimension": 1280})
        b = tl.ExportFrame(j["frame"] - start, {"outputType": "file", "filePath": f"{OUT}/{j['id']}-b.tif", "maxDimension": 1280})
        done[j["id"]] = bool(a and a.get("success") and b and b.get("success"))
    result = {"exported": done}
```

A join with `False`: look at it with `get_image` instead and pass no `--diff` for it. The stills show the full composite, which is right: a title over the join is on both frames and cancels out.

## Duplicate

```python
SOURCE_ID = "<timeline_id from the dump>"
NAME = "<source name> - jump <YYYY-MM-DD>"

pm = resolve.GetProjectManager()
project = pm.GetCurrentProject()
pm.SaveProject()
tl = project.GetCurrentTimeline()
names = {project.GetTimelineByIndex(i).GetName() for i in range(1, project.GetTimelineCount() + 1)}
if tl.GetUniqueId() != SOURCE_ID:
    result = {"error": "the source timeline is not current", "current": tl.GetName()}
elif NAME in names:
    result = {"error": "name taken", "name": NAME}
else:
    copy = tl.DuplicateTimeline(NAME)
    project.SetCurrentTimeline(copy)
    now = project.GetCurrentTimeline()
    result = {"copy": now.GetName(), "copy_id": now.GetUniqueId(), "is_copy": now.GetUniqueId() != SOURCE_ID}
```

A taken name gets ` v2`, ` v3`. The copy has new item ids: dump it and run `jump_cuts.py joins` on that dump into a scratch file to map the old join ids onto the copy's items by `frame` (the frames are the same). Don't overwrite `joins.json`: it holds the decisions.

## State before the changes

With `run_script_unsafe` (it writes a file), on the copy before the first change:

```python
import json
COPY_ID = "<copy_id>"
PATH = "<mac work>/jump-before.json"
A_ROLL, VOICE = 0, 0

tl = project.GetCurrentTimeline()
assert tl.GetUniqueId() == COPY_ID
def rows(kind, index, with_props):
    return [{"item_id": it.GetUniqueId(), "start": it.GetStart(), "end": it.GetEnd(),
             "left_offset": it.GetLeftOffset(), "right_offset": it.GetRightOffset(),
             "properties": it.GetProperties() if with_props else None}
            for it in tl.GetItemListInTrack(kind, index) or []]
with open(PATH, "w", encoding="utf-8") as f:
    json.dump({"timeline_id": COPY_ID, "video": rows("video", A_ROLL, True), "audio": rows("audio", VOICE, False)}, f, indent=1, default=str)
result = {"path": PATH}
```

## Roll

One join per call. `k` > 0 moves the cut later, `k` < 0 earlier. The edge that retreats goes first, so the edge that grows lands in the gap and overwrites nothing (`resolve-core/reference.md`, edge trims: `updateLinkedItems` always False). Both tracks are found and checked before the first change, and a `False` stops the script before the growing edge moves.

```python
COPY_ID = "<copy_id>"
A_ROLL, VOICE = 0, 0
FRAME = 0          # the join's absolute frame before the roll
K = 0

tl = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
TRACKS = (("video", A_ROLL), ("audio", VOICE))

def edges():
    return {kind: [(i.GetUniqueId(), i.GetStart(), i.GetEnd()) for i in tl.GetItemListInTrack(kind, index) or []]
            for kind, index in TRACKS}

def pair(kind, index):
    items = tl.GetItemListInTrack(kind, index) or []
    return (next((i for i in items if i.GetEnd() == FRAME), None), next((i for i in items if i.GetStart() == FRAME), None))

def roll(left, right):
    lo, ro = right.GetLeftOffset(), left.GetRightOffset()
    retreat, grow = ((right.SetLeftOffset, lo + K), (left.SetRightOffset, ro - K))
    if K < 0:
        retreat, grow = grow, retreat
    first = retreat[0](retreat[1], False, False)
    second = grow[0](grow[1], False, False) if first else None
    return {"ok": [first, second], "landed": left.GetEnd() == FRAME + K == right.GetStart()}

if tl.GetUniqueId() != COPY_ID:
    result = {"error": "the copy is not current", "current": tl.GetName()}
else:
    pairs = {kind: pair(kind, index) for kind, index in TRACKS}
    problems = {kind: "no two items meet at the join" if None in p
                else "not enough media beyond the edge" if p[0].GetRightOffset() < K or p[1].GetLeftOffset() < -K else None
                for kind, p in pairs.items()}
    if any(problems.values()):
        result = {"error": problems, "changed": False}
    else:
        before, out = edges(), {}
        for kind, _ in TRACKS:
            out[kind] = roll(*pairs[kind])
            if not all(out[kind]["ok"]):
                break
        after = edges()
        moved = {kind: [{"item_id": a[0], "from": b[1:], "to": a[1:]} for b, a in zip(before[kind], after[kind]) if b != a]
                 for kind in after}
        result = {"rolled": out, "moved": moved, "same_count": all(len(before[k]) == len(after[k]) for k in after)}
```

Good result: every `ok` true, `landed` true for both kinds, `same_count` true, and `moved` lists exactly two items per kind (the left one's end and the right one's start, each by `K`). Anything else: stop. An `error` changed nothing. A video roll followed by a failed audio roll leaves the picture rolled without its sound: roll the video back with `K` negated (video track only) and report the join. Voice items split from their picture (a `claude:split` join) never meet at `FRAME`; the script reports that before touching anything, and such joins are not rolled anyway. A second voice track (`Voice 2`) cut at the same joins is not handled: say so and leave `roll` joins to `punch`.

## Smooth Cut

```python
COPY_ID = "<copy_id>"
A_ROLL = 0
FRAME = 0
DURATION = 6

tl = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
if tl.GetUniqueId() != COPY_ID:
    result = {"error": "the copy is not current", "current": tl.GetName()}
else:
    items = tl.GetItemListInTrack("video", A_ROLL) or []
    left = next((i for i in items if i.GetEnd() == FRAME), None)
    tr = left.AddTransition({"type": "Smooth Cut", "category": "simple", "position": "end",
                             "alignment": "center", "duration": DURATION}) if left else None
    result = {"added": tr is not None,
              "type": tr.GetType() if tr else None, "name": tr.GetName() if tr else None,
              "duration": tr.GetDuration() if tr else None,
              "left_end": left.GetEnd() if left else None}
```

Unverified on 21.2: the type name `Smooth Cut` and its category. `added` false → try once with the names `search_scripting_api("transition")` and `resolve.GetEffectsList("video")` show for it; still nothing → the fallback in SKILL.md §4. `added` true: `left_end` must still be `FRAME` (a transition must not move the cut), then look at `FRAME` with `get_image`. The transition may be listed by `GetItemListInTrack` as one more item (type `transition`, no media pool item): the verification in SKILL.md §5 leaves such rows out of the count. Removing a transition is a delete: the guard asks, and it happens only when the user says so.

## Punch

```python
COPY_ID = "<copy_id>"
A_ROLL = 0
PUNCH = {"<item id on the copy>": {"ZoomX": 1.12, "ZoomY": 1.12, "Pan": 0.0, "Tilt": 0.0}}   # from zooms.py punch

tl = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
if tl.GetUniqueId() != COPY_ID:
    result = {"error": "the copy is not current", "current": tl.GetName()}
else:
    out = {}
    for it in tl.GetItemListInTrack("video", A_ROLL) or []:
        props = PUNCH.get(it.GetUniqueId())
        if props:
            ok = it.SetProperties(props)
            back = it.GetProperties() or {}
            out[it.GetUniqueId()] = {"ok": ok, "read_back": {k: back.get(k) for k in props}}
    result = {"set": out, "missing": [i for i in PUNCH if i not in out]}
```

First call: one item only, then a still of its middle frame next to the same frame of the original timeline. The eyes sit at the same height and no edge of the frame shows black; if Pan / Tilt moved the picture the wrong way, the unit or sign differs on this build: fix it in the values, not in `zooms.py`, and say so in the report.

## Cover marker

```python
COPY_ID = "<copy_id>"
COVER = [{"frame": 0, "note": "jump cut: cover 2 s with B-roll or the screen"}]

tl = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
if tl.GetUniqueId() != COPY_ID:
    result = {"error": "the copy is not current", "current": tl.GetName()}
else:
    start, placed = tl.GetStartFrame(), []
    for c in COVER:
        rel = c["frame"] - start
        while rel in tl.GetMarkers():
            rel += 1
        ok = tl.AddMarker(rel, "Cream", "jump", c["note"], 1, "claude:jump:cover")
        placed.append({"frame": rel, "ok": ok, "read_back": tl.GetMarkers().get(rel, {}).get("customData")})
    result = {"placed": placed}
```

The join usually holds the Cream `cut` marker of `text-based-cut`, so the new one lands a frame later; no existing marker is touched.
