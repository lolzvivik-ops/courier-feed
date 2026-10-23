"""
Reddit iOS private API client.

Uses Reddit's OAuth2 password grant with the reversed iOS app client_id.
No PRAW, no reddit wrappers — raw OAuth2 + REST calls.

Entry points:
  login(username, password)
  submit_post(subreddit, title, text, url)
  submit_image_post(subreddit, title, image_path)
  submit_video_post(subreddit, title, video_path, thumb_path)
  send_dm(username, subject, text)
  get_dm_inbox(count)
  register(username, password, email)
  search_users(query)
"""

import base64
import hashlib
import json
import mimetypes
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from ..core.device  import DeviceProfile
from ..core.session import PlatformSession
from ..core.crypto  import reddit_basic_auth
import config


class RedditClient(PlatformSession):

    _BASE_URL = config.RD_API_URL

    def __init__(
        self,
        device:       Optional[DeviceProfile] = None,
        proxy_url:    Optional[str]            = None,
        session_file: Optional[str]            = None,
    ):
        self._device = device or DeviceProfile.random()
        super().__init__(self._device, proxy_url, session_file)

        self._access_token:  Optional[str] = None
        self._token_expiry:  float         = 0.0
        self._username:      Optional[str] = None

        if self._auth_data:
            self._access_token = self._auth_data.get("access_token")
            self._token_expiry = self._auth_data.get("token_expiry", 0.0)
            self._username     = self._auth_data.get("username")
            if self._access_token:
                self._http.headers.update(
                    {"Authorization": f"bearer {self._access_token}"}
                )

    # ── headers ──────────────────────────────────────────────────────────────

    def _default_headers(self) -> Dict[str, str]:
        d = self._device
        return {
            "User-Agent":      d.reddit_user_agent(config.RD_APP_VERSION),
            "Accept":          "application/json",
            "Accept-Language": d.language,
            "Accept-Encoding": "gzip, deflate",
            "x-reddit-loid":   _random_loid(),
            "x-reddit-api-key": config.RD_CLIENT_ID,
        }

    def _ensure_token(self) -> bool:
        if self._access_token and time.time() < self._token_expiry - 60:
            return True
        return False  # caller must re-login or refresh

    # ── authentication ────────────────────────────────────────────────────────

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        POST /api/v1/access_token  (password grant)
        Uses Reddit iOS app client_id (no secret needed for installed apps).
        """
        url  = f"{config.RD_AUTH_URL}/access_token"
        data = {
            "grant_type":     "password",
            "username":       username,
            "password":       password,
            "two_factor_code": "",
        }
        resp = self._http.post(
            url,
            data    = data,
            headers = {
                "Authorization":  reddit_basic_auth(config.RD_CLIENT_ID),
                "User-Agent":     self._device.reddit_user_agent(config.RD_APP_VERSION),
                "Content-Type":   "application/x-www-form-urlencoded",
            },
            timeout = (10, 30),
        )
        result = resp.json()
        if "access_token" in result:
            self._access_token = result["access_token"]
            self._token_expiry = time.time() + result.get("expires_in", 3600)
            self._username     = username
            self._http.headers.update({"Authorization": f"bearer {self._access_token}"})
            self._auth_data = {
                "access_token":  self._access_token,
                "token_expiry":  self._token_expiry,
                "username":      username,
            }
            self.save_session()
        return result

    def refresh_token(self, refresh_tok: str) -> Dict[str, Any]:
        url  = f"{config.RD_AUTH_URL}/access_token"
        data = {
            "grant_type":    "refresh_token",
            "refresh_token": refresh_tok,
        }
        resp = self._http.post(
            url,
            data    = data,
            headers = {
                "Authorization": reddit_basic_auth(config.RD_CLIENT_ID),
                "User-Agent":    self._device.reddit_user_agent(config.RD_APP_VERSION),
                "Content-Type":  "application/x-www-form-urlencoded",
            },
            timeout = (10, 30),
        )
        result = resp.json()
        if "access_token" in result:
            self._access_token = result["access_token"]
            self._token_expiry = time.time() + result.get("expires_in", 3600)
            self._http.headers.update({"Authorization": f"bearer {self._access_token}"})
        return result

    # ── registration ──────────────────────────────────────────────────────────

    def register(
        self,
        username: str,
        password: str,
        email:    str = "",
    ) -> Dict[str, Any]:
        """
        POST /api/register
        Creates a new Reddit account.
        """
        # first fetch CSRF token from login page
        reg_url = f"{config.RD_AUTH_URL}/register"
        resp_html = self._http.get(
            "https://www.reddit.com/register",
            headers={"User-Agent": self._device.reddit_user_agent(config.RD_APP_VERSION)},
            timeout=(10, 30),
        )
        # extract modhash from meta tag if present
        modhash = _extract_modhash(resp_html.text)

        data: Dict[str, Any] = {
            "user":              username,
            "passwd":            password,
            "passwd2":           password,
            "email":             email,
            "rem":               "True",
            "op":                "reg",
            "dest":              "https://www.reddit.com",
            "json":              "1",
        }
        if modhash:
            data["uh"] = modhash

        resp = self._http.post(
            "https://www.reddit.com/api/register",
            data    = data,
            headers = {
                "User-Agent":    self._device.reddit_user_agent(config.RD_APP_VERSION),
                "Content-Type":  "application/x-www-form-urlencoded",
                "Referer":       "https://www.reddit.com/register",
            },
            timeout = (10, 30),
        )
        return resp.json()

    # ── posting ───────────────────────────────────────────────────────────────

    def submit_post(
        self,
        subreddit: str,
        title:     str,
        text:      str   = "",
        url:       str   = "",
        nsfw:      bool  = False,
        flair_id:  str   = "",
    ) -> Dict[str, Any]:
        """
        POST /api/submit
        Submits a self (text) or link post.
        """
        kind = "link" if url else "self"
        data: Dict[str, Any] = {
            "sr":         subreddit,
            "kind":       kind,
            "title":      title,
            "text":       text,
            "url":        url,
            "nsfw":       "true" if nsfw else "false",
            "spoiler":    "false",
            "sendreplies": "true",
            "api_type":   "json",
        }
        if flair_id:
            data["flair_id"] = flair_id
        return self.post("/api/submit", data=data).json()

    def submit_image_post(
        self,
        subreddit:  str,
        title:      str,
        image_path: str,
    ) -> Dict[str, Any]:
        """
        Upload image to Reddit CDN then submit as an image post.
        Follows Reddit's two-step image upload flow.
        """
        # step 1: get upload lease
        with open(image_path, "rb") as fh:
            img_bytes = fh.read()
        mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        ext  = os.path.splitext(image_path)[1].lstrip(".") or "jpg"

        lease_resp = self.post(
            "/api/v1/s3_upload_lease",
            data={
                "filepath":    os.path.basename(image_path),
                "mimetype":    mime,
            },
        ).json()

        if "args" not in lease_resp.get("s3UploadLease", {}):
            return lease_resp

        lease    = lease_resp["s3UploadLease"]
        upload_url = "https:" + lease["action"]
        fields   = {f["name"]: f["value"] for f in lease["args"]["fields"]}
        fields["file"] = img_bytes

        # step 2: multipart POST to S3
        self._http.post(upload_url, files=fields, timeout=(10, 120))

        ws_url = f"https://i.redd.it/{lease['asset']['asset_id']}.{ext}"

        # step 3: submit post with the CDN URL
        return self.submit_post(subreddit=subreddit, title=title, url=ws_url)

    # ── video post ────────────────────────────────────────────────────────────

    def submit_video_post(
        self,
        subreddit:   str,
        title:       str,
        video_path:  str,
        thumb_path:  str,
    ) -> Dict[str, Any]:
        """
        Reddit's native video upload via /api/media/asset.json +
        /api/submit with kind=video / videogif.
        """
        with open(video_path, "rb") as fh:
            vid_bytes = fh.read()
        with open(thumb_path, "rb") as fh:
            thumb_bytes = fh.read()

        # get upload lease for video
        lease_resp = self.post(
            "/api/media/asset.json",
            data={
                "filepath": os.path.basename(video_path),
                "mimetype": "video/mp4",
            },
        ).json()

        upload_lease = lease_resp.get("args", {})
        if not upload_lease.get("action"):
            return lease_resp

        upload_url = "https:" + upload_lease["action"]
        fields     = {f["name"]: f["value"] for f in upload_lease.get("fields", [])}
        fields["file"] = vid_bytes
        self._http.post(upload_url, files=fields, timeout=(10, 300))

        asset_id = lease_resp.get("asset", {}).get("asset_id", "")
        video_url = f"https://v.redd.it/{asset_id}"

        return self.submit_post(subreddit=subreddit, title=title, url=video_url)

    # ── direct messages ───────────────────────────────────────────────────────

    def get_dm_inbox(self, count: int = 25, mark_read: bool = False) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "limit": str(count),
            "mark":  "true" if mark_read else "false",
        }
        return self.get("/message/inbox", params=params).json()

    def send_dm(
        self,
        to_username: str,
        subject:     str,
        text:        str,
    ) -> Dict[str, Any]:
        """
        POST /api/compose
        Sends a private message to another Reddit user.
        """
        data = {
            "to":        to_username,
            "subject":   subject,
            "text":      text,
            "api_type":  "json",
        }
        return self.post("/api/compose", data=data).json()

    def reply_to_dm(self, thing_id: str, text: str) -> Dict[str, Any]:
        data = {
            "thing_id": thing_id,
            "text":     text,
            "api_type": "json",
        }
        return self.post("/api/comment", data=data).json()

    # ── user lookup ───────────────────────────────────────────────────────────

    def search_users(self, query: str, count: int = 25) -> Dict[str, Any]:
        return self.get(
            "/users/search",
            params={"q": query, "limit": str(count), "sort": "relevance"},
        ).json()

    def get_user_info(self, username: str) -> Dict[str, Any]:
        return self.get(f"/user/{username}/about").json()

    def get_user_posts(self, username: str, count: int = 25) -> Dict[str, Any]:
        return self.get(
            f"/user/{username}/submitted",
            params={"limit": str(count), "sort": "new"},
        ).json()

    def subscribe_subreddit(self, subreddit: str, action: str = "sub") -> Dict[str, Any]:
        sr_resp = self.get(f"/r/{subreddit}/about").json()
        sr_id   = sr_resp.get("data", {}).get("name", "")
        return self.post(
            "/api/subscribe",
            data={"action": action, "sr": sr_id, "api_type": "json"},
        ).json()


# ── helpers ───────────────────────────────────────────────────────────────────

def _random_loid() -> str:
    """Generate a Reddit LOID (logged-out ID) in the correct format."""
    return base64.b64encode(os.urandom(18)).decode().rstrip("=")


def _extract_modhash(html: str) -> str:
    import re
    m = re.search(r'"modhash":\s*"([a-f0-9]+)"', html)
    return m.group(1) if m else ""
