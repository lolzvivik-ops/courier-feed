"""
/accounts — Platform account management.

POST /accounts/                  — register account in DB
GET  /accounts/{id}              — get account details
GET  /accounts/                  — list (by model_id / platform / status)
POST /accounts/{id}/auto-modes   — toggle auto-mode flags
GET  /accounts/{id}/metrics      — last N days of account_metrics
POST /accounts/{id}/health-check — trigger on-demand smoke test
"""

import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel

from ...engine.models import PlatformAccount, AuditLog
from ...engine.db import execute

router = APIRouter()


class CreateAccountRequest(BaseModel):
    model_id:     str
    platform:     str
    username:     str
    account_type: str = "content"
    session_file: Optional[str] = None
    device_file:  Optional[str] = None
    limits:       Optional[Dict] = None
    auto_modes:   Optional[Dict] = None


class AutoModesRequest(BaseModel):
    owner_id:   str
    auto_modes: Dict[str, bool]   # {"feed_post": True, "ppv_message": False}


@router.post("/", status_code=201)
async def create_account(body: CreateAccountRequest,
                         x_api_key: Optional[str] = Header(None)):
    row = PlatformAccount.create(
        model_id     = body.model_id,
        platform     = body.platform,
        username     = body.username,
        account_type = body.account_type,
        session_file = body.session_file,
        device_file  = body.device_file,
        limits       = body.limits,
        auto_modes   = body.auto_modes,
    )
    if not row:
        raise HTTPException(409, "account already exists")
    AuditLog.write("api", "system", "account_created",
                   "platform_account", row.get("id"),
                   {"platform": body.platform, "username": body.username})
    return row


@router.get("/{account_id}")
async def get_account(account_id: str, x_api_key: Optional[str] = Header(None)):
    row = PlatformAccount.get(account_id)
    if not row:
        raise HTTPException(404, "account not found")
    return row


@router.get("/")
async def list_accounts(
    model_id:  Optional[str] = Query(None),
    platform:  Optional[str] = Query(None),
    status:    Optional[str] = Query(None),
    limit:     int            = Query(100, le=500),
    x_api_key: Optional[str] = Header(None),
):
    filters: dict = {}
    if model_id: filters["model_id"] = model_id
    if platform: filters["platform"] = platform
    if status:   filters["status"]   = status
    return PlatformAccount.find(**filters)[:limit]


@router.post("/{account_id}/auto-modes")
async def update_auto_modes(account_id: str, body: AutoModesRequest,
                             x_api_key: Optional[str] = Header(None)):
    row = PlatformAccount.get(account_id)
    if not row:
        raise HTTPException(404, "account not found")

    existing = row.get("auto_modes") or {}
    existing.update(body.auto_modes)

    import json
    execute(
        "UPDATE platform_accounts SET auto_modes=%s WHERE id=%s",
        (json.dumps(existing), account_id),
    )
    AuditLog.write(body.owner_id, "owner", "auto_modes_updated",
                   "platform_account", account_id, body.auto_modes)
    return {"account_id": account_id, "auto_modes": existing}


@router.get("/{account_id}/metrics")
async def get_metrics(
    account_id: str,
    days:       int           = Query(30, le=365),
    x_api_key:  Optional[str] = Header(None),
):
    rows = execute(
        """SELECT * FROM account_metrics
           WHERE account_id=%s
           ORDER BY date DESC LIMIT %s""",
        (account_id, days), fetch="all",
    )
    return [dict(r) for r in (rows or [])]


@router.post("/{account_id}/health-check")
async def trigger_health_check(account_id: str,
                                x_api_key: Optional[str] = Header(None)):
    """
    On-demand health check — returns current DB status.
    Full smoke test requires running with the client factory; here we return
    the DB-persisted status and last check time.
    """
    row = PlatformAccount.get(account_id)
    if not row:
        raise HTTPException(404, "account not found")
    return {
        "account_id": account_id,
        "status":     row.get("status"),
        "last_check": row.get("last_login_check"),
        "note":       "Full re-check runs on next scheduler cycle",
    }
