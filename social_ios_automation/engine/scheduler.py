"""
Periodic task scheduler.

Runs in a background thread (or standalone process).
Uses a simple time-based loop — no external cron dependency.

Tasks registered:
  • every 1h  — account health smoke tests (B1)
  • every 24h — daily metrics collection (B5) at 03:00 UTC
  • every 6h  — content calendar buffer check (B6)
  • every 30m — job queue flush (runs Worker.run_once in a burst)

Entry point:
  Scheduler(worker, client_factory, notify_fn).start()  # blocks
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .health    import run_all_checks
from .metrics   import run_collection
from .calendar  import calculate_buffer
from .models    import PlatformAccount
from .publisher import Worker

logger = logging.getLogger(__name__)


class Scheduler:
    """
    client_factory(platform, account_row) → client
    notify(owner_id, event_type, payload) → None
    """

    def __init__(
        self,
        worker:         Worker,
        client_factory: Callable[[str, Dict], Any],
        notify:         Optional[Callable[[str, str, dict], None]] = None,
        model_ids:      Optional[List[str]] = None,
    ):
        self._worker    = worker
        self._factory   = client_factory
        self._notify    = notify or (lambda *a: None)
        self._model_ids = model_ids    # None = all models
        self._stop      = threading.Event()

        self._last = {
            "health":   0.0,
            "metrics":  0.0,
            "calendar": 0.0,
        }
        self._intervals = {
            "health":   3600,
            "metrics":  86400,
            "calendar": 21600,
        }

    def stop(self) -> None:
        self._stop.set()

    def start(self, queue_poll: float = 5.0) -> None:
        """Block and run all periodic tasks plus the job queue."""
        logger.info("Scheduler started")
        while not self._stop.is_set():
            now = time.time()

            for task, interval in self._intervals.items():
                if now - self._last[task] >= interval:
                    self._run_task(task)
                    self._last[task] = now

            # drain a batch of jobs
            for _ in range(20):
                result = self._worker.run_once()
                if not result:
                    break

            time.sleep(queue_poll)

        logger.info("Scheduler stopped")

    def _run_task(self, task: str) -> None:
        try:
            if task == "health":
                self._task_health()
            elif task == "metrics":
                self._task_metrics()
            elif task == "calendar":
                self._task_calendar()
        except Exception:
            logger.exception("Periodic task %s failed", task)

    def _task_health(self) -> None:
        logger.info("Running account health checks")
        accounts = PlatformAccount.find()
        if self._model_ids:
            accounts = [a for a in accounts if a.get("model_id") in self._model_ids]
        results = run_all_checks(
            accounts, self._factory,
            notify=lambda owner, acct_id, status: self._notify(
                owner, "account_status_changed",
                {"account_id": acct_id, "status": status}
            ),
        )
        degraded = [r for r in results if r.status not in ("ok",)]
        if degraded:
            logger.warning("%d accounts degraded", len(degraded))

    def _task_metrics(self) -> None:
        now = datetime.now(timezone.utc)
        if now.hour != 3:    # collect at 03:xx UTC only
            return
        logger.info("Running daily metrics collection for %s",
                    now.date().isoformat())
        accounts = PlatformAccount.find(platform="fansly")
        if self._model_ids:
            accounts = [a for a in accounts if a.get("model_id") in self._model_ids]
        run_collection(accounts, self._factory,
                       date_str=now.date().isoformat())

    def _task_calendar(self) -> None:
        logger.info("Running content calendar buffer check")
        model_ids = self._model_ids
        if not model_ids:
            from .db import execute
            rows = execute(
                "SELECT DISTINCT model_id FROM platform_accounts", fetch="all")
            model_ids = [str(r["model_id"]) for r in (rows or [])]

        for mid in model_ids:
            try:
                report = calculate_buffer(mid)
                if report.needs_content:
                    self._notify("system", "content_buffer_low", {
                        "model_id":     mid,
                        "days_covered": report.days_covered,
                        "threshold":    report.threshold_days,
                    })
            except Exception as exc:
                logger.warning("Calendar check failed for model %s: %s", mid, exc)
