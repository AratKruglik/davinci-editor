"""Compare a handoff snapshot with the timeline after the user's edits (no Resolve needed).

python3 memory.py changed <old snapshot.json> <new snapshot.json>      (exit 1 = the timeline changed)
python3 memory.py diff <old snapshot.json> <new snapshot.json> [--ledger placed.json] --out events.json
python3 memory.py selftest

Snapshots: resolve-core/reference.md "Handoff snapshot". Frames are absolute timeline frames.
"""
import argparse
import json
import os
import sys
from copy import deepcopy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "resolve-core", "scripts"))
from tc import frames_to_tc


CUT_ROLES = ("a-roll", "screen")
PROPS = ("ZoomX", "ZoomY", "Pan", "Tilt", "Opacity")
KEYS = ("item_id", "clip_id", "name", "start", "end", "source_start", "source_end", "enabled", "props", "fades", "fusion")


def role(track_name):
    return track_name.strip().lower().rstrip(" 0123456789")


def rows(snap):
    return [{**it, "_kind": kind, "_index": t["index"], "_track": t["name"], "_role": role(t["name"])}
            for kind, tracks in snap["tracks"].items() for t in tracks for it in t["items"]]


def user_markers(snap):
    return {f: m for f, m in snap.get("markers", {}).items() if not str(m.get("customData") or "").startswith("claude:")}


def changed(old, new):
    olds, news = rows(old), rows(new)
    keys = [k for k in KEYS if any(k in r for r in olds) and any(k in r for r in news)]

    def view(snap_rows, snap):
        return user_markers(snap), [(r["_kind"], r["_index"], r["_track"], [r.get(k) for k in keys]) for r in snap_rows]
    return view(olds, old) != view(news, new)


def same_source(a, b):
    """Resolve's source_end is exclusive for partial items but not for whole clips, so ranges come from lengths."""
    return a.get("clip_id") is not None and a.get("clip_id") == b.get("clip_id") and \
        a["source_start"] < b["source_start"] + length(b) and b["source_start"] < a["source_start"] + length(a)


def shift_at(shifts, frame):
    return next((s for f, s in reversed(shifts) if f <= frame), 0)


def length(item):
    return item["end"] - item["start"]


def match(old, new):
    """Old row index -> new row indices (the first is the item itself, the rest are blade pieces of it)."""
    olds, news = rows(old), rows(new)
    pairs, used = {}, set()

    def take(i, j):
        pairs.setdefault(i, []).append(j)
        used.add(j)

    def nearest(i, fits, shifts):
        o = olds[i]
        want = o["start"] + shift_at(shifts, o["start"])
        free = [j for j, n in enumerate(news) if j not in used and n["_role"] == o["_role"] and fits(o, n)]
        return min(free, key=lambda j: abs(news[j]["start"] - want), default=None)

    by_id = {n["item_id"]: j for j, n in enumerate(news) if n.get("item_id")}
    for i, o in enumerate(olds):
        if by_id.get(o.get("item_id")) is not None:
            take(i, by_id[o["item_id"]])
    for i in range(len(olds)):
        if i not in pairs and (j := nearest(i, same_source, [])) is not None:
            take(i, j)
    for j, n in enumerate(news):
        owner = next((i for i, js in pairs.items() if olds[i]["_role"] == n["_role"] and same_source(olds[i], n)
                      and not any(same_source(news[k], n) for k in js)), None) if j not in used else None
        if owner is not None:
            take(owner, j)

    # shortcut: offsets of blade pieces inside a speed-changed item are read as timeline frames
    spans = []
    for i, o in enumerate(olds):
        if o["_role"] in CUT_ROLES:
            for p in (news[j] for j in pairs.get(i, [])):
                lo = o["start"] + p["source_start"] - o["source_start"]
                spans.append((lo, lo + length(p), p["start"] - lo))
    # an old frame takes the observed shift of the cut-track piece over it, or of the next piece after a gap;
    # where A-roll and Screen overlap, the first one wins so a synced cut counts once
    shifts, covered = [], None
    for lo, hi, shift in sorted(spans):
        if covered is None or hi > covered:
            frame = min([lo] + [r["start"] for r in olds]) if covered is None else covered
            if shift != (shifts[-1][1] if shifts else 0):
                shifts.append((frame, shift))
            covered = hi if covered is None else max(covered, hi)

    def same_text(o, n):
        return o.get("fusion") is not None and n.get("fusion") is not None and o["fusion"].get("text") == n["fusion"].get("text")
    for i in range(len(olds)):
        if i not in pairs and (j := nearest(i, same_text, shifts)) is not None:
            take(i, j)
    return olds, news, pairs, used, shifts


