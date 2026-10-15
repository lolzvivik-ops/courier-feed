#!/usr/bin/env python3
"""Find stretches where the picture doesn't move (spec §10: none longer than 0.5 s).

    .venv/bin/python scripts/check_static.py out/preview_540x960.mp4

Frames are averaged down to 54x96 (which also averages the film grain away) and
compared to the previous frame; a frame is "static" when the mean change is below
0.05 levels.
"""
import subprocess
import sys

import numpy as np

path = sys.argv[1]
probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip()
num, den = map(int, probe.split("/"))
fps = num / den
w, h = 54, 96
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={w}:{h}:flags=area", "-f", "rawvideo",
                      "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
diff = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
static = diff < 0.05
runs, start = [], None
for i, s in enumerate(np.append(static, False)):
    if s and start is None:
        start = i
    elif not s and start is not None:
        runs.append((start + 1, i, (i - start) / fps))
        start = None
longest = max(runs, key=lambda r: r[2]) if runs else None
print(f"{len(frames)} frames @ {fps:g} fps; static runs: {len(runs)}; "
      f"longest: {longest[2]:.3f}s (frames {longest[0]}-{longest[1]})" if longest else "no static frames")
bad = [r for r in runs if r[2] > 0.5]
for r in bad:
    print(f"  STATIC {r[2]:.2f}s frames {r[0]}-{r[1]}")
print("PASS" if not bad else "FAIL")
