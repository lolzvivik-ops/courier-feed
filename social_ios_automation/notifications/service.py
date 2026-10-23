"""
D1–D4 — Notification routing service.

NotificationService.send(user_id, user_type, event_type, data)
  → NotificationResult

Applies:
  - quiet hours check per user settings
  - anti-spam (max 3 same event_type per user per hour)
  - no_text_mode (D2)
  - badge suppression (D2 default: badge off)
  - category-level enable/disable per user (D2)
  - APNs delivery to all registered devices
  - DB persistence (notifications table)
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .catalog import get_text
from .apns    import APNsClient, APNsResult

logger = logging.getLogger(__name__)

_SPAM_WINDOW_SECS = 3600
_SPAM_LIMIT       = 3


@dataclass
class NotificationResult:
    notification_id: Optional[str]
    status:          str    # sent | skipped_quiet | skipped_spam | skipped_disabled | error
    apns_results:    List[APNsResult]
    reason:          Optional[str] = None


class NotificationService:

    def __init__(
        self,
        apns_client:     Optional[APNsClient] = None,
        db_execute=None,   # injected db.execute callable
    ):
        self._apns   = apns_client
        self._exec   = db_execute    # execute(sql, params, fetch)

    # ── public API ────────────────────────────────────────────────────────────

    def send(
        self,
        user_id:    str,
        user_type:  str,   # model | owner
        event_type: str,
        data:       Optional[Dict[str, Any]] = None,
        deep_link:  Optional[str]           = None,
        urgent:     bool                    = False,
        thread_id:  Optional[str]           = None,
    ) -> NotificationResult:

        settings = self._get_settings(user_id, event_type)

        # ── category disabled ─────────────────────────────────────────────────
        if not settings.get("enabled", True):
            return NotificationResult(None, "skipped_disabled",
                                      [], "category disabled by user")

        # ── quiet hours ───────────────────────────────────────────────────────
        if not urgent and self._in_quiet_hours(settings):
            return NotificationResult(None, "skipped_quiet", [],
                                      "quiet hours active")

        # ── anti-spam ─────────────────────────────────────────────────────────
        if self._is_spam(user_id, event_type):
            return NotificationResult(None, "skipped_spam", [],
                                      f">{_SPAM_LIMIT} same events this hour")

        # ── text lookup ───────────────────────────────────────────────────────
        no_text = settings.get("no_text_mode", False)
        badge   = 1 if settings.get("badge_enabled", False) else None
        text    = get_text(event_type, user_type, no_text=no_text)
        title   = text.get("title", "")
        body    = text.get("body", "")
        category= text.get("category", "general")

        # ── persist notification row ──────────────────────────────────────────
        notif_id = str(uuid.uuid4())
        if self._exec:
            self._exec(
                """INSERT INTO notifications
                   (id, user_id, user_type, event_type, category,
                    title, body, deep_link, thread_id, is_urgent, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')""",
                (notif_id, user_id, user_type, event_type, category,
                 title, body, deep_link, thread_id, urgent),
            )

        # ── APNs delivery ──────────────────────────────────────────────────────
        apns_results: List[APNsResult] = []
        devices = self._get_devices(user_id, user_type)

        for device in devices:
            if not self._apns:
                break
            result = self._apns.send(
                token       = device["apns_token"],
                title       = title,
                body        = body,
                data        = {"event": event_type, "data": data or {}},
                environment = device.get("environment", "production"),
                thread_id   = thread_id,
                badge       = badge,
            )
            apns_results.append(result)
            if result.success and self._exec:
                self._exec(
                    "UPDATE notifications SET status='sent', sent_at=NOW(), apns_message_id=%s WHERE id=%s",
                    (result.apns_id, notif_id),
                )

        final_status = "sent"
        if devices and not any(r.success for r in apns_results):
            final_status = "error"
        elif not devices:
            final_status = "sent"   # no device registered yet, still persisted

        return NotificationResult(notif_id, final_status, apns_results)

    # ── private helpers ───────────────────────────────────────────────────────

    def _get_settings(self, user_id: str, event_type: str) -> dict:
        if not self._exec:
            return {}
        # get category from catalog
        from .catalog import CATALOG
        category = CATALOG.get(event_type, {}).get("owner", {}).get("category", "general")
        row = self._exec(
            "SELECT * FROM notification_settings WHERE user_id=%s AND category=%s",
            (user_id, category), fetch="one",
        )
        return dict(row) if row else {}

    def _in_quiet_hours(self, settings: dict) -> bool:
        qs = settings.get("quiet_start")
        qe = settings.get("quiet_end")
        if not qs or not qe:
            return False
        now_utc = datetime.now(timezone.utc).time()
        qs_t = qs if hasattr(qs, "hour") else _parse_time(str(qs))
        qe_t = qe if hasattr(qe, "hour") else _parse_time(str(qe))
        # handle overnight range e.g. 23:00–08:00
        if qs_t < qe_t:
            return qs_t <= now_utc < qe_t
        return now_utc >= qs_t or now_utc < qe_t

    def _is_spam(self, user_id: str, event_type: str) -> bool:
        if not self._exec:
            return False
        count = self._exec(
            """SELECT COUNT(*) AS cnt FROM notifications
               WHERE user_id=%s AND event_type=%s
                 AND created_at > NOW() - INTERVAL '1 hour'""",
            (user_id, event_type), fetch="one",
        )
        return (count or {}).get("cnt", 0) >= _SPAM_LIMIT

    def _get_devices(self, user_id: str, user_type: str) -> List[dict]:
        if not self._exec:
            return []
        app = "cabinet" if user_type == "model" else "remote"
        rows = self._exec(
            "SELECT * FROM devices WHERE user_id=%s AND app=%s",
            (user_id, app), fetch="all",
        )
        return [dict(r) for r in (rows or [])]


def _parse_time(s: str):
    from datetime import time as dtime
    parts = s.split(":")
    return dtime(int(parts[0]), int(parts[1]) if len(parts)>1 else 0)
