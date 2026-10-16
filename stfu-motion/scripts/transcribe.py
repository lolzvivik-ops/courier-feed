#!/usr/bin/env python3
"""Word-level transcription of the vocal stem → .cache/asr/<tag>.json (times in song seconds)

    .venv-asr/bin/python scripts/transcribe.py --model large-v3 --stem vocals_ft --crop 57.3 91.7 --prompt "..."
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--model", default="large-v3")
ap.add_argument("--stem", default="vocals_ft")
ap.add_argument("--crop", nargs=2, type=float, default=None)
ap.add_argument("--prompt", default=None)
ap.add_argument("--beam", type=int, default=5)
ap.add_argument("--tag", default=None)
ap.add_argument("--no-context", action="store_true")
a = ap.parse_args()

x, sr = sf.read(ROOT / ".cache" / "stems" / f"{a.stem}.wav", dtype="float32")
x = x.mean(axis=1)
off = 0.0
if a.crop:
    off = a.crop[0]
    x = x[int(a.crop[0] * sr):int(a.crop[1] * sr)]
audio = resample_poly(x, 160, 441).astype(np.float32)

t0 = time.time()
model = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=4)
segments, _ = model.transcribe(audio, language="en", beam_size=a.beam, word_timestamps=True, vad_filter=False,
                               condition_on_previous_text=not a.no_context, temperature=0.0, initial_prompt=a.prompt)
out = []
for seg in segments:
    out.append({"start": seg.start + off, "end": seg.end + off, "text": seg.text,
                "words": [{"w": w.word, "s": round(w.start + off, 3), "e": round(w.end + off, 3), "p": round(w.probability, 3)} for w in seg.words]})
tag = a.tag or f"{a.model}_{a.stem}{'_prompt' if a.prompt else ''}"
dst = ROOT / ".cache" / "asr" / f"{tag}.json"
dst.parent.mkdir(exist_ok=True)
dst.write_text(json.dumps(out, indent=1))
print(f"{tag}: {time.time() - t0:.0f}s")
for seg in out:
    print(f"  [{seg['start']:6.2f}-{seg['end']:6.2f}] {seg['text']}")
