"""Plan screen-recording and PiP camera segments that follow an already cut A-roll.

python3 pip_plan.py plan.json      (input described below; prints the plan as JSON)
python3 pip_plan.py selftest

Input:
{
 "timeline": {"fps": 25, "width": 3840, "height": 2160},
 "aroll": [{"record_start": 86400, "duration": 250, "clip_id": "cam1", "source_start": 1000}],  # timeline items, frames
 "clips": {"cam1": {"fps": 25}, "scr1": {"fps": 60, "frames": 90000}},
 "pairs": [{"camera": "cam1", "screen": "scr1", "offset_s": 12.5}],       # screen time = camera time + offset_s
 "sections": [{"start": 86400, "mode": "camera"}, {"start": 86500, "mode": "pip"}],  # each lasts until the next
 "layout": "corner-br", "pip_size": 0.28, "margin": 0.03
}
Frame ranges in the output are [start, end) in each clip's own frames; convert `end` for AppendToTimeline
with the calibration from resolve-core.
"""
import json
import sys

MODES = ("camera", "screen", "pip")
CORNERS = {"corner-br": (1, 1), "corner-bl": (-1, 1), "corner-tr": (1, -1), "corner-tl": (-1, -1)}


def pip_properties(width, height, layout, size, margin):
    """Camera scaled to `size` of the frame and pushed into a corner. Pan/Tilt are pixels from center, Tilt up."""
    sx, sy = CORNERS[layout]
    pan = sx * (width * (1 - size) / 2 - width * margin)
    tilt = -sy * (height * (1 - size) / 2 - width * margin)
    return {"ZoomX": round(size, 4), "ZoomY": round(size, 4), "Pan": round(pan, 1), "Tilt": round(tilt, 1)}


def mode_spans(sections, start, end):
    """Split [start, end) by section boundaries -> [(s, e, mode)]."""
    ordered = sorted(sections, key=lambda s: s["start"])
    spans = []
    for i, sec in enumerate(ordered):
        s = max(start, sec["start"])
        e = min(end, ordered[i + 1]["start"] if i + 1 < len(ordered) else end)
        if s < e:
            spans.append((s, e, sec["mode"]))
    if not ordered or ordered[0]["start"] > start:
        spans.insert(0, (start, min(end, ordered[0]["start"]) if ordered else end, "camera"))
    return spans


def plan(data):
    tl = data["timeline"]
    fps = tl["fps"]
    clips = data["clips"]
    pairs = {p["camera"]: p for p in data["pairs"]}
    bad = [s["mode"] for s in data["sections"] if s["mode"] not in MODES]
    if bad:
        raise SystemExit(f"unknown section modes {bad}; use {MODES}")
    out = {"screen": [], "pip": [], "warnings": []}
    for item in data["aroll"]:
        cam = clips[item["clip_id"]]
        if abs(cam["fps"] - fps) > 0.01:
            out["warnings"].append(f'{item["clip_id"]}: camera {cam["fps"]} fps != timeline {fps} fps; source math assumes 1:1')
        for s, e, mode in mode_spans(data["sections"], item["record_start"], item["record_start"] + item["duration"]):
            if mode == "camera":
                continue
            cam_start = item["source_start"] + (s - item["record_start"])
            pair = pairs.get(item["clip_id"])
            if not pair:
                out["warnings"].append(f'{item["clip_id"]} @ {s}: no synced screen recording; left as camera')
                continue
            scr = clips[pair["screen"]]
            scr_start = round((cam_start / cam["fps"] + pair["offset_s"]) * scr["fps"])
            scr_end = scr_start + round((e - s) / fps * scr["fps"])
            lo, hi = max(0, scr_start), min(scr.get("frames", scr_end), scr_end)
            if hi <= lo:
                out["warnings"].append(f"{pair['screen']}: no screen recording for record {s}-{e}; left as camera")
                continue
            if (lo, hi) != (scr_start, scr_end):
                out["warnings"].append(f"{pair['screen']}: screen recording covers only part of record {s}-{e}")
            rec = s + round((lo - scr_start) / scr["fps"] * fps)
            out["screen"].append({"clip_id": pair["screen"], "start": lo, "end": hi, "record": rec, "mode": mode})
            if mode == "pip":
                out["pip"].append({"clip_id": item["clip_id"], "start": cam_start, "end": cam_start + (e - s), "record": s})
    out["pip_properties"] = pip_properties(tl["width"], tl["height"], data.get("layout", "corner-br"),
                                           data.get("pip_size", 0.28), data.get("margin", 0.03))
    return out


def selftest():
    data = {
        "timeline": {"fps": 25, "width": 3840, "height": 2160},
        "aroll": [{"record_start": 1000, "duration": 100, "clip_id": "cam1", "source_start": 500},
                  {"record_start": 1100, "duration": 100, "clip_id": "cam1", "source_start": 900}],
        "clips": {"cam1": {"fps": 25}, "scr1": {"fps": 60, "frames": 3000}},
        "pairs": [{"camera": "cam1", "screen": "scr1", "offset_s": -10}],
        "sections": [{"start": 1050, "mode": "screen"}, {"start": 1150, "mode": "pip"}],
    }
    p = plan(data)
    # cam frame 550 = 22 s -> screen 12 s = frame 720; 50 timeline frames = 2 s = 120 screen frames
    assert p["screen"][0] == {"clip_id": "scr1", "start": 720, "end": 840, "record": 1050, "mode": "screen"}, p
    assert p["screen"][1]["start"] == round((900 / 25 - 10) * 60) and p["screen"][1]["mode"] == "screen", p
    # cam frame 950 = 38 s -> screen 28 s = frame 1680
    assert p["screen"][2] == {"clip_id": "scr1", "start": 1680, "end": 1800, "record": 1150, "mode": "pip"}, p
    assert p["pip"] == [{"clip_id": "cam1", "start": 950, "end": 1000, "record": 1150}], p
    assert not p["warnings"], p

    short = dict(data, clips={"cam1": {"fps": 25}, "scr1": {"fps": 60, "frames": 1750}})
    q = plan(short)
    assert q["screen"][2]["end"] == 1750 and any("only part" in w for w in q["warnings"]), q

    props = pip_properties(3840, 2160, "corner-br", 0.25, 0.03)
    right_edge = 3840 / 2 + props["Pan"] + 3840 * 0.25 / 2
    bottom_edge = 2160 / 2 - props["Tilt"] + 2160 * 0.25 / 2
    assert abs(right_edge - 3840 * 0.97) < 0.5 and abs(bottom_edge - (2160 - 3840 * 0.03)) < 0.5, props
    assert pip_properties(3840, 2160, "corner-tl", 0.25, 0.03)["Pan"] == -props["Pan"]
    print("pip_plan selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        selftest()
    else:
        with open(sys.argv[1], encoding="utf-8") as f:
            print(json.dumps(plan(json.load(f)), indent=1))
