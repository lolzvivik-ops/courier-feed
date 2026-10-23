"""
D1 — APNs HTTP/2 push notification sender.

Uses APNs HTTP/2 API with ES256 JWT (.p8 key).
No third-party APNs library — raw HTTP/2 via httpx.

Entry points:
  APNsClient(team_id, key_id, key_path, bundle_id)
  .send(token, title, body, data, environment)  → APNsResult
  .send_batch(tokens, ...)                       → list[APNsResult]

JWT is cached for up to 50 minutes (APNs tokens expire at 60m).
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_APNS_PROD    = "https://api.push.apple.com"
_APNS_SANDBOX = "https://api.sandbox.push.apple.com"


@dataclass
class APNsResult:
    token:       str
    success:     bool
    apns_id:     Optional[str]
    status_code: int
    error:       Optional[str]


class APNsClient:

    def __init__(
        self,
        team_id:    str,
        key_id:     str,
        key_path:   str,       # path to AuthKey_XXXXXXXXXX.p8
        bundle_id:  str,
        topic:      Optional[str] = None,
    ):
        self._team_id   = team_id
        self._key_id    = key_id
        self._bundle_id = bundle_id
        self._topic     = topic or bundle_id

        with open(key_path, "r") as fh:
            self._private_key_pem = fh.read()

        self._jwt:       Optional[str] = None
        self._jwt_time:  float         = 0.0
        self._jwt_ttl:   float         = 50 * 60   # 50 minutes

        # persistent HTTP/2 client
        self._http = httpx.Client(http2=True, timeout=10.0)

    # ── JWT ───────────────────────────────────────────────────────────────────

    def _get_jwt(self) -> str:
        now = time.time()
        if self._jwt and (now - self._jwt_time) < self._jwt_ttl:
            return self._jwt
        self._jwt      = self._build_jwt()
        self._jwt_time = now
        return self._jwt

    def _build_jwt(self) -> str:
        """Build ES256-signed JWT for APNs provider authentication."""
        import base64
        import hashlib
        import hmac as _hmac
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.backends import default_backend

        iat   = int(time.time())
        header = {"alg": "ES256", "kid": self._key_id}
        claims = {"iss": self._team_id, "iat": iat}

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        header_b64  = b64url(json.dumps(header, separators=(",",":")).encode())
        payload_b64 = b64url(json.dumps(claims, separators=(",",":")).encode())
        msg         = f"{header_b64}.{payload_b64}".encode()

        key = serialization.load_pem_private_key(
            self._private_key_pem.encode(), password=None,
            backend=default_backend(),
        )
        signature = key.sign(msg, ec.ECDSA(hashes.SHA256()))

        # DER → raw R||S
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
        r, s = decode_dss_signature(signature)
        raw_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")

        return f"{header_b64}.{payload_b64}.{b64url(raw_sig)}"

    # ── send ──────────────────────────────────────────────────────────────────

    def send(
        self,
        token:       str,
        title:       str,
        body:        str,
        data:        Optional[Dict[str, Any]] = None,
        environment: str = "production",   # production | sandbox
        thread_id:   Optional[str] = None,
        collapse_id: Optional[str] = None,
        badge:       Optional[int] = None,
        sound:       str = "default",
    ) -> APNsResult:
        base_url  = _APNS_PROD if environment == "production" else _APNS_SANDBOX
        apns_id   = str(uuid.uuid4())

        aps: Dict[str, Any] = {
            "alert": {"title": title, "body": body},
            "sound": sound,
        }
        if badge is not None:
            aps["badge"] = badge

        payload: Dict[str, Any] = {"aps": aps}
        if data:
            payload.update(data)

        headers = {
            "authorization":  f"bearer {self._get_jwt()}",
            "apns-id":        apns_id,
            "apns-topic":     self._topic,
            "content-type":   "application/json",
        }
        if thread_id:
            headers["apns-thread-id"] = thread_id
        if collapse_id:
            headers["apns-collapse-id"] = collapse_id

        url = f"{base_url}/3/device/{token}"
        try:
            resp = self._http.post(url, content=json.dumps(payload).encode(),
                                   headers=headers)
            ok = resp.status_code == 200
            err = None
            if not ok:
                try:
                    err = resp.json().get("reason", resp.text[:200])
                except Exception:
                    err = resp.text[:200]
            return APNsResult(
                token=token, success=ok,
                apns_id=resp.headers.get("apns-id", apns_id),
                status_code=resp.status_code, error=err,
            )
        except Exception as exc:
            logger.error("APNs send failed for token %s…: %s", token[:8], exc)
            return APNsResult(token=token, success=False, apns_id=None,
                              status_code=0, error=str(exc))

    def send_batch(
        self,
        tokens:      List[str],
        title:       str,
        body:        str,
        data:        Optional[Dict] = None,
        environment: str = "production",
        thread_id:   Optional[str] = None,
        badge:       Optional[int] = None,
    ) -> List[APNsResult]:
        return [
            self.send(t, title, body, data, environment, thread_id, badge=badge)
            for t in tokens
        ]
