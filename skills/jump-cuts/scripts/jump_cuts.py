"""Judge every A-roll join of a cut timeline and plan the lightest treatment that hides the jump.

python3 jump_cuts.py joins <dump.json> --transcripts <dir> [--fixed-transform ITEM_ID ...] [--source-offset 0] --out joins.json
python3 jump_cuts.py diff <a.tif> <b.tif>
python3 jump_cuts.py observe joins.json --join j3 [--diff 0.04 --max-cell 0.2] [--blink left|right] [--mouth left|right] --pose same|shifted|different --background static|moving
python3 jump_cuts.py classify joins.json --threshold 0.02 --scale 1.12
python3 jump_cuts.py decide joins.json --join j3 --decision leave|roll|smooth-cut|punch|cover [--k N] --scale 1.12
python3 jump_cuts.py rolled joins.json --join j3 --k N
python3 jump_cuts.py table joins.json
python3 jump_cuts.py selftest

Frames are absolute timeline frames; a join's `frame` is the first frame of its right segment. Word bounds for
`roll_range` are source frames from the clip start ([start, end), end exclusive).
"""
import argparse
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "resolve-core", "scripts"))
from tc import frames_to_tc
from timeline_map import find_track, load, source_words

sys.path.insert(0, os.path.join(HERE, "..", "..", "thumbnail-frames", "scripts"))
from thumbs import luma_grid, write_tiff

COVER_ROLES = ("b-roll", "screen")
MIN_SEGMENT_S = 2
AFTER_WORD = 2
ATTACK_S = 0.15
MAX_ROLL = 6
SMOOTH_FACTOR = 3
SMOOTH_HANDLE = 3
CELLS = 8
SAME_SCALE = ("leave", "roll", "smooth-cut")
TREATMENTS = SAME_SCALE + ("punch", "cover")


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


