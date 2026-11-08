"""Subtitles from words on the cut timeline (timeline_map.py words): YouTube SRT and word-timed Shorts captions.

python3 subtitles.py srt <words.json> --out <file.srt> [--max-chars 42] [--max-lines 2] [--max-cps 17] [--min-s 1] [--max-s 7]
python3 subtitles.py captions <words.json> --out <file.json> [--max-words 3] [--max-chars 22]
python3 subtitles.py fusion <captions.json> --item-start F [--comp-start 0] --width W --height H [--no-highlight] \
    [--font Montserrat --style Bold --text #FFFFFF --accent #FFD400] --out <spec.json>
python3 subtitles.py selftest

SRT time 0 = the timeline's first frame (what YouTube expects for the rendered video).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "fusion-motion-graphics", "scripts"))
from motion import hex_rgb, merge_keys, ramp, text_tool

SENTENCE_END = (".", "?", "!", "…")
SOFT_END = (",", ";", ":", "—", "–")
# a line shouldn't end on these: they belong to the next word
CLINGY = {"в", "у", "і", "й", "та", "а", "але", "на", "з", "із", "зі", "зо", "до", "від", "по", "за", "для", "про",
          "що", "як", "не", "ні", "чи", "би", "б", "о", "об", "при", "під", "над", "без", "через", "щоб", "або"}
PAUSE_S = 0.6
GAP_FRAMES = 2


def srt_time(frames, fps):
    ms = round(frames * 1000 / fps)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def text_of(words):
    return " ".join(w["text"] for w in words)


def wrap(text, max_chars, max_lines):
    """Balanced line breaks; never leave a short preposition or conjunction at a line end."""
    words = text.split()
    if len(text) <= max_chars or max_lines == 1:
        return [text]
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        if len(a) > max_chars or len(b) > max_chars:
            continue
        inside_quote = a.count("«") > a.count("»")
        cost = abs(len(a) - len(b)) + (100 if words[i - 1].lower().strip("«(\"") in CLINGY else 0) + (60 if inside_quote else 0)
        cost -= 15 if words[i - 1].endswith(SOFT_END + SENTENCE_END) else 0
        if best is None or cost < best[0]:
            best = (cost, [a, b])
    return best[1] if best else [text]


def group(words, fps, max_chars, max_s, pause_s=PAUSE_S, max_words=None):
    cues, cur = [], []
    for w in words:
        if cur:
            nxt_text = text_of(cur + [w])
            too_long = len(nxt_text) > max_chars or (w["end"] - cur[0]["start"]) / fps > max_s
            pause = (w["start"] - cur[-1]["end"]) / fps > pause_s
            full = max_words and len(cur) >= max_words
            ended = cur[-1]["text"].endswith(SENTENCE_END)
            soft = cur[-1]["text"].endswith(SOFT_END) and len(text_of(cur)) > 0.4 * max_chars
            if too_long or pause or full or ended or soft:
                carry = [cur.pop()] if (too_long or full) and len(cur) > 1 and cur[-1]["text"].lower() in CLINGY else []
                cues.append(cur)
                cur = carry
        cur.append(w)
    if cur:
        cues.append(cur)
    return cues


def build_srt(data, max_chars=42, max_lines=2, max_cps=17, min_s=1.0, max_s=7.0):
    fps, origin, words = data["fps"], data["start_frame"], data["words"]
    groups = group(words, fps, max_chars * max_lines, max_s)
    cues, warnings = [], []
    for n, g in enumerate(groups):
        start, end = g[0]["start"], g[-1]["end"]
        limit = groups[n + 1][0]["start"] - GAP_FRAMES if n + 1 < len(groups) else end + round(max_s * fps)
        text = text_of(g)
        need = max(round(min_s * fps), round(len(text) / max_cps * fps))
        end = min(max(end, start + need), limit, start + round(max_s * fps))
        if len(text) / ((end - start) / fps) > max_cps + 0.5:
            warnings.append(f"cue {n + 1} at {srt_time(start - origin, fps)}: {len(text) / ((end - start) / fps):.0f} chars/s, fast speech")
        cues.append({"start": start, "end": end, "lines": wrap(text, max_chars, max_lines)})
    srt = "".join(f"{i}\n{srt_time(c['start'] - origin, fps)} --> {srt_time(c['end'] - origin, fps)}\n" + "\n".join(c["lines"]) + "\n\n"
                  for i, c in enumerate(cues, 1))
    return srt, cues, warnings


def build_captions(data, max_words=3, max_chars=22):
    fps, origin = data["fps"], data["start_frame"]
    out = []
    for g in group(data["words"], fps, max_chars, 2.5, pause_s=0.4, max_words=max_words):
        text, pos, spans = text_of(g), 0, []
        for w in g:
            spans.append({"text": w["text"], "start": w["start"], "end": w["end"], "from": pos, "to": pos + len(w["text"])})
            pos += len(w["text"]) + 1
        out.append({"start": g[0]["start"], "end": g[-1]["end"], "text": text, "words": spans})
    for a, b in zip(out, out[1:]):
        a["end"] = min(max(a["end"], a["start"] + round(0.5 * fps)), b["start"])   # no flicker, no overlap
    return {"fps": fps, "start_frame": origin, "captions": out}


def caption_spec(caps, item_start, comp_start, brand, highlight=True):
    """One Fusion comp for all captions of a Short: per caption a white Text+, an accent copy whose Write On window
    follows the spoken word (`Start`/`End` = character fractions), both faded in/out with Merge Blend."""
    fps = caps["fps"]
    to_comp = lambda f: f - item_start + comp_start
    size, spot = brand.get("size", 0.075), (0.5, 0.36)   # above the Shorts UI at the bottom, clear of the right icons
    tools = [{"name": "CLEAR", "id": "Background", "inputs": {"Width": brand["width"], "Height": brand["height"], "TopLeftAlpha": 0.0}}]
    layer = "CLEAR"
    pop = max(2, round(0.12 * fps))
    for n, c in enumerate(caps["captions"], 1):
        s, e = to_comp(c["start"]), to_comp(c["end"])
        base = text_tool(f"CAP{n}", c["text"], brand["font"], brand["style"], size, hex_rgb(brand["text"]), spot, 1)
        base["inputs"].update({"Enabled2": 1, "Red2": 0.0, "Green2": 0.0, "Blue2": 0.0, "Alpha2": 0.85, "Thickness2": 0.08})
        base["keys"] = {"Size": merge_keys(ramp(s, s + pop, size * 0.9, size, "out"))}
        blend = {str(s - 1): 0.0, str(s): 1.0, str(e - 1): 1.0, str(e): 0.0}
        tools += [base, {"name": f"MIX{n}", "id": "Merge", "keys": {"Blend": blend},
                         "connect": {"Background": f"{layer}.Output", "Foreground": f"CAP{n}.Output"}}]
        layer = f"MIX{n}"
        if highlight:
            total = max(1, len(c["text"]))
            hi = text_tool(f"HI{n}", c["text"], brand["font"], brand["style"], size, hex_rgb(brand["accent"]), spot, 1)
            start_keys, end_keys = {}, {}
            for w in c["words"]:
                for f in (to_comp(w["start"]), to_comp(max(w["start"], w["end"] - 1))):
                    start_keys[str(f)] = round(w["from"] / total, 5)
                    end_keys[str(f)] = round(w["to"] / total, 5)
            hi["keys"] = {"Size": base["keys"]["Size"], "Start": start_keys, "End": end_keys}
            tools += [hi, {"name": f"HMIX{n}", "id": "Merge", "keys": {"Blend": blend},
                           "connect": {"Background": f"{layer}.Output", "Foreground": f"HI{n}.Output"}}]
            layer = f"HMIX{n}"
    tools.append({"name": "MediaOut1", "id": "MediaOut", "connect": {"Input": f"{layer}.Output"}})
    return {"captions": len(caps["captions"]), "highlight": highlight, "pop_frames": pop, "tools": tools,
            "visible": [to_comp(caps["captions"][0]["start"]), to_comp(caps["captions"][-1]["end"])] if caps["captions"] else None}


def selftest():
    def w(t, s, e):
        return {"text": t, "start": s, "end": e}
    data = {"fps": 25, "start_frame": 1000, "words": [
        w("Сьогодні", 1000, 1012), w("налаштуємо", 1013, 1030), w("роутер", 1031, 1045), w("з", 1046, 1048),
        w("нуля.", 1049, 1060), w("Спершу", 1100, 1112), w("відкрийте", 1113, 1125), w("браузер", 1126, 1140),
        w("і", 1141, 1143), w("введіть", 1144, 1156), w("адресу", 1157, 1170), w("192.168.0.1,", 1171, 1190),
        w("потім", 1191, 1200), w("натисніть", 1201, 1214), w("Enter.", 1215, 1226)]}
    srt, cues, _ = build_srt(data)
    assert srt.startswith("1\n00:00:00,000 --> "), srt
    assert cues[0]["lines"] == ["Сьогодні налаштуємо роутер з нуля."] or all(not l.split()[-1] in CLINGY for l in cues[0]["lines"])
    assert len(cues) >= 2 and cues[1]["start"] == 1100, cues
    for c in cues:
        assert all(len(l) <= 42 for l in c["lines"]) and len(c["lines"]) <= 2, c
        assert all(l.split()[-1].lower() not in CLINGY for l in c["lines"]), c
    for a, b in zip(cues, cues[1:]):
        assert b["start"] - a["end"] >= GAP_FRAMES, (a, b)
    assert wrap("відкрийте браузер і введіть адресу роутера", 30, 2)[0].split()[-1] != "і"
    quoted = wrap("Відкрийте розділ «Бездротова мережа» і задайте назву", 42, 2)
    assert quoted[0].count("«") == quoted[0].count("»"), quoted
    long = dict(data, words=[w(t, 2000 + i * 13, 2010 + i * 13) for i, t in enumerate(
        "Спершу відкрийте браузер і введіть адресу роутера потім натисніть кнопку входу і зачекайте кілька секунд.".split())])
    for c in build_srt(long)[1]:
        assert all(l.split()[-1].lower() not in CLINGY for l in c["lines"]), c

    cap = build_captions(data)["captions"]
    assert all(len(c["words"]) <= 3 for c in cap), cap
    first = cap[0]
    assert first["text"][first["words"][1]["from"]:first["words"][1]["to"]] == "налаштуємо", first
    assert cap[1]["start"] >= first["end"], cap
    assert not any(c["text"].endswith("нуля.") and len(c["words"]) > 2 and c["words"][0]["text"] == "Спершу" for c in cap)
    brand = {"width": 1080, "height": 1920, "font": "Montserrat", "style": "Bold", "text": "#FFFFFF", "accent": "#FFD400"}
    caps = build_captions(data)
    spec = caption_spec(caps, item_start=1000, comp_start=0, brand=brand)
    hi1 = next(t for t in spec["tools"] if t["name"] == "HI1")
    word2 = caps["captions"][0]["words"][1]
    assert hi1["keys"]["Start"][str(word2["start"] - 1000)] == round(word2["from"] / len(caps["captions"][0]["text"]), 5)
    assert spec["tools"][-1]["connect"]["Input"] == f"HMIX{len(caps['captions'])}.Output"
    mix1 = next(t for t in spec["tools"] if t["name"] == "MIX1")["keys"]["Blend"]
    assert mix1["0"] == 1.0 and mix1[str(caps["captions"][0]["end"] - 1000)] == 0.0, mix1
    size = next(t for t in spec["tools"] if t["name"] == "CAP1")["keys"]["Size"]
    assert spec["pop_frames"] == 3 and max(size, key=int) == str(spec["pop_frames"]), size
    plain = caption_spec(caps, 1000, 0, brand, highlight=False)
    assert not any(t["name"].startswith("HI") for t in plain["tools"])
    print("subtitles selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("srt")
    s.add_argument("words")
    s.add_argument("--out", required=True)
    s.add_argument("--max-chars", type=int, default=42)
    s.add_argument("--max-lines", type=int, default=2)
    s.add_argument("--max-cps", type=float, default=17)
    s.add_argument("--min-s", type=float, default=1.0)
    s.add_argument("--max-s", type=float, default=7.0)
    c = sub.add_parser("captions")
    c.add_argument("words")
    c.add_argument("--out", required=True)
    c.add_argument("--max-words", type=int, default=3)
    c.add_argument("--max-chars", type=int, default=22)
    fu = sub.add_parser("fusion")
    fu.add_argument("captions")
    fu.add_argument("--item-start", type=int, required=True)
    fu.add_argument("--comp-start", type=int, default=0)
    fu.add_argument("--width", type=int, required=True)
    fu.add_argument("--height", type=int, required=True)
    fu.add_argument("--no-highlight", action="store_true")
    fu.add_argument("--font", default="Montserrat")
    fu.add_argument("--style", default="Bold")
    fu.add_argument("--text", default="#FFFFFF")
    fu.add_argument("--accent", default="#FFD400")
    fu.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.words, encoding="utf-8") as f:
        data = json.load(f)
    if a.cmd == "fusion":
        brand = {"width": a.width, "height": a.height, "font": a.font, "style": a.style, "text": a.text, "accent": a.accent}
        spec = caption_spec(data, a.item_start, a.comp_start, brand, not a.no_highlight)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(spec, f, ensure_ascii=False, indent=1)
        return print(json.dumps({"out": a.out, "captions": spec["captions"], "tools": len(spec["tools"]), "visible": spec["visible"],
                                 "pop_frames": spec["pop_frames"]}))
    if a.cmd == "srt":
        srt, cues, warnings = build_srt(data, a.max_chars, a.max_lines, a.max_cps, a.min_s, a.max_s)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(srt)
        print(json.dumps({"out": a.out, "cues": len(cues), "warnings": warnings}, ensure_ascii=False, indent=1))
    else:
        caps = build_captions(data, a.max_words, a.max_chars)
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(caps, f, ensure_ascii=False, indent=1)
        print(json.dumps({"out": a.out, "captions": len(caps["captions"])}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
