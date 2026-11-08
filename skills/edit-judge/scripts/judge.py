"""Numbers, verdict and blind ranking for edit-judge.

python3 judge.py metrics <dump.json> <words.json> [--ledger placed.json] --format youtube|shorts [--pause-ms 700] --out metrics.json
python3 judge.py verdict <scores.json> [--critic critic.json] [--qc qc.json] [--stale critic|qc ...] [--metrics metrics.json] --out judge.json
      (also writes the report judge.md next to judge.json)
python3 judge.py blind <candidates.json> --out blind.json --key key.json [--seed N]
python3 judge.py pairs <blind.json>                                  (comparisons to run: every pair, both orders)
python3 judge.py rank <results.json> --key key.json
python3 judge.py selftest

scores.json: {criterion: {"score": 1..5, "evidence": [tc, ...], "note": str, "owner": skill (optional)}} for hook, pace, graphics, consistency, rules, ending.
results.json: [{"pair": [x, y], "order": "xy"|"yx", "winner": x|y}], labels as in blind.json.
--critic/--qc given but unreadable: exit 2, no verdict written; omitted: recorded as "missing" and counted as no findings.
--stale critic|qc: that file is outdated (critic.py / qc.py stale); its open errors still count, and an info row "re-run <skill>"
  is added that doesn't force REWORK by itself. Needs the file passed too.
judge.json: verdict, must_fix, info, critic, qc (verdict | "missing") and the scores as given.
blind keeps only range, still, text of a candidate; more than 6 candidates: exit 2 (a pick runs N*(N-1) comparisons).
A pair judged in both orders with different winners is a tie: half a win for each.
"""
import argparse
import contextlib
import io
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "resolve-core", "scripts"))
from placed import live
from tc import frames_to_tc

CRITERIA = ("hook", "pace", "graphics", "consistency", "rules", "ending")
HOOK_S = {"youtube": 30, "shorts": 3}
STATIC_S = {"youtube": 20, "shorts": 4}
STATIC_ROLES = ("a-roll", "screen", "b-roll")
NOT_GRAPHICS = ("zoom", "caption")
BLIND_FIELDS = ("range", "still", "text")
MAX_CANDIDATES = 6
CHECK_SKILL = {"critic": "frame-critic", "qc": "pre-delivery-qc"}


def role(name):
    return name.strip().lower().rstrip(" 0123456789")


def check_format(fmt):
    if fmt not in HOOK_S:
        raise SystemExit(f"format must be one of {', '.join(HOOK_S)}, got {fmt!r}")


def metrics(dump, words, ledger, fmt, pause_ms):
    check_format(fmt)
    fps, t0 = dump["fps"], dump["start_frame"]
    drop = dump.get("drop_frame", False)

    def tc(frame):
        return frames_to_tc(frame, fps, drop)

    tracks = dump["tracks"].get("video", []) + dump["tracks"].get("audio", [])
    end = dump.get("end_frame") or max((i["end"] for t in tracks for i in t["items"]), default=t0)
    spoken = sorted(words.get("words", []), key=lambda w: w["start"])
    entries, _ = live(ledger, dump)

    hook = [w["text"] for w in spoken if w["start"] < t0 + HOOK_S[fmt] * fps]
    pauses = [[tc(a["end"]), tc(b["start"])] for a, b in zip(spoken, spoken[1:])
              if (b["start"] - a["end"]) * 1000 / fps > pause_ms]

    cuts = {t0, end}
    for t in dump["tracks"].get("video", []):
        if role(t["name"]) in STATIC_ROLES:
            cuts.update(f for i in t["items"] if i.get("enabled", True) for f in (i["start"], i["end"]))
    cuts.update(f for e in entries for f in (e["start"], e["end"]))
    edges = sorted(f for f in cuts if t0 <= f <= end)
    static = [[tc(a), tc(b)] for a, b in zip(edges, edges[1:]) if b - a > STATIC_S[fmt] * fps]

    per_kind = {}
    for e in entries:
        per_kind[e["kind"]] = per_kind.get(e["kind"], 0) + 1
    minutes = (end - t0) / fps / 60
    graphics = sum(n for kind, n in per_kind.items() if kind not in NOT_GRAPHICS)
    return {"format": fmt, "hook_words": {"window_s": HOOK_S[fmt], "count": len(hook), "text": " ".join(hook)},
            "pauses": pauses, "static": static, "graphics_per_min": round(graphics / minutes, 2) if minutes else 0,
            "per_kind": per_kind, "tail_s": round((end - spoken[-1]["end"]) / fps, 2) if spoken else None}


