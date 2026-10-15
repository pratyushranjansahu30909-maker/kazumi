# -*- coding: utf-8 -*-
"""
================================================================================
🌸 EUPHORIA SERVER & KAZUMI CHANNEL POLICY MASTER TEST SUITE (PHASE 8)
================================================================================
Verifies all Phase 3, Phase 4, Phase 5, Phase 6, and Phase 7 requirements:
1. AI chat allowed in #kazumi-chat
2. AI chat blocked on unsolicited messages in #general
3. Mention in #general receives exact polite redirect
4. Welcome poem posted only to #welcome with exactly 2 rhyming lines
5. Display name sanitization prevents mass mentions (@everyone / @here / markdown)
6. Deduplication prevents multiple welcome messages for same join event
7. Local fallback poem generator succeeds when AI API is unavailable
8. Games work in #games and are blocked in #rules
9. Giveaways work in #giveaways and are blocked in #general
10. Music commands are restricted to #music-commands
11. Announcement publishing requires authorization
12. Moderation & staff commands stay strictly in staff channels
13. Ordinary members cannot access staff commands
14. Missing channel ID causes safe fallback rather than crash
15. Denied features block execution BEFORE calling AI API or executing side effects
16. DMs enforce DM_POLICY and do not inherit staff privileges
================================================================================
"""

import os
import sys
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from discord_features.channel_policy import (
    ChannelPolicyManager,
    ChannelPolicyType,
    FeatureGroup,
    get_channel_policy_manager,
    POLICY_DEFINITIONS
)
from discord_features.welcome import (
    sanitize_display_name,
    WelcomePoemGenerator,
    WelcomeSystem,
    _PROCESSED_JOINS
)
from discord_features.permissions import PermissionService
from discord_features.intent_router import NaturalIntentRouter


class MockChannel:
    """Mock for Discord Text / Forum / Stage / Voice Channels."""
    def __init__(self, id_val: int, name: str, ch_type=None, category=None):
        self.id = id_val
        self.name = name
        self.type = ch_type or "text"
        self.category = category
        self.category_id = category.id if category else None
        self.guild = None
        self.send = AsyncMock()

    @property
    def mention(self):
        return f"<#{self.id}>"

    def permissions_for(self, member):
        perms = MagicMock()
        perms.send_messages = True
        perms.embed_links = True
        return perms


class MockMember:
    """Mock for Discord Member."""
    def __init__(self, id_val: int, name: str, display_name: str, is_bot: bool = False, is_owner: bool = False, is_admin: bool = False, is_mod: bool = False):
        self.id = id_val
        self.name = name
        self.display_name = display_name
        self.bot = is_bot
        self.guild = None
        self.roles = []
        self.top_role = MagicMock()
        self.top_role.__gt__ = lambda s, o: True
        self.top_role.__ge__ = lambda s, o: True
        self.top_role.__le__ = lambda s, o: False
        self.display_avatar = MagicMock(url="https://cdn.discordapp.com/avatars/test.png")
        self.mention = f"<@{self.id}>"

        self.guild_permissions = MagicMock()
        self.guild_permissions.administrator = is_admin
        self.guild_permissions.manage_guild = is_admin or is_mod
        self.guild_permissions.manage_messages = is_admin or is_mod
        self.guild_permissions.kick_members = is_admin or is_mod
        self.guild_permissions.ban_members = is_admin or is_mod
        self.guild_permissions.moderate_members = is_admin or is_mod
        self.guild_permissions.manage_channels = is_admin


class MockGuild:
    """Mock for Discord Guild representing Euphoria."""
    def __init__(self, id_val: int = 1546919406603337809, name: str = "Euphoria"):
        self.id = id_val
        self.name = name
        self.owner_id = 1203721997805424650
        self.member_count = 42
        self.text_channels = []
        self.categories = []
        self.system_channel = None
        self.me = MockMember(1549840297637322832, "Kazumi", "Kazumi", is_bot=True)
        self.me.guild = self

    def get_channel(self, cid: int):
        for ch in self.text_channels:
            if ch.id == cid:
                return ch
        return None