def ripple_shift(old, new):
    return match(old, new)[4]


def numbers(item):
    fusion = item.get("fusion") or {}
    center = fusion.get("center") or [None, None]
    return {**{k: (item.get("props") or {}).get(k) for k in PROPS + ("AudioVolume",)},
            **{k: (item.get("fades") or {}).get(k) for k in ("FadeIn", "FadeOut")},
            "Center.x": center[0], "Center.y": center[1], "Size": fusion.get("size")}


def diff(old, new, ledger):
    olds, news, pairs, used, shifts = match(old, new)
    owners = {}
    for entry in (ledger or {}).get("items", []):
        owners.setdefault(entry["item_id"], entry)
    cut_clips = {o.get("clip_id") for o in olds if o["_role"] in CUT_ROLES} - {None}
    events = []

    def emit(kind, item, item_id, value, **extra):
        entry = owners.get(item_id)
        events.append({"type": kind, "owner": entry["owner"] if entry else "user", "kind": entry["kind"] if entry else None,
                       "item_id": item_id, "track": item["_track"], "tc": frames_to_tc(item["start"], new["fps"], new.get("drop_frame", False)),
                       "frame": item["start"], "value": value, **extra})

    for i, o in enumerate(olds):
        if i not in pairs:
            if o["_role"] in CUT_ROLES:
                emit("cut_changed", o, o.get("item_id"), -length(o))
            elif o["_kind"] != "audio" or o.get("clip_id") not in cut_clips:
                emit("deleted", o, o.get("item_id"), None)
            continue
        n = news[pairs[i][0]]
        item_id = o.get("item_id") or n.get("item_id")
        delta = sum(length(news[j]) for j in pairs[i]) - length(o)
        if o["_role"] in CUT_ROLES:
            if delta:
                emit("cut_changed", n, item_id, delta)
        else:
            # a head trim moves the start but not the content: measure where the new first frame sat in the old timeline
            was = o["start"] + (n["source_start"] - o["source_start"] if o.get("clip_id") is not None else 0)
            off = n["start"] - (was + shift_at(shifts, was))
            if abs(off) > 1:
                emit("moved", n, item_id, off)
            # audio linked to a cut clip gets trimmed with it; that is the cut, not a retime
            if delta and (o["_kind"] != "audio" or o.get("clip_id") not in cut_clips):
                emit("retimed", n, item_id, delta)
        if o["_track"] != n["_track"]:
            emit("track_changed", n, item_id, n["_track"])
        if o.get("fusion") and n.get("fusion") and o["fusion"].get("text") != n["fusion"].get("text"):
            emit("text_changed", n, item_id, n["fusion"].get("text"))
        was, now = numbers(o), numbers(n)
        for k in was:
            if isinstance(was[k], (int, float)) and isinstance(now[k], (int, float)) and was[k] != now[k]:
                value = round(now[k] - was[k], 4)
                if k == "AudioVolume":
                    emit("volume_changed", n, item_id, value)
                else:
                    emit("property_changed", n, item_id, value, property=k)
    for j, n in enumerate(news):
        if j not in used and n.get("item_id") not in owners:
            emit("added_by_user", n, n.get("item_id"), None)
    return sorted(events, key=lambda e: (e["frame"], e["type"]))


