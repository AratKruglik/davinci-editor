"""Self-check on a synthetic 25 fps transcript: filler, pause, repeat, retake, head/tail, assemble."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "cut_candidates.py")
sys.path.insert(0, os.path.join(HERE, "..", "..", "resolve-core", "scripts"))
from tc import frames_to_tc

FPS = 25
ORIGIN = 90000


def build(segments, t=50):
    """segments: list of [(text, frames)], laid out back to back from frame t. Returns Resolve-style segments."""
    out = []
    for spec in segments:
        words = []
        for text, dur in spec:
            words.append({"text": text, "start": frames_to_tc(ORIGIN + t, FPS), "end": frames_to_tc(ORIGIN + t + dur, FPS)})
            t += dur
        out.append({"words": words})
    return out


def cli(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)


def run():
    segments = build([
        [("Привіт,", 10), ("сьогодні", 12), ("ми", 5), ("поговоримо", 15), ("(...)", 10)],
        [("Привіт,", 10), ("сьогодні", 12), ("ми", 5), ("поговоримо", 15), ("про", 5), ("колір.", 10), ("(...)", 40)],
        [("е", 6), ("це", 5), ("це", 5), ("важливо", 15), ("ну", 5), ("справді.", 12), ("(...)", 30)],
    ])
    data = {"clip_name": "A001", "clip_id": "id1", "fps": FPS, "start_tc": "01:00:00:00", "drop_frame": False,
            "transcription": {"language": "uk", "segments": segments}}
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "A001.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        cuts, plan_path = os.path.join(d, "cuts.json"), os.path.join(d, "plan.json")
        assert cli("analyze", d, "--out", cuts).returncode == 0
        with open(cuts, encoding="utf-8") as f:
            result = json.load(f)
        types = {c["type"] for c in result["candidates"]}
        assert {"filler", "head", "pause", "repeat", "retake", "soft_filler", "tail"} <= types, types
        retake = next(c for c in result["candidates"] if c["type"] == "retake")
        assert retake["start"] == 50 and retake["decision"] == "review", retake

        blocked = cli("assemble", cuts, "--out", plan_path)
        assert blocked.returncode != 0 and "undecided" in blocked.stderr

        for c in result["candidates"]:
            if c["decision"] == "review":
                c["decision"] = "cut"
        with open(cuts, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
        assert cli("assemble", cuts, "--out", plan_path).returncode == 0
        with open(plan_path) as f:
            plan = json.load(f)
        assert plan and all(p["end"] > p["start"] for p in plan)
        assert all(a["end"] <= b["start"] for a, b in zip(plan, plan[1:]))
        second_take_start = 50 + 52
        assert plan[0]["start"] >= second_take_start - 3, plan[0]
        flub = build([[("Отже", 8), ("наступний", 12), ("крок", 8), ("це", 5), ("(...)", 10)]])
        restart = build([[("Отже,", 8), ("наступний", 12), ("крок", 8), ("це", 5), ("експорт.", 15)]])
        for name, segs in (("B001", flub), ("B002", restart)):
            with open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
                json.dump({**data, "clip_name": name, "clip_id": name, "transcription": {"segments": segs}}, f, ensure_ascii=False)
        assert cli("analyze", d, "--out", cuts).returncode == 0
        with open(cuts, encoding="utf-8") as f:
            cross = [c for c in json.load(f)["candidates"] if c["type"] == "retake" and c["clip"] == "B001"]
        assert cross and "B002" in cross[0]["reason"], cross
        markers = os.path.join(d, "markers.json.txt")
        with open(markers, "w", encoding="utf-8") as f:
            json.dump([{"id": "g1", "clip": "A001", "frame": 60, "duration": 1, "color": "Green", "task": "keep"},
                       {"id": "r1", "clip": "A001", "frame": 200, "duration": 1, "color": "Red", "task": "cut", "note": "зайве"},
                       {"id": "y1", "clip": "A001", "frame": 120, "duration": 10, "color": "Yellow", "task": "doubt"}], f)
        assert cli("analyze", d, "--out", cuts, "--markers", markers).returncode == 0
        with open(cuts, encoding="utf-8") as f:
            marked = [c for c in json.load(f)["candidates"] if c["clip"] == "A001"]
        first_retake = next(c for c in marked if c["type"] == "retake" and c["start"] == 50)
        assert first_retake["decision"] == "keep" and "g1" in first_retake["marker_ids"], first_retake
        assert any(c["type"] == "retake" and c["start"] == 102 and "Green" in c["reason"] for c in marked), "later take not proposed"
        red = next(c for c in marked if c["type"] == "marker" and c["decision"] == "cut")
        assert red["start"] <= 200 < red["end"] and "важливо" in red["text"], red
        assert all(c["decision"] == "review" for c in marked if c["start"] < 130 and c["end"] > 120 and "y1" in c.get("marker_ids", [])), "yellow"
        assert any("y1" in c.get("marker_ids", []) for c in marked)
        # Resolve's own words carry a leading space (" слово"), the silence word too
        native = build([[(" е", 6), (" це", 5), (" важливо", 15), (" (...)", 40), (" далі", 10), (" (...)", 10)]])
        with open(os.path.join(d, "C001.json"), "w", encoding="utf-8") as f:
            json.dump({**data, "clip_name": "C001", "clip_id": "C001", "transcription": {"segments": native}}, f, ensure_ascii=False)
        assert cli("analyze", d, "--out", cuts).returncode == 0
        with open(cuts, encoding="utf-8") as f:
            spaced = [c for c in json.load(f)["candidates"] if c["clip"] == "C001"]
        assert {"filler", "pause"} <= {c["type"] for c in spaced}, spaced
        assert all("  " not in c["text"] and "(...)" not in c["text"] for c in spaced), spaced

        beats = build([[("Готово.", 10), ("(...)", 25), ("Тепер", 10), ("(...)", 25), ("далі", 10), ("ем", 5), ("йдемо.", 10)]])
        with open(os.path.join(d, "D001.json"), "w", encoding="utf-8") as f:
            json.dump({**data, "clip_name": "D001", "clip_id": "D001", "transcription": {"segments": beats}}, f, ensure_ascii=False)
        assert cli("analyze", d, "--out", cuts).returncode == 0
        with open(cuts, encoding="utf-8") as f:
            paced = [c for c in json.load(f)["candidates"] if c["clip"] == "D001"]
        after_sentence, mid_phrase = [c for c in paced if c["type"] == "pause"]
        kept = lambda c, silence=26: silence - (c["end"] - c["start"])
        assert kept(after_sentence) == 10 and kept(mid_phrase) == 8, (after_sentence, mid_phrase)   # 400 ms vs 2 x 150 ms
        glued = next(c for c in paced if c["type"] == "filler")
        assert glued["decision"] == "review" and "by ear" in glued["reason"], glued
    print("ok", sorted(types), len(plan), "segments")


if __name__ == "__main__":
    run()
