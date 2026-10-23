"""
Instagram iOS private API client.

Endpoints are the same ones Instagram 259.x uses on iPhone.
No third-party exploitation library — raw HTTP via requests
with manually crafted headers and HMAC-SHA256 signed payloads.

Entry points:
  login(username, password)
  upload_photo(image_path, caption)
  upload_video(video_path, thumbnail_path, caption)
  upload_story(media_path)
  send_dm(thread_id, text)
  get_dm_threads()
  register(email, name, username, password, dob)
  fetch_user(username)
"""

import hashlib
import json
import mimetypes
import os
import time
import uuid
import random
from typing import Any, Dict, List, Optional, Tuple

from ..core.device  import DeviceProfile
from ..core.session import PlatformSession
from ..core.crypto  import sign_ig_body, encrypt_ig_password
import config


# *Private* Instagram public key (fetched from /qp/batch_fetch_web_bloks/
# and /api/v1/qe/sync/ — hardcoded here for the key active in 2023/2024)
_IG_PUBKEY_ID  = 181
_IG_PUBKEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgzuIhAQEBBQADggEPADCCAQoCggEBAKIVQnHWlRDmNa4t+Q/C4hPb
LHUVAn+M+Ny1GUzfbWLAI5RZbqAuX3Uc5LOi3f7C0lm3wGW5BrgSRMYiYPnV
D+5PGGmZAlicv8KpEgDDWZ5nLZE2G6H+H1P6x3AGYUmOPuHj0VK4E4U5MjTU
TaRd6CJbFiYVT9HEiDMwh7G9k8OmGKm3YbDg/2FFXT3hDqj1W4/Qg6YDhOu3
4cXKQXF8DM2C4PiYPSiMCFzCGZWXmvQ0TfFKxaUpBKiZ6mjHkBhD5H2PaSmQ
jHTWwF6iVwTlTv/a/ql+S3v8E2OBRXhPrq7UfRkMZ7t1ZF6+OuWJwzUFPjx4
aQIDAQAB
-----END PUBLIC KEY-----"""


class InstagramClient(PlatformSession):

    _BASE_URL = config.IG_API_URL

    def __init__(
        self,
        device:       Optional[DeviceProfile] = None,
        proxy_url:    Optional[str]            = None,
        session_file: Optional[str]            = None,
    ):
        self._device = device or DeviceProfile.random()
        super().__init__(self._device, proxy_url, session_file)

        # populated after login
        self._user_id:    Optional[str] = None
        self._username:   Optional[str] = None
        self._csrf_token: Optional[str] = None

        # restore from saved auth if available
        if self._auth_data:
            self._user_id    = self._auth_data.get("user_id")
            self._username   = self._auth_data.get("username")
            self._csrf_token = self._auth_data.get("csrf_token")

    # ── headers ──────────────────────────────────────────────────────────────

    def _default_headers(self) -> Dict[str, str]:
        d = self._device
        return {
            "User-Agent":                   d.ig_user_agent(config.IG_APP_VERSION, config.IG_VERSION_CODE),
            "X-IG-App-ID":                  config.IG_APP_ID,
            "X-IG-Capabilities":            config.IG_CAPABILITIES,
            "X-IG-Connection-Type":         d.connection_type,
            "X-IG-Connection-Speed":        f"{random.randint(2000,8000)}kbps",
            "X-IG-Bandwidth-Speed-KBPS":    f"{random.uniform(1000,5000):.3f}",
            "X-IG-Bandwidth-TotalBytes-B":  str(random.randint(100000, 900000)),
            "X-IG-Bandwidth-TotalTime-MS":  str(random.randint(30, 200)),
            "X-IG-Device-ID":               d.device_id,
            "X-IG-Android-ID":              d.android_id,  # kept for compat
            "X-MID":                        "",
            "Accept-Language":              d.language,
            "Accept-Encoding":              "gzip, deflate",
            "Content-Type":                 "application/x-www-form-urlencoded; charset=UTF-8",
        }

    def _csrf(self) -> str:
        return self._csrf_token or self.get_cookie("csrftoken") or ""

    # ── login ─────────────────────────────────────────────────────────────────

    def pre_login_flow(self) -> None:
        """Seed CSRF token and device headers before login."""
        resp = self.get("/si/fetch_headers/", params={"challenge_type": "signup", "guid": self._device.uuid})
        tok = resp.cookies.get("csrftoken")
        if tok:
            self._csrf_token = tok

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        POST /accounts/login/
        Signs the payload with HMAC-SHA256 (ig_sig_key scheme).
        Returns the parsed JSON response (contains user_id, session_id, etc.)
        """
        self.pre_login_flow()
        self.jitter_sleep(1.5)

        enc_password = encrypt_ig_password(password, _IG_PUBKEY_ID, _IG_PUBKEY_PEM)

        payload = {
            "jazoest":          _jazoest(self._device.device_id),
            "country_codes":    '[{"country_code":"1","source":["default"]}]',
            "phone_id":         self._device.phone_id,
            "enc_password":     enc_password,
            "username":         username,
            "adid":             self._device.advertising_id,
            "guid":             self._device.uuid,
            "device_id":        self._device.android_id,
            "google_tokens":    "[]",
            "login_attempt_count": "0",
        }

        signed = sign_ig_body(payload, config.IG_SIG_KEY, config.IG_SIG_KEY_VERSION)
        resp   = self.post(
            "/accounts/login/",
            data           = signed,
            extra_headers  = {"X-CSRFToken": self._csrf()},
        )
        data = resp.json()

        if data.get("status") == "ok" and data.get("logged_in_user"):
            user = data["logged_in_user"]
            self._user_id    = str(user["pk"])
            self._username   = username
            self._csrf_token = resp.cookies.get("csrftoken", self._csrf_token)
            self._auth_data  = {
                "user_id":    self._user_id,
                "username":   username,
                "csrf_token": self._csrf_token,
            }
            self._http.headers.update({"X-CSRFToken": self._csrf_token})
            self.save_session()
        return data

    def two_factor_login(self, username: str, code: str, identifier: str) -> Dict[str, Any]:
        """
        POST /accounts/two_factor_login/
        identifier comes from the 'two_factor_identifier' field in the login response.
        """
        payload = {
            "username":              username,
            "verification_code":     code,
            "two_factor_identifier": identifier,
            "trust_this_device":     "1",
            "device_id":             self._device.android_id,
        }
        resp = self.post("/accounts/two_factor_login/", data=sign_ig_body(payload, config.IG_SIG_KEY))
        data = resp.json()
        if data.get("logged_in_user"):
            self._user_id    = str(data["logged_in_user"]["pk"])
            self._csrf_token = resp.cookies.get("csrftoken", self._csrf_token)
            self.save_session()
        return data

    # ── registration ──────────────────────────────────────────────────────────

    def register(
        self,
        email:    str,
        fullname: str,
        username: str,
        password: str,
        birthday: str = "1995-06-15",   # YYYY-MM-DD
    ) -> Dict[str, Any]:
        """
        POST /accounts/create/
        Creates a new Instagram account.
        birthday must be >= 13 years ago.
        """
        self.pre_login_flow()
        self.jitter_sleep(2)

        enc_password = encrypt_ig_password(password, _IG_PUBKEY_ID, _IG_PUBKEY_PEM)

        payload = {
            "is_secondary_account_creation": "false",
            "jazoest":           _jazoest(self._device.device_id),
            "tos_version":       "row",
            "suggestedUsername": "",
            "verification_code": "",
            "sn_result":         "API_ERROR:+null",
            "do_dynamic_onboarding": "0",
            "phone_id":          self._device.phone_id,
            "enc_password":      enc_password,
            "username":          username,
            "first_name":        fullname,
            "adid":              self._device.advertising_id,
            "guid":              self._device.uuid,
            "year":              birthday.split("-")[0],
            "month":             str(int(birthday.split("-")[1])),
            "day":               str(int(birthday.split("-")[2])),
            "device_id":         self._device.android_id,
            "email":             email,
            "_csrftoken":        self._csrf(),
            "one_tap_opt_in":    "true",
        }
        return self.post(
            "/accounts/create/",
            data          = sign_ig_body(payload, config.IG_SIG_KEY),
            extra_headers = {"X-CSRFToken": self._csrf()},
        ).json()

    def check_username(self, username: str) -> Dict[str, Any]:
        payload = {
            "_csrftoken":  self._csrf(),
            "username":    username,
        }
        return self.post("/users/check_username/", data=sign_ig_body(payload, config.IG_SIG_KEY)).json()

    # ── media upload — photo ──────────────────────────────────────────────────

    def upload_photo(
        self,
        image_path:  str,
        caption:     str = "",
        location:    Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Full photo upload pipeline:
          1. POST /media/upload/photo/   → server returns upload_id
          2. POST /media/configure/      → publishes the post
        """
        upload_id = str(int(time.time() * 1000))

        # ── step 1: upload image bytes ──────────────────────────────────────
        with open(image_path, "rb") as fh:
            image_data = fh.read()

        mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        upload_headers = {
            "X_FB_PHOTO_WATERFALL_ID": str(uuid.uuid4()),
            "X-Entity-Type":           mime,
            "Offset":                  "0",
            "X-Instagram-Rupload-Params": json.dumps({
                "upload_id":          upload_id,
                "media_type":         "1",
                "retry_context":      '{"num_step_auto_retry":0,"num_reupload":0,"num_step_manual_retry":0}',
                "xsharing_enabled":   "true",
            }),
            "X-Entity-Name":           f"fb_uploader_{upload_id}",
            "X-Entity-Length":         str(len(image_data)),
            "Content-Type":            "application/octet-stream",
            "Content-Length":          str(len(image_data)),
        }
        up_resp = self.raw_post(
            f"{config.IG_CDN_URL}/{upload_id}",
            data           = image_data,
            extra_headers  = upload_headers,
        )
        up_data = up_resp.json()
        if up_data.get("status") != "ok":
            return up_data

        # ── step 2: configure / publish ─────────────────────────────────────
        configure_payload: Dict[str, Any] = {
            "_csrftoken":   self._csrf(),
            "_uid":         self._user_id,
            "_uuid":        self._device.uuid,
            "caption":      caption,
            "upload_id":    upload_id,
            "source_type":  "4",
            "device":       {
                "manufacturer":    "Apple",
                "model":           self._device.model_id,
                "android_version": 25,
                "android_release": self._device.ios_ver_str,
            },
            "edits": {
                "crop_original_size": [1080.0, 1080.0],
                "crop_center":        [0.0, -0.0],
                "crop_zoom":          1.0,
            },
            "extra": {"source_width": 1080, "source_height": 1080},
        }
        if location:
            configure_payload["location"] = json.dumps(location)

        return self.post(
            "/media/configure/",
            data = sign_ig_body(configure_payload, config.IG_SIG_KEY),
        ).json()

    # ── media upload — video ──────────────────────────────────────────────────

    def upload_video(
        self,
        video_path:     str,
        thumbnail_path: str,
        caption:        str = "",
        duration_ms:    int = 0,
    ) -> Dict[str, Any]:
        """
        Video upload pipeline:
          1. POST /media/upload/video/          → segment upload url
          2. Upload raw video bytes in segments
          3. POST /media/upload/video/           (finish)
          4. POST /media/configure_to_clips/    → publish
        """
        upload_id = str(int(time.time() * 1000))

        with open(video_path, "rb") as fh:
            video_bytes = fh.read()
        with open(thumbnail_path, "rb") as fh:
            thumb_bytes = fh.read()

        video_size = len(video_bytes)
        thumb_size = len(thumb_bytes)

        # ── step 1: init upload ─────────────────────────────────────────────
        rupload_params = json.dumps({
            "upload_id":        upload_id,
            "media_type":       "2",
            "upload_media_height":  "1080",
            "upload_media_width":   "1920",
            "upload_media_duration_ms": str(duration_ms or 0),
            "retry_context":    '{"num_step_auto_retry":0,"num_reupload":0}',
        })
        init_headers = {
            "X-Instagram-Rupload-Params": rupload_params,
            "X-Entity-Type":              "video/mp4",
            "X-Entity-Name":              f"fb_uploader_{upload_id}",
            "X-Entity-Length":            str(video_size),
            "Offset":                     "0",
            "Content-Type":               "application/octet-stream",
            "Content-Length":             str(video_size),
        }
        self.raw_post(
            f"{config.IG_CDN_URL}/{upload_id}",
            data           = video_bytes,
            extra_headers  = init_headers,
        )

        # ── step 2: upload thumbnail ─────────────────────────────────────────
        thumb_upload_id = str(int(time.time() * 1000))
        thumb_headers = {
            "X-Instagram-Rupload-Params": json.dumps({
                "upload_id":       thumb_upload_id,
                "media_type":      "1",
                "retry_context":   '{}',
            }),
            "X-Entity-Type":    "image/jpeg",
            "X-Entity-Name":    f"fb_uploader_{thumb_upload_id}",
            "X-Entity-Length":  str(thumb_size),
            "Offset":           "0",
            "Content-Type":     "application/octet-stream",
            "Content-Length":   str(thumb_size),
        }
        self.raw_post(
            f"{config.IG_CDN_URL}/{thumb_upload_id}",
            data           = thumb_bytes,
            extra_headers  = thumb_headers,
        )

        # ── step 3: configure ────────────────────────────────────────────────
        payload = {
            "_csrftoken":        self._csrf(),
            "_uid":              self._user_id,
            "_uuid":             self._device.uuid,
            "caption":           caption,
            "upload_id":         upload_id,
            "poster_frame_index": "0",
            "length":            "0.00",
            "audio_muted":       "false",
            "filter_type":       "0",
            "source_type":       "4",
            "date_time_digitalized": "",
        }
        return self.post(
            "/media/configure/?video=1",
            data = sign_ig_body(payload, config.IG_SIG_KEY),
        ).json()

    # ── story upload ──────────────────────────────────────────────────────────

    def upload_story(self, media_path: str) -> Dict[str, Any]:
        """Upload an image or video as an Instagram Story."""
        upload_id  = str(int(time.time() * 1000))
        is_video   = media_path.lower().endswith((".mp4", ".mov"))
        with open(media_path, "rb") as fh:
            media_bytes = fh.read()

        mime  = "video/mp4" if is_video else "image/jpeg"
        mtype = "2" if is_video else "1"

        rupload_params = json.dumps({
            "upload_id":  upload_id,
            "media_type": mtype,
            "retry_context": '{}',
        })
        self.raw_post(
            f"{config.IG_CDN_URL}/{upload_id}",
            data = media_bytes,
            extra_headers = {
                "X-Instagram-Rupload-Params": rupload_params,
                "X-Entity-Type":              mime,
                "X-Entity-Name":              f"fb_uploader_{upload_id}",
                "X-Entity-Length":            str(len(media_bytes)),
                "Offset":                     "0",
                "Content-Type":               "application/octet-stream",
                "Content-Length":             str(len(media_bytes)),
            },
        )

        payload = {
            "_csrftoken":  self._csrf(),
            "_uid":        self._user_id,
            "_uuid":       self._device.uuid,
            "upload_id":   upload_id,
            "source_type": "3",
        }
        endpoint = "/media/configure_to_story/?video=1" if is_video else "/media/configure_to_story/"
        return self.post(endpoint, data=sign_ig_body(payload, config.IG_SIG_KEY)).json()

    # ── direct messages ───────────────────────────────────────────────────────

    def get_dm_threads(self, cursor: str = "") -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "visual_message_return_type": "unseen",
            "persistentBadging":          "true",
            "limit":                      "20",
            "thread_message_limit":       "10",
        }
        if cursor:
            params["cursor"] = cursor
        return self.get("/direct_v2/inbox/", params=params).json()

    def send_dm(self, thread_id: str, text: str) -> Dict[str, Any]:
        """Send a text message to an existing thread."""
        payload = {
            "action":      "send_item",
            "item_type":   "text",
            "text":        text,
            "thread_ids":  f'["{thread_id}"]',
            "_csrftoken":  self._csrf(),
            "_uid":        self._user_id,
            "_uuid":       self._device.uuid,
        }
        return self.post(
            f"/direct_v2/threads/{thread_id}/broadcast/text/",
            data = sign_ig_body(payload, config.IG_SIG_KEY),
        ).json()

    def send_dm_to_user(self, recipient_id: str, text: str) -> Dict[str, Any]:
        """Open a new DM thread with a user and send a message."""
        payload = {
            "action":          "send_item",
            "item_type":       "text",
            "text":            text,
            "recipient_users": f'[["{recipient_id}"]]',
            "_csrftoken":      self._csrf(),
            "_uid":            self._user_id,
            "_uuid":           self._device.uuid,
        }
        return self.post(
            "/direct_v2/threads/broadcast/text/",
            data = sign_ig_body(payload, config.IG_SIG_KEY),
        ).json()

    def create_group_thread(self, user_ids: List[str]) -> Dict[str, Any]:
        payload = {
            "recipient_users": json.dumps([[uid] for uid in user_ids]),
            "_csrftoken":      self._csrf(),
            "_uuid":           self._device.uuid,
        }
        return self.post(
            "/direct_v2/create_group_thread/",
            data = sign_ig_body(payload, config.IG_SIG_KEY),
        ).json()

    # ── user lookup ───────────────────────────────────────────────────────────

    def fetch_user(self, username: str) -> Dict[str, Any]:
        return self.get(
            f"/users/{username}/usernameinfo/",
        ).json()

    def search_users(self, query: str) -> Dict[str, Any]:
        return self.get(
            "/users/search/",
            params={"q": query, "count": "30"},
        ).json()

    def get_user_followers(self, user_id: str, max_id: str = "") -> Dict[str, Any]:
        params: Dict[str, Any] = {"count": "200"}
        if max_id:
            params["max_id"] = max_id
        return self.get(f"/friendships/{user_id}/followers/", params=params).json()

    def follow_user(self, user_id: str) -> Dict[str, Any]:
        payload = {
            "_csrftoken": self._csrf(),
            "_uid":       self._user_id,
            "_uuid":      self._device.uuid,
            "user_id":    user_id,
        }
        return self.post(
            f"/friendships/create/{user_id}/",
            data = sign_ig_body(payload, config.IG_SIG_KEY),
        ).json()


# ── helpers ───────────────────────────────────────────────────────────────────

def _jazoest(seed: str) -> str:
    """Produces the jazoest parameter from a UUID-like string."""
    total = sum(ord(c) for c in seed) + 2
    return str(total)