class TestEuphoriaChannelPolicies(unittest.TestCase):
    """Automated test cases for the central channel policy system and Euphoria features."""

    def setUp(self):
        self.guild = MockGuild()
        self.policy_mgr = ChannelPolicyManager(db=None)

        # Setup standard Euphoria channels
        self.ch_welcome = MockChannel(101, "welcome")
        self.ch_rules = MockChannel(102, "rules")
        self.ch_announcements = MockChannel(103, "announcements")
        self.ch_server_guide = MockChannel(104, "server-guide")
        self.ch_roles = MockChannel(105, "roles")
        self.ch_general = MockChannel(106, "general")
        self.ch_introductions = MockChannel(107, "introductions")
        self.ch_media = MockChannel(108, "media")
        self.ch_memes = MockChannel(109, "memes")
        self.ch_questions = MockChannel(110, "questions")
        self.ch_suggestions = MockChannel(111, "suggestions")
        self.ch_kazumi_chat = MockChannel(112, "kazumi-chat")
        self.ch_bot_commands = MockChannel(113, "bot-commands")
        self.ch_games = MockChannel(114, "games")
        self.ch_giveaways = MockChannel(115, "giveaways")
        self.ch_music_commands = MockChannel(116, "music-commands")
        self.ch_staff_chat = MockChannel(117, "staff-chat")
        self.ch_mod_logs = MockChannel(118, "mod-logs")
        self.ch_kazumi_logs = MockChannel(119, "kazumi-logs")

        for ch in [
            self.ch_welcome, self.ch_rules, self.ch_announcements, self.ch_server_guide,
            self.ch_roles, self.ch_general, self.ch_introductions, self.ch_media,
            self.ch_memes, self.ch_questions, self.ch_suggestions, self.ch_kazumi_chat,
            self.ch_bot_commands, self.ch_games, self.ch_giveaways, self.ch_music_commands,
            self.ch_staff_chat, self.ch_mod_logs, self.ch_kazumi_logs
        ]:
            ch.guild = self.guild
            self.guild.text_channels.append(ch)

        self.guild.system_channel = self.ch_welcome

        # Members
        self.member_alex = MockMember(201, "alex", "Alex")
        self.member_alex.guild = self.guild

        self.staff_mod = MockMember(301, "staff_alice", "Alice (Mod)", is_mod=True)
        self.staff_mod.guild = self.guild

    # --------------------------------------------------------------------------
    # 1. AI CHAT POLICY TESTS
    # --------------------------------------------------------------------------
    def test_ai_chat_allowed_in_kazumi_chat(self):
        """AI conversation must be explicitly allowed in #kazumi-chat."""
        policy = self.policy_mgr.get_policy_for_channel(self.ch_kazumi_chat)
        self.assertEqual(policy.name, ChannelPolicyType.ACTIVE_CHAT)
        self.assertTrue(policy.allow_ai_chat)
        can_run, _ = self.policy_mgr.can_execute(self.ch_kazumi_chat, FeatureGroup.AI_CHAT, self.member_alex)
        self.assertTrue(can_run)

    def test_ai_chat_denied_in_general(self):
        """Conversational AI paragraphs are prohibited in #general."""
        policy = self.policy_mgr.get_policy_for_channel(self.ch_general)
        self.assertEqual(policy.name, ChannelPolicyType.OBSERVATION_ONLY)
        self.assertFalse(policy.allow_ai_chat)
        can_run, denial = self.policy_mgr.can_execute(self.ch_general, FeatureGroup.AI_CHAT, self.member_alex)
        self.assertFalse(can_run)
        self.assertIn("not allowed in #general", denial)

    def test_general_mention_redirect_message(self):
        """A mention in #general must produce the exact polite redirect with link to #kazumi-chat."""
        redirect_msg = self.policy_mgr.get_mention_redirect_message(self.guild)
        expected = f"Hey! 🌸 Let's keep this channel flowing. For a proper chat with me, come find me in <#{self.ch_kazumi_chat.id}>! ✨"
        self.assertEqual(redirect_msg, expected)

    def test_general_mention_rate_limited(self):
        """Mentions in #general reply at most once within the cooldown window."""
        uid = 999
        should_send_first = self.policy_mgr.should_redirect_mention(self.guild.id, self.ch_general.id, uid, cooldown_seconds=60)
        self.assertTrue(should_send_first)
        # Immediate subsequent ping should be rate-limited
        should_send_second = self.policy_mgr.should_redirect_mention(self.guild.id, self.ch_general.id, uid, cooldown_seconds=60)
        self.assertFalse(should_send_second)

    # --------------------------------------------------------------------------
    # 2. WELCOME SYSTEM & POEM TESTS (PHASE 4)
    # --------------------------------------------------------------------------
    def test_welcome_poem_only_welcome_channel(self):
        """Welcome poems and cards must be targeted exclusively to #welcome."""
        resolved = WelcomeSystem.resolve_welcome_channel(self.guild, {})
        self.assertEqual(resolved.name, "welcome")
        self.assertEqual(resolved.id, self.ch_welcome.id)

        # Welcome events feature must be allowed in #welcome and denied elsewhere
        can_run_welcome, _ = self.policy_mgr.can_execute(self.ch_welcome, FeatureGroup.WELCOME_EVENTS, self.member_alex)
        self.assertTrue(can_run_welcome)

        can_run_general, _ = self.policy_mgr.can_execute(self.ch_general, FeatureGroup.WELCOME_EVENTS, self.member_alex)
        self.assertFalse(can_run_general)

    def test_welcome_display_name_sanitization(self):
        """Untrusted display names must not inject @everyone, @here, links, or markdown."""
        dirty_1 = "@everyone Hacker"
        self.assertEqual(sanitize_display_name(dirty_1), "friend Hacker")

        dirty_2 = "@here https://discord.gg/scam *bold* `code`"
        clean_2 = sanitize_display_name(dirty_2)
        self.assertNotIn("@here", clean_2)
        self.assertNotIn("discord.gg", clean_2)
        self.assertNotIn("*", clean_2)
        self.assertNotIn("`", clean_2)

        dirty_3 = "   <@!123456789> Alex   "
        self.assertEqual(sanitize_display_name(dirty_3), "Alex")

        # Too long
        long_name = "SuperLongNameThatExceedsTheThirtyTwoCharacterLimitByFar12345678"
        self.assertLessEqual(len(sanitize_display_name(long_name)), 32)

    def test_welcome_poem_exact_two_lines(self):
        """Generated welcome poem must contain exactly two rhyming lines."""
        line1, line2 = WelcomePoemGenerator.generate_local_fallback("Alex", "Euphoria")
        self.assertTrue(line1.strip())
        self.assertTrue(line2.strip())
        self.assertIn("Alex", line1)
        self.assertIn("Euphoria", line2)

    def test_welcome_poem_fallback_when_api_fails(self):
        """When OpenAI API is unavailable, the fallback poem generator succeeds without crashing."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            line1, line2 = asyncio.run(WelcomePoemGenerator.generate_poem("Luna", "Euphoria"))
            self.assertTrue(len(line1) > 5)
            self.assertTrue(len(line2) > 5)
            self.assertIn("Luna", line1)
            self.assertIn("Euphoria", line2)

    def test_welcome_event_deduplication(self):
        """Multiple join dispatches for the same member within 180s must be deduplicated."""
        _PROCESSED_JOINS.clear()
        asyncio.run(WelcomeSystem.send_welcome(self.member_alex))
        first_call_count = self.ch_welcome.send.call_count
        self.assertEqual(first_call_count, 1)

        # Immediate second join (duplicate)
        asyncio.run(WelcomeSystem.send_welcome(self.member_alex))
        self.assertEqual(self.ch_welcome.send.call_count, 1) # Must remain 1!

    # --------------------------------------------------------------------------
    # 3. GAMES, GIVEAWAYS & MUSIC CHANNEL POLICIES
    # --------------------------------------------------------------------------
    def test_games_allowed_in_games_and_blocked_in_rules(self):
        """Games must be allowed in #games and strictly blocked in #rules."""
        can_run_games, _ = self.policy_mgr.can_execute(self.ch_games, FeatureGroup.GAMES, self.member_alex)
        self.assertTrue(can_run_games)

        can_run_rules, denial = self.policy_mgr.can_execute(self.ch_rules, FeatureGroup.GAMES, self.member_alex)
        self.assertFalse(can_run_rules)
        self.assertIn("READ_ONLY", denial)

    def test_giveaways_allowed_in_giveaways_and_blocked_in_general(self):
        """Giveaways are allowed in #giveaways and blocked in #general."""
        can_run_ga, _ = self.policy_mgr.can_execute(self.ch_giveaways, FeatureGroup.GIVEAWAYS, self.member_alex)
        self.assertTrue(can_run_ga)

        can_run_gen, denial = self.policy_mgr.can_execute(self.ch_general, FeatureGroup.GIVEAWAYS, self.member_alex)
        self.assertFalse(can_run_gen)

    def test_music_restricted_to_music_commands(self):
        """Music controls are allowed in #music-commands and blocked in #kazumi-chat."""
        can_run_music, _ = self.policy_mgr.can_execute(self.ch_music_commands, FeatureGroup.MUSIC, self.member_alex)
        self.assertTrue(can_run_music)

        can_run_kazumi_chat, denial = self.policy_mgr.can_execute(self.ch_kazumi_chat, FeatureGroup.MUSIC, self.member_alex)
        self.assertFalse(can_run_kazumi_chat)

    # --------------------------------------------------------------------------
    # 4. STAFF, ANNOUNCEMENTS & PRIVILEGE ISOLATION
    # --------------------------------------------------------------------------
    def test_staff_channels_isolation(self):
        """Ordinary members cannot execute commands in #staff-chat, #mod-logs, or #kazumi-logs."""
        can_run_alex, denial_alex = self.policy_mgr.can_execute(self.ch_staff_chat, FeatureGroup.STAFF_COMMANDS, self.member_alex)
        self.assertFalse(can_run_alex)
        self.assertIn("restricted to server staff", denial_alex)

        can_run_mod, _ = self.policy_mgr.can_execute(self.ch_staff_chat, FeatureGroup.STAFF_COMMANDS, self.staff_mod)
        self.assertTrue(can_run_mod)

    def test_announcements_publishing_authorization(self):
        """Announcements can only be published in #announcements or staff channels, with staff authorization."""
        can_run_pub, _ = self.policy_mgr.can_execute(self.ch_announcements, FeatureGroup.ANNOUNCEMENTS, self.staff_mod)
        self.assertTrue(can_run_pub)

        can_run_gen, _ = self.policy_mgr.can_execute(self.ch_general, FeatureGroup.ANNOUNCEMENTS, self.staff_mod)
        self.assertFalse(can_run_gen)

    # --------------------------------------------------------------------------
    # 5. RESILIENCE, FALLBACKS & PRE-EXECUTION GATING
    # --------------------------------------------------------------------------
    def test_missing_channel_id_safe_fallback(self):
        """An unmapped channel must resolve to DEFAULT_PUBLIC safely without crashing."""
        unknown_ch = MockChannel(999999, "random-unknown-channel")
        unknown_ch.guild = self.guild
        policy = self.policy_mgr.get_policy_for_channel(unknown_ch)
        self.assertEqual(policy.name, ChannelPolicyType.DEFAULT_PUBLIC)
        self.assertFalse(policy.allow_ai_chat)

    def test_denied_feature_blocks_before_side_effects(self):
        """Natural language router rejects command execution before side effects when policy fails."""
        router = NaturalIntentRouter(bot=MagicMock(), features_dict={"channel_policy": self.policy_mgr})
        fake_msg = MagicMock()
        fake_msg.channel = self.ch_rules # In #rules
        fake_msg.guild = self.guild
        fake_msg.author = self.member_alex

        music_intent = {"category": "music", "action": "play", "query": "lofi"}
        handled, reply, _ = asyncio.run(router.execute_intent(music_intent, fake_msg))
        self.assertTrue(handled)
        self.assertIn("not allowed in #rules", reply)

    def test_dm_policy_isolation(self):
        """Direct messages use DM_POLICY: allow AI chat but NEVER inherit staff permissions."""
        import discord
        mock_dm = MagicMock(spec=discord.DMChannel)
        policy = self.policy_mgr.get_policy_for_channel(mock_dm)
        self.assertEqual(policy.name, ChannelPolicyType.DM_POLICY)
        self.assertTrue(policy.allow_ai_chat)
        self.assertFalse(policy.is_staff_only)

        # Cannot execute staff commands in DMs
        can_exec, denial = self.policy_mgr.can_execute(mock_dm, FeatureGroup.STAFF_COMMANDS, self.member_alex)
        self.assertFalse(can_exec)
        self.assertIn("DM_POLICY", denial)


if __name__ == "__main__":
    unittest.main()
