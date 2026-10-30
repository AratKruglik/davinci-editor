"""ColorChecker Classic 24 match for Apple Log footage. Pure Python, no numpy/OpenCV.

fit:     python3 chart_match.py fit STILL.tif --corners x1,y1 x2,y2 x3,y3 x4,y4 --out DIR [--name NAME]
measure: python3 chart_match.py measure STILL.tif --corners ... [--log apple-log|linear]

Corners are pixel centers of patches 1 (dark skin), 6 (bluish green), 24 (black), 19 (white),
i.e. top-left, top-right, bottom-right, bottom-left of the chart as it appears in the frame.
The still must be the raw Apple Log signal (all nodes disabled, no RCM), exported as uncompressed TIFF.
"""
import argparse
import json
import math
import os
import struct

# X-Rite ColorChecker Classic, post-Nov-2014 formulation, CIE L*a*b* D50.
REFERENCE_LAB_D50 = [
    (37.54, 14.37, 14.92), (64.66, 19.27, 17.50), (49.32, -3.82, -22.54), (43.46, -12.74, 22.72),
    (54.94, 9.61, -24.79), (70.48, -32.26, -0.37), (62.73, 35.83, 56.50), (39.43, 10.75, -45.17),
    (50.57, 48.64, 16.67), (30.10, 22.54, -20.87), (71.77, -24.13, 58.19), (71.51, 18.24, 67.37),
    (28.37, 15.42, -49.80), (54.38, -39.72, 32.27), (42.43, 51.05, 28.62), (81.80, 2.67, 80.41),
    (50.63, 51.28, -14.12), (49.57, -29.71, -28.32), (95.19, -1.03, 2.93), (81.29, -0.57, 0.44),
    (66.89, -0.75, -0.06), (50.76, -0.13, 0.14), (35.63, -0.46, -0.48), (20.64, 0.07, -0.46),
]
PATCH_NAMES = [
    "dark skin", "light skin", "blue sky", "foliage", "blue flower", "bluish green",
    "orange", "purplish blue", "moderate red", "purple", "yellow green", "orange yellow",
    "blue", "green", "red", "yellow", "magenta", "cyan",
    "white", "neutral 8", "neutral 6.5", "neutral 5", "neutral 3.5", "black",
]
GREY_FOR_BALANCE = [19, 20, 21, 22]  # neutral 8..3.5; white may clip, black is noisy
WHITE_D50 = (0.96422, 1.0, 0.82521)
WHITE_D65 = (0.95047, 1.0, 1.08883)
BRADFORD_D50_TO_D65 = [[0.9555766, -0.0230393, 0.0631636], [-0.0282895, 1.0099416, 0.0210077], [0.0122982, -0.0204830, 1.3299098]]
REC2020_TO_XYZ = [[0.6369580, 0.1446169, 0.1688810], [0.2627002, 0.6779981, 0.0593017], [0.0, 0.0280727, 1.0609851]]
XYZ_TO_REC2020 = [[1.7166512, -0.3556708, -0.2533663], [-0.6666844, 1.6164812, 0.0157685], [0.0176399, -0.0427706, 0.9421031]]

# Apple Log, from Apple's "Apple Log Profile" white paper.
AL_R0, AL_RT, AL_C, AL_B, AL_G, AL_D = -0.05641088, 0.01, 47.28711236, 0.00964052, 0.08550479, 0.69336945
AL_PT = AL_C * (AL_RT - AL_R0) ** 2


def apple_log_decode(x):
    if x >= AL_PT:
        return 2 ** ((x - AL_D) / AL_G) - AL_B
    if x >= 0:
        return math.sqrt(x / AL_C) + AL_R0
    return AL_R0


def apple_log_encode(r):
    if r >= AL_RT:
        return AL_G * math.log2(r + AL_B) + AL_D
    if r >= AL_R0:
        return AL_C * (r - AL_R0) ** 2
    return 0.0


def mat_vec(m, v):
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def lab_to_xyz(lab, white):
    L, a, b = lab
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200
    inv = lambda t: t ** 3 if t ** 3 > 216 / 24389 else (116 * t - 16) / (24389 / 27)
    return (white[0] * inv(fx), white[1] * inv(fy), white[2] * inv(fz))


