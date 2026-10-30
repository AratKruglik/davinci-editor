"""Read duration, frame size and codecs from a rendered .mp4/.mov (ISO BMFF boxes, stdlib only) and check them.

python3 mp4_info.py check <file> [--seconds S] [--width W --height H] [--codec hevc|h264] [--audio] [--min-mbps M]
python3 mp4_info.py selftest

A render job's 'Complete' status is not proof: this reads the file that actually landed on disk.
"""
import argparse
import json
import os
import struct
import sys
import tempfile

CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts"}
CODECS = {b"hvc1": "hevc", b"hev1": "hevc", b"avc1": "h264", b"avc3": "h264", b"apch": "prores", b"apcn": "prores",
          b"mp4a": "aac", b"lpcm": "pcm", b"sowt": "pcm", b"twos": "pcm", b"ipcm": "pcm"}


def boxes(f, start, end):
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        size, kind = struct.unpack(">I4s", f.read(8))
        header = 8
        if size == 1:
            size, header = struct.unpack(">Q", f.read(8))[0], 16
        elif size == 0:
            size = end - pos
        if size < header:
            raise SystemExit(f"broken box {kind!r} at {pos}")
        yield kind, pos + header, pos + size
        pos += size


def info(path):
    out = {"file": path, "bytes": os.path.getsize(path), "tracks": []}
    with open(path, "rb") as f:
        def walk(start, end, track):
            for kind, body, stop in boxes(f, start, end):
                f.seek(body)
                if kind == b"mvhd":
                    version = f.read(1)[0]
                    f.read(3)
                    if version == 1:
                        f.read(16)
                        scale, duration = struct.unpack(">IQ", f.read(12))
                    else:
                        f.read(8)
                        scale, duration = struct.unpack(">II", f.read(8))
                    out["seconds"] = round(duration / scale, 3) if scale else None
                elif kind == b"trak":
                    t = {}
                    walk(body, stop, t)
                    out["tracks"].append(t)
                elif kind == b"tkhd":
                    f.seek(stop - 8)
                    w, h = struct.unpack(">II", f.read(8))
                    track["width"], track["height"] = w >> 16, h >> 16
                elif kind == b"hdlr":
                    f.read(8)
                    track["type"] = {b"vide": "video", b"soun": "audio"}.get(f.read(4), "other")
                elif kind == b"stsd":
                    f.read(8)
                    _, fourcc = struct.unpack(">I4s", f.read(8))
                    track["codec"] = CODECS.get(fourcc, fourcc.decode("latin-1"))
                elif kind in CONTAINERS:
                    walk(body, stop, track)
        walk(0, out["bytes"], {})
    return out


def check(path, seconds=None, width=None, height=None, codec=None, audio=False, fps=25, min_mbps=None):
    if not os.path.exists(path):
        return {"ok": False, "errors": [f"{path}: no such file"]}
    i = info(path)
    video = [t for t in i["tracks"] if t.get("type") == "video"]
    sound = [t for t in i["tracks"] if t.get("type") == "audio"]
    errors = []
    if i["bytes"] < 1024:
        errors.append(f"{i['bytes']} bytes: empty render")
    if not video:
        errors.append("no video track")
    if seconds and (i.get("seconds") is None or abs(i["seconds"] - seconds) > 1.5 / fps):
        errors.append(f"duration {i.get('seconds')} s, expected {seconds} s")
    if video and width and (video[0].get("width"), video[0].get("height")) != (width, height):
        errors.append(f"frame {video[0].get('width')}x{video[0].get('height')}, expected {width}x{height}")
    if video and codec and video[0].get("codec") != codec:
        errors.append(f"video codec {video[0].get('codec')}, expected {codec}")
    if audio and not sound:
        errors.append("no audio track")
    mbps = round(i["bytes"] * 8 / i["seconds"] / 1e6, 2) if i.get("seconds") else None
    if min_mbps and (mbps is None or mbps < min_mbps):
        errors.append(f"average bitrate {mbps} Mbit/s, expected at least {min_mbps} (broken or wrongly encoded render)")
    return dict(i, ok=not errors, errors=errors, mbps=mbps)


def _box(kind, payload):
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def _sample_mp4(path, seconds, width, height, fourcc=b"hvc1", with_audio=True):
    mvhd = _box(b"mvhd", b"\0\0\0\0" + b"\0" * 8 + struct.pack(">II", 1000, int(seconds * 1000)) + b"\0" * 80)
    def trak(handler, codec, w=0, h=0):
        tkhd = _box(b"tkhd", b"\0\0\0\0" + b"\0" * 72 + struct.pack(">II", w << 16, h << 16))
        hdlr = _box(b"hdlr", b"\0" * 8 + handler + b"\0" * 13)
        stsd = _box(b"stsd", b"\0" * 8 + struct.pack(">I4s", 16, codec) + b"\0" * 8)
        return _box(b"trak", tkhd + _box(b"mdia", hdlr + _box(b"minf", _box(b"stbl", stsd))))
    moov = _box(b"moov", mvhd + trak(b"vide", fourcc, width, height) + (trak(b"soun", b"mp4a") if with_audio else b""))
    with open(path, "wb") as f:
        f.write(_box(b"ftyp", b"isom\0\0\0\0") + _box(b"mdat", b"\0" * 2048) + moov)


def selftest():
    with tempfile.TemporaryDirectory() as d:
        good = os.path.join(d, "good.mp4")
        _sample_mp4(good, 600.0, 3840, 2160)
        r = check(good, seconds=600.0, width=3840, height=2160, codec="hevc", audio=True)
        assert r["ok"], r
        assert not check(good, seconds=600.0, min_mbps=30)["ok"], "a 2 KB file is not a 60 Mbit/s render"
        assert [t["type"] for t in r["tracks"]] == ["video", "audio"] and r["tracks"][1]["codec"] == "aac", r
        bad = os.path.join(d, "bad.mp4")
        _sample_mp4(bad, 598.0, 1920, 1080, fourcc=b"avc1", with_audio=False)
        e = check(bad, seconds=600.0, width=3840, height=2160, codec="hevc", audio=True)["errors"]
        assert len(e) == 4 and any("duration" in x for x in e) and any("no audio" in x for x in e), e
        assert not check(os.path.join(d, "missing.mp4"))["ok"]
    print("mp4_info selftest ok")


def main():
    if sys.argv[1:] == ["selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("file")
    c.add_argument("--seconds", type=float)
    c.add_argument("--fps", type=float, default=25)
    c.add_argument("--width", type=int)
    c.add_argument("--height", type=int)
    c.add_argument("--codec")
    c.add_argument("--audio", action="store_true")
    c.add_argument("--min-mbps", type=float)
    a = ap.parse_args()
    r = check(a.file, a.seconds, a.width, a.height, a.codec, a.audio, a.fps, a.min_mbps)
    print(json.dumps(r, indent=1))
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
