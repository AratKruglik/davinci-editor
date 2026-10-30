"""Index and search a local sound effects / music library. Never modifies the files.

index:  python3 sound_library.py index --sfx DIR --music DIR --out index.json
search: python3 sound_library.py search index.json --kind sfx|music [--min-s 1] [--max-s 4] [--bpm 90-110] WORDS...

Tags come from folder and file names ("Whooshes/Fast/whoosh_air_01.wav" -> whooshes, fast, whoosh, air).
"source" is the first folder under the library root (e.g. a vendor or pack); "license" points to a
LICENSE/README file found in that source folder, so the user can check YouTube Content ID terms.
"""
import argparse
import json
import os
import re
import subprocess
import wave

AUDIO = {".wav", ".aif", ".aiff", ".mp3", ".m4a", ".flac", ".caf"}
LICENSE_FILE = re.compile(r"^(licen[cs]e|readme|terms)", re.I)
BPM = re.compile(r"(\d{2,3})\s*-?\s*bpm", re.I)
SPLIT = re.compile(r"[^0-9a-zа-яіїєґ]+", re.I)


def tags_of(rel):
    words = []
    for part in re.sub(r"([a-z])([A-Z])", r"\1 \2", os.path.splitext(rel)[0]).split(os.sep):
        words += [w.lower() for w in SPLIT.split(part) if len(w) > 1 and not w.isdigit()]
    return list(dict.fromkeys(words))


def duration(path):
    if path.lower().endswith(".wav"):
        try:
            with wave.open(path) as w:
                return round(w.getnframes() / w.getframerate(), 2)
        except (wave.Error, EOFError):
            pass
    try:  # macOS Core Audio reads every other format here
        out = subprocess.run(["afinfo", path], capture_output=True, text=True, timeout=10).stdout
        m = re.search(r"estimated duration:\s*([\d.]+)", out)
        return round(float(m.group(1)), 2) if m else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def license_for(root, source):
    folder = os.path.join(root, source) if source else root
    for base in (folder, root):
        for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            if LICENSE_FILE.match(name) and os.path.isfile(os.path.join(base, name)):
                return os.path.join(base, name)
    return None


def index(libraries):
    items = []
    for kind, root in libraries:
        if not root or not os.path.isdir(root):
            continue
        licenses = {}
        for folder, _, files in os.walk(root):
            for name in sorted(files):
                if os.path.splitext(name)[1].lower() not in AUDIO or name.startswith("._"):
                    continue
                path = os.path.join(folder, name)
                rel = os.path.relpath(path, root)
                source = rel.split(os.sep)[0] if os.sep in rel else ""
                if source not in licenses:
                    licenses[source] = license_for(root, source)
                bpm = BPM.search(name)
                items.append({"kind": kind, "path": path, "name": name, "tags": tags_of(rel), "duration_s": duration(path),
                              "bpm": int(bpm.group(1)) if bpm else None, "source": source, "license": licenses[source]})
    return items


def search(items, words, kind=None, min_s=None, max_s=None, bpm=None, limit=10):
    words = [w.lower() for w in words]
    lo, hi = (int(x) for x in bpm.split("-")) if bpm else (None, None)
    ranked = []
    for it in items:
        d = it["duration_s"]
        if kind and it["kind"] != kind:
            continue
        if (min_s is not None and (d is None or d < min_s)) or (max_s is not None and (d is None or d > max_s)):
            continue
        if bpm and not (it["bpm"] and lo <= it["bpm"] <= hi):
            continue
        score = sum(2 if w in it["tags"] else 1 for w in words if any(w in t for t in it["tags"]))
        if score or not words:
            ranked.append((score, it))
    ranked.sort(key=lambda r: (-r[0], r[1]["path"]))
    return [dict(it, score=score) for score, it in ranked[:limit]]


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="mode", required=True)
    i = sub.add_parser("index")
    i.add_argument("--sfx")
    i.add_argument("--music")
    i.add_argument("--out", required=True)
    s = sub.add_parser("search")
    s.add_argument("index")
    s.add_argument("words", nargs="*")
    s.add_argument("--kind", choices=["sfx", "music"])
    s.add_argument("--min-s", type=float)
    s.add_argument("--max-s", type=float)
    s.add_argument("--bpm", help="range like 90-110")
    s.add_argument("--limit", type=int, default=10)
    a = p.parse_args()
    if a.mode == "index":
        items = index([("sfx", a.sfx), ("music", a.music)])
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
        sources = {}
        for it in items:
            sources.setdefault(f'{it["kind"]}:{it["source"] or "-"}', {"files": 0, "license": it["license"]})["files"] += 1
        print(json.dumps({"files": len(items), "no_duration": sum(1 for it in items if it["duration_s"] is None), "sources": sources},
                         ensure_ascii=False, indent=1))
    else:
        with open(a.index, encoding="utf-8") as f:
            items = json.load(f)
        print(json.dumps(search(items, a.words, a.kind, a.min_s, a.max_s, a.bpm, a.limit), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
