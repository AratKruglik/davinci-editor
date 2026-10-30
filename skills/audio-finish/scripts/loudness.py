"""Integrated loudness (ITU-R BS.1770-4 / EBU R128) and sample peak of a PCM WAV mixdown. Pure Python.

python3 loudness.py measure MIX.wav [--target -14] [--ceiling -1]
python3 loudness.py selftest

shortcut: reports sample peak, not 4x-oversampled true peak (can read up to ~0.5 dB low); the skill keeps 0.5 dB
extra headroom. Upgrade to an oversampling true-peak meter if mixes start failing a platform's true-peak check.
"""
import argparse
import array
import json
import math
import sys
import wave

BLOCK_S, STEP_S = 0.4, 0.1
ABS_GATE, REL_GATE = -70.0, -10.0
# 48 kHz K-weighting coefficients straight from BS.1770-4 (stage 1 shelf, stage 2 high-pass).
SPEC_48K = [([1.53512485958697, -2.69169618940638, 1.19839281085285], [-1.69065929318241, 0.73248077421585]),
            ([1.0, -2.0, 1.0], [-1.99004745483398, 0.99007225036621])]


def k_filters(rate):
    return SPEC_48K if rate == 48000 else k_filters_formula(rate)


def k_filters_formula(rate):
    """Biquads (b, [a1, a2]) for any rate, derived from the filters' analog parameters."""
    f0, gain, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = math.tan(math.pi * f0 / rate)
    vh = 10 ** (gain / 20)
    vb = vh ** 0.4996667741545416
    a0 = 1 + k / q + k * k
    shelf = ([(vh + vb * k / q + k * k) / a0, 2 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0],
             [2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0])
    f0, q = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * f0 / rate)
    a0 = 1 + k / q + k * k
    highpass = ([1.0, -2.0, 1.0], [2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0])
    return [shelf, highpass]


