"""
Thin ORM-like helpers for the tables defined in schema/001_initial.sql.
No ORM framework — raw SQL kept deliberately minimal.

Each class exposes class-methods that wrap db.execute():
  .create(**kwargs) → dict (the inserted row)
  .get(id)          → dict | None
  .update(id, **kwargs) → dict
  .find(**filters)  → list[dict]
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .db import execute, with_conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_set_clause(fields: Dict[str, Any]) -> tuple:
    """Returns (SET clause string, ordered values list) for UPDATE."""
    parts  = []
    values = []
    for k, v in fields.items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v)
        parts.append(f"{k} = %s")
        values.append(v)
    return ", ".join(parts), values


def _build_where_clause(filters: Dict[str, Any]) -> tuple:
    """Returns (WHERE clause string, ordered values list) or ('', [])."""
    if not filters:
        return "", []
    parts  = []
    values = []
    for k, v in filters.items():
        if v is None:
            parts.append(f"{k} IS NULL")
        else:
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            parts.append(f"{k} = %s")
            values.append(v)
    return "WHERE " + " AND ".join(parts), values


# ── platform_accounts ─────────────────────────────────────────────────────────

class PlatformAccount:
    TABLE = "platform_accounts"

    @classmethod
    def create(cls, model_id: str, platform: str, username: str,
               account_type: str = "content", session_file: str = None,
               device_file: str = None, limits: dict = None,
               auto_modes: dict = None) -> Dict:
        row = execute(
            """INSERT INTO platform_accounts
               (id, model_id, platform, account_type, username,
                session_file, device_file, limits, auto_modes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING *""",
            (str(uuid.uuid4()), model_id, platform, account_type, username,
             session_file, device_file,
             json.dumps(limits or {"posts_per_day":3,"messages_per_hour":10,"min_pause_seconds":30}),
             json.dumps(auto_modes or {})),
            fetch="one",
        )
        return dict(row) if row else {}

    @classmethod
    def get(cls, account_id: str) -> Optional[Dict]:
        row = execute(
            "SELECT * FROM platform_accounts WHERE id = %s",
            (account_id,), fetch="one",
        )
        return dict(row) if row else None

    @classmethod
    def find(cls, **filters) -> List[Dict]:
        where, vals = _build_where_clause(filters)
        rows = execute(
            f"SELECT * FROM platform_accounts {where} ORDER BY created_at",
            tuple(vals), fetch="all",
        )
        return [dict(r) for r in (rows or [])]

    @classmethod
    def update_status(cls, account_id: str, status: str) -> None:
        execute(
            "UPDATE platform_accounts SET status=%s WHERE id=%s",
            (status, account_id),
        )


# ── publish_jobs ──────────────────────────────────────────────────────────────

class PublishJob:
    TABLE = "publish_jobs"

    STATUSES = {
        "queued", "running", "awaiting_confirm",
        "published", "sent", "needs_human",
        "failed", "cancelled", "removed_by_platform",
    }

    @classmethod
    def create(cls, account_id: str, job_type: str, payload: dict,
               idempotency_key: str = "", scheduled_for: datetime = None,
               approvals_required: int = 1) -> Dict:
        idem = idempotency_key or str(uuid.uuid4())
        row = execute(
            """INSERT INTO publish_jobs
               (id, idempotency_key, account_id, job_type, status,
                payload, scheduled_for, approvals_required)
               VALUES (%s,%s,%s,%s,'queued',%s,%s,%s)
               ON CONFLICT (idempotency_key) DO NOTHING
               RETURNING *""",
            (str(uuid.uuid4()), idem, account_id, job_type,
             json.dumps(payload), scheduled_for, approvals_required),
            fetch="one",
        )
        return dict(row) if row else {}

    @classmethod
    def get(cls, job_id: str) -> Optional[Dict]:
        row = execute(
            "SELECT * FROM publish_jobs WHERE id = %s",
            (job_id,), fetch="one",
        )
        return dict(row) if row else None

    @classmethod
    def claim_next(cls, conn) -> Optional[Dict]:
        """
        SELECT FOR UPDATE SKIP LOCKED — atomically claim the oldest queued job
        whose scheduled_for is due (or NULL). Caller holds the transaction.
        """
        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM publish_jobs
                   WHERE status = 'queued'
                     AND (scheduled_for IS NULL OR scheduled_for <= NOW())
                   ORDER BY created_at
                   LIMIT 1
                   FOR UPDATE SKIP LOCKED"""
            )
            row = cur.fetchone()
            if not row:
                return None
            job_id = row["id"]
            cur.execute(
                """UPDATE publish_jobs
                   SET status='running', started_at=NOW()
                   WHERE id=%s""",
                (job_id,),
            )
            cur.execute("SELECT * FROM publish_jobs WHERE id=%s", (job_id,))
            return dict(cur.fetchone())

    @classmethod
    def transition(cls, job_id: str, new_status: str,
                   actor_id: str = "system",
                   result: dict = None, error: str = None,
                   external_id: str = None) -> None:
        assert new_status in cls.STATUSES, f"Unknown status: {new_status}"
        with with_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status FROM publish_jobs WHERE id=%s FOR UPDATE",
                    (job_id,)
                )
                row = cur.fetchone()
                if not row:
                    return
                old_status = row["status"]

                extras = []
                vals: list = []
                if result is not None:
                    extras.append("result=%s"); vals.append(json.dumps(result))
                if error is not None:
                    extras.append("error_message=%s"); vals.append(error)
                if external_id is not None:
                    extras.append("external_id=%s"); vals.append(external_id)
                if new_status in ("published","sent","failed","cancelled"):
                    extras.append("finished_at=NOW()")

                extra_sql = (", " + ", ".join(extras)) if extras else ""
                cur.execute(
                    f"UPDATE publish_jobs SET status=%s{extra_sql} WHERE id=%s",
                    [new_status] + vals + [job_id],
                )
                cur.execute(
                    """INSERT INTO publish_events
                       (id, job_id, event_type, old_status, new_status, actor_id, details)
                       VALUES (%s,%s,'status_change',%s,%s,%s,%s)""",
                    (str(uuid.uuid4()), job_id, old_status, new_status, actor_id,
                     json.dumps({"error": error} if error else {})),
                )

    @classmethod
    def pending_approval(cls, job_id: str, owner_id: str) -> bool:
        """Return True if this owner hasn't yet approved this job."""
        row = execute(
            "SELECT approvals FROM publish_jobs WHERE id=%s",
            (job_id,), fetch="one",
        )
        if not row:
            return False
        approvals = row["approvals"] or []
        return not any(a.get("owner_id") == owner_id for a in approvals)

    @classmethod
    def add_approval(cls, job_id: str, owner_id: str) -> Dict:
        with with_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT approvals, approvals_required FROM publish_jobs WHERE id=%s FOR UPDATE",
                    (job_id,)
                )
                row = dict(cur.fetchone())
                approvals = row["approvals"] or []
                approvals.append({"owner_id": owner_id, "approved_at": _now_iso()})
                cur.execute(
                    "UPDATE publish_jobs SET approvals=%s WHERE id=%s",
                    (json.dumps(approvals), job_id),
                )
                if len(approvals) >= row["approvals_required"]:
                    cur.execute(
                        "UPDATE publish_jobs SET status='queued' WHERE id=%s AND status='awaiting_confirm'",
                        (job_id,),
                    )
                    return {"promoted": True, "approvals": len(approvals)}
                return {"promoted": False, "approvals": len(approvals)}


