"""Learn from the user's edits: compare handoff snapshots, keep an event log, turn repeated edits into approved rules.

python3 memory.py changed <old snapshot.json> <new snapshot.json>      (exit 1 = the timeline changed)
python3 memory.py diff <old snapshot.json> <new snapshot.json> [--ledger placed.json] --out events.json
python3 memory.py log events.json --project P --timeline T [--date YYYY-MM-DD] [--memory edit-memory.json]
python3 memory.py lessons|show [--memory edit-memory.json]
python3 memory.py approve --candidate '<json or file>' --text T [--param name=value] [--format F] [--memory ...]
python3 memory.py reject <event id>... | forget <rule id> | confirm <rule id> [--memory ...]
python3 memory.py rules [--skill S] [--format F] [--memory ...]            (JSON list; frame-critic reads it via --rules)
python3 memory.py selftest

--memory is the rules file; the event log edit-memory-events.jsonl sits in the same folder.

Snapshots: resolve-core/reference.md "Handoff snapshot". Frames are absolute timeline frames.
"""
import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import statistics
from copy import deepcopy
from datetime import date as today

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


EVENTS_NAME = "edit-memory-events.jsonl"
SAME_CUT_FRAMES = 2


def events_path_for(memory_path):
    return os.path.join(os.path.dirname(os.path.abspath(memory_path)), EVENTS_NAME)


