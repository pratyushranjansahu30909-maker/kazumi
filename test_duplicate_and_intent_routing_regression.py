# -*- coding: utf-8 -*-
"""
🌸 Kazumi Regression Test Suite — Duplicate Replies, Intent Routing & New Powers
Verifies all 16 Phase 6 regression requirements:
 1. One mention generates exactly one response
 2. Same message delivered twice to internal dispatcher does not produce duplicate output
 3. Multiple registered handlers cannot independently send competing normal replies
 4. Normal conversational message receives one relevant response
 5. Giveaway request is classified as an action, not generic affection
 6. 'gw' and 'giveaway' are both recognized
 7. Amount '800 Robux' is extracted without being mistaken for duration or winner count
 8. Missing giveaway fields trigger clarification
 9. Unauthorized giveaway requests do not execute
 10. Successful mocked giveaway creation produces one accurate confirmation
 11. Failed action does not produce a false success confirmation
 12. Conversation follow-ups such as 'yeah', 'ok', and 'wait' continue to work
 13. Capability queries describe real implementations
 14. Memory and relationship state remain isolated per user
 15. Bot-authored messages do not trigger response loops
 16. Existing modules and components integrate correctly
"""

import os
import sys
import time
import shutil
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from discord_features.database import FeatureDatabase
from discord_features.intent_router import NaturalIntentRouter
from discord_features.action_engine import AutonomousActionEngine, ActionRisk
from discord_features.channel_policy import ChannelPolicyManager, ChannelPolicyType
from person_memory.memory_manager import PersonMemoryManager
from person_memory.relationship_manager import RelationshipManager

import discord_bot


class DuplicateAndIntentRoutingRegressionTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(__file__), "test_reg_storage_tmp")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        os.makedirs(self.test_dir, exist_ok=True)

        self.db = FeatureDatabase(persist_dir=self.test_dir)
        self.mem_mgr = PersonMemoryManager(persist_dir=self.test_dir)
        self.rel_mgr = RelationshipManager()
        mock_bot_user = MagicMock(spec=discord.User)
        mock_bot_user.id = 999000
        mock_bot_user.name = "Kazumi"
        mock_bot_user.bot = True
        discord_bot.bot._user = mock_bot_user
        discord_bot.bot._connection.user = mock_bot_user

        self.mock_giveaways = MagicMock()
        self.mock_giveaways.audit_ledger = MagicMock()
        self.intent_router = NaturalIntentRouter(bot=discord_bot.bot, features_dict={"db": self.db, "giveaways": self.mock_giveaways})
        self.action_engine = AutonomousActionEngine(bot=discord_bot.bot, features={"db": self.db, "giveaways": self.mock_giveaways})

        # Clear dedup caches and rapid typing for clean test isolation
        discord_bot._processed_message_ids_set.clear()
        discord_bot._processed_message_ids_deque.clear()
        discord_bot.active_conversations.clear()
        discord_bot.user_rapid_typing.clear()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_mock_message(self, content: str, author_id: int = 12345, channel_name: str = "kazumi-chat", msg_id: int = 50001, is_bot: bool = False, has_perms: bool = False):
        mock_msg = MagicMock(spec=discord.Message)
        mock_msg.id = msg_id
        mock_msg.content = content
        mock_msg.author = MagicMock(spec=discord.Member)
        mock_msg.author.id = author_id
        mock_msg.author.bot = is_bot
        mock_msg.author.name = "TestUser"
        mock_msg.author.display_name = "TestUser"

        # Permissions
        perms = MagicMock()
        perms.administrator = has_perms
        perms.manage_guild = has_perms
        perms.manage_messages = has_perms
        perms.moderate_members = has_perms
        perms.kick_members = has_perms
        perms.ban_members = has_perms
        mock_msg.author.guild_permissions = perms

        class MockTyping:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass

        mock_msg.channel = MagicMock(spec=discord.TextChannel)
        mock_msg.channel.id = 88888
        mock_msg.channel.name = channel_name
        mock_msg.channel.send = AsyncMock()
        mock_msg.channel.typing = MagicMock(return_value=MockTyping())
        mock_msg.reply = AsyncMock()
        mock_msg.add_reaction = AsyncMock()

        mock_msg.guild = MagicMock(spec=discord.Guild)
        mock_msg.guild.id = 77777
        mock_msg.guild.name = "TestGuild"
        mock_msg.guild.me = MagicMock()
        mock_msg.guild.me.roles = []
        mock_msg.guild.me.guild_permissions = perms
        mock_msg.guild.get_channel = MagicMock(return_value=mock_msg.channel)

        mock_msg.mentions = [discord_bot.bot.user] if discord_bot.bot.user else []
        mock_msg.role_mentions = []
        mock_msg.reference = None
        mock_msg.attachments = []
        mock_msg.stickers = []
        return mock_msg

    # 1. One mention generates exactly one response
    async def test_01_one_mention_generates_exactly_one_response(self):
        msg = self._create_mock_message("@Kazumi u mad?", msg_id=1001)
        with patch("discord_bot.ask_kazumi", return_value="Not at all! 🌸 I'm feeling great!"):
            await discord_bot.on_message(msg)

        total_replies = msg.reply.call_count + msg.channel.send.call_count
        self.assertEqual(total_replies, 1, f"Expected exactly 1 reply, got {total_replies}")

    # 2. Same message delivered twice does not produce duplicate output
    async def test_02_duplicate_message_delivery_prevented(self):
        msg = self._create_mock_message("@Kazumi hey", msg_id=1002)
        with patch("discord_bot.ask_kazumi", return_value="Hello there! ✨"):
            await discord_bot.on_message(msg)
            # Second delivery of same message ID
            await discord_bot.on_message(msg)

        total_replies = msg.reply.call_count + msg.channel.send.call_count
        self.assertEqual(total_replies, 1, f"Duplicate message delivery produced {total_replies} replies instead of 1")

    # 3. Multiple registered handlers cannot independently send competing replies
    async def test_03_competing_handlers_do_not_double_reply(self):
        # A giveaway message in kazumi-chat
        msg = self._create_mock_message("@Kazumi host a gw for 800 robux", msg_id=1003, has_perms=True)
        with patch("discord_bot.ask_kazumi", return_value="Generic affection fallback"):
            await discord_bot.on_message(msg)

        # Should only be answered by the action/intent router, NOT also by ask_kazumi fallback
        total_replies = msg.reply.call_count + msg.channel.send.call_count
        self.assertEqual(total_replies, 1, f"Competing handlers sent {total_replies} replies")
        first_reply = msg.reply.call_args[0][0] if msg.reply.call_args else msg.channel.send.call_args[0][0]
        self.assertIn("800 robux", first_reply.lower())
        self.assertNotIn("affection", first_reply.lower())

    # 4. Normal conversational message receives one relevant response
    async def test_04_normal_conversational_message_receives_one_response(self):
        msg = self._create_mock_message("@Kazumi how are you doing today?", msg_id=1004)
        with patch("discord_bot.ask_kazumi", return_value="I am feeling wonderful, thank you for asking! 🌸"):
            await discord_bot.on_message(msg)

        total_replies = msg.reply.call_count + msg.channel.send.call_count
        self.assertEqual(total_replies, 1)

    # 5. Giveaway request is classified as action, not generic affection
    def test_05_giveaway_intent_classification(self):
        msg = self._create_mock_message("host a gw for 800 robux")
        intent = self.intent_router.detect_intent("host a gw for 800 robux", msg)
        self.assertIsNotNone(intent)
        self.assertEqual(intent.get("category"), "giveaway")
        self.assertEqual(intent.get("action"), "create")

    # 6. 'gw' and 'giveaway' are both recognized
    def test_06_gw_and_giveaway_abbreviations(self):
        msg = self._create_mock_message("dummy")
        # Test 'gw'
        intent_gw = self.intent_router.detect_intent("host a gw for 800 robux", msg)
        self.assertIsNotNone(intent_gw)
        self.assertEqual(intent_gw.get("category"), "giveaway")

        # Test 'giveaway'
        intent_ga = self.intent_router.detect_intent("start a giveaway for Nitro", msg)
        self.assertIsNotNone(intent_ga)
        self.assertEqual(intent_ga.get("category"), "giveaway")

    # 7. Amount '800 Robux' is extracted without being mistaken for duration or winner count
    def test_07_prize_amount_extraction(self):
        msg = self._create_mock_message("dummy")
        intent = self.intent_router.detect_intent("host a gw for 800 robux", msg)
        self.assertIsNotNone(intent)
        prize = intent.get("prize")
        self.assertIn("800 robux", prize.lower())
        self.assertIsNone(intent.get("duration"))
        self.assertEqual(intent.get("winners", 1), 1)

    # 8. Missing giveaway fields trigger clarification
    async def test_08_missing_giveaway_fields_trigger_clarification(self):
        msg = self._create_mock_message("host a gw for 800 robux", has_perms=True)
        intent = self.intent_router.detect_intent("host a gw for 800 robux", msg)
        handled, reply_text, reply_embed = await self.intent_router.execute_intent(intent, msg)
        self.assertTrue(handled)
        self.assertIn("how long should it run", reply_text.lower())
        self.assertIn("800 robux", reply_text.lower())

    # 9. Unauthorized giveaway requests do not execute
    async def test_09_unauthorized_giveaway_request_denied(self):
        # User lacks manage_guild
        msg = self._create_mock_message("host a gw for 800 robux in 1h", has_perms=False)
        intent = self.intent_router.detect_intent("host a gw for 800 robux in 1h", msg)
        handled, reply_text, reply_embed = await self.intent_router.execute_intent(intent, msg)
        self.assertTrue(handled)
        self.assertIn("manage guild", reply_text.lower())

    # 10. Successful mocked giveaway creation produces one accurate confirmation
    async def test_10_successful_giveaway_creation(self):
        msg = self._create_mock_message("host a gw for 800 robux for 10m", has_perms=True)
        msg.channel.send = AsyncMock(return_value=MagicMock(id=999888))
        intent = self.intent_router.detect_intent("host a gw for 800 robux for 10m", msg)
        handled, reply_text, reply_embed = await self.intent_router.execute_intent(intent, msg)
        self.assertTrue(handled)
        self.assertIn("created successfully", reply_text.lower())
        self.assertIn("800 robux", reply_text.lower())

    # 11. Failed action does not produce false success confirmation
    async def test_11_failed_action_reports_failure(self):
        msg = self._create_mock_message("mod timeout 999999 for 60s", has_perms=False)
        res = await self.action_engine.execute_action("mod_timeout", {"target_id": 999999, "duration_seconds": 60}, msg)
        self.assertFalse(res.success)
        self.assertIn("permission denied", res.error.lower())

    # 12. Conversation follow-ups such as 'yeah', 'ok', and 'wait' continue to work
    async def test_12_conversation_followup_continuity(self):
        # Start a conversation session
        msg1 = self._create_mock_message("@Kazumi hey", author_id=22222, msg_id=2001)
        with patch("discord_bot.ask_kazumi", return_value="Hey! What are you working on today? 🌸"):
            await discord_bot.on_message(msg1)

        self.assertIn((msg1.channel.id, 22222), discord_bot.active_conversations)

        # Follow up with 'yeah'
        msg2 = self._create_mock_message("yeah", author_id=22222, msg_id=2002)
        with patch("discord_bot.ask_kazumi", return_value="Tell me more about it! ✨"):
            await discord_bot.on_message(msg2)
            self.assertEqual(msg2.reply.call_count, 1)

        # Follow up with 'wait'
        msg3 = self._create_mock_message("wait", author_id=22222, msg_id=2003)
        with patch("discord_bot.ask_kazumi", return_value="Take your time, I'm listening! 🌸"):
            await discord_bot.on_message(msg3)
            self.assertEqual(msg3.reply.call_count, 1)

    # 13. Capability queries describe real implementations
    async def test_13_capability_queries_describe_real_powers(self):
        msg = self._create_mock_message("what powers do you have?")
        intent = self.intent_router.detect_intent("what powers do you have?", msg)
        self.assertEqual(intent.get("category"), "capability")
        self.assertEqual(intent.get("action"), "list_capabilities")
        handled, reply_text, reply_embed = await self.intent_router.execute_intent(intent, msg)
        self.assertTrue(handled)
        self.assertIsNotNone(reply_embed)
        embed_dict = reply_embed.to_dict()
        self.assertIn("Powers", embed_dict["title"])
        # Verify real powers are mentioned in description
        desc = embed_dict.get("description", "")
        self.assertIn("Giveaways", desc)
        self.assertIn("Music", desc)
        self.assertIn("Mini-Games", desc)

    # 14. Memory and relationship state remain isolated per user
    def test_14_user_memory_isolation(self):
        user_a = "10001"
        user_b = "10002"

        prof_a = self.mem_mgr.get_profile(user_a)
        prof_b = self.mem_mgr.get_profile(user_b)

        prof_a.affection_level = 25
        prof_b.affection_level = 5
        self.mem_mgr.save_profile(prof_a)
        self.mem_mgr.save_profile(prof_b)

        reloaded_a = self.mem_mgr.get_profile(user_a)
        reloaded_b = self.mem_mgr.get_profile(user_b)

        self.assertEqual(reloaded_a.affection_level, 25)
        self.assertEqual(reloaded_b.affection_level, 5)
        self.assertNotEqual(reloaded_a.affection_level, reloaded_b.affection_level)

    # 15. Bot-authored messages do not trigger response loops
    async def test_15_bot_authored_messages_ignored(self):
        msg = self._create_mock_message("@Kazumi are you there?", msg_id=3001, is_bot=True)
        await discord_bot.on_message(msg)
        self.assertEqual(msg.reply.call_count, 0)
        self.assertEqual(msg.channel.send.call_count, 0)

    # 16. Existing channel policies & redirect for bare mention
    async def test_16_bare_mention_redirects_in_observation_channel(self):
        # Bare mention in observation channel (e.g. general) -> triggers polite redirect
        msg = self._create_mock_message("<@999000>", msg_id=4001, channel_name="general")
        await discord_bot.on_message(msg)
        # Exactly one redirect reply
        self.assertEqual(msg.reply.call_count, 1)
        reply_content = msg.reply.call_args[0][0]
        self.assertIn("come find me in", reply_content)


if __name__ == "__main__":
    unittest.main()
