#!/usr/bin/env python3
"""Isolate the vocal with Demucs → .cache/stems/vocals_<tag>.wav (44.1 kHz).
htdemucs_ft (tag "ft", ~3 min on 4 CPU cores) is what the lyric aligner reads.

    .venv-asr/bin/python scripts/separate_vocals.py [htdemucs|htdemucs_ft]

Uses the same ffmpeg decode as everything else, so sample 0 is the same instant.
"""
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from demucs.apply import apply_model
from demucs.pretrained import get_model

sys.path.insert(0, str(Path(__file__).parent))
from audio_io import decode  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
name = sys.argv[1] if len(sys.argv) > 1 else "htdemucs"
torch.set_num_threads(4)
model = get_model(name)
model.eval()
sr = model.samplerate
x = decode(ROOT / "public" / "stfu.mp3", sr=sr)
wav = torch.from_numpy(x.T.copy())[None]
ref = wav.mean(1)
mu, sd = ref.mean(), ref.std()
t0 = time.time()
with torch.no_grad():
    out = apply_model(model, (wav - mu) / sd, device="cpu", shifts=1, split=True, overlap=0.25, progress=False)[0]
out = out * sd + mu
voc = out[model.sources.index("vocals")].numpy().T
acc = (out.sum(0).numpy().T - voc)
dst = ROOT / ".cache" / "stems"
dst.mkdir(parents=True, exist_ok=True)
tag = "ft" if name == "htdemucs_ft" else name
sf.write(dst / f"vocals_{tag}.wav", voc, sr, subtype="FLOAT")
sf.write(dst / f"accomp_{tag}.wav", acc, sr, subtype="FLOAT")
print(f"{name}: {len(x) / sr:.1f}s separated in {time.time() - t0:.0f}s -> {dst}")
