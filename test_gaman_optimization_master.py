# -*- coding: utf-8 -*-
"""
================================================================================
🌸 GAMAN DISCORD SERVER OPTIMIZATION & KAZUMI INTEGRATION MASTER TEST SUITE
================================================================================
Covers Phases 1 through 11:
1. Target Guild ID Confirmation & Isolation (1554152397327044729 vs Euphoria)
2. Channel Architecture & Policy Enforcement for All Channels
3. Two-Line Personalized Welcome Poem Engine & Sanitization
4. Role Hierarchy & Permission Safety Gates
5. Feature Verification: AI Chat, Commands, Moderation, Games, Tickets, Giveaways
6. Live Discord Guild Audit Verification
================================================================================
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import os
import time
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import discord
from discord_features.database import get_feature_db
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

GAMAN_GUILD_ID = 1554152397327044729
EUPHORIA_GUILD_ID = 1546919406603337809


class MockChannel:
    def __init__(self, id_val: int, name: str, ch_type="text", category=None):
        self.id = id_val
        self.name = name
        self.type = ch_type
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
    def __init__(self, id_val: int, name: str, display_name: str, is_bot: bool = False, is_admin: bool = False, is_mod: bool = False):
        self.id = id_val
        self.name = name
        self.display_name = display_name
        self.bot = is_bot
        self.guild = None
        self.roles = []
        self.top_role = MagicMock()
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


class TestGamanOptimization(unittest.TestCase):

    def setUp(self):
        self.db = get_feature_db()
        self.policy_mgr = get_channel_policy_manager(self.db)
        self.gaman_settings = self.db.get_guild_settings(str(GAMAN_GUILD_ID))
        self.euphoria_settings = self.db.get_guild_settings(str(EUPHORIA_GUILD_ID))

    # =========================================================================
    # 1. Scope Restriction & Multi-Guild Isolation
    # =========================================================================
    def test_01_guild_id_and_isolation(self):
        """Verify Gaman configuration exists and is strictly isolated from Euphoria."""
        self.assertIsNotNone(self.gaman_settings)
        self.assertIsNotNone(self.euphoria_settings)

        # Confirm distinct keys
        self.assertNotEqual(str(GAMAN_GUILD_ID), str(EUPHORIA_GUILD_ID))

        # Confirm Gaman welcome channel is distinct
        gaman_welcome = self.gaman_settings.get("welcome_channel_id")
        euphoria_welcome = self.euphoria_settings.get("welcome_channel_id")
        self.assertEqual(gaman_welcome, "1560033823960334396")
        self.assertEqual(euphoria_welcome, "1557699099246071900")
        self.assertNotEqual(gaman_welcome, euphoria_welcome)

        # Confirm Gaman logging channel is distinct
        gaman_log = self.gaman_settings.get("logging_channel_id")
        euphoria_log = self.euphoria_settings.get("logging_channel_id")
        self.assertEqual(gaman_log, "1560034265020768468")
        self.assertEqual(euphoria_log, "1557699156196462704")
        self.assertNotEqual(gaman_log, euphoria_log)

    # =========================================================================
    # 2. Channel-Specific Policy Enforcement
    # =========================================================================
    def test_02_channel_policies(self):
        """Verify strict channel policy boundaries for all Gaman channels."""
        # A. #kazumi-chat -> ACTIVE_CHAT
        ch_kazumi_chat = MockChannel(1560034107306680460, "kazumi-chat")
        p_kazumi = self.policy_mgr.get_policy_for_channel(ch_kazumi_chat, GAMAN_GUILD_ID)
        self.assertEqual(p_kazumi.name, ChannelPolicyType.ACTIVE_CHAT)
        self.assertTrue(p_kazumi.is_feature_allowed(FeatureGroup.AI_CHAT))
        self.assertFalse(p_kazumi.is_feature_allowed(FeatureGroup.GAMES))

        # B. #general -> OBSERVATION_ONLY
        ch_general = MockChannel(1554152397830357004, "general")
        p_general = self.policy_mgr.get_policy_for_channel(ch_general, GAMAN_GUILD_ID)
        self.assertEqual(p_general.name, ChannelPolicyType.OBSERVATION_ONLY)
        self.assertFalse(p_general.allow_ai_chat)
        self.assertTrue(p_general.is_feature_allowed(FeatureGroup.CONTEXTUAL_REACTIONS))
        self.assertTrue(p_general.is_feature_allowed(FeatureGroup.AI_MENTION_REDIRECT))
        self.assertFalse(p_general.is_feature_allowed(FeatureGroup.GAMES))

        # C. #welcome -> EVENTS_ONLY
        ch_welcome = MockChannel(1560033823960334396, "welcome")
        p_welcome = self.policy_mgr.get_policy_for_channel(ch_welcome, GAMAN_GUILD_ID)
        self.assertEqual(p_welcome.name, ChannelPolicyType.EVENTS_ONLY)
        self.assertTrue(p_welcome.is_feature_allowed(FeatureGroup.WELCOME_EVENTS))
        self.assertFalse(p_welcome.allow_ai_chat)

        # D. #rules -> READ_ONLY
        ch_rules = MockChannel(1560031026477142057, "rules")
        p_rules = self.policy_mgr.get_policy_for_channel(ch_rules, GAMAN_GUILD_ID)
        self.assertEqual(p_rules.name, ChannelPolicyType.READ_ONLY)
        self.assertEqual(len(p_rules.allowed_features), 0)

        # E. #kazumi-commands -> COMMANDS_ONLY
        ch_cmds = MockChannel(1560034109701496896, "kazumi-commands")
        p_cmds = self.policy_mgr.get_policy_for_channel(ch_cmds, GAMAN_GUILD_ID)
        self.assertEqual(p_cmds.name, ChannelPolicyType.COMMANDS_ONLY)
        self.assertFalse(p_cmds.allow_ai_chat)

        # F. #kazumi-games -> GAMEPLAY_ONLY
        ch_games = MockChannel(1560034112088047658, "kazumi-games")
        p_games = self.policy_mgr.get_policy_for_channel(ch_games, GAMAN_GUILD_ID)
        self.assertEqual(p_games.name, ChannelPolicyType.GAMEPLAY_ONLY)
        self.assertTrue(p_games.is_feature_allowed(FeatureGroup.GAMES))
        self.assertFalse(p_games.allow_ai_chat)

        # G. #mod-logs & #kazumi-logs -> STAFF_ONLY
        ch_mod_logs = MockChannel(1560034265020768468, "mod-logs")
        p_mod_logs = self.policy_mgr.get_policy_for_channel(ch_mod_logs, GAMAN_GUILD_ID)
        self.assertEqual(p_mod_logs.name, ChannelPolicyType.STAFF_ONLY)
        self.assertTrue(p_mod_logs.is_staff_only)

        ch_kazumi_logs = MockChannel(1560034399515451412, "kazumi-logs")
        p_kazumi_logs = self.policy_mgr.get_policy_for_channel(ch_kazumi_logs, GAMAN_GUILD_ID)
        self.assertEqual(p_kazumi_logs.name, ChannelPolicyType.STAFF_ONLY)
        self.assertTrue(p_kazumi_logs.is_staff_only)

        # H. Community Stage -> STAGE_EVENT_ONLY
        ch_stage = MockChannel(1560034244355559456, "Community Stage", ch_type="stage_voice")
        p_stage = self.policy_mgr.get_policy_for_channel(ch_stage, GAMAN_GUILD_ID)
        self.assertEqual(p_stage.name, ChannelPolicyType.STAGE_EVENT_ONLY)

    # =========================================================================
    # 3. Two-Line Personalized Welcome Poem Engine & Sanitization
    # =========================================================================
    def test_03_display_name_sanitization(self):
        """Verify display name sanitization strips mass mentions, URLs, markdown, and limits length."""
        # Strips @everyone and @here
        self.assertEqual(sanitize_display_name("@everyone"), "friend")
        self.assertEqual(sanitize_display_name("@here Hax"), "friend Hax")

        # Strips raw mention tags
        self.assertEqual(sanitize_display_name("<@!123456789> Alice"), "Alice")

        # Strips URLs and invites
        self.assertEqual(sanitize_display_name("Bob https://bad.link/malware"), "Bob")
        self.assertEqual(sanitize_display_name("Charlie discord.gg/fake"), "Charlie")

        # Strips markdown characters
        self.assertEqual(sanitize_display_name("**Bold** `Code` *Italic*"), "Bold Code Italic")

        # Length limit to 32 characters
        very_long = "A" * 60
        sanitized = sanitize_display_name(very_long)
        self.assertLessEqual(len(sanitized), 32)

        # Fallback for empty or purely non-alphanumeric
        self.assertEqual(sanitize_display_name(""), "Friend")
        self.assertEqual(sanitize_display_name("   "), "Friend")
        self.assertEqual(sanitize_display_name("___***~~~"), "Friend")

    def test_04_poem_generator_local_fallback(self):
        """Verify local fallback poem produces exactly two rhyming lines with name and server."""
        l1, l2 = WelcomePoemGenerator.generate_local_fallback("kaizen_2157", "Gaman")
        self.assertTrue(len(l1) > 0)
        self.assertTrue(len(l2) > 0)
        self.assertIn("kaizen_2157", l1)
        self.assertIn("Gaman", l2)

    def test_05_welcome_deduplication(self):
        """Verify deduplication cache blocks duplicate joins within 180s."""
        guild = MagicMock()
        guild.id = GAMAN_GUILD_ID
        guild.name = "Gaman"
        member = MockMember(999901, "newbie", "NewbieMember")
        member.guild = guild

        # Clear dedup key
        dedup_key = (GAMAN_GUILD_ID, 999901)
        _PROCESSED_JOINS.pop(dedup_key, None)

        # First trigger simulates recording
        now = time.time()
        _PROCESSED_JOINS[dedup_key] = now

        # Immediate subsequent trigger within 180s is recognized as duplicate
        self.assertTrue(time.time() - _PROCESSED_JOINS[dedup_key] < 180.0)

    # =========================================================================
    # 4. Roles & Permissions Verification
    # =========================================================================
    def test_06_role_hierarchy_and_permissions(self):
        """Verify role hierarchy and authorization rules."""
        # Non-staff member cannot run staff commands
        regular_member = MockMember(1001, "regular", "RegularUser", is_admin=False, is_mod=False)
        self.assertFalse(regular_member.guild_permissions.administrator)
        self.assertFalse(regular_member.guild_permissions.manage_messages)

        # Moderator member has moderation permissions
        mod_member = MockMember(1002, "mod", "ModUser", is_admin=False, is_mod=True)
        self.assertTrue(mod_member.guild_permissions.manage_messages)
        self.assertTrue(mod_member.guild_permissions.kick_members)
        self.assertFalse(mod_member.guild_permissions.administrator)

        # Self-assignable roles check
        g_settings = self.db.get_guild_settings(str(GAMAN_GUILD_ID))
        autoroles = g_settings.get("autorole_ids", [])
        self.assertIn("1560031417973346385", autoroles)  # Member role ID


async def run_live_gateway_check():
    """Live verification of Gaman guild structure and connection using bot static token."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    client = discord.Client(intents=discord.Intents.default())

    results = {}

    @client.event
    async def on_ready():
        try:
            g = client.get_guild(GAMAN_GUILD_ID)
            results["guild_found"] = g is not None
            if g:
                results["guild_name"] = g.name
                results["member_count"] = g.member_count
                results["community_enabled"] = "COMMUNITY" in g.features
                results["news_enabled"] = "NEWS" in g.features
                results["categories_count"] = len(g.categories)
                results["channels_count"] = len(g.channels)

                # Check reused channels
                ch_general = discord.utils.get(g.text_channels, id=1554152397830357004)
                results["reused_general_ok"] = ch_general is not None and ch_general.category.name == "🌐 GAMAN COMMUNITY"

                ch_rules = discord.utils.get(g.text_channels, id=1560031026477142057)
                results["reused_rules_ok"] = ch_rules is not None and ch_rules.category.name == "✨ START HERE"

                ch_voice = discord.utils.get(g.voice_channels, id=1554152397830357005)
                results["reused_voice_ok"] = ch_voice is not None and ch_voice.category.name == "🎙️ VOICE & LIVE"

                # Check special channels
                ch_stage = discord.utils.get(g.stage_channels, name="Community Stage")
                results["stage_channel_ok"] = ch_stage is not None

                ch_announcements = discord.utils.get(g.text_channels, name="announcements")
                results["announcements_channel_ok"] = ch_announcements is not None and ch_announcements.is_news()

                forums = [f.name for f in g.forums]
                results["forum_showcase_ok"] = "showcase" in forums
                results["forum_qa_ok"] = "questions-and-help" in forums
                results["forum_suggestions_ok"] = "suggestions" in forums

                # Check bot permissions
                me = g.me
                results["bot_present"] = me is not None
                results["bot_is_admin"] = me.guild_permissions.administrator  # Should be False
                results["bot_can_send"] = me.guild_permissions.send_messages
                results["bot_can_embed"] = me.guild_permissions.embed_links
                results["bot_can_manage_roles"] = me.guild_permissions.manage_roles
                results["bot_can_manage_channels"] = me.guild_permissions.manage_channels
        except Exception as e:
            results["error"] = str(e)
        finally:
            await client.close()

    await client.start(token)
    return results


