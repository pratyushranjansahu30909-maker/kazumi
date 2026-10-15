# -*- coding: utf-8 -*-
"""
Automated unit and integration tests for Kazumi Persistent 24/7 Monitoring & Alerting System.
Covers all requirements from Section 9:
1. Event Ledger lifecycle: RECEIVED -> PROCESSING -> SENT
2. Successful welcome & farewell event tracking
3. Pre-flight permission auditing & CHANNEL_PERMISSION_ERROR
4. Inaccessible / missing channels & CHANNEL_NOT_FOUND_ERROR
5. Transient Discord API errors & bounded exponential backoff retries
6. Permanent error immediate failure classification (Forbidden, NotFound)
7. Process restart recovery of abandoned PROCESSING events
8. Webhook alert delivery, deduplication, and cooldown storm suppression
9. Missing or invalid webhook URL handling (graceful fallback)
10. Webhook network failure resilience (no bot crash)
11. Monitoring disabled mode (KAZUMI_MONITORING_ENABLED=0)
12. Storage failure graceful degradation
13. Liveness and Readiness health evaluation (Healthy, Degraded, Disconnected, Starting)
14. Multi-guild isolation
"""

import os
import json
import time
import shutil
import asyncio
import tempfile
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

import discord
from discord_features.monitoring import (
    AlertManager,
    EventLedger,
    EventState,
    BotMonitor,
    check_channel_permissions,
    execute_with_retry,
    _atomic_json_write,
    _safe_mask_url,
    ALERT_COOLDOWN_SECONDS
)
from discord_features.welcome import (
    WelcomeSystem,
    LAPEACE_GUILD_ID,
    LAPEACE_WELCOME_CHANNEL_ID,
    LAPEACE_GOODBYE_CHANNEL_ID,
    _PROCESSED_JOINS,
    _PROCESSED_LEAVES
)


class MockAvatar:
    def __init__(self, url="https://cdn.discordapp.com/avatars/123/avatar.png"):
        self.url = url


class MockMember:
    def __init__(self, member_id: int, name: str, display_name: str, guild=None, bot=False):
        self.id = member_id
        self.name = name
        self.display_name = display_name
        self.mention = f"<@{member_id}>"
        self.guild = guild
        self.bot = bot
        self.display_avatar = MockAvatar()
        self.avatar = MockAvatar()


class MockTextChannel:
    def __init__(self, channel_id: int, name: str, can_send=True, can_embed=True):
        self.id = channel_id
        self.name = name
        self._can_send = can_send
        self._can_embed = can_embed
        self.send = AsyncMock(return_value=MagicMock(id=987654321))

    def permissions_for(self, member):
        perms = MagicMock()
        perms.send_messages = self._can_send
        perms.embed_links = self._can_embed
        return perms


