"""
iOS device fingerprint generator.
Produces a stable, per-instance device identity that survives serialization.
Every field value here comes from real iOS hardware data tables.
"""

import uuid
import json
import random
import hashlib
import os
import time
from dataclasses import dataclass, asdict, field
from typing import Optional


# ── Hardware lookup tables ────────────────────────────────────────────────────

_IPHONE_MODELS = [
    # (model_id, marketing_name, width, height, scale, chip)
    ("iPhone13,2", "iPhone 12",      1170, 2532, 3.0, "A14"),
    ("iPhone13,3", "iPhone 12 Pro",  1170, 2532, 3.0, "A14"),
    ("iPhone13,4", "iPhone 12 Pro Max", 1284, 2778, 3.0, "A14"),
    ("iPhone14,2", "iPhone 13 Pro",  1170, 2532, 3.0, "A15"),
    ("iPhone14,3", "iPhone 13 Pro Max", 1284, 2778, 3.0, "A15"),
    ("iPhone14,4", "iPhone 13 mini", 1080, 2340, 3.0, "A15"),
    ("iPhone14,5", "iPhone 13",      1170, 2532, 3.0, "A15"),
    ("iPhone15,2", "iPhone 14 Pro",  1179, 2556, 3.0, "A16"),
    ("iPhone15,3", "iPhone 14 Pro Max", 1290, 2796, 3.0, "A16"),
    ("iPhone14,7", "iPhone 14",      1170, 2532, 3.0, "A15"),
    ("iPhone14,8", "iPhone 14 Plus", 1284, 2778, 3.0, "A15"),
]

_IOS_VERSIONS = [
    ("15_0",   "15.0"),
    ("15_1",   "15.1"),
    ("15_3_1", "15.3.1"),
    ("15_4",   "15.4"),
    ("15_6_1", "15.6.1"),
    ("16_0",   "16.0"),
    ("16_1",   "16.1"),
    ("16_3_1", "16.3.1"),
    ("16_4",   "16.4"),
    ("16_6",   "16.6"),
]

_LOCALES = [
    ("en_US", "en-US"),
    ("en_GB", "en-GB"),
    ("fr_FR", "fr-FR"),
    ("de_DE", "de-DE"),
    ("es_ES", "es-ES"),
    ("pt_BR", "pt-BR"),
]

_CONNECTION_TYPES = ["WIFI", "WIFI", "WIFI", "LTE", "5G"]


@dataclass
class DeviceProfile:
    """Fully seeded iOS device identity for one platform session."""

    # hardware
    model_id:    str
    model_name:  str
    width:       int
    height:      int
    scale:       float
    chip:        str

    # software
    ios_ver_slug: str    # e.g. "15_1"
    ios_ver_str:  str    # e.g. "15.1"

    # locale
    locale:   str        # e.g. "en_US"
    language: str        # e.g. "en-US"

    # identifiers
    device_id:        str   # UUID4  — stable device serial
    phone_id:         str   # UUID4  — phone-level ID
    uuid:             str   # UUID4  — app install ID
    advertising_id:   str   # UUID4  — IDFA
    android_id:       str   # 16-char hex (kept for mixed profiles)

    # network hint
    connection_type: str

    # serialization seed (lets us reconstruct the same profile)
    seed: int = field(default_factory=lambda: int(time.time() * 1000))

    # ── constructors ────────────────────────────────────────────────────────

    @classmethod
    def random(cls, seed: Optional[int] = None) -> "DeviceProfile":
        """Generate a fresh random device profile."""
        rng = random.Random(seed)
        hw  = rng.choice(_IPHONE_MODELS)
        ios = rng.choice(_IOS_VERSIONS)
        loc = rng.choice(_LOCALES)
        net = rng.choice(_CONNECTION_TYPES)

        def rng_uuid() -> str:
            return str(uuid.UUID(bytes=bytes(rng.getrandbits(8) for _ in range(16)), version=4))

        return cls(
            model_id      = hw[0],
            model_name    = hw[1],
            width         = hw[2],
            height        = hw[3],
            scale         = hw[4],
            chip          = hw[5],
            ios_ver_slug  = ios[0],
            ios_ver_str   = ios[1],
            locale        = loc[0],
            language      = loc[1],
            device_id     = rng_uuid(),
            phone_id      = rng_uuid(),
            uuid          = rng_uuid(),
            advertising_id= rng_uuid(),
            android_id    = "".join(f"{rng.randint(0,255):02x}" for _ in range(8)),
            connection_type = net,
            seed          = seed or int(time.time() * 1000),
        )

    @classmethod
    def from_file(cls, path: str) -> "DeviceProfile":
        with open(path) as fh:
            return cls(**json.load(fh))

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as fh:
            json.dump(asdict(self), fh, indent=2)

    # ── user-agent builders ─────────────────────────────────────────────────

    def ig_user_agent(self, app_version: str, version_code: str) -> str:
        """
        Instagram iOS UA pattern.
        e.g.  Instagram 259.0.0.27.98 (iPhone13,2; iOS 15_1; en_US; en-US;
                scale=3.00; 1170x2532; 405398279)
        """
        return (
            f"Instagram {app_version} "
            f"({self.model_id}; iOS {self.ios_ver_slug}; "
            f"{self.locale}; {self.language}; "
            f"scale={self.scale:.2f}; {self.width}x{self.height}; "
            f"{version_code})"
        )

    def tiktok_user_agent(self, app_version: str, build: str) -> str:
        """
        TikTok iOS UA pattern.
        e.g.  TikTok 26.1.0 rv:261018 (iPhone; iOS 15.3.1; en_US) Cronet
        """
        return (
            f"TikTok {app_version} rv:{build} "
            f"(iPhone; iOS {self.ios_ver_str}; {self.locale}) Cronet"
        )

    def twitter_user_agent(self) -> str:
        """Twitter iOS UA pattern."""
        return (
            f"Twitter-iPhone/9.0 iOS/{self.ios_ver_str} "
            f"({self.model_name}; {self.locale})"
        )

    def reddit_user_agent(self, app_version: str) -> str:
        return f"Reddit/{app_version}/iOS/{self.ios_ver_str} {self.model_id}"

    # ── repr ────────────────────────────────────────────────────────────────

    def __str__(self) -> str:
        return (
            f"<DeviceProfile {self.model_name} iOS {self.ios_ver_str} "
            f"[{self.device_id[:8]}…]>"
        )
