#!/usr/bin/env python3
"""Numeric A/V sync check (spec §4.5).

    npm run sync-report

Every visual event (scene change, word, main event, cue, kick punch) is
rounded to the frame it actually lands on (60 and 30 fps) and compared to the
nearest strong onset detected in the track (full-band onsets from beats.json
with ≥ 30 % of the strongest onset within ±50 ms; kick onsets also count for
the punches). Pass: mean |Δ| < 1 frame at 60 fps (16.7 ms) and
max |Δ| ≤ 20 ms. Events with no onset within 50 ms are listed separately: they
sit on the grid between sounds (e.g. an 8th with no hit) and have nothing to
be late or early against.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
WINDOW = 0.050


def main() -> None:
    tl = json.loads((ROOT / ".cache" / "timeline.json").read_text())
    beats = json.loads((ROOT / "src" / "data" / "beats.json").read_text())
    a0, a1 = tl["audioStart"], tl["audioEnd"]
    sel = [o for o in beats["onsets"] if a0 - 0.1 <= o["t"] <= a1 + 0.1]
    onsets = np.array([o["t"] - a0 for o in sel])
    strength = np.array([o["s"] for o in sel])
    kicks = np.array([k["t"] - a0 for k in beats["kicks"] if a0 - 0.1 <= k["t"] <= a1 + 0.1])

    lines = []
    summary = {}
    for fps in (60, 30):
        devs, by_kind, unmatched = [], {}, []
        for ev in tl["events"]:
            frame_t = round(ev["sec"] * fps) / fps
            # nearest onset among the strong ones around the event (≥ 30 % of the
            # strongest within the window), so a faint ghost note can't win
            near = np.abs(onsets - frame_t) <= WINDOW
            pool = onsets[near & (strength >= 0.3 * strength[near].max())] if near.any() else onsets[:0]
            if ev["kind"] == "punch":  # a punch also counts against the kick onset itself
                pool = np.concatenate([pool, kicks[np.abs(kicks - frame_t) <= WINDOW]])
            if not len(pool):
                unmatched.append(ev)
                continue
            j = int(np.argmin(np.abs(pool - frame_t)))
            d = frame_t - pool[j]
            if abs(d) > WINDOW:
                unmatched.append(ev)
                continue
            devs.append(d)
            by_kind.setdefault(ev["kind"], []).append(d)
            if fps == 60:
                lines.append(f"  {ev['kind']:12s} {ev['sec']:7.3f}s  f{round(ev['sec'] * fps):5d}  Δ {d * 1000:+6.1f} ms  {ev['id']}")
        devs = np.array(devs)
        mean_abs, max_abs = float(np.mean(np.abs(devs)) * 1000), float(np.max(np.abs(devs)) * 1000)
        summary[fps] = (mean_abs, max_abs, float(np.median(devs) * 1000), len(devs), unmatched, by_kind)

    print(f"A/V sync — {len(tl['events'])} events vs {len(onsets)} onsets / {len(kicks)} kicks in the fragment "
          f"(SYNC_OFFSET_MS = {tl['syncOffsetMs']}, visual lead = {tl['leadFrames60']} frame @60)")
    print("\nper event @60 fps (Δ = frame time − nearest onset; negative = picture first):")
    print("\n".join(lines))
    ok = True
    for fps, (mean_abs, max_abs, med, n, unmatched, by_kind) in summary.items():
        frame_ms = 1000 / fps
        print(f"\n@{fps} fps: matched {n}, mean |Δ| {mean_abs:.1f} ms ({mean_abs / frame_ms:.2f} frame), "
              f"max |Δ| {max_abs:.1f} ms, median Δ {med:+.1f} ms")
        for kind, ds in sorted(by_kind.items()):
            ds = np.array(ds) * 1000
            print(f"    {kind:12s} n={len(ds):2d}  mean |Δ| {np.mean(np.abs(ds)):5.1f} ms  max {np.max(np.abs(ds)):5.1f} ms")
        if unmatched:
            print(f"    no onset within {WINDOW * 1000:.0f} ms (grid-only): " + ", ".join(e["id"] for e in unmatched))
        if fps == 60:
            passed = mean_abs < 1000 / 60 and max_abs <= 20.0
            ok &= passed
            print(f"    criteria (mean < 16.7 ms, max ≤ 20 ms): {'PASS' if passed else 'FAIL'}")
            if not passed:
                print(f"    → try SYNC_OFFSET_MS = {-med:.0f} in src/config.ts")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
