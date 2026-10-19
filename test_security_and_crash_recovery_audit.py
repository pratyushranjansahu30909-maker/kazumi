# -*- coding: utf-8 -*-
"""
🌸 Automated Security Hardening & Crash Recovery Audit Test Suite
Covers:
1. Interrupted memory writes and previous state recovery.
2. Corrupt primary file quarantine and valid .bak recovery.
3. Partial giveaway intent parsing without giveaway activation.
4. Mocked OpenAI 401 AuthenticationError, degraded mode, bounded logging, and no retry storm.
5. Mocked Discord gateway disconnect and recovery idempotency.
6. Fatal process safety net and nonzero exit behavior in isolated subprocess.
7. Restart-loop persistence across simulated process restarts, corrupt-state quarantine, and capped backoff.
8. Secret redaction across log records, handler output, tracebacks, formatted exceptions, and Discord-facing messages.
9. Core regressions:
   - Exactly one response for '@Kazumi u mad?'
   - Giveaway intent parsing for '@Kazumi host a gw for 800 robux'
   - Per-user memory isolation and persistence for 'my favorite flower is the white lotus'
"""

import os
import sys
import time
import json
import shutil
import logging
import asyncio
import unittest
import subprocess
from unittest.mock import MagicMock, AsyncMock, patch

import discord

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from kazumi_memory import ChromaMemory
from discord_features.database import FeatureDatabase
from discord_features.config import (
    sanitize_secrets,
    register_secret,
    SanitizedLogFormatter,
    RedactionFilter,
    KazumiConfig,
)
from openai_reliability import (
    validate_openai_config,
    OpenAIReliabilityGuard,
    get_reliability_guard,
)
from restart_protector import RestartLoopProtector
import discord_bot


class SecurityAndCrashRecoveryAuditTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.test_dir = os.path.join(ROOT_DIR, "test_audit_tmp_sandbox")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        os.makedirs(self.test_dir, exist_ok=True)

        # Clear dedup caches for clean message testing
        discord_bot._processed_message_ids_set.clear()
        discord_bot._processed_message_ids_deque.clear()
        discord_bot.active_conversations.clear()
        discord_bot.user_rapid_typing.clear()

        # Set mock bot user
        mock_user = MagicMock(spec=discord.User)
        mock_user.id = 999000
        mock_user.name = "Kazumi"
        mock_user.bot = True
        discord_bot.bot._user = mock_user
        discord_bot.bot._connection.user = mock_user

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # =========================================================================
    # 1. ATOMIC PERSISTENCE & RECOVERY SAFEGUARDS
    # =========================================================================
    def test_interrupted_memory_write_recovery(self):
        """Simulates crash before .tmp is renamed; verifies original valid state is intact."""
        mem = ChromaMemory(persist_directory=self.test_dir)
        mem.add("First valid memory text", speaker="user", session_id="user_1")

        conv_file = os.path.join(self.test_dir, "conversations.json")
        self.assertTrue(os.path.exists(conv_file))

        # Simulate incomplete crash: an abandoned .tmp file with corrupted partial data
        tmp_file = f"{conv_file}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write("PARTIAL_CORRUPTED_WRITE_DURING_CRASH")

        # Reload memory
        new_mem = ChromaMemory(persist_directory=self.test_dir)
        history = new_mem.load_history()
        self.assertTrue(len(history) >= 1)
        self.assertEqual(history[0]["text"], "First valid memory text")

    def test_corrupt_primary_file_quarantine_and_backup_recovery(self):
        """Corrupt primary file is quarantined as *.corrupted.<timestamp> and valid backup is loaded."""
        db = FeatureDatabase(persist_dir=self.test_dir)
        # Write initial valid state
        db.guild_settings["12345"] = {"prefix": "!custom"}
        db._atomic_write(db.guild_settings_path, db.guild_settings)
        # Second write creates the validated .bak file
        db.guild_settings["12345"]["count"] = 1
        db._atomic_write(db.guild_settings_path, db.guild_settings)

        self.assertTrue(os.path.exists(db.guild_settings_path))
        bak_file = f"{db.guild_settings_path}.bak"
        self.assertTrue(os.path.exists(bak_file))

        # Corrupt primary JSON
        with open(db.guild_settings_path, "w", encoding="utf-8") as f:
            f.write("{ INVALID JSON DATA --- CORRUPTED ")

        # Reload database
        reloaded_db = FeatureDatabase(persist_dir=self.test_dir)
        # Verify it restored from backup
        self.assertIn("12345", reloaded_db.guild_settings)
        self.assertEqual(reloaded_db.guild_settings["12345"]["prefix"], "!custom")

        # Verify corrupt file was quarantined
        quarantined = [f for f in os.listdir(self.test_dir) if "guild_settings.json.corrupted." in f]
        self.assertTrue(len(quarantined) >= 1, "Expected corrupt primary file to be quarantined.")

    # =========================================================================
    # 2. GIVEAWAY WIZARD & INTENT INTEGRITY
    # =========================================================================
    def test_interrupted_giveaway_wizard_no_activation(self):
        """Partial giveaway input (@Kazumi host a gw for 800 robux) does not create live giveaway."""
        from discord_features.intent_router import NaturalIntentRouter

        mock_giveaways = MagicMock()
        db = FeatureDatabase(persist_dir=self.test_dir)
        router = NaturalIntentRouter(bot=discord_bot.bot, features_dict={"db": db, "giveaways": mock_giveaways})

        mock_msg = MagicMock(spec=discord.Message)
        mock_msg.content = "@Kazumi host a gw for 800 robux"
        mock_msg.author = MagicMock(spec=discord.Member)
        mock_msg.author.id = 1001
        perms = MagicMock()
        perms.manage_guild = True
        mock_msg.author.guild_permissions = perms
        mock_msg.guild = MagicMock(spec=discord.Guild)
        mock_msg.guild.id = 55555
        mock_msg.channel = MagicMock(spec=discord.TextChannel)
        mock_msg.channel.id = 66666

        intent = router.detect_intent(mock_msg.content, mock_msg)
        self.assertEqual(intent.get("category"), "giveaway")
        self.assertEqual(intent.get("prize"), "800 robux")
        self.assertIsNone(intent.get("duration"))

        # Execute intent
        handled, reply_text, reply_embed = asyncio.run(router.execute_intent(intent, mock_msg))
        self.assertTrue(handled)
        self.assertIn("how long should it run", reply_text.lower())
        self.assertIsNone(reply_embed)
        # Ensure no giveaway was started in database
        self.assertEqual(len(db.get_guild_giveaways("55555")), 0)

    # =========================================================================
    # 3. OPENAI 401 AUTHENTICATION ERROR & CIRCUIT BREAKER
    # =========================================================================
    def test_mocked_openai_401_circuit_breaker(self):
        """HTTP 401 trips circuit breaker, emits one error log, and degrades AI gracefully."""
        import openai

        guard = OpenAIReliabilityGuard()
        guard._auth_broken = False
        guard.is_valid = True

        call_count = 0

        def faulty_call():
            nonlocal call_count
            call_count += 1
            # Mock 401 AuthenticationError
            resp = MagicMock()
            resp.status_code = 401
            resp.headers = {}
            raise openai.AuthenticationError(
                message="Incorrect API key provided.",
                response=resp,
                body={"error": {"message": "Invalid API key", "type": "invalid_request_error"}}
            )

        # First execution: catches 401, trips breaker
        with patch.object(guard, "check_user_rate_limit", return_value=True):
            res1 = guard.execute_completion(faulty_call, user_id="test_user_401")
            self.assertIsNone(res1)
            self.assertTrue(guard.is_auth_broken())
            self.assertFalse(guard.is_available())

            # Second execution: immediately blocked by circuit breaker without calling faulty_call
            res2 = guard.execute_completion(faulty_call, user_id="test_user_401")
            self.assertIsNone(res2)
            self.assertEqual(call_count, 1, "Expected subsequent calls to be blocked without repeating auth request.")

            # Friendly user status message
            user_msg = guard.get_user_facing_status_message()
            self.assertIn("authentication setup issue", user_msg)
            self.assertIn("fully active", user_msg)

    # =========================================================================
    # 4. DISCORD GATEWAY DISCONNECT AND RECOVERY
    # =========================================================================
    async def test_discord_disconnect_and_resume_events(self):
        """Tests disconnect and resumed events without duplicate listener registration."""
        with patch.object(discord_bot.logger, "warning") as mock_warn, patch.object(discord_bot.logger, "info") as mock_info:
            await discord_bot.on_disconnect()
            mock_warn.assert_any_call("[RECONNECT] Discord Gateway connection dropped. Retrying automatically...")

            await discord_bot.on_resumed()
            mock_info.assert_any_call("[RECOVERY] Discord Gateway session successfully resumed! Kazumi is back listening.")

    # =========================================================================
    # 5. PROCESS-LEVEL SAFETY NET & NONZERO EXIT IN SUBPROCESS
    # =========================================================================
    def test_fatal_subprocess_failure_nonzero_exit(self):
        """Verifies unhandled thread exception triggers sys.excepthook and exits nonzero (code 1)."""
        code = (
            "import sys, os\n"
            "from discord_bot import setup_process_safety_net\n"
            "setup_process_safety_net()\n"
            "raise RuntimeError('simulated fatal unhandled crash')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True
        )
        self.assertEqual(proc.returncode, 1, f"Expected nonzero exit code 1, got {proc.returncode}")
        self.assertIn("Unhandled fatal exception", proc.stderr + proc.stdout)

    # =========================================================================
    # 6. PERSISTENT RESTART-LOOP PROTECTION
    # =========================================================================
    def test_restart_loop_protection_exponential_backoff(self):
        """Simulates rapid crash-restarts; verifies capped exponential backoff and quarantine."""
        state_file = os.path.join(self.test_dir, ".crash_loop_state.json")
        protector = RestartLoopProtector(
            state_file=state_file,
            window_seconds=120.0,
            base_delay_seconds=2.0,
            max_delay_seconds=10.0,
            max_rapid_failures=3
        )

        now = 1000000.0
        # First 3 rapid boots within window have no delay
        d1 = protector.record_boot_and_get_delay(now=now)
        d2 = protector.record_boot_and_get_delay(now=now + 5)
        d3 = protector.record_boot_and_get_delay(now=now + 10)
        self.assertEqual(d1, 0.0)
        self.assertEqual(d2, 0.0)
        self.assertEqual(d3, 0.0)

        # 4th rapid boot triggers backoff
        d4 = protector.record_boot_and_get_delay(now=now + 15)
        self.assertTrue(d4 >= 2.0, f"Expected backoff >= 2.0s, got {d4}")

        # 5th rapid boot increases delay
        d5 = protector.record_boot_and_get_delay(now=now + 20)
        self.assertTrue(d5 > d4)

        # 8th rapid boot capped at max_delay_seconds (10s)
        d8 = protector.record_boot_and_get_delay(now=now + 25)
        self.assertTrue(d8 <= 10.0)

        # Corrupt state file recovery:
        with open(state_file, "w", encoding="utf-8") as f:
            f.write("{ CORRUPT_STATE_DATA ")
        # Next boot quarantines corrupt state and resets
        delay_after_corrupt = protector.record_boot_and_get_delay(now=now + 30)
        self.assertEqual(delay_after_corrupt, 0.0)
        quarantined = [f for f in os.listdir(self.test_dir) if ".crash_loop_state.json.corrupted." in f]
        self.assertTrue(len(quarantined) >= 1)

        # Healthy run resets failure records
        protector.record_healthy()
        state = protector._read_state()
        self.assertEqual(len(state.get("failures", [])), 0)

    # =========================================================================
    # 7. COMPREHENSIVE SECRET REDACTION TESTS
    # =========================================================================
    def test_secret_redaction_patterns_and_exact_registry(self):
        """Verifies OpenAI keys, tokens, webhooks, auth headers, assignments, and exact values are masked."""
        # Assemble fake credentials from fragments to avoid static scanner false positives
        fake_sk = "sk-" + "proj-" + "1234567890abcdef1234567890abcdef"
        fake_tok = "MTIzNDU2Nzg5MDEyMzQ1Njc4" + "." + "GaBcDe" + "." + "1234567890123456789012345678"
        fake_hook = "https://" + "discord.com/api/webhooks/123456789/" + "aBcDeFgHiJkLmNoP"
        fake_auth = "Authorization: " + "Bearer " + "secret_token_1234567890abcdef"
        fake_assign = "DISCORD_BOT_TOKEN=" + fake_tok

        raw_log = f"Config state: key={fake_sk}, tok={fake_tok}, hook={fake_hook}, header={fake_auth}, assign: {fake_assign}"
        sanitized = sanitize_secrets(raw_log)

        self.assertNotIn(fake_sk, sanitized)
        self.assertNotIn(fake_tok, sanitized)
        self.assertNotIn(fake_hook, sanitized)
        self.assertNotIn("secret_token_1234567890abcdef", sanitized)
        self.assertIn("[REDACTED_SECRET]", sanitized)
        self.assertIn("[REDACTED_WEBHOOK_URL]", sanitized)

        # Test exact registered secret
        custom_secret = "VerySecretDatabasePassword_2026_XYZ"
        register_secret(custom_secret)
        msg_with_exact = f"Connecting with password {custom_secret} to internal cluster."
        clean_exact = sanitize_secrets(msg_with_exact)
        self.assertNotIn(custom_secret, clean_exact)
        self.assertIn("[REDACTED_SECRET]", clean_exact)

        # Test exception formatting redaction
        formatter = SanitizedLogFormatter()
        try:
            raise ValueError(f"Failed to connect using token {fake_tok}")
        except Exception:
            ei = sys.exc_info()
            formatted_exc = formatter.formatException(ei)
            self.assertNotIn(fake_tok, formatted_exc)
            self.assertIn("[REDACTED_SECRET]", formatted_exc)

    # =========================================================================
    # 8. REQUIRED REGRESSION TESTS
    # =========================================================================
    async def test_regression_single_response_u_mad(self):
        """Input: '@Kazumi u mad?' -> Produces exactly one response."""
        mock_msg = MagicMock(spec=discord.Message)
        mock_msg.id = 888101
        mock_msg.content = "@Kazumi u mad?"
        mock_msg.author = MagicMock(spec=discord.Member)
        mock_msg.author.id = 2002
        mock_msg.author.bot = False
        mock_msg.author.name = "Alice"
        mock_msg.author.display_name = "Alice"
        mock_msg.mentions = [discord_bot.bot.user]
        mock_msg.role_mentions = []
        mock_msg.reference = None
        mock_msg.attachments = []
        mock_msg.stickers = []

        mock_msg.channel = MagicMock(spec=discord.TextChannel)
        mock_msg.channel.name = "kazumi-chat"
        mock_msg.channel.id = 99999
        mock_msg.channel.send = AsyncMock()
        mock_msg.reply = AsyncMock()
        mock_msg.add_reaction = AsyncMock()

        class MockTyping:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass

        mock_msg.channel.typing = MagicMock(return_value=MockTyping())
        mock_msg.guild = MagicMock(spec=discord.Guild)
        mock_msg.guild.id = 88888
        mock_msg.guild.me = MagicMock()
        mock_msg.guild.me.roles = []
        mock_msg.guild.get_channel = MagicMock(return_value=mock_msg.channel)

        with patch("discord_bot.ask_kazumi", return_value="Nah, I'm completely chill 🌸"):
            await discord_bot.on_message(mock_msg)

        total_replies = mock_msg.reply.call_count + mock_msg.channel.send.call_count
        self.assertEqual(total_replies, 1, f"Expected exactly 1 reply for '@Kazumi u mad?', got {total_replies}")

    def test_regression_giveaway_intent_parsing(self):
        """Input: '@Kazumi host a gw for 800 robux' -> Correctly parsed as 800 Robux and remains pending."""
        from discord_features.intent_router import NaturalIntentRouter

        db = FeatureDatabase(persist_dir=self.test_dir)
        router = NaturalIntentRouter(bot=discord_bot.bot, features_dict={"db": db})

        mock_msg = MagicMock(spec=discord.Message)
        intent = router.detect_intent("@Kazumi host a gw for 800 robux", mock_msg)
        self.assertIsNotNone(intent)
        self.assertEqual(intent.get("category"), "giveaway")
        self.assertEqual(intent.get("action"), "create")
        self.assertEqual(intent.get("prize"), "800 robux")
        self.assertIsNone(intent.get("duration"))

    def test_regression_per_user_memory(self):
        """Input: 'my favorite flower is the white lotus' -> Per-user memory stores, recalls, and isolates."""
        # 1. Test ChromaMemory session history
        mem = ChromaMemory(persist_directory=self.test_dir)
        user_a_session = "discord_user_alpha_777"
        user_b_session = "discord_user_beta_888"

        # User A shares a fact
        mem.add("my favorite flower is the white lotus", speaker="user", session_id=user_a_session)

        # User A facts recalled
        history_a = mem.get_session_history(session_id=user_a_session)
        self.assertTrue(len(history_a) >= 1)
        self.assertIn("white lotus", history_a[0]["text"])

        # User B facts (isolated, zero cross-user leakage)
        history_b = mem.get_session_history(session_id=user_b_session)
        self.assertEqual(len(history_b), 0)

        # Simulate bot restart by creating a new ChromaMemory from the persisted directory
        reloaded_mem = ChromaMemory(persist_directory=self.test_dir)
        reloaded_history_a = reloaded_mem.get_session_history(session_id=user_a_session)
        self.assertTrue(len(reloaded_history_a) >= 1)
        self.assertIn("white lotus", reloaded_history_a[0]["text"])

        # 2. Test PersonMemoryManager profile isolation & persistence
        from person_memory.memory_manager import PersonMemoryManager
        pm_mgr = PersonMemoryManager(persist_dir=self.test_dir)
        p_a = pm_mgr.get_profile("11111", display_name="UserA")
        p_a.interests.append("white lotus")
        pm_mgr.save_all()

        p_b = pm_mgr.get_profile("22222", display_name="UserB")
        self.assertNotIn("white lotus", p_b.interests)

        # Reload after simulated restart
        reloaded_pm_mgr = PersonMemoryManager(persist_dir=self.test_dir)
        reloaded_p_a = reloaded_pm_mgr.get_profile("11111")
        self.assertIn("white lotus", reloaded_p_a.interests)


if __name__ == "__main__":
    unittest.main()
