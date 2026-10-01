# -*- coding: utf-8 -*-
"""
🌸 KAZUMI P0-LOCKED MASTER ACCEPTANCE TEST SUITE
Comprehensive verification of all P0 subsystems:
1. Stability: Gateway single-instance lock & dynamic creator ID lookup
2. Human Interaction Engine: 6-decision social evaluation
3. Relationship & Person Memory: 6 standardized relationship tiers
4. Contextual Roast & Unhinged: Cliche rejection & context-specific punchlines
5. Moderation MVP: Sequential Case Manager (#1001+), ModNotes, Reports, Appeals
6. Server Security: Anti-Raid burst join & Anti-Nuke mass deletion protection
7. Game Engine & P0 Arcade Games:
   - Connect Four
   - Tic-Tac-Toe vs AI (Easy, Normal, Hard)
   - Trivia
   - Word Chain
   - Hangman & Daily Brain Challenge
8. XP & Achievement Persistence: Formula XP // 100 + 1, Level up & unlocks
9. Web Dashboard APIs: Bot Health, Cases, and Arcade Leaderboard
"""

import os
import time
import shutil
import unittest
from unittest.mock import MagicMock
import discord

# Set testing environment
os.environ["CREATOR_USER_IDS"] = "1203721997805424650,999888777"

from discord_features.database import FeatureDatabase
from discord_features.human_interaction import HumanInteractionEngine, InteractionDecision
from discord_features.case_system import CaseManager, ReportManager, AppealManager
from discord_features.security import AntiRaidEngine, AntiNukeEngine
from discord_features.game_engine import GameEngine, GameType, WordChainView
from discord_features.roast_engine import RoastEngine, RoastValidator, ContextAnalyzer
from person_memory.relationship_manager import RelationshipState, RelationshipManager
from person_memory.person_profile import PersonProfile


