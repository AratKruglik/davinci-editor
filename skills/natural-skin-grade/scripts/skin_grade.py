"""Skin tone analysis on a Rec.709 still and CDL suggestions that keep skin natural. Pure Python.

python3 skin_grade.py analyze STILL.tif --skin X,Y,W,H [--skin ...] [--neutral X,Y,W,H] [--strength 0.6] [--max-sat 0.35]

The still is display-referred Rec.709 (after the CST, with PRIMARY/SKIN at identity). Boxes are in full-resolution pixels.
Hue is the vectorscope angle atan2(Cr, Cb) in degrees; the skin tone line sits at SKIN_LINE_DEG.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "chart-match", "scripts"))
from chart_match import read_tiff

SKIN_LINE_DEG = 123.0
DEADBAND_DEG = 3.0       # within this, skin is "on the line"; leave it alone
MAX_SHIFT_DEG = 8.0      # never rotate skin more than this in one pass
SLOPE_LIMITS = (0.85, 1.15)
KR, KB = 0.2126, 0.0722


def ycbcr(rgb):
    r, g, b = rgb
    y = KR * r + (1 - KR - KB) * g + KB * b
    return y, (b - y) / (2 * (1 - KB)), (r - y) / (2 * (1 - KR))


def rgb(y, cb, cr):
    r = y + 2 * (1 - KR) * cr
    b = y + 2 * (1 - KB) * cb
    return r, (y - KR * r - KB * b) / (1 - KR - KB), b


def describe(color):
    y, cb, cr = ycbcr(color)
    chroma = math.hypot(cb, cr)
    hue = math.degrees(math.atan2(cr, cb)) % 360
    return {"rgb": [round(c, 4) for c in color], "luma": round(y, 4), "hue_deg": round(hue, 2),
            "line_offset_deg": round(hue - SKIN_LINE_DEG, 2), "chroma": round(chroma, 4),
            "sat_ratio": round(chroma / y, 4) if y > 0 else None}


def box_mean(pixel, width, height, box):
    x, y, w, h = box
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise SystemExit(f"box {box} is outside the {width}x{height} still")
    step = max(1, int(math.sqrt(w * h / 4000)))
    total, n, clipped = [0.0, 0.0, 0.0], 0, 0
    for yy in range(y, y + h, step):
        for xx in range(x, x + w, step):
            p = pixel(xx, yy)
            if max(p) >= 0.98 or min(p) <= 0.02:
                clipped += 1
                continue
            total = [t + c for t, c in zip(total, p)]
            n += 1
    if not n:
        raise SystemExit(f"box {box}: every sample is clipped")
    return [t / n for t in total], clipped / (n + clipped)


def clamp_slope(s):
    return min(SLOPE_LIMITS[1], max(SLOPE_LIMITS[0], s))


def neutral_slope(neutral):
    y = ycbcr(neutral)[0]
    return [clamp_slope(y / c) for c in neutral]


def skin_correction(skin, strength, max_sat):
    """Slope that rotates the skin mean part-way to the skin line at constant luma, plus a saturation cap."""
    y, cb, cr = ycbcr(skin)
    chroma = math.hypot(cb, cr)
    hue = math.degrees(math.atan2(cr, cb))
    offset = hue - SKIN_LINE_DEG
    shift = 0.0 if abs(offset) <= DEADBAND_DEG else -max(-MAX_SHIFT_DEG, min(MAX_SHIFT_DEG, offset * strength))
    target = rgb(y, chroma * math.cos(math.radians(hue + shift)), chroma * math.sin(math.radians(hue + shift)))
    slope = [clamp_slope(t / c) for t, c in zip(target, skin)]
    sat = 1.0
    if max_sat and y > 0 and chroma / y > max_sat:
        sat = round(max(0.8, max_sat / (chroma / y)), 3)
    return slope, round(shift, 2), sat


def apply(color, slope, sat=1.0):
    out = [c * s for c, s in zip(color, slope)]
    y, cb, cr = ycbcr(out)
    return list(rgb(y, cb * sat, cr * sat))


def cdl(slope, sat=1.0):
    return {"Slope": " ".join(f"{s:.4f}" for s in slope), "Offset": "0 0 0", "Power": "1 1 1", "Saturation": sat}


def analyze(still, skin_boxes, neutral_box, strength, max_sat):
    width, height, pixel = read_tiff(still)
    samples = [box_mean(pixel, width, height, b) for b in skin_boxes]
    skin = [sum(s[0][i] for s in samples) / len(samples) for i in range(3)]
    out = {"size": [width, height], "skin_before": describe(skin), "skin_clipped": round(max(s[1] for s in samples), 3), "warnings": []}
    primary = [1.0, 1.0, 1.0]
    if neutral_box:
        neutral, clipped = box_mean(pixel, width, height, neutral_box)
        out["neutral_before"] = describe(neutral)
        if out["neutral_before"]["sat_ratio"] and out["neutral_before"]["sat_ratio"] > 0.25:
            out["warnings"].append("neutral box is strongly colored; is it really grey/white?")
        primary = neutral_slope(neutral)
        skin = apply(skin, primary)
        out["skin_after_primary"] = describe(skin)
    slope, shift, sat = skin_correction(skin, strength, max_sat)
    out["primary_cdl"] = cdl(primary)
    out["skin_cdl"] = cdl(slope, sat)
    out["skin_shift_deg"] = shift
    out["skin_predicted"] = describe(apply(skin, slope, sat))
    if out["skin_clipped"] > 0.2:
        out["warnings"].append("over 20% of skin samples clipped; move the box off highlights and shadows")
    luma = out["skin_before"]["luma"]
    if luma < 0.3 or luma > 0.85:
        out["warnings"].append(f"skin luma {luma:.2f} looks badly exposed; consider exposure on PRIMARY first (ask the user)")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["analyze"])
    p.add_argument("still")
    p.add_argument("--skin", action="append", required=True, help="X,Y,W,H of a skin area (cheek, forehead); repeatable")
    p.add_argument("--neutral", help="X,Y,W,H of something grey or white in the same light")
    p.add_argument("--strength", type=float, default=0.6, help="share of the hue offset to correct, 0..1")
    p.add_argument("--max-sat", type=float, default=0.35, help="chroma/luma ratio above which skin saturation is capped")
    a = p.parse_args()
    parse = lambda s: [int(v) for v in s.split(",")]
    print(json.dumps(analyze(a.still, [parse(b) for b in a.skin], a.neutral and parse(a.neutral), a.strength, a.max_sat), indent=1))


if __name__ == "__main__":
    main()
