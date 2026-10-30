"""Timing, easing and Fusion build specs for on-screen graphics (lower thirds, callouts, kinetic phrases, counters).

python3 motion.py build --kind lower-third --text "Олексій" [--sub "автор каналу"] --fps 25 --width 3840 --height 2160 \
    [--at X Y] [--count FROM TO] [--hold-s S] [--comp-start 0] [--font Montserrat --style Bold] \
    [--text-color #FFFFFF --accent #FFD400 --plate #000000 --plate-opacity 0.7] --out spec.json
python3 motion.py selftest

The spec is applied by the builder in resolve-core/reference.md#fusion-builds-from-a-spec. Positions are Fusion
coordinates (0..1, y up); `--at` takes screen coordinates (0..1 from the top-left), as read off an exported still.
Keyframes are sampled every frame from the easing curve, so the motion doesn't depend on Fusion's spline defaults.
"""
import argparse
import json
import os
import sys

KINDS = ("lower-third", "callout", "kinetic", "counter")
MIN_HOLD_S = {"lower-third": 3.0, "callout": 2.0, "kinetic": 1.2, "counter": 1.0}
CPS = 14          # comfortable reading speed for Ukrainian on screen, characters per second
MAX_HOLD_S = 7.0
SAFE = 0.06       # margin from the frame edge inside the 90 % action-safe area


def hex_rgb(value):
    h = value.lstrip("#")
    if len(h) != 6:
        raise SystemExit(f"color {value!r}: use #RRGGBB")
    return tuple(round(int(h[i:i + 2], 16) / 255, 4) for i in (0, 2, 4))


def ease(t, kind):
    t = min(1.0, max(0.0, t))
    if kind == "out":
        return 1 - (1 - t) ** 3
    if kind == "in":
        return t ** 3
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ramp(f0, f1, v0, v1, kind):
    """{frame: value} for every frame f0..f1 inclusive; v may be a number or an (x, y) pair."""
    n = max(1, f1 - f0)
    out = {}
    for f in range(f0, f1 + 1):
        e = ease((f - f0) / n, kind)
        out[f] = (round(v0 + (v1 - v0) * e, 5) if not isinstance(v0, tuple)
                  else {1: round(v0[0] + (v1[0] - v0[0]) * e, 5), 2: round(v0[1] + (v1[1] - v0[1]) * e, 5)})
    return out


def merge_keys(*parts):
    out = {}
    for p in parts:
        out.update(p)
    return {str(k): v for k, v in sorted(out.items())}


def timing(kind, text, fps, hold_s=None, count_s=0.0):
    intro, outro = round(0.4 * fps), round(0.3 * fps)
    chars = len(text.replace("\n", " "))
    hold = hold_s if hold_s else max(MIN_HOLD_S[kind] + count_s, min(MAX_HOLD_S, 0.5 + chars / CPS))
    hold_f = round(hold * fps)
    return {"in": intro, "hold": hold_f, "out": outro, "total": intro + hold_f + outro}


def est_width(text, size):
    """Rough text width as a share of frame width (bold sans, Cyrillic). Placement is re-checked on a still."""
    longest = max((len(line) for line in text.split("\n")), default=0)
    return longest * size * 0.62


def text_tool(name, text, font, style, size, color, center, justify):
    r, g, b = color
    return {"name": name, "id": "TextPlus", "inputs": {
        "StyledText": text, "Font": font, "Style": style, "Size": size, "Center": {1: center[0], 2: center[1]},
        "HorizontalJustificationNew": justify, "Red1": r, "Green1": g, "Blue1": b, "Alpha1": 1.0}}


def plate(tool, color, opacity, pad=0.25):
    """Text+ shading element 3 as an auto-sized box behind the text (no width guessing)."""
    r, g, b = color
    tool["inputs"].update({"Enabled3": 1, "Type3": 2, "Level3": 1, "Red3": r, "Green3": g, "Blue3": b,
                           "Alpha3": opacity, "ExtendHorizontal3": pad, "ExtendVertical3": pad * 0.6, "Round3": 0.15})
    return tool


