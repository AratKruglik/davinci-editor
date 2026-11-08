"""Numeric checks on elements that skills placed on the timeline (no Resolve needed).

python3 critic.py inventory <placed ledger.json> <dump.json> --out elements.json
python3 critic.py check <elements.json> <dump.json> --zoom-max Z --cps-max C --chars-max N [--rules rules.json]
                        [--changed ELEMENT_ID ... | --scope OWNER] --out critic.json
      (without --changed: a fresh run, round 1. With --changed: a re-check after a fix; an existing critic.json of
       the same timeline keeps its round and its `add` findings, except those of the --changed elements and of
       elements no longer in the inventory. With --scope: a fresh run for one owner that keeps the `add` findings
       of the other owners' elements, but not their round)
python3 critic.py add <critic.json> --severity error|warn --kind K --element ID --tc TC --message M
                      [--frame F] [--still PATH] [--bbox x0 y0 x1 y1] [--fix-skill S --fix-change C]
python3 critic.py bbox <track on.tif> <track off.tif>      (bounds of what changed between the two renders)
python3 critic.py stale <critic.json> <fresh dump.json> [--ledger placed.json]
      (exit 1 = the timeline changed since the check, or an owner re-recorded the ledger after it)
python3 critic.py next-round <critic.json>                   (round + 1; exit 1 once two fix rounds are used up)
python3 critic.py selftest

Frames are absolute timeline frames (dump start_frame included). Kinds: see placed.py.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "resolve-core", "scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "pre-delivery-qc", "scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "chart-match", "scripts"))
from chart_match import read_tiff
from placed import live, load
from qc import ORDER, stale, state_of, summarize
from tc import frames_to_tc

TEXT_KINDS = ("lower-third", "callout", "kinetic", "counter")
CUT_ROLES = ("a-roll", "screen")
MAX_FIX_ROUNDS = 2


def role(track_name):
    return track_name.strip().lower().rstrip(" 0123456789")


def cut_frames(dump):
    bounds = {f for t in dump["tracks"].get("video", []) if role(t["name"]) in CUT_ROLES
              for i in t["items"] for f in (i["start"], i["end"])}
    return bounds - {dump["start_frame"], dump["end_frame"]}


def inventory(ledger, dump):
    entries, notes = live(ledger, dump)
    return [{**e, "id": f"{e['owner']}/{e['item_id']}" + (f"#{e['part']}" if e.get("part") is not None else ""),
             "mid": (e["full"] + e["hold_end"]) // 2} for e in entries], notes


def critic_stale(result, dump, ledger_path=None):
    """Owners re-record the ledger on every re-apply, and a fix may keep the item count and the end frame."""
    if stale(result, dump):
        return True
    if not ledger_path or not os.path.exists(ledger_path):
        return False
    written = datetime.fromtimestamp(int(os.path.getmtime(ledger_path)))   # checked_at keeps whole seconds
    return written > datetime.fromisoformat(result["checked_at"])


def add_finding(result, severity, kind, element, tc, message, frame=None, owner=None, evidence=None, fix=None, source="check"):
    if severity not in ORDER:
        raise SystemExit(f"severity must be one of {list(ORDER)}")
    result["findings"].append({
        "id": f"f{len(result['findings']) + 1}", "element": element, "owner": owner or element.split("/")[0],
        "tc": tc, "frame": frame, "severity": severity, "kind": kind, "message": message,
        "evidence": evidence or {"still": None, "bbox": None}, "fix": fix or {"skill": None, "change": None},
        "source": source})
    return summarize(result)


def carry_over(result, previous, elements, changed=(), scope=None):
    """A re-check after a fix round keeps the round and the measured or seen findings of elements nobody touched.
    A fresh run scoped to one owner keeps only the other owners' measured or seen findings."""
    if previous.get("timeline_id") != result["timeline_id"]:
        return result
    if scope:
        keep = {e["id"] for e in elements if e["owner"] != scope}
    else:
        result["round"] = previous["round"]
        keep = {e["id"] for e in elements} - set(changed)
    for f in previous["findings"]:
        if f.get("source") == "add" and f["element"] in keep:
            add_finding(result, f["severity"], f["kind"], f["element"], f["tc"], f["message"], frame=f["frame"],
                        owner=f["owner"], evidence=f["evidence"], fix=f["fix"], source="add")
    return summarize(result)


