"""Find cut candidates in Resolve transcripts and turn approved cuts into keep ranges.

analyze:  python3 cut_candidates.py analyze <transcripts dir> --out <cuts.json> [--fillers ...] [--soft-fillers ...] [--pause-ms 700] [--handle-ms 150] [--sentence-ms 400] [--markers markers.json]
assemble: python3 cut_candidates.py assemble <cuts.json> --out <plan.json>

All frames are source frames relative to the clip start (Start TC), end exclusive.
A word's end timecode is treated as its last frame (inclusive), so a cut filler never leaves a frame of sound behind.
In cuts.json each candidate has "decision": "cut" | "keep" | "review"; assemble refuses while any "review" is left.
--markers applies the user's Red/Green/Yellow markers (task cut/keep/doubt) on top of the automatic candidates.
"""
import argparse
import difflib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "resolve-core", "scripts"))
from tc import ms_to_frames, tc_to_frames

SILENCE = "(...)"
RETAKE_WINDOW_S = 45
PUNCT = "\"'«»„“”.,!?…:;()[]—–-"
SENTENCE_END = ".!?…"


def norm(word):
    return word.lower().replace("’", "'").replace("ʼ", "'").strip(PUNCT)


def parse_list(value):
    return [tuple(norm(w) for w in item.split()) for item in value.split(",") if item.strip()]


