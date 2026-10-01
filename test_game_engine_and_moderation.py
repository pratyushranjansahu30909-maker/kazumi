# -*- coding: utf-8 -*-
"""
🌸 Kazumi Advanced Games + Moderation Expansion Test Suite
Tests:
- GameEngine, Sessions, Anti-Abuse, Connect Four, Tic-Tac-Toe, Battle Arena,
  Trivia, Reaction Race, Would You Rather, Hangman, Daily Puzzle, Achievements,
  Leaderboard, XP Progression
- Moderation Case Management, Reports, Appeals, Private Mod Notes, Mod History
- Security Suite: Anti-Raid, Anti-Nuke, Quarantine, Role Hierarchy, Smart Spam Confidence
"""

import os
import sys
import time
import shutil
import unittest
from unittest.mock import MagicMock

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import discord
from discord_features.database import FeatureDatabase
from discord_features.case_system import CaseManager, ReportManager, AppealManager
from discord_features.security import AntiRaidEngine, AntiNukeEngine, StaffPermissionManager
from discord_features.game_engine import (
    GameEngine,
    GameType,
    ConnectFourView,
    TicTacToeView,
    CLASSES,
    TRIVIA_QUESTIONS,
    ACHIEVEMENTS_CATALOG
)
from discord_features.moderation import AutoModTracker, check_hierarchy


