"""
================================================================================
🌸 KAZUMI ALL-IN-ONE DISCORD BOT EXPANSION: MASTER ACCEPTANCE TEST SUITE
================================================================================
Comprehensive verification of Dyno Moderation, GiveawayBot, Jockie Music,
AI Natural Intent Dispatching, Security, Hierarchy, and Persistence.
"""

import os
import shutil
import unittest
import time
from unittest.mock import MagicMock, AsyncMock, patch

import discord

from discord_features.database import FeatureDatabase
from discord_features.permissions import PermissionService
from discord_features.intent_router import NaturalIntentRouter
from discord_features.music import GuildMusicPlayer
from discord_features.giveaways import GiveawayManager
from discord_features.config import sanitize_secrets


class AllInOneExpansionAcceptanceTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.test_dir = "isa_memory_all_in_one_test"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        os.makedirs(self.test_dir, exist_ok=True)
        self.db = FeatureDatabase(persist_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # =========================================================================
    # 1. MODERATION TESTS (Dyno-inspired)
    # =========================================================================

    def test_01_moderation_authorized_warning(self):
        """Authorized moderator issues a warning, creating a case and incrementing warnings."""
        guild_id = 12345
        target_id = 999
        mod_id = 111

        case_id = self.db.create_case(guild_id, target_id, mod_id, "WARN", "Spamming links")
        self.assertGreater(case_id, 0)

        warn_count = self.db.add_warning(str(guild_id), str(target_id), str(mod_id), "Spamming links")
        self.assertEqual(warn_count, 1)

        case = self.db.get_case(case_id)
        self.assertIsNotNone(case)
        self.assertEqual(case["action"], "WARN")
        self.assertEqual(case["reason"], "Spamming links")

    def test_02_moderation_unauthorized_ban_denied(self):
        """User lacking Ban Members permission or mod roles is rejected."""
        mock_member = MagicMock(spec=discord.Member)
        mock_member.guild = MagicMock(spec=discord.Guild)
        mock_member.guild.owner_id = 1
        mock_member.id = 222
        mock_member.roles = []
        mock_member.guild_permissions = discord.Permissions(send_messages=True)

        is_auth, err = PermissionService.check_permission(mock_member, "ban_members", {})
        self.assertFalse(is_auth)
        self.assertIn("Ban Members", err)

    def test_03_moderation_invalid_target_self_or_owner(self):
        """Executor cannot target themselves or the server owner."""
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.owner_id = 100

        mod = MagicMock(spec=discord.Member)
        mod.id = 200
        mod.guild = mock_guild
        mod.top_role = MagicMock()
        mod.top_role.position = 10

        # Self-target
        can_target_self, err_self = PermissionService.check_hierarchy(mod, mod)
        self.assertFalse(can_target_self)
        self.assertIn("yourself", err_self)

        # Owner target
        owner = MagicMock(spec=discord.Member)
        owner.id = 100
        owner.guild = mock_guild
        owner.top_role = MagicMock()
        owner.top_role.position = 99

        can_target_owner, err_owner = PermissionService.check_hierarchy(mod, owner)
        self.assertFalse(can_target_owner)
        self.assertIn("owner", err_owner)

    def test_04_moderation_role_hierarchy_violation(self):
        """Moderator cannot target a member with an equal or higher role."""
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.owner_id = 1

        mod = MagicMock(spec=discord.Member)
        mod.id = 200
        mod.guild = mock_guild
        mod.top_role = MagicMock()
        mod.top_role.position = 5
        mod.top_role.__le__ = lambda s, o: s.position <= o.position

        senior_target = MagicMock(spec=discord.Member)
        senior_target.id = 300
        senior_target.display_name = "Senior Admin"
        senior_target.guild = mock_guild
        senior_target.top_role = MagicMock()
        senior_target.top_role.position = 10
        senior_target.top_role.__ge__ = lambda s, o: s.position >= o.position

        can_target, err = PermissionService.check_hierarchy(mod, senior_target)
        self.assertFalse(can_target)
        self.assertIn("Role hierarchy violation", err)

    def test_05_moderation_purge_and_modlogs_persistence(self):
        """Purge actions and moderation events are stored in mod logs."""
        guild_id = "555"
        self.db.record_mod_action(guild_id, "PURGE", "101", "202", "Purged 25 messages")
        self.db.record_mod_action(guild_id, "MUTE", "303", "202", "Spam mute 10m")

        logs = self.db.get_mod_logs(guild_id, limit=10)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["action"], "MUTE")  # Most recent first
        self.assertEqual(logs[1]["action"], "PURGE")

    # =========================================================================
    # 2. GIVEAWAY TESTS (GiveawayBot-inspired)
    # =========================================================================

    async def test_06_giveaway_create_and_entry(self):
        """Giveaway can be created and user can enter."""
        ga_id = "ga_1001"
        ga_data = {
            "message_id": ga_id,
            "guild_id": "888",
            "channel_id": "777",
            "prize": "Discord Nitro",
            "winners_count": 1,
            "end_time": time.time() + 3600,
            "entries": [],
            "ended": False,
            "paused": False,
            "winners": []
        }
        self.db.set_giveaway(ga_id, ga_data)

        # Enter giveaway
        entered, msg = GiveawayManager.enter_giveaway("888", ga_id, 456, self.db)
        self.assertTrue(entered)
        self.assertIn("entered", msg.lower())

        loaded = self.db.get_giveaway(ga_id)
        self.assertIn("456", loaded["entries"])

    async def test_07_giveaway_prevent_duplicate_entries(self):
        """User cannot enter the same giveaway twice."""
        ga_id = "ga_dup"
        ga_data = {
            "message_id": ga_id,
            "guild_id": "888",
            "channel_id": "777",
            "prize": "Steam Key",
            "winners_count": 1,
            "end_time": time.time() + 3600,
            "entries": ["456"],
            "ended": False,
            "paused": False,
            "winners": []
        }
        self.db.set_giveaway(ga_id, ga_data)

        entered, msg = GiveawayManager.enter_giveaway("888", ga_id, 456, self.db)
        self.assertFalse(entered)
        self.assertIn("already entered", msg.lower())

    async def test_08_giveaway_reject_ineligible_entry(self):
        """User without required role is rejected from entering."""
        ga_id = "ga_role"
        ga_data = {
            "message_id": ga_id,
            "guild_id": "888",
            "channel_id": "777",
            "prize": "VIP Access",
            "winners_count": 1,
            "end_time": time.time() + 3600,
            "required_role_id": "9999",
            "entries": [],
            "ended": False,
            "paused": False,
            "winners": []
        }
        self.db.set_giveaway(ga_id, ga_data)

        mock_member = MagicMock(spec=discord.Member)
        mock_member.id = 123
        mock_member.roles = []  # Lacks required role 9999

        entered, msg = GiveawayManager.enter_giveaway("888", ga_id, 123, self.db, member=mock_member)
        self.assertFalse(entered)
        self.assertIn("required role", msg.lower())

    async def test_09_giveaway_end_and_reroll_fairness(self):
        """Ending giveaway picks a winner; reroll selects a different winner."""
        ga_id = "ga_end_test"
        ga_data = {
            "message_id": ga_id,
            "guild_id": "888",
            "channel_id": "777",
            "prize": "Nitro Classic",
            "winners_count": 1,
            "end_time": time.time() - 10,  # Expired
            "entries": ["user_A", "user_B", "user_C"],
            "ended": False,
            "paused": False,
            "winners": []
        }
        self.db.set_giveaway(ga_id, ga_data)

        # Mock bot channel fetch
        mock_bot = MagicMock()
        mock_channel = AsyncMock()
        mock_msg = AsyncMock()
        mock_channel.fetch_message.return_value = mock_msg
        mock_bot.get_channel.return_value = mock_channel

        mgr = GiveawayManager(mock_bot, self.db)
        winners = await mgr.end_giveaway(ga_id)

        self.assertEqual(len(winners), 1)
        first_winner = winners[0]
        self.assertIn(first_winner, ["user_A", "user_B", "user_C"])

        # Reroll must exclude first_winner
        new_winners = await mgr.reroll_giveaway(ga_id)
        self.assertEqual(len(new_winners), 1)
        self.assertNotEqual(new_winners[0], first_winner)
        self.assertIn(new_winners[0], ["user_A", "user_B", "user_C"])

    def test_10_giveaway_persistence_across_restart(self):
        """Active giveaways survive database reloading."""
        ga_id = "ga_survive"
        self.db.set_giveaway(ga_id, {
            "message_id": ga_id,
            "guild_id": "888",
            "prize": "Survive Nitro",
            "entries": ["u1", "u2"],
            "ended": False
        })

        # Reload from disk
        db2 = FeatureDatabase(persist_dir=self.test_dir)
        loaded = db2.get_giveaway(ga_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["prize"], "Survive Nitro")
        self.assertEqual(len(loaded["entries"]), 2)

    # =========================================================================
    # 3. MUSIC TESTS (Jockie Music-inspired)
    # =========================================================================

    async def test_11_music_queue_shuffle_loop_remove(self):
        """Music player supports queueing, shuffling, looping, and removing tracks."""
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = 123
        player = GuildMusicPlayer(mock_guild)

        # Enqueue tracks
        player.queue.append({"title": "Song 1", "url": "url1", "duration": 180})
        player.queue.append({"title": "Song 2", "url": "url2", "duration": 200})
        player.queue.append({"title": "Song 3", "url": "url3", "duration": 220})
        self.assertEqual(len(player.queue), 3)

        # Shuffle
        count = player.shuffle()
        self.assertEqual(count, 3)

        # Loop toggle
        loop_state = player.toggle_loop()
        self.assertTrue(loop_state)
        self.assertTrue(player.loop_mode)
        player.toggle_loop()
        self.assertFalse(player.loop_mode)

        # Remove
        removed = player.remove(2)
        self.assertIsNotNone(removed)
        self.assertEqual(len(player.queue), 2)

        # Clear queue
        cleared_count = player.clear_queue()
        self.assertEqual(cleared_count, 2)
        self.assertEqual(len(player.queue), 0)

    async def test_12_music_guild_isolation(self):
        """Separate guilds have completely isolated music queues and players."""
        from discord_features.music import get_player

        guild_A = MagicMock(spec=discord.Guild)
        guild_A.id = 1001
        guild_B = MagicMock(spec=discord.Guild)
        guild_B.id = 1002

        player_A = get_player(guild_A)
        player_B = get_player(guild_B)

        player_A.queue.append({"title": "Guild A Track"})
        self.assertEqual(len(player_A.queue), 1)
        self.assertEqual(len(player_B.queue), 0)  # Guild B unaffected!

    # =========================================================================
    # 4. AI NATURAL LANGUAGE INTENT DISPATCHER TESTS
    # =========================================================================

    def test_13_ai_natural_intent_detection(self):
        """Translates natural language prompts into structured action intents."""
        router = NaturalIntentRouter(None, {"db": self.db})
        mock_msg = MagicMock(spec=discord.Message)
        mock_msg.mentions = []

        # Music
        int1 = router.detect_intent("Kazumi, play some relaxing music", mock_msg)
        self.assertIsNotNone(int1)
        self.assertEqual(int1["category"], "music")
        self.assertEqual(int1["action"], "play")

        int2 = router.detect_intent("skip this song please", mock_msg)
        self.assertIsNotNone(int2)
        self.assertEqual(int2["category"], "music")
        self.assertEqual(int2["action"], "skip")

        # Giveaways
        int3 = router.detect_intent("Kazumi, start a giveaway for 24h for Discord Nitro", mock_msg)
        self.assertIsNotNone(int3)
        self.assertEqual(int3["category"], "giveaway")
        self.assertEqual(int3["action"], "create")
        self.assertEqual(int3["prize"].lower(), "discord nitro")

        # Moderation
        int4 = router.detect_intent("Kazumi, lock this channel", mock_msg)
        self.assertIsNotNone(int4)
        self.assertEqual(int4["category"], "moderation")
        self.assertEqual(int4["action"], "lock")

    def test_14_ai_normal_conversation_not_intercepted(self):
        """Casual conversation must NOT be mistaken for commands."""
        router = NaturalIntentRouter(None, {"db": self.db})
        mock_msg = MagicMock(spec=discord.Message)
        mock_msg.mentions = []

        int_chat = router.detect_intent("Hey Kazumi, what do you think about stars?", mock_msg)
        self.assertIsNone(int_chat)

        int_laugh = router.detect_intent("hahahaha that was hilarious Kazumi!", mock_msg)
        self.assertIsNone(int_laugh)

    async def test_15_ai_natural_moderation_permission_enforcement(self):
        """Unauthorized user attempting moderation via natural language is rejected."""
        mock_bot = MagicMock()
        router = NaturalIntentRouter(mock_bot, {"db": self.db})

        mock_author = MagicMock(spec=discord.Member)
        mock_author.id = 999
        mock_author.guild_permissions = discord.Permissions(send_messages=True)  # No mod perms

        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.owner_id = 1
        mock_author.guild = mock_guild

        mock_msg = MagicMock(spec=discord.Message)
        mock_msg.guild = mock_guild
        mock_msg.author = mock_author
        mock_msg.channel = MagicMock()

        intent = {"category": "moderation", "action": "lock"}
        handled, reply, _ = await router.execute_intent(intent, mock_msg)

        self.assertTrue(handled)
        self.assertIn("permission", reply.lower())

    # =========================================================================
    # 5. SECURITY & SECRET REDACTION TESTS
    # =========================================================================

    def test_16_secret_sanitization(self):
        """Bot tokens and webhooks must be redacted from logs."""
        part1 = "MTAxMjM0NTY3ODkwMTIzNDU2Nw"
        part2 = "GABCDE"
        part3 = "1234567890123456789012345678"
        raw_token = ".".join([part1, part2, part3])
        raw_webhook = "https://" + "discord.com/api/webhooks/123/xyz"
        raw_log = f"Connected with token {raw_token} and webhook {raw_webhook}"
        sanitized = sanitize_secrets(raw_log)
        self.assertNotIn(raw_token, sanitized)
        self.assertIn("[REDACTED_SECRET]", sanitized)
        self.assertIn("[REDACTED_WEBHOOK_URL]", sanitized)

    # =========================================================================
    # 6. PERSISTENCE & USER DATA INTEGRITY TESTS
    # =========================================================================

    def test_17_user_affection_and_memory_preserved(self):
        """Existing profile affection and memory structures remain intact."""
        from kazumi import Kazumi
        kazumi = Kazumi()
        # Verify profile has loaded memory structures and affection score
        self.assertTrue(hasattr(kazumi, "memory"))
        self.assertIn("affection_level", kazumi.memory.profile)


if __name__ == "__main__":
    unittest.main()
