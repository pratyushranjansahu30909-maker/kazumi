# -*- coding: utf-8 -*-
"""
🌸 Comprehensive Security & Reliability Unit Tests for Kazumi OpenAI Integration
Validates:
1. Configuration validation: missing key, empty key, placeholder values
2. Secret redaction: sk-*, Bearer, Discord tokens, HF tokens, credential URLs
3. Canonical variable harmonization (OPENAI_API_KEY and API_KEY)
4. HTTP 401 Auth error handling & circuit breaker lock
5. HTTP 429 Quota exhaustion vs Rate limit distinction & cooldown
6. HTTP 5xx transient error handling with bounded exponential backoff
7. Per-user request limiting and duplicate prompt prevention
8. Graceful cognitive fallback in Kazumi core when API is offline
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from openai_reliability import (
    validate_openai_config,
    is_placeholder_key,
    OpenAIReliabilityGuard,
    get_reliability_guard,
)
from discord_features.config import sanitize_secrets


class TestOpenAISecurityAndReliability(unittest.TestCase):
    def setUp(self):
        # Save env state
        self._orig_openai_key = os.environ.get("OPENAI_API_KEY")
        self._orig_api_key = os.environ.get("API_KEY")

    def tearDown(self):
        # Restore env state
        if self._orig_openai_key is not None:
            os.environ["OPENAI_API_KEY"] = self._orig_openai_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)

        if self._orig_api_key is not None:
            os.environ["API_KEY"] = self._orig_api_key
        else:
            os.environ.pop("API_KEY", None)

    # =========================================================================
    # 1. Configuration Validation & Placeholder Rejection
    # =========================================================================
    def test_placeholder_detection(self):
        """Verifies that dummy, template, and placeholder keys are caught."""
        self.assertTrue(is_placeholder_key(""))
        self.assertTrue(is_placeholder_key(None))
        self.assertTrue(is_placeholder_key("your_openai_api_key_here"))
        self.assertTrue(is_placeholder_key("your_api_key_here"))
        self.assertTrue(is_placeholder_key("sk-placeholder1234567890123"))
        self.assertTrue(is_placeholder_key("sk-dummy123456789012345678"))
        self.assertTrue(is_placeholder_key("short"))
        self.assertTrue(is_placeholder_key("no_prefix_12345678901234567890"))
        # Real-looking format is not rejected by placeholder heuristic
        self.assertFalse(is_placeholder_key("sk-" + "proj-" + "prodvalidformat1234567890abcdef"))

    def test_missing_key_validation(self):
        """Missing key produces a safe configuration error without throwing."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "API_KEY": ""}, clear=True):
            with patch("os.path.exists", return_value=False):
                valid, msg, key = validate_openai_config()
                self.assertFalse(valid)
                self.assertIn("missing", msg.lower())
                self.assertIsNone(key)

    def test_placeholder_key_validation(self):
        """Placeholder key produces clear error and rejects the credential."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "your_openai_api_key_here", "API_KEY": ""}, clear=False):
            valid, msg, key = validate_openai_config()
            self.assertFalse(valid)
            self.assertIn("placeholder", msg.lower())
            self.assertIsNone(key)

    def test_canonical_synchronization(self):
        """Valid OPENAI_API_KEY synchronizes API_KEY in os.environ."""
        fake_key = "sk-" + "proj-" + "testvalidcanonicalcredential1234567890abcdef"
        with patch.dict(os.environ, {"OPENAI_API_KEY": fake_key, "API_KEY": ""}, clear=False):
            valid, msg, key = validate_openai_config()
            self.assertTrue(valid)
            self.assertEqual(key, fake_key)
            self.assertEqual(os.environ.get("API_KEY"), fake_key)
            # Never expose the full key in the message
            self.assertNotIn(fake_key, msg)

    # =========================================================================
    # 2. Secret Redaction & Sanitization
    # =========================================================================
    def test_secret_redaction(self):
        """Ensures all varieties of secrets are masked from logs and strings."""
        # OpenAI project key
        sk_proj = "sk-" + "proj-" + "faketestdummy1234567890abcdefghijklmnopqrstuvwxyz"
        clean = sanitize_secrets(f"Connecting to OpenAI with {sk_proj} now.")
        self.assertNotIn(sk_proj, clean)
        self.assertIn("[REDACTED_SECRET]", clean)

        # Bearer header
        auth_header = "Authorization: " + "Bearer " + "9876543210fedcba9876543210"
        clean = sanitize_secrets(f"Headers: {auth_header}")
        self.assertNotIn("9876543210fedcba9876543210", clean)
        self.assertIn("Bearer [REDACTED_SECRET]", clean)

        # HuggingFace token
        hf_token = "hf_" + "AbCdEfGhIjKlMnOpQrStUvWxYz123456"
        clean = sanitize_secrets(f"Cloning from git with token {hf_token}...")
        self.assertNotIn(hf_token, clean)
        self.assertIn("[REDACTED_SECRET]", clean)

        # Discord webhook
        webhook = "https://" + "discord.com/api/webhooks/123456789/" + "AbCdEfGhIjKlMnOp"
        clean = sanitize_secrets(f"Posting to {webhook}")
        self.assertNotIn(webhook, clean)
        self.assertIn("[REDACTED_WEBHOOK_URL]", clean)

        # URL with embedded credentials
        cred_url = "https://" + "user:my_secret_password_123@" + "github.com/repo.git"
        clean = sanitize_secrets(f"Remote: {cred_url}")
        self.assertNotIn("my_secret_password_123", clean)
        self.assertIn("[REDACTED_AUTH]@", clean)

    # =========================================================================
    # 3. HTTP 401 Authentication Error & Circuit Breaker
    # =========================================================================
    def test_auth_error_circuit_breaker(self):
        """HTTP 401 Unauthorized trips circuit breaker and ceases further attempts."""
        import openai
        guard = OpenAIReliabilityGuard()
        # Reset guard state for test
        guard._auth_broken = False
        guard.is_valid = True
        guard._client = MagicMock()

        # Mock function raising AuthenticationError
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.headers = {}
        err = openai.AuthenticationError(
            message="Incorrect API key provided: sk-invalid...",
            response=mock_resp,
            body={"error": {"message": "Invalid key", "type": "invalid_request_error"}}
        )

        call_fn = MagicMock(side_effect=err)
        result = guard.execute_completion(call_fn, user_id="12345")

        self.assertIsNone(result)
        self.assertTrue(guard._auth_broken)
        self.assertFalse(guard.is_available())
        # Exactly one call attempted; circuit breaker prevents repeated attempts
        self.assertEqual(call_fn.call_count, 1)

        # Next call is rejected immediately by is_available() without hitting call_fn
        result2 = guard.execute_completion(call_fn, user_id="12345")
        self.assertIsNone(result2)
        self.assertEqual(call_fn.call_count, 1)

        # Reset state
        guard._auth_broken = False

    # =========================================================================
    # 4. HTTP 429 Quota Exhaustion vs Rate Limit
    # =========================================================================
    def test_quota_exhausted_trips_breaker(self):
        """Quota exhaustion (insufficient_quota) enters 300s cooldown without spamming retries."""
        import openai
        guard = OpenAIReliabilityGuard()
        guard._auth_broken = False
        guard._quota_cooldown_until = 0.0
        guard.is_valid = True
        guard._client = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        err = openai.RateLimitError(
            message="You exceeded your current quota, please check your plan and billing details.",
            response=mock_resp,
            body={"error": {"code": "insufficient_quota", "message": "You exceeded your current quota."}}
        )

        call_fn = MagicMock(side_effect=err)
        result = guard.execute_completion(call_fn, user_id="12345")

        self.assertIsNone(result)
        # Quota breaker set in future
        self.assertGreater(guard._quota_cooldown_until, time.time())
        self.assertFalse(guard.is_available())
        self.assertEqual(call_fn.call_count, 1)

        # Reset cooldown
        guard._quota_cooldown_until = 0.0

    def test_rate_limit_transient_retry(self):
        """Temporary rate limiting (non-quota) attempts bounded backoff before falling back."""
        import openai
        guard = OpenAIReliabilityGuard()
        guard._auth_broken = False
        guard._quota_cooldown_until = 0.0
        guard.is_valid = True
        guard._client = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"retry-after": "0.1"}
        err = openai.RateLimitError(
            message="Rate limit reached for requests per min (RPM).",
            response=mock_resp,
            body={"error": {"code": "rate_limit_exceeded"}}
        )

        call_fn = MagicMock(side_effect=err)
        result = guard.execute_completion(call_fn, user_id="12345", max_retries=1)

        self.assertIsNone(result)
        # Bounded retries: 1 initial + 1 retry = 2 attempts
        self.assertEqual(call_fn.call_count, 2)

    # =========================================================================
    # 5. HTTP 5xx Server Error Bounded Backoff
    # =========================================================================
    def test_transient_server_error_recovery(self):
        """Transient 5xx error recovers on second attempt."""
        import openai
        guard = OpenAIReliabilityGuard()
        guard._auth_broken = False
        guard._quota_cooldown_until = 0.0
        guard.is_valid = True
        guard._client = MagicMock()

        mock_success = MagicMock()
        mock_success.choices = [MagicMock(message=MagicMock(content="Hello!"))]

        mock_resp = MagicMock()
        mock_resp.status_code = 502
        err = openai.InternalServerError(message="Bad Gateway", response=mock_resp, body=None)

        call_fn = MagicMock(side_effect=[err, mock_success])
        result = guard.execute_completion(call_fn, user_id="12345", max_retries=2)

        self.assertIsNotNone(result)
        self.assertEqual(call_fn.call_count, 2)
        self.assertEqual(result.choices[0].message.content, "Hello!")

    # =========================================================================
    # 6. Per-User Rate Limiting & Duplicate Prompt Prevention
    # =========================================================================
    def test_per_user_rate_limit(self):
        """User exceeding 5 requests in 10s is throttled to fallback."""
        guard = OpenAIReliabilityGuard()
        uid = "test_rate_user_999"
        guard._user_requests.pop(uid, None)

        for _ in range(5):
            self.assertTrue(guard.check_user_rate_limit(uid, max_requests=5, window_seconds=10.0))
        # 6th request fails rate limit
        self.assertFalse(guard.check_user_rate_limit(uid, max_requests=5, window_seconds=10.0))

    def test_duplicate_prompt_prevention(self):
        """Submitting identical prompt within TTL is identified as duplicate."""
        guard = OpenAIReliabilityGuard()
        uid = "test_dup_user_888"
        prompt = "Hello Kazumi!"

        self.assertFalse(guard.is_duplicate_request(uid, prompt, ttl_seconds=2.0))
        # Immediate resubmission is duplicate
        self.assertTrue(guard.is_duplicate_request(uid, prompt, ttl_seconds=2.0))
        # Different prompt is not duplicate
        self.assertFalse(guard.is_duplicate_request(uid, "Different text", ttl_seconds=2.0))

    # =========================================================================
    # 7. Kazumi Cognitive Fallback Integration
    # =========================================================================
    def test_kazumi_offline_personality_fallback(self):
        """When OpenAI is offline, Kazumi replies using local personality fallback pools."""
        from kazumi import Kazumi
        bot = Kazumi()
        guard = get_reliability_guard()
        with patch.object(guard, "is_available", return_value=False):
            # Test direct reply
            reply = bot.reply("hello")
            self.assertIsNotNone(reply)
            self.assertTrue(len(reply) > 0)
            self.assertNotIn("Error", reply)
            self.assertNotIn("Exception", reply)

            # Test cognitive controller generate_response
            reply2 = bot.controller.generate_response("hello", valence=0.5, memory_context={})
            self.assertIsNotNone(reply2)
            self.assertTrue(len(reply2) > 0)


if __name__ == "__main__":
    unittest.main()