def check_scores(scores):
    missing = [c for c in CRITERIA if c not in scores]
    if missing:
        raise SystemExit(f"scores lack criteria: {', '.join(missing)}")
    for c in CRITERIA:
        if scores[c].get("score") not in (1, 2, 3, 4, 5):
            raise SystemExit(f"{c}: score must be an integer 1..5, got {scores[c].get('score')!r}")


def verdict(scores, critic, qc, stale=()):
    check_scores(scores)
    must_fix = [{"criterion": c, "evidence": scores[c].get("evidence", []), "note": scores[c].get("note", ""), "owner": scores[c].get("owner")}
                for c in CRITERIA if scores[c]["score"] <= 2]
    for source, result in (("critic", critic), ("qc", qc)):
        for f in (result or {}).get("findings", []):
            if f["severity"] == "error":
                owner = ((f.get("fix") or {}).get("skill") or f.get("owner")) if source == "critic" else None
                must_fix.append({"tc": f.get("tc"), "kind": f["kind"], "message": f["message"], "owner": owner, "source": source})
    info = [{"kind": "stale", "message": f"re-run {CHECK_SKILL[source]}", "owner": CHECK_SKILL[source], "source": source}
            for source in sorted(set(stale))]
    return {"verdict": "REWORK" if must_fix else "SHIP", "must_fix": must_fix, "info": info}


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def report(title, result, metrics=None):
    lines = [f"# {title}", "",
             f"**Verdict:** {result['verdict']} · frame-critic: {result['critic']} · pre-delivery-qc: {result['qc']}", "",
             "| criterion | score | evidence | note |", "|---|---|---|---|"]
    for c in CRITERIA:
        s = result["scores"][c]
        lines.append(f"| {c} | {s['score']} | {cell(', '.join(s.get('evidence', [])))} | {cell(s.get('note', ''))} |")
    lines += ["", "## Must fix", ""]
    if result["must_fix"]:
        lines += ["| TC | problem | owner skill |", "|---|---|---|"]
        for f in result["must_fix"]:
            if "criterion" in f:
                lines.append(f"| {cell(', '.join(f['evidence']))} | {f['criterion']}: {cell(f['note'])} | {f['owner'] or '-'} |")
            else:
                lines.append(f"| {cell(f['tc'] or '')} | {f['kind']}: {cell(f['message'])} ({f['source']}) | {f['owner'] or '-'} |")
    else:
        lines.append("Nothing.")
    for f in result["info"]:
        lines += ["", f"Info: {f['message']} ({f['source']} result is older than the timeline; its errors above still count)."]
    if metrics:
        hook = metrics["hook_words"]
        lines += ["", "## Numbers", "",
                  f"- words in the first {hook['window_s']} s: {hook['count']}",
                  f"- pauses over the threshold: {len(metrics['pauses'])}",
                  f"- static spans: {', '.join('-'.join(r) for r in metrics['static']) or 'none'}",
                  f"- graphics per minute: {metrics['graphics_per_min']} {json.dumps(metrics['per_kind'], ensure_ascii=False)}",
                  f"- after the last word: {metrics['tail_s']} s"]
    lines += ["", "Advice only: the user decides whether to fix or ship; pre-delivery-qc is the hard gate."]
    return "\n".join(lines) + "\n"


def blind(candidates, seed):
    ids = [c["id"] for c in candidates]
    if len(set(ids)) != len(ids):
        raise SystemExit("candidate ids must be unique")
    if len(candidates) > MAX_CANDIDATES:
        print(f"error: {len(candidates)} candidates, at most {MAX_CANDIDATES} per pick; the caller pre-selects", file=sys.stderr)
        sys.exit(2)
    shuffled = list(candidates)
    random.Random(seed).shuffle(shuffled)
    labels = [chr(ord("A") + n) for n in range(len(shuffled))]
    hidden = [{"label": label, **{k: c[k] for k in BLIND_FIELDS if k in c}} for label, c in zip(labels, shuffled)]
    return hidden, {label: c["id"] for label, c in zip(labels, shuffled)}


