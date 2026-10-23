"""
D3/D4 — Notification text catalog.

All push notification bodies live here.  Per-TZ rules:
  - No platform names, no amounts in push text (privacy)
  - Model sees soft/friendly language
  - Owner sees operational/terse language

CATALOG[event_type] = {
    "model":   {"title": ..., "body": ..., "category": ...},
    "owner":   {"title": ..., "body": ..., "category": ...},
}
"""

from typing import Dict, Optional


CATALOG: Dict[str, dict] = {

    # ── A1: feed post ─────────────────────────────────────────────────────────
    "post_published": {
        "model": {
            "category": "publications",
            "title":    "Публикация вышла ✓",
            "body":     "Новый пост опубликован на твоей странице.",
        },
        "owner": {
            "category": "publications",
            "title":    "Post live",
            "body":     "Feed post published successfully.",
        },
    },
    "post_needs_confirm": {
        "model": {
            "category": "requests",
            "title":    "Ждём подтверждения",
            "body":     "Публикация ждёт одобрения.",
        },
        "owner": {
            "category": "requests",
            "title":    "Approve post",
            "body":     "A feed post is waiting for your confirmation.",
        },
    },
    "post_failed": {
        "model": {
            "category": "publications",
            "title":    "Не удалось опубликовать",
            "body":     "Произошла ошибка. Мы уже разбираемся.",
        },
        "owner": {
            "category": "publications",
            "title":    "Post failed — action required",
            "body":     "A feed post failed and needs manual review.",
        },
    },

    # ── A2: PPV message ───────────────────────────────────────────────────────
    "ppv_sent": {
        "model": {
            "category": "requests",
            "title":    "Сообщение отправлено",
            "body":     "Платное сообщение успешно отправлено.",
        },
        "owner": {
            "category": "requests",
            "title":    "PPV sent",
            "body":     "Paid message delivered.",
        },
    },
    "ppv_purchased": {
        "model": {
            "category": "money",
            "title":    "Покупка!",
            "body":     "Твоё сообщение приобрели.",
        },
        "owner": {
            "category": "money",
            "title":    "PPV purchased",
            "body":     "A paid message was purchased.",
        },
    },
    "ppv_needs_confirm": {
        "model": {
            "category": "requests",
            "title":    "Нужно одобрение",
            "body":     "Платное сообщение ждёт подтверждения.",
        },
        "owner": {
            "category": "requests",
            "title":    "Approve PPV",
            "body":     "A paid message is waiting for your confirmation.",
        },
    },

    # ── B1: account health ────────────────────────────────────────────────────
    "account_login_required": {
        "model": {
            "category": "accounts",
            "title":    "Нужен вход",
            "body":     "Требуется повторная авторизация в аккаунте.",
        },
        "owner": {
            "category": "accounts",
            "title":    "Account needs re-login",
            "body":     "An account requires re-authentication.",
        },
    },
    "account_limited": {
        "model": {
            "category": "accounts",
            "title":    "Ограничения аккаунта",
            "body":     "Аккаунт может быть временно ограничен.",
        },
        "owner": {
            "category": "accounts",
            "title":    "Account limited",
            "body":     "An account may have a temporary restriction.",
        },
    },

    # ── B4: inbox ─────────────────────────────────────────────────────────────
    "inbox_new_messages": {
        "model": {
            "category": "requests",
            "title":    "Новые сообщения",
            "body":     "У тебя непрочитанные сообщения.",
        },
        "owner": {
            "category": "requests",
            "title":    "Unread messages",
            "body":     "New unread messages in inbox.",
        },
    },
    "inbox_buyer_waiting": {
        "model": {
            "category": "requests",
            "title":    "Покупатель ждёт",
            "body":     "Есть покупатель, которому ещё не ответили.",
        },
        "owner": {
            "category": "requests",
            "title":    "Buyer waiting",
            "body":     "A buyer has not been replied to.",
        },
    },

    # ── B6: content buffer ────────────────────────────────────────────────────
    "content_buffer_low": {
        "model": {
            "category": "plan",
            "title":    "Нужен новый контент",
            "body":     "Запас контента заканчивается, пора снимать!",
        },
        "owner": {
            "category": "plan",
            "title":    "Content buffer low",
            "body":     "Scheduled content is running low.",
        },
    },

    # ── C1/C2: money ──────────────────────────────────────────────────────────
    "period_draft_ready": {
        "model": {
            "category": "money",
            "title":    "Расчёт готов",
            "body":     "Предварительный расчёт за период сформирован.",
        },
        "owner": {
            "category": "money",
            "title":    "Period draft ready",
            "body":     "Period calculation is ready for review.",
        },
    },
    "period_needs_review": {
        "model": {
            "category": "money",
            "title":    "Нужна проверка",
            "body":     "В расчёте обнаружено расхождение. Идёт проверка.",
        },
        "owner": {
            "category": "money",
            "title":    "Period needs review",
            "body":     "Discrepancy detected — manual review required.",
        },
    },

    # ── C3: blockchain ────────────────────────────────────────────────────────
    "payout_verified": {
        "model": {
            "category": "money",
            "title":    "Выплата подтверждена",
            "body":     "Транзакция успешно верифицирована.",
        },
        "owner": {
            "category": "money",
            "title":    "Payout verified",
            "body":     "Transaction confirmed on chain.",
        },
    },
    "payout_needs_human": {
        "model": {
            "category": "money",
            "title":    "Нужна проверка оплаты",
            "body":     "Возникло расхождение при проверке транзакции.",
        },
        "owner": {
            "category": "money",
            "title":    "Payout discrepancy — action required",
            "body":     "Transaction verification failed. Manual check needed.",
        },
    },

    # ── D5: daily digest ──────────────────────────────────────────────────────
    "daily_digest": {
        "model": {
            "category": "plan",
            "title":    "Итоги дня",
            "body":     "Твои показатели за сегодня готовы.",
        },
        "owner": {
            "category": "plan",
            "title":    "Daily digest",
            "body":     "Daily metrics digest is ready.",
        },
    },
}


def get_text(
    event_type: str,
    user_type:  str,         # "model" | "owner"
    no_text:    bool = False,
) -> dict:
    """
    Look up notification title+body for event_type + user_type.
    If no_text mode is enabled (D2 setting), body is suppressed.
    Returns {"title": ..., "body": ..., "category": ...}
    """
    entry = CATALOG.get(event_type, {})
    user_entry = entry.get(user_type, entry.get("owner", {}))
    result = dict(user_entry)
    if no_text:
        result["body"] = ""
        result["title"] = ""
    return result
