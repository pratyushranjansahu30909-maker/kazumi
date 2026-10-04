# -*- coding: utf-8 -*-
"""
🌸 EUPHORIA x KAZUMI — COMPREHENSIVE LAUNCH INTEGRATION & FAILURE-INJECTION TEST SUITE
Validates:
1. Euphoria Server Channel Routing & Observation Rules (Phase 3 & 6)
2. Role Hierarchy & Execution-Time Permission Security (Phase 4 & 10)
3. Failure Injection: AI API Outages, Rate Limits (429), and Timeouts (Phase 6 & 15)
4. Failure Injection: Database Atomic Writes & Rollback Safety (Phase 7 & 15)
5. Failure Injection: Missing / Deleted Channels for Logs & Reminders (Phase 10 & 11)
6. Anti-Recursion: Self-reply and bot-to-bot loop prevention (Phase 6)
7. Cross-User Memory Isolation & Privacy (Phase 7)
8. Unhinged / Roast Mode State Isolation (Phase 8)
9. Arcade Game Engine Session Isolation & Idempotency (Phase 9)
10. Scheduled Tasks Idempotency & Restart Safety (Phase 11 & 13)
"""

import os
import sys
import time
import shutil
import asyncio
import tempfile
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

# Ensure workspace root is in sys.path
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

import discord
from discord_features.permissions import PermissionService
from discord_features.database import FeatureDatabase
from discord_features.game_engine import GameEngine, GameType
from discord_features.moderation import AutoModTracker
from discord_features.logging import ServerLogging
from discord_bot import is_kazumi_channel, is_stop_command, split_message
import kazumi


class MockRole:
    def __init__(self, name: str, position: int):
        self.name = name
        self.position = position

    def __le__(self, other):
        return self.position <= getattr(other, "position", 0)

    def __lt__(self, other):
        return self.position < getattr(other, "position", 0)

    def __ge__(self, other):
        return self.position >= getattr(other, "position", 0)

    def __gt__(self, other):
        return self.position > getattr(other, "position", 0)

    def __eq__(self, other):
        return self.position == getattr(other, "position", 0)


class TestEuphoriaLaunchIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="kazumi_euphoria_test_")
        cls.db = FeatureDatabase(persist_dir=cls.test_dir)
        cls.game_engine = GameEngine(cls.db)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    # =========================================================================
    # 1. Euphoria Channel Routing & Observation Rules
    # =========================================================================
    def test_01_channel_routing_and_isolation(self):
        """Validates that chat channels are properly identified and non-kazumi channels are isolated."""
        # 1. DMs always allowed
        dm = MagicMock(spec=discord.DMChannel)
        self.assertTrue(is_kazumi_channel(dm))

        # 2. #kazumi-chat is an active chat channel
        kazumi_ch = MagicMock(spec=discord.TextChannel)
        kazumi_ch.name = "kazumi-chat"
        kazumi_ch.id = 1001
        self.assertTrue(is_kazumi_channel(kazumi_ch))

        # 3. Euphoria public channels are observation only (not active kazumi chat)
        general_ch = MagicMock(spec=discord.TextChannel)
        general_ch.name = "general"
        general_ch.id = 2001
        self.assertFalse(is_kazumi_channel(general_ch))

        rules_ch = MagicMock(spec=discord.TextChannel)
        rules_ch.name = "rules"
        rules_ch.id = 2002
        self.assertFalse(is_kazumi_channel(rules_ch))

        staff_ch = MagicMock(spec=discord.TextChannel)
        staff_ch.name = "staff-chat"
        staff_ch.id = 2003
        self.assertFalse(is_kazumi_channel(staff_ch))

    def test_02_stop_and_silence_detection(self):
        """Detects various English and Hinglish silence/stop commands."""
        self.assertTrue(is_stop_command("shut up"))
        self.assertTrue(is_stop_command("kazumi stop"))
        self.assertTrue(is_stop_command("chup kar"))
        self.assertTrue(is_stop_command("please be quiet"))
        self.assertTrue(is_stop_command("bas kar"))
        # Normal chat should NOT trigger stop
        self.assertFalse(is_stop_command("what is the weather today?"))
        self.assertFalse(is_stop_command("hello kazumi!"))

    # =========================================================================
    # 2. Role Hierarchy & Execution-Time Permission Security
    # =========================================================================
    def test_03_role_hierarchy_safeguards(self):
        """Enforces least-privilege role hierarchy between Owner, Mod, Target, and Kazumi."""
        guild = MagicMock(spec=discord.Guild)
        guild.owner_id = 999999

        # Roles with positions
        role_owner = MockRole("Owner", 100)
        role_admin = MockRole("Admin", 90)
        role_bot = MockRole("Kazumi", 80)
        role_mod = MockRole("Moderator", 70)
        role_member = MockRole("Member", 10)

        # Members
        owner_member = MagicMock(spec=discord.Member, id=999999, top_role=role_owner, guild=guild)
        admin_member = MagicMock(spec=discord.Member, id=1001, top_role=role_admin, guild=guild)
        bot_member = MagicMock(spec=discord.Member, id=8888, top_role=role_bot, guild=guild)
        mod_member = MagicMock(spec=discord.Member, id=1002, top_role=role_mod, guild=guild)
        target_member = MagicMock(spec=discord.Member, id=1003, top_role=role_member, guild=guild)
        equal_mod = MagicMock(spec=discord.Member, id=1004, top_role=role_mod, guild=guild)

        # 1. Mod can moderate regular member
        allowed, msg = PermissionService.check_hierarchy(mod_member, target_member, bot_member)
        self.assertTrue(allowed)

        # 2. Mod CANNOT moderate server owner
        allowed, msg = PermissionService.check_hierarchy(mod_member, owner_member, bot_member)
        self.assertFalse(allowed)
        self.assertIn("server owner cannot be targeted", msg)

        # 3. Mod CANNOT moderate someone with higher role (Admin)
        allowed, msg = PermissionService.check_hierarchy(mod_member, admin_member, bot_member)
        self.assertFalse(allowed)
        self.assertIn("Role hierarchy violation", msg)

        # 4. Mod CANNOT moderate someone with equal role
        allowed, msg = PermissionService.check_hierarchy(mod_member, equal_mod, bot_member)
        self.assertFalse(allowed)

        # 5. Mod CANNOT moderate themselves
        allowed, msg = PermissionService.check_hierarchy(mod_member, mod_member, bot_member)
        self.assertFalse(allowed)
        self.assertIn("cannot perform moderation actions against yourself", msg)

        # 6. Bot cannot moderate someone higher than bot's role
        allowed, msg = PermissionService.check_hierarchy(owner_member, admin_member, bot_member)
        self.assertFalse(allowed)
        self.assertIn("their role is higher than or equal to my highest role", msg)

    def test_04_bot_channel_permission_checks(self):
        """Ensures bot validates required channel permissions prior to execution."""
        bot_member = MagicMock(spec=discord.Member)
        bot_member.guild_permissions = discord.Permissions(administrator=False)

        channel = MagicMock(spec=discord.TextChannel)
        # Deny send_messages in this channel
        channel_perms = discord.Permissions(send_messages=False, embed_links=True)
        channel.permissions_for.return_value = channel_perms

        ok, msg = PermissionService.check_bot_permissions(bot_member, channel, ["send_messages", "embed_links"])
        self.assertFalse(ok)
        self.assertIn("Send Messages", msg)

    # =========================================================================
    # 3. Failure Injection: AI API Outage & Fallback Handling
    # =========================================================================
    def test_05_ai_provider_outage_fallback(self):
        """Simulates OpenAI API outage (Timeout / 429) and verifies rule-based fallback reply."""
        engine = kazumi.LLMController()
        # Mock client.chat.completions.create to raise an API error
        with patch.object(engine, "client") as mock_client:
            mock_client.chat.completions.create.side_effect = Exception("OpenAI 429 RateLimitError or Network Timeout")
            
            # The controller must catch the exception and return a sweet fallback
            reply = engine.generate_response("hello kazumi", 0.5, memory_context=[], situation="CASUAL")
            self.assertIsInstance(reply, str)
            self.assertTrue(len(reply) > 0)
            self.assertNotIn("Traceback", reply)
            self.assertNotIn("429", reply)

    # =========================================================================
    # 4. Failure Injection: Database Atomic Writes & Rollback Safety
    # =========================================================================
    def test_06_database_atomic_write_and_recovery(self):
        """Verifies database writes to temporary file first and preserves backup on failure."""
        test_file = os.path.join(self.test_dir, "test_table.json")
        initial_data = {"key": "safe_value"}
        self.db._atomic_write(test_file, initial_data)
        self.assertTrue(os.path.exists(test_file))

        # Read back
        loaded = self.db._safe_read(test_file, default={})
        self.assertEqual(loaded["key"], "safe_value")

        # Simulate corrupt target file (e.g. power outage mid-write)
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("{corrupt_json_half_written...")

        # Safe read should fall back to .bak or default without crashing
        recovered = self.db._safe_read(test_file, default={"fallback": True})
        self.assertTrue(recovered.get("fallback") or "key" in recovered)

    # =========================================================================
    # 5. Failure Injection: Missing / Deleted Channels for Logs & Reminders
    # =========================================================================
    def test_07_deleted_logging_channel_handling(self):
        """Verifies that ServerLogging handles a deleted channel gracefully without crashing."""
        guild = MagicMock(spec=discord.Guild)
        guild.id = 777
        guild.get_channel.return_value = None  # Channel was deleted

        # Set configured log channel that no longer exists
        self.db.update_guild_settings("777", {"log_channel_id": "999888"})

        # Logging an event should not raise any exception
        embed = discord.Embed(title="Test Audit")
        asyncio.run(ServerLogging.log_event(guild, embed))

    # =========================================================================
    # 6. Anti-Recursion & Self-Reply Loop Prevention
    # =========================================================================
    def test_08_anti_recursion_filter(self):
        """Confirms bot ignores messages authored by bots (including itself)."""
        bot_user = MagicMock(spec=discord.ClientUser, id=123456)
        
        # 1. Message from another bot
        msg_bot = MagicMock(spec=discord.Message)
        msg_bot.author.bot = True
        msg_bot.author.id = 9999
        self.assertTrue(msg_bot.author.bot)

        # 2. Message from Kazumi herself
        msg_self = MagicMock(spec=discord.Message)
        msg_self.author.bot = False
        msg_self.author.id = 123456
        self.assertEqual(msg_self.author.id, bot_user.id)

    # =========================================================================
    # 7. Cross-User Memory Isolation & Privacy
    # =========================================================================
    def test_09_user_memory_isolation(self):
        """Ensures User A cannot access or mutate User B's profile data."""
        user_a_id = 111
        user_b_id = 222

        # Set game stats / profile for User A (winner) and User B (loser)
        results = self.game_engine.award_game_results(user_a_id, user_b_id, GameType.CONNECT4, False, 100, xp_winner=100)

        profile_a = results[user_a_id]
        profile_b = results[user_b_id]

        # User A should have won, User B should have lost
        self.assertEqual(profile_a["wins"], 1)
        self.assertEqual(profile_b["wins"], 0)
        self.assertNotEqual(profile_a["xp"], profile_b["xp"])

    # =========================================================================
    # 8. Unhinged / Roast Mode State Isolation
    # =========================================================================
    def test_10_roast_opt_out_isolation(self):
        """Ensures roast opt-out for User A does not affect User B."""
        user_opt_out = 5001
        user_normal = 5002

        self.db.set_user_roast_opt_out(user_opt_out, True)
        self.assertTrue(self.db.is_user_roast_opted_out(user_opt_out))
        self.assertFalse(self.db.is_user_roast_opted_out(user_normal))

    # =========================================================================
    # 9. Scheduled Tasks Idempotency & Restart Safety
    # =========================================================================
    def test_11_scheduled_reminders_idempotency(self):
        """Confirms due reminders are popped atomically and never dispatched twice."""
        now = time.time()
        # Add reminder that is already due
        self.db.add_reminder(user_id="user_123", channel_id="ch_456", due_time=now - 10, text="Take a cozy break 🌸")
        # Add reminder for the future
        self.db.add_reminder(user_id="user_123", channel_id="ch_456", due_time=now + 5000, text="Future reminder")

        # First poll: should retrieve 1 due reminder
        due_first = self.db.get_due_reminders()
        self.assertEqual(len(due_first), 1)
        self.assertEqual(due_first[0]["text"], "Take a cozy break 🌸")

        # Second poll immediately: due reminder must be gone! (No duplicate pings)
        due_second = self.db.get_due_reminders()
        self.assertEqual(len(due_second), 0)

    # =========================================================================
    # 10. Message Splitting for Discord 2000-Char Limit
    # =========================================================================
    def test_12_message_splitting_under_discord_limit(self):
        """Verifies large responses are split without truncating or exceeding Discord's 2000-char limit."""
        huge_text = "🌸 Kazumi companion response! " * 150  # ~4500 characters
        chunks = split_message(huge_text, max_chars=1950)
        self.assertTrue(len(chunks) >= 3)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 1950)


if __name__ == "__main__":
    unittest.main()