def next_round(result):
    if result["round"] > MAX_FIX_ROUNDS:
        raise SystemExit(f"max {MAX_FIX_ROUNDS} rounds: report what is left instead of fixing again")
    result["round"] += 1
    return result


def check(elements, dump, cfg):
    fps = dump["fps"]
    margin = cfg.get("cut_margin", 6)
    extra = cfg.get("hold_extra_s", {})
    result = {"timeline": dump.get("name"), "timeline_id": dump.get("timeline_id"),
              "checked_at": datetime.now().isoformat(timespec="seconds"), "round": 1,
              "state": state_of(dump), "findings": []}

    def flag(e, severity, kind, frame, message, change=None):
        add_finding(result, severity, kind, e["id"], frames_to_tc(frame, fps, dump.get("drop_frame", False)), message,
                    frame=frame, owner=e["owner"], fix={"skill": e["owner"], "change": change})

    texts = [e for e in elements if e["kind"] in TEXT_KINDS]
    for e in texts:
        hold = (e["hold_end"] - e["full"]) / fps
        bonus = 0 if e.get("explicit_hold") else extra.get(e["kind"], 0)
        reading = 0.5 + len(e["text"]) / 14
        need = max(3, reading) + bonus if e["kind"] == "lower-third" else reading + bonus
        if hold < need:
            flag(e, "error", "short-hold", e["full"], f"{e['kind']} {e['text']!r} is fully visible {hold:.1f} s, needs {need:.1f} s",
                 f"hold at least {need:.1f} s")

    for a, b in combinations(sorted(texts, key=lambda e: e["full"]), 2):
        if a["full"] < b["gone"] and b["full"] < a["gone"] and "callout" not in (a["kind"], b["kind"]):
            flag(b, "error", "overlap", b["full"], f"{b['kind']} {b['text']!r} appears while {a['kind']} {a['text']!r} is still on screen")

    cuts = cut_frames(dump)
    for e in elements:
        if e["kind"] in ("zoom", "pip"):    # the item itself, cut with the Screen sections: its edges are the cuts
            continue
        for edge in (e["start"], e["gone"]):
            near = min(cuts, key=lambda c: abs(c - edge), default=None)
            if near is not None and abs(near - edge) < margin:
                flag(e, "warn", "near-cut", edge, f"{e['kind']} edge is {abs(near - edge)} frames from the cut at frame {near}")

    for e in elements:
        if e["kind"] == "zoom" and e["scale"] is not None and e["scale"] > cfg["zoom_max"]:
            flag(e, "error", "zoom-scale", e["full"], f"zoom {e['scale']} exceeds {cfg['zoom_max']}", f"scale at most {cfg['zoom_max']}")
        if e["kind"] == "caption":
            cps = len(e["text"]) / max((e["gone"] - e["full"]) / fps, 1 / fps)
            if cps > cfg["cps_max"]:
                flag(e, "warn", "cps", e["full"], f"{cps:.1f} characters per second, limit {cfg['cps_max']}")
            longest = max(len(line) for line in e["text"].split("\n"))
            if longest > cfg["chars_max"]:
                flag(e, "warn", "chars", e["full"], f"line of {longest} characters, limit {cfg['chars_max']}")
    return summarize(result)


def apply_rules(cfg, rules):
    """Only numeric memory rules matter here; the judge reads the rest."""
    cfg = {**cfg, "hold_extra_s": dict(cfg.get("hold_extra_s", {}))}
    for rule in rules:
        param = rule.get("param") or {}
        name, value = param.get("name"), param.get("value")
        if name == "hold_extra_s":
            kind = rule["scope"]["kind"]
            cfg["hold_extra_s"][kind] = max(cfg["hold_extra_s"].get(kind, 0), value)
        elif name == "max_scale":
            cfg["zoom_max"] = min(cfg["zoom_max"], value)
    return cfg


