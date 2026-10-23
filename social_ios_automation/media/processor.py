"""
A3 — Media processor: ffmpeg-based transcoding for social platform uploads.

All video → 9:16 vertical, 1080×1920, H.264 (yuv420p) + AAC 192kbps.
Cover frame → JPEG extracted at 0.5s.

Entry points:
  transcode(input_path, platform)   → TranscodeResult
  extract_cover(video_path)         → str (path to JPEG)
  probe(input_path)                 → dict (ffprobe JSON)
"""

import json
import logging
import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_OUT_DIR = os.getenv("MEDIA_OUT_DIR", "/tmp/social_media_out")
os.makedirs(_OUT_DIR, exist_ok=True)

# Per-platform constraints
_PLATFORM_SPECS = {
    "fansly":    {"max_dur": 0,     "max_mb": 0},    # no enforced limit
    "instagram": {"max_dur": 60,    "max_mb": 100},
    "tiktok":    {"max_dur": 180,   "max_mb": 500},
    "x":         {"max_dur": 140,   "max_mb": 512},
    "reddit":    {"max_dur": 900,   "max_mb": 1000},
}


@dataclass
class TranscodeResult:
    platform:     str
    output_path:  str
    cover_path:   Optional[str]
    duration_secs: float
    resolution:   str          # "1080x1920"
    file_size_mb:  float
    status:       str          # ok | error
    error:        Optional[str] = None


def probe(input_path: str) -> dict:
    """Run ffprobe and return parsed JSON."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        input_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return json.loads(result.stdout)


def transcode(input_path: str, platform: str = "instagram") -> TranscodeResult:
    """
    Transcode to 9:16 1080×1920, H.264+AAC.
    Pads with black bars if source is not 9:16.
    Trims to platform max_dur if set.
    """
    spec    = _PLATFORM_SPECS.get(platform, _PLATFORM_SPECS["instagram"])
    out_id  = str(uuid.uuid4())[:8]
    out_path = os.path.join(_OUT_DIR, f"{out_id}_{platform}.mp4")

    # scale + pad filter: fit into 1080x1920 with black letterbox
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
    )

    cmd = ["ffmpeg", "-y", "-i", input_path]

    if spec["max_dur"] > 0:
        cmd += ["-t", str(spec["max_dur"])]

    cmd += [
        "-vf",     vf,
        "-c:v",    "libx264",
        "-preset", "fast",
        "-crf",    "23",
        "-pix_fmt","yuv420p",
        "-c:a",    "aac",
        "-b:a",    "192k",
        "-movflags","+faststart",
        "-f",      "mp4",
        out_path,
    ]

    logger.debug("ffmpeg cmd: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        return TranscodeResult(
            platform=platform, output_path="", cover_path=None,
            duration_secs=0, resolution="", file_size_mb=0,
            status="error", error=result.stderr[-500:],
        )

    info = probe(out_path)
    dur  = float(info.get("format", {}).get("duration", 0))
    sz   = os.path.getsize(out_path) / (1024 * 1024)

    cover = extract_cover(out_path)
    return TranscodeResult(
        platform=platform, output_path=out_path, cover_path=cover,
        duration_secs=dur, resolution="1080x1920",
        file_size_mb=round(sz, 2), status="ok",
    )


def extract_cover(video_path: str, at_second: float = 0.5) -> Optional[str]:
    """Extract a single JPEG frame from video_path at at_second."""
    cover_path = video_path.rsplit(".", 1)[0] + "_cover.jpg"
    cmd = [
        "ffmpeg", "-y",
        "-ss",   str(at_second),
        "-i",    video_path,
        "-vframes", "1",
        "-q:v",  "2",
        cover_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0 or not os.path.exists(cover_path):
        logger.warning("Cover extraction failed: %s", result.stderr[:200])
        return None
    return cover_path


def transcode_for_all_platforms(input_path: str) -> dict:
    """
    Convenience: transcode once per social platform that the original
    video is approved for.  Returns {platform: TranscodeResult}.
    """
    results = {}
    for platform in ("instagram", "tiktok", "x", "reddit"):
        try:
            results[platform] = transcode(input_path, platform)
        except Exception as exc:
            results[platform] = TranscodeResult(
                platform=platform, output_path="", cover_path=None,
                duration_secs=0, resolution="", file_size_mb=0,
                status="error", error=str(exc),
            )
    return results