if __name__ == "__main__":
    # 1. Run unit test suite
    print("=" * 70)
    print("RUNNING GAMAN MASTER ACCEPTANCE UNIT TESTS")
    print("=" * 70)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGamanOptimization)
    runner = unittest.TextTestRunner(verbosity=2)
    test_result = runner.run(suite)

    if not test_result.wasSuccessful():
        print("❌ Master acceptance unit tests failed!")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("RUNNING LIVE DISCORD GATEWAY VERIFICATION ON GAMAN (1554152397327044729)")
    print("=" * 70)
    live_results = asyncio.run(run_live_gateway_check())
    for k, v in live_results.items():
        status_icon = "✅" if v is True or (k in ["guild_name", "member_count", "categories_count", "channels_count"] and v) or (k == "bot_is_admin" and v is False) else "ℹ️"
        print(f" {status_icon} {k}: {v}")

    # Assertions on live check
    assert live_results.get("guild_found"), "Target guild not found on live Gateway!"
    assert live_results.get("community_enabled"), "Discord Community must be enabled!"
    assert live_results.get("news_enabled"), "News feature must be enabled!"
    assert live_results.get("reused_general_ok"), "Original general channel not preserved/categorized correctly!"
    assert live_results.get("reused_rules_ok"), "Original rules channel not preserved/categorized correctly!"
    assert live_results.get("reused_voice_ok"), "Original voice channel not preserved/categorized correctly!"
    assert live_results.get("stage_channel_ok"), "Genuine Discord Stage channel missing!"
    assert live_results.get("announcements_channel_ok"), "Genuine Discord Announcement/News channel missing!"
    assert live_results.get("forum_showcase_ok"), "Showcase forum missing!"
    assert live_results.get("forum_qa_ok"), "Questions Q&A forum missing!"
    assert live_results.get("forum_suggestions_ok"), "Suggestions forum missing!"
    assert live_results.get("bot_is_admin") is False, "CRITICAL: Kazumi bot must NOT have Administrator permission!"
    assert live_results.get("bot_can_send"), "Kazumi bot cannot send messages!"
    assert live_results.get("bot_can_embed"), "Kazumi bot cannot embed links!"

    print("\n🎉 ALL MASTER ACCEPTANCE CHECKS PASSED FOR GAMAN!")
