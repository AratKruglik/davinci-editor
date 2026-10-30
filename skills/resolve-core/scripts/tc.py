"""Timecode <-> frame conversion for DaVinci Resolve frame rates, including 29.97/59.94 drop-frame.

CLI:
  python3 tc.py to-frames 01:00:02:05 --fps 25
  python3 tc.py to-tc 90055 --fps 29.97 --drop
  python3 tc.py selftest
"""
import argparse
import re


def nominal_fps(fps):
    return int(round(float(fps)))


def tc_to_frames(tc, fps, drop=None):
    hh, mm, ss, ff = (int(x) for x in re.split(r"[:;.]", tc.strip()))
    if drop is None:
        drop = ";" in tc
    base = nominal_fps(fps)
    total_minutes = hh * 60 + mm
    frames = (total_minutes * 60 + ss) * base + ff
    if drop:
        dropped = 2 * base // 30
        frames -= dropped * (total_minutes - total_minutes // 10)
    return frames


def frames_to_tc(frames, fps, drop=False):
    base = nominal_fps(fps)
    sep = ":"
    if drop:
        dropped = 2 * base // 30
        per_10min = base * 600 - dropped * 9
        per_min = base * 60 - dropped
        tens, rem = divmod(frames, per_10min)
        if rem > dropped:
            frames += dropped * 9 * tens + dropped * ((rem - dropped) // per_min)
        else:
            frames += dropped * 9 * tens
        sep = ";"
    ff = frames % base
    ss = frames // base % 60
    mm = frames // (base * 60) % 60
    hh = frames // (base * 3600)
    return f"{hh:02d}:{mm:02d}:{ss:02d}{sep}{ff:02d}"


def ms_to_frames(ms, fps):
    return round(ms * float(fps) / 1000.0)


def selftest():
    assert tc_to_frames("01:00:00:00", 25) == 90000
    assert frames_to_tc(90000, 25) == "01:00:00:00"
    assert tc_to_frames("00:01:00;02", 29.97) == 1800
    assert frames_to_tc(1800, 29.97, drop=True) == "00:01:00;02"
    assert tc_to_frames("00:10:00;00", 29.97) == 17982
    for fps, drop in ((23.976, False), (24, False), (25, False), (29.97, True), (50, False), (59.94, True)):
        for f in (0, 1, 1799, 1800, 17981, 17982, 107892, 215999):
            assert tc_to_frames(frames_to_tc(f, fps, drop), fps, drop) == f, (fps, drop, f)
    assert ms_to_frames(120, 25) == 3
    print("ok")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("to-frames")
    a.add_argument("tc")
    a.add_argument("--fps", required=True)
    a.add_argument("--drop", action="store_true", default=None)
    b = sub.add_parser("to-tc")
    b.add_argument("frames", type=int)
    b.add_argument("--fps", required=True)
    b.add_argument("--drop", action="store_true")
    sub.add_parser("selftest")
    args = p.parse_args()
    if args.cmd == "to-frames":
        print(tc_to_frames(args.tc, args.fps, args.drop))
    elif args.cmd == "to-tc":
        print(frames_to_tc(args.frames, args.fps, args.drop))
    else:
        selftest()
