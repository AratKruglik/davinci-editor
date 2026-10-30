"""Self-check on a tiny generated library."""
import os
import sys
import tempfile
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sound_library import index, search, tags_of


def tone(path, seconds):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * int(8000 * seconds))


def main():
    assert tags_of(os.path.join("Whooshes", "FastAir", "whoosh_air_01.wav")) == ["whooshes", "fast", "air", "whoosh"]
    with tempfile.TemporaryDirectory() as d:
        sfx, music = os.path.join(d, "sfx"), os.path.join(d, "music")
        tone(os.path.join(sfx, "PackA", "Whooshes", "whoosh_fast_01.wav"), 0.8)
        tone(os.path.join(sfx, "PackA", "UI", "click_soft.wav"), 0.2)
        tone(os.path.join(sfx, "PackA", "UI", "._click_soft.wav"), 0.2)
        with open(os.path.join(sfx, "PackA", "LICENSE.txt"), "w") as f:
            f.write("royalty free")
        tone(os.path.join(music, "Calm", "lofi_bed_92bpm.wav"), 3.0)
        tone(os.path.join(music, "Tense", "pulse 120 BPM.wav"), 2.0)
        with open(os.path.join(music, "Calm", "broken.wav"), "w") as f:
            f.write("not audio")

        items = index([("sfx", sfx), ("music", music), ("sfx", os.path.join(d, "missing"))])
        names = sorted(i["name"] for i in items)
        assert names == ["broken.wav", "click_soft.wav", "lofi_bed_92bpm.wav", "pulse 120 BPM.wav", "whoosh_fast_01.wav"], names
        whoosh = next(i for i in items if i["name"].startswith("whoosh"))
        assert whoosh["source"] == "PackA" and whoosh["license"].endswith("LICENSE.txt") and whoosh["duration_s"] == 0.8, whoosh
        assert next(i for i in items if i["name"] == "broken.wav")["duration_s"] is None

        assert [h["name"] for h in search(items, ["whoosh"], kind="sfx")] == ["whoosh_fast_01.wav"]
        assert [h["name"] for h in search(items, ["click"], kind="sfx", max_s=0.5)] == ["click_soft.wav"]
        assert search(items, ["click"], kind="sfx", min_s=1) == []
        assert [h["name"] for h in search(items, [], kind="music", bpm="80-100")] == ["lofi_bed_92bpm.wav"]
        assert [h["name"] for h in search(items, ["calm"], kind="music", min_s=2.5)] == ["lofi_bed_92bpm.wav"]
    print("sound_library selftest ok")


if __name__ == "__main__":
    main()
