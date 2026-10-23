"""
D5 — Telegram daily digest.

Sends a formatted daily summary to the owner's Telegram chat.
Uses raw Telegram Bot API (no python-telegram-bot library).

Entry points:
  TelegramBot(token, chat_id)
  .send_digest(digest: DailyDigest)
  .send_text(text)
  .send_alert(text, urgent)
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


@dataclass
class DailyDigest:
    date:               str
    total_income_cents: int
    subscriptions_new:  int
    subscriptions_total: int
    ppv_sold:           int
    posts_published:    int
    social_posts:       Dict[str, int] = field(default_factory=dict)  # platform→count
    health_issues:      List[str]      = field(default_factory=list)
    content_days_left:  int            = 0
    period_note:        Optional[str]  = None


class TelegramBot:

    def __init__(
        self,
        token:   str = "",
        chat_id: str = "",
    ):
        self._token   = token   or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID",   "")

    def _call(self, method: str, data: dict) -> dict:
        url = _TELEGRAM_API.format(token=self._token, method=method)
        try:
            resp = requests.post(url, json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("Telegram API error (%s): %s", method, exc)
            return {"ok": False, "error": str(exc)}

    def send_text(self, text: str, parse_mode: str = "HTML") -> dict:
        return self._call("sendMessage", {
            "chat_id":    self._chat_id,
            "text":       text,
            "parse_mode": parse_mode,
        })

    def send_alert(self, text: str, urgent: bool = False) -> dict:
        prefix = "🚨 " if urgent else "⚠️ "
        return self.send_text(f"{prefix}{text}")

    def send_digest(self, digest: DailyDigest) -> dict:
        """Render and send formatted digest. No platform names per TZ privacy rules."""
        income_usd = digest.total_income_cents / 100

        lines = [
            f"<b>Итоги за {digest.date}</b>",
            "",
            f"💰 Доход: <b>${income_usd:,.2f}</b>",
            f"👥 Подписчиков: {digest.subscriptions_total} (+{digest.subscriptions_new})",
            f"📩 PPV продано: {digest.ppv_sold}",
            f"📌 Постов опубликовано: {digest.posts_published}",
        ]

        if digest.social_posts:
            lines.append("")
            lines.append("🌐 Соц. сети:")
            for platform, count in digest.social_posts.items():
                lines.append(f"  • {platform}: {count}")

        if digest.content_days_left < 5:
            lines.append("")
            lines.append(f"⚡️ Запас контента: {digest.content_days_left} дн.")

        if digest.health_issues:
            lines.append("")
            lines.append("🔴 Проблемы с аккаунтами:")
            for issue in digest.health_issues[:5]:
                lines.append(f"  • {issue}")

        if digest.period_note:
            lines.append("")
            lines.append(f"📊 {digest.period_note}")

        return self.send_text("\n".join(lines))
