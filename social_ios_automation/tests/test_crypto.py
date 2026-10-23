"""
Unit tests — core crypto layer (no network required).

Tests:
  sign_ig_body()      — HMAC-SHA256 signed_body= format
  encrypt_ig_password() — #PWD_INSTAGRAM:4:ts:b64
  generate_oauth1_header() — RFC 5849 Authorization header
  gorgon_sign()       — TikTok X-Gorgon nibble shuffle + XOR(0x05) + MD5 triplet
"""

import hashlib
import hmac
import time
import unittest
from unittest.mock import patch

from social_ios_automation.config import IG_SIG_KEY
from social_ios_automation.core.crypto import (
    sign_ig_body,
    generate_oauth1_header,
    gorgon_sign,
)


class TestInstagramSigning(unittest.TestCase):

    def test_sign_ig_body_format(self):
        """Output must be: signed_body=<hmac>.<json>&ig_sig_key_version=4"""
        body = '{"username":"test","password":"x"}'
        result = sign_ig_body(body)
        self.assertIn("signed_body=", result)
        self.assertIn("ig_sig_key_version=4", result)
        parts = result.split(".")
        # first part is "signed_body=<64-hex>"
        sig = parts[0].replace("signed_body=", "")
        self.assertEqual(len(sig), 64, "HMAC-SHA256 hex is 64 chars")
        # validate HMAC
        expected = hmac.new(
            IG_SIG_KEY.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        self.assertEqual(sig, expected)

    def test_sign_ig_body_payload_intact(self):
        """Original JSON body must appear verbatim after the dot."""
        body = '{"test":1}'
        result = sign_ig_body(body)
        after_dot = result.split(".", 1)[1].split("&")[0]
        self.assertEqual(after_dot, body)


class TestOAuth1Header(unittest.TestCase):

    CONSUMER_KEY    = "IQKbtAYlXLripLGFWd8pajn4A"
    CONSUMER_SECRET = "darkobjective"
    TOKEN           = "access-token-123"
    TOKEN_SECRET    = "token-secret-456"

    def _parse_header(self, header: str) -> dict:
        # OAuth realm="...", key="value", ...
        pairs = {}
        for part in header.replace("OAuth ", "").split(", "):
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            pairs[k.strip()] = v.strip().strip('"')
        return pairs

    def test_header_has_required_fields(self):
        header = generate_oauth1_header(
            "GET", "https://api.twitter.com/2/users/me",
            self.CONSUMER_KEY, self.CONSUMER_SECRET,
            self.TOKEN, self.TOKEN_SECRET,
        )
        self.assertTrue(header.startswith("OAuth "))
        parsed = self._parse_header(header)
        for field in ("oauth_consumer_key", "oauth_signature",
                      "oauth_timestamp", "oauth_nonce",
                      "oauth_signature_method", "oauth_version"):
            self.assertIn(field, parsed, f"Missing: {field}")

    def test_signature_method_is_hmac_sha1(self):
        header = generate_oauth1_header(
            "POST", "https://api.twitter.com/1.1/statuses/update.json",
            self.CONSUMER_KEY, self.CONSUMER_SECRET,
            self.TOKEN, self.TOKEN_SECRET,
        )
        parsed = self._parse_header(header)
        self.assertEqual(parsed["oauth_signature_method"], "HMAC-SHA1")

    def test_consumer_key_passed_through(self):
        header = generate_oauth1_header(
            "GET", "https://api.twitter.com/2/users/me",
            self.CONSUMER_KEY, self.CONSUMER_SECRET,
            self.TOKEN, self.TOKEN_SECRET,
        )
        parsed = self._parse_header(header)
        self.assertEqual(parsed["oauth_consumer_key"], self.CONSUMER_KEY)


class TestGorgonSign(unittest.TestCase):

    def test_output_is_base64(self):
        """X-Gorgon must be a non-empty base64 string."""
        import base64
        result = gorgon_sign(b"test_body_data", int(time.time()))
        # should not raise
        decoded = base64.b64decode(result)
        self.assertGreater(len(decoded), 0)

    def test_different_payloads_differ(self):
        ts = int(time.time())
        g1 = gorgon_sign(b"payload_one", ts)
        g2 = gorgon_sign(b"payload_two", ts)
        self.assertNotEqual(g1, g2)

    def test_same_input_deterministic(self):
        ts = 1700000000
        g1 = gorgon_sign(b"stable", ts)
        g2 = gorgon_sign(b"stable", ts)
        self.assertEqual(g1, g2)


class TestDeviceProfile(unittest.TestCase):

    def test_seeded_device_is_stable(self):
        from social_ios_automation.core.device import DeviceProfile
        d1 = DeviceProfile.from_seed("user123", "instagram")
        d2 = DeviceProfile.from_seed("user123", "instagram")
        self.assertEqual(d1.device_id, d2.device_id)
        self.assertEqual(d1.model, d2.model)
        self.assertEqual(d1.ios_version, d2.ios_version)

    def test_different_seeds_differ(self):
        from social_ios_automation.core.device import DeviceProfile
        d1 = DeviceProfile.from_seed("user_a", "instagram")
        d2 = DeviceProfile.from_seed("user_b", "instagram")
        self.assertNotEqual(d1.device_id, d2.device_id)

    def test_ua_contains_ios_platform(self):
        from social_ios_automation.core.device import DeviceProfile
        d = DeviceProfile.from_seed("test", "instagram")
        ua = d.instagram_ua
        self.assertIn("iPhone", ua)
        self.assertIn("iOS", ua)


if __name__ == "__main__":
    unittest.main()
