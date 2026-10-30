"""Eased zooms into regions of a screen recording (Fusion Transform spec) and static punch-ins for jump cuts.

python3 zooms.py plan zooms.json --out spec.json
python3 zooms.py punch --width 3840 --height 2160 --scale 1.12 --face X Y
python3 zooms.py selftest

zooms.json:
{"fps": 25, "item_start": 90000, "comp_start": 0,                 # timeline frame of the item's first frame -> comp frame
 "default_scale": 1.6, "max_scale": 2.5, "ease_s": 0.5, "merge_gap_s": 1.0,
 "zooms": [{"start": 90100, "end": 90200, "region": [x, y, w, h], "scale": null, "id": "pink@01:00:04:00"}]}
Regions are 0..1 from the top-left of the frame, read off an exported still. Frames are timeline frames, [start, end).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "fusion-motion-graphics", "scripts"))
from motion import ease

MIN_SCALE = 1.15
FIT_MARGIN = 1.2      # region fills ~83 % of the frame, so its edges aren't glued to the frame edges


def zoom_scale(region, default, maximum, override=None):
    if override:
        return min(maximum, max(MIN_SCALE, override))
    _, _, w, h = region
    if w <= 0 or h <= 0:
        return min(maximum, default)
    return round(min(maximum, max(MIN_SCALE, 1 / (FIT_MARGIN * max(w, h)))), 3)


def clamp_focus(q, s):
    """Image point shown at the frame center; keeps the scaled image covering the whole frame (no black edges)."""
    lo, hi = 0.5 / s, 1 - 0.5 / s
    return min(hi, max(lo, q))


def center_for(s, qx, qy_top):
    """Fusion Transform Center (y up, pivot 0.5) that puts image point (qx, qy) at the frame center at scale s."""
    fx, fy = clamp_focus(qx, s), clamp_focus(1 - qy_top, s)
    return round(0.5 - s * (fx - 0.5), 5), round(0.5 - s * (fy - 0.5), 5)


def plan(data):
    fps = data["fps"]
    ease_f = round(data.get("ease_s", 0.5) * fps)
    gap_f = round(data.get("merge_gap_s", 1.0) * fps)
    to_comp = lambda f: f - data["item_start"] + data.get("comp_start", 0)
    rest = (1.0, 0.5, 0.5)
    keys_size, keys_center, rows, warnings = {}, {}, [], []

    def move(f0, f1, a, b):
        n = max(1, f1 - f0)
        for f in range(f0, f1 + 1):
            e = ease((f - f0) / n, "inout")
            s = a[0] + (b[0] - a[0]) * e
            qx, qy = a[1] + (b[1] - a[1]) * e, a[2] + (b[2] - a[2]) * e
            cx, cy = center_for(s, qx, qy)
            keys_size[str(to_comp(f))] = round(s, 5)
            keys_center[str(to_comp(f))] = {1: cx, 2: cy}

    zooms = sorted(data["zooms"], key=lambda z: z["start"])
    state, prev_end = rest, None
    for i, z in enumerate(zooms):
        length = z["end"] - z["start"]
        e = min(ease_f, max(round(0.25 * fps), (length - round(0.5 * fps)) // 2))
        if length < fps:
            warnings.append(f'{z.get("id", i)}: {length} frames is shorter than 1 s; the zoom will feel like a jolt')
        if prev_end is not None and z["start"] < prev_end:
            warnings.append(f'{z.get("id", i)}: overlaps the previous zoom; start moved to {prev_end}')
            z = dict(z, start=prev_end)
        x, y, w, h = z["region"]
        s = zoom_scale(z["region"], data.get("default_scale", 1.6), data.get("max_scale", 2.5), z.get("scale"))
        target = (s, x + w / 2, y + h / 2)
        chained = prev_end is not None and z["start"] - prev_end <= gap_f
        move(z["start"], z["start"] + e, state, target)
        nxt = zooms[i + 1] if i + 1 < len(zooms) else None
        if nxt and nxt["start"] - z["end"] <= gap_f:
            state, prev_end = target, z["end"]
        else:
            move(z["end"] - e, z["end"], target, rest)
            state, prev_end = rest, z["end"]
        rows.append({"id": z.get("id", i), "start": z["start"], "end": z["end"], "scale": s,
                     "focus": [round(target[1], 3), round(target[2], 3)], "pan_from_previous": chained})
    tools = [{"name": "ZOOM", "id": "Transform", "connect": {"Input": "MediaIn1.Output"},
              "inputs": {"Pivot": {1: 0.5, 2: 0.5}}, "keys": {"Size": keys_size, "Center": keys_center}},
             {"name": "MediaOut1", "id": "MediaOut", "connect": {"Input": "ZOOM.Output"}}]
    return {"zooms": rows, "warnings": warnings, "tools": tools}


def punch(width, height, scale, face_x, face_y):
    """Inspector Zoom/Pan/Tilt that enlarge the shot but keep the face where it was. Pan/Tilt in pixels, Tilt up."""
    pan = (1 - scale) * (face_x - 0.5) * width
    tilt = (scale - 1) * (face_y - 0.5) * height
    return {"ZoomX": scale, "ZoomY": scale, "Pan": round(pan, 1), "Tilt": round(tilt, 1)}


def selftest():
    assert zoom_scale([0.4, 0.4, 0.5, 0.2], 1.6, 2.5) == round(1 / (1.2 * 0.5), 3)
    assert zoom_scale([0, 0, 0.05, 0.05], 1.6, 2.5) == 2.5 and zoom_scale([0, 0, 0.9, 0.9], 1.6, 2.5) == MIN_SCALE
    # corner region at 2x: focus clamps to 0.25/0.75, so the frame edge never shows black
    assert center_for(2.0, 0.95, 0.05) == (0.0, 0.0), center_for(2.0, 0.95, 0.05)
    assert center_for(1.0, 0.5, 0.5) == (0.5, 0.5)

    data = {"fps": 25, "item_start": 1000, "comp_start": 0, "ease_s": 0.5, "merge_gap_s": 1.0,
            "zooms": [{"start": 1050, "end": 1150, "region": [0.6, 0.1, 0.3, 0.2], "id": "a"},
                      {"start": 1160, "end": 1260, "region": [0.1, 0.6, 0.3, 0.2], "id": "b"},
                      {"start": 1500, "end": 1515, "region": [0.4, 0.4, 0.2, 0.2], "id": "c"}]}
    p = plan(data)
    size = p["tools"][0]["keys"]["Size"]
    assert size["50"] == 1.0 and abs(size["62"] - p["zooms"][0]["scale"]) < 1e-9, size
    assert "140" not in size, "a is chained into b: no zoom-out between them"
    assert p["zooms"][1]["pan_from_previous"] and size["260"] == 1.0 and size["160"] == p["zooms"][0]["scale"]
    assert any("shorter than 1 s" in w for w in p["warnings"]), p["warnings"]
    assert all(v >= 1.0 for v in size.values())
    for f, c in p["tools"][0]["keys"]["Center"].items():
        s = size[f]
        for axis in (1, 2):   # the scaled image always covers [0, 1]
            assert c[axis] - s / 2 <= 1e-6 and c[axis] + s / 2 >= 1 - 1e-6, (f, s, c)

    pr = punch(3840, 2160, 1.12, 0.5, 0.4)
    assert pr["Pan"] == 0.0 and pr["Tilt"] == round(0.12 * -0.1 * 2160, 1), pr
    print("zooms selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("input")
    pl.add_argument("--out", required=True)
    pu = sub.add_parser("punch")
    pu.add_argument("--width", type=int, required=True)
    pu.add_argument("--height", type=int, required=True)
    pu.add_argument("--scale", type=float, default=1.12)
    pu.add_argument("--face", type=float, nargs=2, default=(0.5, 0.4))
    a = ap.parse_args()
    if a.cmd == "punch":
        return print(json.dumps(punch(a.width, a.height, a.scale, *a.face)))
    with open(a.input, encoding="utf-8") as f:
        result = plan(json.load(f))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(json.dumps({"out": a.out, "zooms": result["zooms"], "warnings": result["warnings"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