def pairs(labels):
    return [{"pair": [x, y], "order": order} for n, x in enumerate(labels) for y in labels[n + 1:] for order in ("xy", "yx")]


def rank(results, labels):
    wins = {label: 0 for label in labels}
    judged = {}
    for r in results:
        x, y = r["pair"]
        if r["winner"] not in (x, y) or r["order"] not in ("xy", "yx") or x not in wins or y not in wins:
            raise SystemExit(f"bad result: {r}")
        judged.setdefault(frozenset((x, y)), {})[r["order"]] = r["winner"]
    for p in pairs(labels):
        key = frozenset(p["pair"])
        if set(judged.get(key, {})) != {"xy", "yx"}:
            raise SystemExit(f"pair {p['pair']} must be judged in both orders")
    for key, by_order in judged.items():
        a, b = by_order["xy"], by_order["yx"]
        if a == b:
            wins[a] += 1
        else:
            for label in key:
                wins[label] += 0.5
    ranking = sorted(labels, key=lambda label: -wins[label])
    return {"ranking": ranking, "tie": len(ranking) > 1 and wins[ranking[0]] == wins[ranking[1]], "wins": wins}


def cli_missing_inputs_selftest():
    import contextlib
    import io
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        path = lambda name: os.path.join(d, name)
        write(path("scores.json"), {c: {"score": 4, "evidence": [], "note": ""} for c in CRITERIA})
        write(path("ok.json"), {"findings": [], "verdict": "PASS"})
        for flag in ("--critic", "--qc"):
            out = path(f"v{flag}.json")
            argv = ["judge.py", "verdict", path("scores.json"), flag, path("typo.json"), "--out", out]
            old, sys.argv = sys.argv, argv
            try:
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    main()
            except SystemExit as e:
                assert e.code == 2 and "typo.json" in err.getvalue(), (flag, e.code, err.getvalue())
            else:
                raise AssertionError(f"{flag} with a missing file must exit 2")
            finally:
                sys.argv = old
            assert not os.path.exists(out), "no verdict may be written"
        out = path("judge-T.json")

        def run(*args):
            argv = ["judge.py", "verdict", path("scores.json"), *args, "--out", out]
            old, sys.argv = sys.argv, argv
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    main()
            finally:
                sys.argv = old
            return read(out)
        saved = run("--critic", path("ok.json"))
        assert saved["verdict"] == "SHIP" and saved["critic"] == "PASS" and saved["qc"] == "missing", saved
        assert saved["scores"]["hook"]["score"] == 4 and saved["info"] == [], saved
        md = open(path("judge-T.md"), encoding="utf-8").read()
        assert md.startswith("# judge-T\n") and "**Verdict:** SHIP" in md and "| hook | 4 |" in md and "## Numbers" not in md, md
        write(path("qc.json"), {"verdict": "FAIL", "findings": [{"severity": "error", "kind": "black", "tc": "01:00:09:00", "message": "a | b"}]})
        write(path("m.json"), {"hook_words": {"window_s": 30, "count": 5, "text": ""}, "pauses": [], "static": [["01:00:28:00", "01:01:08:00"]],
                               "graphics_per_min": 0.5, "per_kind": {}, "tail_s": 1.5})
        saved = run("--qc", path("qc.json"), "--stale", "qc", "--stale", "qc", "--metrics", path("m.json"))
        assert saved["verdict"] == "REWORK" and saved["qc"] == "FAIL" and len(saved["must_fix"]) == 1, saved
        assert saved["info"] == [{"kind": "stale", "message": "re-run pre-delivery-qc", "owner": "pre-delivery-qc", "source": "qc"}], saved
        md = open(path("judge-T.md"), encoding="utf-8").read()
        assert "| black: a \\| b (qc) | - |" in md and "Info: re-run pre-delivery-qc" in md and "01:00:28:00-01:01:08:00" in md, md
        try:
            run("--stale", "critic")
        except SystemExit as e:
            assert e.code == 2, e.code
        else:
            raise AssertionError("--stale without its file must be refused")

