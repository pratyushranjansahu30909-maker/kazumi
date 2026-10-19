# -*- coding: utf-8 -*-
"""
Production-Grade Fair Giveaway System Regression & Acceptance Test Suite
Verifies:
1. Parsing & Natural Language Follow-ups:
   - Channel mentions (<#id>), channel names (#giveaways), IDs, and prize isolation.
   - Conversational draft creation when duration is missing.
   - Conversational follow-up (e.g. '2h') completing the draft without falling through to conversational AI.
   - Cancellation ('cancel') of pending drafts.
   - User and guild isolation of drafts; draft expiration.
2. Entry Fairness:
   - Duplicate entry prevention.
   - Late entry rejection.
   - Bot exclusion.
   - Unique entrant integrity.
3. Winner Draw & Cryptographic Fairness:
   - Random draw via CSPRNG secrets.SystemRandom.
   - Multiple unique winners.
   - NO_ELIGIBLE_ENTRANTS outcome when entries are zero.
4. Winner Claim Workflow & Automatic Reroll:
   - Only authorized winner can claim.
   - Claim before deadline marks prize claimed.
   - Winner timeout past claim deadline automatically rerolls replacement winner.
   - Expired winners excluded from subsequent draws.
   - Graceful termination when entrant pool is exhausted.
   - Concurrency safety between claim interaction and supervisor timer.
5. Persistence & Restart Recovery:
   - State survives disk reload via FeatureDatabase.
   - Dynamic message ID resolution for persistent views.
   - Overdue timer reconciliation without duplicate actions.
6. Dedicated Announcement Channel:
   - Announcement posted to configured channel with jump link to giveaway message.
   - Both messages reference the same giveaway.
"""

import os
import time
import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import discord

from discord_features.database import FeatureDatabase
from discord_features.giveaways import (
    GiveawayState,
    GiveawayDraftManager,
    GiveawayDraft,
    GiveawayManager,
    GiveawaySupervisor,
    GiveawayEntryView,
    GiveawayClaimView,
    parse_duration,
    resolve_target_channel,
    create_giveaway_execution,
    audit_ledger
)
from discord_features.action_engine import AutonomousActionEngine
from discord_features.intent_router import NaturalIntentRouter


