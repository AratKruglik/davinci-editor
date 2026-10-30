"""Check chapters against YouTube's rules and write the description block.

python3 chapters.py check <chapters.json> --fps 25 --duration-frames N --out chapters.txt
python3 chapters.py selftest

chapters.json: [{"frame": 0, "title": "Вступ", "source": "marker|claude"}]  # frames from the timeline start
YouTube turns the description into chapters only if: the first timestamp is 0:00, there are at least 3, and each
chapter is at least 10 s long. Times are floored to whole seconds (a chapter starting a little early is fine, late is not).
"""
import argparse
import json
import os
import re
import sys

MIN_CHAPTER_S = 10
MIN_COUNT = 3
MAX_TITLE = 100


def stamp(seconds, long_video):
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if long_video else f"{m}:{s:02d}"


def check(chapters, fps, duration_frames):
    errors, warnings = [], []
    items = sorted(chapters, key=lambda c: c["frame"])
    if items != chapters:
        warnings.append("chapters were not in time order; sorted")
    if len(items) < MIN_COUNT:
        errors.append(f"{len(items)} chapters; YouTube needs at least {MIN_COUNT}")
    if not items or items[0]["frame"] >= fps:
        errors.append("the first chapter must start at 0:00 (add an intro chapter at frame 0 or move the first one)")
    ends = [c["frame"] for c in items[1:]] + [duration_frames]
    for c, end in zip(items, ends):
        title = c["title"].strip()
        if not title:
            errors.append(f"chapter at frame {c['frame']} has no title")
        if len(title) > MAX_TITLE:
            errors.append(f"{title[:30]}…: title longer than {MAX_TITLE} characters")
        if re.match(r"^\d+:\d{2}", title):
            errors.append(f"{title!r}: a title must not start with a timestamp")
        if (end - c["frame"]) / fps < MIN_CHAPTER_S:
            errors.append(f"{title!r}: {(end - c['frame']) / fps:.1f} s; every chapter needs at least {MIN_CHAPTER_S} s")
    long_video = duration_frames / fps >= 3600
    lines = [f"{stamp(c['frame'] / fps, long_video)} {c['title'].strip()}" for c in items]
    seen = {}
    for line in lines:
        t = line.split(" ", 1)[0]
        if t in seen:
            errors.append(f"two chapters at {t}: {seen[t]!r} and {line!r}")
        seen[t] = line
    return {"ok": not errors, "errors": errors, "warnings": warnings, "text": "\n".join(lines) + "\n"}


def selftest():
    ok = check([{"frame": 0, "title": "Вступ"}, {"frame": 25 * 40, "title": "Налаштування Wi-Fi"},
                {"frame": 25 * 125 + 20, "title": "Безпека"}], 25, 25 * 300)
    assert ok["ok"] and ok["text"] == "0:00 Вступ\n0:40 Налаштування Wi-Fi\n2:05 Безпека\n", ok
    bad = check([{"frame": 50, "title": "Початок"}, {"frame": 200, "title": "Коротко"}], 25, 25 * 60)
    assert not bad["ok"] and any("0:00" in e for e in bad["errors"]) and any("at least 3" in e for e in bad["errors"])
    short = check([{"frame": 0, "title": "A"}, {"frame": 100, "title": "B"}, {"frame": 1000, "title": "C"}], 25, 2000)
    assert any("'A': 4.0 s" in e for e in short["errors"]), short["errors"]
    hour = check([{"frame": 0, "title": "A"}, {"frame": 25 * 1800, "title": "B"}, {"frame": 25 * 3700, "title": "C"}], 25, 25 * 4000)
    assert hour["text"].splitlines()[2] == "1:01:40 C", hour["text"]
    ntsc = check([{"frame": 0, "title": "A"}, {"frame": 1199, "title": "B"}, {"frame": 2400, "title": "C"}], 29.97, 4000)
    assert ntsc["text"].splitlines()[1] == "0:40 B", ntsc["text"]
    print("chapters selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("chapters")
    c.add_argument("--fps", type=float, required=True)
    c.add_argument("--duration-frames", type=int, required=True)
    c.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.chapters, encoding="utf-8") as f:
        chapters = json.load(f)
    result = check(chapters, a.fps, a.duration_frames)
    if result["ok"]:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(result["text"])
    print(json.dumps(dict(result, out=a.out if result["ok"] else None), ensure_ascii=False, indent=1))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