# ── account_metrics ───────────────────────────────────────────────────────────

class AccountMetrics:
    @classmethod
    def upsert(cls, account_id: str, date: str, data: Dict) -> None:
        execute(
            """INSERT INTO account_metrics
               (id, account_id, date, subscribers_total, subscribers_new,
                subscribers_churned, subscribers_renewed, income_total_cents,
                income_subscriptions_cents, income_ppv_cents, income_tips_cents,
                chargebacks_cents, post_views, raw)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (account_id, date) DO UPDATE SET
                 subscribers_total=EXCLUDED.subscribers_total,
                 subscribers_new=EXCLUDED.subscribers_new,
                 subscribers_churned=EXCLUDED.subscribers_churned,
                 subscribers_renewed=EXCLUDED.subscribers_renewed,
                 income_total_cents=EXCLUDED.income_total_cents,
                 income_subscriptions_cents=EXCLUDED.income_subscriptions_cents,
                 income_ppv_cents=EXCLUDED.income_ppv_cents,
                 income_tips_cents=EXCLUDED.income_tips_cents,
                 chargebacks_cents=EXCLUDED.chargebacks_cents,
                 post_views=EXCLUDED.post_views,
                 raw=EXCLUDED.raw,
                 collected_at=NOW()""",
            (str(uuid.uuid4()), account_id, date,
             data.get("subscribers_total"),     data.get("subscribers_new"),
             data.get("subscribers_churned"),   data.get("subscribers_renewed"),
             data.get("income_total_cents"),    data.get("income_subscriptions_cents"),
             data.get("income_ppv_cents"),      data.get("income_tips_cents"),
             data.get("chargebacks_cents"),     data.get("post_views"),
             json.dumps(data.get("raw", {}))),
        )


