"""Map transcript words onto a cut timeline, and timeline ranges back to source media.

Transcripts (uk-transcribe) are in clip timecode; stage-3 skills work on the cut timeline. Both directions go through
a live dump of the timeline (format: resolve-core/reference.md#timeline-dump), never through plan.json, because the
user may have trimmed after the rough cut.

python3 timeline_map.py words <dump.json> <transcripts dir> [--track Voice] [--source-offset 0] --out words.json
python3 timeline_map.py sources <dump.json> --track A-roll --range START END [--range START END ...]
python3 timeline_map.py selftest

Frames are absolute timeline frames ([start, end), end exclusive). `--source-offset` is the append calibration's
offset (resolve-core): GetSourceStartFrame() = transcript source frame + offset.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tc import tc_to_frames

SILENCE = "(...)"


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_track(dump, kind, role):
    for t in dump["tracks"].get(kind, []):
        if t["name"].strip().lower() == role.lower():
            return t
    names = [t["name"] for t in dump["tracks"].get(kind, [])]
    raise SystemExit(f"no {kind} track named {role!r}; tracks: {names}")


def source_words(data):
    """Words of one transcript JSON as (start, end, text, speaker) in source frames from the clip start."""
    fps, drop = data["fps"], data.get("drop_frame", False)
    origin = tc_to_frames(data["start_tc"], fps, drop)
    for seg in (data.get("transcription") or {}).get("segments", []):
        for w in seg.get("words", []):
            if w["text"].strip() not in ("", SILENCE):
                start = tc_to_frames(w["start"], fps, drop) - origin
                end = max(start + 1, tc_to_frames(w["end"], fps, drop) - origin)
                yield start, end, w["text"].strip(), seg.get("speaker")


def usable(item, warnings, track_name):
    where = f'{track_name} item {item["name"]!r} @ {item["start"]}'
    if not item.get("enabled", True):
        warnings.append(f"{where}: disabled, skipped")
        return False
    if abs(item.get("speed", 100.0) - 100.0) > 0.01:
        warnings.append(f'{where}: speed {item["speed"]} %, skipped (timing would drift)')
        return False
    return True


def words_on_timeline(dump, transcripts, role="Voice", source_offset=0):
    """transcripts: {clip_id: transcript JSON}. A word belongs to the item that shows its midpoint."""
    track = find_track(dump, "audio", role)
    words, warnings = [], []
    for item in sorted(track["items"], key=lambda i: i["start"]):
        data = transcripts.get(item.get("clip_id"))
        if data is None:
            warnings.append(f'{role} item {item["name"]!r} @ {item["start"]}: no transcript for this clip')
            continue
        if not usable(item, warnings, role):
            continue
        lo = item["source_start"] - source_offset
        hi = lo + item["end"] - item["start"]
        prev_end = None
        # transcript order is the spoken order; overlapping segment timings must not reorder words
        for start, end, text, speaker in source_words(data):
            if prev_end is not None and start < prev_end:
                start, end = prev_end, max(end, prev_end + 1)
            prev_end = end
            if lo <= (start + end) / 2 < hi:
                s, e = max(start, lo), min(end, hi)
                words.append({"text": text, "start": item["start"] + s - lo, "end": item["start"] + e - lo,
                              "clip": data["clip_name"], "speaker": speaker})
    return {"fps": dump["fps"], "start_frame": dump["start_frame"], "words": words, "warnings": warnings}


def sources_for_range(dump, kind, role, start, end):
    """Pieces of [start, end) on a track as source ranges: [{clip_id, name, source_start, source_end, record_offset}]."""
    track = find_track(dump, kind, role)
    pieces, warnings = [], []
    for item in sorted(track["items"], key=lambda i: i["start"]):
        s, e = max(start, item["start"]), min(end, item["end"])
        if s >= e or not usable(item, warnings, role):
            continue
        src = item["source_start"] + s - item["start"]
        pieces.append({"clip_id": item["clip_id"], "name": item["name"], "source_start": src,
                       "source_end": src + e - s, "record_offset": s - start})
    covered = sum(p["source_end"] - p["source_start"] for p in pieces)
    if covered < end - start:
        warnings.append(f"{role}: {end - start - covered} of {end - start} frames in {start}-{end} have no usable item (gap)")
    return {"pieces": pieces, "warnings": warnings}


def selftest():
    words = [{"start": "01:00:00:10", "end": "01:00:00:19", "text": "Привіт"},
             {"start": "01:00:00:20", "end": "01:00:01:04", "text": "(...)"},
             {"start": "01:00:01:05", "end": "01:00:01:14", "text": "друзі"},
             {"start": "01:00:02:00", "end": "01:00:02:09", "text": "вирізане"},
             {"start": "01:00:03:00", "end": "01:00:03:09", "text": "кінець"}]
    tr = {"c1": {"clip_name": "IMG_1", "fps": 25, "start_tc": "01:00:00:00",
                 "transcription": {"segments": [{"speaker": None, "words": words}]}}}
    dump = {"fps": 25, "start_frame": 90000, "tracks": {"audio": [{"name": "Voice", "items": [
        {"name": "IMG_1", "clip_id": "c1", "start": 90000, "end": 90040, "source_start": 0, "source_end": 40},
        {"name": "IMG_1", "clip_id": "c1", "start": 90040, "end": 90060, "source_start": 75, "source_end": 95},
        {"name": "IMG_1", "clip_id": "c1", "start": 90060, "end": 90070, "source_start": 0, "source_end": 10, "speed": 50.0},
    ]}], "video": [{"name": "A-roll", "items": [
        {"name": "IMG_1", "clip_id": "c1", "start": 90000, "end": 90040, "source_start": 0, "source_end": 40},
        {"name": "IMG_1", "clip_id": "c1", "start": 90040, "end": 90060, "source_start": 75, "source_end": 95}]}]}}
    out = words_on_timeline(dump, tr)
    texts = [(w["text"], w["start"], w["end"]) for w in out["words"]]
    # "вирізане" (source 50-59) is outside both kept ranges; "кінець" (source 75-84) lands at 90040
    assert texts == [("Привіт", 90010, 90019), ("друзі", 90030, 90039), ("кінець", 90040, 90049)], texts
    assert any("speed 50.0" in w for w in out["warnings"]), out["warnings"]

    overlap = {"c1": dict(tr["c1"], transcription={"segments": [
        {"speaker": None, "words": [{"start": "01:00:00:10", "end": "01:00:00:30", "text": "чия"}, {"start": "01:00:00:31", "end": "01:00:01:05", "text": "вона."}]},
        {"speaker": None, "words": [{"start": "01:00:00:28", "end": "01:00:01:10", "text": "Пароль"}]}]})}
    order = [w["text"] for w in words_on_timeline(dump, overlap)["words"]]
    assert order == ["чия", "вона.", "Пароль"], order

    shifted = words_on_timeline(dump, tr, source_offset=5)
    assert shifted["words"][0]["start"] == 90015, shifted["words"][0]

    src = sources_for_range(dump, "video", "A-roll", 90030, 90050)
    assert src["pieces"] == [
        {"clip_id": "c1", "name": "IMG_1", "source_start": 30, "source_end": 40, "record_offset": 0},
        {"clip_id": "c1", "name": "IMG_1", "source_start": 75, "source_end": 85, "record_offset": 10}], src
    assert not src["warnings"]
    gap = sources_for_range(dump, "video", "A-roll", 90050, 90080)
    assert gap["warnings"] and "20 of 30" in gap["warnings"][0], gap
    print("timeline_map selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("words")
    w.add_argument("dump")
    w.add_argument("transcripts")
    w.add_argument("--track", default="Voice")
    w.add_argument("--source-offset", type=int, default=0)
    w.add_argument("--out", required=True)
    s = sub.add_parser("sources")
    s.add_argument("dump")
    s.add_argument("--kind", default="video", choices=["video", "audio"])
    s.add_argument("--track", default="A-roll")
    s.add_argument("--range", nargs=2, type=int, action="append", required=True, metavar=("START", "END"))
    a = ap.parse_args()
    dump = load(a.dump)
    if a.cmd == "words":
        transcripts = {}
        for name in sorted(os.listdir(a.transcripts)):
            if name.endswith(".json"):
                data = load(os.path.join(a.transcripts, name))
                transcripts[data["clip_id"]] = data
        out = words_on_timeline(dump, transcripts, a.track, a.source_offset)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(json.dumps({"words": len(out["words"]), "warnings": out["warnings"], "out": a.out}, ensure_ascii=False, indent=1))
    else:
        print(json.dumps([dict(range=r, **sources_for_range(dump, a.kind, a.track, *r)) for r in a.range],
                         ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
