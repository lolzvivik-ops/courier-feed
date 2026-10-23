"""
Proxy rotation pool.

Supports HTTP, HTTPS, SOCKS4, SOCKS5 proxies.
Reads from a text file, one proxy per line:
    http://user:pass@host:port
    socks5://host:port
    host:port           ← assumed http://

Rotation strategies:
    "round_robin"   — sequential wrap-around
    "random"        — uniform random pick
    "least_used"    — rotate to the proxy with fewest total requests
    "failover"      — stick to current proxy; rotate only on failure
"""

import os
import random
import threading
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ProxyPool:
    """
    Thread-safe proxy pool with rotation and health tracking.
    """

    def __init__(
        self,
        proxies:    Optional[List[str]] = None,
        proxy_file: Optional[str]       = None,
        strategy:   str                 = "round_robin",
        cooldown:   float               = 0.0,   # seconds between reuse of same proxy
    ):
        raw = list(proxies or [])
        if proxy_file and os.path.exists(proxy_file):
            raw += _load_proxy_file(proxy_file)

        self._proxies: List[str] = [_normalize(p) for p in raw if p.strip()]
        if not self._proxies:
            logger.warning("ProxyPool initialised with 0 proxies.")

        self._strategy  = strategy
        self._cooldown  = cooldown
        self._lock      = threading.Lock()
        self._index     = 0
        self._counters: Dict[str, int]   = {p: 0 for p in self._proxies}
        self._failures: Dict[str, int]   = {p: 0 for p in self._proxies}
        self._last_used: Dict[str, float] = {p: 0.0 for p in self._proxies}

    # ── public API ────────────────────────────────────────────────────────────

    def next(self) -> Optional[str]:
        """Return the next proxy according to the rotation strategy."""
        with self._lock:
            if not self._proxies:
                return None

            available = self._available()
            if not available:
                available = self._proxies   # cooldown exhausted — use any

            if self._strategy == "round_robin":
                proxy = self._round_robin(available)
            elif self._strategy == "random":
                proxy = random.choice(available)
            elif self._strategy == "least_used":
                proxy = min(available, key=lambda p: self._counters[p])
            else:
                proxy = available[0]

            self._counters[proxy]  += 1
            self._last_used[proxy] = time.time()
            return proxy

    def report_failure(self, proxy: str) -> None:
        """Increment failure count; remove proxy after 5 consecutive failures."""
        with self._lock:
            if proxy in self._failures:
                self._failures[proxy] += 1
                if self._failures[proxy] >= 5:
                    logger.warning("Removing dead proxy: %s", proxy)
                    self._proxies.remove(proxy)
                    del self._failures[proxy]
                    del self._counters[proxy]
                    del self._last_used[proxy]

    def report_success(self, proxy: str) -> None:
        with self._lock:
            if proxy in self._failures:
                self._failures[proxy] = 0

    def add(self, proxy: str) -> None:
        p = _normalize(proxy)
        with self._lock:
            if p not in self._proxies:
                self._proxies.append(p)
                self._counters[p]   = 0
                self._failures[p]   = 0
                self._last_used[p]  = 0.0

    def size(self) -> int:
        return len(self._proxies)

    def all(self) -> List[str]:
        return list(self._proxies)

    # ── internal ──────────────────────────────────────────────────────────────

    def _available(self) -> List[str]:
        """Proxies not currently in cooldown."""
        now = time.time()
        return [p for p in self._proxies if now - self._last_used[p] >= self._cooldown]

    def _round_robin(self, subset: List[str]) -> str:
        proxy = subset[self._index % len(subset)]
        self._index = (self._index + 1) % len(subset)
        return proxy


# ── file / format helpers ─────────────────────────────────────────────────────

def _load_proxy_file(path: str) -> List[str]:
    with open(path) as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]


def _normalize(proxy: str) -> str:
    """
    Ensure proxy string has a scheme prefix.
    host:port            → http://host:port
    user:pass@host:port  → http://user:pass@host:port
    socks5://...         → unchanged
    """
    proxy = proxy.strip()
    if proxy.startswith(("http://", "https://", "socks4://", "socks5://")):
        return proxy
    # detect socks5 by port
    parts = proxy.rsplit(":", 1)
    if parts[-1].isdigit():
        port = int(parts[-1])
        if port in (1080, 9050, 9150, 10808):
            return f"socks5://{proxy}"
    return f"http://{proxy}"
