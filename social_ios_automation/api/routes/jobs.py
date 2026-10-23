"""
/jobs — Publish job management.

POST /jobs/               — enqueue a new job
GET  /jobs/{job_id}       — get job status
POST /jobs/{job_id}/approve — owner approves awaiting_confirm job
POST /jobs/{job_id}/cancel  — cancel a queued or awaiting_confirm job
GET  /jobs/               — list jobs for a model/account
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel

from ...engine.models import PublishJob, PlatformAccount, AuditLog

router = APIRouter()


class CreateJobRequest(BaseModel):
    account_id:      str
    job_type:        str
    payload:         dict = {}
    idempotency_key: Optional[str] = None
    scheduled_for:   Optional[datetime] = None


class ApproveRequest(BaseModel):
    owner_id: str


@router.post("/", status_code=201)
async def create_job(body: CreateJobRequest,
                     x_api_key: Optional[str] = Header(None)):
    account = PlatformAccount.get(body.account_id)
    if not account:
        raise HTTPException(404, "account not found")

    job = PublishJob.create(
        account_id       = body.account_id,
        job_type         = body.job_type,
        payload          = body.payload,
        idempotency_key  = body.idempotency_key or str(uuid.uuid4()),
        scheduled_for    = body.scheduled_for,
    )
    if not job:
        raise HTTPException(409, "duplicate idempotency_key")

    AuditLog.write(
        "api", "system", "job_created",
        "publish_job", job.get("id"),
        {"type": body.job_type, "account": body.account_id},
    )
    return job


@router.get("/{job_id}")
async def get_job(job_id: str, x_api_key: Optional[str] = Header(None)):
    job = PublishJob.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


@router.post("/{job_id}/approve")
async def approve_job(job_id: str, body: ApproveRequest,
                      x_api_key: Optional[str] = Header(None)):
    job = PublishJob.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job["status"] != "awaiting_confirm":
        raise HTTPException(400, f"job is in status {job['status']}, not awaiting_confirm")

    result = PublishJob.add_approval(job_id, body.owner_id)
    AuditLog.write(body.owner_id, "owner", "job_approved",
                   "publish_job", job_id, result)
    return result


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, x_api_key: Optional[str] = Header(None)):
    job = PublishJob.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job["status"] not in ("queued", "awaiting_confirm"):
        raise HTTPException(400, f"cannot cancel job in status {job['status']}")

    PublishJob.transition(job_id, "cancelled", actor_id="api")
    AuditLog.write("api", "system", "job_cancelled", "publish_job", job_id)
    return {"status": "cancelled", "job_id": job_id}


@router.get("/")
async def list_jobs(
    account_id: Optional[str] = Query(None),
    model_id:   Optional[str] = Query(None),
    status:     Optional[str] = Query(None),
    limit:      int            = Query(50, le=200),
    x_api_key:  Optional[str] = Header(None),
):
    from ...engine.db import execute
    conditions = []
    params     = []

    if account_id:
        conditions.append("pj.account_id = %s"); params.append(account_id)
    if model_id:
        conditions.append("pa.model_id = %s");   params.append(model_id)
    if status:
        conditions.append("pj.status = %s");     params.append(status)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = execute(
        f"""SELECT pj.*
            FROM publish_jobs pj
            JOIN platform_accounts pa ON pa.id = pj.account_id
            {where}
            ORDER BY pj.created_at DESC LIMIT %s""",
        tuple(params + [limit]), fetch="all",
    )
    return [dict(r) for r in (rows or [])]
