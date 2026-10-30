"""Shorts from a cut timeline: sentence list for picking, then an append plan for a new vertical timeline.

python3 shorts.py sentences <words.json> [--pause-s 0.6] --out sentences.json
python3 shorts.py plan <timeline dump.json> <shorts.json> [--min-s 30] [--max-s 60] [--video A-roll] [--audio Voice] --out plan.json
python3 shorts.py selftest

shorts.json: [{"id": "s1", "title": "...", "ranges": [[start, end], ...]}]  # cut-timeline frames, [start, end), in order
Each Short re-uses the source media of the cut (timeline_map.sources_for_range), so its timeline is independent of the
episode and stays editable. Ranges should start and end on sentence borders from `sentences`.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "resolve-core", "scripts"))
from timeline_map import load, sources_for_range

ENDS = (".", "?", "!", "…")


def sentences(data, pause_s=0.6):
    fps, out, cur = data["fps"], [], []
    for w in data["words"]:
        if cur and (cur[-1]["text"].endswith(ENDS) or (w["start"] - cur[-1]["end"]) / fps > pause_s):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return [{"id": i, "start": s[0]["start"], "end": s[-1]["end"], "seconds": round((s[-1]["end"] - s[0]["start"]) / fps, 1),
             "text": " ".join(w["text"] for w in s)} for i, s in enumerate(out, 1)]


def plan(dump, shorts, min_s=30, max_s=60, video=("A-roll",), audio=("Voice",), lead=3, tail=8):
    """lead/tail: frames of air kept before the first and after the last word of each range."""
    fps = dump["fps"]
    result = []
    for sh in shorts:
        entries, warnings, record = [], [], 0
        ranges = [[max(dump["start_frame"], s - lead), min(dump["end_frame"], e + tail)] for s, e in sh["ranges"]]
        for (s, e), nxt in zip(ranges, ranges[1:] + [None]):
            if nxt and nxt[0] < e:
                warnings.append(f"ranges {s}-{e} and {nxt[0]}-{nxt[1]} overlap or are out of order")
        for s, e in ranges:
            for kind, roles in (("video", video), ("audio", audio)):
                for role in roles:
                    try:
                        found = sources_for_range(dump, kind, role, s, e)
                    except SystemExit as exc:
                        warnings.append(str(exc))
                        continue
                    warnings += found["warnings"]
                    for p in found["pieces"]:
                        entries.append({"kind": kind, "role": role, "clip_id": p["clip_id"], "name": p["name"],
                                        "source_start": p["source_start"], "source_end": p["source_end"],
                                        "record": record + p["record_offset"]})
            record += e - s
        seconds = round(record / fps, 1)
        if seconds < min_s or seconds > max_s:
            warnings.append(f"{seconds} s is outside {min_s}-{max_s} s")
        result.append({"id": sh["id"], "title": sh.get("title", ""), "frames": record, "seconds": seconds,
                       "joins": len(ranges) - 1, "entries": entries, "warnings": warnings})
    return result


def selftest():
    def w(t, s, e):
        return {"text": t, "start": s, "end": e}
    words = {"fps": 25, "start_frame": 1000, "words": [w("Перше", 1000, 1010), w("речення.", 1011, 1030),
             w("Друге", 1050, 1060), w("довше", 1061, 1070), w("речення", 1071, 1080), w("пауза", 1120, 1130)]}
    sen = sentences(words)
    assert [x["text"] for x in sen] == ["Перше речення.", "Друге довше речення", "пауза"], sen
    assert sen[1]["start"] == 1050 and sen[1]["end"] == 1080

    dump = {"fps": 25, "start_frame": 1000, "end_frame": 3000, "tracks": {
        "video": [{"name": "A-roll", "items": [
            {"name": "c", "clip_id": "c1", "start": 1000, "end": 2000, "source_start": 500, "source_end": 1500},
            {"name": "c", "clip_id": "c1", "start": 2000, "end": 3000, "source_start": 2000, "source_end": 3000}]}],
        "audio": [{"name": "Voice", "items": [
            {"name": "c", "clip_id": "c1", "start": 1000, "end": 2000, "source_start": 500, "source_end": 1500},
            {"name": "c", "clip_id": "c1", "start": 2000, "end": 3000, "source_start": 2000, "source_end": 3000}]}]}}
    p = plan(dump, [{"id": "s1", "ranges": [[1203, 1992], [2003, 2392]]}], min_s=30, max_s=60)[0]
    assert p["frames"] == (1992 + 8 - 1200) + (2392 + 8 - 2000), p["frames"]
    vids = [e for e in p["entries"] if e["kind"] == "video"]
    assert vids[0] == {"kind": "video", "role": "A-roll", "clip_id": "c1", "name": "c", "source_start": 700,
                       "source_end": 1500, "record": 0}, vids
    assert vids[1]["source_start"] == 2000 and vids[1]["record"] == 800, vids
    assert len([e for e in p["entries"] if e["kind"] == "audio"]) == 2 and not p["warnings"], p
    short = plan(dump, [{"id": "s2", "ranges": [[1100, 1300]]}])[0]
    assert any("outside 30-60" in x for x in short["warnings"]), short
    print("shorts selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sentences")
    s.add_argument("words")
    s.add_argument("--pause-s", type=float, default=0.6)
    s.add_argument("--out", required=True)
    p = sub.add_parser("plan")
    p.add_argument("dump")
    p.add_argument("shorts")
    p.add_argument("--min-s", type=float, default=30)
    p.add_argument("--max-s", type=float, default=60)
    p.add_argument("--video", default="A-roll")
    p.add_argument("--audio", default="Voice")
    p.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "sentences":
        out = sentences(load(a.words), a.pause_s)
    else:
        out = plan(load(a.dump), load(a.shorts), a.min_s, a.max_s, a.video.split(","), a.audio.split(","))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    summary = [{"id": x["id"], "seconds": x["seconds"], "joins": x["joins"], "warnings": x["warnings"]} for x in out] \
        if a.cmd == "plan" else {"sentences": len(out)}
    print(json.dumps({"out": a.out, "summary": summary}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
