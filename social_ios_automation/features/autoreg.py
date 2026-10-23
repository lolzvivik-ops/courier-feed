"""
AutoRegistrar — bulk account creation engine.

Generates realistic identities (name, username, email, password, DOB),
optionally sources temp email inboxes for verification,
and calls each platform's registration endpoint in sequence.

Usage:
    reg = AutoRegistrar(
        platforms   = ["ig", "tt", "tw", "rd"],
        proxy_pool  = proxy_pool,
        count       = 10,
        output_file = "accounts.json",
    )
    accounts = reg.run()
"""

import json
import os
import random
import re
import string
import time
import logging
import uuid
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional

import requests

from ..core.device   import DeviceProfile
from ..platforms.instagram import InstagramClient
from ..platforms.tiktok    import TikTokClient
from ..platforms.twitter   import TwitterClient
from ..platforms.reddit    import RedditClient
from ..utils.proxy   import ProxyPool

logger = logging.getLogger(__name__)


# ── identity generation ───────────────────────────────────────────────────────

_FIRST_NAMES = [
    "alex","blake","casey","dana","evan","faith","grey","hart","india","jory",
    "kai","lane","morgan","noel","ocean","paris","quinn","reese","sage","tate",
    "uri","vale","west","xen","yale","zane","amber","brook","cedar","delta",
    "ember","fern","glen","haven","iris","jade","koda","luna","mika","nova",
]
_LAST_NAMES = [
    "brooks","carter","davis","evans","foster","garcia","hayes","irvin","jones",
    "kim","lewis","moore","nelson","owens","pierce","quinn","reed","smith","tran",
    "upton","vance","walsh","xu","yang","zhang","allen","bell","cole","dean",
    "ford","grant","hill","hunt","james","lane","lee","mack","nash","page",
]
_DOMAINS = [
    "gmail.com","yahoo.com","outlook.com","hotmail.com","protonmail.com",
    "icloud.com","mail.com","yandex.com",
]
_DOB_RANGE = (1990, 2000)   # 24-34 years old as of 2024


@dataclass
class AccountSpec:
    first_name: str
    last_name:  str
    username:   str
    email:      str
    password:   str
    birthday:   str           # YYYY-MM-DD
    device:     Optional[Any] = field(default=None, repr=False)

    # filled after registration
    platform_ids: Dict[str, str] = field(default_factory=dict)
    platform_status: Dict[str, str] = field(default_factory=dict)

    def full_name(self) -> str:
        return f"{self.first_name.capitalize()} {self.last_name.capitalize()}"

    def to_dict(self) -> Dict:
        d = asdict(self)
        d.pop("device", None)
        return d


def generate_identity(rng: Optional[random.Random] = None) -> AccountSpec:
    r = rng or random
    first = r.choice(_FIRST_NAMES)
    last  = r.choice(_LAST_NAMES)
    sep   = r.choice(["_", ".", ""])
    suffix = str(r.randint(0, 9999)).zfill(r.randint(0, 4))
    username = f"{first}{sep}{last}{suffix}"

    # email variant with random separator
    email_user  = f"{first}{r.choice(['.','+','_'])}{last}{r.randint(10,99)}"
    email_dom   = r.choice(_DOMAINS)
    email       = f"{email_user}@{email_dom}"

    # strong random password
    chars    = string.ascii_letters + string.digits + "!@#$%"
    password = "".join(r.choice(chars) for _ in range(r.randint(14, 20)))
    password = (
        r.choice(string.ascii_uppercase)
        + r.choice(string.digits)
        + r.choice("!@#$%")
        + password[3:]
    )

    yr  = r.randint(*_DOB_RANGE)
    mo  = r.randint(1, 12)
    dy  = r.randint(1, 28)
    dob = f"{yr}-{mo:02d}-{dy:02d}"

    return AccountSpec(
        first_name = first,
        last_name  = last,
        username   = username,
        email      = email,
        password   = password,
        birthday   = dob,
    )


# ── temp email client (guerrillamail API) ─────────────────────────────────────

