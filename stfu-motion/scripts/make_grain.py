#!/usr/bin/env python3
"""Write public/grain.png: a 512×512 tile of monochrome film grain (seeded)."""
from pathlib import Path

import numpy as np
from PIL import Image

rng = np.random.default_rng(1508)
g = rng.normal(128, 52, size=(512, 512))
# a touch of 2-px clumping so it reads as grain, not digital noise
g = 0.75 * g + 0.25 * np.roll(np.roll(g, 1, 0), 1, 1)
img = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), mode="L")
out = Path(__file__).resolve().parent.parent / "public" / "grain.png"
img.save(out, optimize=True)
print("wrote", out)
