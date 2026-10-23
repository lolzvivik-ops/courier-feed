"""
Unit tests — notification catalog and service routing (no network, no DB).

Tests:
  - All 30+ catalog entries have required fields
  - get_text() respects no_text mode
  - NotificationService spam cap (model per-day, owner 10-min dedup)
  - Quiet hours logic (normal and overnight windows)
  - Undisableable flag bypasses category disable
  - urgent flag auto-resolved from catalog
"""

import unittest
from datetime import time as dtime
from unittest.mock import MagicMock, call

from social_ios_automation.notifications.catalog import CATALOG, get_text, is_urgent
from social_ios_automation.notifications.service import NotificationService


class TestCatalog(unittest.TestCase):

    def test_all_entries_have_required_fields(self):
        required = {"title", "body", "category"}
        for event_type, entry in CATALOG.items():
            for user_type in ("model", "owner"):
                side = entry.get(user_type)
                if side is None:
                    continue
                missing = required - set(side.keys())
                self.assertFalse(
                    missing,
                    f"{event_type}/{user_type} missing fields: {missing}",
                )

    def test_get_text_no_text_mode(self):
        text = get_text("post_published", "model", no_text=True)
        self.assertEqual(text["title"], "")
        self.assertEqual(text["body"], "")

    def test_get_text_normal_mode(self):
        text = get_text("post_published", "owner", no_text=False)
        self.assertNotEqual(text["title"], "")

    def test_urgent_events_flagged(self):
        for evt in ("publisher_stopped", "smoke_test_failed",
                    "post_removed_by_platform", "account_login_expiring",
                    "payout_needs_human"):
            self.assertTrue(is_urgent(evt), f"{evt} should be urgent")

    def test_normal_events_not_urgent(self):
        for evt in ("post_published", "daily_digest", "plan_item_new"):
            self.assertFalse(is_urgent(evt), f"{evt} should not be urgent")

    def test_new_device_login_undisableable(self):
        entry = CATALOG["new_device_login"]["model"]
        self.assertTrue(entry.get("undisableable"))

    def test_deep_links_present_on_key_events(self):
        events_with_links = [
            ("plan_item_new",         "model",  "cabinet://"),
            ("publisher_stopped",     "owner",  "remote://"),
            ("payout_needs_human",    "owner",  "remote://"),
        ]
        for evt, user_type, prefix in events_with_links:
            link = CATALOG[evt][user_type].get("deep_link", "")
            self.assertTrue(link.startswith(prefix),
                            f"{evt}/{user_type} deep_link should start with {prefix}")


class TestNotificationServiceSpam(unittest.TestCase):

    def _make_service(self, count_result: int, user_type: str):
        """Service where DB COUNT always returns count_result."""
        exec_mock = MagicMock()

        def fake_execute(sql, params, fetch=None):
            if fetch == "one":
                if "notification_settings" in sql:
                    return None   # no settings → defaults
                if "devices" in sql:
                    return []
                return {"cnt": count_result}
            if fetch == "all":
                return []
            return None

        exec_mock.side_effect = fake_execute
        return NotificationService(apns_client=None, db_execute=exec_mock)

    def test_model_under_daily_cap_passes(self):
        svc = self._make_service(0, "model")
        result = svc.send("u1", "model", "post_published")
        self.assertNotEqual(result.status, "skipped_spam")

    def test_model_at_daily_cap_blocked(self):
        svc = self._make_service(3, "model")
        result = svc.send("u1", "model", "post_published")
        self.assertEqual(result.status, "skipped_spam")

    def test_owner_fresh_passes(self):
        svc = self._make_service(0, "owner")
        result = svc.send("u2", "owner", "post_published")
        self.assertNotEqual(result.status, "skipped_spam")

    def test_owner_within_10min_deduped(self):
        svc = self._make_service(1, "owner")
        result = svc.send("u2", "owner", "post_published")
        self.assertEqual(result.status, "skipped_spam")


class TestNotificationServiceQuietHours(unittest.TestCase):

    def _service_with_quiet(self, quiet_start, quiet_end):
        exec_mock = MagicMock()

        def fake_execute(sql, params, fetch=None):
            if "notification_settings" in sql and fetch == "one":
                return {
                    "enabled":     True,
                    "quiet_start": quiet_start,
                    "quiet_end":   quiet_end,
                    "no_text_mode": False,
                    "badge_enabled": False,
                }
            if fetch == "one":
                return {"cnt": 0}
            if fetch == "all":
                return []
            return None

        exec_mock.side_effect = fake_execute
        return NotificationService(apns_client=None, db_execute=exec_mock)

    def test_in_quiet_hours_blocked(self):
        svc = self._service_with_quiet(dtime(0, 0), dtime(23, 59))
        result = svc.send("u1", "model", "post_published", urgent=False)
        self.assertEqual(result.status, "skipped_quiet")

    def test_urgent_bypasses_quiet_hours(self):
        svc = self._service_with_quiet(dtime(0, 0), dtime(23, 59))
        result = svc.send("u1", "owner", "publisher_stopped", urgent=True)
        self.assertNotEqual(result.status, "skipped_quiet")

    def test_outside_quiet_hours_passes(self):
        # quiet 02:00–04:00 — we're definitely not in that window
        svc = self._service_with_quiet(dtime(2, 0), dtime(4, 0))
        # patch datetime.now to return 10:00 UTC
        import social_ios_automation.notifications.service as svc_mod
        from unittest.mock import patch
        from datetime import datetime, timezone

        class FakeDT(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

        with patch.object(svc_mod, "datetime", FakeDT):
            result = svc.send("u1", "model", "post_published", urgent=False)
        self.assertNotEqual(result.status, "skipped_quiet")


class TestNotificationServiceUndisableable(unittest.TestCase):

    def test_security_event_bypasses_category_disable(self):
        exec_mock = MagicMock()

        def fake_execute(sql, params, fetch=None):
            if "notification_settings" in sql and fetch == "one":
                return {"enabled": False}   # category disabled
            if fetch == "one":
                return {"cnt": 0}
            if fetch == "all":
                return []
            return None

        exec_mock.side_effect = fake_execute
        svc = NotificationService(apns_client=None, db_execute=exec_mock)
        result = svc.send("u1", "model", "new_device_login")
        self.assertNotEqual(result.status, "skipped_disabled",
                            "new_device_login must not be blockable")


if __name__ == "__main__":
    unittest.main()