class TempMailClient:
    """
    Reads from Guerrilla Mail public API to receive verification codes.
    No API key needed — uses the open JSON API.
    """
    _API = "https://api.guerrillamail.com/ajax.php"

    def __init__(self):
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "Mozilla/5.0"
        self._sid_token: Optional[str] = None
        self._email:     Optional[str] = None

    def get_inbox(self, email_user: str, email_domain: str = "guerrillamail.com") -> Optional[str]:
        """Obtain a guerrillamail address and store session token."""
        resp = self._session.get(
            self._API,
            params={
                "f":       "get_email_address",
                "email_user": email_user,
                "lang":    "en",
                "site":    email_domain,
            },
            timeout=15,
        )
        data = resp.json()
        self._sid_token = data.get("sid_token", "")
        self._email     = data.get("email_addr", "")
        return self._email

    def wait_for_code(
        self,
        pattern:      str   = r"\b(\d{6})\b",
        timeout_secs: int   = 120,
        poll_interval: int  = 8,
    ) -> Optional[str]:
        """
        Poll the inbox until an email matching `pattern` arrives.
        Returns the first capture group match or None on timeout.
        """
        deadline = time.time() + timeout_secs
        seq      = 0
        while time.time() < deadline:
            resp = self._session.get(
                self._API,
                params={
                    "f":       "check_email",
                    "seq":     str(seq),
                    "sid_token": self._sid_token,
                },
                timeout=15,
            )
            data = resp.json()
            for msg in data.get("list", []):
                body = msg.get("mail_body", "") + msg.get("mail_subject", "")
                m    = re.search(pattern, body)
                if m:
                    return m.group(1)
            seq  = data.get("count", seq)
            time.sleep(poll_interval)
        return None


# ── bulk registrar ────────────────────────────────────────────────────────────

class AutoRegistrar:
    """
    Creates `count` accounts on each requested platform.
    Saves credentials to output_file as newline-delimited JSON.
    """

    def __init__(
        self,
        platforms:   List[str]              = None,
        proxy_pool:  Optional["ProxyPool"]  = None,
        count:       int                    = 1,
        output_file: str                    = "accounts.json",
        use_temp_mail: bool                 = True,
        delay_between: float                = 5.0,
    ):
        self._platforms   = platforms or ["ig", "tt", "tw", "rd"]
        self._proxy_pool  = proxy_pool
        self._count       = count
        self._output      = output_file
        self._use_tempmail= use_temp_mail
        self._delay       = delay_between
        self._mail_client = TempMailClient() if use_temp_mail else None

    def run(self) -> List[AccountSpec]:
        created = []
        for i in range(self._count):
            logger.info("Registering account %d / %d …", i + 1, self._count)
            spec = generate_identity()
            spec.device = DeviceProfile.random()
            proxy = self._proxy_pool.next() if self._proxy_pool else None

            for platform in self._platforms:
                try:
                    result = self._register_on(platform, spec, proxy)
                    spec.platform_status[platform] = result.get("status", str(result))
                    if "pk" in result:
                        spec.platform_ids[platform] = str(result["pk"])
                    elif "user_id" in result:
                        spec.platform_ids[platform] = str(result["user_id"])
                    logger.info("  [%s] %s: %s", platform, spec.username, spec.platform_status[platform])
                except Exception as exc:
                    logger.exception("  [%s] registration error: %s", platform, exc)
                    spec.platform_status[platform] = f"error: {exc}"
                time.sleep(self._delay + random.uniform(0, 2))

            self._save(spec)
            created.append(spec)
            time.sleep(self._delay * 2)

        return created

    def _register_on(
        self, platform: str, spec: AccountSpec, proxy: Optional[str]
    ) -> Dict[str, Any]:
        if platform == "ig":
            c = InstagramClient(spec.device, proxy_url=proxy)
            return c.register(
                email    = spec.email,
                fullname = spec.full_name(),
                username = spec.username,
                password = spec.password,
                birthday = spec.birthday,
            )

        elif platform == "tt":
            email = spec.email
            if self._mail_client:
                user_part = spec.email.split("@")[0]
                email = self._mail_client.get_inbox(user_part) or spec.email
            c = TikTokClient(spec.device, proxy_url=proxy)
            c.register_device()
            # send verification code
            c.send_email_code(email)
            code: Optional[str] = None
            if self._mail_client:
                code = self._mail_client.wait_for_code(timeout_secs=90)
            if code:
                c.verify_email_code(email, code)
            return c.register(
                username = spec.username,
                password = spec.password,
                email    = email,
                birthday = spec.birthday,
            )

        elif platform == "tw":
            c = TwitterClient(spec.device, proxy_url=proxy)
            c.fetch_guest_token()
            return c.register(
                name     = spec.full_name(),
                email    = spec.email,
                password = spec.password,
            )

        elif platform == "rd":
            c = RedditClient(spec.device, proxy_url=proxy)
            return c.register(
                username = spec.username,
                password = spec.password,
                email    = spec.email,
            )

        return {"error": f"unknown platform {platform}"}

    def _save(self, spec: AccountSpec) -> None:
        with open(self._output, "a") as fh:
            fh.write(json.dumps(spec.to_dict()) + "\n")
