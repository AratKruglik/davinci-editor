"""Plan J- and L-cuts (split edits) only where the picture source changes, and check every one before it is shown.

joins:    python3 split_edits.py joins (--dump <timeline dump> | --rough <plan.json> --frames <clip-frames.json>)
              --transcripts <dir> [--cuts cuts.json] [--source-offset N] [--colors "Red=cut,..."] [--previous split-plan.json]
              [--j-lead 12] [--l-tail 12] [--max 50] [--fade 4] [--max-in-row 3] [--handle-ms 150] --out split-plan.json
audio:    python3 split_edits.py audio split-plan.json --out split-audio.json
verify:   python3 split_edits.py verify <fresh dump> split-audio.json
sections: python3 split_edits.py sections <dump> <transcripts dir> <pip-input.json> [--source-offset N] [--j-lead 12] [--l-tail 12] [--max 50] --out <file>
ambience: python3 split_edits.py ambience <dump> [--j-lead 12] [--l-tail 12] [--fade 4]
python3 split_edits.py selftest

Frames are [start, end), end exclusive. Inside the script source frames are transcript frames (from the clip's Start TC);
in a dump they are API frames = transcript frames + --source-offset (the append calibration in resolve-core), and the
output goes back to the input's convention. --rough mode (text-based-cut, before the timeline exists) uses plan.json
frames as they are, record frames counted from 0. --frames maps clip_id -> media length in frames ("Frames" clip property).

J at a join: the next clip's sound starts n frames before its picture. L: the previous clip's sound runs n frames past
the picture change. Each proposal gets "decision": "review"; set it to "split" or "keep" (type and frames may be edited)
before `audio`, which checks the decided splits again and refuses while any "review" is left.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "resolve-core", "scripts"))
from tc import ms_to_frames
from timeline_map import find_track, load, source_words, usable, words_on_timeline

REQUEST = re.compile(r"^\s*(j|l|split)\s*(\d+)?\s*$", re.IGNORECASE)   # the whole note; "Light leak" stays a transition
SILENCE_CUTS = {"head", "tail", "pause"}   # room tone a J/L may bring back; every other cut is words that must stay gone


def parse_colors(value):
    pairs = (p.split("=", 1) for p in value.split(",") if "=" in p)
    return {task.strip(): color.strip() for color, task in pairs}


def overlaps(ranges, lo, hi):
    return any(s < hi and e > lo for s, e in ranges)


def load_transcripts(folder):
    words = {}
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json"):
            data = load(os.path.join(folder, name))
            if "transcription" in data:
                # a word's end timecode is its last frame (text-based-cut convention), so +1 keeps the whole word
                words[data["clip_id"]] = [[s, e + 1] for s, e, _, _ in source_words(data)]
    return words


def load_cuts(path):
    if not path:
        return {}
    data = load(path)
    ids = {c["clip_name"]: c["clip_id"] for c in data["clips"]}
    cuts = {}
    for c in data["candidates"]:
        if c["decision"] == "cut" and c["type"] not in SILENCE_CUTS:
            cuts.setdefault(ids[c["clip"]], []).append([c["start"], c["end"]])
    return cuts


def segment(item, offset, record=None):
    start = item["start"] if record is None else record
    return {"id": f'{item["name"]}@{start}', "clip_id": item["clip_id"], "clip_name": item["name"],
            "start": start, "end": start + item["end"] - item["start"],
            "src_start": item["source_start"] - offset, "src_end": item["source_start"] - offset + item["end"] - item["start"]}


def dump_segments(dump, offset, warnings):
    """A-roll items as segments; Voice items matched to each end by clip, position and sync."""
    segs = [dict(segment(it, offset), left=it.get("left_offset", it["source_start"]), right=it.get("right_offset"))
            for it in sorted(find_track(dump, "video", "A-roll")["items"], key=lambda i: i["start"])
            if usable(it, warnings, "A-roll")]
    voice = [segment(it, offset) for it in find_track(dump, "audio", "Voice")["items"]]
    for s in segs:
        synced = [v for v in voice if v["clip_id"] == s["clip_id"] and v["start"] - v["src_start"] == s["start"] - s["src_start"]]
        s["voice_left"] = next((v for v in synced if v["start"] == s["start"]), None)
        s["voice_right"] = next((v for v in synced if v["end"] == s["end"]), None)
    return segs


def rough_segments(plan, frames):
    segs, record = [], 0
    for p in plan:
        item = {"name": p["clip_name"], "clip_id": p["clip_id"], "start": 0, "end": p["end"] - p["start"], "source_start": p["start"]}
        s = segment(item, 0, record)
        media = frames.get(p["clip_id"])
        s.update(left=p["start"], right=None if media is None else media - p["end"])
        s["voice_left"] = s["voice_right"] = {k: s[k] for k in ("id", "clip_id", "clip_name", "start", "end", "src_start", "src_end")}
        segs.append(s)
        record = s["end"]
    return segs


def check(a, b, kind, n, ctx):
    """None if a `kind` split of n frames at the a|b join is safe, else the reason."""
    if a["clip_id"] == b["clip_id"]:
        return "same clip on both sides: a jump cut, the shifted sound would not match the mouth"
    if not 0 < n <= ctx["max"]:
        return f"shift {n} is outside 1..{ctx['max']} frames"
    if not (a["voice_right"] and b["voice_left"]):
        return "Voice at this join is not a plain cut under the picture (already split or edited by hand)"
    h = ctx["handle"]
    if kind == "J":
        ext, lo, hi, room = b, b["src_start"] - n, b["src_start"], b["left"]
        trim, tlo, thi = a, a["src_end"] - n - h, a["src_end"]
    else:
        ext, lo, hi, room = a, a["src_end"], a["src_end"] + n, a["right"]
        trim, tlo, thi = b, b["src_start"], b["src_start"] + n + h
    if room is None:
        return f"media length of {ext['clip_name']} unknown, the handle can't be checked"
    if room < n:
        return f"only {room} frames of media beyond {ext['clip_name']}, {n} needed"
    if overlaps(ctx["words"].get(ext["clip_id"], []), lo, hi):
        return f"{ext['clip_name']} has speech in the {n} frames that would become audible"
    if overlaps(ctx["cuts"].get(ext["clip_id"], []), lo, hi):
        return f"the extra sound of {ext['clip_name']} overlaps a cut from cuts.json"
    if overlaps(ctx["words"].get(trim["clip_id"], []), tlo, thi):
        return f"{trim['clip_name']} speaks within {n} frames + handle of the join: a silent mouth or a clipped word"
    return None


def join_key(a, b):
    return [a["clip_id"], a["src_end"], b["clip_id"], b["src_start"]]


def plan_joins(segs, ctx, markers=(), nearby=(), previous=()):
    """markers: [{frame (record), note, id}] split requests; nearby: record frames of transitions / zooms."""
    fps = ctx["fps"]
    joins = [(a, b) for a, b in zip(segs, segs[1:]) if a["end"] == b["start"]]
    decided = {json.dumps(p["key"]): p["decision"] for p in previous}
    requests, questions = {}, []
    for m in markers:
        kind, frames = REQUEST.match(m["note"]).groups()
        near = min(joins, key=lambda j: abs(j[0]["end"] - m["frame"]), default=None)
        if near is None or abs(near[0]["end"] - m["frame"]) > fps:
            questions.append(f'marker {m["id"]} ({m["note"]}) is more than 1 s from any A-roll join: where should it go?')
        else:
            requests[near[0]["end"]] = (kind.upper(), int(frames) if frames else None, m)
    proposals, rejected, done, run = [], [], [], 0
    for a, b in joins:
        join, key = a["end"], join_key(a, b)
        req = requests.get(join)
        if not req and decided.get(json.dumps(key)) in ("keep", "split"):
            done.append({"join": join, "decision": decided[json.dumps(key)]})
            run = 0
            continue
        if not req and a["clip_id"] == b["clip_id"]:
            run = 0
            continue
        close = [f for f in nearby if abs(f - join) <= fps and not (req and f == req[2]["frame"])]
        base = {"id": f"s{len(proposals) + len(rejected) + 1}", "join": join, "key": key, "a": a["id"], "b": b["id"],
                "origin": "marker" if req else "auto", "marker": req[2]["id"] if req else None}
        if close and not req:
            rejected.append(dict(base, reason=f"a transition or zoom within 1 s (frames {close}): two changes at once"))
            run = 0
            continue
        kinds = [req[0]] if req and req[0] != "SPLIT" else ["J", "L"]
        tried = []
        for kind in kinds:
            n = req[1] if req and req[1] else ctx["j_lead"] if kind == "J" else ctx["l_tail"]
            why = check(a, b, kind, n, ctx)
            if why is None:
                break
            tried.append(f"{kind} {n}: {why}")
        if why is not None:
            if req and len(kinds) == 1:
                alt = "L" if kinds[0] == "J" else "J"
                alt_n = ctx["l_tail"] if alt == "L" else ctx["j_lead"]
                alt_why = check(a, b, alt, alt_n, ctx)
                tried.append(f"{alt} {alt_n} would pass instead" if alt_why is None else f"{alt} {alt_n} fails too: {alt_why}")
            rejected.append(dict(base, reason="; ".join(tried)))
            run = 0
            continue
        run += 1
        if run > ctx["max_in_row"] and not req:
            rejected.append(dict(base, type=kind, frames=n, reason=f"more than {ctx['max_in_row']} split edits in a row"))
            run = 0
            continue
        reason = ("sound of the new clip leads its picture" if kind == "J" else "previous sound tails over the new picture")
        if tried:
            reason += f" (J not possible: {tried[0]})"
        warn = [f"a transition or zoom within 1 s (frames {close})"] if close else []
        proposals.append(dict(base, type=kind, frames=n, reason=reason, warnings=warn, decision="review"))
    return {"proposals": proposals, "rejected": rejected, "done": done, "questions": questions}


def audio_ranges(segs, splits, fade):
    """New source/record ranges of the Voice items touched by approved splits ({join: (type, frames)})."""
    out = {}
    for a, b in zip(segs, segs[1:]):
        if a["end"] not in splits or a["end"] != b["start"]:
            continue
        kind, n = splits[a["end"]]
        d = -n if kind == "J" else n
        for v, side in ((a["voice_right"], "right"), (b["voice_left"], "left")):
            row = out.setdefault(v["id"], {"item": v, "left": 0, "right": 0})
            row[side] = d
    rows = []
    for row in out.values():
        v = row["item"]
        rows.append({"voice_item": v["id"], "clip_id": v["clip_id"], "current": [v["start"], v["end"]],
                     "source_start": v["src_start"] + row["left"], "source_end": v["src_end"] + row["right"],
                     "record": v["start"] + row["left"], "fade_in": fade if row["left"] else 0,
                     "fade_out": fade if row["right"] else 0})
    for r in rows:
        if r["source_end"] <= r["source_start"]:
            raise SystemExit(f'{r["voice_item"]}: splits on both sides leave no audio')
    return sorted(rows, key=lambda r: r["record"])


def cmd_joins(a):
    ctx = {"j_lead": a.j_lead, "l_tail": a.l_tail, "max": a.max, "fade": a.fade, "max_in_row": a.max_in_row,
           "words": load_transcripts(a.transcripts), "cuts": load_cuts(a.cuts)}
    warnings, markers, nearby = [], [], []
    if a.dump:
        dump = load(a.dump)
        ctx["fps"], offset = dump["fps"], a.source_offset
        segs = dump_segments(dump, offset, warnings)
        colors = parse_colors(a.colors)
        for f, m in (dump.get("markers") or {}).items():
            frame = dump["start_frame"] + int(float(f))
            if m["color"] == colors.get("transition") and REQUEST.match(m.get("note") or ""):
                if (m.get("customData") or "").startswith("claude:done:split-edits"):
                    continue
                markers.append({"frame": frame, "note": m["note"], "id": f"{m['color']}@{frame}"})
            elif m["color"] in (colors.get("transition"), colors.get("zoom")):
                nearby.append(frame)
    else:
        offset = 0
        segs = rough_segments(load(a.rough), load(a.frames) if a.frames else {})
        fps = {c["fps"] for c in (load(a.cuts)["clips"] if a.cuts else [])}
        ctx["fps"] = fps.pop() if len(fps) == 1 else a.fps
    ctx["handle"] = ms_to_frames(a.handle_ms, ctx["fps"])
    previous = load(a.previous)["proposals"] if a.previous and os.path.exists(a.previous) else []
    result = plan_joins(segs, ctx, markers, nearby, previous)
    plan = {"mode": "dump" if a.dump else "rough", "source_offset": offset, "settings": {k: v for k, v in ctx.items() if k not in ("words", "cuts")},
            **result, "warnings": warnings, "segments": segs,
            "words": {s["clip_id"]: ctx["words"].get(s["clip_id"], []) for s in segs},
            "cuts": {s["clip_id"]: ctx["cuts"].get(s["clip_id"], []) for s in segs}}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    print(json.dumps({"proposals": [{k: p[k] for k in ("id", "join", "type", "frames", "origin", "reason", "warnings")} for p in result["proposals"]],
                      "rejected": [{k: r[k] for k in ("id", "join", "reason")} for r in result["rejected"]],
                      "questions": result["questions"], "warnings": warnings, "out": a.out}, ensure_ascii=False, indent=1))


def apply_plan(plan):
    pending = [p["id"] for p in plan["proposals"] if p["decision"] not in ("split", "keep")]
    if pending:
        raise SystemExit(f"undecided proposals (set decision to split or keep): {pending}")
    ctx = dict(plan["settings"], words=plan["words"], cuts=plan["cuts"])
    segs = {s["end"]: s for s in plan["segments"]}
    nexts = {s["start"]: s for s in plan["segments"]}
    splits = {}
    for p in plan["proposals"]:
        if p["decision"] == "split":
            why = check(segs[p["join"]], nexts[p["join"]], p["type"], p["frames"], ctx)
            if why:
                raise SystemExit(f'{p["id"]} ({p["type"]} {p["frames"]}) fails a hard check: {why}')
            splits[p["join"]] = (p["type"], p["frames"])
    rows = audio_ranges(plan["segments"], splits, ctx["fade"])
    off = plan["source_offset"]
    for r in rows:
        r["source_start"] += off
        r["source_end"] += off
    if plan["mode"] == "rough":
        # text-based-cut appends every segment's audio from this list, changed or not
        changed = {r["voice_item"]: r for r in rows}
        rows = [changed.get(s["id"]) or {"voice_item": s["id"], "clip_id": s["clip_id"], "current": [s["start"], s["end"]],
                                          "source_start": s["src_start"], "source_end": s["src_end"], "record": s["start"],
                                          "fade_in": 0, "fade_out": 0} for s in plan["segments"]]
    return {"mode": plan["mode"], "splits": [{"join": j, "type": t, "frames": n} for j, (t, n) in sorted(splits.items())], "audio": rows}


def verify(dump, expected, offset=0):
    """Problems after the build: every Voice item in sync with the A-roll item of its clip, relaid items where planned."""
    problems = []
    video = find_track(dump, "video", "A-roll")["items"]
    voice = find_track(dump, "audio", "Voice")["items"]
    for v in voice:
        pics = [p for p in video if p["clip_id"] == v["clip_id"] and p["start"] < v["end"] and p["end"] > v["start"]]
        for p in pics:
            if p["start"] - p["source_start"] != v["start"] - v["source_start"]:
                problems.append(f'Voice {v["name"]} @ {v["start"]} is {(v["start"] - v["source_start"]) - (p["start"] - p["source_start"])} frames out of sync with A-roll @ {p["start"]}')
    for r in expected["audio"]:
        hit = [v for v in voice if v["clip_id"] == r["clip_id"] and v["start"] == r["record"]
               and v["source_start"] == r["source_start"] and v["end"] - v["start"] == r["source_end"] - r["source_start"]]
        if not hit:
            problems.append(f'{r["voice_item"]}: no Voice item at {r["record"]} with source {r["source_start"]}-{r["source_end"]}')
    return problems


def shift_sections(sections, words, lead, tail, maxf):
    """Screen / PiP switches move into the phrase they fall in, so the picture follows the words: `tail` frames after
    its start into screen / PiP (L), `lead` frames back to camera (J: the voice returns first)."""
    ordered = sorted(sections, key=lambda s: s["start"])
    out, notes = [], []
    for i, sec in enumerate(ordered):
        prev_mode = ordered[i - 1]["mode"] if i else None
        nxt = ordered[i + 1]["start"] if i + 1 < len(ordered) else None
        word = next((w for w in words if w["end"] > sec["start"]), None)
        if prev_mode is None or prev_mode == sec["mode"] or word is None:
            out.append(sec)
            continue
        kind = "J" if sec["mode"] == "camera" else "L"
        new = max(sec["start"], word["start"]) + (lead if kind == "J" else tail)
        if new - sec["start"] > maxf or (nxt is not None and new >= nxt):
            notes.append(f'{sec["start"]} ({prev_mode} -> {sec["mode"]}): left as is, the phrase starts too late ({word["text"]!r} @ {word["start"]})')
            out.append(sec)
            continue
        notes.append(f'{sec["start"]} -> {new} ({kind}, {prev_mode} -> {sec["mode"]}): picture switches {new - word["start"]} frames into {word["text"]!r}')
        out.append(dict(sec, start=new, split=kind))
    return out, notes


def ambience(dump, lead, tail, fade):
    """Live sound of B-roll inserts: starts `lead` frames early (J), ends `tail` frames late (L), within the media and
    without overlapping the neighbour. B-roll -> Ambience, B-roll 2 -> Ambience 2."""
    rows = []
    for t in dump["tracks"]["video"]:
        m = re.fullmatch(r"b-roll( \d+)?", t["name"].strip().lower())
        if not m:
            continue
        mine, last_end = [], dump["start_frame"]
        for it in sorted(t["items"], key=lambda i: i["start"]):
            if not it.get("enabled", True):
                continue
            pre = max(0, min(lead, it.get("left_offset", it["source_start"]), it["start"] - last_end))
            if mine and mine[-1]["record_end"] > it["start"] - pre:
                cut = mine[-1]["record_end"] - (it["start"] - pre)
                mine[-1].update(tail=mine[-1]["tail"] - cut, source_end=mine[-1]["source_end"] - cut, record_end=mine[-1]["record_end"] - cut)
            post = min(tail, it["right_offset"]) if it.get("right_offset") is not None else 0
            mine.append({"track": "Ambience" + (m.group(1) or ""), "clip_id": it["clip_id"], "name": it["name"],
                         "record": it["start"] - pre, "record_end": it["end"] + post, "source_start": it["source_start"] - pre,
                         "source_end": it["source_start"] + it["end"] - it["start"] + post,
                         "lead": pre, "tail": post, "fade_in": fade, "fade_out": fade})
            last_end = it["end"]
        rows += mine
    return rows


def selftest():
    def item(name, cid, start, length, src, left=None, right=None):
        it = {"name": name, "clip_id": cid, "start": start, "end": start + length, "source_start": src, "source_end": src + length}
        if left is not None:
            it["left_offset"] = left
        if right is not None:
            it["right_offset"] = right
        return it

    ctx = {"fps": 25, "j_lead": 12, "l_tail": 12, "max": 50, "fade": 4, "max_in_row": 3, "handle": 4,
           "words": {"c1": [[10, 90], [200, 280], [300, 380]], "c2": [[40, 120]], "c3": [[0, 60]], "c4": [[60, 100]]},
           "cuts": {"c4": [[30, 55]]}}
    video = [item("IMG_1", "c1", 1000, 100, 0, right=500),      # 1000-1100, speech ends at src 90 -> 10 frames before its end
             item("IMG_1", "c1", 1100, 100, 190, right=300),    # jump cut c1|c1 at 1100
             item("IMG_2", "c2", 1200, 150, 20, left=20),       # c1|c2 at 1200: c2 has 20 silent frames before src 20
             item("IMG_3", "c3", 1350, 100, 0, left=0, right=10),  # c2|c3 at 1350: no media before c3
             item("IMG_4", "c4", 1450, 100, 60, left=60)]       # c3|c4 at 1450: c3 speaks till its end
    dump = {"fps": 25, "start_frame": 1000, "end_frame": 1550, "markers": {},
            "tracks": {"video": [{"name": "A-roll", "items": video}], "audio": [{"name": "Voice", "items": [dict(v) for v in video]}]}}
    segs = dump_segments(dump, 0, [])
    r = plan_joins(segs, ctx)
    by_join = {p["join"]: p for p in r["proposals"]}
    rej = {x["join"]: x["reason"] for x in r["rejected"]}
    assert not by_join and 1100 not in rej, r                     # a same-clip jump cut is never even a candidate
    # 1200: c1 speaks until src 280, 10 frames before its end; L would bring back c1's next words at src 300
    assert "J 12: IMG_1 speaks within" in rej[1200] and "L 12: IMG_1 has speech" in rej[1200], rej
    assert "only 0 frames of media beyond IMG_3" in rej[1350] and "media length of IMG_2 unknown" in rej[1350], rej
    assert "J 12: the extra sound of IMG_4 overlaps a cut" in rej[1450] and "L 12: only 10 frames" in rej[1450], rej

    # a clean source change: silence on both sides
    ctx2 = dict(ctx, words={"c1": [[10, 60]], "c2": [[40, 120]]}, cuts={})
    v2 = [item("IMG_1", "c1", 1000, 100, 0, right=500), item("IMG_2", "c2", 1100, 100, 20, left=20)]
    d2 = dict(dump, tracks={"video": [{"name": "A-roll", "items": v2}], "audio": [{"name": "Voice", "items": [dict(v) for v in v2]}]})
    s2 = dump_segments(d2, 0, [])
    p2 = plan_joins(s2, ctx2)["proposals"]
    assert [(p["join"], p["type"], p["frames"]) for p in p2] == [(1100, "J", 12)], p2
    rows = audio_ranges(s2, {1100: ("J", 12)}, 4)
    assert rows == [{"voice_item": "IMG_1@1000", "clip_id": "c1", "current": [1000, 1100], "source_start": 0, "source_end": 88,
                     "record": 1000, "fade_in": 0, "fade_out": 4},
                    {"voice_item": "IMG_2@1100", "clip_id": "c2", "current": [1100, 1200], "source_start": 8, "source_end": 120,
                     "record": 1088, "fade_in": 4, "fade_out": 0}], rows
    # handle smaller than the shift
    assert "only 20 frames" in check(s2[0], s2[1], "J", 30, ctx2), check(s2[0], s2[1], "J", 30, ctx2)
    # a word inside the extension
    assert "speech in the 12" in check(s2[0], s2[1], "J", 12, dict(ctx2, words={"c1": [[10, 60]], "c2": [[10, 15], [40, 120]]}))
    # a cut inside the extension
    assert "overlaps a cut" in check(s2[0], s2[1], "J", 12, dict(ctx2, cuts={"c2": [[12, 18]]}))
    # L: c1 extension src 100-112 silent, c2 trimmed src 20-36 silent (first word at 40)
    assert check(s2[0], s2[1], "L", 12, ctx2) is None
    assert "speaks within" in check(s2[0], s2[1], "L", 20, ctx2)
    # already split: Voice no longer ends at the join
    moved = dict(d2, tracks={"video": d2["tracks"]["video"], "audio": [{"name": "Voice", "items": [
        dict(v2[0], end=1088, source_end=88), dict(v2[1], start=1088, source_start=8)]}]})
    assert "not a plain cut" in check(*dump_segments(moved, 0, []), "J", 12, ctx2)

    # user marker "L 20" near the join wins over the default; a far marker is a question
    marks = [{"frame": 1105, "note": "L 8", "id": "Cocoa@1105"}, {"frame": 1180, "note": "J", "id": "Cocoa@1180"}]
    m = plan_joins(s2, ctx2, marks)
    assert [(p["type"], p["frames"], p["origin"]) for p in m["proposals"]] == [("L", 8, "marker")], m
    assert len(m["questions"]) == 1 and "Cocoa@1180" in m["questions"][0], m
    # a marker that fails its hard checks is rejected, and the other type is tried for the user
    alt = plan_joins(s2, ctx2, [{"frame": 1100, "note": "L 20", "id": "Cocoa@1100"}])
    assert not alt["proposals"] and "L 12 would pass" not in alt["rejected"][0]["reason"] and "J 12 would pass instead" in alt["rejected"][0]["reason"], alt
    # note syntax: the whole note, frames with or without a space
    assert REQUEST.match("J10") and REQUEST.match(" l 8 ") and REQUEST.match("split")
    assert not REQUEST.match("Light leak") and not REQUEST.match("Luma fade") and not REQUEST.match("J-cut please")
    # silence cuts (head, tail, pause) may become audible, word cuts may not
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"clips": [{"clip_name": "IMG_2", "clip_id": "c2"}], "candidates": [
            {"clip": "IMG_2", "type": "head", "start": 0, "end": 18, "decision": "cut"},
            {"clip": "IMG_2", "type": "editorial", "start": 200, "end": 260, "decision": "cut"},
            {"clip": "IMG_2", "type": "filler", "start": 300, "end": 310, "decision": "keep"}]}, f)
    assert load_cuts(f.name) == {"c2": [[200, 260]]}, load_cuts(f.name)
    os.unlink(f.name)
    # a transition marker-edit already built (claude:done) still counts as nearby
    built = dict(d2, markers={"110": {"color": "Cocoa", "note": "Cross Dissolve", "customData": "claude:done:marker-edit:2026-11-02"}})
    with tempfile.TemporaryDirectory() as tmp:
        dp = os.path.join(tmp, "dump.json")
        json.dump(built, open(dp, "w"))
        args = argparse.Namespace(dump=dp, rough=None, frames=None, fps=25, transcripts=tmp, cuts=None, source_offset=0,
                                  colors="Cocoa=transition,Pink=zoom", previous=None, handle_ms=150, out=os.path.join(tmp, "p.json"),
                                  j_lead=12, l_tail=12, max=50, fade=4, max_in_row=3)
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_joins(args)
        assert load(args.out)["rejected"][0]["reason"].startswith("a transition or zoom"), load(args.out)
    # a zoom next to an automatic candidate blocks it
    assert plan_joins(s2, ctx2, nearby=[1110])["rejected"][0]["reason"].startswith("a transition or zoom")
    # previous run's decision is respected
    prev = [{"key": join_key(s2[0], s2[1]), "decision": "keep"}]
    assert plan_joins(s2, ctx2, previous=prev)["proposals"] == []

    # max in a row: four clean source changes -> the fourth is dropped
    clips = [item(f"IMG_{i}", f"k{i}", 1000 + 100 * i, 100, 100, left=100, right=500) for i in range(5)]
    ctx3 = dict(ctx2, words={f"k{i}": [[130, 170]] for i in range(5)})
    d3 = dict(dump, tracks={"video": [{"name": "A-roll", "items": clips}], "audio": [{"name": "Voice", "items": [dict(c) for c in clips]}]})
    r3 = plan_joins(dump_segments(d3, 0, []), ctx3)
    assert len(r3["proposals"]) == 3 and "in a row" in r3["rejected"][0]["reason"], r3

    # rough mode (text-based-cut): every segment comes back, relative record frames
    plan = {"mode": "rough", "source_offset": 0, "settings": dict(ctx2, words=None, cuts=None),
            "segments": rough_segments([{"clip_name": "IMG_1", "clip_id": "c1", "start": 0, "end": 100},
                                        {"clip_name": "IMG_2", "clip_id": "c2", "start": 20, "end": 120}], {"c1": 600}),
            "words": ctx2["words"], "cuts": {}}
    plan["proposals"] = [dict(p, decision="split") for p in plan_joins(plan["segments"], dict(ctx2, handle=4))["proposals"]]
    out = apply_plan(plan)
    assert [(r["record"], r["source_start"], r["source_end"]) for r in out["audio"]] == [(0, 0, 88), (88, 8, 120)], out
    plan["proposals"][0]["frames"] = 30
    try:
        apply_plan(plan)
        raise AssertionError("an edited shift beyond the handle must be refused")
    except SystemExit as e:
        assert "only 20 frames" in str(e), e

    # verify: relaid audio in sync, or reports drift
    built = dict(d2, tracks={"video": d2["tracks"]["video"], "audio": [{"name": "Voice", "items": [
        item("IMG_1", "c1", 1000, 88, 0), item("IMG_2", "c2", 1088, 112, 8)]}]})
    assert verify(built, {"audio": rows}) == [], verify(built, {"audio": rows})
    drift = dict(built, tracks={"video": built["tracks"]["video"], "audio": [{"name": "Voice", "items": [
        item("IMG_1", "c1", 1000, 88, 0), item("IMG_2", "c2", 1088, 112, 10)]}]})
    assert any("out of sync" in p for p in verify(drift, {"audio": rows})), verify(drift, {"audio": rows})

    # sections: camera -> screen at 1200 moves to 12 frames into the phrase starting at 1210
    words = [{"text": "Відкриваємо", "start": 1210, "end": 1240}, {"text": "налаштування", "start": 1400, "end": 1430}]
    secs, notes = shift_sections([{"start": 1000, "mode": "camera"}, {"start": 1200, "mode": "screen"}, {"start": 1300, "mode": "camera"}], words, 12, 12, 50)
    assert [s["start"] for s in secs] == [1000, 1222, 1300], secs   # 1300 -> 1412 is beyond max 50
    assert secs[1]["split"] == "L" and "left as is" in notes[1], (secs, notes)

    # ambience: lead limited by media and the previous insert
    br = {"start_frame": 1000, "tracks": {"video": [{"name": "B-roll", "items": [
        item("B1", "b1", 1100, 50, 5, left=5, right=100), item("B2", "b2", 1155, 50, 200, left=200, right=0)]}]}}
    amb = ambience(br, 12, 12, 4)
    # B2's 5-frame lead (all the gap allows) takes B1's tail; B2 has no media after its end
    assert [(a["record"], a["record_end"], a["lead"], a["tail"]) for a in amb] == [(1095, 1150, 5, 0), (1150, 1205, 5, 0)], amb
    print("split_edits selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    def knobs(p, *names):
        defaults = {"j-lead": 12, "l-tail": 12, "max": 50, "fade": 4, "max-in-row": 3}
        for n in names:
            p.add_argument(f"--{n}", type=int, default=defaults[n])

    j = sub.add_parser("joins")
    src = j.add_mutually_exclusive_group(required=True)
    src.add_argument("--dump")
    src.add_argument("--rough")
    j.add_argument("--frames")
    j.add_argument("--fps", type=float, default=25)
    j.add_argument("--transcripts", required=True)
    j.add_argument("--cuts")
    j.add_argument("--source-offset", type=int, default=0)
    j.add_argument("--colors", default="Cocoa=transition,Pink=zoom")
    j.add_argument("--previous")
    j.add_argument("--handle-ms", type=float, default=150)
    j.add_argument("--out", required=True)
    knobs(j, "j-lead", "l-tail", "max", "fade", "max-in-row")
    au = sub.add_parser("audio")
    au.add_argument("plan")
    au.add_argument("--out", required=True)
    v = sub.add_parser("verify")
    v.add_argument("dump")
    v.add_argument("expected")
    s = sub.add_parser("sections")
    s.add_argument("dump")
    s.add_argument("transcripts")
    s.add_argument("pip_input")
    s.add_argument("--source-offset", type=int, default=0)
    s.add_argument("--out", required=True)
    knobs(s, "j-lead", "l-tail", "max")
    am = sub.add_parser("ambience")
    am.add_argument("dump")
    knobs(am, "j-lead", "l-tail", "fade")
    a = ap.parse_args()

    if a.cmd == "joins":
        return cmd_joins(a)
    if a.cmd == "audio":
        out = apply_plan(load(a.plan))
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(json.dumps({"splits": out["splits"], "audio_items": len(out["audio"]), "out": a.out}, ensure_ascii=False))
    elif a.cmd == "verify":
        problems = verify(load(a.dump), load(a.expected))
        print(json.dumps({"ok": not problems, "problems": problems}, ensure_ascii=False, indent=1))
    elif a.cmd == "sections":
        dump, data = load(a.dump), load(a.pip_input)
        transcripts = {}
        for name in sorted(os.listdir(a.transcripts)):
            if name.endswith(".json"):
                t = load(os.path.join(a.transcripts, name))
                transcripts[t["clip_id"]] = t
        words = words_on_timeline(dump, transcripts, "Voice", a.source_offset)["words"]
        data["sections"], notes = shift_sections(data["sections"], words, a.j_lead, a.l_tail, a.max)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print(json.dumps({"notes": notes, "out": a.out}, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(ambience(load(a.dump), a.j_lead, a.l_tail, a.fade), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