def is_transcript(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return isinstance(data, dict) and "transcription" in data and "start_tc" in data


def load_clip(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    fps, drop = data["fps"], data.get("drop_frame", False)
    origin = tc_to_frames(data["start_tc"], fps, drop)
    words, segments = [], []
    for seg in (data.get("transcription") or {}).get("segments", []):
        first = len(words)
        for w in seg.get("words", []):
            text = w["text"].strip()   # Resolve's own words start with a space
            words.append({"text": text, "norm": norm(text) if text != SILENCE else None,
                          "start": tc_to_frames(w["start"], fps, drop) - origin, "end": tc_to_frames(w["end"], fps, drop) - origin + 1})
        speech = [i for i in range(first, len(words)) if words[i]["norm"]]
        if speech:
            segments.append(speech)
    return {"clip_name": data["clip_name"], "clip_id": data["clip_id"], "fps": fps, "start_tc": data["start_tc"],
            "drop_frame": drop, "words": words, "segments": segments}


def context(words, i, j, pad=6):
    spoken = lambda a, b: " ".join(w["text"] for w in words[a:b] if w["norm"])
    return f"{spoken(max(0, i - pad), i)} [{spoken(i, j)}] {spoken(j, j + pad)}".strip()


def analyze_clip(clip, fillers, soft_fillers, pause_frames, handle, sentence=0):
    words, out = clip["words"], []
    speech = [i for i, w in enumerate(words) if w["norm"]]

    def add(kind, i, j, start, end, decision, reason):
        if end - start > 0:
            out.append({"clip": clip["clip_name"], "type": kind, "start": start, "end": end, "text": context(words, i, j),
                        "decision": decision, "reason": reason})

    if speech:
        first, last = words[speech[0]], words[speech[-1]]
        add("head", 0, speech[0], 0, first["start"] - handle, "cut", "before first word")
        tail_end = max(w["end"] for w in words)
        add("tail", speech[-1] + 1, len(words), last["end"] + handle, tail_end, "cut", "after last word")

    for i, w in enumerate(words):
        if w["norm"] is None and speech and speech[0] < i < speech[-1] and w["end"] - w["start"] > pause_frames:
            before = next(words[x]["text"] for x in reversed(speech) if x < i)
            beat = before.rstrip("\"'»”)")[-1:] in SENTENCE_END
            add("pause", i, i + 1, w["start"] + (max(handle, sentence - handle) if beat else handle), w["end"] - handle, "cut",
                f"silence {round((w['end'] - w['start']) / clip['fps'], 2)} s" + (", after a sentence: a beat is kept" if beat else ""))

    for k, i in enumerate(speech):
        for phrases, kind, decision in ((fillers, "filler", "cut"), (soft_fillers, "soft_filler", "review")):
            for phrase in phrases:
                idx = speech[k:k + len(phrase)]
                if len(idx) == len(phrase) and tuple(words[x]["norm"] for x in idx) == phrase:
                    start, end = words[idx[0]]["start"], words[idx[-1]]["end"]
                    around = [words[x] for x in speech[max(0, k - 1):k] + speech[k + len(phrase):k + len(phrase) + 1]]
                    glued = decision == "cut" and len(around) == 2 and around[0]["end"] >= start and around[1]["start"] <= end
                    add(kind, idx[0], idx[-1] + 1, start, end, "review" if glued else decision,
                        " ".join(phrase) + ("; no pause on either side, the neighbours may get clipped: check by ear" if glued else ""))

    for k in range(len(speech)):
        for n in (4, 3, 2, 1):
            a, b = speech[k:k + n], speech[k + n:k + 2 * n]
            if len(b) == n and [words[x]["norm"] for x in a] == [words[x]["norm"] for x in b]:
                add("repeat", a[0], a[-1] + 1, words[a[0]]["start"], words[b[0]]["start"], "cut" if n > 1 else "review",
                    f"immediate repeat of {n} word(s)")
                break

    segs = clip["segments"]
    for s, seg in enumerate(segs):
        head = [words[x]["norm"] for x in seg[:5]]
        for nxt in segs[s + 1:]:
            if (words[nxt[0]]["start"] - words[seg[-1]]["end"]) / clip["fps"] > RETAKE_WINDOW_S:
                break
            other = [words[x]["norm"] for x in nxt[:5]]
            if len(head) >= 3 and difflib.SequenceMatcher(None, head, other).ratio() >= 0.75:
                add("retake", seg[0], nxt[0], words[seg[0]]["start"], words[nxt[0]]["start"] - handle, "review",
                    "same opening as a later take: " + " ".join(w["text"] for w in (words[x] for x in nxt[:12])))
                out[-1]["later_take"] = [clip["clip_name"], words[nxt[0]]["start"], words[nxt[-1]]["end"]]
                break
    return out


def opening(clip, seg):
    return [clip["words"][x]["norm"] for x in seg[:5]]


def cross_clip_retakes(clips, handle):
    """A flub often ends the file and the presenter restarts in the next one: compare clip ends with the next clip's start."""
    out = []
    for clip, nxt in zip(clips, clips[1:]):
        starts = [opening(nxt, seg) for seg in nxt["segments"][:2]]
        for seg in clip["segments"][-2:]:
            head = opening(clip, seg)
            if len(head) >= 3 and any(difflib.SequenceMatcher(None, head, o).ratio() >= 0.75 for o in starts):
                words = clip["words"]
                out.append({"clip": clip["clip_name"], "type": "retake", "start": max(0, words[seg[0]]["start"] - handle),
                            "end": max(w["end"] for w in words), "text": context(words, seg[0], len(words)), "decision": "review",
                            "reason": f"restarted at the beginning of {nxt['clip_name']}",
                            "later_take": [nxt["clip_name"], nxt["words"][nxt["segments"][0][0]]["start"], nxt["words"][nxt["segments"][0][-1]]["end"]]})
                break
    return out


def segment_span(clip, frame):
    """Bounds of the spoken segment containing the frame, or the nearest one within 1 s."""
    best = None
    for seg in clip["segments"]:
        start, end = clip["words"][seg[0]]["start"], clip["words"][seg[-1]]["end"]
        gap = 0 if start <= frame < end else min(abs(frame - start), abs(frame - end))
        if best is None or gap < best[0]:
            best = (gap, start, end)
    return (best[1], best[2]) if best and best[0] <= clip["fps"] else (frame, frame + 1)


def apply_markers(candidates, clips, markers):
    """User markers beat automatic suggestions: Red cuts, Green protects (and its take wins), Yellow forces a question."""
    by_name = {c["clip_name"]: c for c in clips}
    overlaps = lambda c, clip, a, b: c["clip"] == clip and c["start"] < b and c["end"] > a
    ranges = []
    for m in markers:
        clip = by_name.get(m["clip"])
        if not clip:
            continue
        a, b = (m["frame"], m["frame"] + m["duration"]) if m.get("duration", 1) > 1 else segment_span(clip, m["frame"])
        ranges.append((m, a, b))
        label = f"{m.get('color', m['task'])} marker" + (f": {m['note']}" if m.get("note") else "")
        if m["task"] == "cut":
            candidates.append({"clip": m["clip"], "type": "marker", "start": a, "end": b, "text": context_frames(clip, a, b),
                               "decision": "cut", "reason": label, "marker_ids": [m.get("id")]})
        elif m["task"] == "doubt":
            hit = [c for c in candidates if overlaps(c, m["clip"], a, b)]
            for c in hit:
                c["decision"], c["reason"] = "review", c["reason"] + f"; {label}"
                c.setdefault("marker_ids", []).append(m.get("id"))
            if not hit:
                candidates.append({"clip": m["clip"], "type": "marker", "start": a, "end": b, "text": context_frames(clip, a, b),
                                   "decision": "review", "reason": label, "marker_ids": [m.get("id")]})
    for m, a, b in ranges:
        if m["task"] != "keep":
            continue
        label = f"{m.get('color', 'Green')} marker"
        for c in [c for c in candidates if overlaps(c, m["clip"], a, b)]:
            if c["type"] == "marker" and c["decision"] == "cut":
                c["decision"], c["reason"] = "review", c["reason"] + f"; conflicts with {label} (keep)"
            else:
                c["decision"], c["reason"] = "keep", c["reason"] + f"; protected by {label}"
            c.setdefault("marker_ids", []).append(m.get("id"))
            if c["type"] == "retake" and c.get("later_take"):
                clip_name, la, lb = c["later_take"]
                candidates.append({"clip": clip_name, "type": "retake", "start": la, "end": lb,
                                   "text": context_frames(by_name[clip_name], la, lb), "decision": "review",
                                   "reason": f"earlier take chosen by {label}; this later repeat is likely redundant"})
    return candidates


def context_frames(clip, a, b):
    idx = [i for i, w in enumerate(clip["words"]) if w["norm"] and w["start"] < b and w["end"] > a]
    return context(clip["words"], idx[0], idx[-1] + 1) if idx else ""


def analyze(args):
    paths = [os.path.join(args.folder, n) for n in sorted(os.listdir(args.folder)) if n.endswith(".json")]
    clips = [load_clip(p) for p in paths if is_transcript(p)]
    clips = [c for c in clips if c["words"]]
    fillers, soft = parse_list(args.fillers), parse_list(args.soft_fillers)
    candidates = []
    for c in clips:
        candidates += analyze_clip(c, fillers, soft, ms_to_frames(args.pause_ms, c["fps"]), ms_to_frames(args.handle_ms, c["fps"]),
                                    ms_to_frames(args.sentence_ms, c["fps"]))
    candidates += cross_clip_retakes(clips, ms_to_frames(args.handle_ms, clips[0]["fps"]) if clips else 0)
    if args.markers:
        with open(args.markers, encoding="utf-8") as f:
            candidates = apply_markers(candidates, clips, json.load(f))
    for n, cand in enumerate(candidates, 1):
        cand["id"] = n
    result = {"handle_ms": args.handle_ms, "clips": [{k: c[k] for k in ("clip_name", "clip_id", "fps", "start_tc", "drop_frame")} |
                                                     {"source_frames": max(w["end"] for w in c["words"]),
                                                      "speech": [[w["start"], w["end"]] for w in c["words"] if w["norm"]]} for c in clips],
              "candidates": candidates}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    summary = {}
    for cand in candidates:
        key = f"{cand['type']}:{cand['decision']}"
        summary[key] = summary.get(key, 0) + 1
    print(json.dumps({"clips": len(clips), "candidates": len(candidates), "by_type": summary, "out": args.out}, ensure_ascii=False))


def keep_ranges(total, cuts, speech):
    ranges, pos = [], 0
    for start, end in sorted((max(0, s), min(total, e)) for s, e in cuts):
        if start > pos:
            ranges.append([pos, start])
        pos = max(pos, end)
    if pos < total:
        ranges.append([pos, total])
    has_speech = lambda r: any(s < r[1] and e > r[0] for s, e in speech)
    return [r for r in ranges if r[1] - r[0] > 0 and has_speech(r)]


def assemble(args):
    with open(args.cuts, encoding="utf-8") as f:
        data = json.load(f)
    pending = [c["id"] for c in data["candidates"] if c["decision"] == "review"]
    if pending:
        raise SystemExit(f"undecided candidates (set decision to cut or keep): {pending}")
    plan, before, after = [], 0, 0
    for clip in data["clips"]:
        cuts = [(c["start"], c["end"]) for c in data["candidates"] if c["clip"] == clip["clip_name"] and c["decision"] == "cut"]
        for start, end in keep_ranges(clip["source_frames"], cuts, clip["speech"]):
            plan.append({"clip_name": clip["clip_name"], "clip_id": clip["clip_id"], "start": start, "end": end})
            after += (end - start) / clip["fps"]
        before += clip["source_frames"] / clip["fps"]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    print(json.dumps({"segments": len(plan), "seconds_before": round(before, 1), "seconds_after": round(after, 1), "out": args.out}))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("folder")
    a.add_argument("--out", required=True)
    a.add_argument("--fillers", default="е,ее,еее,ем,емм,мм,ммм,хм")
    a.add_argument("--soft-fillers", default="ну,типу,коротше,значить,як би,власне,так би мовити")
    a.add_argument("--pause-ms", type=float, default=700)
    a.add_argument("--handle-ms", type=float, default=150)
    a.add_argument("--sentence-ms", type=float, default=400, help="silence kept after a sentence end when its pause is cut")
    a.add_argument("--markers", help="JSON list of user markers: {id, clip, frame (source, from clip start), duration, color, task: cut|keep|doubt, note}")
    b = sub.add_parser("assemble")
    b.add_argument("cuts")
    b.add_argument("--out", required=True)
    args = p.parse_args()
    analyze(args) if args.cmd == "analyze" else assemble(args)
