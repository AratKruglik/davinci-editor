"""Ledger of elements placed on the timeline by skills (read by frame-critic and edit-memory).

python3 placed.py add <ledger.json> --timeline-id ID --item-id ID --owner SKILL --kind KIND --track NAME
                  --start F --end F --full F --hold-end F --gone F [--spec PATH] [--text=T] [--scale S] [--part P]
python3 placed.py drop <ledger.json> --item-id ID        (before re-recording an item whose parts may change)
python3 placed.py selftest

All frames are absolute timeline frames, as item.GetStart() returns them. An existing (item_id, part) is replaced.
--part tells apart several elements inside one item (the captions of one Fusion comp, the zooms of one clip).
"""
import argparse
import json
import os
import sys
import tempfile

KINDS = ("lower-third", "callout", "kinetic", "counter", "zoom", "caption", "pip")
FIELDS = ("item_id", "owner", "kind", "spec", "track", "start", "end", "full", "hold_end", "gone", "text", "scale")


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


def save(path, ledger):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=1)
    return ledger


def selftest():
    def entry(item_id, start=100, kind="lower-third"):
        return {"item_id": item_id, "owner": "fusion-motion-graphics", "kind": kind, "spec": None, "track": "Titles",
                "start": start, "end": start + 100, "full": start + 10, "hold_end": start + 90, "gone": start + 100,
                "text": "Привіт", "scale": None}

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
    a = p.parse_args()
    ledger = add(a.ledger, {**{k: getattr(a, k) for k in FIELDS}, "part": a.part}, a.timeline_id)
    print(f"{len(ledger['items'])} items in {a.ledger}")


if __name__ == "__main__":
    main()