def frame_diff(a_path, b_path):
    """Mean absolute luma difference of two stills (0..1) and the largest mean over an 8 x 8 grid of cells."""
    try:
        (wa, ha, ga), (wb, hb, gb) = luma_grid(a_path), luma_grid(b_path)
    except OSError as e:
        raise SystemExit(f"cannot read still: {e}")
    if (wa, ha) != (wb, hb):
        raise SystemExit(f"stills differ in size: {a_path} {wa}x{ha}, {b_path} {wb}x{hb}")
    rows, cols = len(ga), len(ga[0])
    cells = {}
    for y in range(rows):
        for x in range(cols):
            cells.setdefault((y * CELLS // rows, x * CELLS // cols), []).append(abs(ga[y][x] - gb[y][x]))
    total = sum(sum(v) for v in cells.values()) / (rows * cols)
    return {"diff": round(total, 4), "max_cell": round(max(sum(v) / len(v) for v in cells.values()), 4)}


def effective(join):
    return join["decision"] or join["auto"]


def find_join(data, join_id):
    for join in data["joins"]:
        if join["id"] == join_id:
            return join
    raise SystemExit(f"no join {join_id!r}; joins: {[j['id'] for j in data['joins']]}")


def assign_scales(data, scale):
    """Punch-in is a state of a segment: equal across leave / roll / smooth-cut joins, different across punch joins."""
    segs = data["segments"]
    by_left = {j["left"]: j for j in data["joins"]}
    group = list(range(len(segs)))
    for i in range(len(segs) - 1):
        if i in by_left and effective(by_left[i]) in SAME_SCALE:
            group[i + 1] = group[i]
    fixed_groups = {group[i] for i, s in enumerate(segs) if s["fixed"]}
    scales = [1.0] * len(segs)
    chain_start, chain_fixed = 0, bool(segs) and group[0] in fixed_groups
    for i in range(len(segs) - 1):
        join = by_left.get(i)
        decision = effective(join) if join else None
        next_fixed = group[i + 1] in fixed_groups
        if decision in SAME_SCALE:
            scales[i + 1] = scales[i]
            continue
        if decision == "punch":
            want = scale if scales[i] == 1.0 else 1.0
            if next_fixed and want != 1.0 and not chain_fixed:
                for n in range(chain_start, i + 1):
                    scales[n] = scale if scales[n] == 1.0 else 1.0
                want = 1.0
            if not (next_fixed and want != 1.0):
                scales[i + 1] = want
                chain_fixed = chain_fixed or next_fixed
                continue
            if join["decision"] == "punch":
                raise SystemExit(f"{join['id']}: punch-in impossible, the segments on both sides must stay at 100 % "
                                 "(shorter than 2 s, own transform, or tied to such a segment)")
            join["auto"], join["reason"] = "cover", "punch-in impossible: both sides must stay at 100 %"
        chain_start, chain_fixed = i + 1, next_fixed
    for seg, value in zip(segs, scales):
        seg["scale"] = value


def classify(data, threshold, scale):
    segs = data["segments"]
    missing = [j["id"] for j in data["joins"] if not (j["covered"] or j["source_change"] or j["skip"]) and j["observation"] is None]
    if missing:
        raise SystemExit(f"no observation for {', '.join(missing)}: run `observe` for each join first")
    for j in data["joins"]:
        left, right = segs[j["left"]], segs[j["right"]]
        obs, diff = j["observation"] or {}, j["diff"]
        measured = "" if diff is not None else " (not measured)"
        trigger = obs.get("blink") or obs.get("mouth")
        if j["covered"]:
            auto, reason = "hidden", "the join is under B-roll / Screen"
        elif j["source_change"] or j["skip"]:
            auto, reason = "source-change", j["skip"] or "the source changes here: not a jump cut"
        elif (diff is not None and diff < threshold) or (diff is None and obs["pose"] == "same" and not trigger):
            auto, reason = "leave", "the jump is not visible" + measured
        elif trigger and not j["rolled"] and j["roll_range"]:
            what = "closed eyes" if obs.get("blink") else "mouth mid-move"
            auto, reason = "roll", f"{what} on the {trigger} frame; the cut can move {j['roll_range'][0]}..{j['roll_range'][1]} frames"
        elif (diff is not None and diff < SMOOTH_FACTOR * threshold and obs["pose"] == "same" and obs["background"] == "static"
              and left["right_offset"] >= SMOOTH_HANDLE and right["left_offset"] >= SMOOTH_HANDLE):
            auto, reason = "smooth-cut", "same pose, still background, small difference"
        elif left["fixed"] is None and right["fixed"] is None:
            auto, reason = "punch", "visible jump" + measured
        else:
            side = left if left["fixed"] else right
            auto, reason = "cover", f"visible jump, but a neighbour cannot change scale ({side['fixed']})" + measured
        j["auto"], j["reason"] = auto, reason
    assign_scales(data, scale)
    return data


def decide(data, join_id, decision, scale, k=None):
    join = find_join(data, join_id)
    if decision not in TREATMENTS:
        raise SystemExit(f"decision must be one of {', '.join(TREATMENTS)}")
    if join["covered"] or join["source_change"] or join["skip"]:
        raise SystemExit(f"{join_id}: hidden or a source change, no treatment applies")
    if decision == "roll":
        rng = join["roll_range"]
        if join["rolled"] or not rng or k is None or k == 0 or not rng[0] <= k <= rng[1]:
            raise SystemExit(f"{join_id}: roll needs --k inside {rng}, not 0, on a join that was not rolled yet")
        join["k"] = k
    else:
        join.pop("k", None)
    join["decision"] = decision
    assign_scales(data, scale)
    return data


def rolled(data, join_id, k):
    join = find_join(data, join_id)
    left, right = data["segments"][join["left"]], data["segments"][join["right"]]
    left["end"] += k
    left["right_offset"] -= k
    right["start"] += k
    right["source_start"] += k
    right["left_offset"] += k
    join["frame"] += k
    join.update(rolled=True, diff=None, max_cell=None, observation=None, auto=None, decision=None)
    join.pop("k", None)
    return data


def table(data):
    segs = data["segments"]
    return [{"id": j["id"], "tc": frames_to_tc(j["frame"], data["fps"]), "frame": j["frame"], "removed": j["removed"],
             "diff": j["diff"], "decision": effective(j), "k": j.get("k"), "by_user": j["decision"] is not None,
             "scale": [segs[j["left"]]["scale"], segs[j["right"]]["scale"]], "reason": j["reason"]} for j in data["joins"]]


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

    def exits(fn):
        try:
            fn()
        except SystemExit:
            return True
        return False

    with tempfile.TemporaryDirectory() as d:
        a, b, c, small = (os.path.join(d, n) for n in ("a.tif", "b.tif", "c.tif", "small.tif"))
        write_tiff(a, 64, 64, lambda x, y: (100, 100, 100))
        write_tiff(b, 64, 64, lambda x, y: (100, 100, 100))
        write_tiff(c, 64, 64, lambda x, y: (200, 200, 200) if x < 8 and y < 8 else (100, 100, 100))
        write_tiff(small, 32, 32, lambda x, y: (100, 100, 100))
        assert frame_diff(a, b) == {"diff": 0.0, "max_cell": 0.0}
        moved = frame_diff(a, c)
        assert 0 < moved["diff"] < 0.02 and moved["max_cell"] > 0.3, moved
        assert exits(lambda: frame_diff(a, small)) and exits(lambda: frame_diff(a, os.path.join(d, "missing.tif")))

    def chain(*decisions, fixed=()):
        segs = [{"index": n, "item_id": f"s{n}", "start": n * 100, "end": n * 100 + 100, "source_start": n * 200,
                 "left_offset": 50, "right_offset": 50, "fixed": "short" if n in fixed else None, "scale": 1.0}
                for n in range(len(decisions) + 1)]
        joins = [{"id": f"j{n + 1}", "frame": n * 100 + 100, "left": n, "right": n + 1, "removed": "", "split": False,
                  "covered": False, "source_change": False, "skip": None, "roll_range": [-3, 4], "rolled": False,
                  "diff": 0.09, "max_cell": 0.2, "observation": {"blink": None, "mouth": None, "pose": "shifted", "background": "static"},
                  "auto": dec, "decision": None, "reason": ""} for n, dec in enumerate(decisions)]
        return {"fps": 25.0, "start_frame": 0, "segments": segs, "joins": joins}

    def scales(data):
        assign_scales(data, 1.12)
        return [s["scale"] for s in data["segments"]]

    def effective(data):
        return {x["id"]: x["decision"] or x["auto"] for x in data["joins"]}

    assert scales(chain("punch", "leave", "punch", "source-change", "punch")) == [1.0, 1.12, 1.12, 1.0, 1.0, 1.12]
    assert scales(chain("punch", "punch")) == [1.0, 1.12, 1.0]
    assert scales(chain("punch", "leave", fixed=(2,))) == [1.12, 1.0, 1.0], "a free chain start takes the punch-in"
    boxed = chain("leave", "punch", "leave", fixed=(0, 3))
    assert scales(boxed) == [1.0, 1.0, 1.0, 1.0] and effective(boxed)["j2"] == "cover", boxed["joins"][1]

    data = chain(*[None] * 7, fixed=(7,))
    jn = {x["id"]: x for x in data["joins"]}
    jn["j1"]["covered"] = True
    jn["j2"]["source_change"] = True
    jn["j3"]["diff"] = 0.01
    jn["j4"]["observation"]["blink"] = "left"
    jn["j5"].update(diff=0.04, observation={"blink": None, "mouth": None, "pose": "same", "background": "static"})
    classify(data, 0.02, 1.12)
    assert effective(data) == {"j1": "hidden", "j2": "source-change", "j3": "leave", "j4": "roll", "j5": "smooth-cut",
                               "j6": "punch", "j7": "cover"}, effective(data)
    assert [s["scale"] for s in data["segments"]] == [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.12, 1.0], data["segments"]
    jn["j5"]["observation"]["background"] = "moving"
    classify(data, 0.02, 1.12)
    assert effective(data)["j5"] == "punch"
    unmeasured = chain(None, None)
    unmeasured["joins"][0].update(diff=None, observation={"blink": None, "mouth": None, "pose": "same", "background": "static"})
    unmeasured["joins"][1]["diff"] = None
    classify(unmeasured, 0.02, 1.12)
    assert effective(unmeasured) == {"j1": "leave", "j2": "punch"} and "not measured" in unmeasured["joins"][0]["reason"]
    unobserved = chain(None)
    unobserved["joins"][0]["observation"] = None
    assert exits(lambda: classify(unobserved, 0.02, 1.12))

    decide(data, "j6", "leave", 1.12)
    classify(data, 0.02, 1.12)
    assert jn["j6"]["decision"] == "leave" and effective(data)["j6"] == "leave"
    assert exits(lambda: decide(chain("leave", "cover", "leave", fixed=(0, 3)), "j2", "punch", 1.12))
    assert exits(lambda: decide(data, "j1", "punch", 1.12)), "a hidden join takes no treatment"
    assert exits(lambda: decide(data, "j4", "roll", 1.12, k=9)) and exits(lambda: decide(data, "j4", "roll", 1.12, k=0))
    decide(data, "j4", "roll", 1.12, k=2)
    before = (data["segments"][3]["end"], data["segments"][4]["start"], data["segments"][4]["source_start"])
    rolled(data, "j4", 2)
    after = (data["segments"][3]["end"], data["segments"][4]["start"], data["segments"][4]["source_start"])
    assert after == tuple(v + 2 for v in before) and jn["j4"]["frame"] == 402, (before, after)
    assert jn["j4"]["rolled"] and jn["j4"]["observation"] is None and jn["j4"]["decision"] is None and "k" not in jn["j4"]
    jn["j4"]["observation"] = {"blink": "left", "mouth": None, "pose": "shifted", "background": "static"}
    jn["j4"]["diff"] = 0.09
    classify(data, 0.02, 1.12)
    assert effective(data)["j4"] == "punch", "a rolled join is not rolled twice"
    empty = chain()
    classify(empty, 0.02, 1.12)
    assert table(empty) == [] and len(table(data)) == 7
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
    di = sub.add_parser("diff")
    di.add_argument("a")
    di.add_argument("b")
    ob = sub.add_parser("observe")
    ob.add_argument("--diff", type=float)
    ob.add_argument("--max-cell", type=float)
    ob.add_argument("--blink", choices=["left", "right"])
    ob.add_argument("--mouth", choices=["left", "right"])
    ob.add_argument("--pose", choices=["same", "shifted", "different"], required=True)
    ob.add_argument("--background", choices=["static", "moving"], required=True)
    cl = sub.add_parser("classify")
    cl.add_argument("--threshold", type=float, required=True)
    de = sub.add_parser("decide")
    de.add_argument("--decision", required=True)
    de.add_argument("--k", type=int)
    ro = sub.add_parser("rolled")
    ro.add_argument("--k", type=int, required=True)
    ta = sub.add_parser("table")
    for p in (ob, cl, de, ro, ta):
        p.add_argument("file")
    for p in (ob, de, ro):
        p.add_argument("--join", required=True)
    for p in (cl, de):
        p.add_argument("--scale", type=float, required=True)
    a = ap.parse_args()
    if a.cmd == "diff":
        return print(json.dumps(frame_diff(a.a, a.b)))
    if a.cmd != "joins":
        data = load(a.file)
        if a.cmd == "table":
            return print(json.dumps(table(data), ensure_ascii=False, indent=1))
        if a.cmd == "observe":
            join = find_join(data, a.join)
            join.update(diff=a.diff, max_cell=a.max_cell,
                        observation={"blink": a.blink, "mouth": a.mouth, "pose": a.pose, "background": a.background})
        elif a.cmd == "classify":
            classify(data, a.threshold, a.scale)
        elif a.cmd == "decide":
            decide(data, a.join, a.decision, a.scale, a.k)
        else:
            rolled(data, a.join, a.k)
        save(a.file, data)
        counts = {}
        for j in data["joins"]:
            counts[effective(j) or "undecided"] = counts.get(effective(j) or "undecided", 0) + 1
        return print(json.dumps({"joins": counts, "file": a.file}))
    if a.cmd == "joins":
        transcripts = load_transcripts(a.transcripts) if a.transcripts and os.path.isdir(a.transcripts) else {}
        data = build_joins(load(a.dump), transcripts, set(a.fixed_transform), a.source_offset)
        save(a.out, data)
        return print(json.dumps({"joins": len(data["joins"]), "segments": len(data["segments"]), "out": a.out}))


if __name__ == "__main__":
    main()
