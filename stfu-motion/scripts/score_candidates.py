#!/usr/bin/env python3
"""Rank alternative transcriptions of a line by acoustic fit (CTC forced-alignment
log-likelihood with the MMS aligner) over the same window of the vocal stem.

    .venv-asr/bin/python scripts/score_candidates.py
"""
import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio
import torchaudio.functional as F
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parent.parent
bundle = torchaudio.pipelines.MMS_FA
model = bundle.get_model(with_star=False).eval()
dictionary = bundle.get_dict(star=None)

x, sr = sf.read(ROOT / ".cache" / "stems" / "vocals_ft.wav", dtype="float32")
x16 = resample_poly(x.mean(axis=1), 160, 441).astype(np.float32)


def norm(text: str) -> list[str]:
    return [w for w in re.sub(r"[^a-z' ]", " ", text.lower().replace("-", " ")).split() if w]


def score(t0: float, t1: float, text: str) -> float:
    seg = torch.from_numpy(x16[int(t0 * 16000):int(t1 * 16000)])[None]
    with torch.inference_mode():
        em, _ = model(seg)
    em = torch.log_softmax(em, dim=-1)
    toks = [dictionary[c] for w in norm(text) for c in w if c in dictionary]
    ali, sc = F.forced_align(em, torch.tensor([toks], dtype=torch.int32), blank=0)
    return float(sc.sum())  # Viterbi path log-likelihood over the whole window


# Candidate wordings live in lyrics.candidates.json (local, gitignored: they are lyrics):
# {"L1 ~72.1": {"window": [71.9, 74.8], "candidates": ["...", "..."]}, ...}
LINES = {k: (v["window"][0], v["window"][1], v["candidates"])
         for k, v in json.loads((ROOT / "lyrics.candidates.json").read_text()).items()}
for name, (t0, t1, cands) in LINES.items():
    res = sorted(((score(t0, t1, c), c) for c in cands), reverse=True)
    best = res[0][0]
    print(f"{name}  [{t0}-{t1}]")
    for s, c in res:
        print(f"   {s - best:+8.2f}  {c}")
