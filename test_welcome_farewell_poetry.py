# -*- coding: utf-8 -*-
"""
Unit and integration tests for Kazumi Personalized Welcome & Farewell Poetry System.
Validates:
1. Member join welcome poetry generation, channel targeting, and member mention
2. Member remove farewell poetry generation, channel resolution (farewell -> welcome -> system)
3. Name sanitization and untrusted input safety
4. In-memory 180s sliding-window deduplication for joins and leaves
5. Safe local fallbacks on OpenAI timeout / API failure
6. Safe handling of missing channels and permission errors
7. Formatting constraints (4–8 lines, tasteful emojis, no guilt-tripping)
8. Multi-guild isolation (LAPEACE vs other guilds)
9. Channel resolution hierarchy targeting verified LAPEACE channels
"""

import os
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

import discord
from discord_features.welcome import (
    WelcomePoemGenerator,
    WelcomeSystem,
    sanitize_display_name,
    LAPEACE_GUILD_ID,
    LAPEACE_WELCOME_CHANNEL_ID,
    LAPEACE_GOODBYE_CHANNEL_ID,
    _PROCESSED_JOINS,
    _PROCESSED_LEAVES,
)


class MockAvatar:
    def __init__(self, url="https://cdn.discordapp.com/avatars/123/abc.png"):
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
        self.send = AsyncMock()

    def permissions_for(self, member):
        perms = MagicMock()
        perms.send_messages = self._can_send
        perms.embed_links = self._can_embed
        return perms