def selftest():
    fps = 25

    def item(start, end, item_id="i"):
        return {"item_id": item_id, "start": start, "end": end, "enabled": True}

    def dump_of(video, end, start=90000, ledger=None):
        placed = [item(e["item_start"], e["item_start"] + e["end"] - e["start"], e["item_id"]) for e in (ledger or {}).get("items", [])]
        return {"fps": fps, "start_frame": start, "end_frame": end,
                "tracks": {"video": [{"name": n, "items": items} for n, items in video.items()] + [{"name": "Titles", "items": placed}],
                           "audio": []}}

    def word(text, start, end):
        return {"text": text, "start": start, "end": end}

    def entry(kind, start, end):
        return {"item_id": f"{kind}{start}", "owner": "o", "kind": kind, "track": "Titles", "item_start": start, "start": start, "end": end,
                "full": start, "hold_end": end, "gone": end, "part": None}

    def placed_metrics(video, end, words, ledger, fmt="youtube"):
        return metrics(dump_of(video, end, ledger=ledger), words, ledger, fmt, 700)

    t0 = 90000
    long = dump_of({"A-roll": [item(t0, t0 + 25 * fps)]}, t0 + 25 * fps)
    m = metrics(long, {"words": []}, {"items": []}, "youtube", 700)
    assert m["static"] == [["01:00:00:00", "01:00:25:00"]], m["static"]
    cut = dump_of({"A-roll": [item(t0, t0 + 10 * fps), item(t0 + 10 * fps, t0 + 25 * fps)]}, t0 + 25 * fps)
    assert metrics(cut, {"words": []}, {"items": []}, "youtube", 700)["static"] == [], "cuts end the static span"
    a_roll = {"A-roll": [item(t0, t0 + 25 * fps)]}
    zoomed = placed_metrics(a_roll, t0 + 25 * fps, {"words": []}, {"items": [entry("zoom", t0 + 12 * fps, t0 + 14 * fps)]})
    assert zoomed["static"] == [], zoomed["static"]
    titled = placed_metrics(a_roll, t0 + 25 * fps, {"words": []}, {"items": [entry("lower-third", t0 + 2 * fps, t0 + 4 * fps)]})
    assert titled["static"] == [["01:00:04:00", "01:00:25:00"]], titled["static"]
    deleted = metrics(long, {"words": []}, {"items": [entry("lower-third", t0 + 2 * fps, t0 + 4 * fps)]}, "youtube", 700)
    assert deleted["static"] == [["01:00:00:00", "01:00:25:00"]] and deleted["per_kind"] == {}, "an entry gone from the timeline is ignored"
    moved_lt = entry("lower-third", t0 + 2 * fps, t0 + 4 * fps)
    moved_dump = dump_of(a_roll, t0 + 25 * fps, ledger={"items": [{**moved_lt, "item_start": t0 + 21 * fps}]})
    moved = metrics(moved_dump, {"words": []}, {"items": [moved_lt]}, "youtube", 700)
    assert moved["static"] == [["01:00:00:00", "01:00:21:00"]], moved["static"]
    overlay = dump_of({"A-roll": [item(t0, t0 + 25 * fps)], "Titles 2": [item(t0 + 10 * fps, t0 + 12 * fps)]}, t0 + 25 * fps)
    assert metrics(overlay, {"words": []}, {"items": []}, "youtube", 700)["static"] == [["01:00:00:00", "01:00:25:00"]]
    for seconds, expected in ((3, 0), (5, 1)):
        short = dump_of({"Screen 1": [item(t0, t0 + seconds * fps)]}, t0 + seconds * fps)
        assert len(metrics(short, {"words": []}, {"items": []}, "shorts", 700)["static"]) == expected, seconds

    words = {"words": [word("Привіт", t0 + 10, t0 + 20), word("світ", t0 + 25, t0 + 50), word("тут", t0 + 100, t0 + 110),
                       word("пізно", t0 + 40 * fps, t0 + 41 * fps)]}
    m = placed_metrics({"A-roll": [item(t0, t0 + 50 * fps)]}, t0 + 50 * fps, words,
                       {"items": [entry("lower-third", t0 + 100, t0 + 200), entry("lower-third", t0 + 300, t0 + 400), entry("zoom", t0 + 500, t0 + 600)]})
    assert m["hook_words"]["count"] == 3 and m["hook_words"]["text"] == "Привіт світ тут", m["hook_words"]
    assert m["pauses"] == [["01:00:02:00", "01:00:04:00"], ["01:00:04:10", "01:00:40:00"]], m["pauses"]
    assert m["per_kind"] == {"lower-third": 2, "zoom": 1}, m["per_kind"]
    assert m["graphics_per_min"] == 2.4, m["graphics_per_min"]
    assert m["tail_s"] == 9.0, m["tail_s"]
    assert metrics(dump_of({"A-roll": [item(t0, t0 + 50 * fps)]}, t0 + 50 * fps), words, {"items": []}, "shorts", 700)["hook_words"]["count"] == 2

    scores = {c: {"score": 4, "evidence": ["01:00:01:00"], "note": "ok"} for c in CRITERIA}
    clean = {"findings": [], "verdict": "PASS"}
    assert verdict(scores, clean, clean) == {"verdict": "SHIP", "must_fix": [], "info": []}
    low = {**scores, "pace": {"score": 2, "evidence": ["01:00:10:00"], "note": "drags"}}
    v = verdict(low, clean, clean)
    assert v["verdict"] == "REWORK" and v["must_fix"] == [{"criterion": "pace", "evidence": ["01:00:10:00"], "note": "drags", "owner": None}], v
    err = {"findings": [{"severity": "error", "kind": "overlap", "tc": "01:00:05:00", "message": "two titles", "fix": {"skill": "fusion-motion-graphics"}},
                        {"severity": "warn", "kind": "near-cut", "tc": "01:00:06:00", "message": "close", "fix": {"skill": None}}]}
    v = verdict(scores, err, clean)
    assert v["verdict"] == "REWORK" and v["must_fix"] == [
        {"tc": "01:00:05:00", "kind": "overlap", "message": "two titles", "owner": "fusion-motion-graphics", "source": "critic"}], v
    qc_err = {"findings": [{"severity": "error", "kind": "black", "tc": "01:00:09:00", "message": "no picture", "track": None}]}
    v = verdict(scores, None, qc_err)
    assert v["verdict"] == "REWORK" and v["must_fix"][0]["source"] == "qc" and v["must_fix"][0]["owner"] is None, v
    assert verdict(scores, None, None)["verdict"] == "SHIP"
    v = verdict(scores, clean, clean, stale=["critic", "critic"])
    assert v["verdict"] == "SHIP" and v["must_fix"] == [] and v["info"] == [
        {"kind": "stale", "message": "re-run frame-critic", "owner": "frame-critic", "source": "critic"}], v
    v = verdict(scores, err, clean, stale=["critic"])
    assert v["verdict"] == "REWORK" and len(v["must_fix"]) == 1 and len(v["info"]) == 1, v
    for bad in ({**scores, "pace": {"score": 6, "evidence": [], "note": ""}}, {k: v for k, v in scores.items() if k != "hook"}):
        try:
            verdict(bad, clean, clean)
        except SystemExit:
            pass
        else:
            raise AssertionError("bad scores must be refused")

    cands = [{"id": f"moment-{n}", "label": f"Секунда {n}", "range": [n, n + 5]} for n in range(4)]
    b1, key1 = blind(cands, 7)
    b2, key2 = blind(cands, 7)
    assert (b1, key1) == (b2, key2) and [c["label"] for c in b1] == ["A", "B", "C", "D"]
    assert sorted(key1.values()) == sorted(c["id"] for c in cands) and "moment" not in json.dumps(b1) and "Секунда" not in json.dumps(b1)
    leaky = blind([{"id": "x", "label": "L", "range": [1, 2], "score": 9, "favourite": True}], 1)[0]
    assert leaky == [{"label": "A", "range": [1, 2]}], leaky
    assert all(c["range"] == cands[int(key1[c["label"]][-1])]["range"] for c in b1)
    assert blind(cands, 8)[1] != key1 or blind(cands, 9)[1] != key1
    many = [{"id": f"m{n}", "label": "", "text": str(n)} for n in range(MAX_CANDIDATES + 1)]
    assert len(blind(many[:MAX_CANDIDATES], 1)[0]) == MAX_CANDIDATES
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            blind(many, 1)
    except SystemExit as e:
        assert e.code == 2, e.code
    else:
        raise AssertionError("more than MAX_CANDIDATES must be refused")

    assert rank([], ["A"]) == {"ranking": ["A"], "tie": False, "wins": {"A": 0}}
    assert [p["pair"] + [p["order"]] for p in pairs(["A", "B"])] == [["A", "B", "xy"], ["A", "B", "yx"]]
    assert len(pairs(["A", "B", "C"])) == 6

    def run(winner_xy, winner_yx):
        return rank([{"pair": ["A", "B"], "order": "xy", "winner": winner_xy}, {"pair": ["A", "B"], "order": "yx", "winner": winner_yx}], ["A", "B"])
    assert run("B", "B") == {"ranking": ["B", "A"], "tie": False, "wins": {"A": 0, "B": 1}}
    r = run("A", "B")
    assert r["tie"] is True and r["wins"] == {"A": 0.5, "B": 0.5}, r
    three = [{"pair": p["pair"], "order": p["order"], "winner": "C" if "C" in p["pair"] else p["pair"][0]} for p in pairs(["A", "B", "C"])]
    r = rank(three, ["A", "B", "C"])
    assert r["ranking"][0] == "C" and r["tie"] is False, r
    for bad in ([{"pair": ["A", "B"], "order": "xy", "winner": "A"}], [{"pair": ["A", "B"], "order": "xy", "winner": "Z"}] * 2):
        try:
            rank(bad, ["A", "B"])
        except SystemExit:
            pass
        else:
            raise AssertionError("incomplete or foreign results must be refused")
    cli_missing_inputs_selftest()
    print("judge selftest ok")


