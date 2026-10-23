"""
Job queue worker.

State machine:
  queued → running → [awaiting_confirm | published | sent | needs_human | failed]
  awaiting_confirm → [queued (after approval) | cancelled]

Uses SELECT FOR UPDATE SKIP LOCKED so multiple worker processes can run
safely without double-processing the same job.

Entry points:
  Worker(clients_factory).run_once()  — process one job, return result
  Worker(clients_factory).run_loop()  — block and process continuously
"""

import logging
import time
import traceback
import uuid
from typing import Any, Callable, Dict, Optional

from .db   import get_conn, release
from .models import PublishJob, PlatformAccount, AuditLog

logger = logging.getLogger(__name__)

# ── client-type imports (deferred to avoid circular) ─────────────────────────
# The worker receives a factory callable that builds platform clients on demand.
# Signature: clients_factory(platform: str, account: dict) → platform_client


class Worker:
    """
    Single-threaded job worker.
    clients_factory: (platform, account_row) → platform client instance
    auto_mode_check: (account_id, job_type) → bool  (True = execute without confirmation)
    notify_owner:    (owner_id, job_id, job_type) → None  (sends push to Пульт app)
    """

    def __init__(
        self,
        clients_factory: Callable[[str, dict], Any],
        auto_mode_check: Optional[Callable[[str, str], bool]] = None,
        notify_owner:    Optional[Callable[[str, str, str], None]] = None,
    ):
        self._factory       = clients_factory
        self._auto_check    = auto_mode_check or (lambda acct_id, job_type: False)
        self._notify_owner  = notify_owner or (lambda *a: None)

    # ── main loop ─────────────────────────────────────────────────────────────

    def run_loop(self, poll_interval: float = 5.0) -> None:
        logger.info("Worker starting, poll_interval=%.1fs", poll_interval)
        while True:
            try:
                result = self.run_once()
                if not result:
                    time.sleep(poll_interval)
            except Exception:
                logger.exception("Worker loop error")
                time.sleep(poll_interval)

    def run_once(self) -> Optional[Dict]:
        """Claim and execute one job. Returns job result dict or None."""
        conn = get_conn()
        try:
            conn.autocommit = False
            job = PublishJob.claim_next(conn)
            conn.commit()
            if not job:
                return None
        except Exception:
            conn.rollback()
            raise
        finally:
            release(conn)

        job_id   = job["id"]
        job_type = job["job_type"]
        acct_id  = job["account_id"]

        account = PlatformAccount.get(acct_id)
        if not account:
            PublishJob.transition(job_id, "failed", error="account not found")
            return {"job_id": job_id, "status": "failed"}

        platform = account["platform"]
        logger.info("Processing job %s type=%s platform=%s", job_id, job_type, platform)

        # ── confirmation gate ─────────────────────────────────────────────────
        auto = self._auto_check(acct_id, job_type)
        if not auto:
            PublishJob.transition(job_id, "awaiting_confirm", actor_id="system")
            self._notify_owner("system", job_id, job_type)
            logger.info("Job %s waiting for owner confirmation", job_id)
            return {"job_id": job_id, "status": "awaiting_confirm"}

        # ── execute ───────────────────────────────────────────────────────────
        try:
            client   = self._factory(platform, account)
            result   = self._dispatch(client, platform, job_type, job)
            new_status = "published" if job_type in (
                "feed_post","social_post","profile_update"
            ) else "sent"
            PublishJob.transition(
                job_id, new_status, actor_id="system",
                result=result,
                external_id=result.get("post_id") or result.get("message_id"),
            )
            AuditLog.write("system", "system", f"job_{new_status}",
                           "publish_job", job_id, result)
            logger.info("Job %s → %s  external_id=%s", job_id, new_status,
                        result.get("post_id") or result.get("message_id"))
            return {"job_id": job_id, "status": new_status, "result": result}

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("Job %s failed: %s\n%s", job_id, exc, tb)
            PublishJob.transition(job_id, "needs_human", actor_id="system",
                                  error=str(exc))
            AuditLog.write("system", "system", "job_needs_human",
                           "publish_job", job_id, {"error": str(exc)})
            return {"job_id": job_id, "status": "needs_human", "error": str(exc)}

    # ── dispatcher ────────────────────────────────────────────────────────────

    def _dispatch(self, client: Any, platform: str, job_type: str,
                  job: Dict) -> Dict:
        payload = job.get("payload") or {}
        idem    = job.get("idempotency_key", str(uuid.uuid4()))

        # ── Fansly ─────────────────────────────────────────────────────────
        if platform == "fansly":
            if job_type == "feed_post":
                # upload each media file first
                media_ids = []
                for fpath in payload.get("media_files", []):
                    r = client.upload_media(fpath, idempotency_key=idem + fpath)
                    if r.get("status") not in ("ok", "processing"):
                        raise RuntimeError(f"Media upload failed: {r}")
                    media_ids.append(r["media_id"])
                return client.create_post(
                    text             = payload.get("text", ""),
                    media_ids        = media_ids,
                    visibility       = payload.get("visibility", 0),
                    tier_ids         = payload.get("tier_ids"),
                    schedule_at      = payload.get("schedule_at"),
                    idempotency_key  = idem,
                )
            if job_type == "ppv_message":
                conv_id = payload.get("conversation_id")
                if not conv_id:
                    username = payload["recipient_username"]
                    conv_id  = client.find_conversation(username)
                    if not conv_id:
                        raise RuntimeError(f"No conversation found for {username!r}")
                media_ids = []
                for fpath in payload.get("media_files", []):
                    r = client.upload_media(fpath, idempotency_key=idem + fpath)
                    if r.get("status") not in ("ok", "processing"):
                        raise RuntimeError(f"Media upload failed: {r}")
                    media_ids.append(r["media_id"])
                return client.send_ppv_message(
                    conversation_id  = conv_id,
                    text             = payload.get("text", ""),
                    media_ids        = media_ids,
                    price_cents      = payload["price_cents"],
                    idempotency_key  = idem,
                )
            if job_type == "profile_update":
                return client.update_profile(
                    bio          = payload.get("bio"),
                    display_name = payload.get("display_name"),
                    banner_url   = payload.get("banner_url"),
                    links        = payload.get("links"),
                )

        # ── Instagram ──────────────────────────────────────────────────────
        if platform == "instagram":
            if job_type in ("feed_post", "social_post"):
                fpath = payload["media_file"]
                if fpath.endswith((".mp4", ".mov")):
                    return client.upload_video(fpath,
                                               caption=payload.get("caption",""))
                return client.upload_photo(fpath,
                                           caption=payload.get("caption",""))
            if job_type == "story":
                return client.upload_story(payload["media_file"])
            if job_type == "ppv_message":
                return client.send_dm_to_user(
                    payload["recipient_username"], payload["text"])

        # ── TikTok ────────────────────────────────────────────────────────
        if platform == "tiktok":
            if job_type in ("feed_post", "social_post"):
                return client.upload_video(
                    payload["media_file"],
                    caption   = payload.get("caption",""),
                    hashtags  = payload.get("hashtags",[]),
                )
            if job_type == "ppv_message":
                return client.send_dm_to_user(
                    payload["recipient_username"], payload["text"])

        # ── X (Twitter) ───────────────────────────────────────────────────
        if platform == "x":
            if job_type in ("feed_post", "social_post"):
                media_id = None
                if payload.get("media_file"):
                    r = client.upload_media(payload["media_file"])
                    media_id = r.get("media_id_string")
                return client.post_tweet(
                    payload.get("caption",""), media_id=media_id)
            if job_type == "ppv_message":
                return client.send_dm(
                    payload["recipient_id"], payload["text"])

        # ── Reddit ────────────────────────────────────────────────────────
        if platform == "reddit":
            if job_type in ("feed_post", "social_post"):
                fpath = payload["media_file"]
                sr    = payload.get("subreddit", "u_me")
                title = payload.get("title", payload.get("caption",""))
                nsfw  = payload.get("nsfw", False)
                if fpath.endswith((".mp4", ".mov")):
                    return client.submit_video_post(sr, title, fpath, nsfw=nsfw)
                return client.submit_image_post(sr, title, fpath, nsfw=nsfw)
            if job_type == "ppv_message":
                return client.send_dm(
                    payload["recipient_username"], payload["subject"],
                    payload["text"])

        raise NotImplementedError(f"No dispatcher for platform={platform}, type={job_type}")
