"""Self-check: synthetic stills with a greenish cast, a magenta-ish skin, an on-line skin and an oversaturated skin."""
import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from skin_grade import SKIN_LINE_DEG, apply, describe, ycbcr, rgb

W, H = 64, 32


def write_tiff(path, left, right):
    """8-bit RGB TIFF: left half one color, right half another."""
    row = b"".join(bytes(round(c * 255) for c in (left if x < W // 2 else right)) for x in range(W))
    pixels = row * H
    entries = [(256, 3, 1, W), (257, 3, 1, H), (258, 3, 1, 8), (259, 3, 1, 1), (262, 3, 1, 2),
               (273, 4, 1, 8), (277, 3, 1, 3), (278, 3, 1, H), (279, 4, 1, len(pixels)), (284, 3, 1, 1)]
    ifd = struct.pack("<H", len(entries)) + b"".join(
        struct.pack("<HHI", t, typ, n) + (struct.pack("<HH", v, 0) if typ == 3 else struct.pack("<I", v)) for t, typ, n, v in entries)
    with open(path, "wb") as f:
        f.write(b"II" + struct.pack("<HI", 42, 8 + len(pixels)) + pixels + ifd + b"\0\0\0\0")


def skin_at(hue_deg, y=0.6, chroma=0.12):
    import math
    return rgb(y, chroma * math.cos(math.radians(hue_deg)), chroma * math.sin(math.radians(hue_deg)))


def run(left, right, *extra):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "s.tif")
        write_tiff(path, left, right)
        args = [sys.executable, os.path.join(HERE, "skin_grade.py"), "analyze", path, "--skin", "4,4,24,24", *extra]
        out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
        return json.loads(out)


def main():
    assert abs(describe(skin_at(SKIN_LINE_DEG))["line_offset_deg"]) < 0.5

    on_line = run(skin_at(SKIN_LINE_DEG + 1), (0.5, 0.5, 0.5))
    assert on_line["skin_shift_deg"] == 0 and on_line["skin_cdl"]["Slope"] == "1.0000 1.0000 1.0000", on_line

    magenta = run(skin_at(SKIN_LINE_DEG - 12), (0.5, 0.5, 0.5))
    pred = magenta["skin_predicted"]["line_offset_deg"]
    assert 0 < magenta["skin_shift_deg"] <= 8 and abs(pred) < 12 and pred < 0, magenta
    assert abs(magenta["skin_predicted"]["luma"] - magenta["skin_before"]["luma"]) < 0.02, magenta

    green_cast = (0.47, 0.55, 0.47)
    skin = apply(skin_at(SKIN_LINE_DEG), [1.0, 1.15, 1.0])
    cast = run(skin, green_cast, "--neutral", "36,4,24,24")
    slope = [float(s) for s in cast["primary_cdl"]["Slope"].split()]
    assert slope[1] < 1 < slope[0] and slope[1] < slope[2], cast
    assert abs(cast["skin_after_primary"]["line_offset_deg"]) < abs(cast["skin_before"]["line_offset_deg"]), cast

    hot = run(skin_at(SKIN_LINE_DEG, y=0.55, chroma=0.3), (0.5, 0.5, 0.5))
    assert hot["skin_cdl"]["Saturation"] < 1, hot
    print("skin_grade selftest ok")


if __name__ == "__main__":
    main()