def read(path):
    if path is None:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print(f"error: cannot read {path}: {e}", file=sys.stderr)
        sys.exit(2)


def write(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("metrics")
    m.add_argument("dump")
    m.add_argument("words")
    m.add_argument("--ledger")
    m.add_argument("--format", required=True, choices=list(HOOK_S))
    m.add_argument("--pause-ms", type=int, default=700)
    m.add_argument("--out", required=True)
    v = sub.add_parser("verdict")
    v.add_argument("scores")
    v.add_argument("--critic")
    v.add_argument("--qc")
    v.add_argument("--stale", action="append", choices=list(CHECK_SKILL), default=[])
    v.add_argument("--metrics")
    v.add_argument("--out", required=True)
    b = sub.add_parser("blind")
    b.add_argument("candidates")
    b.add_argument("--out", required=True)
    b.add_argument("--key", required=True)
    b.add_argument("--seed", type=int, default=random.SystemRandom().randrange(2**31))
    pr = sub.add_parser("pairs")
    pr.add_argument("blind")
    r = sub.add_parser("rank")
    r.add_argument("results")
    r.add_argument("--key", required=True)
    a = p.parse_args()

    if a.cmd == "metrics":
        result = metrics(read(a.dump), read(a.words), read(a.ledger) or {"items": []}, a.format, a.pause_ms)
        write(a.out, result)
        return print(json.dumps({"out": a.out, "static": len(result["static"]), "pauses": len(result["pauses"])}))
    if a.cmd == "verdict":
        for name in a.stale:
            if not getattr(a, name):
                p.error(f"--stale {name} needs --{name}: the outdated file still counts")
        scores, critic, qc, numbers = read(a.scores), read(a.critic), read(a.qc), read(a.metrics)
        result = {**verdict(scores, critic, qc, a.stale), "critic": "missing" if critic is None else critic.get("verdict"),
                  "qc": "missing" if qc is None else qc.get("verdict"), "scores": scores}
        write(a.out, result)
        md = os.path.splitext(a.out)[0] + ".md"
        with open(md, "w", encoding="utf-8") as f:
            f.write(report(os.path.splitext(os.path.basename(a.out))[0], result, numbers))
        return print(json.dumps({"out": a.out, "report": md, "verdict": result["verdict"], "must_fix": len(result["must_fix"]),
                                 "info": len(result["info"]), "critic": result["critic"], "qc": result["qc"]}, ensure_ascii=False))
    if a.cmd == "blind":
        hidden, key = blind(read(a.candidates), a.seed)
        write(a.out, hidden)
        write(a.key, key)
        return print(json.dumps({"out": a.out, "key": a.key, "candidates": len(hidden)}))
    if a.cmd == "pairs":
        return print(json.dumps(pairs([c["label"] for c in read(a.blind)])))
    key = read(a.key)
    result = rank(read(a.results), sorted(key))
    result["ranking"] = [key[label] for label in result["ranking"]]
    result["wins"] = {key[label]: n for label, n in result["wins"].items()}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
