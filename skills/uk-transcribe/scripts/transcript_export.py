"""Turn Resolve transcript JSON dumps into .srt and timecoded .txt.

python3 transcript_export.py <folder with <clip>.json> [--max-chars N]   (SRT line length, default 42)
python3 transcript_export.py selftest
"""
import json
import os
import sys
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "resolve-core", "scripts"))
from tc import tc_to_frames

SILENCE = "(...)"


def srt_time(frames, fps):
    ms = round(frames * 1000 / fps)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def speech_segments(data):
    fps, drop = data["fps"], data.get("drop_frame", False)
    origin = tc_to_frames(data["start_tc"], fps, drop)
    for seg in (data.get("transcription") or {}).get("segments", []):
        # Resolve's own words carry a leading space (" слово"); words written back by SetTranscription may not
        spoken = [w for w in seg.get("words", []) if w["text"].strip() not in ("", SILENCE)]
        text = " ".join(w["text"].strip() for w in spoken) or seg.get("text", "").replace(SILENCE, "").strip()
        if text:
            start, end = (spoken[0]["start"], spoken[-1]["end"]) if spoken else (seg["start"], seg["end"])
            yield (tc_to_frames(start, fps, drop) - origin, tc_to_frames(end, fps, drop) - origin, text, seg.get("speaker"))


def srt_cues(start, end, text, max_chars):
    """A segment longer than two lines becomes several cues of at most two lines each."""
    lines = textwrap.wrap(text, max_chars) or [text]
    chunks = [lines[i:i + 2] for i in range(0, len(lines), 2)]
    # shortcut: cue times split by character share, not word timings; enough for a review SRT
    total, done, cue_start = sum(len(" ".join(c)) for c in chunks), 0, start
    for n, chunk in enumerate(chunks):
        done += len(" ".join(chunk))
        cue_end = end if n == len(chunks) - 1 else start + round((end - start) * done / total)
        yield cue_start, cue_end, chunk
        cue_start = cue_end


def export(path, max_chars=42):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    fps = data["fps"]
    base = os.path.splitext(path)[0]
    segments = list(speech_segments(data))
    with open(base + ".srt", "w", encoding="utf-8") as f:
        cues = [cue for start, end, text, _ in segments for cue in srt_cues(start, end, text, max_chars)]
        for n, (start, end, lines) in enumerate(cues, 1):
            f.write(f"{n}\n{srt_time(start, fps)} --> {srt_time(end, fps)}\n" + "\n".join(lines) + "\n\n")
    with open(base + ".txt", "w", encoding="utf-8") as f:
        for start, _, text, speaker in segments:
            f.write(f"[{srt_time(start, fps)[:8]}] " + (f"{speaker}: " if speaker else "") + text + "\n")
    language = (data.get("transcription") or {}).get("language")
    duration = segments[-1][1] / fps if segments else 0
    speakers = sorted({s for *_, s in segments if s})
    return {"clip": data["clip_name"], "language": language, "segments": len(segments), "speech_seconds_to": round(duration, 1), "speakers": speakers}


def selftest():
    text = "Привіт, друзі! Сьогодні ми розберемо, як налаштувати колір у DaVinci Resolve за три кроки."
    cues = list(srt_cues(100, 400, text, 30))
    assert len(cues) == 2 and all(len(c[2]) <= 2 and all(len(l) <= 30 for l in c[2]) for c in cues), cues
    assert cues[0][0] == 100 and cues[-1][1] == 400 and cues[0][1] == cues[1][0], cues
    assert " ".join(l for c in cues for l in c[2]) == text
    assert list(srt_cues(0, 50, "Коротко.", 42)) == [(0, 50, ["Коротко."])]
    words = [{"start": "01:00:00:10", "end": "01:00:00:19", "text": " Привіт,"}, {"start": "01:00:00:20", "end": "01:00:01:04", "text": " (...)"},
             {"start": "01:00:01:05", "end": "01:00:01:14", "text": " друзі!"}, {"start": "01:00:01:15", "end": "01:00:01:20", "text": "Ок"}]
    data = {"fps": 25, "start_tc": "01:00:00:00", "transcription": {"segments": [{"start": "01:00:00:10", "end": "01:00:01:20", "words": words}]}}
    assert list(speech_segments(data)) == [(10, 45, "Привіт, друзі! Ок", None)], list(speech_segments(data))
    print("transcript_export selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        selftest()
        sys.exit()
    folder = sys.argv[1]
    max_chars = int(sys.argv[sys.argv.index("--max-chars") + 1]) if "--max-chars" in sys.argv else 42
    print(json.dumps([export(os.path.join(folder, n), max_chars) for n in sorted(os.listdir(folder)) if n.endswith(".json")], ensure_ascii=False, indent=1))