def write_atomic(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def read_rules(memory_path):
    if not os.path.exists(memory_path):
        return {"version": 1, "rules": []}
    with open(memory_path, encoding="utf-8") as f:
        return json.load(f)


def write_rules(memory_path, memory):
    write_atomic(memory_path, json.dumps(memory, ensure_ascii=False, indent=1) + "\n")


def read_events(events_path):
    if not os.path.exists(events_path):
        return []
    with open(events_path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_events(events_path, events):
    write_atomic(events_path, "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events))


def log_events(events_path, events, project, timeline, date):
    stored = read_events(events_path)
    batch = f"{date}-{len(stored) + 1}"
    new = [{**e, "id": f"{date}-{len(stored) + i + 1}", "batch": batch, "project": project, "timeline": timeline, "date": date}
           for i, e in enumerate(events)]
    if new:
        write_events(events_path, stored + new)
    return len(new)


def direction(event):
    value = event.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value == 0:
        return "none"
    return "+" if value > 0 else "-"


def group_of(event):
    return event["owner"], event["kind"], event["type"], event.get("property")


def counted(events):
    """One edit, one event: a head drag also logs `moved` next to `retimed`, a synced cut logs `cut_changed` per track."""
    retimed = {(e.get("batch"), e["item_id"]) for e in events if e["type"] == "retimed"}
    kept, cuts = [], {}
    for e in events:
        if e["type"] == "moved" and (e.get("batch"), e["item_id"]) in retimed:
            continue
        if e["type"] == "cut_changed":
            frames = cuts.setdefault(e.get("batch"), [])
            if any(abs(e["frame"] - f) <= SAME_CUT_FRAMES for f in frames):
                continue
            frames.append(e["frame"])
        kept.append(e)
    return kept


def rule_directions(rules, events):
    """{(rule id, group): direction} read off the events each approved rule consumed."""
    live = {r["id"] for r in rules}
    values = {}
    for e in events:
        if e.get("rule_id") in live and direction(e) != "none":
            values.setdefault((e["rule_id"], group_of(e)), []).append(e["value"])
    return {key: "+" if statistics.median(v) > 0 else "-" for key, v in values.items()}


def lessons(events_path, rules):
    # shortcut: share is among the logged events of the group, not among all placed elements of that kind
    events = read_events(events_path)
    taught = rule_directions(rules.get("rules", []), events)
    open_events = [e for e in counted(events) if e["owner"] != "user" and e.get("rule_id") is None and not e.get("rejected")]
    totals = {}
    for e in open_events:
        totals[group_of(e)] = totals.get(group_of(e), 0) + 1
    sides = {}
    for e in open_events:
        sides.setdefault((group_of(e), direction(e)), []).append(e)
    found = []
    for (group, side), members in sides.items():
        values = [e["value"] for e in members if side != "none"]
        opposite = {"+": "-", "-": "+"}.get(side)
        conflicts = sorted(rid for (rid, g), d in taught.items() if g == group and d == opposite)
        found.append({"group": list(group[:3]), "property": group[3], "count": len(members),
                      "share": round(len(members) / totals[group], 2),
                      "median": round(statistics.median(values), 4) if values else None, "direction": side,
                      "events": [e["id"] for e in members], "conflicts_with": conflicts[0] if conflicts else None,
                      "one_off": len(members) < 2})
    return sorted(found, key=lambda c: (c["one_off"], -c["count"], c["group"]))


def approve(memory_path, events_path, candidate, text, param=None, fmt=None):
    memory, events = read_rules(memory_path), read_events(events_path)
    chosen = [e for e in events if e["id"] in set(candidate["events"])]
    if len(chosen) != len(candidate["events"]) or any(e.get("rule_id") is not None or e.get("rejected") for e in chosen):
        raise ValueError("candidate is stale: its events are missing or already used")
    owner, kind, _ = candidate["group"]
    evidence = {}
    for e in chosen:
        evidence.setdefault((e["project"], e["timeline"], e["date"]), []).append(e["tc"])
    rule_id = 1 + max([r["id"] for r in memory["rules"]] + [e["rule_id"] for e in events if e.get("rule_id") is not None], default=0)
    rule = {"id": rule_id, "text": text, "scope": {"skill": owner, "kind": kind, **({"format": fmt} if fmt else {})},
            "param": param, "evidence": [{"project": p, "timeline": t, "tcs": tcs, "date": d} for (p, t, d), tcs in evidence.items()],
            "confirmed": 1, "created": today.today().isoformat()}
    write_rules(memory_path, {**memory, "rules": memory["rules"] + [rule]})
    used = {e["id"] for e in chosen}
    write_events(events_path, [{**e, "rule_id": rule_id} if e["id"] in used else e for e in events])
    return rule


def reject(events_path, event_ids):
    events, ids = read_events(events_path), set(event_ids)
    if ids - {e["id"] for e in events}:
        raise ValueError(f"unknown events: {sorted(ids - {e['id'] for e in events})}")
    write_events(events_path, [{**e, "rejected": True} if e["id"] in ids else e for e in events])
    return len(ids)


def find_rule(memory, rule_id):
    rule = next((r for r in memory["rules"] if r["id"] == rule_id), None)
    if rule is None:
        raise ValueError(f"no rule {rule_id}")
    return rule


def forget(memory_path, rule_id):
    memory = read_rules(memory_path)
    find_rule(memory, rule_id)
    write_rules(memory_path, {**memory, "rules": [r for r in memory["rules"] if r["id"] != rule_id]})


def confirm(memory_path, rule_id):
    memory = read_rules(memory_path)
    rule = find_rule(memory, rule_id)
    rule["confirmed"] += 1
    write_rules(memory_path, memory)
    return rule


def rules(memory_path, skill=None, fmt=None):
    return [r for r in read_rules(memory_path)["rules"]
            if (skill is None or r["scope"].get("skill") == skill)
            and (fmt is None or r["scope"].get("format") in (None, fmt))]


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
    selftest_memory()
    print("memory selftest ok")


def selftest_memory():
    def ev(kind, value, owner="fusion-motion-graphics", type_="retimed", item="t1", frame=90250, **extra):
        return {"type": type_, "owner": owner, "kind": kind, "item_id": item, "track": "Titles", "tc": "01:00:10:00",
                "frame": frame, "value": value, **extra}

    with tempfile.TemporaryDirectory() as tmp:
        mem = os.path.join(tmp, "edit-memory.json")
        log = events_path_for(mem)
        assert os.path.basename(log) == "edit-memory-events.jsonl" and os.path.dirname(log) == tmp
        assert rules(mem) == [] and lessons(log, read_rules(mem)) == []

        assert log_events(log, [ev("lower-third", 26)], "Ep1", "main", "2026-11-01") == 1
        assert log_events(log, [ev("lower-third", 24, item="t9")], "Ep2", "main", "2026-11-05") == 1
        found = lessons(log, read_rules(mem))
        assert len(found) == 1, found
        cand = found[0]
        assert cand["group"] == ["fusion-motion-graphics", "lower-third", "retimed"] and cand["count"] == 2
        assert cand["median"] == 25 and cand["direction"] == "+" and cand["share"] == 1.0
        assert cand["conflicts_with"] is None and not cand["one_off"] and len(set(cand["events"])) == 2

        rule = approve(mem, log, cand, "Hold lower-thirds 1 s longer", {"name": "hold_extra_s", "value": 1.0}, fmt="youtube")
        assert rule["id"] == 1 and rule["confirmed"] == 1 and rule["text"] == "Hold lower-thirds 1 s longer"
        assert rule["scope"] == {"skill": "fusion-motion-graphics", "kind": "lower-third", "format": "youtube"}
        assert rule["param"] == {"name": "hold_extra_s", "value": 1.0}
        assert sorted((x["project"], x["timeline"], x["date"], tuple(x["tcs"])) for x in rule["evidence"]) == [
            ("Ep1", "main", "2026-11-01", ("01:00:10:00",)), ("Ep2", "main", "2026-11-05", ("01:00:10:00",))]
        assert lessons(log, read_rules(mem)) == []
        assert [r["id"] for r in rules(mem)] == [1] and not [f for f in os.listdir(tmp) if f.endswith(".tmp")]

        log_events(log, [ev("lower-third", -10), ev("lower-third", -14, item="t2")], "Ep3", "main", "2026-11-08")
        opposite = lessons(log, read_rules(mem))
        assert len(opposite) == 1 and opposite[0]["direction"] == "-" and opposite[0]["conflicts_with"] == 1, opposite
        assert reject(log, opposite[0]["events"]) == 2
        assert lessons(log, read_rules(mem)) == []
        assert all(e.get("rejected") for e in read_events(log)[-2:])

        assert confirm(mem, 1)["confirmed"] == 2 and rules(mem)[0]["confirmed"] == 2
        approve(mem, log, {"group": ["tutorial-zooms", "zoom", "property_changed"], "events": []}, "Zoom less", None)
        assert rules(mem, skill="tutorial-zooms")[0]["param"] is None
        assert [r["id"] for r in rules(mem, skill="fusion-motion-graphics", fmt="youtube")] == [1]
        assert rules(mem, skill="fusion-motion-graphics", fmt="shorts") == []
        assert [r["id"] for r in rules(mem, fmt="shorts")] == [2] and [r["id"] for r in rules(mem)] == [1, 2]
        forget(mem, 1)
        assert [r["id"] for r in rules(mem)] == [2]
        again = approve(mem, log, {"group": ["x", "y", "deleted"], "events": []}, "Next", None)
        assert again["id"] == 3
        try:
            forget(mem, 1)
        except ValueError:
            pass
        else:
            raise AssertionError("forgetting an unknown rule must fail")

    with tempfile.TemporaryDirectory() as tmp:
        mem = os.path.join(tmp, "m.json")
        log = events_path_for(mem)
        log_events(log, [ev("lower-third", 24), ev("lower-third", -20, item="t2")], "Ep1", "main", "2026-11-01")
        found = lessons(log, read_rules(mem))
        assert len(found) == 2 and all(f["one_off"] and f["count"] == 1 for f in found), found
        assert {f["direction"] for f in found} == {"+", "-"} and {f["share"] for f in found} == {0.5}

        log_events(log, [ev("lower-third", 20, type_="moved"), ev("lower-third", 20), ev("lower-third", 20, item="t3", type_="moved")],
                   "Ep2", "main", "2026-11-02")
        by_type = {}
        for f in lessons(log, read_rules(mem)):
            by_type.setdefault(f["group"][2], []).append(f)
        retimed_up = next(f for f in by_type["retimed"] if f["direction"] == "+")
        moved_up = next(f for f in by_type["moved"] if f["direction"] == "+")
        assert retimed_up["count"] == 2 and moved_up["count"] == 1, (retimed_up, moved_up)

    with tempfile.TemporaryDirectory() as tmp:
        mem = os.path.join(tmp, "m.json")
        log = events_path_for(mem)
        cuts = [ev(None, -48, owner="a-roll-cutter", type_="cut_changed", item="a1", frame=90000),
                ev(None, -48, owner="a-roll-cutter", type_="cut_changed", item="s1", frame=90001)]
        log_events(log, cuts, "Ep1", "main", "2026-11-01")
        log_events(log, [ev(None, -48, owner="a-roll-cutter", type_="cut_changed", item="a1", frame=90000)], "Ep2", "main", "2026-11-02")
        found = lessons(log, read_rules(mem))
        assert len(found) == 1 and found[0]["count"] == 2 and not found[0]["one_off"], found

        log_events(log, [ev("zoom", -0.3, owner="tutorial-zooms", type_="property_changed", property="ZoomX"),
                         ev("zoom", 5.0, owner="tutorial-zooms", type_="property_changed", property="Opacity"),
                         ev(None, 9, owner="user", type_="retimed"), ev(None, 9, owner="user", type_="retimed", item="u2"),
                         ev("lower-third", None, type_="deleted"), ev("lower-third", None, type_="deleted", item="t2"),
                         ev("lower-third", "Hi", type_="text_changed", item="t5")],
                   "Ep3", "main", "2026-11-03")
        found = lessons(log, read_rules(mem))
        assert not [f for f in found if f["group"][0] == "user"]
        deleted = next(f for f in found if f["group"][2] == "deleted")
        assert deleted["count"] == 2 and deleted["direction"] == "none" and deleted["median"] is None and not deleted["one_off"]
        props = sorted((f["property"], f["one_off"]) for f in found if f["group"][2] == "property_changed")
        assert props == [("Opacity", True), ("ZoomX", True)], props
        assert next(f for f in found if f["group"][2] == "text_changed")["one_off"]

        count = log_events(log, [ev("lower-third", 26)], "Ep4", "main", "2026-11-04")
        assert count == 1
        ids = [e["id"] for e in read_events(log)]
        assert len(ids) == len(set(ids))

        main_out = io.StringIO()
        with contextlib.redirect_stdout(main_out):
            main(["rules", "--memory", mem])
            main(["lessons", "--memory", mem])
        first, second = main_out.getvalue().splitlines()
        assert json.loads(first) == [] and isinstance(json.loads(second), list)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    def memory_arg(p):
        p.add_argument("--memory", default="edit-memory.json")
        return p

    ch = sub.add_parser("changed")
    ch.add_argument("old")
    ch.add_argument("new")
    df = sub.add_parser("diff")
    df.add_argument("old")
    df.add_argument("new")
    df.add_argument("--ledger")
    df.add_argument("--out", required=True)
    lg = memory_arg(sub.add_parser("log"))
    lg.add_argument("events", help="events.json written by diff")
    lg.add_argument("--project", required=True)
    lg.add_argument("--timeline", required=True)
    lg.add_argument("--date", default=today.today().isoformat())
    memory_arg(sub.add_parser("lessons"))
    memory_arg(sub.add_parser("show"))
    ap_ = memory_arg(sub.add_parser("approve"))
    ap_.add_argument("--candidate", required=True, help="a candidate from `lessons`: JSON text or a JSON file")
    ap_.add_argument("--text", required=True)
    ap_.add_argument("--param", help="name=value, value as JSON")
    ap_.add_argument("--format")
    rj = memory_arg(sub.add_parser("reject"))
    rj.add_argument("ids", nargs="+")
    fg = memory_arg(sub.add_parser("forget"))
    fg.add_argument("id", type=int)
    cf = memory_arg(sub.add_parser("confirm"))
    cf.add_argument("id", type=int)
    rl = memory_arg(sub.add_parser("rules"))
    rl.add_argument("--skill")
    rl.add_argument("--format")
    a = ap.parse_args(argv)

    def read(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def out(value):
        print(json.dumps(value, ensure_ascii=False))

    if a.cmd in ("changed", "diff"):
        old, new = read(a.old), read(a.new)
        if a.cmd == "changed":
            result = changed(old, new)
            out({"changed": result})
            return 1 if result else 0
        events = diff(old, new, read(a.ledger) if a.ledger and os.path.exists(a.ledger) else {"items": []})
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=1)
        return out({"out": a.out, "events": len(events), "shift": ripple_shift(old, new)})

    log = events_path_for(a.memory)
    try:
        if a.cmd == "log":
            out({"logged": log_events(log, read(a.events), a.project, a.timeline, a.date)})
        elif a.cmd == "lessons":
            out(lessons(log, read_rules(a.memory)))
        elif a.cmd == "show":
            out({"rules": rules(a.memory), "lessons": lessons(log, read_rules(a.memory))})
        elif a.cmd == "approve":
            candidate = json.loads(a.candidate) if a.candidate.lstrip().startswith("{") else read(a.candidate)
            param = None
            if a.param:
                name, _, value = a.param.partition("=")
                param = {"name": name, "value": json.loads(value)}
            out(approve(a.memory, log, candidate, a.text, param, a.format))
        elif a.cmd == "reject":
            out({"rejected": reject(log, a.ids)})
        elif a.cmd == "forget":
            forget(a.memory, a.id)
            out({"forgotten": a.id})
        elif a.cmd == "confirm":
            out(confirm(a.memory, a.id))
        else:
            out(rules(a.memory, a.skill, a.format))
    except ValueError as err:
        print(err, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
