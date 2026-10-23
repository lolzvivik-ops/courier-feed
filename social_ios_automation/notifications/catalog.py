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

    # ══════════════════════════════════════════════════════════════════════════
    # D3 — Кабинет (model)
    # TZ §D2: no platform names, amounts, client names, or work-character words
    # ══════════════════════════════════════════════════════════════════════════

    # ── Plan items ────────────────────────────────────────────────────────────
    "plan_item_new": {
        "model": {
            "category": "plan",
            "title":    "В плане новый пункт",
            "body":     "В плане новый пункт",
            "deep_link":"cabinet://plan",
        },
        "owner": {
            "category": "plan",
            "title":    "New plan item",
            "body":     "A new plan item was added.",
            "deep_link":"remote://plan",
        },
    },
    "plan_item_deadline_2days": {
        "model": {
            "category": "plan",
            "title":    "Через 2 дня срок по плану",
            "body":     "Через 2 дня срок по плану",
            "deep_link":"cabinet://plan/item",
        },
        "owner": {
            "category": "plan",
            "title":    "Deadline in 2 days",
            "body":     "Plan item deadline in 2 days.",
            "deep_link":"remote://plan/item",
        },
    },
    "plan_item_deadline_today": {
        "model": {
            "category": "plan",
            "title":    "Сегодня срок по плану",
            "body":     "Сегодня срок по плану. Не успеваете — можно попросить перенос",
            "deep_link":"cabinet://plan/item",
        },
        "owner": {
            "category": "plan",
            "title":    "Deadline today",
            "body":     "Plan item deadline is today.",
            "deep_link":"remote://plan/item",
        },
    },

    # ── Work lifecycle ────────────────────────────────────────────────────────
    "work_accepted": {
        "model": {
            "category": "plan",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan/work",
        },
        "owner": {
            "category": "publications",
            "title":    "Work accepted",
            "body":     "Work has been accepted.",
            "deep_link":"remote://review",
        },
    },
    "work_published": {
        "model": {
            "category": "plan",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan/work",
        },
        "owner": {
            "category": "publications",
            "title":    "Published",
            "body":     "Work has been published.",
            "deep_link":"remote://publications",
        },
    },
    "work_replace_files": {
        "model": {
            "category": "plan",
            "title":    "Есть комментарий к работе",
            "body":     "Есть комментарий к работе",
            "deep_link":"cabinet://plan/work",
        },
        "owner": {
            "category": "plan",
            "title":    "Files replacement requested",
            "body":     "Replacement files have been requested.",
            "deep_link":"remote://review",
        },
    },
    "work_rejected": {
        "model": {
            "category": "plan",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan/work",
        },
        "owner": {
            "category": "plan",
            "title":    "Work rejected",
            "body":     "Work was not accepted.",
            "deep_link":"remote://review",
        },
    },
    "work_deadline_postpone_answer": {
        "model": {
            "category": "plan",
            "title":    "Есть ответ по сроку",
            "body":     "Есть ответ по сроку",
            "deep_link":"cabinet://plan/item",
        },
        "owner": {
            "category": "plan",
            "title":    "Deadline postpone answered",
            "body":     "A deadline postponement request was answered.",
            "deep_link":"remote://plan",
        },
    },

    # ── Requests ──────────────────────────────────────────────────────────────
    "request_answered": {
        "model": {
            "category": "requests",
            "title":    "Команда ответила",
            "body":     "Команда ответила",
            "deep_link":"cabinet://requests",
        },
        "owner": {
            "category": "requests",
            "title":    "Request answered",
            "body":     "A model request was answered.",
            "deep_link":"remote://requests",
        },
    },

    # ── Money (model) ─────────────────────────────────────────────────────────
    "period_draft_ready": {
        "model": {
            "category": "money",
            "title":    "Есть новости по деньгам",
            "body":     "Есть новости по деньгам",
            "deep_link":"cabinet://money/period",
        },
        "owner": {
            "category": "money",
            "title":    "Period draft ready",
            "body":     "Period calculation is ready for review.",
            "deep_link":"remote://money/period",
        },
    },
    "period_needs_review": {
        "model": {
            "category": "money",
            "title":    "Есть новости по деньгам",
            "body":     "Есть новости по деньгам",
            "deep_link":"cabinet://money/period",
        },
        "owner": {
            "category": "money",
            "title":    "Period needs review",
            "body":     "Discrepancy detected — manual review required.",
            "deep_link":"remote://money/period",
        },
    },
    "payout_sent": {
        "model": {
            "category": "money",
            "title":    "Есть новости по выплате",
            "body":     "Есть новости по выплате",
            "deep_link":"cabinet://money/payout",
        },
        "owner": {
            "category": "money",
            "title":    "Payout sent",
            "body":     "Payout has been sent.",
            "deep_link":"remote://money/payout",
        },
    },
    "payout_confirm_reminder": {
        "model": {
            "category": "money",
            "title":    "Проверьте, пришли ли деньги",
            "body":     "Проверьте, пришли ли деньги",
            "deep_link":"cabinet://money/payout",
        },
        "owner": {
            "category": "money",
            "title":    "Awaiting receipt confirmation",
            "body":     "Waiting for model to confirm receipt.",
            "deep_link":"remote://money/payout",
        },
    },

    # ── Lessons ───────────────────────────────────────────────────────────────
    "new_lesson": {
        "model": {
            "category": "plan",
            "title":    "Новый урок",
            "body":     "Новый урок",
            "deep_link":"cabinet://lessons",
        },
        "owner": {
            "category": "plan",
            "title":    "New lesson published",
            "body":     "A new lesson was published.",
            "deep_link":"remote://lessons",
        },
    },

    # ── Security (cannot be disabled for model, TZ §D2) ──────────────────────
    "new_device_login": {
        "model": {
            "category": "accounts",
            "title":    "Вход с нового устройства",
            "body":     "Вход с нового устройства. Если это не вы — напишите владельцам",
            "deep_link":"cabinet://security",
            "undisableable": True,
        },
        "owner": {
            "category": "accounts",
            "title":    "New device login",
            "body":     "A new device login was detected.",
            "deep_link":"remote://security",
        },
    },

    # ══════════════════════════════════════════════════════════════════════════
    # D4 — Пульт (owners)
    # urgent=True → APNs interruption-level: time-sensitive
    # ══════════════════════════════════════════════════════════════════════════

    "owner_new_request": {
        "model": {
            "category": "requests",
            "title":    "Команда ответила",
            "body":     "Команда ответила",
            "deep_link":"cabinet://requests",
        },
        "owner": {
            "category": "requests",
            "title":    "New request",
            "body":     "New request from a model.",
            "deep_link":"remote://requests",
        },
    },
    "owner_work_for_review": {
        "model": {
            "category": "plan",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan",
        },
        "owner": {
            "category": "plan",
            "title":    "Work for review",
            "body":     "Work submitted for review.",
            "deep_link":"remote://review",
        },
    },
    "owner_approval_needed": {
        "model": {
            "category": "plan",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan",
        },
        "owner": {
            "category": "publications",
            "title":    "Your approval needed",
            "body":     "Approval required (2 of 3).",
            "deep_link":"remote://approvals",
        },
    },
    "owner_ready_to_send": {
        "model": {
            "category": "publications",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan",
        },
        "owner": {
            "category": "publications",
            "title":    "Ready to send",
            "body":     "Ready to send — awaiting confirmation.",
            "deep_link":"remote://publications",
        },
    },

    # ── Urgent owner alerts (time-sensitive APNs) ─────────────────────────────
    "publisher_stopped": {
        "model": {
            "category": "accounts",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan",
        },
        "owner": {
            "category": "accounts",
            "title":    "Publisher stopped — action required",
            "body":     "Publisher needs human intervention.",
            "deep_link":"remote://accounts",
            "urgent":   True,
        },
    },
    "account_warning": {
        "model": {
            "category": "accounts",
            "title":    "Ограничения аккаунта",
            "body":     "Аккаунт может быть временно ограничен.",
            "deep_link":"cabinet://accounts",
        },
        "owner": {
            "category": "accounts",
            "title":    "Account warning — paused",
            "body":     "Platform warning received. Account paused.",
            "deep_link":"remote://accounts",
            "urgent":   True,
        },
    },
    "smoke_test_failed": {
        "model": {
            "category": "accounts",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan",
        },
        "owner": {
            "category": "accounts",
            "title":    "Smoke test failed",
            "body":     "Platform UI changed — confirmation mode enabled.",
            "deep_link":"remote://accounts",
            "urgent":   True,
        },
    },
    "post_removed_by_platform": {
        "model": {
            "category": "publications",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan",
        },
        "owner": {
            "category": "publications",
            "title":    "Post removed by platform",
            "body":     "A post was removed by the platform.",
            "deep_link":"remote://publications",
            "urgent":   True,
        },
    },
    "payout_needs_human": {
        "model": {
            "category": "money",
            "title":    "Есть новости по выплате",
            "body":     "Есть новости по выплате",
            "deep_link":"cabinet://money/payout",
        },
        "owner": {
            "category": "money",
            "title":    "Payout discrepancy — action required",
            "body":     "Transaction verification failed. Manual check needed.",
            "deep_link":"remote://money/payout",
            "urgent":   True,
        },
    },
    "account_login_expiring": {
        "model": {
            "category": "accounts",
            "title":    "Нужен вход",
            "body":     "Требуется повторная авторизация в аккаунте.",
            "deep_link":"cabinet://accounts",
        },
        "owner": {
            "category": "accounts",
            "title":    "Login expiring soon",
            "body":     "Account login will expire — re-login needed.",
            "deep_link":"remote://accounts",
            "urgent":   True,
        },
    },

    # ── Non-urgent owner ──────────────────────────────────────────────────────
    "ppv_purchased": {
        "model": {
            "category": "money",
            "title":    "Есть новости по выплате",
            "body":     "Есть новости по выплате",
            "deep_link":"cabinet://money",
        },
        "owner": {
            "category": "money",
            "title":    "PPV purchased",
            "body":     "A paid message was purchased.",
            "deep_link":"remote://money",
        },
    },
    "proof_ready": {
        "model": {
            "category": "money",
            "title":    "Есть новости по деньгам",
            "body":     "Есть новости по деньгам",
            "deep_link":"cabinet://money",
        },
        "owner": {
            "category": "money",
            "title":    "Proof ready to send",
            "body":     "Balance proof is ready for review.",
            "deep_link":"remote://money/proof",
        },
    },
    "payout_verified": {
        "model": {
            "category": "money",
            "title":    "Есть новости по выплате",
            "body":     "Есть новости по выплате",
            "deep_link":"cabinet://money/payout",
        },
        "owner": {
            "category": "money",
            "title":    "Payout verified",
            "body":     "Transaction confirmed on chain.",
            "deep_link":"remote://money/payout",
        },
    },
    "content_buffer_low": {
        "model": {
            "category": "plan",
            "title":    "Нужен новый контент",
            "body":     "Запас контента заканчивается, пора снимать!",
            "deep_link":"cabinet://plan",
        },
        "owner": {
            "category": "plan",
            "title":    "Content buffer low",
            "body":     "Scheduled content is running low.",
            "deep_link":"remote://plan/calendar",
        },
    },
    "account_login_required": {
        "model": {
            "category": "accounts",
            "title":    "Нужен вход",
            "body":     "Требуется повторная авторизация в аккаунте.",
            "deep_link":"cabinet://accounts",
        },
        "owner": {
            "category": "accounts",
            "title":    "Account needs re-login",
            "body":     "An account requires re-authentication.",
            "deep_link":"remote://accounts",
        },
    },
    "inbox_unanswered": {
        "model": {
            "category": "requests",
            "title":    "Новые сообщения",
            "body":     "У вас непрочитанные сообщения.",
            "deep_link":"cabinet://inbox",
        },
        "owner": {
            "category": "requests",
            "title":    "Unanswered messages",
            "body":     "Client messages have been waiting > N hours.",
            "deep_link":"remote://inbox",
        },
    },
    "vote_needed": {
        "model": {
            "category": "requests",
            "title":    "Есть вопрос",
            "body":     "Есть вопрос от команды.",
            "deep_link":"cabinet://requests",
        },
        "owner": {
            "category": "requests",
            "title":    "Your vote needed",
            "body":     "A vote or duty transfer requires your input.",
            "deep_link":"remote://today",
        },
    },

    # ── A1/A2: publication results ────────────────────────────────────────────
    "post_published": {
        "model": {
            "category": "publications",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan/work",
        },
        "owner": {
            "category": "publications",
            "title":    "Post live",
            "body":     "Feed post published successfully.",
            "deep_link":"remote://publications",
        },
    },
    "post_needs_confirm": {
        "model": {
            "category": "publications",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan/work",
        },
        "owner": {
            "category": "publications",
            "title":    "Approve post",
            "body":     "A feed post is waiting for your confirmation.",
            "deep_link":"remote://publications",
        },
    },
    "post_failed": {
        "model": {
            "category": "publications",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan/work",
        },
        "owner": {
            "category": "publications",
            "title":    "Post failed — action required",
            "body":     "A feed post failed and needs manual review.",
            "deep_link":"remote://publications",
            "urgent":   True,
        },
    },
    "ppv_sent": {
        "model": {
            "category": "requests",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan",
        },
        "owner": {
            "category": "requests",
            "title":    "PPV sent",
            "body":     "Paid message delivered.",
            "deep_link":"remote://publications",
        },
    },
    "ppv_needs_confirm": {
        "model": {
            "category": "requests",
            "title":    "Есть новости по плану",
            "body":     "Есть новости по плану",
            "deep_link":"cabinet://plan",
        },
        "owner": {
            "category": "requests",
            "title":    "Approve PPV",
            "body":     "A paid message is waiting for your confirmation.",
            "deep_link":"remote://publications",
        },
    },

    # ── D5: daily digest ──────────────────────────────────────────────────────
    "daily_digest": {
        "model": {
            "category": "plan",
            "title":    "Итоги дня",
            "body":     "Итоги дня готовы.",
            "deep_link":"cabinet://plan",
        },
        "owner": {
            "category": "plan",
            "title":    "Daily digest",
            "body":     "Daily metrics digest is ready.",
            "deep_link":"remote://today",
        },
    },
}


def get_text(
    event_type: str,
    user_type:  str,         # "model" | "owner"
    no_text:    bool = False,
) -> dict:
    """
    Returns full catalog entry for event_type + user_type, including:
      title, body, category, deep_link, urgent, undisableable.
    If no_text mode is on (D2 privacy setting), title+body are blanked.
    """
    entry      = CATALOG.get(event_type, {})
    user_entry = entry.get(user_type, entry.get("owner", {}))
    result     = dict(user_entry)
    if no_text:
        result["body"]  = ""
        result["title"] = ""
    return result


def is_urgent(event_type: str) -> bool:
    """Shorthand: True if either model or owner side marks urgent."""
    entry = CATALOG.get(event_type, {})
    return (entry.get("owner", {}).get("urgent", False) or
            entry.get("model", {}).get("urgent", False))
