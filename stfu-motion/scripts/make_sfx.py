#!/usr/bin/env python3
"""Synthesize the UI sounds → public/sfx/*.wav (48 kHz, 16-bit).

No Apple sounds and no samples: everything is generated here from sines,
noise and envelopes, seeded, so it is reproducible and free to use.
Each file is loudness-normalised: its *active* RMS (5 ms frames within
20 dB of the sound's own peak) is set to SFX_REF_DBFS, so a gain of -23 dB
in src/timeline.ts really means "23 dB under the track" (the track's RMS is
TRACK_RMS_DBFS in src/config.ts). Peaks are capped at -1 dBFS.
A sound's transient sits at t = 0 unless the timeline gives it a `pre`.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import scipy.signal as ss
from scipy.io import wavfile

SR = 48_000
SFX_REF_DBFS = -20.0
OUT = Path(__file__).resolve().parent.parent / "public" / "sfx"
rng = np.random.default_rng(47)


def t_axis(sec: float) -> np.ndarray:
    return np.arange(int(sec * SR)) / SR


def sweep(f0: float, f1: float, sec: float, curve: float = 1.0) -> np.ndarray:
    """Sine with an exponential-ish pitch glide (phase-accurate)."""
    t = t_axis(sec)
    k = (t / sec) ** curve
    f = f0 * (f1 / f0) ** k
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def env_ad(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-np.maximum(0, t - attack) / decay)


def band(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    return ss.sosfilt(ss.butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def click(sec: float = 0.004, lo: float = 2500, hi: float = 9000) -> np.ndarray:
    n = int(sec * SR)
    return band(rng.standard_normal(n), lo, hi) * env_ad(n, 0.0003, sec / 4)


def pad(x: np.ndarray, sec: float) -> np.ndarray:
    n = int(sec * SR)
    return np.pad(x, (0, max(0, n - len(x))))[:n]


def place(dst: np.ndarray, src: np.ndarray, at: float, gain: float = 1.0) -> None:
    i = int(at * SR)
    m = min(len(src), len(dst) - i)
    if m > 0:
        dst[i:i + m] += gain * src[:m]


def pop() -> np.ndarray:  # icon jump: an upward "bloop"
    n = 0.2
    body = sweep(330, 820, 0.09, 0.8)
    x = pad(body * env_ad(len(body), 0.002, 0.045), n)
    place(x, click(0.003, 1500, 6000), 0, 0.35)
    return x


def roll() -> np.ndarray:  # badge rolling 1 → 47: ticks that slow down (quartic ease-out)
    dur = 0.42
    x = np.zeros(int(0.5 * SR))
    for k in range(1, 47):
        p = 1 - (1 - k / 46) ** 0.25  # inverse of 1-(1-x)^4
        tick = sweep(3600, 3000, 0.006) * env_ad(int(0.006 * SR), 0.0002, 0.0018)
        place(x, tick, p * dur, 0.55 + 0.45 * (k / 46))
    return x


def swoosh() -> np.ndarray:  # container morph: airy swell peaking at 140 ms
    sec, peak = 0.32, 0.14
    noise = rng.standard_normal(int(sec * SR))
    t = t_axis(sec)
    f = 700 * (5000 / 700) ** np.clip(t / peak, 0, 1)
    y = np.zeros_like(noise)
    zi = None
    for i in range(0, len(noise), 256):  # piecewise band sweep
        sos = ss.butter(2, [f[i] * 0.7, min(f[i] * 1.4, 20000)], "band", fs=SR, output="sos")
        if zi is None:
            zi = ss.sosfilt_zi(sos) * 0
        y[i:i + 256], zi = ss.sosfilt(sos, noise[i:i + 256], zi=zi)
    e = np.where(t < peak, (t / peak) ** 2.2, np.exp(-(t - peak) / 0.05))
    return y * e


def bubble() -> np.ndarray:  # message in: two soft partials, quick upward blip
    n = 0.16
    a = sweep(880, 1320, 0.11, 0.35)
    b = sweep(1320, 1980, 0.11, 0.35)
    body = (a + 0.35 * b) * env_ad(len(a), 0.0015, 0.032)
    x = pad(body, n)
    place(x, click(0.002, 3000, 9000), 0, 0.2)
    return x


def buzz() -> np.ndarray:  # missed call: a short phone vibration
    sec = 0.17
    t = t_axis(sec)
    saw = ss.sawtooth(2 * np.pi * 168 * t) + 0.5 * np.sin(2 * np.pi * 336 * t)
    lp = ss.sosfilt(ss.butter(2, 900, "low", fs=SR, output="sos"), saw)
    e = np.clip(t / 0.01, 0, 1) * np.clip((sec - t) / 0.04, 0, 1) * (0.75 + 0.25 * np.sin(2 * np.pi * 26 * t))
    return lp * e


def toggle() -> np.ndarray:  # switch: knob leaves (soft) and lands (crisper), 38 ms apart
    x = np.zeros(int(0.12 * SR))
    place(x, click(0.004, 1800, 7000), 0.0, 0.55)
    land = pad(click(0.005, 2200, 9000), 0.012) + 0.6 * sweep(2100, 1900, 0.012) * env_ad(int(0.012 * SR), 0.0005, 0.003)
    place(x, land, 0.038, 1.0)
    return x


def impact() -> np.ndarray:  # the drop: sub thump + dark noise burst
    sec = 0.7
    sub = sweep(120, 38, 0.45, 0.6)
    sub = pad(sub * env_ad(len(sub), 0.002, 0.16), sec)
    n = rng.standard_normal(int(sec * SR))
    burst = ss.sosfilt(ss.butter(2, 1800, "low", fs=SR, output="sos"), n) * env_ad(len(n), 0.001, 0.05)
    x = sub + 0.45 * burst
    place(x, click(0.004, 800, 5000), 0, 0.5)
    return x


def press() -> np.ndarray:  # alert button: a soft thock
    n = 0.12
    body = sweep(520, 380, 0.06) * env_ad(int(0.06 * SR), 0.001, 0.014)
    x = pad(body, n)
    place(x, click(0.003, 1200, 5000), 0, 0.5)
    return x


def collapse() -> np.ndarray:  # alert implodes: a reversed whoosh, sucked inwards (peaks at 60 ms)
    w = swoosh()[::-1]
    peak = int(np.argmax(np.abs(w)))
    return w[max(0, peak - int(0.06 * SR)):peak + int(0.03 * SR)]


def burst() -> np.ndarray:  # badge pops: a bubble pop and a few sparks
    x = np.zeros(int(0.3 * SR))
    pop_ = sweep(1500, 620, 0.05, 0.5) * env_ad(int(0.05 * SR), 0.0008, 0.012)
    place(x, pop_, 0, 1.0)
    place(x, click(0.003, 2000, 10000), 0, 0.6)
    for i, at in enumerate([0.035, 0.06, 0.09, 0.13]):
        f = 4200 + 900 * i
        place(x, sweep(f, f * 0.9, 0.012) * env_ad(int(0.012 * SR), 0.0004, 0.003), at, 0.25 / (1 + i * 0.4))
    return x


SOUNDS = {
    "pop": pop, "roll": roll, "swoosh": swoosh, "bubble": bubble, "buzz": buzz, "toggle": toggle,
    "impact": impact, "press": press, "collapse": collapse, "burst": burst,
}


def active_rms(x: np.ndarray) -> float:
    """RMS over 5 ms frames that are within 20 dB of the loudest frame."""
    f = int(0.005 * SR)
    n = len(x) // f
    fr = np.sqrt(np.mean(x[: n * f].reshape(n, f) ** 2, axis=1))
    on = fr > fr.max() * 0.1
    return float(np.sqrt(np.mean(fr[on] ** 2)))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in SOUNDS.items():
        x = np.asarray(fn(), dtype=np.float64)
        fade = int(0.004 * SR)
        x[-fade:] *= np.linspace(1, 0, fade)
        x *= 10 ** (SFX_REF_DBFS / 20) / active_rms(x)
        peak = np.max(np.abs(x))
        note = ""
        if peak > 10 ** (-1 / 20):
            x *= 10 ** (-1 / 20) / peak
            note = f"  (peak-capped: {20 * np.log10(active_rms(x)) - SFX_REF_DBFS:+.1f} dB vs ref)"
        wavfile.write(OUT / f"{name}.wav", SR, (x * 32767).astype(np.int16))
        print(f"sfx/{name}.wav  {len(x) / SR * 1000:4.0f} ms  peak {20 * np.log10(np.max(np.abs(x))):6.1f} dBFS{note}")


if __name__ == "__main__":
    main()
