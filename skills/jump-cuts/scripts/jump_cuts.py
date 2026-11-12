"""Judge every A-roll join of a cut timeline and plan the lightest treatment that hides the jump.

python3 jump_cuts.py joins <dump.json> --transcripts <dir> [--fixed-transform ITEM_ID ...] [--source-offset 0] --out joins.json
python3 jump_cuts.py selftest

Frames are absolute timeline frames; a join's `frame` is the first frame of its right segment. Word bounds for
`roll_range` are source frames from the clip start ([start, end), end exclusive).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "resolve-core", "scripts"))
from tc import frames_to_tc
from timeline_map import find_track, load, source_words

COVER_ROLES = ("b-roll", "screen")
MIN_SEGMENT_S = 2
AFTER_WORD = 2
ATTACK_S = 0.15
MAX_ROLL = 6


def role(track_name):
    return track_name.strip().lower().rstrip(" 0123456789")


def roll_range(left_out, right_in, left_words, right_words, fps):
    """Frames [lo, hi] the cut may move by without touching a word on either side; None when it may not move."""
    if not left_words or not right_words:
        return None
    lo, hi = -MAX_ROLL, MAX_ROLL
    kept = [e for s, e in left_words if s < left_out]
    removed_next = [s for s, e in left_words if s >= left_out]
    removed_prev = [e for s, e in right_words if e <= right_in]
    first = [s for s, e in right_words if e > right_in]
    if kept:
        lo = max(lo, max(kept) + AFTER_WORD - left_out)
    if removed_next:
        hi = min(hi, min(removed_next) - left_out)
    if removed_prev:
        lo = max(lo, max(removed_prev) + AFTER_WORD - right_in)
    if first:
        hi = min(hi, min(first) - round(ATTACK_S * fps) - right_in)
    return None if lo > hi or lo == hi == 0 else [lo, hi]


def build_joins(dump, transcripts, fixed_transform=frozenset(), source_offset=0):
    fps = dump["fps"]
    items = sorted(find_track(dump, "video", "A-roll")["items"], key=lambda i: i["start"])
    covers = sorted((i["start"], i["end"]) for t in dump["tracks"]["video"]
                    if t.get("enabled", True) and role(t["name"]) in COVER_ROLES
                    for i in t["items"] if i.get("enabled", True))
    markers = {dump["start_frame"] + int(f): m for f, m in (dump.get("markers") or {}).items()}
    words = {clip: [(s, e) for s, e, _, _ in source_words(data)] for clip, data in transcripts.items()}

    def covered(start, end):
        pos = start
        for s, e in covers:
            if s <= pos < e:
                pos = e
        return pos >= end

    def unusable(item):
        if not item.get("enabled", True):
            return "disabled"
        return "speed" if abs(item.get("speed", 100.0) - 100.0) > 0.01 else None

    def fixed(item):
        if unusable(item):
            return unusable(item)
        if covered(item["start"], item["end"]):
            return "hidden"
        if item.get("item_id") in fixed_transform:
            return "transform"
        return "short" if item["end"] - item["start"] < round(MIN_SEGMENT_S * fps) else None

    segments = [{"index": n, "item_id": i.get("item_id"), "clip_id": i.get("clip_id"), "start": i["start"], "end": i["end"],
                 "source_start": i["source_start"], "left_offset": i.get("left_offset", 0),
                 "right_offset": i.get("right_offset", 0), "fixed": fixed(i), "scale": 1.0} for n, i in enumerate(items)]
    joins = []
    for n, (left, right) in enumerate(zip(items, items[1:])):
        if left["end"] != right["start"]:
            continue
        frame = right["start"]
        marker = markers.get(frame, {})
        left_out = left["source_start"] - source_offset + left["end"] - left["start"]
        right_in = right["source_start"] - source_offset
        join = {"id": f"j{len(joins) + 1}", "frame": frame, "left": n, "right": n + 1,
                "removed": marker.get("note", "") if marker.get("customData") == "claude:cut" else "",
                "split": marker.get("customData") == "claude:split",
                "covered": covered(frame - 1, frame + 1),
                "source_change": left.get("clip_id") != right.get("clip_id") or right_in < left_out,
                "skip": unusable(left) or unusable(right), "roll_range": None, "rolled": False,
                "diff": None, "max_cell": None, "observation": None, "auto": None, "decision": None, "reason": ""}
        if not (join["split"] or join["covered"] or join["source_change"] or join["skip"]):
            clip_words = words.get(left.get("clip_id"), [])
            join["roll_range"] = roll_range(left_out, right_in, clip_words, clip_words, fps)
        joins.append(join)
    return {"timeline_id": dump.get("timeline_id"), "fps": fps, "width": dump.get("width"), "height": dump.get("height"),
            "start_frame": dump["start_frame"], "segments": segments, "joins": joins}


def load_transcripts(folder):
    transcripts = {}
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json"):
            data = load(os.path.join(folder, name))
            transcripts[data["clip_id"]] = data
    return transcripts


def save(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def _fixture():
    def item(item_id, start, end, source_start, clip="c1", **extra):
        return dict({"name": clip, "item_id": item_id, "clip_id": clip, "start": start, "end": end,
                     "source_start": source_start, "source_end": source_start + end - start,
                     "left_offset": source_start, "right_offset": 900, "enabled": True, "speed": 100.0}, **extra)

    def transcript(clip, pairs):
        words = [{"start": frames_to_tc(90000 + s, 25), "end": frames_to_tc(90000 + e, 25), "text": "слово"} for s, e in pairs]
        return {"clip_id": clip, "clip_name": clip, "fps": 25, "start_tc": "01:00:00:00",
                "transcription": {"segments": [{"speaker": None, "words": words}]}}

    a_roll = [item("id-a", 90000, 90250, 0), item("id-b", 90250, 90400, 300), item("id-c", 90400, 90440, 500),
              item("id-d", 90440, 90600, 0, clip="c2"), item("id-e", 90600, 90800, 400, clip="c2"),
              item("id-f", 90810, 91000, 700, clip="c2")]
    dump = {"timeline_id": "tl", "fps": 25.0, "width": 3840, "height": 2160, "start_frame": 90000, "end_frame": 91000,
            "markers": {"250": {"customData": "claude:cut", "note": "pause"}, "600": {"customData": "claude:split", "note": "J"}},
            "tracks": {"video": [
                {"index": 2, "name": "A-roll", "enabled": True, "items": a_roll},
                {"index": 3, "name": "B-roll", "enabled": True, "items": [item("id-x", 90250, 90410, 0, clip="b1")]},
                {"index": 4, "name": "Titles", "enabled": True, "items": [item("id-t", 90000, 91000, 0, clip=None)]}],
                "audio": [{"index": 1, "name": "Voice", "enabled": True, "items": []}]}}
    transcripts = {"c1": transcript("c1", [(200, 245), (254, 290), (310, 330), (505, 530)]),
                   "c2": transcript("c2", [(10, 150), (405, 590), (705, 880)])}
    return dump, transcripts, item


def selftest():
    dump, transcripts, item = _fixture()
    j = build_joins(dump, transcripts)
    by = {x["id"]: x for x in j["joins"]}
    seg = j["segments"]
    assert [x["id"] for x in j["joins"]] == ["j1", "j2", "j3", "j4"], j["joins"]
    assert by["j1"]["roll_range"] == [-3, 4] and not by["j1"]["covered"] and by["j1"]["removed"] == "pause", by["j1"]
    assert by["j2"]["covered"] and by["j2"]["roll_range"] is None, by["j2"]
    assert by["j3"]["source_change"], by["j3"]
    assert by["j4"]["split"] and by["j4"]["roll_range"] is None, by["j4"]
    assert seg[2]["fixed"] == "short" and seg[1]["fixed"] == "hidden" and seg[0]["fixed"] is None, seg
    assert build_joins(dump, transcripts, {"id-a"})["segments"][0]["fixed"] == "transform"
    assert all(x["frame"] != 90810 for x in j["joins"])
    assert not by["j3"]["covered"], "a title above the join must not count as cover"

    one = dict(dump, tracks={"video": [{"index": 2, "name": "A-roll", "enabled": True, "items": [item("id-a", 90000, 90250, 0)]}]})
    assert build_joins(one, {})["joins"] == []
    slow = dict(dump, tracks={"video": [{"index": 2, "name": "A-roll", "enabled": True, "items": [
        item("id-a", 90000, 90250, 0), item("id-b", 90250, 90400, 300, speed=50.0)]}]})
    out = build_joins(slow, transcripts)
    assert out["joins"][0]["skip"] == "speed" and out["segments"][1]["fixed"] == "speed", out
    assert build_joins(dump, {})["joins"][0]["roll_range"] is None

    assert roll_range(250, 400, [(200, 240), (260, 280)], [(380, 390), (410, 430)], 25.0) == [-6, 6]
    assert roll_range(250, 400, [(200, 249), (252, 280)], [(380, 399), (405, 430)], 25.0) == [1, 1]
    assert roll_range(250, 400, [(200, 250), (250, 280)], [(380, 400), (402, 430)], 25.0) is None
    assert roll_range(250, 400, [], [], 25.0) is None
    print("jump_cuts selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    jo = sub.add_parser("joins")
    jo.add_argument("dump")
    jo.add_argument("--transcripts")
    jo.add_argument("--fixed-transform", nargs="*", default=[])
    jo.add_argument("--source-offset", type=int, default=0)
    jo.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "joins":
        transcripts = load_transcripts(a.transcripts) if a.transcripts and os.path.isdir(a.transcripts) else {}
        data = build_joins(load(a.dump), transcripts, set(a.fixed_transform), a.source_offset)
        save(a.out, data)
        return print(json.dumps({"joins": len(data["joins"]), "segments": len(data["segments"]), "out": a.out}))


if __name__ == "__main__":
    main()
