#!/usr/bin/env python3
"""Analyse the track and write src/data/beats.json.

    .venv/bin/python scripts/analyze_beats.py public/stfu.mp3 src/data/beats.json

What it does, in order:
1. librosa gives a first tempo guess; a fine search then fits a constant-tempo
   grid (BPM + phase) to the full-band spectral flux. Trap is made on a DAW grid,
   so a near-integer BPM is snapped when it scores as well.
2. Hi-hats on 8ths make "on the beat" vs "on the and" ambiguous, and the bar
   line is unknown. Both are resolved together: of the 8 possible 8th-note
   phases of the bar, pick the one that puts the biggest energy jumps in the
   song (section entries, the bass drop) exactly on bar lines.
3. Kicks = peaks of low-band (30-150 Hz) flux; onsets = full-band onsets.
4. Section changes per bar (novelty of a bar self-similarity matrix + energy
   lift) give drop candidates; the fragment is placed so the drop lands on
   bar PRE_DROP_BARS and the whole thing is 18-22 s.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import librosa
import numpy as np
import scipy.signal as ss

sys.path.insert(0, str(Path(__file__).parent))
from audio_io import SR, decode  # noqa: E402

HOP = 128  # 2.67 ms at 48 kHz
PRE_DROP_BARS = 6  # scenes before the drop: 1 + 2 + 1 + 2 bars
SCRIPT_BARS = 11  # bars in the script; the last scene absorbs any extra bar
MIN_SEC, MAX_SEC = 18.0, 22.0


def log_flux(y: np.ndarray, lo: float, hi: float, n_fft: int) -> np.ndarray:
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=HOP))
    fr = librosa.fft_frequencies(sr=SR, n_fft=n_fft)
    L = np.log1p(1000 * S[(fr >= lo) & (fr < hi)])
    return np.maximum(0, np.diff(L, axis=1, prepend=L[:, :1])).sum(axis=0)


def grid_score(env: np.ndarray, bpm: float, phase: float, t_end: float) -> float:
    times = np.arange(phase, t_end, 60.0 / bpm)
    idx = np.round(times * SR / HOP).astype(int)
    idx = idx[(idx > 1) & (idx < len(env) - 2)]
    return float(np.maximum.reduce([env[idx - 1], env[idx], env[idx + 1]]).mean())


def fit_grid(env: np.ndarray, bpm0: float, t_end: float) -> tuple[float, float, float]:
    best = (-1.0, bpm0, 0.0)
    for bpm in np.arange(bpm0 * 0.97, bpm0 * 1.03, 0.01):
        period = 60 / bpm
        for ph in np.arange(0, period, 0.002):
            s = grid_score(env, bpm, ph, t_end)
            if s > best[0]:
                best = (s, bpm, ph)
    s, bpm, ph = best
    for b in np.arange(bpm - 0.02, bpm + 0.02, 0.001):
        for p in np.arange(ph - 0.004, ph + 0.004, 0.0002):
            sc = grid_score(env, b, p, t_end)
            if sc > s:
                s, bpm, ph = sc, b, p
    # snap to an integer BPM if it explains the onsets as well (DAW grid)
    ib = round(bpm)
    if abs(bpm - ib) < 0.05:
        p_best = max(np.arange(0, 60 / ib, 0.0002), key=lambda p: grid_score(env, ib, p, t_end))
        s_int = grid_score(env, ib, p_best, t_end)
        if s_int >= 0.995 * s:
            return float(ib), float(p_best), s_int
    return float(bpm), float(ph), s


def energy_jumps(y: np.ndarray, bar: float) -> tuple[np.ndarray, np.ndarray]:
    """dB change of low+broadband energy: next half-bar vs previous half-bar."""
    hop = 256
    rms_lo = librosa.feature.rms(y=ss.sosfiltfilt(ss.butter(4, 150, "low", fs=SR, output="sos"), y),
                                 frame_length=1024, hop_length=hop)[0]
    rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=hop)[0]
    t = librosa.frames_to_time(np.arange(len(rms)), sr=SR, hop_length=hop)
    w = int(bar / 2 * SR / hop)
    db = 10 * np.log10(rms_lo**2 + 1e-10) + 10 * np.log10(rms**2 + 1e-10)
    c = np.concatenate([[0], np.cumsum(db)])
    J = np.zeros_like(db)
    for i in range(w, len(db) - w):
        J[i] = (c[i + w] - c[i]) / w - (c[i] - c[i - w]) / w
    return t, J


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out")
    args = ap.parse_args()

    stereo = decode(args.audio)
    y = stereo.mean(axis=1)
    dur = len(y) / SR
    print(f"decoded {dur:.2f}s @ {SR} Hz")

    # 1. tempo + grid ---------------------------------------------------------
    env_full = log_flux(y, 20, 16000, 1024)
    oenv = librosa.onset.onset_strength(y=y, sr=SR, hop_length=256, aggregate=np.median)
    bpm0 = float(np.atleast_1d(librosa.beat.beat_track(onset_envelope=oenv, sr=SR, hop_length=256)[0])[0])
    bpm, phase, score = fit_grid(env_full, bpm0, dur - 0.1)
    P = 60.0 / bpm
    bar = 4 * P
    print(f"librosa {bpm0:.2f} BPM -> grid {bpm:.3f} BPM, phase {phase:.4f}s, score {score:.1f}")

    # 2. bar phase (8 candidates: which 8th of the bar is the downbeat) ---------
    tj, J = energy_jumps(y, bar)
    pk, _ = ss.find_peaks(np.maximum(J, 0), distance=int(bar * SR / 256))
    top = sorted(pk, key=lambda i: -J[i])[:8]
    jumps = [(float(tj[i]), float(J[i])) for i in top]
    cands = []
    for k in range(8):
        db_phase = phase + k * P / 2
        s = 0.0
        for tt, mag in jumps:
            d = ((tt - db_phase + bar / 2) % bar) - bar / 2  # distance to nearest bar line
            s += mag * np.exp(-(d / 0.03) ** 2)
        cands.append((s, k))
    s_best, k_best = max(cands)
    downbeat_phase = phase + k_best * P / 2
    first_beat = downbeat_phase % P
    first_downbeat = downbeat_phase % bar
    print(f"bar phase: +{k_best} eighths -> first downbeat {first_downbeat:.4f}s "
          f"(jumps used: {[round(t, 3) for t, _ in jumps[:4]]})")

    beats = np.arange(first_beat, dur - 0.05, P)
    downbeats = np.arange(first_downbeat, dur - 0.05, bar)

    # 3. kicks and onsets -------------------------------------------------------
    env_low = log_flux(y, 30, 150, 2048)
    t_env = librosa.frames_to_time(np.arange(len(env_low)), sr=SR, hop_length=HOP)
    med = ss.medfilt(env_low, 301)
    mad = np.median(np.abs(env_low - np.median(env_low)))
    kp, props = ss.find_peaks(env_low, height=med + 6 * mad, distance=int(P / 4 * SR / HOP * 0.9))
    strength = env_low[kp]
    ref = np.percentile(strength, 95) if len(strength) else 1.0
    kicks = []
    for i, st in zip(kp, strength):
        if st < 0.35 * ref:
            continue
        t = float(t_env[i])
        pos16 = (t - first_beat) / (P / 4)
        dev = (pos16 - round(pos16)) * P / 4
        kicks.append({"t": round(t, 4), "s": round(float(st / ref), 3),
                      "beat": round(round(pos16) / 4, 2), "dev": round(dev * 1000, 1)})

    # 5 ms peak windows (pre_max/post_max/wait = 2 hops): librosa's defaults (30 ms)
    # keep only the first hit of a flam and hide the on-beat transient right after a
    # pickup, which then reads as a ~20 ms sync error that isn't there.
    on = librosa.onset.onset_detect(onset_envelope=env_full, sr=SR, hop_length=HOP, units="frames",
                                    backtrack=False, normalize=True, delta=0.07,
                                    pre_max=2, post_max=2, pre_avg=10, post_avg=10, wait=2)
    onsets = [{"t": round(float(i * HOP / SR), 4), "s": round(float(env_full[i] / env_full.max()), 3)}
              for i in on]

    # 4. sections / drop ---------------------------------------------------------
    nbars = int((dur - first_downbeat) / bar)
    bar_t = first_downbeat + bar * np.arange(nbars + 1)
    hop = 512
    C = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=hop)
    M = librosa.feature.mfcc(y=y, sr=SR, hop_length=hop, n_mfcc=20)
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
    fr = librosa.fft_frequencies(sr=SR, n_fft=2048)
    bands = [(20, 120), (120, 800), (800, 5000), (5000, 20000)]
    B = np.stack([10 * np.log10((S[(fr >= a) & (fr < b)] ** 2).sum(axis=0) + 1e-9) for a, b in bands])
    tf = librosa.frames_to_time(np.arange(C.shape[1]), sr=SR, hop_length=hop)

    def barsync(F: np.ndarray) -> np.ndarray:
        return np.array([F[:, (tf >= bar_t[i]) & (tf < bar_t[i + 1])].mean(axis=1) for i in range(nbars)])

    Cb, Mb, Bb = barsync(C), barsync(M), barsync(B)
    z = lambda X: (X - X.mean(0)) / (X.std(0) + 1e-6)  # noqa: E731
    F = np.hstack([z(Cb), z(Mb), z(Bb)])
    F /= np.linalg.norm(F, axis=1, keepdims=True)
    SSM = F @ F.T
    L = 4
    kern = np.ones((2 * L, 2 * L))
    kern[:L, L:] = kern[L:, :L] = -1
    nov = np.zeros(nbars)
    for i in range(L, nbars - L):
        nov[i] = (SSM[i - L:i + L, i - L:i + L] * kern).sum()
    loud = Bb.mean(axis=1)
    lift = np.zeros(nbars)
    for i in range(2, nbars - 2):
        lift[i] = loud[i:i + 2].mean() - loud[i - 2:i].mean()

    # Fragment length: script bars, plus bars on the last scene until >= 18 s.
    total = SCRIPT_BARS
    while total * bar < MIN_SEC:
        total += 1
    while total * bar > MAX_SEC:
        total -= 1
    post = total - PRE_DROP_BARS

    # A drop is a section boundary (local novelty peak) where energy goes UP.
    # Bars next to a big boundary inherit inflated novelty/lift, so only local
    # maxima within +-2 bars count; energy decreases (outros, breakdowns) don't.
    drop_cands = []
    for i in range(nbars):
        lo, hi = max(0, i - 2), min(nbars, i + 3)
        if nov[i] <= 0 or nov[i] < nov[lo:hi].max() or lift[i] < 0.5:
            continue
        fits = i - PRE_DROP_BARS >= 0 and i + post <= nbars
        sc = float(nov[i] / (nov.max() + 1e-9) + lift[i] / (lift.max() + 1e-9))
        drop_cands.append({"bar": i, "t": round(float(bar_t[i]), 4), "novelty": round(float(nov[i]), 2),
                           "lift": round(float(lift[i]), 2), "score": round(sc, 3), "fits": bool(fits)})
    ranked = sorted(drop_cands, key=lambda c: -c["score"])
    drop = next(c for c in ranked if c["fits"])
    start_bar = drop["bar"] - PRE_DROP_BARS
    # Repeated sections: which earlier bars does the drop section copy?
    rep = max(((float(np.mean([SSM[drop["bar"] + k, j + k] for k in range(8)])), j)
               for j in range(0, nbars - 8) if abs(j - drop["bar"]) > 4 and drop["bar"] + 8 <= nbars),
              default=(0.0, -1))
    fragment = {
        "startBar": start_bar,
        "dropBar": drop["bar"],
        "bars": total,
        "preDropBars": PRE_DROP_BARS,
        "AUDIO_START": round(float(bar_t[start_bar]), 5),
        "AUDIO_END": round(float(bar_t[start_bar] + total * bar), 5),
        "DROP": round(float(bar_t[drop["bar"]]), 5),
        "seconds": round(total * bar, 4),
        "dropRepeatsBar": rep[1],
        "dropRepeatSimilarity": round(rep[0], 3),
        "note": "Strongest drop overall: " + ", ".join(
            f"bar {c['bar']} @ {c['t']}s{'' if c['fits'] else ' (not enough bars before it)'}"
            for c in ranked[:3]),
    }
    print("drop candidates:", [(c["bar"], c["t"], c["score"], c["fits"]) for c in ranked[:5]])
    print("fragment:", fragment)

    out = {
        "source": Path(args.audio).name,
        "sampleRate": SR,
        "duration": round(dur, 4),
        "tempo": {"bpm": bpm, "beatPeriod": round(P, 6), "barBeats": 4, "librosaEstimate": round(bpm0, 2),
                  "gridScore": round(score, 2), "feel": f"half-time ({bpm / 2:g} felt), grid counted at {bpm:g}"},
        "grid": {"firstBeat": round(float(first_beat), 5), "firstDownbeat": round(float(first_downbeat), 5),
                 "phaseEighths": k_best,
                 "phaseEvidence": [{"t": round(t, 3), "jumpDb": round(m, 1)} for t, m in jumps]},
        "fragment": fragment,
        "beats": [round(float(b), 5) for b in beats],
        "downbeats": [round(float(b), 5) for b in downbeats],
        "kicks": kicks,
        "onsets": onsets,
        "bars": [{"i": i, "t": round(float(bar_t[i]), 4), "novelty": round(float(nov[i]), 2),
                  "lift": round(float(lift[i]), 2), "bands": [round(float(v), 1) for v in Bb[i]]}
                 for i in range(nbars)],
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {args.out}: {len(beats)} beats, {len(kicks)} kicks, {len(onsets)} onsets")


if __name__ == "__main__":
    main()
