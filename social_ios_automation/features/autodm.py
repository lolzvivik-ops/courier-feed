"""
AutoDM — bulk direct-message engine.

Reads a target list and a message template file, then dispatches DMs
across all configured platform clients with per-platform rate limiting
and jittered human-like delays.

Target file format (targets.txt):
    ig:  <username>                 — Instagram username
    ig:  <user_id>                  — numeric user ID
    tt:  <user_id>                  — TikTok user_id
    tw:  <user_id>                  — Twitter numeric user_id
    rd:  <username>                 — Reddit username

Message template file (messages.txt):
    Line 1 — Subject line (used for Reddit)
    ----
    Hello {name}, this is an automated message about {topic}.
    ----
    Hello {first}! Check this out: {url}

    Multiple templates separated by ---- → chosen at random per send.

Usage:
    from platforms import InstagramClient, TikTokClient, TwitterClient, RedditClient
    dm = AutoDM(
        clients        = clients,
        target_file    = "targets.txt",
        message_file   = "messages.txt",
        delay_seconds  = 8,
        max_per_session= 100,
    )
    dm.run()
"""

import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── data classes ──────────────────────────────────────────────────────────────

@dataclass
class DMTarget:
    platform: str   # "ig", "tt", "tw", "rd"
    identifier: str # username or numeric ID


@dataclass
class MessageTemplate:
    subject: str
    body:    str

    def render(self, **kwargs) -> Tuple[str, str]:
        """Fill {placeholder} vars in subject and body."""
        subj = self.subject
        body = self.body
        for k, v in kwargs.items():
            subj = subj.replace(f"{{{k}}}", str(v))
            body = body.replace(f"{{{k}}}", str(v))
        return subj, body


# ── file parsers ──────────────────────────────────────────────────────────────

def load_targets(path: str) -> List[DMTarget]:
    """
    Parse targets file.
    Each line: <platform>: <identifier>
    Blank lines and # comments ignored.
    """
    targets: List[DMTarget] = []
    if not os.path.exists(path):
        logger.warning("Target file not found: %s", path)
        return targets
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                plat, ident = line.split(":", 1)
                targets.append(DMTarget(platform=plat.strip().lower(),
                                        identifier=ident.strip()))
    return targets


