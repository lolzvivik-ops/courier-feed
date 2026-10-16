#!/usr/bin/env python3
"""Time every lyric word to the vocal → src/data/lyrics.json

    npm run lyrics      (.venv-asr; needs .cache/stems/vocals_ft.wav from scripts/separate_vocals.py)

1. Each line of lyrics.txt is force-aligned (MMS CTC aligner, 20 ms frames) inside a
   window around its rough start time, on the Demucs vocal stem.
2. Each word start is then snapped to the nearest vocal onset (scripts/vocal_onsets.py,
   the same detector the sync report uses) within ±60 ms, so a word appears exactly
   when its consonant hits.
3. Also writes src/data/lyrics.placeholder.json (same timings, words as bullets) — the
   committed stand-in when the real lyrics aren't present.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio
import torchaudio.functional as F
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).parent))
from vocal_onsets import vocal_onsets  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SNAP = 0.060


def parse(path: Path):
    lines = []
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        t, text = raw.split("|", 1)
        text = text.strip()
        unsure = text.endswith(" ?")
        if unsure:
            text = text[:-2].strip()
        lines.append({"approx": float(t), "text": text, "unsure": unsure})
    return lines


def main() -> None:
    lines = parse(ROOT / "lyrics.txt")
    x, sr = sf.read(ROOT / ".cache" / "stems" / "vocals_ft.wav", dtype="float32")
    mono = x.mean(axis=1)
    x16 = resample_poly(mono, 160, 441).astype(np.float32)
    bundle = torchaudio.pipelines.MMS_FA
    on_t = vocal_onsets(mono, sr)

    model = bundle.get_model(with_star=True).eval()
    dictionary = bundle.get_dict()  # includes '*'

    def align(t0: float, t1: float, groups: list[list[str]]):
        """CTC forced alignment of word groups (lines) in [t0, t1], '*' between groups.
        Returns {(group, word): (start_s, end_s, conf)}."""
        seg = torch.from_numpy(x16[int(t0 * 16000):int(t1 * 16000)])[None]
        with torch.inference_mode():
            em, _ = model(seg)
        em = torch.log_softmax(em, dim=-1)
        fps = em.shape[1] / (t1 - t0)
        toks, owner = [dictionary["*"]], [None]
        for gi, words in enumerate(groups):
            for wi, w in enumerate(words):
                for c in re.sub(r"[^a-z']", "", w.lower()):
                    if c in dictionary:
                        toks.append(dictionary[c])
                        owner.append((gi, wi))
            toks.append(dictionary["*"])
            owner.append(None)
        ali, scores = F.forced_align(em, torch.tensor([toks], dtype=torch.int32), blank=0)
        ali, scores = ali[0].tolist(), scores[0].exp().tolist()
        spans: dict = {}
        ti, prev = -1, 0
        for fi, a in enumerate(ali):
            if a != 0 and (a != prev or prev == 0):
                ti += 1
            if a != 0 and owner[ti] is not None:
                sp = spans.setdefault(owner[ti], [fi, fi + 1, []])
                sp[1] = fi + 1
                sp[2].append(scores[fi])
            prev = a
        return {k: (t0 + v[0] / fps, t0 + v[1] / fps, float(np.mean(v[2]))) for k, v in spans.items()}

    words_of = [ln["text"].split() for ln in lines]
    # Pass 1: the whole fragment at once keeps lines in order (no overlaps); '*' soaks up ad-libs.
    g = align(lines[0]["approx"] - 0.6, lines[-1]["approx"] + 2.2, words_of)
    # Pass 2: each line again, boxed between its neighbours from pass 1; per word keep the
    # more confident of the two (pass 1 can smear a word across a held vowel, pass 2 can't
    # leave its box).
    chosen: dict = {}
    for li, words in enumerate(words_of):
        lo = g[(li, 0)][0] - 0.25 if li == 0 else max(g[(li - 1, len(words_of[li - 1]) - 1)][1], g[(li, 0)][0] - 0.25)
        hi = g[(li + 1, 0)][0] if li + 1 < len(lines) else g[(li, len(words) - 1)][1] + 0.4
        loc = align(lo, hi, [words])
        for wi in range(len(words)):
            a, b = g[(li, wi)], loc[(0, wi)]
            chosen[(li, wi)] = (b, "line") if b[2] > a[2] else (a, "global")

    out_lines = []
    last = -1.0
    for li, ln in enumerate(lines):
        out_words = []
        for wi, w in enumerate(words_of[li]):
            (start, end, conf), src = chosen[(li, wi)]
            near = np.where(np.abs(on_t - start) <= SNAP)[0]
            snapped = float(on_t[near[np.argmin(np.abs(on_t[near] - start))]]) if len(near) else start
            snapped = max(snapped, last + 0.02)  # strictly increasing
            last = snapped
            out_words.append({"text": w, "start": round(snapped, 4), "aligned": round(start, 4), "end": round(max(end, snapped + 0.05), 4),
                              "conf": round(conf, 3), "pass": src})
        out_lines.append({"text": ln["text"], "unsure": ln["unsure"], "words": out_words})
        print(f"{out_words[0]['start']:7.3f}  {'?' if ln['unsure'] else ' '} " + "  ".join(
            f"{w['text']}@{w['start']:.2f}[{w['pass'][0]}{w['conf']:.2f}]" for w in out_words))

    meta = {"source": "lyrics.txt aligned to the Demucs (htdemucs_ft) vocal stem with the MMS CTC aligner",
            "time": "song seconds"}
    (ROOT / "src" / "data" / "lyrics.json").write_text(json.dumps({**meta, "lines": out_lines}, indent=1))
    ph = {**meta, "placeholder": True, "lines": [
        {"text": " ".join("•" * min(4, max(1, len(w["text"]) // 2)) for w in ln["words"]), "unsure": False,
         "words": [{**w, "text": "•" * min(4, max(1, len(w["text"]) // 2))} for w in ln["words"]]} for ln in out_lines]}
    (ROOT / "src" / "data" / "lyrics.placeholder.json").write_text(json.dumps(ph, indent=1))
    print("wrote src/data/lyrics.json (+ placeholder)")


if __name__ == "__main__":
    main()
