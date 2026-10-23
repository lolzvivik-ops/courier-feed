"""
B1 — Account health monitoring.

smoke_test(account)  → HealthResult
run_all_checks()     → list[HealthResult]

HealthResult.status: "ok" | "login_required" | "limited" | "paused" | "disabled"

Called by scheduler.py once per hour.  On login_required the account's
DB row is updated so the publisher skips it and the owner gets a push.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .models import PlatformAccount, AuditLog

logger = logging.getLogger(__name__)


@dataclass
class HealthResult:
    account_id: str
    platform:   str
    username:   str
    status:     str          # ok | login_required | limited | paused | disabled
    detail:     str = ""
    raw:        dict = field(default_factory=dict)


def smoke_test(account: Dict, client: Any) -> HealthResult:
    """
    Call the cheapest authenticated endpoint and map the result to a status.
    Platform-agnostic: each branch calls verify_session or equivalent.
    """
    acct_id  = account["id"]
    platform = account["platform"]
    username = account.get("username","")

    try:
        if platform == "fansly":
            ok = client.verify_session()
            if not ok:
                return HealthResult(acct_id, platform, username, "login_required",
                                    "token expired or revoked")
            return HealthResult(acct_id, platform, username, "ok")

        if platform == "instagram":
            resp = client.get(
                "/accounts/current_user/",
                params={"edit": "true"},
            ).json()
            if resp.get("status") == "ok":
                return HealthResult(acct_id, platform, username, "ok")
            if resp.get("message","").lower() in ("login_required","not_authorized"):
                return HealthResult(acct_id, platform, username, "login_required",
                                    resp.get("message",""))
            return HealthResult(acct_id, platform, username, "limited",
                                resp.get("message",""), resp)

        if platform == "tiktok":
            resp = client.get(
                "/passport/user/info/",
                params={"iid": getattr(client,"_install_id","0")},
            ).json()
            if str(resp.get("error_code","0")) == "0":
                return HealthResult(acct_id, platform, username, "ok")
            return HealthResult(acct_id, platform, username, "login_required",
                                str(resp.get("error_code","?")), resp)

        if platform == "x":
            resp = client.get("/1.1/account/verify_credentials.json").json()
            if resp.get("id"):
                return HealthResult(acct_id, platform, username, "ok")
            return HealthResult(acct_id, platform, username, "login_required",
                                str(resp.get("errors",[])), resp)

        if platform == "reddit":
            resp = client.get("/api/v1/me").json()
            if resp.get("name"):
                return HealthResult(acct_id, platform, username, "ok")
            return HealthResult(acct_id, platform, username, "login_required",
                                resp.get("message",""), resp)

        return HealthResult(acct_id, platform, username, "ok", "no check for platform")

    except Exception as exc:
        logger.warning("Health check failed for %s %s: %s", platform, username, exc)
        return HealthResult(acct_id, platform, username, "limited",
                            str(exc))


def run_all_checks(
    accounts: List[Dict],
    client_factory: Callable[[str, Dict], Any],
    notify: Optional[Callable[[str, str, str], None]] = None,
) -> List[HealthResult]:
    """
    Check every account.  Persist status changes to DB and emit audit events.
    notify(owner_id, account_id, new_status) — used to push alerts to Пульт.
    """
    results = []
    for account in accounts:
        try:
            client = client_factory(account["platform"], account)
            result = smoke_test(account, client)
        except Exception as exc:
            result = HealthResult(
                account["id"], account["platform"], account.get("username",""),
                "limited", f"client build failed: {exc}",
            )

        old_status = account.get("status","ok")
        if result.status != old_status:
            PlatformAccount.update_status(account["id"], result.status)
            AuditLog.write(
                "system", "system", "account_status_change",
                "platform_account", account["id"],
                {"old": old_status, "new": result.status, "detail": result.detail},
            )
            if notify and result.status in ("login_required","disabled"):
                try:
                    notify("system", account["id"], result.status)
                except Exception:
                    pass

        logger.info("Health %s %s → %s", result.platform, result.username, result.status)
        results.append(result)
    return results
