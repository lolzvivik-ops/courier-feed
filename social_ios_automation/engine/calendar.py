"""
B6 — Content calendar: buffer calculation and slot suggestions.

calculate_buffer(model_id, days_ahead) → BufferReport
suggest_slots(model_id, n_slots)       → list[datetime]

Reads approved promo videos and published social posts to estimate
how many days of scheduled content remain in the pipeline.
Suggests optimal posting slots (morning / evening, platform-aware).
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from .db import execute

logger = logging.getLogger(__name__)

# Default posting windows (local time expressed as UTC offsets; caller adjusts)
_WINDOWS = [9, 17]   # 09:00 and 17:00 UTC posting slots

PLATFORM_DAILY_LIMITS = {
    "instagram": 3,
    "tiktok":    4,
    "x":         5,
    "reddit":    2,
}


@dataclass
class BufferReport:
    model_id:            str
    days_covered:        int     # number of full days of content queued
    queued_jobs:         int
    approved_videos:     int
    pending_variants:    int
    platforms:           Dict[str, int] = field(default_factory=dict)  # platform→queued
    days_until_empty:    float          = 0.0
    needs_content:       bool           = False
    threshold_days:      int            = 5    # alert below this


def calculate_buffer(model_id: str, threshold_days: int = 5) -> BufferReport:
    """
    Count queued publish_jobs + approved promo_videos ready to transcode
    and estimate how many days of posts they cover.
    """
    # queued social posts per platform
    rows = execute(
        """SELECT pa.platform, COUNT(*) AS cnt
           FROM publish_jobs pj
           JOIN platform_accounts pa ON pa.id = pj.account_id
           WHERE pa.model_id = %s
             AND pj.status IN ('queued','awaiting_confirm')
             AND pj.job_type IN ('social_post','feed_post')
           GROUP BY pa.platform""",
        (model_id,), fetch="all",
    )
    platform_counts: Dict[str,int] = {r["platform"]: r["cnt"] for r in (rows or [])}
    total_queued = sum(platform_counts.values())

    # approved promo videos not yet transcoded into social_variants
    approved_videos = execute(
        """SELECT COUNT(*) AS cnt FROM promo_videos
           WHERE model_id=%s AND status='approved'""",
        (model_id,), fetch="one",
    ) or {"cnt": 0}

    # pending social_variants (transcoded but post not yet queued)
    pending_variants = execute(
        """SELECT COUNT(*) AS cnt FROM social_variants sv
           LEFT JOIN social_posts sp ON sp.variant_id = sv.id
           WHERE sp.id IS NULL""",
        (), fetch="one",
    ) or {"cnt": 0}

    # estimate: avg posts/day across active platforms
    active_platforms = max(len(platform_counts), 1)
    avg_posts_day    = sum(
        min(platform_counts.get(p, 0), lim)
        for p, lim in PLATFORM_DAILY_LIMITS.items()
    ) / max(active_platforms, 1)
    # each pending variant generates ~1 post per platform
    total_content = total_queued + pending_variants["cnt"] * active_platforms

    days_covered = (total_content / max(avg_posts_day, 1)) if avg_posts_day else 0

    return BufferReport(
        model_id         = model_id,
        days_covered     = int(days_covered),
        queued_jobs      = total_queued,
        approved_videos  = approved_videos["cnt"],
        pending_variants = pending_variants["cnt"],
        platforms        = platform_counts,
        days_until_empty = days_covered,
        needs_content    = days_covered < threshold_days,
        threshold_days   = threshold_days,
    )


def suggest_slots(
    model_id:     str,
    n_slots:      int   = 6,
    start_from:   Optional[datetime] = None,
) -> List[datetime]:
    """
    Return n_slots future posting datetimes, spaced across _WINDOWS,
    avoiding times already occupied by scheduled jobs.
    """
    now   = start_from or datetime.now(timezone.utc)
    slots = []
    day   = now.date()

    # existing scheduled slots
    existing_rows = execute(
        """SELECT pj.scheduled_for
           FROM publish_jobs pj
           JOIN platform_accounts pa ON pa.id = pj.account_id
           WHERE pa.model_id = %s
             AND pj.scheduled_for > %s
             AND pj.status IN ('queued','running','awaiting_confirm')""",
        (model_id, now), fetch="all",
    ) or []
    busy_hours = {
        (r["scheduled_for"].date(), r["scheduled_for"].hour)
        for r in existing_rows
        if r.get("scheduled_for")
    }

    for _ in range(n_slots * 30):   # iterate up to 30 days to fill n_slots
        for hour in _WINDOWS:
            candidate = datetime(day.year, day.month, day.day, hour, 0,
                                 tzinfo=timezone.utc)
            if candidate <= now:
                continue
            if (day, hour) not in busy_hours:
                slots.append(candidate)
                busy_hours.add((day, hour))
            if len(slots) >= n_slots:
                return slots
        day = day + timedelta(days=1)

    return slots