def selftest():
    def item(name, clip_id, start, end, src=0, fusion=None, **props):
        return {"name": name, "item_id": name, "clip_id": clip_id, "start": start, "end": end,
                "source_start": src, "source_end": src + end - start - 1, "enabled": True,
                "props": {"ZoomX": 1.0, "ZoomY": 1.0, "Pan": 0.0, "Tilt": 0.0, "Opacity": 100.0, "AudioVolume": 0.0, **props},
                "fades": {"FadeIn": 0, "FadeOut": 0}, "fusion": fusion}

    def title(name, start, text):
        return item(name, None, start, start + 50, fusion={"text": text, "center": [0.5, 0.2], "size": 0.08})

    base = {"name": "ep", "timeline_id": "tl", "fps": 25.0, "drop_frame": False, "start_frame": 90000,
            "markers": {"40": {"color": "Blue", "name": "", "note": "", "customData": ""}},
            "tracks": {"video": [
                {"index": 1, "name": "A-roll", "items": [item("a1", "c1", 90000, 90200), item("a2", "c1", 90200, 90400, 500),
                                                         item("a3", "c2", 90400, 90600)]},
                {"index": 2, "name": "B-roll", "items": [item("b1", "c3", 90020, 90060, ZoomX=1.6)]},
                {"index": 3, "name": "Titles", "items": [title("t1", 90250, "Один"), title("t2", 90350, "Два"),
                                                         title("t3", 90450, "Три")]},
                {"index": 4, "name": "Titles 2", "items": []}],
                "audio": [{"index": 1, "name": "Voice", "items": [item("v1", "c1", 90000, 90200), item("v2", "c1", 90200, 90400, 500),
                                                                  item("v3", "c2", 90400, 90600)]}],
                "subtitle": []}}
    ledger = {"timeline_id": "tl", "items": [
        {"item_id": t, "owner": "fusion-motion-graphics", "kind": "lower-third", "part": None} for t in ("t1", "t2", "t3")] + [
        {"item_id": "b1", "owner": "tutorial-zooms", "kind": "zoom", "part": "0"},
        {"item_id": "b1", "owner": "tutorial-zooms", "kind": "callout", "part": "1"}]}

    def tracks(snap, kind="video"):
        return {t["name"]: t["items"] for t in snap["tracks"][kind]}

    def cut48():
        new = deepcopy(base)
        for kind, first in (("video", "A-roll"), ("audio", "Voice")):
            items = tracks(new, kind)[first]
            head = items[0]
            tail = {**deepcopy(head), "item_id": head["item_id"] + "-2", "start": 90080, "end": 90152,
                    "source_start": 128, "source_end": 199}
            head.update(end=90080, source_end=79)
            for it in items[1:]:
                it["start"] -= 48
                it["end"] -= 48
            items.insert(1, tail)
        for t in tracks(new)["Titles"]:
            t["start"] -= 48
            t["end"] -= 48
        return new

    def kinds(events):
        return sorted((e["type"], e["item_id"]) for e in events)

    new = cut48()
    assert ripple_shift(base, new) == [(90080, -48)]
    events = diff(base, new, ledger)
    assert kinds(events) == [("cut_changed", "a1")], events
    over_a1, over_cut = deepcopy(base), deepcopy(new)
    tracks(over_a1)["Titles"].append(title("t0", 90140, "Нуль"))
    tracks(over_cut)["Titles"].append(title("t0", 90092, "Нуль"))
    assert kinds(diff(over_a1, over_cut, ledger)) == [("cut_changed", "a1")]
    head = deepcopy(base)
    tracks(head)["B-roll"].clear()
    for first in (tracks(head)["A-roll"], tracks(head, "audio")["Voice"]):
        first[0].update(end=90152, source_start=48)
        for it in first[1:]:
            it.update(start=it["start"] - 48, end=it["end"] - 48)
    for it in tracks(head)["Titles"]:
        it.update(start=it["start"] - 48, end=it["end"] - 48)
    assert ripple_shift(base, head) == [(90000, -48)]
    assert kinds(diff(base, head, ledger)) == [("cut_changed", "a1"), ("deleted", "b1")]
    gap = deepcopy(base)
    tracks(gap)["A-roll"][1].update(start=90248, source_start=548)
    assert ripple_shift(base, gap) == [] and kinds(diff(base, gap, ledger)) == [("cut_changed", "a2")]
    inserted = deepcopy(base)
    for it in tracks(inserted)["A-roll"][1:] + tracks(inserted, "audio")["Voice"][1:] + tracks(inserted)["Titles"]:
        it.update(start=it["start"] + 100, end=it["end"] + 100)
    tracks(inserted)["A-roll"].insert(1, item("new", "c9", 90200, 90300))
    assert ripple_shift(base, inserted) == [(90200, 100)]
    assert kinds(diff(base, inserted, ledger)) == [("added_by_user", "new")]
    bladed = deepcopy(base)
    for it in (it for t in bladed["tracks"].values() for tr in t for it in tr["items"]):
        it["source_end"] += 1
    whole = deepcopy(bladed)
    a1 = tracks(bladed)["A-roll"][0]
    tracks(bladed)["A-roll"].insert(1, {**deepcopy(a1), "item_id": "a1b", "start": 90100, "source_start": 100})
    a1.update(end=90100, source_end=100)
    assert ripple_shift(whole, bladed) == [] and diff(whole, bladed, ledger) == []
    screen = deepcopy(base)
    screen["tracks"]["video"].insert(1, {"index": 2, "name": "Screen", "items": [item("s1", "c5", 90000, 90600)]})
    for i, t in enumerate(screen["tracks"]["video"]):
        t["index"] = i + 1
    synced = deepcopy(screen)
    for first in (tracks(synced)["A-roll"], tracks(synced, "audio")["Voice"]):
        first[0].update(end=90180, source_end=179)
        first[1].update(start=90180, end=90360, source_start=520)
        first[2].update(start=90360, end=90560)
    s1 = tracks(synced)["Screen"][0]
    tracks(synced)["Screen"].append({**deepcopy(s1), "item_id": "s1b", "start": 90180, "end": 90560, "source_start": 220})
    s1.update(end=90180, source_end=179)
    for it in tracks(synced)["Titles"]:
        it.update(start=it["start"] - 40, end=it["end"] - 40)
    assert ripple_shift(screen, synced) == [(90180, -40)]
    assert {e["type"] for e in diff(screen, synced, ledger)} == {"cut_changed"}
    assert kinds(diff(base, screen, ledger)) == [("added_by_user", "s1")]
    shifted = deepcopy(base)
    shifted["tracks"]["video"].insert(0, {"index": 1, "name": "Backgrounds", "items": []})
    for i, t in enumerate(shifted["tracks"]["video"]):
        t["index"] = i + 1
    assert diff(base, shifted, ledger) == []
    trimmed = deepcopy(base)
    tracks(trimmed)["B-roll"][0].update(start=90030, source_start=10)
    assert kinds(diff(base, trimmed, ledger)) == [("retimed", "b1")]
    pip = deepcopy(base)
    pip["tracks"]["video"].append({"index": 5, "name": "PiP", "items": [item("p1", "c1", 90000, 90100)]})
    pip_cut = deepcopy(pip)
    tracks(pip_cut)["PiP"][0]["end"] = 90080
    assert kinds(diff(pip, pip_cut, ledger)) == [("retimed", "p1")]
    assert events[0]["value"] == -48 and events[0]["owner"] == "user" and events[0]["track"] == "A-roll"

    tracks(new)["Titles"][1]["start"] += 24
    tracks(new)["Titles"][1]["end"] += 24
    moved = [e for e in diff(base, new, ledger) if e["type"] == "moved"]
    assert len(moved) == 1 and moved[0]["item_id"] == "t2" and moved[0]["value"] == 24, moved
    assert moved[0]["owner"] == "fusion-motion-graphics" and moved[0]["kind"] == "lower-third"

    new = deepcopy(base)
    for kind, first in (("video", "A-roll"), ("audio", "Voice")):
        items = tracks(new, kind)[first]
        del items[1]
        items[1].update(start=90200, end=90400)
    for t in tracks(new)["Titles"]:
        t.update(start=t["start"] - 200, end=t["end"] - 200)
    assert ripple_shift(base, new) == [(90200, -200)]
    events = diff(base, new, ledger)
    assert kinds(events) == [("cut_changed", "a2")] and events[0]["value"] == -200, events

    dup = deepcopy(base)
    for t in dup["tracks"].values():
        for tr in t:
            for it in tr["items"]:
                it["item_id"] = "dup-" + it["item_id"]
    for t in tracks(dup)["Titles"]:
        del t["item_id"]
    assert diff(base, dup, ledger) == []
    assert ripple_shift(base, dup) == []

    pre_task2 = deepcopy(base)
    for t in pre_task2["tracks"].values():
        for tr in t:
            for it in tr["items"]:
                del it["item_id"]
    assert diff(pre_task2, base, ledger) == []
    assert kinds(diff(pre_task2, cut48(), ledger)) == [("cut_changed", "a1")]

    new = deepcopy(base)
    t1, t2, t3 = tracks(new)["Titles"]
    t1["fusion"]["text"] = "Один!"
    t1["end"] += 26
    tracks(new)["B-roll"][0]["props"]["ZoomX"] = 1.3
    tracks(new, "audio")["Voice"][2]["props"]["AudioVolume"] = -6.0
    tracks(new)["Titles"].remove(t3)
    tracks(new)["Titles"].remove(t2)
    tracks(new)["Titles 2"].append(t2)
    tracks(new)["Titles"].append({**title("t4", 90550, "Нове")})
    events = diff(base, new, ledger)
    assert kinds(events) == [("added_by_user", "t4"), ("deleted", "t3"), ("property_changed", "b1"), ("retimed", "t1"),
                             ("text_changed", "t1"), ("track_changed", "t2"), ("volume_changed", "v3")], kinds(events)
    by = {e["type"]: e for e in events}
    assert by["text_changed"]["value"] == "Один!" and by["text_changed"]["tc"] == "01:00:10:00"
    assert by["text_changed"]["frame"] == 90250 and by["text_changed"]["owner"] == "fusion-motion-graphics"
    assert by["property_changed"]["property"] == "ZoomX" and by["property_changed"]["value"] == -0.3
    assert by["property_changed"]["kind"] == "zoom" and by["retimed"]["value"] == 26
    assert by["volume_changed"]["value"] == -6.0 and by["track_changed"]["value"] == "Titles 2"
    assert by["deleted"]["owner"] == "fusion-motion-graphics" and by["deleted"]["frame"] == 90450
    assert by["added_by_user"]["owner"] == "user" and by["added_by_user"]["kind"] is None
    assert all(set(e) >= {"type", "owner", "kind", "item_id", "track", "tc", "frame", "value"} for e in events)

    marked = deepcopy(base)
    marked["markers"]["300"] = {"color": "Cream", "name": "offscreen", "note": "", "customData": "claude:critic:offscreen"}
    assert not changed(base, marked) and diff(base, marked, ledger) == []
    marked["markers"]["310"] = {"color": "Pink", "name": "", "note": "зум", "customData": ""}
    assert changed(base, marked)
    assert changed(base, cut48()) and not changed(base, deepcopy(base))
    assert not changed(pre_task2, base) and changed(pre_task2, cut48())
    print("memory selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ch = sub.add_parser("changed")
    ch.add_argument("old")
    ch.add_argument("new")
    df = sub.add_parser("diff")
    df.add_argument("old")
    df.add_argument("new")
    df.add_argument("--ledger")
    df.add_argument("--out", required=True)
    a = ap.parse_args()

    def read(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    old, new = read(a.old), read(a.new)
    if a.cmd == "changed":
        result = changed(old, new)
        print(json.dumps({"changed": result}))
        return 1 if result else 0
    events = diff(old, new, read(a.ledger) if a.ledger and os.path.exists(a.ledger) else {"items": []})
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=1)
    print(json.dumps({"out": a.out, "events": len(events), "shift": ripple_shift(old, new)}))


if __name__ == "__main__":
    sys.exit(main())
