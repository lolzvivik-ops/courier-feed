"""
C2 — Balance proof screenshot generator.

Renders a Fansly earnings summary as a PIL image with all
subscriber / client nicknames redacted.  Returns path to PNG.

Entry points:
  render_proof(earnings_summary, period_label, output_path) → str
"""

import os
import textwrap
from datetime import datetime, timezone
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# ── layout constants ──────────────────────────────────────────────────────────
_W, _H          = 800, 560
_BG             = (18, 18, 18)
_ACCENT         = (0, 200, 120)
_TEXT_COLOR     = (240, 240, 240)
_MUTED          = (140, 140, 140)
_REDACT_BG      = (50, 50, 50)
_FONT_LARGE     = 28
_FONT_MED       = 20
_FONT_SMALL     = 15
_PADDING        = 40


def _cents_to_usd(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def render_proof(
    earnings:     dict,
    period_label: str,
    output_path:  Optional[str] = None,
) -> str:
    """
    earnings dict keys (all in USD cents):
      total_cents, subscriptions, ppv, tips, chargebacks, platform_fee
    Returns path to written PNG.
    """
    if not _PIL_AVAILABLE:
        raise RuntimeError("Pillow not installed; run: pip install Pillow")

    if output_path is None:
        ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = f"/tmp/proof_{ts_str}.png"

    img  = Image.new("RGB", (_W, _H), _BG)
    draw = ImageDraw.Draw(img)

    try:
        font_large  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  _FONT_LARGE)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",        _FONT_MED)
        font_small  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",        _FONT_SMALL)
    except OSError:
        font_large = font_medium = font_small = ImageFont.load_default()

    # header
    draw.text((_PADDING, _PADDING), "Fansly Earnings Report",
              font=font_large, fill=_ACCENT)
    draw.text((_PADDING, _PADDING + 38), period_label,
              font=font_medium, fill=_MUTED)

    # divider
    y = _PADDING + 80
    draw.line([(_PADDING, y), (_W - _PADDING, y)], fill=_MUTED, width=1)
    y += 20

    rows = [
        ("Gross Revenue",   earnings.get("total_cents", 0)),
        ("Subscriptions",   earnings.get("subscriptions", 0)),
        ("PPV",             earnings.get("ppv", 0)),
        ("Tips",            earnings.get("tips", 0)),
        ("Chargebacks",     -abs(earnings.get("chargebacks", 0))),
        ("Platform Fee",    -abs(earnings.get("platform_fee", 0))),
    ]

    for label, cents in rows:
        color = (255, 100, 100) if cents < 0 else _TEXT_COLOR
        draw.text((_PADDING, y),             label, font=font_medium, fill=_MUTED)
        draw.text((_W - _PADDING - 140, y),  _cents_to_usd(abs(cents)),
                  font=font_medium, fill=color)
        y += 34

    # total divider
    draw.line([(_PADDING, y), (_W - _PADDING, y)], fill=_MUTED, width=1)
    y += 16

    net = (earnings.get("total_cents", 0)
           - abs(earnings.get("chargebacks", 0))
           - abs(earnings.get("platform_fee", 0)))
    draw.text((_PADDING, y), "Net (after fees)", font=font_large, fill=_TEXT_COLOR)
    draw.text((_W - _PADDING - 160, y),
              _cents_to_usd(net), font=font_large, fill=_ACCENT)
    y += 50

    # redact notice
    redact_text = "Subscriber / client names: ████████████████  [REDACTED]"
    draw.rectangle([(_PADDING, y), (_W - _PADDING, y + 30)], fill=_REDACT_BG)
    draw.text((_PADDING + 8, y + 7), redact_text, font=font_small, fill=_MUTED)
    y += 44

    # timestamp watermark
    ts = datetime.now(timezone.utc).strftime("Generated %Y-%m-%d %H:%M UTC")
    draw.text((_PADDING, y), ts, font=font_small, fill=_MUTED)

    img.save(output_path, format="PNG", optimize=True)
    return output_path
