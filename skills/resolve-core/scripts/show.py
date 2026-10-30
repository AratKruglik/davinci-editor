"""Print the tail of files matching a glob, or a fallback line. Always exits 0 (used by skills' inline `!` context).

python3 show.py '<glob>' [lines] [fallback text]
"""
import glob
import sys

pattern = sys.argv[1] if len(sys.argv) > 1 else ""
lines = int(sys.argv[2]) if len(sys.argv) > 2 else 40
fallback = sys.argv[3] if len(sys.argv) > 3 else "nothing yet"
paths = sorted(glob.glob(pattern)) if "${" not in pattern else []
if not paths:
    print(fallback)
for path in paths:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            tail = f.readlines()[-lines:]
        print(f"--- {path}\n" + "".join(tail).rstrip())
    except OSError as exc:
        print(f"--- {path}: {exc}")