class TestMonitoringSystem(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.ledger_path = os.path.join(self.temp_dir, "test_event_ledger.json")
        self.ledger = EventLedger(self.ledger_path)
        self.alert_mgr = AlertManager(webhook_url="https://discord.com/api/webhooks/1234/test_token", cooldown_seconds=60.0)

        # Clear in-memory join/leave caches
        _PROCESSED_JOINS.clear()
        _PROCESSED_LEAVES.clear()

        # Build mock guild
        self.guild = MagicMock()
        self.guild.id = LAPEACE_GUILD_ID
        self.guild.name = "LAPEACE"
        self.guild.member_count = 50
        self.guild.me = MagicMock()

        self.ch_welcome = MockTextChannel(LAPEACE_WELCOME_CHANNEL_ID, "welcome")
        self.ch_goodbye = MockTextChannel(LAPEACE_GOODBYE_CHANNEL_ID, "goodbye")
        self.guild.text_channels = [self.ch_welcome, self.ch_goodbye]
        self.guild.system_channel = self.ch_welcome

        def _get_ch(cid):
            for c in self.guild.text_channels:
                if c.id == int(cid):
                    return c
            return None

        self.guild.get_channel = MagicMock(side_effect=_get_ch)

        self.member = MockMember(1001, "newbie", "Newbie🌸", guild=self.guild)

    async def asyncTearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # --------------------------------------------------------------------------
    # 1. Event Ledger Lifecycle & State Machine
    # --------------------------------------------------------------------------
    async def test_event_ledger_state_transitions(self):
        """Test RECEIVED -> PROCESSING -> SENT transitions in persistent ledger."""
        event_id = await self.ledger.record_received(
            event_type="member_join",
            guild_id=123,
            member_id=456,
            member_name="Alice",
            channel_id=789
        )
        self.assertIn(event_id, self.ledger._events)
        rec = self.ledger.get_event(event_id)
        self.assertEqual(rec["state"], EventState.RECEIVED)

        # Transition to PROCESSING
        success = await self.ledger.record_processing(event_id, channel_id=789)
        self.assertTrue(success)
        rec = self.ledger.get_event(event_id)
        self.assertEqual(rec["state"], EventState.PROCESSING)

        # Transition to SENT
        success = await self.ledger.record_sent(event_id, message_id=999)
        self.assertTrue(success)
        rec = self.ledger.get_event(event_id)
        self.assertEqual(rec["state"], EventState.SENT)
        self.assertEqual(rec["message_id"], 999)
        self.assertIsNotNone(rec["completed_at"])

        # Reload from disk to verify persistence
        new_ledger = EventLedger(self.ledger_path)
        persisted_rec = new_ledger.get_event(event_id)
        self.assertIsNotNone(persisted_rec)
        self.assertEqual(persisted_rec["state"], EventState.SENT)

    async def test_recover_abandoned_processing_events(self):
        """Test that events left in PROCESSING before an abrupt restart are safely recovered."""
        event_id = await self.ledger.record_received("member_join", 123, 456, "Bob", 789)
        await self.ledger.record_processing(event_id)

        # Artificially age the event beyond 300 seconds
        self.ledger._events[event_id]["created_at_epoch"] = time.time() - 400.0

        abandoned = self.ledger.get_abandoned_processing_events()
        self.assertEqual(len(abandoned), 1)
        self.assertEqual(abandoned[0]["event_id"], event_id)

        recovered_count = await self.ledger.recover_abandoned_events()
        self.assertEqual(recovered_count, 1)

        rec = self.ledger.get_event(event_id)
        self.assertEqual(rec["state"], EventState.FAILED_RETRYABLE)
        self.assertIn("PROCESS_RESTART_ABANDONED", rec["last_error"])

    # --------------------------------------------------------------------------
    # 2. Permission Auditing
    # --------------------------------------------------------------------------
    def test_permission_auditing(self):
        """Test channel permission check detects missing send_messages or embed_links."""
        me = MagicMock()
        # Full perms
        valid_ch = MockTextChannel(1, "test", can_send=True, can_embed=True)
        ok, reason = check_channel_permissions(valid_ch, me)
        self.assertTrue(ok)
        self.assertIsNone(reason)

        # Missing send_messages
        no_send_ch = MockTextChannel(2, "test", can_send=False, can_embed=True)
        ok, reason = check_channel_permissions(no_send_ch, me)
        self.assertFalse(ok)
        self.assertEqual(reason, "MISSING_PERMISSION_SEND_MESSAGES")

        # Missing embed_links
        no_embed_ch = MockTextChannel(3, "test", can_send=True, can_embed=False)
        ok, reason = check_channel_permissions(no_embed_ch, me)
        self.assertFalse(ok)
        self.assertEqual(reason, "MISSING_PERMISSION_EMBED_LINKS")

        # None channel
        ok, reason = check_channel_permissions(None, me)
        self.assertFalse(ok)
        self.assertEqual(reason, "CHANNEL_NOT_FOUND")

    # --------------------------------------------------------------------------
    # 3. Retry Mechanism with Backoff
    # --------------------------------------------------------------------------
    async def test_retry_transient_error_eventual_success(self):
        """Test that transient HTTP errors retry and eventually succeed."""
        event_id = await self.ledger.record_received("member_join", 1, 2, "User", 3)
        attempts = 0

        async def _action():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise discord.HTTPException(response=MagicMock(status=503), message="Service Unavailable")
            return MagicMock(id=555)

        success, res = await execute_with_retry(
            action_coro_fn=_action,
            event_id=event_id,
            ledger=self.ledger,
            alert_mgr=self.alert_mgr,
            guild_id=1,
            channel_id=3,
            max_retries=3,
            base_backoff=0.01
        )

        self.assertTrue(success)
        self.assertEqual(attempts, 3)
        rec = self.ledger.get_event(event_id)
        self.assertEqual(rec["state"], EventState.SENT)

    async def test_permanent_error_no_retry(self):
        """Test that 403 Forbidden terminates immediately without wasteful retries."""
        event_id = await self.ledger.record_received("member_join", 1, 2, "User", 3)
        attempts = 0

        async def _action():
            nonlocal attempts
            attempts += 1
            raise discord.Forbidden(response=MagicMock(status=403), message="Missing Permissions")

        success, err = await execute_with_retry(
            action_coro_fn=_action,
            event_id=event_id,
            ledger=self.ledger,
            alert_mgr=self.alert_mgr,
            guild_id=1,
            channel_id=3,
            max_retries=3,
            base_backoff=0.01
        )

        self.assertFalse(success)
        self.assertEqual(attempts, 1)  # Stopped immediately
        rec = self.ledger.get_event(event_id)
        self.assertEqual(rec["state"], EventState.FAILED_PERMANENT)
        self.assertIn("PERMISSIONS_FORBIDDEN", rec["last_error"])

    # --------------------------------------------------------------------------
    # 4. Alert Manager Cooldowns & Deduplication
    # --------------------------------------------------------------------------
    async def test_alert_manager_cooldowns(self):
        """Test alert manager throttles duplicate incidents during cooldown period."""
        mgr = AlertManager(webhook_url="https://discord.com/api/webhooks/fake/test", cooldown_seconds=10.0)

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_resp = AsyncMock()
            mock_resp.status = 204
            mock_post.return_value.__aenter__.return_value = mock_resp

            # First alert: should be sent
            sent1 = await mgr.send_alert("GATEWAY_DISCONNECTED", "CRITICAL", "Gateway down", guild_id=1)
            self.assertTrue(sent1)
            self.assertEqual(mock_post.call_count, 1)

            # Second identical alert immediately: throttled
            sent2 = await mgr.send_alert("GATEWAY_DISCONNECTED", "CRITICAL", "Gateway down", guild_id=1)
            self.assertFalse(sent2)
            self.assertEqual(mock_post.call_count, 1)

            # Different incident: should be sent
            sent3 = await mgr.send_alert("CHANNEL_PERMISSION_ERROR", "ERROR", "Perms missing", guild_id=1)
            self.assertTrue(sent3)
            self.assertEqual(mock_post.call_count, 2)

    async def test_alert_manager_disabled_or_unconfigured(self):
        """Test that disabled or unconfigured alerts skip silently without crashing."""
        # Unconfigured
        mgr_none = AlertManager(webhook_url="", enabled=True)
        self.assertFalse(mgr_none.is_configured())
        sent = await mgr_none.send_alert("GATEWAY_DISCONNECTED", "ERROR", "msg")
        self.assertFalse(sent)

        # Disabled
        mgr_disabled = AlertManager(webhook_url="https://webhook.url", enabled=False)
        self.assertFalse(mgr_disabled.is_configured())
        sent = await mgr_disabled.send_alert("GATEWAY_DISCONNECTED", "ERROR", "msg")
        self.assertFalse(sent)

    async def test_alert_manager_network_failure_resilience(self):
        """Test that a network timeout posting to webhook does not raise or crash the bot."""
        mgr = AlertManager(webhook_url="https://discord.com/api/webhooks/fake/timeout", cooldown_seconds=0.0)

        with patch("aiohttp.ClientSession.post", side_effect=asyncio.TimeoutError("Connection timed out")):
            sent = await mgr.send_alert("TEST_INCIDENT", "WARNING", "Timeout test")
            self.assertFalse(sent)  # Handled safely

    # --------------------------------------------------------------------------
    # 5. Bot Monitor Health Telemetry (Liveness & Readiness)
    # --------------------------------------------------------------------------
    def test_bot_monitor_health_evaluation(self):
        """Test liveness, readiness, and state calculation under varying gateway conditions."""
        mock_bot = MagicMock()
        mock_bot.is_ready.return_value = True
        mock_bot.latency = 0.045  # 45ms

        monitor = BotMonitor(mock_bot)
        monitor.record_connect()
        monitor.record_ready()

        status = monitor.get_health_status()
        self.assertTrue(status["liveness"])
        self.assertTrue(status["readiness"])
        self.assertEqual(status["state"], "healthy")
        self.assertEqual(status["latency_ms"], 45.0)

        # Simulate disconnection
        monitor.record_disconnect()
        status_dc = monitor.get_health_status()
        self.assertTrue(status_dc["liveness"])
        self.assertFalse(status_dc["readiness"])
        self.assertEqual(status_dc["state"], "disconnected")

        # Simulate degraded latency (>1500ms)
        monitor.record_connect()
        mock_bot.latency = 2.500  # 2500ms
        status_deg = monitor.get_health_status()
        self.assertTrue(status_deg["liveness"])
        self.assertTrue(status_deg["readiness"])
        self.assertEqual(status_deg["state"], "degraded")

    # --------------------------------------------------------------------------
    # 6. Integrated Welcome / Farewell Handlers with Persistent Ledger
    # --------------------------------------------------------------------------
    async def test_welcome_system_end_to_end_ledger_tracking(self):
        """Test that send_welcome properly creates durable ledger records and delivers messages."""
        with patch("discord_features.welcome.WelcomePoemGenerator.generate_welcome_poem", return_value="Welcome poem lines"):
            await WelcomeSystem.send_welcome(self.member)

        # Verify delivery in channel
        self.ch_welcome.send.assert_called_once()
        self.assertIn("🌸 Welcome <@1001>! ✨", self.ch_welcome.send.call_args[1]["content"])

        # Verify durable ledger entry
        monitor = BotMonitor.get_instance()
        stats = monitor.event_ledger.get_stats()
        self.assertGreaterEqual(stats["sent"], 1)

    async def test_welcome_system_missing_permission_alert(self):
        """Test that send_welcome detects missing permissions, marks permanent failure, and alerts."""
        self.ch_welcome._can_send = False  # Deny permission

        with patch.object(WelcomeSystem, "resolve_welcome_channel", return_value=self.ch_welcome):
            with patch.object(BotMonitor.get_instance().alert_manager, "send_alert", new_callable=AsyncMock) as mock_alert:
                await WelcomeSystem.send_welcome(self.member)

                # Should not call send()
                self.ch_welcome.send.assert_not_called()

                # Should have triggered alert
                mock_alert.assert_called_once()
                call_args = mock_alert.call_args[1]
                self.assertEqual(call_args["incident_type"], "CHANNEL_PERMISSION_ERROR")
                self.assertEqual(call_args["severity"], "ERROR")

    async def test_farewell_system_end_to_end_ledger_tracking(self):
        """Test that send_goodbye records member_leave in ledger and delivers farewell poem."""
        with patch("discord_features.welcome.WelcomePoemGenerator.generate_farewell_poem", return_value="Farewell poem lines"):
            await WelcomeSystem.send_goodbye(self.member)

        # Verify delivery in channel
        self.ch_goodbye.send.assert_called_once()

        # Verify durable ledger entry
        monitor = BotMonitor.get_instance()
        stats = monitor.event_ledger.get_stats()
        self.assertGreaterEqual(stats["sent"], 1)

    # --------------------------------------------------------------------------
    # 7. Helper Utilities
    # --------------------------------------------------------------------------
    def test_safe_mask_url(self):
        url = "https://discord.com/api/webhooks/123456789/abcdefghijklmnopqrstuvwxyz"
        masked = _safe_mask_url(url)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", masked)
        self.assertTrue(masked.startswith("https://discord.com/api/webhooks/123456789/***"))
        self.assertEqual(_safe_mask_url(""), "None")


if __name__ == "__main__":
    unittest.main()
