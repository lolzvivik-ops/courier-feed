"""
X / Twitter iOS private API client.

Uses the reversed consumer key/secret from Twitter for iPhone 9.x,
OAuth 1.0a handshake built from scratch (no tweepy, no requests_oauthlib).

Entry points:
  request_token()
  login(username, password)          ← password auth (legacy flow still active)
  post_tweet(text, media_ids)
  upload_media(file_path)
  send_dm(recipient_id, text)
  get_dm_conversations(count)
  register(name, email, password)
  search_users(query)
"""

import base64
import hashlib
import hmac as _hmac
import json
import mimetypes
import os
import random
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, quote

from ..core.device  import DeviceProfile
from ..core.session import PlatformSession
from ..core.crypto  import generate_oauth1_header
import config


class TwitterClient(PlatformSession):

    _BASE_URL = config.TW_API_URL

    def __init__(
        self,
        device:       Optional[DeviceProfile] = None,
        proxy_url:    Optional[str]            = None,
        session_file: Optional[str]            = None,
    ):
        self._device = device or DeviceProfile.random()
        super().__init__(self._device, proxy_url, session_file)

        # OAuth credentials
        self._access_token:  Optional[str] = None
        self._access_secret: Optional[str] = None
        self._user_id:       Optional[str] = None
        self._username:      Optional[str] = None
        self._guest_token:   Optional[str] = None

        if self._auth_data:
            self._access_token  = self._auth_data.get("access_token")
            self._access_secret = self._auth_data.get("access_secret")
            self._user_id       = self._auth_data.get("user_id")
            self._username      = self._auth_data.get("username")

    # ── headers ──────────────────────────────────────────────────────────────

    def _default_headers(self) -> Dict[str, str]:
        d = self._device
        return {
            "User-Agent":      d.twitter_user_agent(),
            "Accept":          "*/*",
            "Accept-Language": d.language,
            "Accept-Encoding": "gzip, deflate",
            "X-Twitter-Client": "Twitter-iPhone",
            "X-Twitter-Client-Version": "9.0",
            "X-Twitter-Client-Language": d.locale[:2],
            "X-Twitter-Active-User": "yes",
        }

    def _oauth1_header(
        self,
        method: str,
        url:    str,
        extra:  Optional[Dict[str, str]] = None,
    ) -> str:
        return generate_oauth1_header(
            method          = method,
            url             = url,
            consumer_key    = config.TW_CONSUMER_KEY,
            consumer_secret = config.TW_CONSUMER_SECRET,
            access_token    = self._access_token  or "",
            access_secret   = self._access_secret or "",
            extra_params    = extra,
        )

    def _bearer_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {config.TW_BEARER_TOKEN}"}

    # ── guest token (for unauthenticated calls) ───────────────────────────────

    def fetch_guest_token(self) -> str:
        resp = self.post(
            "/1.1/guest/activate.json",
            extra_headers = {**self._bearer_headers(),
                             "Content-Length": "0"},
        )
        self._guest_token = resp.json().get("guest_token", "")
        return self._guest_token

    # ── login — password flow ─────────────────────────────────────────────────

    def _request_token(self) -> Tuple[str, str]:
        """
        POST /oauth/request_token
        Returns (oauth_token, oauth_token_secret).
        """
        url = f"{config.TW_API_URL}/oauth/request_token"
        auth_header = generate_oauth1_header(
            method          = "POST",
            url             = url,
            consumer_key    = config.TW_CONSUMER_KEY,
            consumer_secret = config.TW_CONSUMER_SECRET,
            extra_params    = {"oauth_callback": "oob"},
        )
        resp = self.post(
            "/oauth/request_token",
            extra_headers = {"Authorization": auth_header,
                             "Content-Length": "0"},
        )
        # response is URL-encoded: oauth_token=X&oauth_token_secret=Y&...
        parts = dict(p.split("=", 1) for p in resp.text.strip().split("&") if "=" in p)
        return parts.get("oauth_token", ""), parts.get("oauth_token_secret", "")

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Twitter iOS password-based auth flow (still active for legacy apps).
        Uses the embedded app consumer key/secret and the x-auth grant type.
        POST /oauth/access_token with x_auth_mode=client_auth
        """
        url   = f"{config.TW_API_URL}/oauth/access_token"
        extra = {
            "x_auth_username": username,
            "x_auth_password": password,
            "x_auth_mode":     "client_auth",
        }
        auth_header = generate_oauth1_header(
            method          = "POST",
            url             = url,
            consumer_key    = config.TW_CONSUMER_KEY,
            consumer_secret = config.TW_CONSUMER_SECRET,
            extra_params    = extra,
        )
        resp = self.post(
            "/oauth/access_token",
            data          = urlencode(extra),
            extra_headers = {
                "Authorization":  auth_header,
                "Content-Type":   "application/x-www-form-urlencoded",
            },
        )
        parts = dict(p.split("=", 1) for p in resp.text.strip().split("&") if "=" in p)
        if "oauth_token" in parts:
            self._access_token  = parts["oauth_token"]
            self._access_secret = parts["oauth_token_secret"]
            self._user_id       = parts.get("user_id", "")
            self._username      = parts.get("screen_name", username)
            self._auth_data = {
                "access_token":  self._access_token,
                "access_secret": self._access_secret,
                "user_id":       self._user_id,
                "username":      self._username,
            }
            self.save_session()
            return {"status": "ok", **parts}
        return {"status": "error", "raw": resp.text}

    # ── registration ──────────────────────────────────────────────────────────

    def register(
        self,
        name:     str,
        email:    str,
        password: str,
    ) -> Dict[str, Any]:
        """
        POST /1.1/account/create.json
        Creates a new Twitter account (no phone verification if guest token used).
        """
        if not self._guest_token:
            self.fetch_guest_token()

        url  = f"{config.TW_API_URL}/1.1/account/create.json"
        data = {
            "name":          name,
            "email":         email,
            "password":      password,
            "lang":          self._device.locale[:2],
            "time":          str(int(time.time())),
            "geoEnabled":    "true",
            "app_id":        config.TW_CONSUMER_KEY,
        }
        auth_header = generate_oauth1_header(
            method          = "POST",
            url             = url,
            consumer_key    = config.TW_CONSUMER_KEY,
            consumer_secret = config.TW_CONSUMER_SECRET,
            extra_params    = data,
        )
        resp = self.post(
            "/1.1/account/create.json",
            data          = urlencode(data),
            extra_headers = {
                "Authorization":  auth_header,
                "X-Guest-Token":  self._guest_token or "",
                "Content-Type":   "application/x-www-form-urlencoded",
            },
        )
        return resp.json()

    # ── media upload ──────────────────────────────────────────────────────────

    def upload_media(self, file_path: str) -> Optional[str]:
        """
        Twitter chunked media upload (INIT → APPEND → FINALIZE).
        Returns media_id_string or None on failure.

        POST https://upload.twitter.com/1.1/media/upload.json
        """
        with open(file_path, "rb") as fh:
            media_bytes = fh.read()

        mime      = mimetypes.guess_type(file_path)[0] or "image/jpeg"
        total_sz  = len(media_bytes)
        upload_url = f"{config.TW_UPLOAD_URL}/1.1/media/upload.json"

        # ── INIT ─────────────────────────────────────────────────────────────
        init_data = {
            "command":        "INIT",
            "total_bytes":    str(total_sz),
            "media_type":     mime,
            "media_category": "tweet_video" if mime.startswith("video") else "tweet_image",
        }
        auth_hdr = self._oauth1_header("POST", upload_url, extra=init_data)
        resp = self.raw_post(
            upload_url,
            data          = urlencode(init_data).encode(),
            extra_headers = {
                "Authorization": auth_hdr,
                "Content-Type":  "application/x-www-form-urlencoded",
            },
        )
        media_id = resp.json().get("media_id_string")
        if not media_id:
            return None

        # ── APPEND (5 MB chunks) ──────────────────────────────────────────────
        chunk_sz = 5 * 1024 * 1024
        seg = 0
        for offset in range(0, total_sz, chunk_sz):
            chunk = media_bytes[offset:offset + chunk_sz]
            b64   = base64.b64encode(chunk).decode()
            app_data = {
                "command":          "APPEND",
                "media_id":         media_id,
                "segment_index":    str(seg),
                "media_data":       b64,
            }
            auth_hdr = self._oauth1_header("POST", upload_url, extra={
                "command": "APPEND", "media_id": media_id,
                "segment_index": str(seg),
            })
            self.raw_post(
                upload_url,
                data          = urlencode(app_data).encode(),
                extra_headers = {
                    "Authorization": auth_hdr,
                    "Content-Type":  "application/x-www-form-urlencoded",
                },
            )
            seg += 1

        # ── FINALIZE ──────────────────────────────────────────────────────────
        fin_data = {"command": "FINALIZE", "media_id": media_id}
        auth_hdr = self._oauth1_header("POST", upload_url, extra=fin_data)
        fin_resp = self.raw_post(
            upload_url,
            data          = urlencode(fin_data).encode(),
            extra_headers = {
                "Authorization": auth_hdr,
                "Content-Type":  "application/x-www-form-urlencoded",
            },
        )
        fin_data = fin_resp.json()
        # poll if processing_info present (video/gif)
        pi = fin_data.get("processing_info", {})
        while pi.get("state") in ("pending", "in_progress"):
            time.sleep(pi.get("check_after_secs", 2))
            status_data = {"command": "STATUS", "media_id": media_id}
            auth_hdr = self._oauth1_header("GET", upload_url, extra=status_data)
            st_resp  = self.get(
                upload_url,
                params        = status_data,
                extra_headers = {"Authorization": auth_hdr},
            )
            pi = st_resp.json().get("processing_info", {})

        return media_id if pi.get("state") != "failed" else None

    # ── tweet posting ─────────────────────────────────────────────────────────

    def post_tweet(
        self,
        text:      str,
        media_ids: Optional[List[str]] = None,
        reply_to:  Optional[str]       = None,
    ) -> Dict[str, Any]:
        """
        POST /1.1/statuses/update.json
        """
        url  = f"{config.TW_API_URL}/1.1/statuses/update.json"
        data: Dict[str, str] = {"status": text}
        if media_ids:
            data["media_ids"] = ",".join(media_ids)
        if reply_to:
            data["in_reply_to_status_id"] = reply_to
        auth_hdr = self._oauth1_header("POST", url, extra=data)
        resp = self.post(
            "/1.1/statuses/update.json",
            data          = urlencode(data),
            extra_headers = {
                "Authorization": auth_hdr,
                "Content-Type":  "application/x-www-form-urlencoded",
            },
        )
        return resp.json()

    def post_with_media(self, text: str, file_path: str) -> Dict[str, Any]:
        media_id = self.upload_media(file_path)
        if not media_id:
            return {"error": "media upload failed"}
        return self.post_tweet(text, media_ids=[media_id])

    # ── direct messages ───────────────────────────────────────────────────────

    def get_dm_conversations(self, count: int = 20) -> Dict[str, Any]:
        url = f"{config.TW_API_URL}/1.1/direct_messages/events/list.json"
        auth_hdr = self._oauth1_header("GET", url, extra={"count": str(count)})
        return self.get(
            "/1.1/direct_messages/events/list.json",
            params        = {"count": str(count)},
            extra_headers = {"Authorization": auth_hdr},
        ).json()

    def send_dm(self, recipient_id: str, text: str) -> Dict[str, Any]:
        """
        POST /1.1/direct_messages/events/new.json
        """
        url  = f"{config.TW_API_URL}/1.1/direct_messages/events/new.json"
        body = {
            "event": {
                "type": "message_create",
                "message_create": {
                    "target":        {"recipient_id": recipient_id},
                    "message_data":  {"text": text},
                },
            }
        }
        auth_hdr = self._oauth1_header("POST", url)
        return self.post(
            "/1.1/direct_messages/events/new.json",
            json_body     = body,
            extra_headers = {
                "Authorization": auth_hdr,
                "Content-Type":  "application/json",
            },
        ).json()

    # ── user lookup ───────────────────────────────────────────────────────────

    def search_users(self, query: str, count: int = 20) -> Dict[str, Any]:
        url  = f"{config.TW_API_URL}/1.1/users/search.json"
        params = {"q": query, "count": str(count), "include_entities": "false"}
        auth_hdr = self._oauth1_header("GET", url, extra=params)
        return self.get(
            "/1.1/users/search.json",
            params        = params,
            extra_headers = {"Authorization": auth_hdr},
        ).json()

    def lookup_user(self, username: str) -> Dict[str, Any]:
        url    = f"{config.TW_API_URL}/1.1/users/show.json"
        params = {"screen_name": username}
        auth_hdr = self._oauth1_header("GET", url, extra=params)
        return self.get(
            "/1.1/users/show.json",
            params        = params,
            extra_headers = {"Authorization": auth_hdr},
        ).json()

    def follow_user(self, user_id: str) -> Dict[str, Any]:
        url  = f"{config.TW_API_URL}/1.1/friendships/create.json"
        data = {"user_id": user_id, "follow": "true"}
        auth_hdr = self._oauth1_header("POST", url, extra=data)
        return self.post(
            "/1.1/friendships/create.json",
            data          = urlencode(data),
            extra_headers = {
                "Authorization": auth_hdr,
                "Content-Type":  "application/x-www-form-urlencoded",
            },
        ).json()
