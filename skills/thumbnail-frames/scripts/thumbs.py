"""Rank exported stills as thumbnail candidates by sharpness, exposure and clipping (stdlib only).

python3 thumbs.py score <still.tif | folder> ... [--out scores.json]
python3 thumbs.py selftest

Faces, eyes and expression are judged by looking at the images; this script only removes the technically weak ones
(motion blur, blinks often blur too, under/over-exposure) so the visual pass starts from the best frames.
"""
import argparse
import json
import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "chart-match", "scripts"))
from chart_match import read_tiff

GRID = 480   # samples across; enough to see focus and motion blur at thumbnail size


def luma_grid(path):
    width, height, pixel = read_tiff(path)
    step = max(1, width // GRID)
    rows = []
    for y in range(0, height, step):
        rows.append([0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in (pixel(x, y) for x in range(0, width, step))])
    return width, height, rows


def score(path):
    width, height, g = luma_grid(path)
    flat = [v for row in g for v in row]
    n = len(flat)
    mean = sum(flat) / n
    std = (sum((v - mean) ** 2 for v in flat) / n) ** 0.5
    lap = [4 * g[y][x] - g[y - 1][x] - g[y + 1][x] - g[y][x - 1] - g[y][x + 1]
           for y in range(1, len(g) - 1) for x in range(1, len(g[0]) - 1)]
    lap_mean = sum(lap) / len(lap)
    sharp = sum((v - lap_mean) ** 2 for v in lap) / len(lap) * 1000
    clipped_hi = sum(v > 0.98 for v in flat) / n
    clipped_lo = sum(v < 0.02 for v in flat) / n
    exposure_ok = 0.25 <= mean <= 0.7
    total = sharp * (1 if exposure_ok else 0.5) * (1 - min(0.5, 3 * (clipped_hi + clipped_lo)))
    return {"file": os.path.basename(path), "path": path, "size": [width, height], "sharpness": round(sharp, 3),
            "mean_luma": round(mean, 3), "contrast": round(std, 3), "clipped_highlights": round(clipped_hi, 4),
            "clipped_shadows": round(clipped_lo, 4), "exposure_ok": exposure_ok, "score": round(total, 3)}


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += sorted(os.path.join(p, n) for n in os.listdir(p) if n.lower().endswith((".tif", ".tiff")))
        else:
            out.append(p)
    return out


def write_tiff(path, width, height, rgb):
    """Minimal uncompressed 8-bit RGB TIFF (used by the selftest)."""
    data = bytes(v for y in range(height) for x in range(width) for v in rgb(x, y))
    entries = [(256, 4, 1, width), (257, 4, 1, height), (258, 3, 1, 8), (259, 3, 1, 1), (262, 3, 1, 2),
               (273, 4, 1, 8), (277, 3, 1, 3), (278, 4, 1, height), (279, 4, 1, len(data)), (284, 3, 1, 1)]
    ifd = 8 + len(data)
    with open(path, "wb") as f:
        f.write(b"II" + struct.pack("<HI", 42, ifd) + data + struct.pack("<H", len(entries)))
        for tag, typ, count, value in entries:
            f.write(struct.pack("<HHII", tag, typ, count, value) if typ == 4 else struct.pack("<HHIHH", tag, typ, count, value, 0))
        f.write(struct.pack("<I", 0))


def selftest():
    with tempfile.TemporaryDirectory() as d:
        sharp, soft, dark = (os.path.join(d, n) for n in ("a_sharp.tif", "b_soft.tif", "c_dark.tif"))
        write_tiff(sharp, 64, 36, lambda x, y: (200, 180, 160) if (x // 2 + y // 2) % 2 else (60, 50, 40))
        write_tiff(soft, 64, 36, lambda x, y: (130 + x, 115 + x, 100 + x))
        write_tiff(dark, 64, 36, lambda x, y: (8, 6, 4) if (x // 2 + y // 2) % 2 else (1, 1, 1))
        s = {r["file"]: r for r in map(score, collect([d]))}
        assert s["a_sharp.tif"]["sharpness"] > 10 * s["b_soft.tif"]["sharpness"], s
        assert s["a_sharp.tif"]["exposure_ok"] and not s["c_dark.tif"]["exposure_ok"], s
        assert s["c_dark.tif"]["clipped_shadows"] > 0.4 and s["a_sharp.tif"]["score"] > s["c_dark.tif"]["score"], s
    print("thumbs selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score")
    s.add_argument("paths", nargs="+")
    s.add_argument("--out")
    a = ap.parse_args()
    ranked = sorted((score(p) for p in collect(a.paths)), key=lambda r: -r["score"])
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(ranked, f, ensure_ascii=False, indent=1)
    print(json.dumps([{k: r[k] for k in ("file", "score", "sharpness", "mean_luma", "exposure_ok")} for r in ranked], indent=1))


if __name__ == "__main__":
    main()
