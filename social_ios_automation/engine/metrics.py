"""
B5 — Daily statistics collection.

collect_daily(account, client, date_str)  → MetricsResult
run_collection(accounts, client_factory)  → list[MetricsResult]

Normalises raw Fansly dashboard data into account_metrics rows.
Called by scheduler every day at ~03:00 UTC after the platform
closes the previous day's books.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .models import AccountMetrics, AuditLog

logger = logging.getLogger(__name__)


@dataclass
class MetricsResult:
    account_id:  str
    date:        str
    status:      str           # ok | error | partial
    data:        dict = field(default_factory=dict)
    error:       Optional[str] = None


def _day_bounds_unix(date_str: str) -> tuple:
    """Return (start_ts, end_ts) UTC Unix timestamps for a YYYY-MM-DD date."""
    d  = date.fromisoformat(date_str)
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    start = int(dt.timestamp())
    end   = start + 86399
    return start, end


def collect_daily(
    account:    Dict,
    client:     Any,
    date_str:   Optional[str] = None,
) -> MetricsResult:
    """
    Pull one day of metrics from Fansly dashboard + subscriber stats.
    Falls back gracefully if sub-endpoints are unavailable.
    """
    if date_str is None:
        date_str = date.today().isoformat()

    acct_id  = account["id"]
    platform = account["platform"]

    if platform != "fansly":
        # Social platform post metrics (Instagram, TikTok, X, Reddit)
        # — per-post metrics are pulled separately via collect_post_metrics()
        return MetricsResult(acct_id, date_str, "partial",
                             error="post-level collection only for social platforms")

    start_ts, end_ts = _day_bounds_unix(date_str)
    data: Dict = {}

    try:
        dash = client.get_dashboard_stats(start_ts, end_ts)
        earnings = dash.get("response", {}).get("earnings", {})

        data["income_total_cents"]         = earnings.get("total", 0)
        data["income_subscriptions_cents"] = earnings.get("subscriptions", 0)
        data["income_ppv_cents"]           = earnings.get("ppv", 0)
        data["income_tips_cents"]          = earnings.get("tips", 0)
        data["chargebacks_cents"]          = earnings.get("chargebacks", 0)
        data["raw"]                        = dash.get("response", {})
    except Exception as exc:
        logger.warning("Dashboard stats failed for %s: %s", acct_id, exc)
        return MetricsResult(acct_id, date_str, "error", error=str(exc))

    try:
        sub_stats = client.get_subscriber_stats()
        sub_data  = sub_stats.get("response", {})
        data["subscribers_total"]   = sub_data.get("total", 0)
        data["subscribers_new"]     = sub_data.get("new", 0)
        data["subscribers_churned"] = sub_data.get("expired", 0)
        data["subscribers_renewed"] = sub_data.get("renewed", 0)
    except Exception as exc:
        logger.warning("Subscriber stats failed for %s: %s", acct_id, exc)

    AccountMetrics.upsert(acct_id, date_str, data)
    AuditLog.write("system","system","metrics_collected","platform_account",
                   acct_id, {"date": date_str, "total": data.get("income_total_cents",0)})

    return MetricsResult(acct_id, date_str, "ok", data=data)


def run_collection(
    accounts:       List[Dict],
    client_factory: Callable[[str, Dict], Any],
    date_str:       Optional[str] = None,
    delay_between:  float = 2.0,
) -> List[MetricsResult]:
    results = []
    for account in accounts:
        if account.get("status","ok") in ("disabled","login_required"):
            logger.info("Skip metrics for %s (status=%s)",
                        account.get("username"), account.get("status"))
            continue
        try:
            client = client_factory(account["platform"], account)
            result = collect_daily(account, client, date_str)
        except Exception as exc:
            result = MetricsResult(account["id"], date_str or "?",
                                   "error", error=str(exc))
        results.append(result)
        time.sleep(delay_between)
    return results