def xyz_to_lab(xyz, white):
    f = lambda t: t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = (f(xyz[i] / white[i]) for i in range(3))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def reference_rec2020():
    return [mat_vec(XYZ_TO_REC2020, mat_vec(BRADFORD_D50_TO_D65, lab_to_xyz(lab, WHITE_D50))) for lab in REFERENCE_LAB_D50]


def reference_lab_d65():
    return [xyz_to_lab(mat_vec(BRADFORD_D50_TO_D65, lab_to_xyz(lab, WHITE_D50)), WHITE_D65) for lab in REFERENCE_LAB_D50]


def rec2020_to_lab(rgb):
    return xyz_to_lab(mat_vec(REC2020_TO_XYZ, rgb), WHITE_D65)


def delta_e2000(lab1, lab2):
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    c_bar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(c_bar ** 7 / (c_bar ** 7 + 25 ** 7)))
    a1p, a2p = a1 * (1 + g), a2 * (1 + g)
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360
    h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dl, dc = L2 - L1, c2p - c1p
    dh = 0.0
    if c1p * c2p:
        dh = h2p - h1p
        dh = dh - 360 if dh > 180 else dh + 360 if dh < -180 else dh
    dH = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2))
    l_bar, cp_bar = (L1 + L2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        h_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_bar = (h1p + h2p) / 2
    else:
        h_bar = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(h_bar - 30)) + 0.24 * math.cos(math.radians(2 * h_bar))
         + 0.32 * math.cos(math.radians(3 * h_bar + 6)) - 0.20 * math.cos(math.radians(4 * h_bar - 63)))
    sl = 1 + 0.015 * (l_bar - 50) ** 2 / math.sqrt(20 + (l_bar - 50) ** 2)
    sc = 1 + 0.045 * cp_bar
    sh = 1 + 0.015 * cp_bar * t
    rt = -2 * math.sqrt(cp_bar ** 7 / (cp_bar ** 7 + 25 ** 7)) * math.sin(math.radians(60 * math.exp(-(((h_bar - 275) / 25) ** 2))))
    return math.sqrt((dl / sl) ** 2 + (dc / sc) ** 2 + (dH / sh) ** 2 + rt * (dc / sc) * (dH / sh))


