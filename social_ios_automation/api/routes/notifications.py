"""
/notifications — Notification management endpoints.

POST /notifications/device          — register APNs device token
DELETE /notifications/device/{token} — unregister
GET  /notifications/                — list notifications for a user
POST /notifications/{id}/read       — mark notification read
GET  /notifications/settings        — get user's notification settings
PUT  /notifications/settings        — update settings
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel

from ...engine.db import execute

router = APIRouter()


class RegisterDeviceRequest(BaseModel):
    user_id:     str
    app:         str       # cabinet | remote
    apns_token:  str
    environment: str = "production"


class UpdateSettingsRequest(BaseModel):
    user_id:      str
    category:     str
    enabled:      Optional[bool] = None
    quiet_start:  Optional[str]  = None   # "23:00"
    quiet_end:    Optional[str]  = None   # "08:00"
    no_text_mode: Optional[bool] = None
    badge_enabled: Optional[bool] = None
    timezone:     Optional[str]  = None


@router.post("/device", status_code=201)
async def register_device(body: RegisterDeviceRequest,
                          x_api_key: Optional[str] = Header(None)):
    row = execute(
        """INSERT INTO devices (id, user_id, app, apns_token, environment)
           VALUES (%s,%s,%s,%s,%s)
           ON CONFLICT (apns_token, app) DO UPDATE SET
             user_id=EXCLUDED.user_id,
             environment=EXCLUDED.environment,
             last_active=NOW()
           RETURNING *""",
        (str(uuid.uuid4()), body.user_id, body.app,
         body.apns_token, body.environment),
        fetch="one",
    )
    return dict(row) if row else {}


@router.delete("/device/{token}", status_code=204)
async def unregister_device(token: str, app: str = Query("cabinet"),
                             x_api_key: Optional[str] = Header(None)):
    execute("DELETE FROM devices WHERE apns_token=%s AND app=%s", (token, app))


@router.get("/")
async def list_notifications(
    user_id:   str            = Query(...),
    unread_only: bool         = Query(False),
    limit:     int            = Query(50, le=200),
    x_api_key: Optional[str] = Header(None),
):
    conditions = ["user_id=%s"]
    params     = [user_id]
    if unread_only:
        conditions.append("read_at IS NULL")

    where = "WHERE " + " AND ".join(conditions)
    rows  = execute(
        f"SELECT * FROM notifications {where} ORDER BY created_at DESC LIMIT %s",
        tuple(params + [limit]), fetch="all",
    )
    return [dict(r) for r in (rows or [])]


@router.post("/{notif_id}/read")
async def mark_read(notif_id: str, x_api_key: Optional[str] = Header(None)):
    execute(
        "UPDATE notifications SET read_at=NOW(), status='read' WHERE id=%s",
        (notif_id,),
    )
    return {"status": "read", "id": notif_id}


@router.get("/settings")
async def get_settings(user_id:   str            = Query(...),
                       x_api_key: Optional[str] = Header(None)):
    rows = execute(
        "SELECT * FROM notification_settings WHERE user_id=%s",
        (user_id,), fetch="all",
    )
    return [dict(r) for r in (rows or [])]


@router.put("/settings")
async def update_settings(body: UpdateSettingsRequest,
                          x_api_key: Optional[str] = Header(None)):
    fields: dict = {}
    if body.enabled      is not None: fields["enabled"]       = body.enabled
    if body.quiet_start  is not None: fields["quiet_start"]   = body.quiet_start
    if body.quiet_end    is not None: fields["quiet_end"]     = body.quiet_end
    if body.no_text_mode is not None: fields["no_text_mode"]  = body.no_text_mode
    if body.badge_enabled is not None: fields["badge_enabled"]= body.badge_enabled
    if body.timezone     is not None: fields["timezone"]      = body.timezone

    if not fields:
        raise HTTPException(400, "no fields to update")

    set_parts = [f"{k}=%s" for k in fields]
    values    = list(fields.values()) + [body.user_id, body.category]

    execute(
        f"""INSERT INTO notification_settings (id, user_id, category)
            VALUES (%s,%s,%s)
            ON CONFLICT (user_id, category) DO UPDATE SET
              {", ".join(set_parts)}""",
        tuple([str(uuid.uuid4()), body.user_id, body.category] + list(fields.values())),
    )
    row = execute(
        "SELECT * FROM notification_settings WHERE user_id=%s AND category=%s",
        (body.user_id, body.category), fetch="one",
    )
    return dict(row) if row else {}