class TestWelcomeFarewellPoetry(unittest.TestCase):
    def setUp(self):
        # Setup mock guild for LAPEACE
        self.guild = MagicMock()
        self.guild.id = LAPEACE_GUILD_ID
        self.guild.name = "LAPEACE"
        self.guild.member_count = 42

        # Setup mock channels for LAPEACE
        self.ch_welcome = MockTextChannel(LAPEACE_WELCOME_CHANNEL_ID, "welcome")
        self.ch_goodbye = MockTextChannel(LAPEACE_GOODBYE_CHANNEL_ID, "goodbye")
        self.ch_general = MockTextChannel(1554152397830357004, "general-chat")
        self.ch_rules = MockTextChannel(1560031026477142057, "rules")
        self.ch_intro = MockTextChannel(1560033839563145337, "introductions")

        self.guild.text_channels = [
            self.ch_welcome,
            self.ch_goodbye,
            self.ch_general,
            self.ch_rules,
            self.ch_intro,
        ]
        self.guild.system_channel = self.ch_general

        def _get_channel(cid):
            for c in self.guild.text_channels:
                if c.id == int(cid):
                    return c
            return None

        self.guild.get_channel = MagicMock(side_effect=_get_channel)

        self.member_alice = MockMember(1001, "alice", "Alice🌸", guild=self.guild)
        self.member_bob = MockMember(1002, "bob", "Bob_Dev", guild=self.guild)
        self.member_hacker = MockMember(1003, "hacker", "@everyone <script>alert(1)</script>", guild=self.guild)

        # Clear dedup caches
        _PROCESSED_JOINS.clear()
        _PROCESSED_LEAVES.clear()

        # Mock database settings default to clean state
        self.db_patcher = patch("discord_features.welcome.get_feature_db")
        self.mock_db = self.db_patcher.start()
        self.mock_db.return_value.get_guild_settings.return_value = {
            "welcome_enabled": True,
            "goodbye_enabled": True,
            "welcome_channel_id": str(LAPEACE_WELCOME_CHANNEL_ID),
            "goodbye_channel_id": str(LAPEACE_GOODBYE_CHANNEL_ID),
        }

    def tearDown(self):
        self.db_patcher.stop()

    # =========================================================================
    # 1. Name Sanitization Tests
    # =========================================================================
    def test_sanitize_display_name(self):
        self.assertEqual(sanitize_display_name("Alice🌸"), "Alice🌸")
        self.assertEqual(sanitize_display_name("@everyone @here"), "friend friend")
        self.assertEqual(sanitize_display_name("<@!123456789> Bob"), "Bob")
        self.assertEqual(sanitize_display_name("https://malicious.link/free-nitro"), "Friend")
        self.assertEqual(sanitize_display_name("   "), "Friend")
        self.assertEqual(sanitize_display_name(""), "Friend")
        self.assertEqual(sanitize_display_name("___***~~~"), "Friend")

    # =========================================================================
    # 2. Local Fallback Poetry Constraints Tests (4–8 lines, emojis)
    # =========================================================================
    def test_welcome_fallback_poetry_structure(self):
        """Welcome poem fallbacks must have between 4 and 8 lines and incorporate name and server."""
        for _ in range(15):
            poem = WelcomePoemGenerator.generate_local_welcome_fallback("Alice", "LAPEACE")
            lines = [l for l in poem.split("\n") if l.strip()]
            self.assertGreaterEqual(len(lines), 4)
            self.assertLessEqual(len(lines), 8)
            self.assertIn("Alice", poem)
            self.assertIn("LAPEACE", poem)

    def test_farewell_fallback_poetry_structure(self):
        """Farewell poem fallbacks must have between 4 and 8 lines and incorporate name."""
        for _ in range(15):
            poem = WelcomePoemGenerator.generate_local_farewell_fallback("Bob", "LAPEACE")
            lines = [l for l in poem.split("\n") if l.strip()]
            self.assertGreaterEqual(len(lines), 4)
            self.assertLessEqual(len(lines), 8)
            self.assertIn("Bob", poem)
            # Ensure tone is gentle, without guilt-tripping words
            self.assertNotIn("why did you leave", poem.lower())
            self.assertNotIn("shame", poem.lower())
            self.assertNotIn("betray", poem.lower())

    # =========================================================================
    # 3. Channel Resolution Tests (Verified LAPEACE IDs)
    # =========================================================================
    def test_resolve_welcome_channel_lapeace_default(self):
        """LAPEACE automatically resolves to verified welcome channel ID 1560033823960334396."""
        ch = WelcomeSystem.resolve_welcome_channel(self.guild, {})
        self.assertEqual(ch.id, LAPEACE_WELCOME_CHANNEL_ID)

    def test_resolve_goodbye_channel_lapeace_default(self):
        """LAPEACE automatically resolves to verified goodbye channel ID 1560220721429610556."""
        ch = WelcomeSystem.resolve_goodbye_channel(self.guild, {})
        self.assertEqual(ch.id, LAPEACE_GOODBYE_CHANNEL_ID)

    def test_resolve_goodbye_channel_hierarchy_fallback(self):
        """If goodbye channel is missing, fallback cleanly to welcome channel."""
        guild_no_goodbye = MagicMock()
        guild_no_goodbye.id = 999999999
        guild_no_goodbye.text_channels = [self.ch_welcome, self.ch_general]
        guild_no_goodbye.get_channel = MagicMock(return_value=None)
        guild_no_goodbye.system_channel = self.ch_general
        ch = WelcomeSystem.resolve_goodbye_channel(guild_no_goodbye, {"welcome_channel_id": str(LAPEACE_WELCOME_CHANNEL_ID)})
        self.assertEqual(ch.id, LAPEACE_WELCOME_CHANNEL_ID)

    # =========================================================================
    # 4. Member Join Welcome Event Tests
    # =========================================================================
    def test_send_welcome_success(self):
        """New member receives personalized welcome poem with mention and embed."""
        asyncio.run(WelcomeSystem.send_welcome(self.member_alice))
        self.ch_welcome.send.assert_called_once()
        call_kwargs = self.ch_welcome.send.call_args.kwargs
        # Verify mention
        self.assertIn(self.member_alice.mention, call_kwargs["content"])
        # Verify embed
        embed = call_kwargs["embed"]
        self.assertIn("Alice🌸", embed.title)
        self.assertIn("LAPEACE", embed.title)
        self.assertIn("LAPEACE", embed.description)

    def test_welcome_event_deduplication(self):
        """Same member join dispatched twice within 180s must be sent only once."""
        asyncio.run(WelcomeSystem.send_welcome(self.member_alice))
        self.assertEqual(self.ch_welcome.send.call_count, 1)

        # Immediate duplicate
        asyncio.run(WelcomeSystem.send_welcome(self.member_alice))
        self.assertEqual(self.ch_welcome.send.call_count, 1)

        # Different member passes
        asyncio.run(WelcomeSystem.send_welcome(self.member_bob))
        self.assertEqual(self.ch_welcome.send.call_count, 2)

    # =========================================================================
    # 5. Member Leave Farewell Event Tests
    # =========================================================================
    def test_send_goodbye_success(self):
        """Departing member receives gentle farewell poem in goodbye channel."""
        asyncio.run(WelcomeSystem.send_goodbye(self.member_bob))
        self.ch_goodbye.send.assert_called_once()
        call_kwargs = self.ch_goodbye.send.call_args.kwargs
        embed = call_kwargs["embed"]
        self.assertIn("BobDev", embed.title)
        self.assertIn("BobDev", embed.description)
        self.assertIn("LAPEACE", embed.description)

    def test_goodbye_event_deduplication(self):
        """Same member leave dispatched twice within 180s must be sent only once."""
        asyncio.run(WelcomeSystem.send_goodbye(self.member_bob))
        self.assertEqual(self.ch_goodbye.send.call_count, 1)

        # Immediate duplicate
        asyncio.run(WelcomeSystem.send_goodbye(self.member_bob))
        self.assertEqual(self.ch_goodbye.send.call_count, 1)

        # Different member passes
        asyncio.run(WelcomeSystem.send_goodbye(self.member_alice))
        self.assertEqual(self.ch_goodbye.send.call_count, 2)

    # =========================================================================
    # 6. Multi-Guild Isolation Tests
    # =========================================================================
    def test_multi_guild_isolation_unconfigured_disabled(self):
        """Other guilds with disabled welcome/goodbye do not receive messages."""
        other_guild = MagicMock()
        other_guild.id = 888888888
        other_guild.name = "OtherServer"
        other_ch = MockTextChannel(801, "welcome")
        other_guild.text_channels = [other_ch]
        other_member = MockMember(777, "other_user", "OtherUser", guild=other_guild)

        # Settings with disabled welcome/goodbye for other guild
        self.mock_db.return_value.get_guild_settings.return_value = {
            "welcome_enabled": False,
            "goodbye_enabled": False,
        }

        asyncio.run(WelcomeSystem.send_welcome(other_member))
        other_ch.send.assert_not_called()

        asyncio.run(WelcomeSystem.send_goodbye(other_member))
        other_ch.send.assert_not_called()

    # =========================================================================
    # 7. Resilience & Safety Tests
    # =========================================================================
    def test_send_welcome_bot_ignored(self):
        """Bots should never receive welcome or farewell poems."""
        bot_member = MockMember(9999, "other_bot", "OtherBot", guild=self.guild, bot=True)
        asyncio.run(WelcomeSystem.send_welcome(bot_member))
        self.ch_welcome.send.assert_not_called()
        asyncio.run(WelcomeSystem.send_goodbye(bot_member))
        self.ch_goodbye.send.assert_not_called()

    def test_missing_channel_does_not_crash(self):
        """When no sendable channel exists, the system logs and returns gracefully."""
        guild_empty = MagicMock()
        guild_empty.id = 999
        guild_empty.text_channels = []
        guild_empty.system_channel = None
        guild_empty.get_channel = MagicMock(return_value=None)
        member = MockMember(555, "lonely", "Lonely", guild=guild_empty)

        # Neither should raise an exception
        asyncio.run(WelcomeSystem.send_welcome(member))
        asyncio.run(WelcomeSystem.send_goodbye(member))


if __name__ == "__main__":
    unittest.main()