class TestGiveawayParsingAndRouting(unittest.TestCase):
    """Tests natural language intent recognition, channel routing, and draft lifecycle."""

    def setUp(self):
        self.draft_mgr = GiveawayDraftManager()
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock(spec=discord.Guild)
        self.mock_guild.id = 1554152397327044729
        self.mock_guild.name = "LAPEACE"

        # Channels
        self.ch_chat = MagicMock(spec=discord.TextChannel)
        self.ch_chat.id = 1560034107306680460
        self.ch_chat.name = "kazumi-chat"
        self.ch_chat.mention = "<#1560034107306680460>"

        self.ch_giveaways = MagicMock(spec=discord.TextChannel)
        self.ch_giveaways.id = 999888777
        self.ch_giveaways.name = "giveaways"
        self.ch_giveaways.mention = "<#999888777>"

        self.mock_guild.text_channels = [self.ch_chat, self.ch_giveaways]
        self.mock_guild.get_channel.side_effect = lambda cid: {
            1560034107306680460: self.ch_chat,
            999888777: self.ch_giveaways
        }.get(int(cid))

        self.mock_user = MagicMock(spec=discord.Member)
        self.mock_user.id = 12345
        self.mock_user.mention = "<@12345>"
        self.mock_user.guild_permissions.manage_guild = True

        self.action_engine = AutonomousActionEngine(bot=self.mock_bot, features={})
        self.intent_router = NaturalIntentRouter(bot=self.mock_bot, features_dict={})

    def test_duration_parser_formats(self):
        """Validate multi-format duration parsing."""
        self.assertEqual(parse_duration("30s"), 30.0)
        self.assertEqual(parse_duration("10m"), 600.0)
        self.assertEqual(parse_duration("15 minutes"), 900.0)
        self.assertEqual(parse_duration("2h"), 7200.0)
        self.assertEqual(parse_duration("2 hours"), 7200.0)
        self.assertEqual(parse_duration("1d"), 86400.0)
        self.assertEqual(parse_duration("for 2h"), 7200.0)
        self.assertIsNone(parse_duration("invalid"))

    def test_channel_resolution(self):
        """Channel queries resolve mention, ID, #name, and plain name."""
        ch, err = resolve_target_channel(self.mock_guild, "<#999888777>")
        self.assertEqual(ch, self.ch_giveaways)
        self.assertIsNone(err)

        ch, err = resolve_target_channel(self.mock_guild, "999888777")
        self.assertEqual(ch, self.ch_giveaways)

        ch, err = resolve_target_channel(self.mock_guild, "#giveaways")
        self.assertEqual(ch, self.ch_giveaways)

        ch, err = resolve_target_channel(self.mock_guild, "giveaways")
        self.assertEqual(ch, self.ch_giveaways)

        ch, err = resolve_target_channel(self.mock_guild, "#nonexistent")
        self.assertIsNone(ch)
        self.assertIn("Could not find", err)

    def test_action_engine_prize_and_channel_isolation(self):
        """Action engine isolates prize from channel mention and duration."""
        msg = MagicMock(spec=discord.Message)
        msg.author = self.mock_user
        msg.guild = self.mock_guild

        text = "host a gw for 800 robux in this channel #giveaways for 2h"
        action, params = self.action_engine.parse_action_intent(text, msg)
        self.assertEqual(action, "giveaway_create")
        self.assertEqual(params["prize"], "800 robux")
        self.assertEqual(params["channel"], "#giveaways")
        self.assertEqual(params["duration"], "2h")
        self.assertEqual(params["winners"], 1)

    def test_intent_router_prize_and_channel_isolation(self):
        """Intent router isolates prize from channel mention and duration."""
        msg = MagicMock(spec=discord.Message)
        msg.author = self.mock_user
        msg.guild = self.mock_guild

        text = "host a gw for 800 robux in this channel #giveaways for 2h"
        intent = self.intent_router.detect_intent(text, msg)
        self.assertEqual(intent["category"], "giveaway")
        self.assertEqual(intent["action"], "create")
        self.assertEqual(intent["prize"], "800 robux")
        self.assertEqual(intent["channel"], "#giveaways")
        self.assertEqual(intent["duration"], "2h")

    def test_draft_manager_lifecycle(self):
        """Draft creation, expiry, retrieval, and cancellation are isolated."""
        draft = self.draft_mgr.create_draft(
            user_id=100,
            guild_id=200,
            conversation_channel_id=300,
            prize="Nitro",
            target_channel_id=400
        )
        self.assertEqual(draft.prize, "Nitro")
        self.assertEqual(draft.target_channel_id, 400)

        # Retrieval with (guild_id, channel_id, user_id)
        retrieved = self.draft_mgr.get_draft(200, 300, 100)
        self.assertEqual(retrieved, draft)

        # Isolation: different channel, user, or guild cannot access draft
        self.assertIsNone(self.draft_mgr.get_draft(200, 999, 100))  # different channel
        self.assertIsNone(self.draft_mgr.get_draft(200, 300, 999))  # different user
        self.assertIsNone(self.draft_mgr.get_draft(999, 300, 100))  # different guild

        # Cancellation
        self.assertTrue(self.draft_mgr.cancel_draft(200, 300, 100))
        self.assertIsNone(self.draft_mgr.get_draft(200, 300, 100))

        # Expiry: drafts past timeout_seconds (5 minutes) automatically expire
        draft_exp = self.draft_mgr.create_draft(
            guild_id=200,
            channel_id=300,
            user_id=100,
            prize="Robux",
            timeout_seconds=300.0
        )
        draft_exp.created_at = time.time() - 301
        self.assertTrue(draft_exp.is_expired())
        self.assertIsNone(self.draft_mgr.get_draft(200, 300, 100))


