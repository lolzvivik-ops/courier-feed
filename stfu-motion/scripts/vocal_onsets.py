"""One definition of "vocal onset", shared by the lyric aligner and the sync report:
librosa onsets of the Demucs vocal stem, 1024-pt window, 2.9 ms hop, 150–8000 Hz."""
from __future__ import annotations

import numpy as np


def vocal_onsets(y: np.ndarray, sr: int) -> np.ndarray:
    import librosa

    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=128, n_fft=1024, fmin=150, fmax=8000)
    return librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=128, units="time", backtrack=False,
                                      pre_max=2, post_max=2, pre_avg=10, post_avg=10, wait=2, delta=0.05)