def load_templates(path: str) -> List[MessageTemplate]:
    """
    Parse message templates file.
    Templates separated by a line containing only '----'.
    First line of each block is the subject; rest is body.
    """
    templates: List[MessageTemplate] = []
    if not os.path.exists(path):
        logger.warning("Message file not found: %s", path)
        return [MessageTemplate(subject="Hello", body="Hello from AutoDM")]
    with open(path) as fh:
        raw = fh.read()
    blocks = re.split(r"\n----\n", raw.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue
        subject = lines[0].strip()
        body    = "\n".join(lines[1:]).strip() if len(lines) > 1 else subject
        templates.append(MessageTemplate(subject=subject, body=body))
    return templates


# ── AutoDM engine ─────────────────────────────────────────────────────────────

class AutoDM:
    """
    Dispatches DMs to a list of targets across platforms.
    Tracks sent targets in a log file to avoid double-sends.
    """

    def __init__(
        self,
        clients:         Dict[str, Any],
        target_file:     str   = "targets.txt",
        message_file:    str   = "messages.txt",
        delay_seconds:   float = 8.0,
        delay_variance:  float = 0.4,
        max_per_session: int   = 200,
        sent_log:        str   = ".sent_dms.json",
        template_vars:   Optional[Dict[str, str]] = None,
    ):
        self._clients       = clients
        self._delay         = delay_seconds
        self._variance      = delay_variance
        self._max           = max_per_session
        self._sent_log_path = sent_log
        self._template_vars = template_vars or {}

        self._targets   = load_targets(target_file)
        self._templates = load_templates(message_file)
        self._sent:     set = set()
        self._load_sent_log()

    # ── public ────────────────────────────────────────────────────────────────

    def run(self) -> Dict[str, Any]:
        """Send DMs to all pending targets, respecting max_per_session."""
        stats = {"sent": 0, "failed": 0, "skipped": 0}
        pending = [t for t in self._targets if self._target_key(t) not in self._sent]
        logger.info("AutoDM: %d pending targets", len(pending))

        for target in pending[:self._max]:
            key = self._target_key(target)
            tmpl = random.choice(self._templates)
            subj, body = tmpl.render(**self._template_vars)

            result = self._dispatch(target, subj, body)
            if result.get("ok"):
                stats["sent"] += 1
                self._mark_sent(key)
            else:
                stats["failed"] += 1
                logger.warning("DM failed → %s: %s", key, result.get("error"))

            self._sleep()

        logger.info("AutoDM done — sent=%d failed=%d skipped=%d",
                    stats["sent"], stats["failed"], stats["skipped"])
        return stats

    def send_one(
        self,
        platform:   str,
        identifier: str,
        message:    str,
        subject:    str = "",
    ) -> Dict[str, Any]:
        """Send a single DM without using the target file."""
        target = DMTarget(platform=platform, identifier=identifier)
        return self._dispatch(target, subject or "Hi", message)

    def broadcast(
        self,
        platform:  str,
        user_ids:  List[str],
        message:   str,
        subject:   str = "",
        delay:     float = 5.0,
    ) -> Dict[str, Any]:
        """Send the same message to a list of user IDs on one platform."""
        stats = {"sent": 0, "failed": 0}
        for uid in user_ids:
            result = self.send_one(platform, uid, message, subject)
            if result.get("ok"):
                stats["sent"] += 1
            else:
                stats["failed"] += 1
                logger.warning("[%s] DM to %s failed: %s", platform, uid, result.get("error"))
            _jitter_sleep(delay)
        return stats

    # ── platform dispatch ─────────────────────────────────────────────────────

    def _dispatch(self, target: DMTarget, subject: str, body: str) -> Dict[str, Any]:
        client = self._clients.get(target.platform)
        if not client:
            return {"ok": False, "error": f"no client for {target.platform}"}

        try:
            if target.platform == "ig":
                resp = self._ig_dm(client, target.identifier, body)
            elif target.platform == "tt":
                resp = self._tt_dm(client, target.identifier, body)
            elif target.platform == "tw":
                resp = self._tw_dm(client, target.identifier, body)
            elif target.platform == "rd":
                resp = self._rd_dm(client, target.identifier, subject, body)
            else:
                return {"ok": False, "error": f"unknown platform {target.platform}"}
            return {"ok": True, "response": resp}
        except Exception as exc:
            logger.exception("DM dispatch error %s %s: %s", target.platform, target.identifier, exc)
            return {"ok": False, "error": str(exc)}

    # ── platform-specific DM senders ──────────────────────────────────────────

    @staticmethod
    def _ig_dm(client, identifier: str, text: str) -> Dict:
        """
        Resolve identifier to user_id if it's a username, then send.
        Identifier is treated as user_id if it's all digits.
        """
        if identifier.isdigit():
            user_id = identifier
        else:
            info    = client.fetch_user(identifier)
            user_id = str(info.get("user", {}).get("pk", ""))
            if not user_id:
                raise ValueError(f"IG user not found: {identifier}")
        return client.send_dm_to_user(user_id, text)

    @staticmethod
    def _tt_dm(client, user_id: str, text: str) -> Dict:
        return client.send_dm_to_user(user_id, text)

    @staticmethod
    def _tw_dm(client, user_id: str, text: str) -> Dict:
        return client.send_dm(user_id, text)

    @staticmethod
    def _rd_dm(client, username: str, subject: str, text: str) -> Dict:
        return client.send_dm(username, subject or "Hello", text)

    # ── internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _target_key(t: DMTarget) -> str:
        return f"{t.platform}:{t.identifier}"

    def _sleep(self) -> None:
        lo = self._delay * (1 - self._variance)
        hi = self._delay * (1 + self._variance)
        time.sleep(random.uniform(lo, hi))

    def _mark_sent(self, key: str) -> None:
        self._sent.add(key)
        self._save_sent_log()

    def _load_sent_log(self) -> None:
        if os.path.exists(self._sent_log_path):
            try:
                with open(self._sent_log_path) as fh:
                    self._sent = set(json.load(fh))
            except Exception:
                self._sent = set()

    def _save_sent_log(self) -> None:
        with open(self._sent_log_path, "w") as fh:
            json.dump(list(self._sent), fh)


def _jitter_sleep(base: float) -> None:
    time.sleep(base * random.uniform(0.7, 1.4))