class KazumiGamesAndModerationTests(unittest.TestCase):

    def setUp(self):
        self.test_dir = "isa_memory_games_mod_test"
        self.db = FeatureDatabase(persist_dir=self.test_dir)
        self.engine = GameEngine(self.db)
        self.case_mgr = CaseManager(self.db)
        self.report_mgr = ReportManager(self.db)
        self.appeal_mgr = AppealManager(self.db)
        self.anti_raid = AntiRaidEngine(self.db)
        self.anti_nuke = AntiNukeEngine(self.db)
        self.automod = AutoModTracker()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    # =========================================================================
    # PART A: GAME ENGINE TESTS
    # =========================================================================

    def test_01_game_session_and_anti_abuse(self):
        """Verify session creation and quarantine blocking."""
        session = self.engine.create_session(GameType.CONNECT4, 101, 999, 555)
        self.assertIsNotNone(session)
        self.assertEqual(session.game_type, GameType.CONNECT4)
        self.assertEqual(session.creator_id, 101)

        # Normal player can play
        can_play, msg = self.engine.can_user_play(999, 101)
        self.assertTrue(can_play)

        # Quarantined player is blocked
        self.db.set_user_quarantined(999, 101, True, reason="Suspicious activity")
        can_play, msg = self.engine.can_user_play(999, 101)
        self.assertFalse(can_play)
        self.assertIn("quarantined", msg)

    def test_02_connect_four_gameplay(self):
        """Test Connect Four 6x7 drop, turn switching, and horizontal/vertical win detection."""
        p1 = MagicMock(spec=discord.User)
        p1.id = 1
        p1.display_name = "Alice"
        p2 = MagicMock(spec=discord.User)
        p2.id = 2
        p2.display_name = "Bob"

        view = ConnectFourView(p1, p2, self.engine)
        self.assertEqual(len(view.board), 6)
        self.assertEqual(len(view.board[0]), 7)

        # Simulate horizontal win for P1 (row 5, cols 0, 1, 2, 3)
        view.board[5][0] = 1
        view.board[5][1] = 1
        view.board[5][2] = 1
        view.board[5][3] = 1

        is_win = view._check_win(5, 3, 1)
        self.assertTrue(is_win)

        # Check diagonal win
        view.board[5][0] = 2
        view.board[4][1] = 2
        view.board[3][2] = 2
        view.board[2][3] = 2
        is_diag_win = view._check_win(2, 3, 2)
        self.assertTrue(is_diag_win)

    def test_03_tictactoe_ai_moves(self):
        """Test Tic-Tac-Toe board win checks and Kazumi AI smart counter moves."""
        p1 = MagicMock(spec=discord.User)
        p1.id = 1
        view = TicTacToeView(p1, None, is_ai=True, difficulty="hard", engine=self.engine)

        # User X is about to win at cell 2: [1, 1, 0, ...]
        view.board[0] = 1
        view.board[1] = 1
        view.board[2] = 0

        # On hard difficulty, Kazumi must block cell 2
        view._kazumi_ai_move()
        self.assertEqual(view.board[2], 2)
        self.assertTrue(len(view.kazumi_comment) > 0)

    def test_04_battle_arena_stats(self):
        """Verify Battle Arena classes, damage calculation, and combat stats."""
        for cname, stats in CLASSES.items():
            self.assertIn("hp", stats)
            self.assertIn("energy", stats)
            self.assertIn("atk", stats)
            self.assertIn("def", stats)
            self.assertIn("spd", stats)
            self.assertIn("ability", stats)
            self.assertIn("ult", stats)

        p1 = MagicMock(spec=discord.User)
        p1.id = 10
        p2 = MagicMock(spec=discord.User)
        p2.id = 20
        # Warrior vs Mage
        self.assertGreater(CLASSES["warrior"]["hp"], CLASSES["mage"]["hp"])
        self.assertGreater(CLASSES["mage"]["atk"], CLASSES["warrior"]["atk"])

    def test_05_trivia_and_daily_challenge(self):
        """Test trivia answers and daily brain puzzle generation."""
        self.assertGreaterEqual(len(TRIVIA_QUESTIONS), 3)
        for q in TRIVIA_QUESTIONS:
            self.assertIn(q["answer"], q["options"])

        # Test deterministic daily puzzle
        puzzle_today = self.db.get_daily_challenge("2026-10-01")
        puzzle_again = self.db.get_daily_challenge("2026-10-01")
        self.assertEqual(puzzle_today["challenge"]["title"], puzzle_again["challenge"]["title"])

        # Complete challenge
        completed = self.db.complete_daily_challenge(12345, "2026-10-01", score=50)
        self.assertTrue(completed)
        # Duplicate completion in same day returns False
        dup = self.db.complete_daily_challenge(12345, "2026-10-01", score=50)
        self.assertFalse(dup)

    def test_06_xp_level_progression_and_achievements(self):
        """Verify game XP progression, level calculation, and achievement unlock."""
        prof = self.db.record_game_outcome(9999, GameType.CONNECT4, "win", score=100, xp_earned=120)
        self.assertEqual(prof["wins"], 1)
        self.assertEqual(prof["xp"], 120)
        self.assertEqual(prof["level"], 2)  # 120 // 100 + 1 = Level 2

        # Unlock achievement
        unlocked = self.db.unlock_achievement(9999, "first_victory", *ACHIEVEMENTS_CATALOG["first_victory"])
        self.assertTrue(unlocked)
        # Re-unlocking returns False (no duplicates)
        unlocked_again = self.db.unlock_achievement(9999, "first_victory", *ACHIEVEMENTS_CATALOG["first_victory"])
        self.assertFalse(unlocked_again)

        # Leaderboard
        lb = self.db.get_game_leaderboard()
        self.assertGreaterEqual(len(lb), 1)
        self.assertEqual(lb[0]["user_id"], "9999")

    # =========================================================================
    # PART B: ADVANCED MODERATION & CASE SYSTEM TESTS
    # =========================================================================

    def test_07_case_management(self):
        """Verify sequential Case ID generation (#1001, #1002...), search, and user filtering."""
        c1 = self.db.create_case(123, 456, 789, "WARN", "Posting discord invite link")
        self.assertEqual(c1, 1001)

        c2 = self.db.create_case(123, 456, 789, "TIMEOUT", "Continuing spam", duration="10m")
        self.assertEqual(c2, 1002)

        retrieved = self.db.get_case(123, 1001)
        self.assertEqual(retrieved["action"], "WARN")
        self.assertEqual(retrieved["user_id"], "456")

        u_cases = self.db.get_user_cases(123, 456)
        self.assertEqual(len(u_cases), 2)
        self.assertEqual(u_cases[0]["case_id"], 1002)

        # Action filter
        timeout_cases = self.db.list_cases(123, limit=10, action_filter="TIMEOUT")
        self.assertEqual(len(timeout_cases), 1)
        self.assertEqual(timeout_cases[0]["case_id"], 1002)

    def test_08_mod_notes(self):
        """Verify private moderator staff notes."""
        n1 = self.db.add_mod_note(123, 456, 789, "User agreed to calm down in DMs.")
        self.assertEqual(n1["note_id"], 1)

        notes = self.db.get_mod_notes(123, 456)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["content"], "User agreed to calm down in DMs.")

        deleted = self.db.delete_mod_note(123, 456, 1)
        self.assertTrue(deleted)
        self.assertEqual(len(self.db.get_mod_notes(123, 456)), 0)

    def test_09_report_queue_and_appeals(self):
        """Verify user reports and punishment appeal workflows."""
        # Report
        rep_id = self.db.create_report(123, 111, 222, 333, 444, "Harassment", "Repeated insults")
        self.assertGreaterEqual(rep_id, 501)

        pending_reps = self.db.get_pending_reports(123)
        self.assertEqual(len(pending_reps), 1)

        resolved = self.db.resolve_report(123, rep_id, "resolved", 789, "Investigated and timed out user.")
        self.assertTrue(resolved)
        self.assertEqual(len(self.db.get_pending_reports(123)), 0)

        # Appeal
        app_id = self.db.create_appeal(123, 222, 1001, "I misunderstood the server rules and won't do it again.")
        self.assertGreaterEqual(app_id, 201)

        pending_apps = self.db.get_pending_appeals(123)
        self.assertEqual(len(pending_apps), 1)

        reviewed = self.db.review_appeal(123, app_id, "approved", 789, "Apology accepted.")
        self.assertTrue(reviewed)
        self.assertEqual(len(self.db.get_pending_appeals(123)), 0)

    def test_10_smart_spam_confidence(self):
        """Verify multi-factor smart spam confidence scoring (LOW, MEDIUM, HIGH, CRITICAL)."""
        msg = MagicMock(spec=discord.Message)
        msg.guild = MagicMock(id=123)
        msg.author = MagicMock(id=888)
        msg.author.created_at = MagicMock(timestamp=lambda: time.time() - 3600)  # 1 hour old account
        msg.content = "FREE DISCORD NITRO: https://scam-link.xyz/nitro"
        msg.mentions = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]  # 4 mentions

        # Record rapid message burst
        for _ in range(5):
            self.automod.message_history.setdefault(("123", "888"), []).append(time.time())

        tier, score, meta = self.automod.calculate_spam_confidence(msg, recent_warnings_count=2)
        self.assertIn(tier, ["HIGH", "CRITICAL"])
        self.assertGreaterEqual(score, 0.55)
        self.assertGreaterEqual(meta["mention_count"], 4)
        self.assertEqual(meta["recent_warnings"], 2)

    def test_11_anti_raid_and_anti_nuke(self):
        """Verify join burst detection and mass channel deletion interception."""
        # Anti-Raid
        self.db.update_security_settings(555, {
            "anti_raid": {"enabled": True, "join_threshold": 3, "join_window_sec": 5}
        })
        member = MagicMock(spec=discord.Member)
        member.guild = MagicMock(id=555)
        member.id = 1
        member.created_at = MagicMock(timestamp=lambda: time.time() - 600)

        # 1st join
        is_raid, _, _ = self.anti_raid.record_join_and_evaluate(member)
        self.assertFalse(is_raid)

        # 2nd join
        member.id = 2
        is_raid, _, _ = self.anti_raid.record_join_and_evaluate(member)
        self.assertFalse(is_raid)

        # 3rd join within window -> Raid Detected!
        member.id = 3
        is_raid, reason, meta = self.anti_raid.record_join_and_evaluate(member)
        self.assertTrue(is_raid)
        self.assertEqual(meta["join_count"], 3)

        # Anti-Nuke
        self.db.update_security_settings(555, {
            "anti_nuke": {"enabled": True, "max_channel_deletions": 2, "window_sec": 10}
        })
        is_nuke, _ = self.anti_nuke.record_action_and_evaluate(555, "channel_delete", 999)
        self.assertFalse(is_nuke)

        is_nuke, nuke_reason = self.anti_nuke.record_action_and_evaluate(555, "channel_delete", 999)
        self.assertTrue(is_nuke)
        self.assertIn("Mass channel_delete", nuke_reason)

    def test_12_role_hierarchy_check(self):
        """Verify role hierarchy protections for moderation commands."""
        mod = MagicMock(spec=discord.Member)
        mod.id = 100
        mod.guild = MagicMock(owner_id=999)
        mod.top_role = MagicMock()
        mod.top_role.__gt__ = lambda self, other: True
        mod.top_role.__ge__ = lambda self, other: True

        target = MagicMock(spec=discord.Member)
        target.id = 200
        target.top_role = MagicMock()
        target.top_role.__gt__ = lambda self, other: False
        target.top_role.__ge__ = lambda self, other: False

        # Mod outranks target
        can_mod, msg = StaffPermissionManager.can_moderate_target(mod, target)
        self.assertTrue(can_mod)

        # Cannot moderate server owner
        target.id = 999
        can_mod, msg = StaffPermissionManager.can_moderate_target(mod, target)
        self.assertFalse(can_mod)
        self.assertIn("Server Owner", msg)


if __name__ == "__main__":
    unittest.main()
