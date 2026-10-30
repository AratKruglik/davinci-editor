"""Turn Resolve transcript JSON dumps into .srt and timecoded .txt.

python3 transcript_export.py <folder with <clip>.json>
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
        spoken = [w for w in seg.get("words", []) if w["text"] != SILENCE]
        text = " ".join(w["text"] for w in spoken).strip() or seg.get("text", "").replace(SILENCE, "").strip()
        if text:
            start, end = (spoken[0]["start"], spoken[-1]["end"]) if spoken else (seg["start"], seg["end"])
            yield (tc_to_frames(start, fps, drop) - origin, tc_to_frames(end, fps, drop) - origin, text, seg.get("speaker"))


def export(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    fps = data["fps"]
    base = os.path.splitext(path)[0]
    segments = list(speech_segments(data))
    with open(base + ".srt", "w", encoding="utf-8") as f:
        for n, (start, end, text, _) in enumerate(segments, 1):
            lines = textwrap.wrap(text, 42)
            f.write(f"{n}\n{srt_time(start, fps)} --> {srt_time(end, fps)}\n" + "\n".join(lines[:2] if len(lines) <= 2 else [lines[0], " ".join(lines[1:])]) + "\n\n")
    with open(base + ".txt", "w", encoding="utf-8") as f:
        for start, _, text, speaker in segments:
            f.write(f"[{srt_time(start, fps)[:8]}] " + (f"{speaker}: " if speaker else "") + text + "\n")
    language = (data.get("transcription") or {}).get("language")
    duration = segments[-1][1] / fps if segments else 0
    speakers = sorted({s for *_, s in segments if s})
    return {"clip": data["clip_name"], "language": language, "segments": len(segments), "speech_seconds_to": round(duration, 1), "speakers": speakers}


if __name__ == "__main__":
    folder = sys.argv[1]
    print(json.dumps([export(os.path.join(folder, n)) for n in sorted(os.listdir(folder)) if n.endswith(".json")], ensure_ascii=False, indent=1))
