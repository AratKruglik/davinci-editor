"""Read-only pre-delivery checks on a timeline dump (resolve-core/reference.md#timeline-dump).

python3 qc.py check <dump.json> [--expect-width 3840 --expect-height 2160 --expect-fps 25] [--sliver 3] --out qc.json
python3 qc.py add <qc.json> --severity error|warn|info --kind <kind> --message "<text>" [--tc <TC>] [--track <name>]
python3 qc.py stale <qc.json> <fresh dump.json>      (exit 1 = the timeline changed since the QC)
python3 qc.py selftest

Severity: error = will be visible/audible in the render; warn = probably a mistake, the user decides; info = cleanup.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "resolve-core", "scripts"))
from tc import frames_to_tc

OVERLAY_ROLES = ("titles", "effects", "subtitles")   # these don't count as picture: black under a title is still black
SPEECH_ROLES = ("voice",)


def is_overlay(name):
    return name.strip().lower().rstrip(" 0123456789") in OVERLAY_ROLES


def covered(intervals):
    merged = []
    for s, e in sorted(intervals):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def holes(merged, start, end):
    out, cur = [], start
    for s, e in merged:
        if s > cur:
            out.append((cur, min(s, end)))
        cur = max(cur, e)
    if cur < end:
        out.append((cur, end))
    return [h for h in out if h[1] > h[0]]


def check(dump, expect=None, sliver=3):
    fps, t0 = dump["fps"], dump["start_frame"]
    tc = lambda f: frames_to_tc(f, fps, dump.get("drop_frame", False))
    found = []

    def add(sev, kind, frame, track, msg):
        found.append({"severity": sev, "kind": kind, "frame": frame, "tc": tc(frame) if frame is not None else None,
                      "track": track, "message": msg})

    video = dump["tracks"].get("video", [])
    audio = dump["tracks"].get("audio", [])
    picture = [(i["start"], i["end"]) for t in video if t.get("enabled", True) and not is_overlay(t["name"])
               for i in t["items"] if i.get("enabled", True)]
    last_picture = max((e for _, e in picture), default=t0)
    last_any = max((i["end"] for t in video + audio for i in t["items"]), default=t0)
    for s, e in holes(covered(picture), t0, last_picture):
        add("error", "black", s, None, f"no picture for {e - s} frames ({tc(s)}–{tc(e)})")
    if last_any > last_picture:
        add("warn", "tail", last_picture, None, f"{last_any - last_picture} frames of audio/titles after the last picture: black at the end")

    for kind, tracks in (("video", video), ("audio", audio)):
        for t in tracks:
            name = t["name"]
            items = sorted(t["items"], key=lambda i: i["start"])
            if not items:
                add("info", "empty-track", None, f"{kind} {t['index']} {name}", "empty track (track-layout cleanup)")
                continue
            if not t.get("enabled", True):
                add("warn", "track-disabled", items[0]["start"], name, f"disabled track with {len(items)} items won't render")
            for i in items:
                where = f"{name}: {i['name']}"
                if i["end"] - i["start"] <= sliver:
                    add("error", "sliver", i["start"], name, f"{i['end'] - i['start']}-frame item {i['name']!r} (flash frame)")
                if i.get("clip_id") and i.get("online") not in (None, "Online"):
                    add("error", "offline", i["start"], name, f"{i['name']!r}: media {i.get('online')} ({i.get('file')})")
                if not i.get("enabled", True):
                    add("warn", "clip-disabled", i["start"], name, f"{i['name']!r} is disabled")
                if abs(i.get("speed", 100.0) - 100.0) > 0.01:
                    add("info", "speed", i["start"], name, f"{i['name']!r} at {i['speed']} %")
                if kind == "video" and i.get("fps") and abs(float(i["fps"]) - fps) > 0.01 and abs(i.get("speed", 100.0) - 100.0) < 0.01:
                    add("warn", "fps", i["start"], name, f"{i['name']!r} is {i['fps']} fps on a {fps} fps timeline: judder or frame blending")
            if kind == "audio" and name.strip().lower().rstrip(" 0123456789") in SPEECH_ROLES:
                for a, b in zip(items, items[1:]):
                    if 0 < b["start"] - a["end"] <= 2:
                        add("warn", "audio-dropout", a["end"], name, f"{b['start'] - a['end']}-frame hole between voice items: click or dropout")

    for f, m in sorted(dump.get("markers", {}).items(), key=lambda kv: int(kv[0])):
        frame = t0 + int(f)
        data = m.get("customData") or ""
        if m["color"] == "Cream":
            add("info", "claude-marker", frame, None, f"Cream marker {m.get('name')!r}: {m.get('note', '')} (review, then remove)")
        elif not data.startswith("claude:done") and not data.startswith("claude:skipped"):
            add("warn", "open-marker", frame, None, f"{m['color']} marker {m.get('name')!r} not handled yet: {m.get('note', '')}")

    if expect:
        for key, want in expect.items():
            have = dump.get(key)
            if want is not None and have is not None and abs(float(have) - float(want)) > 0.01:
                add("error", "settings", None, None, f"timeline {key} {have} != delivery {want}")
    return summarize({"timeline": dump.get("name"), "findings": found, "state": state_of(dump)})


ORDER = {"error": 0, "warn": 1, "info": 2}


def state_of(dump):
    """What the QC was run on; deliver compares it with a fresh dump to spot a stale QC."""
    return {"end_frame": dump["end_frame"], "items": {k: sum(len(t["items"]) for t in v) for k, v in dump["tracks"].items()}}


def summarize(result):
    result["findings"].sort(key=lambda x: (ORDER[x["severity"]], x["frame"] if x["frame"] is not None else -1))
    result["counts"] = {s: sum(x["severity"] == s for x in result["findings"]) for s in ORDER}
    result["verdict"] = "FAIL" if result["counts"]["error"] else ("PASS WITH WARNINGS" if result["counts"]["warn"] else "PASS")
    return result


def add(result, severity, kind, message, tc=None, track=None):
    """Findings from the Resolve-side checks (grades, looks, subtitles, chapters, loudness)."""
    if severity not in ORDER:
        raise SystemExit(f"severity must be one of {list(ORDER)}")
    result["findings"].append({"severity": severity, "kind": kind, "frame": None, "tc": tc, "track": track, "message": message})
    return summarize(result)


def stale(result, dump):
    return result.get("state") != state_of(dump)


def selftest():
    dump = {"name": "t", "fps": 25, "start_frame": 1000, "end_frame": 1400, "width": 3840, "height": 2160,
            "markers": {"10": {"color": "Cream", "name": "cut", "note": "", "customData": "claude:cut"},
                        "50": {"color": "Pink", "name": "", "note": "зум", "customData": ""},
                        "60": {"color": "Red", "name": "", "note": "", "customData": "claude:done:text-based-cut:2026-11-01"}},
            "tracks": {"video": [
                {"index": 1, "name": "A-roll", "enabled": True, "items": [
                    {"name": "a", "clip_id": "c1", "start": 1000, "end": 1100, "online": "Online", "fps": 25},
                    {"name": "b", "clip_id": "c1", "start": 1100, "end": 1102, "online": "Online", "fps": 25},
                    {"name": "c", "clip_id": "c2", "start": 1110, "end": 1300, "online": "Offline", "file": "/x.mov", "fps": 30}]},
                {"index": 2, "name": "Titles", "enabled": True, "items": [{"name": "t", "clip_id": None, "start": 1300, "end": 1350}]},
                {"index": 3, "name": "B-roll 2", "enabled": True, "items": []}],
                "audio": [{"index": 1, "name": "Voice", "enabled": True, "items": [
                    {"name": "a", "clip_id": "c1", "start": 1000, "end": 1100}, {"name": "c", "clip_id": "c2", "start": 1101, "end": 1300}]}]}}
    r = check(dump, expect={"width": 1920}, sliver=3)
    kinds = [(f["severity"], f["kind"]) for f in r["findings"]]
    assert ("error", "black") in kinds and ("error", "sliver") in kinds and ("error", "offline") in kinds, kinds
    assert ("error", "settings") in kinds and ("warn", "fps") in kinds and ("warn", "tail") in kinds, kinds
    assert ("warn", "audio-dropout") in kinds and ("warn", "open-marker") in kinds, kinds
    assert ("info", "empty-track") in kinds and ("info", "claude-marker") in kinds, kinds
    black = next(f for f in r["findings"] if f["kind"] == "black")
    assert black["frame"] == 1102 and "8 frames" in black["message"], black
    assert not any(f["kind"] == "open-marker" and "Red" in f["message"] for f in r["findings"])
    assert kinds.index(("error", "black")) < kinds.index(("warn", "tail")) < kinds.index(("info", "empty-track"))
    assert r["verdict"] == "FAIL" and r["state"]["end_frame"] == 1400 and r["state"]["items"]["video"] == 4, r["state"]
    errors = r["counts"]["error"]
    r2 = add(r, "error", "loudness", "-18.3 LUFS, target -14")
    assert r2["counts"]["error"] == errors + 1 and any(f["kind"] == "loudness" for f in r2["findings"]), r2["counts"]
    assert not stale(r, dump)
    moved = json.loads(json.dumps(dump))
    moved["tracks"]["video"][0]["items"].pop()
    assert stale(r, moved)
    print("qc selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("dump")
    c.add_argument("--expect-width", type=int)
    c.add_argument("--expect-height", type=int)
    c.add_argument("--expect-fps", type=float)
    c.add_argument("--sliver", type=int, default=3)
    c.add_argument("--out", required=True)
    ad = sub.add_parser("add")
    ad.add_argument("qc")
    ad.add_argument("--severity", required=True)
    ad.add_argument("--kind", required=True)
    ad.add_argument("--message", required=True)
    ad.add_argument("--tc")
    ad.add_argument("--track")
    st = sub.add_parser("stale")
    st.add_argument("qc")
    st.add_argument("dump")
    a = ap.parse_args()
    if a.cmd in ("add", "stale"):
        with open(a.qc, encoding="utf-8") as f:
            result = json.load(f)
        if a.cmd == "stale":
            with open(a.dump, encoding="utf-8") as f:
                is_stale = stale(result, json.load(f))
            print(json.dumps({"stale": is_stale, "verdict": result.get("verdict")}))
            sys.exit(1 if is_stale else 0)
        result = add(result, a.severity, a.kind, a.message, a.tc, a.track)
        with open(a.qc, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        return print(json.dumps({"verdict": result["verdict"], "counts": result["counts"]}))
    with open(a.dump, encoding="utf-8") as f:
        dump = json.load(f)
    result = check(dump, {"width": a.expect_width, "height": a.expect_height, "fps": a.expect_fps}, a.sliver)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(json.dumps({"out": a.out, "verdict": result["verdict"], "counts": result["counts"],
                      "errors": [f"{x['tc']} {x['message']}" for x in result["findings"] if x["severity"] == "error"]},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