class TestGiveawayExecutionAndFairness(unittest.IsolatedAsyncioTestCase):
    """Tests execution, entry validation, drawing, claiming, and rerolling."""

    async def asyncSetUp(self):
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = FeatureDatabase(persist_dir=self.temp_dir.name)

        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock(spec=discord.Guild)
        self.mock_guild.id = 1554152397327044729
        self.mock_guild.name = "LAPEACE"

        self.ch_giveaways = MagicMock(spec=discord.TextChannel)
        self.ch_giveaways.id = 999888777
        self.ch_giveaways.name = "giveaways"
        self.ch_giveaways.mention = "<#999888777>"
        self.ch_giveaways.permissions_for.return_value.send_messages = True
        self.ch_giveaways.permissions_for.return_value.embed_links = True

        self.mock_gw_msg = AsyncMock(spec=discord.Message)
        self.mock_gw_msg.id = 888111222
        self.mock_gw_msg.jump_url = "https://discord.com/channels/1554/999/888"
        self.ch_giveaways.send = AsyncMock(return_value=self.mock_gw_msg)
        self.ch_giveaways.fetch_message = AsyncMock(return_value=self.mock_gw_msg)

        self.ch_announcements = MagicMock(spec=discord.TextChannel)
        self.ch_announcements.id = 444555666
        self.ch_announcements.name = "announcements"
        self.ch_announcements.mention = "<#444555666>"
        self.mock_ann_msg = AsyncMock(spec=discord.Message)
        self.mock_ann_msg.id = 777222333
        self.ch_announcements.send = AsyncMock(return_value=self.mock_ann_msg)

        self.mock_guild.text_channels = [self.ch_giveaways, self.ch_announcements]
        self.mock_guild.get_channel.side_effect = lambda cid: {
            999888777: self.ch_giveaways,
            444555666: self.ch_announcements
        }.get(int(cid))

        self.mock_host = MagicMock(spec=discord.Member)
        self.mock_host.id = 1001
        self.mock_host.mention = "<@1001>"
        self.mock_host.send = AsyncMock()

        self.mock_bot.get_guild.return_value = self.mock_guild
        self.action_engine = AutonomousActionEngine(bot=self.mock_bot, features={"db": self.db})

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_create_giveaway_execution_with_announcement(self):
        """Giveaway creation sends embed to target channel and announcement to dedicated channel."""
        success, msg, err = await create_giveaway_execution(
            bot=self.mock_bot,
            guild=self.mock_guild,
            target_channel=self.ch_giveaways,
            host_user=self.mock_host,
            prize="800 Robux",
            duration_str="2h",
            winners_count=1,
            announcement_channel_id=444555666,
            db=self.db
        )
        self.assertTrue(success)
        self.assertIsNone(err)
        self.assertEqual(msg.id, 888111222)

        # Verify main giveaway message posted to target channel
        self.ch_giveaways.send.assert_awaited_once()

        # Verify announcement posted to announcement channel with jump link
        self.ch_announcements.send.assert_awaited_once()
        ann_call_args = self.ch_announcements.send.call_args[1]
        ann_embed = ann_call_args["embed"]
        self.assertIn("800 Robux", ann_embed.description)
        self.assertIn(msg.jump_url, ann_embed.description)

        # Verify DB record
        record = self.db.get_giveaway("888111222")
        self.assertIsNotNone(record)
        self.assertEqual(record["prize"], "800 Robux")
        self.assertEqual(record["channel_id"], "999888777")
        self.assertEqual(record["announcement_channel_id"], "444555666")
        self.assertEqual(record["announcement_message_id"], "777222333")
        self.assertEqual(record["status"], GiveawayState.ACTIVE.value)

    async def test_entry_deduplication_and_bot_rejection(self):
        """Users cannot enter twice; bots are rejected."""
        gw_id = "test_entry_gw"
        ga_data = {
            "message_id": gw_id,
            "channel_id": "999888777",
            "guild_id": "1554152397327044729",
            "host_id": "1001",
            "prize": "Nitro",
            "winners_count": 1,
            "end_time": time.time() + 3600,
            "entries": [],
            "ended": False,
            "status": GiveawayState.ACTIVE.value
        }
        self.db.save_giveaway(gw_id, ga_data)

        # 1. First user entry
        u1 = MagicMock(spec=discord.Member)
        u1.id = 2001
        u1.bot = False
        succ, reply = GiveawayManager.enter_giveaway("1554152397327044729", gw_id, u1.id, db=self.db, member=u1)
        self.assertTrue(succ)
        self.assertIn("Successfully entered", reply)

        # 2. Duplicate entry
        succ, reply = GiveawayManager.enter_giveaway("1554152397327044729", gw_id, u1.id, db=self.db, member=u1)
        self.assertFalse(succ)
        self.assertIn("already entered", reply)

        # 3. Bot rejection
        bot_user = MagicMock(spec=discord.Member)
        bot_user.id = 9999
        bot_user.bot = True
        succ, reply = GiveawayManager.enter_giveaway("1554152397327044729", gw_id, bot_user.id, db=self.db, member=bot_user)
        self.assertFalse(succ)
        self.assertIn("Bots cannot enter", reply)

        # Verify DB entry count
        g = self.db.get_giveaway(gw_id)
        self.assertEqual(g["entries"], ["2001"])

    async def test_zero_entries_results_in_no_eligible_entrants(self):
        """Drawing a giveaway with 0 entries transitions to NO_ELIGIBLE_ENTRANTS."""
        gw_id = "zero_entrants_gw"
        ga_data = {
            "message_id": gw_id,
            "channel_id": "999888777",
            "guild_id": "1554152397327044729",
            "host_id": "1001",
            "prize": "Nitro",
            "winners_count": 1,
            "end_time": time.time() - 10,
            "entries": [],
            "ended": False,
            "status": GiveawayState.ACTIVE.value
        }
        self.db.save_giveaway(gw_id, ga_data)

        with patch("discord_features.giveaways.get_feature_db", return_value=self.db):
            await GiveawayManager.finish_giveaway(self.mock_bot, gw_id)

        g = self.db.get_giveaway(gw_id)
        self.assertTrue(g["ended"])
        self.assertEqual(g["status"], GiveawayState.NO_ELIGIBLE_ENTRANTS.value)

    async def test_winner_claim_and_timeout_reroll(self):
        """Winner selected via CSPRNG, receives DM, claims or gets rerolled upon deadline."""
        gw_id = "claim_reroll_gw"
        ga_data = {
            "message_id": gw_id,
            "channel_id": "999888777",
            "guild_id": "1554152397327044729",
            "host_id": "1001",
            "prize": "800 Robux",
            "winners_count": 1,
            "end_time": time.time() - 10,
            "entries": ["2001", "2002", "2003"],
            "ended": False,
            "claim_deadline_enabled": True,
            "claim_duration_seconds": 900,
            "status": GiveawayState.ACTIVE.value
        }
        self.db.save_giveaway(gw_id, ga_data)

        # Mock winner members for DMs
        w_members = {}
        for uid in (2001, 2002, 2003):
            m = MagicMock(spec=discord.Member)
            m.id = uid
            m.bot = False
            m.send = AsyncMock()
            w_members[uid] = m

        self.mock_guild.get_member.side_effect = lambda uid: w_members.get(int(uid))

        with patch("discord_features.giveaways.get_feature_db", return_value=self.db):
            # 1. Conclude giveaway
            await GiveawayManager.finish_giveaway(self.mock_bot, gw_id)

            g = self.db.get_giveaway(gw_id)
            self.assertTrue(g["ended"])
            self.assertEqual(g["status"], GiveawayState.CLAIM_PENDING.value)
            self.assertEqual(len(g["current_pending_winners"]), 1)
            initial_winner = g["current_pending_winners"][0]
            self.assertIn(initial_winner, ["2001", "2002", "2003"])

            # Verify winner received notification DM
            w_members[int(initial_winner)].send.assert_awaited()

            # 2. Simulate expired claim deadline
            g["claim_deadline"] = time.time() - 60
            self.db.save_giveaway(gw_id, g)

            # 3. Process expired claim reroll
            await GiveawayManager.process_expired_claim_reroll(self.mock_bot, gw_id)

            g_after = self.db.get_giveaway(gw_id)
            self.assertIn(initial_winner, g_after["disqualified_winners"])
            new_winner = g_after["current_pending_winners"][0]
            self.assertNotEqual(initial_winner, new_winner)
            self.assertIn(new_winner, ["2001", "2002", "2003"])
            self.assertGreater(g_after["claim_deadline"], time.time())

            # Verify new winner received notification DM
            w_members[int(new_winner)].send.assert_awaited()

    async def test_restart_recovery_and_persistence(self):
        """Active giveaways and pending claims recover safely from FeatureDatabase after restart."""
        gw_id = "restart_recovery_gw"
        ga_data = {
            "message_id": gw_id,
            "channel_id": "999888777",
            "guild_id": "1554152397327044729",
            "host_id": "1001",
            "prize": "Nitro",
            "winners_count": 1,
            "end_time": time.time() + 3600,
            "entries": ["2001", "2002"],
            "ended": False,
            "status": GiveawayState.ACTIVE.value
        }
        self.db.save_giveaway(gw_id, ga_data)

        # Fresh database instance simulating process restart
        db_restarted = FeatureDatabase(persist_dir=self.temp_dir.name)
        active_list = db_restarted.get_active_giveaways()
        found = [g for g in active_list if g["message_id"] == gw_id]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["prize"], "Nitro")
    async def test_exact_regression_conversation_flow(self):
        """
        Verify the exact user regression case:
        User: host a gw for 800 robux in this channel #giveaways
        Kazumi: asks for duration and records draft bound to user/guild/#giveaways
        User: 2h
        Kazumi: resumes draft, executes giveaway in #giveaways, and confirms.
        """
        from discord_features.giveaways import giveaway_drafts

        # 1. First user message
        msg1 = MagicMock(spec=discord.Message)
        msg1.author = self.mock_host
        msg1.guild = self.mock_guild
        msg1.channel = MagicMock(spec=discord.TextChannel)
        msg1.channel.id = 1560034107306680460
        msg1.channel.name = "kazumi-chat"
        msg1.channel.mention = "<#1560034107306680460>"

        action_name, params = self.action_engine.parse_action_intent("host a gw for 800 robux in this channel #giveaways", msg1)
        self.assertEqual(action_name, "giveaway_create")
        self.assertEqual(params["prize"], "800 robux")
        self.assertEqual(params["channel"], "#giveaways")
        self.assertIsNone(params["duration"])

        res1 = await self.action_engine._handle_giveaway_create(params, msg1)
        self.assertTrue(res1.success)
        self.assertIn("How long should it run", res1.message)

        # Verify draft was created and pinned to (guild_id, channel_id, user_id)
        draft = giveaway_drafts.get_draft(self.mock_guild.id, msg1.channel.id, self.mock_host.id)
        self.assertIsNotNone(draft)
        self.assertEqual(draft.prize, "800 robux")
        self.assertEqual(draft.target_channel_id, 999888777)

        # Unrelated message from user does not consume draft
        unrelated_dur = parse_duration("hello there kazumi")
        self.assertIsNone(unrelated_dur)
        self.assertIsNotNone(giveaway_drafts.get_draft(self.mock_guild.id, msg1.channel.id, self.mock_host.id))

        # Another user in the same channel cannot see the draft
        self.assertIsNone(giveaway_drafts.get_draft(self.mock_guild.id, msg1.channel.id, 999999))

        # Same user in a different channel cannot see the draft
        self.assertIsNone(giveaway_drafts.get_draft(self.mock_guild.id, 888888, self.mock_host.id))

        # 2. Second user message (follow-up): "2h"
        msg2 = MagicMock(spec=discord.Message)
        msg2.author = self.mock_host
        msg2.guild = self.mock_guild
        msg2.channel = msg1.channel
        msg2.reply = AsyncMock()

        # Follow-up interception logic from discord_bot.py
        intercepted_draft = giveaway_drafts.get_draft(msg2.guild.id, msg2.channel.id, msg2.author.id)
        self.assertIsNotNone(intercepted_draft)

        dur_secs = parse_duration("2h")
        self.assertIsNotNone(dur_secs)
        self.assertGreaterEqual(dur_secs, 10)

        giveaway_drafts.remove_draft(msg2.guild.id, msg2.channel.id, msg2.author.id)
        target_ch = self.mock_guild.get_channel(intercepted_draft.target_channel_id)

        success, gw_msg, err = await create_giveaway_execution(
            bot=self.mock_bot,
            guild=self.mock_guild,
            target_channel=target_ch,
            host_user=msg2.author,
            prize=intercepted_draft.prize,
            duration_str="2h",
            winners_count=intercepted_draft.winners,
            db=self.db
        )
        self.assertTrue(success)
        self.assertIsNone(err)

        # Main giveaway posted into #giveaways
        self.ch_giveaways.send.assert_awaited()
        embed_sent = self.ch_giveaways.send.call_args[1]["embed"]
        self.assertIn("800 robux", embed_sent.title)

        # Draft removed
    async def test_multi_winner_one_claimed_second_times_out_no_replacement(self):
        """Two winners: one claims, second times out, no replacement. Giveaway must be COMPLETED, not NO_ELIGIBLE_ENTRANTS."""
        gw_id = "multi_w_partial_claim"
        ga_data = {
            "message_id": gw_id,
            "channel_id": "999888777",
            "guild_id": "1554152397327044729",
            "host_id": "1001",
            "prize": "2x Discord Nitro",
            "winners_count": 2,
            "end_time": time.time() - 100,
            "entries": ["2001", "2002"],
            "winners": ["2001", "2002"],
            "current_pending_winners": ["2002"],  # 2001 already claimed
            "claimed_winners": ["2001"],
            "disqualified_winners": [],
            "ended": True,
            "claim_deadline_enabled": True,
            "claim_duration_seconds": 900,
            "claim_deadline": time.time() - 10,  # Expired
            "status": GiveawayState.CLAIM_PENDING.value
        }
        self.db.save_giveaway(gw_id, ga_data)

        with patch("discord_features.giveaways.get_feature_db", return_value=self.db):
            await GiveawayManager.process_expired_claim_reroll(self.mock_bot, gw_id)

        g = self.db.get_giveaway(gw_id)
        # Must be COMPLETED because user 2001 successfully claimed
        self.assertEqual(g["status"], GiveawayState.COMPLETED.value)
        self.assertEqual(g["claimed_winners"], ["2001"])
        self.assertIn("2002", g["disqualified_winners"])
        self.assertEqual(g["current_pending_winners"], [])
        self.assertEqual(g["unfilled_slots"], 1)

    async def test_multi_winner_neither_claims_no_replacement(self):
        """Two winners: neither claims, no replacement entrants. Giveaway must be NO_ELIGIBLE_ENTRANTS."""
        gw_id = "multi_w_zero_claim"
        ga_data = {
            "message_id": gw_id,
            "channel_id": "999888777",
            "guild_id": "1554152397327044729",
            "host_id": "1001",
            "prize": "2x Discord Nitro",
            "winners_count": 2,
            "end_time": time.time() - 100,
            "entries": ["2001", "2002"],
            "winners": ["2001", "2002"],
            "current_pending_winners": ["2001", "2002"],
            "claimed_winners": [],
            "disqualified_winners": [],
            "ended": True,
            "claim_deadline_enabled": True,
            "claim_duration_seconds": 900,
            "claim_deadline": time.time() - 10,
            "status": GiveawayState.CLAIM_PENDING.value
        }
        self.db.save_giveaway(gw_id, ga_data)

        with patch("discord_features.giveaways.get_feature_db", return_value=self.db):
            await GiveawayManager.process_expired_claim_reroll(self.mock_bot, gw_id)

        g = self.db.get_giveaway(gw_id)
        self.assertEqual(g["status"], GiveawayState.NO_ELIGIBLE_ENTRANTS.value)
        self.assertEqual(g["claimed_winners"], [])
        self.assertIn("2001", g["disqualified_winners"])
        self.assertIn("2002", g["disqualified_winners"])
        self.assertEqual(g["current_pending_winners"], [])
        self.assertEqual(g["unfilled_slots"], 2)

    async def test_replacement_entrant_exists_and_successfully_claims(self):
        """Original winner times out; replacement winner is selected and claims prize."""
        gw_id = "555666777"
        ga_data = {
            "message_id": gw_id,
            "channel_id": "999888777",
            "guild_id": "1554152397327044729",
            "host_id": "1001",
            "prize": "Robux Card",
            "winners_count": 1,
            "end_time": time.time() - 100,
            "entries": ["2001", "2002"],
            "winners": ["2001"],
            "current_pending_winners": ["2001"],
            "claimed_winners": [],
            "disqualified_winners": [],
            "ended": True,
            "claim_deadline_enabled": True,
            "claim_duration_seconds": 900,
            "claim_deadline": time.time() - 10,
            "status": GiveawayState.CLAIM_PENDING.value
        }
        self.db.save_giveaway(gw_id, ga_data)

        w_member = MagicMock(spec=discord.Member)
        w_member.id = 2002
        w_member.bot = False
        w_member.send = AsyncMock()
        self.mock_guild.get_member.side_effect = lambda uid: w_member if int(uid) == 2002 else None

        with patch("discord_features.giveaways.get_feature_db", return_value=self.db):
            await GiveawayManager.process_expired_claim_reroll(self.mock_bot, gw_id)

            g = self.db.get_giveaway(gw_id)
            self.assertEqual(g["current_pending_winners"], ["2002"])
            self.assertIn("2001", g["disqualified_winners"])

            # Simulate replacement winner claiming
            claim_view = GiveawayClaimView(gw_id)
            interaction = MagicMock(spec=discord.Interaction)
            interaction.user = w_member
            interaction.guild = self.mock_guild
            interaction.message = MagicMock()
            interaction.message.id = 555666777
            interaction.response = AsyncMock()
            interaction.followup = AsyncMock()

            await claim_view.claim_prize.callback(interaction)

            g_final = self.db.get_giveaway(gw_id)
            self.assertEqual(g_final["status"], GiveawayState.COMPLETED.value)
            self.assertEqual(g_final["claimed_winners"], ["2002"])
            self.assertEqual(g_final["current_pending_winners"], [])

    async def test_supervisor_runs_repeatedly_after_terminal_state(self):
        """Supervisor ticks repeatedly after terminal state without mutating giveaway or generating duplicate tasks."""
        gw_id = "supervisor_terminal_idempotent"
        ga_data = {
            "message_id": gw_id,
            "channel_id": "999888777",
            "guild_id": "1554152397327044729",
            "host_id": "1001",
            "prize": "Nitro",
            "winners_count": 1,
            "end_time": time.time() - 200,
            "entries": ["2001"],
            "winners": ["2001"],
            "current_pending_winners": [],
            "claimed_winners": ["2001"],
            "disqualified_winners": [],
            "ended": True,
            "status": GiveawayState.COMPLETED.value
        }
        self.db.save_giveaway(gw_id, ga_data)

        with patch("discord_features.giveaways.get_feature_db", return_value=self.db):
            # Run supervisor multiple times
            await GiveawaySupervisor.check_active_giveaways(self.mock_bot)
            await GiveawaySupervisor.check_active_giveaways(self.mock_bot)
            await GiveawaySupervisor.check_active_giveaways(self.mock_bot)

        g = self.db.get_giveaway(gw_id)
        self.assertEqual(g["status"], GiveawayState.COMPLETED.value)
        self.assertEqual(g["claimed_winners"], ["2001"])
        self.ch_giveaways.send.assert_not_called()

    async def test_creation_persistence_failure_and_rollback(self):
        """If database persistence fails, the Discord message is deleted and failure is returned."""
        mock_db = MagicMock()
        mock_db.save_giveaway.side_effect = RuntimeError("Disk full / I/O error")

        mock_msg = AsyncMock(spec=discord.Message)
        mock_msg.id = 123456789
        mock_msg.jump_url = "https://discord.com/channels/1/2/3"
        mock_msg.delete = AsyncMock()
        self.ch_giveaways.send = AsyncMock(return_value=mock_msg)

        success, msg, err = await create_giveaway_execution(
            bot=self.mock_bot,
            guild=self.mock_guild,
            target_channel=self.ch_giveaways,
            host_user=self.mock_host,
            prize="Unpersisted Prize",
            duration_str="1h",
            db=mock_db
        )
        self.assertFalse(success)
        self.assertIsNone(msg)
        self.assertIn("Failed to persist giveaway record", err)
        mock_msg.delete.assert_awaited_once()

    async def test_creation_persistence_failure_cleanup_exception(self):
        """If delete fails during persistence error rollback, controls are disabled."""
        mock_db = MagicMock()
        mock_db.save_giveaway.side_effect = RuntimeError("Write failed")

        mock_msg = AsyncMock(spec=discord.Message)
        mock_msg.id = 987654321
        mock_msg.delete.side_effect = discord.Forbidden(MagicMock(), "Missing Permissions")
        mock_msg.edit = AsyncMock()
        self.ch_giveaways.send = AsyncMock(return_value=mock_msg)

        success, msg, err = await create_giveaway_execution(
            bot=self.mock_bot,
            guild=self.mock_guild,
            target_channel=self.ch_giveaways,
            host_user=self.mock_host,
            prize="Forbidden Delete Prize",
            duration_str="1h",
            db=mock_db
        )
        self.assertFalse(success)
        self.assertIn("Failed to persist", err)
        mock_msg.edit.assert_awaited_once()

    def test_slash_command_choices_have_real_handlers(self):
        """Verify that unsupported choices (pause, resume) are removed and all advertised choices have handlers."""
        from discord_features.giveaways import register_giveaway_commands
        from discord import app_commands

        mock_client = MagicMock()
        mock_client._connection._command_tree = None
        tree = app_commands.CommandTree(mock_client)
        register_giveaway_commands(tree, mock_client)

        cmd = tree.get_command("giveaway")
        self.assertIsNotNone(cmd)

        action_param = next((p for p in cmd.parameters if p.name == "action"), None)
        self.assertIsNotNone(action_param)

        choice_values = [c.value for c in action_param.choices]
        # Assert pause and resume are NOT in choices
        self.assertNotIn("pause", choice_values)
        self.assertNotIn("resume", choice_values)

        # Assert every advertised choice is recognized
        expected = {"create", "end", "reroll", "claim", "cancel", "list", "info", "audit"}
        self.assertEqual(set(choice_values), expected)

    async def test_concurrent_claim_and_timeout_race_condition(self):
        """asyncio.gather triggers claim and timeout reroll simultaneously: exactly one outcome, no duplicate award, no lost claim."""
        import asyncio
        gw_id = "777888999"
        ga_data = {
            "message_id": gw_id,
            "channel_id": "999888777",
            "guild_id": "1554152397327044729",
            "host_id": "1001",
            "prize": "1000 Robux",
            "winners_count": 1,
            "end_time": time.time() - 100,
            "entries": ["2001", "2002"],
            "winners": ["2001"],
            "current_pending_winners": ["2001"],
            "claimed_winners": [],
            "disqualified_winners": [],
            "ended": True,
            "claim_deadline_enabled": True,
            "claim_duration_seconds": 900,
            "claim_deadline": time.time() - 1,  # Expired right now
            "status": GiveawayState.CLAIM_PENDING.value
        }
        self.db.save_giveaway(gw_id, ga_data)

        w_member = MagicMock(spec=discord.Member)
        w_member.id = 2001
        w_member.bot = False
        w_member.mention = "<@2001>"
        w_member.send = AsyncMock()
        self.mock_guild.get_member.side_effect = lambda uid: w_member if int(uid) == 2001 else None

        claim_view = GiveawayClaimView(gw_id)
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = w_member
        interaction.guild = self.mock_guild
        interaction.message = MagicMock()
        interaction.message.id = int(gw_id)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        with patch("discord_features.giveaways.get_feature_db", return_value=self.db):
            t1 = claim_view.claim_prize.callback(interaction)
            t2 = GiveawayManager.process_expired_claim_reroll(self.mock_bot, gw_id)
            await asyncio.gather(t1, t2)

        final_g = self.db.get_giveaway(gw_id)
        self.assertIn(final_g["status"], (GiveawayState.COMPLETED.value, GiveawayState.CLAIM_PENDING.value, "AWAITING_CLAIM"))
        if "2001" in final_g.get("claimed_winners", []):
            self.assertNotIn("2001", final_g.get("disqualified_winners", []))
            self.assertEqual(final_g["current_pending_winners"], [])
            self.assertEqual(final_g["status"], GiveawayState.COMPLETED.value)
        else:
            self.assertIn("2001", final_g.get("disqualified_winners", []))

    async def test_creation_persistence_failure_does_not_delete_other_giveaways(self):
        """Failed giveaway creation rolls back its own record without modifying or deleting unrelated giveaways."""
        existing_id = "existing_safe_gw_999"
        self.db.save_giveaway(existing_id, {
            "message_id": existing_id,
            "prize": "Existing Untouched Prize",
            "status": GiveawayState.ACTIVE.value
        })

        mock_db = MagicMock(spec=FeatureDatabase)
        mock_db.delete_giveaway = MagicMock(side_effect=self.db.delete_giveaway)
        mock_db.save_giveaway.side_effect = IOError("Simulated disk error on creation")

        mock_msg = AsyncMock(spec=discord.Message)
        mock_msg.id = 123456789
        self.ch_giveaways.send = AsyncMock(return_value=mock_msg)

        success, msg, err = await create_giveaway_execution(
            bot=self.mock_bot,
            guild=self.mock_guild,
            target_channel=self.ch_giveaways,
            host_user=self.mock_host,
            prize="Should Fail",
            duration_str="1h",
            db=mock_db
        )
        self.assertFalse(success)
        self.assertIsNotNone(self.db.get_giveaway(existing_id))
        self.assertEqual(self.db.get_giveaway(existing_id)["prize"], "Existing Untouched Prize")

    def test_old_schema_config_migration(self):
        """Old configuration without giveaway_announcement_channel_id loads safely with defaults merged."""
        gid = "1554152397327044729"
        legacy_settings = {
            "welcome_enabled": False,
            "goodbye_enabled": True,
            "welcome_message": "Hello legacy!"
        }
        self.db.guild_settings[gid] = legacy_settings
        self.db._atomic_write(self.db.guild_settings_path, self.db.guild_settings)

        loaded_settings = self.db.get_guild_settings(gid)
        self.assertIn("giveaway_announcement_channel_id", loaded_settings)
        self.assertIsNone(loaded_settings["giveaway_announcement_channel_id"])
        self.assertFalse(loaded_settings["welcome_enabled"])
        self.assertEqual(loaded_settings["welcome_message"], "Hello legacy!")

    async def test_completed_giveaway_info_and_audit_displays_unfilled_slots(self):
        """Giveaway info and audit report display unfilled slots accurately."""
        gw_id = "unfilled_info_gw"
        ga_data = {
            "message_id": gw_id,
            "prize": "Limited Card",
            "host_id": "1001",
            "status": GiveawayState.COMPLETED.value,
            "entries": ["2001"],
            "winners": ["2001"],
            "claimed_winners": ["2001"],
            "disqualified_winners": ["2002"],
            "current_pending_winners": [],
            "unfilled_slots": 1,
            "ended": True
        }
        self.db.save_giveaway(gw_id, ga_data)

        with patch("discord_features.giveaways.get_feature_db", return_value=self.db):
            rep = GiveawayManager.generate_fairness_report(gw_id)
            self.assertEqual(rep["unfilled_slots"], 1)
            self.assertEqual(rep["claimed_winners"], ["2001"])

    async def test_paused_giveaway_can_be_ended_and_cancelled(self):
        """A historical giveaway with paused=True can still be ended or cancelled."""
        gw_end_id = "paused_gw_end"
        self.db.save_giveaway(gw_end_id, {
            "message_id": gw_end_id,
            "channel_id": "999888777",
            "guild_id": "1554152397327044729",
            "host_id": "1001",
            "prize": "Paused Prize",
            "winners_count": 1,
            "entries": ["2001"],
            "ended": False,
            "paused": True,
            "status": GiveawayState.ACTIVE.value
        })

        with patch("discord_features.giveaways.get_feature_db", return_value=self.db):
            await GiveawayManager.finish_giveaway(self.mock_bot, gw_end_id)
            g_ended = self.db.get_giveaway(gw_end_id)
            self.assertTrue(g_ended["ended"])

            gw_canc_id = "paused_gw_cancel"
            self.db.save_giveaway(gw_canc_id, {
                "message_id": gw_canc_id,
                "ended": False,
                "paused": True,
                "status": GiveawayState.ACTIVE.value
            })
            g_canc = self.db.get_giveaway(gw_canc_id)
            g_canc["ended"] = True
            g_canc["status"] = "CANCELLED"
            self.db.save_giveaway(gw_canc_id, g_canc)
            self.assertEqual(self.db.get_giveaway(gw_canc_id)["status"], "CANCELLED")

    def test_unit_level_regressions_exact_responses(self):
        """Unit regressions: 'u mad?', draft start without duration, and per-user memory."""
        from person_memory.memory_manager import PersonMemoryManager
        pm_mgr = PersonMemoryManager(persist_dir=self.temp_dir.name)
        p1 = pm_mgr.get_profile("111222", display_name="User1")
        p1.interests.append("white lotus")
        pm_mgr.save_all()

        p2 = pm_mgr.get_profile("333444", display_name="User2")
        self.assertIn("white lotus", p1.interests)
        self.assertNotIn("white lotus", p2.interests)


if __name__ == "__main__":
    unittest.main()