def build(a):
    fps, kind = a.fps, a.kind
    text_c, accent, plate_c = hex_rgb(a.text_color), hex_rgb(a.accent), hex_rgb(a.plate)
    count_s = 1.0 if kind == "counter" else 0.0
    t = timing(kind, a.text if kind != "counter" else "", fps, a.hold_s, count_s)
    s0 = a.comp_start
    f_in, f_hold, f_out, f_end = s0, s0 + t["in"], s0 + t["in"] + t["hold"], s0 + t["total"]
    tools = [{"name": "CLEAR", "id": "Background", "inputs": {"Width": a.width, "Height": a.height, "TopLeftAlpha": 0.0}}]
    moves = []   # (name, source tool, home, slide offset, delay frames, start size)

    if kind == "lower-third":
        size = 0.055
        home = (min(0.5, SAFE + 0.02 + est_width(a.text, size) / 2), 0.2)
        tools.append(plate(text_tool("TXT", a.text, a.font, a.style, size, text_c, home, 1), plate_c, a.plate_opacity))
        moves.append(("MOVE", "TXT", home, (-0.03, 0), 0, 1.0))
        if a.sub:
            sub_home = (min(0.5, SAFE + 0.02 + est_width(a.sub, 0.034) / 2), home[1] - 0.06)
            tools.append(text_tool("SUB", a.sub, a.font, a.sub_style, 0.034, accent, sub_home, 1))
            moves.append(("MOVE2", "SUB", sub_home, (-0.03, 0), round(0.12 * fps), 1.0))
    elif kind == "callout":
        fx, fy = a.at[0], 1 - a.at[1]
        size = 0.04
        half = est_width(a.text, size) / 2
        # label above or below the point (never on it), shifted inward so it stays inside the safe area
        ly = fy - 0.08 if fy > 0.5 else fy + 0.08
        lx = min(1 - SAFE - half, max(SAFE + half, fx))
        spot = (round(lx, 4), round(ly, 4))
        tools.append(plate(text_tool("TXT", a.text, a.font, a.style, size, text_c, spot, 1), plate_c, a.plate_opacity))
        tools.append(text_tool("DOT", "●", a.font, "Regular", 0.03, accent, (fx, fy), 1))
        moves.append(("MOVE_DOT", "DOT", (fx, fy), (0, 0), 0, 0.6))
        moves.append(("MOVE", "TXT", spot, (0, 0.015 if ly < fy else -0.015), round(0.08 * fps), 0.9))
    elif kind == "kinetic":
        spot = (0.5, 0.3)
        tools.append(text_tool("TXT", a.text, a.font, a.style, 0.085, text_c, spot, 1))
        moves.append(("MOVE", "TXT", spot, (0, -0.02), 0, 0.92))
    else:
        lo, hi = a.count
        spot = (0.5, 0.3)
        txt = text_tool("TXT", str(lo), a.font, a.style, 0.11, accent, spot, 1)
        dur = round(count_s * fps)
        # Fusion expression (Lua): ease-out count from lo to hi over `dur` frames after the intro
        txt["expressions"] = {"StyledText": (
            f"Text(string.format('%d', math.floor({lo} + ({hi} - {lo}) * "
            f"(1 - (1 - math.min(math.max((time - {f_hold}) / {dur}, 0), 1)) ^ 3) + 0.5)))")}
        tools.append(txt)
        moves.append(("MOVE", "TXT", spot, (0, 0), 0, 0.85))

    layer = "CLEAR"
    for mv, src, home, offset, d, size_in in moves:
        # Pivot on the element itself, so scaling doesn't drag it across the frame
        tools.append({"name": mv, "id": "Transform", "connect": {"Input": f"{src}.Output"},
                      "inputs": {"Pivot": {1: home[0], 2: home[1]}}, "keys": {
            "Center": merge_keys(ramp(f_in + d, f_hold + d, (0.5 + offset[0], 0.5 + offset[1]), (0.5, 0.5), "out"),
                                 ramp(f_out, f_end, (0.5, 0.5), (0.5, 0.5), "in")),
            "Size": merge_keys(ramp(f_in + d, f_hold + d, size_in, 1.0, "out"), ramp(f_out, f_end, 1.0, 1.0, "in"))}})
        merge = f"MIX_{mv}"
        tools.append({"name": merge, "id": "Merge", "connect": {"Background": f"{layer}.Output", "Foreground": f"{mv}.Output"},
                      "keys": {"Blend": merge_keys(ramp(f_in + d, f_hold + d, 0.0, 1.0, "out"),
                                                   ramp(f_out, f_end, 1.0, 0.0, "in"))}})
        layer = merge
    tools.append({"name": "MediaOut1", "id": "MediaOut", "connect": {"Input": f"{layer}.Output"}})
    return {"kind": kind, "fps": fps, "timing_frames": t, "comp_start": s0, "visible": [f_in, f_end], "tools": tools}