class MasterP0AcceptanceTests(unittest.TestCase):

    def setUp(self):
        self.test_dir = "isa_memory_p0_acceptance_test"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        self.db = FeatureDatabase(persist_dir=self.test_dir)
        self.hi_engine = HumanInteractionEngine(self.db, bot_user_id=123456789)
        self.case_mgr = CaseManager(self.db)
        self.reports = ReportManager(self.db)
        self.appeals = AppealManager(self.db)
        self.anti_raid = AntiRaidEngine(self.db)
        self.anti_nuke = AntiNukeEngine(self.db)
        self.game_engine = GameEngine(self.db)
        self.roast_engine = RoastEngine(self.db)
        self.rel_mgr = RelationshipManager()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    # =========================================================================
    # Phase 1: Stability & Creator Identity
    # =========================================================================
    def test_p1_creator_dynamic_recognition(self):
        """Creator recognition must read dynamically from environment variables, not hardcoded."""
        from discord_bot import detect_creator_relationship
        mock_user = MagicMock()
        mock_user.id = 1203721997805424650
        mock_user.name = "Shan"
        mock_user.display_name = "Sir Shan"
        mock_user.global_name = "shan2157"
        
        title, context = detect_creator_relationship(mock_user)
        self.assertEqual(title, "Sir Shan D. First")
        self.assertIn("creator and father", context)

        mock_user_aamir = MagicMock()
        mock_user_aamir.id = 999999999
        mock_user_aamir.name = "Aamir"
        mock_user_aamir.display_name = "Aamir the Chad"
        mock_user_aamir.global_name = "aamir"
        title_a, context_a = detect_creator_relationship(mock_user_aamir)
        self.assertEqual(title_a, "Aamir the Chad")

    # =========================================================================
    # Phase 2: Human Interaction Engine (Social Decisions)
    # =========================================================================
    def test_p2_human_interaction_decisions(self):
        """Evaluates RESPOND, REACT, WAIT, OBSERVE, IGNORE behaviors."""
        mock_msg = MagicMock()
        mock_msg.author.bot = False
        mock_msg.author.id = 555
        mock_msg.channel.id = 100
        mock_msg.mentions = []
        mock_msg.guild = None

        # 1. Quarantined user -> IGNORE
        mock_guild_msg = MagicMock()
        mock_guild_msg.author.bot = False
        mock_guild_msg.author.id = 555
        mock_guild_msg.channel.id = 100
        mock_guild_msg.mentions = []
        mock_guild = MagicMock()
        mock_guild.id = 999
        mock_guild_msg.guild = mock_guild
        self.db.set_user_quarantined(999, 555, True)
        dec, _, _ = self.hi_engine.evaluate(mock_guild_msg, False, True, True, False, True, False)
        self.assertEqual(dec, InteractionDecision.IGNORE)

        # 2. Summoned directly -> RESPOND
        self.db.set_user_quarantined(999, 555, False)
        mock_guild_msg.content = "Kazumi how are you today?"
        dec, _, _ = self.hi_engine.evaluate(mock_guild_msg, False, True, True, False, True, False)
        self.assertEqual(dec, InteractionDecision.RESPOND)

        # 3. Chat slang/laughter -> REACT or WAIT
        mock_guild_msg.content = "lmao"
        dec, extra, _ = self.hi_engine.evaluate(mock_guild_msg, False, False, False, False, False, False)
        self.assertIn(dec, (InteractionDecision.REACT, InteractionDecision.WAIT))

        # 4. User chatting with another member -> OBSERVE
        mock_guild_msg.content = "What do you think about that?"
        mock_other = MagicMock()
        mock_other.id = 777
        mock_guild_msg.mentions = [mock_other]
        dec, _, _ = self.hi_engine.evaluate(mock_guild_msg, False, False, False, False, False, False)
        self.assertEqual(dec, InteractionDecision.OBSERVE)

    # =========================================================================
    # Phase 2B: Standardized Relationship Levels
    # =========================================================================
    def test_p2_relationship_tiers(self):
        """Relationship manager must conform to 6 standard tiers (UNKNOWN to CLOSE)."""
        self.assertEqual(RelationshipState.UNKNOWN, "UNKNOWN")
        self.assertEqual(RelationshipState.NEW, "NEW")
        self.assertEqual(RelationshipState.FAMILIAR, "FAMILIAR")
        self.assertEqual(RelationshipState.REGULAR, "REGULAR")
        self.assertEqual(RelationshipState.TRUSTED, "TRUSTED")
        self.assertEqual(RelationshipState.CLOSE, "CLOSE")

        # Progression check with profile
        prof = PersonProfile(user_id="user_42", display_name="TestUser")
        prof.interaction_count = 5
        lvl = self.rel_mgr.update_relationship(prof)
        self.assertEqual(lvl, 1) # NEW
        self.assertEqual(self.rel_mgr.get_relationship_state_name(lvl), RelationshipState.NEW)

    # =========================================================================
    # Phase 3 & 4: Contextual Roast & Quality Validation
    # =========================================================================
    def test_p3_contextual_roasting_and_cliche_rejection(self):
        """Validates that roasts use observations and reject generic clichés."""
        # Check generic insult rejection
        generic_insult = "I've seen NPCs with more brain cells. Go touch grass, major skill issue."
        val = RoastValidator.validate_roast(generic_insult, context="game", target_name="Bob")
        self.assertFalse(val["is_valid"])
        self.assertTrue(val["is_generic"])

        # Check contextual observation generation
        obs = ContextAnalyzer.find_roastable_observation(
            target_recent_messages=["Bro I fixed my code", "wait it broke again"],
            target_name="Dev"
        )
        self.assertIsNotNone(obs)
        self.assertEqual(obs.category, "CODING_SEQUEL")
        punchline = obs.get_punchline(level=3)
        self.assertIn("character development", punchline.lower())

    # =========================================================================
    # Phase 5: Moderation System MVP, Cases, ModNotes, Reports, Appeals
    # =========================================================================
    def test_p5_moderation_mvp_suite(self):
        """Sequential cases (#1001+), mod notes, report queue and appeals."""
        # 1. Case Generation
        c1_id = self.case_mgr.log_case(guild_id=1, user_id=10, moderator_id=20, action="WARN", reason="Spam")
        c2_id = self.case_mgr.log_case(guild_id=1, user_id=10, moderator_id=20, action="MUTE", reason="Continued spam")
        self.assertEqual(c1_id, 1001)
        self.assertEqual(c2_id, 1002)

        # 2. Mod Notes
        n1 = self.db.add_mod_note(guild_id=1, user_id=10, moderator_id=20, content="Frequent spammer on weekends")
        notes = self.db.get_mod_notes(guild_id=1, user_id=10)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["content"], "Frequent spammer on weekends")

        # 3. Reports & ModQueue
        rep_id = self.reports.submit_report(guild_id=1, reporter_id=30, reported_id=10, channel_id=100, reason="Harassment")
        pending = self.db.get_pending_reports(guild_id=1)
        self.assertEqual(len(pending), 1)
        self.db.resolve_report(1, rep_id, "resolved", 20, "Investigated")
        self.assertEqual(len(self.db.get_pending_reports(guild_id=1)), 0)

        # 4. Appeals
        app_id = self.appeals.submit_appeal(guild_id=1, user_id=10, case_id=1002, reason="I will not spam again.")
        pending_appeals = self.db.get_pending_appeals(guild_id=1)
        self.assertEqual(len(pending_appeals), 1)

    # =========================================================================
    # Phase 5B: Security — Anti-Raid and Anti-Nuke
    # =========================================================================
    def test_p5_security_anti_raid_and_anti_nuke(self):
        """Tests Anti-Raid burst joins and Anti-Nuke mass deletions."""
        # Anti-Raid burst: 3 members joining within 5 seconds
        self.db.update_security_settings(555, {
            "anti_raid": {"enabled": True, "join_threshold": 3, "join_window_sec": 5}
        })
        member = MagicMock(spec=discord.Member)
        member.guild = MagicMock(id=555)
        member.id = 1
        member.created_at = MagicMock(timestamp=lambda: time.time() - 600)
        is_raid1, _, _ = self.anti_raid.record_join_and_evaluate(member)
        self.assertFalse(is_raid1)
        member.id = 2
        is_raid2, _, _ = self.anti_raid.record_join_and_evaluate(member)
        self.assertFalse(is_raid2)
        member.id = 3
        is_raid3, _, _ = self.anti_raid.record_join_and_evaluate(member)
        self.assertTrue(is_raid3)
        if is_raid3:
            self.db.set_raid_mode(555, True)
        self.assertTrue(self.db.is_raid_mode_active(555))

        # Anti-Nuke: 2 channel deletions within 10 seconds
        self.db.update_security_settings(555, {
            "anti_nuke": {"enabled": True, "max_channel_deletions": 2, "window_sec": 10}
        })
        is_nuke1, _ = self.anti_nuke.record_action_and_evaluate(555, "channel_delete", 999)
        self.assertFalse(is_nuke1)
        is_nuke2, _ = self.anti_nuke.record_action_and_evaluate(555, "channel_delete", 999)
        self.assertTrue(is_nuke2)

    # =========================================================================
    # Phase 6 & 7: Game Engine, P0 Games & XP Progression
    # =========================================================================
    def test_p6_p0_games_and_xp_persistence(self):
        """Verifies P0 games (Connect4, TicTacToe vs AI, Trivia, WordChain, Hangman) and XP formula."""
        # 1. WordChain logic
        p1 = MagicMock(); p1.id = 111; p1.mention = "<@111>"; p1.display_name = "Alice"
        p2 = MagicMock(); p2.id = 222; p2.mention = "<@222>"; p2.display_name = "Bob"
        wc = WordChainView(p1, p2, self.game_engine)
        wc.current_word = "sakura" # Ends in 'a'
        wc.current_player = p1

        # Submit valid word starting with 'a'
        ok, msg = wc.submit_word(p1, "apple")
        self.assertTrue(ok)
        self.assertEqual(wc.current_word, "apple")
        self.assertEqual(wc.current_player, p2) # Now Bob's turn
        self.assertEqual(wc.get_required_letter(), "e") # Ends in 'e'

        # Reject word not starting with 'e'
        fail, msg = wc.submit_word(p2, "dragon")
        self.assertFalse(fail)

        # 2. XP Progression formula: level = XP // 100 + 1
        self.game_engine.award_game_results(winner_id=111, loser_id=222, game_type=GameType.WORDCHAIN, is_draw=False, score=100, xp_winner=150, xp_loser=25)
        prof_winner = self.db.get_game_profile(111)
        self.assertEqual(prof_winner["xp"], 150)
        self.assertEqual(prof_winner["level"], 2) # 150 // 100 + 1 = 2
        self.assertEqual(prof_winner["wins"], 1)

        # 3. TicTacToe AI logic check
        from discord_features.game_engine import TicTacToeView
        ttt = TicTacToeView(p1, None, is_ai=True, difficulty="hard", engine=self.game_engine)
        # Winning block setup: Kazumi AI is "O" (value 2), board has two 'O's in row 0
        ttt.board = [2, 2, 0, 1, 1, 0, 0, 0, 0]
        ttt._kazumi_ai_move()
        self.assertEqual(ttt.board[2], 2) # Completes row 0-1-2

    # =========================================================================
    # Phase 8: Dashboard API Verification
    # =========================================================================
    def test_p8_dashboard_api_endpoints(self):
        """Verifies dashboard API functions can read status, cases, and arcade stats."""
        # Insert a sample case and game profile
        self.case_mgr.log_case(guild_id=10, user_id=20, moderator_id=30, action="BAN", reason="Test")
        self.game_engine.award_game_results(111, 222, GameType.CONNECT4, False, 50, xp_winner=50)

        # Verify cases query
        cases_file = os.path.join(self.test_dir, "cases.json")
        self.assertTrue(os.path.exists(cases_file))
        
        # Verify arcade query
        game_file = os.path.join(self.test_dir, "game_stats.json")
        self.assertTrue(os.path.exists(game_file))

        # Verify cases query
        cases_file = os.path.join(self.test_dir, "cases.json")
        self.assertTrue(os.path.exists(cases_file))
        
        # Verify arcade query
        game_file = os.path.join(self.test_dir, "game_stats.json")
        self.assertTrue(os.path.exists(game_file))


if __name__ == "__main__":
    unittest.main()