def read_tiff(path):
    """Uncompressed, chunky, 8/16-bit RGB(A) baseline TIFF. Returns (width, height, pixel(x, y) -> (r, g, b) in 0..1)."""
    with open(path, "rb") as f:
        data = f.read()
    endian = {b"II": "<", b"MM": ">"}.get(data[:2])
    if not endian or struct.unpack(endian + "H", data[2:4])[0] != 42:
        raise SystemExit(f"{path}: not a classic TIFF; export the still as .tif")
    (ifd,) = struct.unpack(endian + "I", data[4:8])
    (count,) = struct.unpack(endian + "H", data[ifd:ifd + 2])
    sizes = {1: 1, 3: 2, 4: 4}
    tags = {}
    for i in range(count):
        tag, typ, n, raw = struct.unpack(endian + "HHI4s", data[ifd + 2 + 12 * i: ifd + 14 + 12 * i])
        fmt = {1: "B", 3: "H", 4: "I"}.get(typ)
        if not fmt:
            continue
        blob = raw if n * sizes[typ] <= 4 else data[struct.unpack(endian + "I", raw)[0]:][: n * sizes[typ]]
        tags[tag] = struct.unpack(endian + fmt * n, blob[: n * sizes[typ]])
    width, height = tags[256][0], tags[257][0]
    bits = tags.get(258, (8,))[0]
    compression = tags.get(259, (1,))[0]
    spp = tags.get(277, (1,))[0]
    planar = tags.get(284, (1,))[0]
    if compression != 1 or planar != 1 or spp < 3 or bits not in (8, 16):
        raise SystemExit(f"{path}: unsupported TIFF (compression={compression}, planar={planar}, spp={spp}, bits={bits}); "
                         "export an uncompressed 8/16-bit RGB TIFF")
    rows_per_strip = tags.get(278, (height,))[0]
    offsets = tags[273]
    bpp = spp * bits // 8
    row_bytes = width * bpp
    sample_fmt = endian + ("B" if bits == 8 else "H") * 3
    scale = (1 << bits) - 1

    def pixel(x, y):
        strip, row = divmod(y, rows_per_strip)
        pos = offsets[strip] + row * row_bytes + x * bpp
        r, g, b = struct.unpack(sample_fmt, data[pos:pos + 3 * bits // 8])
        return (r / scale, g / scale, b / scale)

    return width, height, pixel


def patch_centers(corners):
    (x1, y1), (x2, y2), (x3, y3), (x4, y4) = corners
    centers = []
    for row in range(4):
        v = row / 3
        for col in range(6):
            u = col / 5
            x = (1 - u) * (1 - v) * x1 + u * (1 - v) * x2 + u * v * x3 + (1 - u) * v * x4
            y = (1 - u) * (1 - v) * y1 + u * (1 - v) * y2 + u * v * y3 + (1 - u) * v * y4
            centers.append((x, y))
    return centers


def sample_patches(pixel, width, height, corners):
    centers = patch_centers(corners)
    pitch = min(math.dist(corners[0], corners[1]) / 5, math.dist(corners[0], corners[3]) / 3)
    half = max(1, int(pitch * 0.2))
    step = max(1, half // 6)
    patches = []
    for cx, cy in centers:
        values = [pixel(min(width - 1, max(0, int(cx) + dx)), min(height - 1, max(0, int(cy) + dy)))
                  for dx in range(-half, half + 1, step) for dy in range(-half, half + 1, step)]
        mean = tuple(sum(v[c] for v in values) / len(values) for c in range(3))
        spread = max(math.sqrt(sum((v[c] - mean[c]) ** 2 for v in values) / len(values)) for c in range(3))
        patches.append({"code": mean, "spread": spread, "center": (round(cx), round(cy))})
    return patches


def solve_row_constrained(xs, ys):
    """Least squares for m (3,) with m0+m1+m2 = 1, so neutrals stay neutral: y - x2 = m0 (x0 - x2) + m1 (x1 - x2)."""
    a = [(x[0] - x[2], x[1] - x[2]) for x in xs]
    t = [y - x[2] for x, y in zip(xs, ys)]
    s00 = sum(p * p for p, _ in a)
    s01 = sum(p * q for p, q in a)
    s11 = sum(q * q for _, q in a)
    t0 = sum(p * v for (p, _), v in zip(a, t))
    t1 = sum(q * v for (_, q), v in zip(a, t))
    det = s00 * s11 - s01 * s01
    m0 = (t0 * s11 - t1 * s01) / det
    m1 = (s00 * t1 - s01 * t0) / det
    return [m0, m1, 1 - m0 - m1]


def fit(linear, usable):
    ref = reference_rec2020()
    greys = [i for i in GREY_FOR_BALANCE if i in usable]
    gains = [sum(ref[i][c] * linear[i][c] for i in greys) / sum(linear[i][c] ** 2 for i in greys) for c in range(3)]
    balanced = [tuple(v[c] * gains[c] for c in range(3)) for v in linear]
    idx = [i for i in usable if i != 23]
    matrix = [solve_row_constrained([balanced[i] for i in idx], [ref[i][c] for i in idx]) for c in range(3)]
    return mat_mul(matrix, [[gains[0], 0, 0], [0, gains[1], 0], [0, 0, gains[2]]]), gains


def report(linear, transform=None):
    ref_lab = reference_lab_d65()
    rows = []
    for i, v in enumerate(linear):
        out = mat_vec(transform, v) if transform else v
        rows.append({"patch": i + 1, "name": PATCH_NAMES[i], "delta_e": round(delta_e2000(rec2020_to_lab(out), ref_lab[i]), 2)})
    des = [r["delta_e"] for r in rows]
    return {"mean": round(sum(des) / len(des), 2), "max": round(max(des), 2), "patches": rows}


def dctl_source(m):
    row = lambda i, v: " + ".join(f"({m[i][j]:.8f}f) * {c}" for j, c in enumerate(v))
    return f"""// Generated by davinci-editor chart-match. Apple Log in -> Apple Log out, correction in linear Rec.2020.
__DEVICE__ float al_decode(float x) {{
    if (x >= {AL_PT:.8f}f) return _exp2f((x - {AL_D}f) / {AL_G}f) - {AL_B}f;
    if (x >= 0.0f) return _sqrtf(x / {AL_C}f) + ({AL_R0}f);
    return {AL_R0}f;
}}

__DEVICE__ float al_encode(float r) {{
    if (r >= {AL_RT}f) return {AL_G}f * _log2f(r + {AL_B}f) + {AL_D}f;
    if (r >= ({AL_R0}f)) return {AL_C}f * (r - ({AL_R0}f)) * (r - ({AL_R0}f));
    return 0.0f;
}}

__DEVICE__ float3 transform(int p_Width, int p_Height, int p_X, int p_Y, float p_R, float p_G, float p_B)
{{
    float r = al_decode(p_R), g = al_decode(p_G), b = al_decode(p_B);
    float ro = {row(0, "rgb")};
    float go = {row(1, "rgb")};
    float bo = {row(2, "rgb")};
    return make_float3(al_encode(ro), al_encode(go), al_encode(bo));
}}
"""


def lut_transform_body(m):
    return f"""M = {json.dumps([[round(v, 8) for v in r] for r in m])}
def dec(x):
    if x >= {AL_PT!r}: return 2 ** ((x - {AL_D!r}) / {AL_G!r}) - {AL_B!r}
    if x >= 0: return math.sqrt(x / {AL_C!r}) + {AL_R0!r}
    return {AL_R0!r}
def enc(v):
    if v >= {AL_RT!r}: return {AL_G!r} * math.log2(v + {AL_B!r}) + {AL_D!r}
    if v >= {AL_R0!r}: return {AL_C!r} * (v - {AL_R0!r}) ** 2
    return 0.0
lin = (dec(r), dec(g), dec(b))
out = [sum(M[i][j] * lin[j] for j in range(3)) for i in range(3)]
return tuple(min(1.0, max(0.0, enc(v))) for v in out)
"""


def load(args):
    width, height, pixel = read_tiff(args.still)
    corners = [tuple(float(v) for v in c.split(",")) for c in args.corners]
    patches = sample_patches(pixel, width, height, corners)
    decode = apple_log_decode if args.log == "apple-log" else (lambda v: v)
    linear = [tuple(decode(v) for v in p["code"]) for p in patches]
    warnings = []
    usable = []
    for i, p in enumerate(patches):
        if max(p["code"]) > 0.97:
            warnings.append(f"patch {i + 1} ({PATCH_NAMES[i]}) clipped")
        elif p["spread"] > 0.04:
            warnings.append(f"patch {i + 1} ({PATCH_NAMES[i]}) not uniform (spread {p['spread']:.3f}): check corners")
        else:
            usable.append(i)
    if len([i for i in GREY_FOR_BALANCE if i in usable]) < 3:
        raise SystemExit("fewer than 3 usable grey patches: check corners, exposure and that the still is ungraded log")
    return patches, linear, usable, warnings


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["fit", "measure", "selftest"])
    p.add_argument("still", nargs="?")
    p.add_argument("--corners", nargs=4)
    p.add_argument("--log", choices=["apple-log", "linear"], default="apple-log")
    p.add_argument("--out", default=".")
    p.add_argument("--name", default="chart-match")
    args = p.parse_args()
    if args.mode == "selftest":
        from test_chart_match import run
        run()
        return
    patches, linear, usable, warnings = load(args)
    result = {"warnings": warnings, "usable_patches": [i + 1 for i in usable],
              "centers": [pt["center"] for pt in patches], "before": report(linear)}
    if args.mode == "fit":
        transform, gains = fit(linear, usable)
        result["gains"] = [round(g, 5) for g in gains]
        result["matrix"] = [[round(v, 6) for v in r] for r in transform]
        result["after_predicted"] = report(linear, transform)
        os.makedirs(args.out, exist_ok=True)
        dctl_path = os.path.join(args.out, args.name + ".dctl")
        lut_path = os.path.join(args.out, args.name + ".lut-transform.py")
        with open(dctl_path, "w") as f:
            f.write(dctl_source(transform))
        with open(lut_path, "w") as f:
            f.write(lut_transform_body(transform))
        result["dctl"] = dctl_path
        result["lut_transform"] = lut_path
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
