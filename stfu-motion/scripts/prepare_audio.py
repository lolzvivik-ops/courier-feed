#!/usr/bin/env python3
"""Cut the fragment and bake the pre-drop "dip" → public/generated/track.wav.

    npm run audio      (exports the timeline first)

- Same ffmpeg decode as the beat analysis, sliced sample-accurately at
  AUDIO_START, so the grid in beats.json is exactly the grid you hear.
- Lowpass dip (spec §7): from a 16th after the Do Not Disturb toggle to the
  drop the track is crossfaded into a 380 Hz lowpass (40 ms fade in), then
  snaps back to full band on the drop (6 ms) — the "silence" before the hit.
- The MP3 decodes with overs (+1.9 dBFS on this master), and the master is
  already brickwalled (RMS -4.7 dBFS), so a limiter would work all the time.
  A static gain puts the peak at -1.5 dBFS instead: transparent, and leaves
  room for the UI sounds on top (platforms normalise loudness anyway).
- 3 ms edge fades so the loop point never clicks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import scipy.signal as ss

sys.path.insert(0, str(Path(__file__).parent))
from audio_io import SR, decode, write_wav  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CEILING_DB = -1.5


def s_curve(n: int) -> np.ndarray:
    x = np.linspace(0, 1, n, endpoint=False)
    return 0.5 - 0.5 * np.cos(np.pi * x)


def main() -> None:
    tl = json.loads((ROOT / ".cache" / "timeline.json").read_text())
    start, dur = tl["audioStart"], tl["summary"]["durationSec"]
    full = decode(ROOT / "public" / "stfu.mp3")
    a = int(round(start * SR))
    n = int(round(dur * SR))
    x = full[a:a + n].astype(np.float64)
    if len(x) < n:
        raise SystemExit("track shorter than the fragment")

    # lowpass dip, crossfaded (zero-phase filter so dry/wet stay aligned)
    dip = tl["dip"]
    sos = ss.butter(4, dip["cutoffHz"], "low", fs=SR, output="sos")
    wet = ss.sosfiltfilt(sos, x, axis=0)
    env = np.zeros(n)
    i0, i1 = int(round(dip["start"] * SR)), int(round(dip["end"] * SR))
    fin, fout = int(0.040 * SR), int(0.006 * SR)
    env[i0:i1] = 1.0
    env[i0:i0 + fin] = s_curve(fin)
    env[i1 - fout:i1] = 1 - s_curve(fout)
    y = x * (1 - env[:, None]) + wet * env[:, None] * 10 ** (-1.0 / 20)

    peak_in = 20 * np.log10(np.max(np.abs(y)) + 1e-12)
    gain_db = min(0.0, CEILING_DB - peak_in)
    y *= 10 ** (gain_db / 20)
    edge = int(0.003 * SR)
    y[:edge] *= s_curve(edge)[:, None]
    y[-edge:] *= (1 - s_curve(edge))[:, None]

    out = ROOT / "public" / "generated" / "track.wav"
    write_wav(out, y.astype(np.float32))
    rms = 20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-12)
    peak = 20 * np.log10(np.max(np.abs(y)) + 1e-12)
    print(f"wrote {out.relative_to(ROOT)}: {dur:.3f}s from {start:.4f}s, dip {dip['start']:.3f}-{dip['end']:.3f}s "
          f"({(dip['end'] - dip['start']) * 1000:.0f} ms)")
    print(f"  peak {peak_in:+.2f} dBFS, static gain {gain_db:+.2f} dB -> peak {peak:+.2f} dBFS, RMS {rms:.1f} dBFS")


if __name__ == "__main__":
    main()