def decode(raw, width, ch):
    """Interleaved integer PCM bytes -> per-channel float lists in -1..1."""
    if width == 3:
        wide = bytearray(len(raw) // 3 * 4)
        wide[1::4], wide[2::4], wide[3::4] = raw[0::3], raw[1::3], raw[2::3]
        raw, width = bytes(wide), 4
    samples = array.array({2: "h", 4: "i"}[width], raw)
    if sys.byteorder == "big":
        samples.byteswap()
    scale = float(1 << (8 * width - 1))
    return [[s / scale for s in samples[c::ch]] for c in range(ch)]


def channel_weights(n):
    if n == 6:
        return [1.0, 1.0, 1.0, 0.0, 1.41, 1.41]  # L R C LFE Ls Rs
    return [1.0] * n


class Meter:
    """Streaming K-weighted meter: feed chunks whose length is a multiple of 100 ms; keeps only per-100 ms powers."""

    def __init__(self, rate, channels):
        self.rate, self.step = rate, int(rate * STEP_S)
        self.filters = k_filters(rate)
        self.weights = channel_weights(channels)
        self.state = [[[0.0] * 4 for _ in self.filters] for _ in range(channels)]
        self.subs, self.peak, self.frames = [], 0.0, 0

    def feed(self, channels):
        n = len(channels[0]) // self.step * self.step
        self.frames += n
        powers = []
        for c, x in enumerate(channels):
            x = x[:n]
            self.peak = max(self.peak, max(map(abs, x), default=0.0))
            for stage, ((b0, b1, b2), (a1, a2)) in enumerate(self.filters):
                x1, x2, y1, y2 = self.state[c][stage]
                y = [0.0] * n
                for i, v in enumerate(x):
                    out = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
                    x2, x1, y2, y1 = x1, v, y1, out
                    y[i] = out
                self.state[c][stage] = [x1, x2, y1, y2]
                x = y
            powers.append([sum(v * v for v in x[i:i + self.step]) / self.step for i in range(0, n, self.step)])
        self.subs += [sum(w * p[i] for w, p in zip(self.weights, powers)) for i in range(len(powers[0]))]

    def integrated(self):
        per_block = round(BLOCK_S / STEP_S)
        blocks = [sum(self.subs[i:i + per_block]) / per_block for i in range(len(self.subs) - per_block + 1)]
        loud = lambda z: -0.691 + 10 * math.log10(z) if z > 0 else -math.inf
        gated = [z for z in blocks if loud(z) > ABS_GATE]
        if not gated:
            return -math.inf
        relative = loud(sum(gated) / len(gated)) + REL_GATE
        gated = [z for z in gated if loud(z) > relative]
        return loud(sum(gated) / len(gated))


def integrated(rate, channels):
    meter = Meter(rate, len(channels))
    meter.feed(channels)
    return meter.integrated()


def measure(path, target=None, ceiling=None):
    with wave.open(path) as w:
        ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        if width not in (2, 3, 4):
            raise SystemExit(f"{path}: {width * 8}-bit PCM not supported; render 16/24/32-bit integer WAV")
        meter = Meter(rate, ch)
        chunk = meter.step * 50  # 5 s per read keeps memory flat for any length
        while True:
            raw = w.readframes(chunk)
            if not raw:
                break
            meter.feed(decode(raw, width, ch))
    lufs = meter.integrated()
    peak_db = 20 * math.log10(meter.peak) if meter.peak > 0 else -math.inf
    out = {"file": path, "rate": rate, "channels": ch, "duration_s": round(meter.frames / rate, 2),
           "integrated_lufs": round(lufs, 2), "sample_peak_dbfs": round(peak_db, 2)}
    if target is not None and math.isfinite(lufs):
        out["gain_to_target_db"] = round(target - lufs, 2)
        if ceiling is not None:
            out["peak_after_gain_dbfs"] = round(peak_db + out["gain_to_target_db"], 2)
            out["needs_limiter"] = out["peak_after_gain_dbfs"] > ceiling - 0.5
    return out


def selftest():
    import os
    import tempfile
    rate, amp = 48000, 10 ** (-23 / 20)
    tone = [amp * math.sin(2 * math.pi * 1000 * n / rate) for n in range(rate * 5)]
    lufs = integrated(rate, [tone, tone])
    assert abs(lufs + 23) < 0.15, lufs  # EBU Tech 3341 case 1: stereo 1 kHz at -23 dBFS reads -23 LUFS
    with_silence = integrated(rate, [tone + [0.0] * rate * 5, tone + [0.0] * rate * 5])
    assert abs(with_silence - lufs) < 0.2, with_silence  # silence is gated out; only the blocks straddling the edge count
    for (b, a), (sb, sa) in zip(k_filters_formula(48000), SPEC_48K):
        assert all(abs(x - y) < 1e-6 for x, y in zip(b + a, sb + sa)), (b, a, sb, sa)
    tone44 = [amp * math.sin(2 * math.pi * 1000 * n / 44100) for n in range(44100 * 5)]
    assert abs(integrated(44100, [tone44, tone44]) + 23) < 0.15
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.wav")
        with wave.open(path, "w") as w:
            w.setnchannels(2), w.setsampwidth(3), w.setframerate(rate)
            frames = bytearray()
            for v in tone[: rate * 2]:
                frames += int(v * 8388607).to_bytes(3, "little", signed=True) * 2
            w.writeframes(bytes(frames))
        m = measure(path, target=-14, ceiling=-1)
        assert abs(m["integrated_lufs"] + 23) < 0.15 and abs(m["sample_peak_dbfs"] + 23) < 0.05, m
        assert abs(m["gain_to_target_db"] - 9) < 0.15 and m["needs_limiter"] is False, m
    print("loudness selftest ok")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["measure", "selftest"])
    p.add_argument("wav", nargs="?")
    p.add_argument("--target", type=float)
    p.add_argument("--ceiling", type=float)
    a = p.parse_args()
    if a.mode == "selftest":
        selftest()
    else:
        print(json.dumps(measure(a.wav, a.target, a.ceiling), indent=1))
