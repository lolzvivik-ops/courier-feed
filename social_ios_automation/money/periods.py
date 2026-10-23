"""
C1 — Period draft calculation.

Fansly pays out twice a month:
  Period 1: 1st  – 15th  (payout arrives ~20th)
  Period 2: 16th – last  (payout arrives ~5th of next month)

calculate_period(model_id, fansly_client, period_start, period_end)
  → PeriodResult

Daily income rows are summed and cross-checked against the dashboard
total.  Discrepancy > 2% → needs_review = True.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from ..engine.models import PeriodDraft

logger = logging.getLogger(__name__)

_PLATFORM_FEE_PCT = 0.20   # Fansly charges 20% of gross
_DEFAULT_AGENCY_PCT = 0.25  # default agency split


@dataclass
class PeriodResult:
    model_id:            str
    period_start:        str
    period_end:          str
    gross_cents:         int
    platform_fee_cents:  int
    chargebacks_cents:   int
    base_cents:          int     # gross - fee - chargebacks
    agency_pct:          float
    agency_cents:        int
    model_cents:         int
    daily_sum_cents:     int
    discrepancy_pct:     float
    needs_review:        bool
    draft_id:            Optional[str] = None


def _date_to_unix(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, 0, 0, tzinfo=timezone.utc).timestamp())


def calculate_period(
    model_id:           str,
    fansly_client,
    period_start:       str,    # "YYYY-MM-DD"
    period_end:         str,
    agency_pct:         float   = _DEFAULT_AGENCY_PCT,
    platform_fee_pct:   float   = _PLATFORM_FEE_PCT,
) -> PeriodResult:
    """
    Fetch dashboard summary for the period, plus daily rows for cross-check,
    then persist a period_draft.
    """
    start_d = date.fromisoformat(period_start)
    end_d   = date.fromisoformat(period_end)
    start_ts = _date_to_unix(start_d)
    end_ts   = _date_to_unix(end_d) + 86399

    # ── dashboard total ──────────────────────────────────────────────────────
    summary = fansly_client.get_earnings_summary(start_ts, end_ts)
    gross_cents       = summary.get("total_cents", 0)
    chargebacks_cents = summary.get("chargebacks", 0)

    # ── daily cross-check ────────────────────────────────────────────────────
    daily_sum = 0
    day = start_d
    while day <= end_d:
        day_ts = _date_to_unix(day)
        try:
            daily_sum += fansly_client.get_daily_income(day_ts)
        except Exception as exc:
            logger.warning("Daily income fetch failed for %s: %s", day, exc)
        import datetime as _dt
        day = day + _dt.timedelta(days=1)

    # ── calculations ─────────────────────────────────────────────────────────
    platform_fee_cents = int(round(gross_cents * platform_fee_pct))
    base_cents         = gross_cents - platform_fee_cents - chargebacks_cents
    agency_cents       = int(round(base_cents * agency_pct))
    model_cents        = base_cents - agency_cents

    discrepancy_pct: float = 0.0
    if gross_cents > 0:
        discrepancy_pct = abs(gross_cents - daily_sum) / gross_cents * 100

    needs_review = discrepancy_pct > 2.0 or chargebacks_cents > 0

    formula_snapshot = {
        "gross":            gross_cents,
        "platform_fee_pct": platform_fee_pct,
        "platform_fee":     platform_fee_cents,
        "chargebacks":      chargebacks_cents,
        "base":             base_cents,
        "agency_pct":       agency_pct,
        "agency":           agency_cents,
        "model":            model_cents,
        "daily_sum":        daily_sum,
        "discrepancy_pct":  discrepancy_pct,
    }

    row = PeriodDraft.create_or_update(
        model_id           = model_id,
        period_start       = period_start,
        period_end         = period_end,
        gross_cents        = gross_cents,
        platform_fee_cents = platform_fee_cents,
        chargebacks_cents  = chargebacks_cents,
        agency_pct         = agency_pct,
        daily_sum_cents    = daily_sum,
        formula_snapshot   = formula_snapshot,
    )

    return PeriodResult(
        model_id           = model_id,
        period_start       = period_start,
        period_end         = period_end,
        gross_cents        = gross_cents,
        platform_fee_cents = platform_fee_cents,
        chargebacks_cents  = chargebacks_cents,
        base_cents         = base_cents,
        agency_pct         = agency_pct,
        agency_cents       = agency_cents,
        model_cents        = model_cents,
        daily_sum_cents    = daily_sum,
        discrepancy_pct    = discrepancy_pct,
        needs_review       = needs_review,
        draft_id           = row.get("id"),
    )


def current_period_dates() -> tuple:
    """Return (start, end) YYYY-MM-DD strings for the current billing period."""
    today = date.today()
    if today.day <= 15:
        start = date(today.year, today.month, 1).isoformat()
        end   = date(today.year, today.month, 15).isoformat()
    else:
        import calendar as _cal
        last  = _cal.monthrange(today.year, today.month)[1]
        start = date(today.year, today.month, 16).isoformat()
        end   = date(today.year, today.month, last).isoformat()
    return start, end
