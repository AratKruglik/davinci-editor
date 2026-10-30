"""Self-check: synthesize an Apple Log still of a chart with a known cast, fit, and expect near-zero error."""
import json
import os
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chart_match as cm


def write_tiff(path, width, height, pixel):
    rows = bytearray()
    for y in range(height):
        for x in range(width):
            rows += struct.pack("<HHH", *(int(round(max(0.0, min(1.0, v)) * 65535)) for v in pixel(x, y)))
    entries = [(256, 4, 1, width), (257, 4, 1, height), (258, 3, 1, 16), (259, 3, 1, 1), (262, 3, 1, 2),
               (273, 4, 1, 8), (277, 3, 1, 3), (278, 4, 1, height), (279, 4, 1, len(rows)), (284, 3, 1, 1)]
    ifd = struct.pack("<H", len(entries)) + b"".join(
        struct.pack("<HHI", t, typ, n) + (struct.pack("<HH", v, 0) if typ == 3 else struct.pack("<I", v)) for t, typ, n, v in entries
    ) + struct.pack("<I", 0)
    with open(path, "wb") as f:
        f.write(b"II" + struct.pack("<HI", 42, 8 + len(rows)) + rows + ifd)


def run():
    assert abs(cm.delta_e2000((50, 2.6772, -79.7751), (50, 0, -82.7485)) - 2.0425) < 1e-3
    assert abs(cm.apple_log_decode(cm.apple_log_encode(0.18)) - 0.18) < 1e-9
    assert abs(cm.apple_log_decode(cm.apple_log_encode(0.005)) - 0.005) < 1e-9

    cast = [[0.9, 0.15, -0.05], [0.05, 0.85, 0.10], [-0.02, 0.12, 0.90]]  # rows sum to 1
    gain = (0.55, 0.62, 0.80)  # underexposed, warm
    ref = cm.reference_rec2020()
    camera = [tuple(g * v for g, v in zip(gain, cm.mat_vec(cast, r))) for r in ref]

    pitch, margin = 40, 30
    width, height = margin * 2 + pitch * 6, margin * 2 + pitch * 4

    def pixel(x, y):
        col, row = (x - margin) // pitch, (y - margin) // pitch
        if 0 <= col < 6 and 0 <= row < 4:
            return tuple(cm.apple_log_encode(v) for v in camera[row * 6 + col])
        return (0.1, 0.1, 0.1)

    with tempfile.TemporaryDirectory() as d:
        still = os.path.join(d, "chart.tif")
        write_tiff(still, width, height, pixel)
        c = lambda col, row: f"{margin + pitch * col + pitch // 2},{margin + pitch * row + pitch // 2}"
        out = subprocess.run([sys.executable, os.path.abspath(cm.__file__), "fit", still, "--corners",
                              c(0, 0), c(5, 0), c(5, 3), c(0, 3), "--out", d], capture_output=True, text=True, check=True)
        result = json.loads(out.stdout)
        assert result["before"]["mean"] > 5, result["before"]["mean"]
        assert result["after_predicted"]["mean"] < 0.5, result["after_predicted"]
        assert os.path.exists(result["dctl"]) and os.path.exists(result["lut_transform"])
    print("ok", result["before"]["mean"], "->", result["after_predicted"]["mean"])


if __name__ == "__main__":
    run()