def parser():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--kind", choices=KINDS, required=True)
    b.add_argument("--text", default="")
    b.add_argument("--sub", default="")
    b.add_argument("--fps", type=float, required=True)
    b.add_argument("--width", type=int, required=True)
    b.add_argument("--height", type=int, required=True)
    b.add_argument("--at", type=float, nargs=2, default=(0.5, 0.5))
    b.add_argument("--count", type=int, nargs=2, default=(0, 100))
    b.add_argument("--hold-s", type=float)
    b.add_argument("--comp-start", type=int, default=0)
    b.add_argument("--font", default="Montserrat")
    b.add_argument("--style", default="Bold")
    b.add_argument("--sub-style", default="Regular")
    b.add_argument("--text-color", default="#FFFFFF")
    b.add_argument("--accent", default="#FFD400")
    b.add_argument("--plate", default="#000000")
    b.add_argument("--plate-opacity", type=float, default=0.7)
    b.add_argument("--out", required=True)
    return ap


def selftest():
    assert hex_rgb("#FFD400") == (1.0, 0.8314, 0.0)
    assert ease(0, "out") == 0 and ease(1, "out") == 1 and ease(0.5, "out") > 0.8 and ease(0.5, "in") < 0.2
    r = ramp(10, 20, 0.0, 1.0, "out")
    assert len(r) == 11 and r[10] == 0.0 and r[20] == 1.0 and all(r[f] <= r[f + 1] for f in range(10, 20))
    t = timing("lower-third", "Олексій", 25)
    assert t == {"in": 10, "hold": 75, "out": 8, "total": 93}, t
    long = timing("kinetic", "х" * 200, 25)
    assert long["hold"] == round(MAX_HOLD_S * 25), long

    a = parser().parse_args(["build", "--kind", "lower-third", "--text", "Олексій", "--sub", "автор", "--fps", "25",
                             "--width", "3840", "--height", "2160", "--comp-start", "100", "--out", "-"])
    spec = build(a)
    names = [x["name"] for x in spec["tools"]]
    assert names == ["CLEAR", "TXT", "SUB", "MOVE", "MIX_MOVE", "MOVE2", "MIX_MOVE2", "MediaOut1"], names
    txt = spec["tools"][1]["inputs"]
    assert txt["Center"][1] - est_width("Олексій", 0.055) / 2 >= SAFE, txt["Center"]   # left edge inside the safe area
    mix = spec["tools"][4]["keys"]["Blend"]
    assert mix["100"] == 0.0 and mix["110"] == 1.0 and mix[str(100 + 93)] == 0.0, mix
    assert spec["tools"][6]["keys"]["Blend"]["103"] == 0.0, "sub line starts 3 frames later"
    assert spec["tools"][-1]["connect"] == {"Input": "MIX_MOVE2.Output"}
    assert spec["tools"][1]["inputs"]["Alpha3"] == 0.7

    c = build(parser().parse_args(["build", "--kind", "callout", "--text", "Save", "--at", "0.9", "0.05", "--fps", "25",
                                   "--width", "1920", "--height", "1080", "--out", "-"]))
    spot = c["tools"][1]["inputs"]["Center"]
    half = est_width("Save", 0.04) / 2
    assert spot[1] + half <= 1 - SAFE + 1e-9 and spot[2] < 0.95 - 0.05, spot   # inside safe area, below the point
    names = [x["name"] for x in c["tools"]]
    out_chain, node = [], "MediaOut1"
    by_name = {x["name"]: x for x in c["tools"]}
    while node in by_name:
        conn = by_name[node].get("connect", {})
        out_chain.append(node)
        node = (conn.get("Foreground") or conn.get("Input") or "").split(".")[0]
    reachable = set()
    for x in c["tools"]:
        for src in x.get("connect", {}).values():
            reachable.add(src.split(".")[0])
    assert {"DOT", "TXT"} <= reachable, "dot and label both feed the output"
    mv = by_name["MOVE"]
    assert mv["inputs"]["Pivot"] == {1: spot[1], 2: spot[2]}, "label scales around itself"

    n = build(parser().parse_args(["build", "--kind", "counter", "--count", "0", "1200", "--fps", "25",
                                   "--width", "1920", "--height", "1080", "--out", "-"]))
    assert "1200" in n["tools"][1]["expressions"]["StyledText"] and n["timing_frames"]["hold"] == 50
    print("motion selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    a = parser().parse_args()
    if a.kind in ("lower-third", "callout", "kinetic") and not a.text.strip():
        raise SystemExit(f"--text is required for {a.kind}")
    spec = build(a)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    print(json.dumps({"out": a.out, "timing_frames": spec["timing_frames"], "visible": spec["visible"]}, indent=1))


if __name__ == "__main__":
    main()
