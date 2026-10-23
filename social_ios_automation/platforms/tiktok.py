"""
TikTok iOS private API client.

Reversed from TikTok v26.1.0 on iPhone.
All signing from scratch — no third-party TikTok libraries.

Entry points:
  login(username, password)
  upload_video(video_path, caption, cover_time_ms)
  send_dm(conversation_id, text)
  get_dm_conversations()
  register(username, password, email)
  search_users(keyword)
"""

import hashlib
import json
import os
import random
import time
import uuid
from typing import Any, Dict, List, Optional

from ..core.device  import DeviceProfile
from ..core.session import PlatformSession
from ..core.crypto  import gorgon_sign, tt_ladon_sign, hmac_sha256_hex
import config


# ── TikTok device registration constants ────────────────────────────────────

_TT_AID         = "1233"          # app_id for TikTok iOS
_TT_APP_NAME    = "trill"         # internal codename for TikTok
_TT_CHANNEL     = "App Store"
_TT_UPDATE_VER  = "2610180"
_TT_SDK_VER     = "26.1.0"


class TikTokClient(PlatformSession):

    _BASE_URL = config.TT_API_URL

    def __init__(
        self,
        device:       Optional[DeviceProfile] = None,
        proxy_url:    Optional[str]            = None,
        session_file: Optional[str]            = None,
    ):
        self._device = device or DeviceProfile.random()

        # persistent device identifiers (generated once per install)
        self._device_id = self._auth_data.get("device_id") if hasattr(self, "_auth_data") else ""
        self._iid       = self._auth_data.get("iid")       if hasattr(self, "_auth_data") else ""

        if not self._device_id:
            self._device_id = str(random.randint(7000000000000000000, 7999999999999999999))
        if not self._iid:
            self._iid = str(random.randint(7000000000000000000, 7999999999999999999))

        super().__init__(self._device, proxy_url, session_file)

        self._session_key: Optional[str] = None
        self._user_id:     Optional[str] = None

        if self._auth_data:
            self._session_key = self._auth_data.get("session_key")
            self._user_id     = self._auth_data.get("user_id")
            self._device_id   = self._auth_data.get("device_id", self._device_id)
            self._iid         = self._auth_data.get("iid", self._iid)

    # ── headers ──────────────────────────────────────────────────────────────

    def _default_headers(self) -> Dict[str, str]:
        d = self._device
        return {
            "User-Agent":      d.tiktok_user_agent(config.TT_APP_VERSION, config.TT_APP_BUILD),
            "Accept":          "application/json",
            "Accept-Language": d.language,
            "Accept-Encoding": "gzip, deflate",
            "sdk-version":     "2",
            "X-SS-TC":         "0",
            "X-SS-DP":         _TT_AID,
            "X-SS-STUB":       "",
        }

    def _base_params(self) -> Dict[str, str]:
        d = self._device
        ts = str(int(time.time()))
        return {
            "device_id":          self._device_id,
            "iid":                self._iid,
            "os_version":         d.ios_ver_str,
            "app_version":        config.TT_APP_VERSION,
            "version_code":       config.TT_APP_BUILD,
            "channel":            _TT_CHANNEL,
            "app_name":           _TT_APP_NAME,
            "aid":                _TT_AID,
            "locale":             d.locale,
            "language":           d.locale[:2],
            "region":             d.locale[-2:],
            "sys_region":         d.locale[-2:],
            "timezone_name":      "America/New_York",
            "timezone_offset":    "-14400",
            "resolution":         f"{d.width}*{d.height}",
            "dpi":                "640",
            "ac":                 "wifi" if d.connection_type == "WIFI" else "4g",
            "os":                 "ios",
            "ts":                 ts,
        }

    def _signed_request(
        self,
        method:  str,
        path:    str,
        params:  Optional[Dict] = None,
        data:    Optional[Dict] = None,
        json_body: Optional[Dict] = None,
    ) -> Any:
        """Execute a signed TikTok API request with X-Gorgon/X-Khronos headers."""
        all_params = self._base_params()
        if params:
            all_params.update(params)

        body_bytes: Optional[bytes] = None
        if data:
            from urllib.parse import urlencode
            body_bytes = urlencode(data).encode()
        elif json_body:
            body_bytes = json.dumps(json_body).encode()

        # Build query string
        from urllib.parse import urlencode
        qs = urlencode(all_params)

        ts = int(time.time())
        gorgon_hdrs = gorgon_sign(qs, body_bytes, self._http.headers.get("Cookie", ""), ts)
        ladon_val   = tt_ladon_sign(self._device_id, self._iid, ts)

        extra_headers = {
            **gorgon_hdrs,
            "X-Ladon":     ladon_val,
        }

        if method.upper() == "GET":
            resp = self.get(path, params=all_params, extra_headers=extra_headers)
        else:
            resp = self.post(
                path,
                data          = data,
                json_body     = json_body,
                params        = all_params,
                extra_headers = extra_headers,
            )

        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text, "status_code": resp.status_code}

    # ── device registration ───────────────────────────────────────────────────

    def register_device(self) -> Dict[str, Any]:
        """
        POST /service/2/device_register/
        Called once on fresh installs to obtain device_id and iid.
        """
        payload = {
            "magic_tag":  "ss_app_log",
            "header": {
                "appkey":         _TT_AID,
                "sdk_version":    _TT_SDK_VER,
                "ios_version":    self._device.ios_ver_str,
                "device_model":   self._device.model_id,
                "package":        "com.zhiliaoapp.musically",
                "channel":        _TT_CHANNEL,
                "display_name":   "TikTok",
                "update_version_code": _TT_UPDATE_VER,
                "region":         self._device.locale[-2:],
                "timezone":       "-4",
                "access":         "WIFI" if self._device.connection_type == "WIFI" else "4G",
                "not_request_sender": 0,
                "openudid":       self._device.advertising_id.replace("-", ""),
                "idfa":           self._device.advertising_id,
            },
        }
        resp = self._signed_request("POST", "/service/2/device_register/", json_body=payload)
        if resp.get("device_id"):
            self._device_id = str(resp["device_id"])
            self._iid       = str(resp.get("install_id", self._iid))
            self._auth_data["device_id"] = self._device_id
            self._auth_data["iid"]       = self._iid
            self.save_session()
        return resp

    # ── login ─────────────────────────────────────────────────────────────────

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        POST /passport/user/login/
        Returns session_key and user_id on success.
        """
        import hashlib
        data = {
            "username":     username,
            "password":     hashlib.md5(password.encode()).hexdigest(),
            "mix_mode":     "1",
            "multi_login":  "1",
        }
        resp = self._signed_request("POST", "/passport/user/login/", data=data)
        if resp.get("data", {}).get("session_key"):
            self._session_key = resp["data"]["session_key"]
            self._user_id     = str(resp["data"].get("user_id", ""))
            self._auth_data.update({
                "session_key": self._session_key,
                "user_id":     self._user_id,
            })
            self._http.cookies.set("sessionid", self._session_key, domain=config.TT_API_DOMAIN)
            self.save_session()
        return resp

    def login_email(self, email: str, password: str) -> Dict[str, Any]:
        import hashlib
        data = {
            "email":        email,
            "password":     hashlib.md5(password.encode()).hexdigest(),
            "mix_mode":     "1",
            "multi_login":  "1",
            "account_sdk_source": "app",
        }
        return self._signed_request("POST", "/passport/email/login/", data=data)

    # ── registration ──────────────────────────────────────────────────────────

    def register(
        self,
        username: str,
        password: str,
        email:    str,
        birthday: str = "1997-03-22",   # YYYY-MM-DD
    ) -> Dict[str, Any]:
        """
        POST /passport/email/register/
        Registers a new TikTok account via email.
        """
        import hashlib
        yr, mo, dy = birthday.split("-")
        data = {
            "email":          email,
            "password":       hashlib.md5(password.encode()).hexdigest(),
            "nickname":       username,
            "birthday":       birthday,
            "birth_year":     yr,
            "birth_month":    mo,
            "birth_day":      dy,
            "multi_login":    "1",
            "account_sdk_source": "app",
        }
        resp = self._signed_request("POST", "/passport/email/register/", data=data)
        if resp.get("data", {}).get("session_key"):
            self._session_key = resp["data"]["session_key"]
            self.save_session()
        return resp

    def send_email_code(self, email: str) -> Dict[str, Any]:
        """Request OTP for email registration."""
        data = {
            "email":  email,
            "type":   "register",
            "account_sdk_source": "app",
        }
        return self._signed_request("POST", "/passport/email/send_code/", data=data)

    def verify_email_code(self, email: str, code: str) -> Dict[str, Any]:
        data = {
            "email": email,
            "code":  code,
        }
        return self._signed_request("POST", "/passport/email/check_code/", data=data)

    # ── video upload ──────────────────────────────────────────────────────────

    def upload_video(
        self,
        video_path:   str,
        caption:      str = "",
        cover_time_ms: int = 0,
        hashtags:     Optional[List[str]] = None,
        privacy:      int = 0,   # 0=public, 1=friends, 2=private
    ) -> Dict[str, Any]:
        """
        Full TikTok iOS video publish pipeline:
          1. POST /api/upload/iphone/get/token/  → upload_id + upload_url
          2. PUT raw video bytes to upload_url
          3. POST /aweme/v1/aweme/post/           → publish
        """
        with open(video_path, "rb") as fh:
            video_bytes = fh.read()
        video_size = len(video_bytes)

        # ── step 1: get upload token ─────────────────────────────────────────
        token_resp = self._signed_request(
            "POST",
            "/api/upload/iphone/get/token/",
            data={"video_size": str(video_size)},
        )
        if "data" not in token_resp:
            return token_resp

        upload_token = token_resp["data"]["video"]["upload_id"]
        upload_url   = token_resp["data"]["video"]["upload_url"]

        # ── step 2: PUT video to CDN ─────────────────────────────────────────
        chunk_size = 10 * 1024 * 1024   # 10 MB chunks
        for offset in range(0, video_size, chunk_size):
            chunk = video_bytes[offset:offset + chunk_size]
            end   = offset + len(chunk) - 1
            cdn_resp = self._http.put(
                upload_url,
                data    = chunk,
                headers = {
                    "Content-Range":  f"bytes {offset}-{end}/{video_size}",
                    "Content-Type":   "video/mp4",
                    "Content-Length": str(len(chunk)),
                    "Upload-Token":   upload_token,
                },
                timeout = (15, 120),
            )

        # ── step 3: publish ──────────────────────────────────────────────────
        tag_text = " ".join(f"#{t}" for t in (hashtags or []))
        full_caption = f"{caption} {tag_text}".strip()

        publish_data = {
            "video_id":           upload_token,
            "desc":               full_caption,
            "cover_tsp":          str(cover_time_ms),
            "video_time_list":    "",
            "music_volume":       "100",
            "original_sound_used": "1",
            "privacy_level":      str(privacy),
            "allow_comment":      "1",
            "allow_duet":         "1",
            "allow_stitch":       "1",
            "from_draft":         "0",
        }
        return self._signed_request("POST", "/aweme/v1/aweme/post/", data=publish_data)

    # ── direct messages ───────────────────────────────────────────────────────

    def get_dm_conversations(self, count: int = 20) -> Dict[str, Any]:
        return self._signed_request(
            "GET",
            "/api/im/query_inbox/",
            params={"count": str(count), "page": "0"},
        )

    def send_dm(self, conversation_id: str, text: str) -> Dict[str, Any]:
        """Send a text message to a TikTok DM conversation."""
        ts = str(int(time.time() * 1000))
        data = {
            "conversation_id":   conversation_id,
            "sender_open_id":    self._user_id or "",
            "content":           json.dumps({"content": text}),
            "type":              "text",
            "from_uid":          self._user_id or "",
            "local_message_id":  str(uuid.uuid4()).replace("-", ""),
            "create_time":       ts,
        }
        return self._signed_request("POST", "/api/im/send_msg/", data=data)

    def send_dm_to_user(self, target_user_id: str, text: str) -> Dict[str, Any]:
        """Open / retrieve a conversation with a user then send a message."""
        # create or get existing 1:1 conversation
        conv_resp = self._signed_request(
            "POST",
            "/api/im/create/conversation/",
            data={"target_user_ids": target_user_id},
        )
        conv_id = conv_resp.get("conversation_id", "")
        if not conv_id:
            return conv_resp
        return self.send_dm(conv_id, text)

    # ── user search ───────────────────────────────────────────────────────────

    def search_users(self, keyword: str, count: int = 20) -> Dict[str, Any]:
        return self._signed_request(
            "GET",
            "/api/search/general/full/",
            params={
                "keyword":      keyword,
                "count":        str(count),
                "offset":       "0",
                "search_source": "uniform_search_bar",
                "type":         "1",   # 1=user, 2=video
            },
        )

    def get_user_info(self, sec_uid: str) -> Dict[str, Any]:
        return self._signed_request(
            "GET",
            "/aweme/v1/user/",
            params={"sec_user_id": sec_uid},
        )

    def follow_user(self, user_id: str) -> Dict[str, Any]:
        return self._signed_request(
            "POST",
            "/aweme/v1/commit/follow/user/",
            data={"user_id": user_id, "type": "1"},
        )
