"""
Fansly iOS private API client.

Reversed from Fansly iOS app (api.fansly.com/api/v1/).
Authentication via Bearer token extracted on first manual login.
No CDP/Playwright — pure iOS mobile API calls.

Entry points:
  login(username, password)
  upload_media(file_path)          → media_id
  create_post(text, media_ids, visibility, schedule_at)   [A1]
  send_ppv_message(recipient_id, text, media_ids, price)  [A2]
  get_inbox(page)                  → unread threads       [B4]
  get_dashboard_stats(date_from, date_to)                 [B5]
  get_post_metrics(post_id)                               [B5]
  get_subscribers(page)
  update_profile(bio, links)                              [B2]
  set_subscription_price(price_usd)                       [B2]

Statuses used by publisher engine:
  - Any API error → caller sets job to needs_human
  - Duplicate protection via idempotency_key header
"""

import hashlib
import json
import mimetypes
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..core.device  import DeviceProfile
from ..core.session import PlatformSession


_FANSLY_API   = "https://apiv3.fansly.com/api/v1"
_FANSLY_CDN   = "https://media.fansly.com"
_APP_VERSION  = "1.7.3"
_APP_BUILD    = "173"


class FanslyClient(PlatformSession):

    _BASE_URL = _FANSLY_API

    def __init__(
        self,
        device:       Optional[DeviceProfile] = None,
        proxy_url:    Optional[str]            = None,
        session_file: Optional[str]            = None,
    ):
        self._device = device or DeviceProfile.random()
        super().__init__(self._device, proxy_url, session_file)

        self._token:   Optional[str] = None
        self._user_id: Optional[str] = None

        if self._auth_data:
            self._token   = self._auth_data.get("token")
            self._user_id = self._auth_data.get("user_id")
            if self._token:
                self._http.headers.update({"Authorization": f"Bearer {self._token}"})

    # ── headers ──────────────────────────────────────────────────────────────

    def _default_headers(self) -> Dict[str, str]:
        d = self._device
        return {
            "User-Agent":       f"Fansly/{_APP_VERSION} ({d.model_id}; iOS {d.ios_ver_str})",
            "X-Fansly-Platform": "ios",
            "X-Fansly-Version": _APP_VERSION,
            "Accept":           "application/json",
            "Accept-Language":  d.language,
            "Accept-Encoding":  "gzip, deflate",
            "Content-Type":     "application/json",
        }

    # ── authentication ────────────────────────────────────────────────────────

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        POST /api/v1/account/token
        Returns Bearer token on success.
        Token is long-lived; no refresh needed typically.
        """
        body = {
            "username": username,
            "password": password,
            "type":     0,         # 0 = password, 1 = email
        }
        resp = self.post("/account/token", json_body=body)
        data = resp.json()
        resp_data = data.get("response", {})
        if resp_data.get("token"):
            self._token   = resp_data["token"]
            self._user_id = str(resp_data.get("account", {}).get("id", ""))
            self._http.headers.update({"Authorization": f"Bearer {self._token}"})
            self._auth_data = {"token": self._token, "user_id": self._user_id}
            self.save_session()
        return data

    def set_token(self, token: str, user_id: str = "") -> None:
        """Inject a manually obtained token (e.g., from Charles Proxy capture)."""
        self._token   = token
        self._user_id = user_id
        self._http.headers.update({"Authorization": f"Bearer {token}"})
        self._auth_data = {"token": token, "user_id": user_id}
        self.save_session()

    # ── media upload ──────────────────────────────────────────────────────────

    def upload_media(self, file_path: str, idempotency_key: str = "") -> Dict[str, Any]:
        """
        Full Fansly media upload pipeline:
          1. POST /account/media/upload — get upload URL + media_id
          2. PUT file bytes to CDN upload URL
          3. POST /account/media/confirm — confirm upload

        Returns {'media_id': str, 'status': 'ok'} or error dict.
        """
        idem = idempotency_key or str(uuid.uuid4())
        mime = mimetypes.guess_type(file_path)[0] or "video/mp4"
        with open(file_path, "rb") as fh:
            file_bytes = fh.read()
        file_size = len(file_bytes)
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        filename  = os.path.basename(file_path)

        # ── step 1: request upload slot ────────────────────────────────────
        init_resp = self.post(
            "/account/media/upload",
            json_body = {
                "filename":  filename,
                "mimetype":  mime,
                "size":      file_size,
                "hash":      file_hash,
            },
            extra_headers = {"Idempotency-Key": idem},
        ).json()

        if not init_resp.get("response", {}).get("upload_url"):
            return {"status": "error", "error": "no upload_url", "raw": init_resp}

        upload_url = init_resp["response"]["upload_url"]
        media_id   = init_resp["response"]["id"]

        # ── step 2: PUT to CDN ──────────────────────────────────────────────
        put_resp = self._http.put(
            upload_url,
            data    = file_bytes,
            headers = {
                "Content-Type":   mime,
                "Content-Length": str(file_size),
            },
            timeout = (15, 300),
        )
        if put_resp.status_code not in (200, 201, 204):
            return {"status": "error", "error": f"CDN PUT {put_resp.status_code}", "media_id": media_id}

        # ── step 3: confirm ──────────────────────────────────────────────────
        confirm_resp = self.post(
            "/account/media/confirm",
            json_body = {"id": media_id},
        ).json()

        status = confirm_resp.get("response", {}).get("status", "")
        # poll until processing complete (videos take time)
        deadline = time.time() + 300
        while status not in ("ready", "complete", "completed") and time.time() < deadline:
            time.sleep(5)
            poll = self.get(f"/account/media/{media_id}").json()
            status = poll.get("response", {}).get("status", status)

        return {
            "status":   "ok" if status in ("ready", "complete", "completed") else "processing",
            "media_id": media_id,
            "raw":      confirm_resp,
        }

    def poll_media_status(self, media_id: str) -> str:
        """Returns 'ready', 'processing', or 'error'."""
        resp = self.get(f"/account/media/{media_id}").json()
        s = resp.get("response", {}).get("status", "")
        if s in ("ready", "complete", "completed"):
            return "ready"
        if s in ("failed", "error"):
            return "error"
        return "processing"

    # ── A1: feed post ─────────────────────────────────────────────────────────

    def create_post(
        self,
        text:           str,
        media_ids:      List[str]       = None,
        visibility:     int             = 0,     # 0=all subscribers, 1=specific tier
        tier_ids:       List[str]       = None,
        schedule_at:    Optional[int]   = None,  # Unix timestamp UTC; None=now
        idempotency_key: str            = "",
    ) -> Dict[str, Any]:
        """
        POST /api/v1/post
        visibility 0 = all subscribers, 3 = free preview
        schedule_at uses Fansly's built-in scheduler (no local cron needed).
        """
        idem = idempotency_key or str(uuid.uuid4())
        attachments = [{"contentId": mid, "contentType": 0} for mid in (media_ids or [])]

        body: Dict[str, Any] = {
            "text":        text,
            "attachments": attachments,
            "permission_flags": visibility,
        }
        if tier_ids:
            body["access_flags"] = {"tiers": tier_ids}
        if schedule_at:
            body["scheduling"] = {"publishAt": schedule_at * 1000}   # ms

        resp = self.post(
            "/post",
            json_body     = body,
            extra_headers = {"Idempotency-Key": idem},
        ).json()

        return {
            "status":  "ok" if resp.get("response", {}).get("id") else "error",
            "post_id": resp.get("response", {}).get("id", ""),
            "raw":     resp,
        }

    # ── A2: PPV / paid message ────────────────────────────────────────────────

    def find_conversation(self, recipient_username: str) -> Optional[str]:
        """
        Search conversations for exact username match.
        Returns conversation_id or None.
        TZ §A2: posimvol'no — any mismatch → returns None → caller stops.
        """
        resp = self.get(
            "/message/conversations",
            params={"limit": "100"},
        ).json()
        conversations = resp.get("response", {}).get("data", [])
        for conv in conversations:
            for participant in conv.get("participants", []):
                acc = participant.get("account", {})
                if acc.get("username", "").lower() == recipient_username.lower():
                    return conv.get("id")
        return None

    def send_ppv_message(
        self,
        conversation_id:  str,
        text:             str,
        media_ids:        List[str],
        price_cents:      int,            # price in USD cents
        idempotency_key:  str = "",
    ) -> Dict[str, Any]:
        """
        POST /api/v1/message
        PPV = Pay-Per-View locked message.
        price_cents: e.g. 2500 = $25.00

        TZ §A2 verification: caller must confirm conversation_id matched
        exactly one recipient before calling this.
        """
        idem = idempotency_key or str(uuid.uuid4())
        attachments = [{"contentId": mid, "contentType": 0} for mid in media_ids]

        body = {
            "conversationId": conversation_id,
            "text":           text,
            "attachments":    attachments,
            "price":          price_cents,   # in cents
        }
        resp = self.post(
            "/message",
            json_body     = body,
            extra_headers = {"Idempotency-Key": idem},
        ).json()

        msg = resp.get("response", {})
        ok  = bool(msg.get("id")) and msg.get("price", 0) > 0

        return {
            "status":     "ok" if ok else "error",
            "message_id": msg.get("id", ""),
            "price":      msg.get("price", 0),
            "raw":        resp,
        }

    def get_message_purchase_status(self, message_id: str) -> str:
        """Returns 'purchased', 'not_purchased', or 'unknown'."""
        resp = self.get(f"/message/{message_id}").json()
        msg  = resp.get("response", {})
        if msg.get("purchased"):
            return "purchased"
        created_ms = msg.get("createdAt", 0)
        age_days   = (time.time() * 1000 - created_ms) / 86_400_000
        if age_days >= 7:
            return "not_purchased"
        return "pending"

    # ── broadcast message (TZ §A2: only via built-in, always Confirmation) ────

    def get_broadcast_message_status(self, broadcast_id: str) -> Dict[str, Any]:
        """Read status of a platform-native mass message (read-only)."""
        return self.get(f"/message/broadcast/{broadcast_id}").json()

    # ── B1: account health ────────────────────────────────────────────────────

    def verify_session(self) -> bool:
        """
        GET /api/v1/account — confirms token is still valid.
        Returns True if logged in, False if token expired.
        """
        resp = self.get("/account").json()
        return bool(resp.get("response", {}).get("id"))

    # ── B2: profile update ────────────────────────────────────────────────────

    def get_profile_snapshot(self) -> Dict[str, Any]:
        """Save current profile values before any modification (for rollback)."""
        return self.get("/account").json()

    def update_profile(
        self,
        bio:            Optional[str] = None,
        display_name:   Optional[str] = None,
        banner_url:     Optional[str] = None,
        links:          Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {}
        if bio           is not None: body["bio"]         = bio
        if display_name  is not None: body["displayName"] = display_name
        if banner_url    is not None: body["bannerUrl"]   = banner_url
        if links         is not None: body["links"]       = links
        return self.post("/account", json_body=body).json()

    def set_subscription_price(
        self,
        price_cents: int,
        tier_id:     Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"price": price_cents}
        if tier_id:
            body["tierId"] = tier_id
        return self.post("/account/subscription/price", json_body=body).json()

    # ── B4: inbox queue ───────────────────────────────────────────────────────

    def get_inbox(self, page: int = 1, limit: int = 50) -> Dict[str, Any]:
        """
        GET /api/v1/message/conversations
        Returns list of conversations sorted by last message time.
        """
        return self.get(
            "/message/conversations",
            params={"page": str(page), "limit": str(limit)},
        ).json()

    def get_unread_conversations(self) -> List[Dict[str, Any]]:
        """Filter conversations with unread messages — used by B4 queue builder."""
        resp  = self.get_inbox()
        convs = resp.get("response", {}).get("data", [])
        return [c for c in convs if c.get("unreadCount", 0) > 0]

    # ── B5: statistics ────────────────────────────────────────────────────────

    def get_dashboard_stats(
        self,
        date_from: int,  # Unix timestamp
        date_to:   int,
    ) -> Dict[str, Any]:
        """
        GET /api/v1/account/dashboard
        Returns daily income breakdown: subscriptions, PPV, tips.
        """
        return self.get(
            "/account/dashboard",
            params={
                "dateFrom": str(date_from * 1000),
                "dateTo":   str(date_to   * 1000),
            },
        ).json()

    def get_subscriber_stats(self) -> Dict[str, Any]:
        """New/churned/renewed subscribers for the current period."""
        return self.get("/account/subscribers/stats").json()

    def get_post_metrics(self, post_id: str) -> Dict[str, Any]:
        return self.get(f"/post/{post_id}/metrics").json()

    def get_posts(self, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        return self.get(
            "/post",
            params={"page": str(page), "limit": str(limit), "type": "0"},
        ).json()

    # ── C2: balance proof screenshot trigger ──────────────────────────────────

    def get_earnings_summary(
        self,
        date_from: int,
        date_to:   int,
    ) -> Dict[str, Any]:
        """
        Structured earnings for the proof period — feeds into C2 proof generator.
        Caller (proof.py) will render this into a screenshot with nicks redacted.
        """
        dash = self.get_dashboard_stats(date_from, date_to).get("response", {})
        return {
            "period_from":     date_from,
            "period_to":       date_to,
            "total_cents":     dash.get("earnings", {}).get("total", 0),
            "subscriptions":   dash.get("earnings", {}).get("subscriptions", 0),
            "ppv":             dash.get("earnings", {}).get("ppv", 0),
            "tips":            dash.get("earnings", {}).get("tips", 0),
            "chargebacks":     dash.get("earnings", {}).get("chargebacks", 0),
            "platform_fee":    dash.get("earnings", {}).get("platformFee", 0),
        }

    # ── C1: daily income read ─────────────────────────────────────────────────

    def get_daily_income(self, date_unix: int) -> int:
        """Return total earnings in cents for a single day."""
        day_start = date_unix - (date_unix % 86400)
        day_end   = day_start + 86399
        summary   = self.get_earnings_summary(day_start, day_end)
        return summary.get("total_cents", 0)
