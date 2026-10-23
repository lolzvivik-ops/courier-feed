"""
Thin HTTP session wrapper that injects the correct iOS headers per platform,
supports proxy rotation, and handles cookie persistence.

Each platform client subclasses PlatformSession and sets:
  _BASE_URL   — root API URL
  _headers()  — platform-specific default headers

Session state (cookies, auth tokens) can be serialized to disk via save/load.
"""

import json
import os
import time
import random
import ssl
import socket
import struct
from http.cookiejar import LWPCookieJar
from typing import Any, Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class _RetryAdapter(HTTPAdapter):
    """Automatic retry with exponential backoff for transient 5xx / network errors."""

    def __init__(self, retries: int = 3, **kw):
        retry = Retry(
            total           = retries,
            backoff_factor  = 0.5,
            status_forcelist= {429, 500, 502, 503, 504},
            allowed_methods = {"GET", "POST"},
            raise_on_status = False,
        )
        super().__init__(max_retries=retry, **kw)


class PlatformSession:
    """
    Base HTTP session for a single platform account.

    Usage:
        s = PlatformSession(device, proxy_url="http://user:pass@host:port")
        resp = s.get("/some/endpoint", params={"k": "v"})
        resp = s.post("/other", data={"field": "val"})
    """

    _BASE_URL: str = ""

    def __init__(
        self,
        device,
        proxy_url: Optional[str]  = None,
        session_file: Optional[str] = None,
        timeout: Tuple[int, int]  = (10, 30),
    ):
        self.device       = device
        self.timeout      = timeout
        self._session_file = session_file

        self._http = requests.Session()
        self._http.mount("https://", _RetryAdapter())
        self._http.mount("http://",  _RetryAdapter())

        # cookie jar backed by a file if requested
        if session_file:
            jar = LWPCookieJar(session_file + ".cookies")
            if os.path.exists(session_file + ".cookies"):
                jar.load(ignore_discard=True, ignore_expires=True)
            self._http.cookies = jar
        else:
            self._http.cookies = requests.cookies.RequestsCookieJar()

        # proxy
        if proxy_url:
            self._http.proxies = {"https": proxy_url, "http": proxy_url}

        self._auth_data: Dict[str, Any] = {}
        if session_file and os.path.exists(session_file):
            self._load_auth(session_file)

        # subclass sets these
        self._http.headers.update(self._default_headers())

    # ── interface for subclasses ──────────────────────────────────────────────

    def _default_headers(self) -> Dict[str, str]:
        """Override in subclass to return platform-specific default headers."""
        return {}

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def get(
        self,
        path: str,
        params: Optional[Dict] = None,
        extra_headers: Optional[Dict] = None,
    ) -> requests.Response:
        url = self._build_url(path)
        return self._http.get(
            url, params=params,
            headers=extra_headers, timeout=self.timeout,
        )

    def post(
        self,
        path: str,
        data:         Optional[Any]  = None,
        json_body:    Optional[Dict] = None,
        files:        Optional[Dict] = None,
        params:       Optional[Dict] = None,
        extra_headers:Optional[Dict] = None,
    ) -> requests.Response:
        url = self._build_url(path)
        return self._http.post(
            url,
            data    = data,
            json    = json_body,
            files   = files,
            params  = params,
            headers = extra_headers,
            timeout = self.timeout,
        )

    def raw_post(
        self,
        url:          str,
        data:         Optional[bytes] = None,
        extra_headers:Optional[Dict]  = None,
    ) -> requests.Response:
        """POST to an absolute URL (e.g., CDN upload endpoints)."""
        return self._http.post(
            url, data=data, headers=extra_headers, timeout=(10, 120),
        )

    # ── cookie helpers ────────────────────────────────────────────────────────

    def set_cookie(self, name: str, value: str, domain: str = "") -> None:
        self._http.cookies.set(name, value, domain=domain)

    def get_cookie(self, name: str) -> Optional[str]:
        return self._http.cookies.get(name)

    def cookies_dict(self) -> Dict[str, str]:
        return dict(self._http.cookies)

    def cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies_dict().items())

    def save_cookies(self) -> None:
        if self._session_file and hasattr(self._http.cookies, "save"):
            self._http.cookies.save(ignore_discard=True, ignore_expires=True)

    # ── auth data serialization ───────────────────────────────────────────────

    def _save_auth(self, path: str) -> None:
        with open(path, "w") as fh:
            json.dump(self._auth_data, fh)

    def _load_auth(self, path: str) -> None:
        with open(path) as fh:
            self._auth_data = json.load(fh)

    def save_session(self) -> None:
        if self._session_file:
            self._save_auth(self._session_file)
            self.save_cookies()

    # ── internal ─────────────────────────────────────────────────────────────

    def _build_url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        base = self._BASE_URL.rstrip("/")
        return f"{base}/{path.lstrip('/')}"

    # ── rate-limit safe delay ─────────────────────────────────────────────────

    @staticmethod
    def jitter_sleep(base_secs: float, variance: float = 0.3) -> None:
        """
        Sleep for base_secs ± variance * base_secs.
        Humanises the request cadence; harder to flag as bot traffic.
        """
        lo = base_secs * (1 - variance)
        hi = base_secs * (1 + variance)
        time.sleep(random.uniform(lo, hi))
