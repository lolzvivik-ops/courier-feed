#!/usr/bin/env python3
"""Check the rendered mix: clipping, and how far each UI sound sits under the track.

    .venv/bin/python scripts/check_mix.py out/mix_check.wav

mix − prepared track = the UI sounds alone (Remotion sums the layers), so each
sound's level is measured against the music in the same 100 ms window.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from audio_io import SR, decode  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def db(x: float) -> float:
    return 20 * np.log10(max(x, 1e-12))


def main() -> None:
    mix = decode(sys.argv[1] if len(sys.argv) > 1 else ROOT / "out" / "mix_check.wav").astype(np.float64)
    track = decode(ROOT / "public" / "generated" / "track.wav").astype(np.float64)
    n = min(len(mix), len(track))
    mix, track = mix[:n], track[:n]
    sfx = mix - track
    tl = json.loads((ROOT / ".cache" / "timeline.json").read_text())

    peak = np.max(np.abs(mix))
    clipped = int(np.sum(np.abs(mix) >= 0.9999))
    print(f"mix: peak {db(peak):+.2f} dBFS, RMS {db(np.sqrt(np.mean(mix ** 2))):.1f} dBFS, clipped samples: {clipped}")
    print(f"track residual outside SFX windows (should be ~silent): ", end="")
    mask = np.ones(n, bool)
    for s in tl["sfx"]:
        a = int(max(0, s["startSec"] - 0.02) * SR)
        mask[a:a + int(0.9 * SR)] = False
    print(f"{db(np.sqrt(np.mean(sfx[mask] ** 2))) if mask.any() else float('nan'):.1f} dBFS")

    print(f"{'sound':16s} {'at (s)':>7s} {'onset err':>9s} {'sfx':>7s} {'track':>7s} {'rel':>6s}")
    rels = []
    for s in tl["sfx"]:
        a = int(max(0, s["startSec"] - 0.03) * SR)
        b = a + int(0.25 * SR)
        e = np.max(np.abs(sfx[a:b]), axis=1)
        if e.max() < 1e-6:
            print(f"{s['id']:16s} MISSING")
            continue
        on = a + int(np.argmax(e > 0.1 * e.max()))
        # active RMS of the sound (5 ms frames within 20 dB of its peak) vs the music over the same frames
        f = int(0.005 * SR)
        seg = sfx[a:b]
        k = len(seg) // f
        fr = np.sqrt(np.mean(seg[: k * f].reshape(k, f, 2) ** 2, axis=(1, 2)))
        act = fr > fr.max() * 0.1
        rs = np.sqrt(np.mean(fr[act] ** 2))
        trk = track[a:b][: k * f].reshape(k, f, 2)
        rt = np.sqrt(np.mean(trk[act] ** 2))
        rel = db(rs) - db(rt)
        rels.append(rel)
        # expected transient time = event time (startSec is the file start incl. pre-roll)
        err = (on / SR - s["startSec"]) * 1000
        print(f"{s['id']:16s} {s['sec']:7.3f} {err:+8.1f}ms {db(rs):6.1f} {db(rt):6.1f} {rel:+6.1f} dB")
    if rels:
        print(f"UI sounds sit {-max(rels):.1f} … {-min(rels):.1f} dB under the music (target 20–26 dB)")
    if clipped:
        raise SystemExit("CLIPPING")


if __name__ == "__main__":
    main()
