"""Shared audio helpers: one decoder for analysis and for the prepared track.

Both the beat analysis and the prepared fragment decode the MP3 with the same
ffmpeg call, so sample 0 means the same instant everywhere (MP3 encoder delay
is handled once, here, instead of differently by each tool).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

SR = 48_000


def decode(path: str | Path, sr: int = SR) -> np.ndarray:
    """Decode any audio file to float32 stereo, shape (n, 2)."""
    path = Path(path)
    if not path.exists():
        raise SystemExit(
            f"Missing audio: {path}. Put the track at public/stfu.mp3 (no substitutes)."
        )
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-map", "0:a:0", "-ac", "2", "-ar", str(sr), "-f", "f32le", "-",
    ]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def write_wav(path: str | Path, audio: np.ndarray, sr: int = SR) -> None:
    """Write float audio as 24-bit PCM WAV via ffmpeg (no extra deps)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.ascontiguousarray(audio, dtype=np.float32)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "f32le", "-ar", str(sr), "-ac", str(audio.shape[1]), "-i", "-",
        "-c:a", "pcm_s24le", str(path),
    ]
    subprocess.run(cmd, input=audio.tobytes(), check=True)
