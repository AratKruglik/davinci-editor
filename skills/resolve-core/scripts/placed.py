"""Ledger of elements placed on the timeline by skills (read by frame-critic and edit-memory).

python3 placed.py add <ledger.json> --timeline-id ID --item-id ID --owner SKILL --kind KIND --track NAME --item-start F
                  --start F --end F --full F --hold-end F --gone F [--spec PATH] [--text=T] [--scale S] [--part P]
                  [--explicit-hold]
python3 placed.py drop <ledger.json> --item-id ID        (before re-recording an item whose parts may change)
python3 placed.py selftest

All frames are absolute timeline frames, as item.GetStart() returns them. An existing (item_id, part) is replaced.
--part tells apart several elements inside one item (the captions of one Fusion comp, the zooms of one clip).
--item-start is item.GetStart() at placement (for a part, the item's start, not the part's): readers rebase the frames
by how far the item has moved since. --explicit-hold: the hold is the user's own (a marker duration), not computed.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

KINDS = ("lower-third", "callout", "kinetic", "counter", "zoom", "caption", "pip")
FIELDS = ("item_id", "owner", "kind", "spec", "track", "item_start", "start", "end", "full", "hold_end", "gone", "text", "scale",
          "explicit_hold")
FRAMES = ("start", "end", "full", "hold_end", "gone")


def load(path):
    if not os.path.exists(path):
        return {"timeline_id": None, "items": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def add(path, entry, timeline_id):
    if entry.get("kind") not in KINDS:
        raise SystemExit(f"kind must be one of {', '.join(KINDS)}, got {entry.get('kind')!r}")
    missing = [k for k in FIELDS if k not in entry]
    if missing:
        raise SystemExit(f"entry lacks fields: {', '.join(missing)}")
    ledger = load(path)
    if ledger["timeline_id"] not in (None, timeline_id):
        raise SystemExit(f"{path} belongs to a different timeline ({ledger['timeline_id']}), not {timeline_id}")
    ledger["timeline_id"] = timeline_id
    key = (entry["item_id"], entry.get("part"))
    ledger["items"] = [i for i in ledger["items"] if (i["item_id"], i.get("part")) != key] + \
                      [{**{k: entry[k] for k in FIELDS}, "part": entry.get("part")}]
    return save(path, ledger)


def drop(path, item_id):
    ledger = load(path)
    ledger["items"] = [i for i in ledger["items"] if i["item_id"] != item_id]
    return save(path, ledger)


def live(ledger, dump):
    """Entries whose item is still on the timeline, frames moved with the item; notes for the rest.
    Ledgers written before item_start existed are taken as they are."""
    items = {i.get("item_id"): i for tracks in dump["tracks"].values() for t in tracks for i in t["items"]}
    entries, notes = [], []
    for entry in ledger["items"]:
        label = f"{entry['owner']}/{entry['item_id']}" + (f"#{entry['part']}" if entry.get("part") is not None else "")
        item = items.get(entry["item_id"])
        if item is None:
            notes.append(f"{label} ({entry['kind']}, {entry['track']}) is not on the timeline any more: skipped")
            continue
        if entry.get("item_start") is None:
            entries.append(entry)
            continue
        shift = item["start"] - entry["item_start"]
        entries.append({**entry, **{k: entry[k] + shift for k in FRAMES}, "item_start": item["start"]})
        if shift:
            notes.append(f"{label} moved {shift:+d} frames since it was placed: its frames follow the item")
        # shortcut: a part's own span is not the item's length, so a trim is noticed only on whole-item entries
        if entry.get("part") is None and item["end"] - item["start"] != entry["end"] - entry["start"]:
            notes.append(f"{label} was trimmed by hand: {entry['end'] - entry['start']} → {item['end'] - item['start']} frames; "
                         "the recorded timing may no longer match what plays")
    return entries, notes


def save(path, ledger):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=1)
    return ledger


def selftest():
    def entry(item_id, start=100, kind="lower-third"):
        return {"item_id": item_id, "owner": "fusion-motion-graphics", "kind": kind, "spec": None, "track": "Titles",
                "item_start": start, "start": start, "end": start + 100, "full": start + 10, "hold_end": start + 90,
                "gone": start + 100, "text": "Привіт", "scale": None, "explicit_hold": False}

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "work", "placed.json")
        assert load(path) == {"timeline_id": None, "items": []}
        add(path, entry("a"), "tl-1")
        assert len(add(path, entry("b", 500, "zoom"), "tl-1")["items"]) == 2
        ledger = add(path, entry("a", 300), "tl-1")
        assert len(ledger["items"]) == 2 and [i["start"] for i in ledger["items"] if i["item_id"] == "a"] == [300]
        assert load(path) == ledger and load(path)["items"][1]["text"] == "Привіт"
        add(path, {**entry("cap", 700, "caption"), "part": "0"}, "tl-1")
        add(path, {**entry("cap", 750, "caption"), "part": "1"}, "tl-1")
        ledger = add(path, {**entry("cap", 760, "caption"), "part": "1"}, "tl-1")
        assert sorted((i["part"], i["start"]) for i in ledger["items"] if i["item_id"] == "cap") == [("0", 700), ("1", 760)]
        assert [i["item_id"] for i in drop(path, "cap")["items"]] == ["b", "a"]
        for bad, tl, text in ((entry("c", kind="wrong"), "tl-1", "kind"), (entry("c"), "tl-2", "different timeline"),
                              ({"item_id": "c", "kind": "zoom"}, "tl-1", "lacks fields")):
            try:
                add(path, bad, tl)
            except SystemExit as e:
                assert text in str(e), e
            else:
                raise AssertionError(f"expected SystemExit: {text}")
        assert len(load(path)["items"]) == 2

    def dump(*items):
        return {"tracks": {"video": [{"items": [{"item_id": i, "start": s, "end": e} for i, s, e in items]}]}}
    moved = {"items": [entry("a", 100), {**entry("z", 500, "zoom"), "item_start": 400, "part": "0"}, entry("gone")]}
    entries, notes = live(moved, dump(("a", 150, 250), ("z", 430, 900)))
    assert [(e["item_id"], e["start"], e["full"], e["hold_end"], e["gone"], e["end"], e["item_start"]) for e in entries] == [
        ("a", 150, 160, 240, 250, 250, 150), ("z", 530, 540, 620, 630, 630, 430)], entries
    assert len(notes) == 3 and "gone" in notes[2] and not any("trimmed" in n for n in notes), notes
    entries, notes = live(moved, dump(("a", 100, 180), ("z", 400, 900)))
    assert entries[0]["full"] == 110 and len(notes) == 2 and "trimmed" in notes[0], notes
    old = {"items": [{k: v for k, v in entry("a", 100).items() if k != "item_start"}]}
    assert live(old, dump(("a", 300, 400)))[0][0]["start"] == 100, "a ledger without item_start is not rebased"
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "placed.json")
        cli = [sys.executable, os.path.abspath(__file__), "add", path, "--timeline-id", "tl", "--item-id", "x", "--owner", "o",
               "--kind", "lower-third", "--track", "Titles", "--item-start", "10", "--start", "10", "--end", "20", "--full", "12",
               "--hold-end", "18", "--gone", "20"]
        subprocess.run(cli + ["--explicit-hold"], check=True, capture_output=True)
        subprocess.run(cli[:7] + ["y"] + cli[8:], check=True, capture_output=True)
        assert [(i["item_id"], i["item_start"], i["explicit_hold"]) for i in load(path)["items"]] == [("x", 10, True), ("y", 10, False)]
    print("placed selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["add", "drop"])
    p.add_argument("ledger")
    p.add_argument("--item-id", required=True)
    if sys.argv[1:2] == ["drop"]:
        a = p.parse_args()
        print(f"{len(drop(a.ledger, a.item_id)['items'])} items in {a.ledger}")
        return
    p.add_argument("--timeline-id", required=True)
    p.add_argument("--owner", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--track", required=True)
    for name in ("start", "end", "full", "hold-end", "gone"):
        p.add_argument(f"--{name}", type=int, required=True)
    p.add_argument("--spec")
    p.add_argument("--text", default="")
    p.add_argument("--scale", type=float)
    p.add_argument("--part")
    p.add_argument("--item-start", type=int, required=True)
    p.add_argument("--explicit-hold", action="store_true")
    a = p.parse_args()
    ledger = add(a.ledger, {**{k: getattr(a, k) for k in FIELDS}, "part": a.part}, a.timeline_id)
    print(f"{len(ledger['items'])} items in {a.ledger}")


if __name__ == "__main__":
    main()