# ── period_drafts ─────────────────────────────────────────────────────────────

class PeriodDraft:
    @classmethod
    def create_or_update(cls, model_id: str, period_start: str,
                          period_end: str, gross_cents: int,
                          platform_fee_cents: int, chargebacks_cents: int,
                          agency_pct: float, daily_sum_cents: int = None,
                          formula_snapshot: dict = None) -> Dict:
        row = execute(
            """INSERT INTO period_drafts
               (id, model_id, period_start, period_end, gross_cents,
                platform_fee_cents, chargebacks_cents, agency_pct,
                daily_sum_cents, formula_snapshot)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (model_id, period_start, period_end) DO UPDATE SET
                 gross_cents=EXCLUDED.gross_cents,
                 platform_fee_cents=EXCLUDED.platform_fee_cents,
                 chargebacks_cents=EXCLUDED.chargebacks_cents,
                 agency_pct=EXCLUDED.agency_pct,
                 daily_sum_cents=EXCLUDED.daily_sum_cents,
                 formula_snapshot=EXCLUDED.formula_snapshot,
                 updated_at=NOW()
               RETURNING *""",
            (str(uuid.uuid4()), model_id, period_start, period_end,
             gross_cents, platform_fee_cents, chargebacks_cents,
             str(agency_pct), daily_sum_cents,
             json.dumps(formula_snapshot or {})),
            fetch="one",
        )
        return dict(row) if row else {}

    @classmethod
    def get_for_model(cls, model_id: str, period_start: str = None) -> List[Dict]:
        if period_start:
            rows = execute(
                "SELECT * FROM period_drafts WHERE model_id=%s AND period_start=%s ORDER BY period_start DESC",
                (model_id, period_start), fetch="all",
            )
        else:
            rows = execute(
                "SELECT * FROM period_drafts WHERE model_id=%s ORDER BY period_start DESC LIMIT 12",
                (model_id,), fetch="all",
            )
        return [dict(r) for r in (rows or [])]


# ── audit_log ─────────────────────────────────────────────────────────────────

class AuditLog:
    @classmethod
    def write(cls, actor_id: str, actor_type: str, action: str,
              entity_type: str = None, entity_id: str = None,
              details: dict = None, ip_address: str = None) -> None:
        execute(
            """INSERT INTO audit_log
               (actor_id, actor_type, action, entity_type, entity_id, details, ip_address)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (actor_id, actor_type, action, entity_type, entity_id,
             json.dumps(details or {}), ip_address),
        )