def bbox_diff(on_path, off_path, threshold=0.04, step=2):
    w, h, on = read_tiff(on_path)
    w2, h2, off = read_tiff(off_path)
    if (w, h) != (w2, h2):
        raise SystemExit(f"render size differs: {w}x{h} vs {w2}x{h2}")
    xs = sorted({*range(0, w, step), w - 1})    # the last column and row are always sampled so edge contact is never missed
    ys = sorted({*range(0, h, step), h - 1})
    hit = [(x, y) for y in ys for x in xs if max(abs(a - b) for a, b in zip(on(x, y), off(x, y))) > threshold]
    if not hit:
        return None
    return [min(x for x, _ in hit), min(y for _, y in hit), max(x for x, _ in hit), max(y for _, y in hit)]


def safe_kinds(bbox, w, h):
    x0, y0, x1, y1 = bbox
    if x0 <= 0 or y0 <= 0 or x1 >= w - 1 or y1 >= h - 1:
        return [("offscreen", "error")]
    for margin, kind, severity in ((0.05, "unsafe", "error"), (0.10, "unsafe-title", "warn")):
        if x0 < w * margin or x1 > w * (1 - margin) or y0 < h * margin or y1 > h * (1 - margin):
            return [(kind, severity)]
    return []


def selftest():
    fps, t0 = 24, 86400

    def entry(item_id, kind="lower-third", text="Олексій Круглик", full=86700, hold=3.5, start=None, scale=None, gone_pad=12):
        hold_end = full + round(hold * fps)
        return {"item_id": item_id, "owner": "fusion-motion-graphics", "kind": kind, "spec": None, "track": "Titles",
                "start": full - 12 if start is None else start, "end": hold_end + gone_pad, "full": full,
                "hold_end": hold_end, "gone": hold_end + gone_pad, "text": text, "scale": scale}

    def dump_with(ids):
        def it(item_id, s, e):
            return {"item_id": item_id, "name": item_id, "start": s, "end": e}
        return {"name": "t", "timeline_id": "tl", "fps": fps, "start_frame": t0, "end_frame": 87400, "tracks": {
            "video": [{"index": 1, "name": "A-roll", "enabled": True, "items": [it("c1", t0, 86600), it("c2", 86600, 87400)]},
                      {"index": 2, "name": "Titles", "enabled": True, "items": [it(i, 86700, 86800) for i in ids]}],
            "audio": []}}

    base = {"zoom_max": 2.5, "cps_max": 17, "chars_max": 32}

    def run(entries, **cfg):
        dump = dump_with([e["item_id"] for e in entries])
        elements, notes = inventory({"timeline_id": "tl", "items": entries}, dump)
        return check(elements, dump, {**base, **cfg}), elements, notes

    def kinds(result):
        return [(f["kind"], f["element"]) for f in result["findings"]]

    r, elements, notes = run([entry("a", hold=2)])
    assert kinds(r) == [("short-hold", "fusion-motion-graphics/a")] and r["verdict"] == "FAIL" and r["counts"]["error"] == 1, r
    assert elements[0]["mid"] == (86700 + 86700 + 48) // 2 and notes == []
    assert kinds(run([entry("a", hold=3.5)])[0]) == [] and run([entry("a", hold=3.5)])[0]["verdict"] == "PASS"
    assert kinds(run([entry("a", hold=3.5)], hold_extra_s={"lower-third": 1.0})[0]) == [("short-hold", "fusion-motion-graphics/a")]
    assert kinds(run([{**entry("a", hold=3.5), "explicit_hold": True}], hold_extra_s={"lower-third": 1.0})[0]) == [], \
        "a marker-timed hold gets no hold_extra_s bonus"
    assert kinds(run([{**entry("a", hold=2.5), "explicit_hold": True}])[0]) == [("short-hold", "fusion-motion-graphics/a")]
    assert kinds(run([entry("a", text="Олексій Круглик, засновник і керівник відділу монтажу", hold=3.5)])[0]) == [("short-hold", "fusion-motion-graphics/a")]
    assert kinds(run([entry("k", "kinetic", "Привіт", hold=0.5)])[0]) == [("short-hold", "fusion-motion-graphics/k")]
    assert kinds(run([entry("k", "kinetic", "Привіт", hold=1.0)])[0]) == []

    r = run([entry("k", "kinetic", "Привіт", full=86700, hold=3), entry("l", full=86750)])[0]
    assert kinds(r) == [("overlap", "fusion-motion-graphics/l")] and r["findings"][0]["frame"] == 86750, r
    assert kinds(run([entry("c", "callout", "Тут", full=86700, hold=3), entry("l", full=86750)])[0]) == []

    r = run([entry("n", full=86700, start=86603)])[0]
    assert kinds(r) == [("near-cut", "fusion-motion-graphics/n")] and r["findings"][0]["severity"] == "warn" and r["verdict"] == "PASS WITH WARNINGS", r
    assert kinds(run([entry("n", start=86610)])[0]) == []
    assert kinds(run([entry("p", "pip", "", start=86600)])[0]) == [], "a PiP item is cut with its Screen section"
    assert kinds(run([entry("n", start=t0 + 2)])[0]) == [], "the timeline start is not a cut"
    r = run([entry("n", start=86600)])[0]
    assert r["findings"][0]["frame"] == 86600 and r["findings"][0]["tc"] == "01:00:08:08", r["findings"][0]
    late = entry("n")
    late["gone"] = 86597
    assert kinds(run([late])[0]) == [("near-cut", "fusion-motion-graphics/n")]

    assert kinds(run([entry("z", "zoom", "", scale=2.8)])[0]) == [("zoom-scale", "fusion-motion-graphics/z")]
    assert kinds(run([entry("z", "zoom", "", scale=2.0, start=86400)])[0]) == []
    assert kinds(run([entry("z", "zoom", "", scale=2.8)], zoom_max=3.0)[0]) == []
    assert kinds(run([entry("z", "zoom", "", scale=None)])[0]) == []

    fast = entry("s", "caption", "x" * 40, full=86700, hold=1, gone_pad=0)
    assert sorted(k for k, _ in kinds(run([fast])[0])) == ["chars", "cps"]
    assert kinds(run([entry("s", "caption", "Привіт, світе", hold=2, gone_pad=0)])[0]) == []

    dump = dump_with(["a"])
    elements, notes = inventory({"timeline_id": "tl", "items": [entry("a"), entry("gone-id")]}, dump)
    assert [e["id"] for e in elements] == ["fusion-motion-graphics/a"] and len(notes) == 1 and "gone-id" in notes[0], (elements, notes)
    elements, _ = inventory({"timeline_id": "tl", "items": [{**entry("a"), "part": "0"}, {**entry("a"), "part": "1"}]}, dump)
    assert [e["id"] for e in elements] == ["fusion-motion-graphics/a#0", "fusion-motion-graphics/a#1"], elements

    r = run([entry("a", hold=2), entry("k", "kinetic", "Привіт", full=87000, hold=0.5)])[0]
    assert sorted(f["id"] for f in r["findings"]) == ["f1", "f2"] and r["state"]["items"]["video"] == 4 and r["timeline_id"] == "tl"
    r = add_finding(r, "warn", "contrast", "fusion-motion-graphics/a", "01:00:10:00", "low contrast", frame=86640,
                    evidence={"still": "critic/a.tif", "bbox": [1, 2, 3, 4]}, fix={"skill": "fusion-motion-graphics", "change": "--color white"})
    added = next(f for f in r["findings"] if f["kind"] == "contrast")
    assert added["id"] == "f3" and added["owner"] == "fusion-motion-graphics" and added["evidence"]["bbox"] == [1, 2, 3, 4], added
    assert r["counts"] == {"error": 2, "warn": 1, "info": 0}
    try:
        add_finding(r, "fatal", "x", "o/1", None, "m")
    except SystemExit as e:
        assert "severity" in str(e)
    else:
        raise AssertionError("expected SystemExit: severity")

    assert not stale(r, dump_with(["a", "k"]))
    shrunk = dump_with(["a", "k"])
    shrunk["tracks"]["video"][1]["items"].pop()
    assert stale(r, shrunk)
    with tempfile.TemporaryDirectory() as d:
        ledger_path = os.path.join(d, "placed-t.json")
        checked = datetime.fromisoformat(r["checked_at"]).timestamp()
        assert not critic_stale(r, dump_with(["a", "k"]), ledger_path), "no ledger file: only the timeline state counts"
        open(ledger_path, "w").close()
        for mtime, expected in ((checked - 60, False), (checked + 0.9, False), (checked + 1, True)):
            os.utime(ledger_path, (mtime, mtime))
            assert critic_stale(r, dump_with(["a", "k"]), ledger_path) == expected, (mtime - checked, expected)
            assert critic_stale(r, dump_with(["a", "k"])) is False
        assert critic_stale(r, shrunk, ledger_path)
        for name, data in (("c.json", r), ("d.json", dump_with(["a", "k"]))):
            with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                json.dump(data, f)
        cli = [sys.executable, os.path.abspath(__file__), "stale", os.path.join(d, "c.json"), os.path.join(d, "d.json")]
        assert subprocess.run(cli, capture_output=True).returncode == 0
        assert subprocess.run(cli + ["--ledger", ledger_path], capture_output=True).returncode == 1

    moved_entry = {**entry("m", full=86712, start=86700), "item_start": 86700}
    moved_dump = dump_with(["m"])
    moved_dump["tracks"]["video"][1]["items"][0].update(start=86750, end=86850)
    (moved,), notes = inventory({"timeline_id": "tl", "items": [moved_entry]}, moved_dump)
    assert (moved["start"], moved["full"], moved["mid"]) == (86750, 86762, (86762 + 86762 + 84) // 2) and "moved +50" in notes[0], (moved, notes)
    assert r["round"] == 1 and next_round(r)["round"] == 2 and next_round(r)["round"] == 3
    try:
        next_round(r)
    except SystemExit as e:
        assert "max 2 rounds" in str(e)
    else:
        raise AssertionError("expected SystemExit: max 2 rounds")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "critic.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({**r, "round": 1}, f)
        cli = [sys.executable, os.path.abspath(__file__), "next-round", path]
        assert [subprocess.run(cli, capture_output=True).returncode for _ in range(2)] == [0, 0]
        refused = subprocess.run(cli, capture_output=True, text=True)
        with open(path, encoding="utf-8") as f:
            assert refused.returncode != 0 and "max 2 rounds" in refused.stderr and json.load(f)["round"] == 3, refused

    first = run([entry("a", hold=2), entry("k", "kinetic", "Привіт", full=87000, hold=3)])[0]
    for element in ("fusion-motion-graphics/a", "fusion-motion-graphics/k", "fusion-motion-graphics/gone"):
        add_finding(first, "error", "offscreen", element, "01:00:12:12", "edge", frame=86700, source="add")
    first["round"] = 2
    again, elements, _ = run([entry("a", hold=2), entry("k", "kinetic", "Привіт", full=87000, hold=3)])
    again = carry_over(again, first, elements, changed=["fusion-motion-graphics/k"])
    assert again["round"] == 2, again["round"]
    assert sorted((f["kind"], f["element"], f["source"]) for f in again["findings"]) == [
        ("offscreen", "fusion-motion-graphics/a", "add"), ("short-hold", "fusion-motion-graphics/a", "check")], again["findings"]
    two = [entry("a", hold=2), {**entry("z", "zoom", "", scale=1.5), "owner": "tutorial-zooms"}]
    scoped, elements, _ = run(two)
    scoped = carry_over(scoped, {**first, "findings": first["findings"] + [
        {**first["findings"][-1], "element": "tutorial-zooms/z", "owner": "tutorial-zooms", "kind": "covers-demo"}]},
        elements, scope="tutorial-zooms")
    assert scoped["round"] == 1, scoped["round"]
    assert sorted((f["kind"], f["element"]) for f in scoped["findings"] if f["source"] == "add") == [
        ("offscreen", "fusion-motion-graphics/a")], scoped["findings"]
    other, elements, _ = run([entry("a", hold=2)])
    other["timeline_id"] = "another"
    other = carry_over(other, first, elements)
    assert other["round"] == 1 and [f["kind"] for f in other["findings"]] == ["short-hold"], other

    with tempfile.TemporaryDirectory() as d:
        paths = {n: os.path.join(d, f"{n}.json") for n in ("el", "dump", "critic")}
        dump = dump_with(["a"])
        elements, _ = inventory({"timeline_id": "tl", "items": [entry("a", hold=2)]}, dump)
        stored = check(elements, dump, base)
        add_finding(stored, "error", "offscreen", "fusion-motion-graphics/a", "01:00:12:12", "edge", frame=86700, source="add")
        stored["round"] = 3
        for name, data in (("el", elements), ("dump", dump), ("critic", stored)):
            with open(paths[name], "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

        def cli_check(*extra):
            subprocess.run([sys.executable, os.path.abspath(__file__), "check", paths["el"], paths["dump"], "--zoom-max", "2.5",
                            "--cps-max", "17", "--chars-max", "32", "--out", paths["critic"], *extra], check=True, capture_output=True)
            with open(paths["critic"], encoding="utf-8") as f:
                return json.load(f)

        recheck = cli_check("--changed", "fusion-motion-graphics/other")
        assert recheck["round"] == 3 and sorted(f["kind"] for f in recheck["findings"]) == ["offscreen", "short-hold"], recheck
        fresh = cli_check()
        assert fresh["round"] == 1 and [f["kind"] for f in fresh["findings"]] == ["short-hold"], fresh

    rules = [{"scope": {"kind": "lower-third"}, "param": {"name": "hold_extra_s", "value": 1.0}},
             {"scope": {"kind": "lower-third"}, "param": {"name": "hold_extra_s", "value": 0.5}},
             {"scope": {"kind": "zoom"}, "param": {"name": "max_scale", "value": 2.0}},
             {"scope": {"kind": "callout"}, "param": {"name": "position", "value": "left"}},
             {"scope": {"kind": "zoom"}, "param": None}]
    cfg = apply_rules(base, rules)
    assert cfg["hold_extra_s"] == {"lower-third": 1.0} and cfg["zoom_max"] == 2.0 and base.get("hold_extra_s") is None
    assert apply_rules(base, [])["zoom_max"] == 2.5

    sys.path.insert(0, os.path.join(HERE, "..", "..", "thumbnail-frames", "scripts"))
    from thumbs import write_tiff
    w, h = 192, 108
    background = lambda x, y: (100 + x // 3, 120, 140 - y // 4)

    def render(path, rect=None, size=(w, h)):
        def px(x, y):
            if rect and rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                return (13, 13, 13)
            return background(x, y)
        write_tiff(path, size[0], size[1], px)

    with tempfile.TemporaryDirectory() as d:
        off, on, small = (os.path.join(d, n) for n in ("off.tif", "on.tif", "small.tif"))
        render(off)
        render(on, (150, 20, 191, 40))
        box = bbox_diff(on, off)
        assert box == [150, 20, 191, 40] and "offscreen" in [k for k, _ in safe_kinds(box, w, h)], box
        render(on, (20, 20, 60, 40))
        assert bbox_diff(on, off) == [20, 20, 60, 40] and safe_kinds(bbox_diff(on, off), w, h) == []
        render(on, (5, 20, 60, 40))
        assert safe_kinds(bbox_diff(on, off), w, h) == [("unsafe", "error")]
        render(on, (12, 20, 60, 40))
        assert safe_kinds(bbox_diff(on, off), w, h) == [("unsafe-title", "warn")]
        assert bbox_diff(off, off) is None
        render(small, size=(96, 54))
        try:
            bbox_diff(on, small)
        except SystemExit as e:
            assert "size" in str(e)
        else:
            raise AssertionError("expected SystemExit: size")
    print("critic selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("ledger")
    inv.add_argument("dump")
    inv.add_argument("--out", required=True)
    ck = sub.add_parser("check")
    ck.add_argument("elements")
    ck.add_argument("dump")
    ck.add_argument("--zoom-max", type=float, required=True)
    ck.add_argument("--cps-max", type=float, required=True)
    ck.add_argument("--chars-max", type=int, required=True)
    ck.add_argument("--rules")
    ck.add_argument("--changed", nargs="+")
    ck.add_argument("--scope")
    ck.add_argument("--out", required=True)
    bb = sub.add_parser("bbox")
    bb.add_argument("on")
    bb.add_argument("off")
    ad = sub.add_parser("add")
    ad.add_argument("critic")
    ad.add_argument("--severity", required=True)
    ad.add_argument("--kind", required=True)
    ad.add_argument("--element", required=True)
    ad.add_argument("--tc", required=True)
    ad.add_argument("--message", required=True)
    ad.add_argument("--frame", type=int)
    ad.add_argument("--still")
    ad.add_argument("--bbox", type=int, nargs=4)
    ad.add_argument("--fix-skill")
    ad.add_argument("--fix-change")
    st = sub.add_parser("stale")
    st.add_argument("critic")
    st.add_argument("dump")
    st.add_argument("--ledger")
    nr = sub.add_parser("next-round")
    nr.add_argument("critic")
    a = ap.parse_args()

    def read(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def write(path, data):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)

    if a.cmd == "inventory":
        elements, notes = inventory(load(a.ledger), read(a.dump))
        write(a.out, elements)
        return print(json.dumps({"out": a.out, "elements": len(elements), "notes": notes}, ensure_ascii=False, indent=1))
    if a.cmd == "check":
        cfg = {"zoom_max": a.zoom_max, "cps_max": a.cps_max, "chars_max": a.chars_max}
        if a.rules:
            cfg = apply_rules(cfg, read(a.rules))
        elements = read(a.elements)
        result = check(elements, read(a.dump), cfg)
        if (a.changed or a.scope) and os.path.exists(a.out):
            result = carry_over(result, read(a.out), elements, a.changed or (), None if a.changed else a.scope)
        write(a.out, result)
        return print(json.dumps({"out": a.out, "round": result["round"], "verdict": result["verdict"], "counts": result["counts"]}))
    if a.cmd == "bbox":
        box = bbox_diff(a.on, a.off)
        w, h, _ = read_tiff(a.on)
        return print(json.dumps({"bbox": box, "width": w, "height": h, "kinds": safe_kinds(box, w, h) if box else []}))
    result = read(a.critic)
    if a.cmd == "stale":
        is_stale = critic_stale(result, read(a.dump), a.ledger)
        print(json.dumps({"stale": is_stale, "verdict": result.get("verdict")}))
        sys.exit(1 if is_stale else 0)
    if a.cmd == "next-round":
        result = next_round(result)
        write(a.critic, result)
        return print(json.dumps({"round": result["round"]}))
    fix = {"skill": a.fix_skill, "change": a.fix_change} if a.fix_skill else None
    result = add_finding(result, a.severity, a.kind, a.element, a.tc, a.message, frame=a.frame,
                         evidence={"still": a.still, "bbox": a.bbox}, fix=fix, source="add")
    write(a.critic, result)
    print(json.dumps({"verdict": result["verdict"], "counts": result["counts"]}))


if __name__ == "__main__":
    main()
