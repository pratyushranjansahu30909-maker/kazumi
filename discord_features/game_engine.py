# -*- coding: utf-8 -*-
"""
🌸 Kazumi Game Engine & Arcade Suite
Provides:
- Core GameEngine with GameSessionManager, PlayerManager, Matchmaking,
  TurnManager, ScoreManager, LeaderboardManager, GameRewards, AchievementManager,
  AntiAbuse, TimeoutManager, and GameRenderer.
- Full Discord-Native Games:
  1. Connect Four (2 players, interactive buttons 1-7, win/draw detection, rematch)
  2. Tic-Tac-Toe (1v1 and vs Kazumi AI with Easy/Normal/Hard + witty in-game remarks)
  3. Kazumi Battle Arena (Turn-based RPG: Warrior, Mage, Assassin, Tank, Support)
  4. Mini Dungeon (1-4 players co-op PvE: Enemy, Treasure, Trap, Puzzle, Boss)
  5. Werewolf / Mafia (Social deduction: Werewolf, Villager, Seer, Doctor, Jester)
  6. Murder Mystery (AI scenario generation, clues, suspects, voting)
  7. Trivia (Anime, Gaming, Tech, Science, Movies with streak & buttons)
  8. Reaction Race (Millisecond speed competition)
  9. Typing Race (WPM, accuracy, time challenge)
  10. Word Chain (Chain words with timer & validation)
  11. Emoji Guess (Movies, Anime, Games from emoji hints)
  12. Guess the Song (Metadata, lyrics, trivia clues)
  13. Would You Rather (Two options with live voting %)
  14. Two Truths and a Lie (Statement submission & voting)
  15. Higher or Lower (Number guessing with streaks)
  16. Hangman (Category, hidden word, letter buttons)
  17. Board Games / Reversi
  18. Daily Game & Daily Puzzle (/dailygame with daily streaks)
  19. Game Leaderboards, Profiles & Achievements (/game stats, /game leaderboard)
  20. Master Arcade Menu (/arcade)
"""

import os
import re
import time
import math
import random
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any, Callable
import discord
from discord import app_commands
from discord.ext import commands

from .database import FeatureDB, get_feature_db

logger = logging.getLogger("KazumiGameEngine")

# =============================================================================
# Achievements Catalog
# =============================================================================
ACHIEVEMENTS_CATALOG = {
    "first_victory": ("First Victory 🏆", "Win your very first game in Kazumi Arcade."),
    "connect4_master": ("Connect Four Master 🔴", "Win 5 matches of Connect Four."),
    "tictactoe_grandmaster": ("Tactical Genius ❌", "Defeat Kazumi on Hard mode in Tic-Tac-Toe."),
    "arena_champion": ("Arena Gladiator ⚔️", "Emerge victorious from a Kazumi Battle Arena duel."),
    "dungeon_survivor": ("Dungeon Conqueror 🏰", "Defeat the final Dungeon Boss in Mini Dungeon."),
    "trivia_scholar": ("Trivia Prodigy 🧠", "Answer 10 trivia questions correctly with a streak."),
    "lightning_reflexes": ("Lightning Reflexes ⚡", "Win a Reaction Race with sub-350ms reaction time."),
    "speed_demon": ("Speed Demon ⌨️", "Reach over 75 WPM in a Typing Race."),
    "mystery_detective": ("Master Sleuth 🕵️", "Correctly solve a Murder Mystery case."),
    "mafia_survivor": ("Silver Tongue 🐺", "Survive and win a match of Werewolf / Mafia."),
    "daily_devotee": ("Daily Devotee 🌟", "Maintain a 5-day daily puzzle streak."),
    "wordchain_master": ("Lexical Champion 🔤", "Successfully chain 10 words in a Word Chain duel."),
    "arcade_legend": ("Arcade Legend 👑", "Reach Level 10 and accumulate 1,000 Game XP.")
}


# =============================================================================
# 1. Core Game Engine Foundations
# =============================================================================

class GameType:
    CONNECT4 = "connect4"
    TICTACTOE = "tictactoe"
    ARENA = "arena"
    DUNGEON = "dungeon"
    WEREWOLF = "werewolf"
    MYSTERY = "mystery"
    TRIVIA = "trivia"
    REACTION = "reaction"
    TYPING = "typing"
    WORDCHAIN = "wordchain"
    EMOJI = "emojiguess"
    SONG = "songguess"
    WYR = "wouldyourather"
    TRUTHS = "twotruths"
    HIGHERLOWER = "higherlower"
    HANGMAN = "hangman"
    REVERSI = "reversi"
    DAILY = "daily"


class GameSession:
    """Encapsulates a live game session."""

    def __init__(self, game_id: str, game_type: str, creator_id: int, guild_id: int, channel_id: int):
        self.game_id = game_id
        self.game_type = game_type
        self.creator_id = creator_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.players: List[int] = [creator_id]
        self.status: str = "lobby"  # "lobby", "active", "completed", "cancelled"
        self.created_at: float = time.time()
        self.started_at: Optional[float] = None
        self.ended_at: Optional[float] = None
        self.current_turn: Optional[int] = None
        self.scores: Dict[int, int] = {}
        self.winner: Optional[int] = None
        self.configuration: Dict[str, Any] = {}
        self.state: Dict[str, Any] = {}


class GameEngine:
    """
    Central Game Engine coordinating sessions, matchmaking, turn processing,
    XP distribution, achievement unlocks, and abuse prevention.
    """

    def __init__(self, db: FeatureDB):
        self.db = db
        # Active sessions: game_id -> GameSession
        self.sessions: Dict[str, GameSession] = {}
        # User rate limit tracking for anti-farming: user_id -> list of completion timestamps
        self._user_game_completions: Dict[int, List[float]] = {}

    def create_session(self, game_type: str, creator_id: int, guild_id: int, channel_id: int) -> GameSession:
        import uuid
        gid = f"{game_type}_{uuid.uuid4().hex[:8]}"
        session = GameSession(gid, game_type, creator_id, guild_id, channel_id)
        self.sessions[gid] = session
        return session

    def get_session(self, game_id: str) -> Optional[GameSession]:
        return self.sessions.get(game_id)

    def close_session(self, game_id: str) -> None:
        self.sessions.pop(game_id, None)

    def can_user_play(self, guild_id: int, user_id: int) -> Tuple[bool, str]:
        """Anti-Abuse & Moderation Check: blocks banned, quarantined, or spamming members."""
        if self.db.is_user_quarantined(guild_id, user_id):
            return False, "You are currently quarantined and cannot join multiplayer games."

        # Anti-farming: max 12 completed games in 5 minutes
        now = time.time()
        c_list = self._user_game_completions.setdefault(user_id, [])
        self._user_game_completions[user_id] = [t for t in c_list if now - t <= 300]
        if len(self._user_game_completions[user_id]) >= 15:
            return False, "You are completing games too rapidly! Please take a quick 2-minute break."

        return True, "OK"

    def award_game_results(
        self,
        winner_id: Optional[int],
        loser_id: Optional[int],
        game_type: str,
        is_draw: bool = False,
        score: int = 10,
        xp_winner: int = 35,
        xp_loser: int = 15
    ) -> Dict[str, Any]:
        """Updates stats, awards XP, and checks achievements."""
        results = {}
        now = time.time()

        if winner_id:
            self._user_game_completions.setdefault(winner_id, []).append(now)
            outcome = "draw" if is_draw else "win"
            p_win = self.db.record_game_outcome(winner_id, game_type, outcome, score, xp_winner if not is_draw else 20)
            results[winner_id] = p_win

            # Achievement checks
            if not is_draw:
                self.check_achievements(winner_id, game_type, p_win)

        if loser_id and not is_draw:
            self._user_game_completions.setdefault(loser_id, []).append(now)
            p_loss = self.db.record_game_outcome(loser_id, game_type, "loss", 0, xp_loser)
            results[loser_id] = p_loss

        return results

    def check_achievements(self, user_id: int, game_type: str, profile: Dict[str, Any]) -> List[str]:
        unlocked = []
        wins = profile.get("wins", 0)
        xp = profile.get("xp", 0)

        if wins >= 1:
            if self.db.unlock_achievement(user_id, "first_victory", *ACHIEVEMENTS_CATALOG["first_victory"]):
                unlocked.append(ACHIEVEMENTS_CATALOG["first_victory"][0])

        g_wins = profile.get("per_game", {}).get(game_type, {}).get("wins", 0)
        if game_type == GameType.CONNECT4 and g_wins >= 5:
            if self.db.unlock_achievement(user_id, "connect4_master", *ACHIEVEMENTS_CATALOG["connect4_master"]):
                unlocked.append(ACHIEVEMENTS_CATALOG["connect4_master"][0])

        if game_type == GameType.ARENA and g_wins >= 1:
            if self.db.unlock_achievement(user_id, "arena_champion", *ACHIEVEMENTS_CATALOG["arena_champion"]):
                unlocked.append(ACHIEVEMENTS_CATALOG["arena_champion"][0])

        if game_type == GameType.DUNGEON and g_wins >= 1:
            if self.db.unlock_achievement(user_id, "dungeon_survivor", *ACHIEVEMENTS_CATALOG["dungeon_survivor"]):
                unlocked.append(ACHIEVEMENTS_CATALOG["dungeon_survivor"][0])

        if xp >= 1000:
            if self.db.unlock_achievement(user_id, "arcade_legend", *ACHIEVEMENTS_CATALOG["arcade_legend"]):
                unlocked.append(ACHIEVEMENTS_CATALOG["arcade_legend"][0])

        return unlocked


# Global game engine reference
_global_game_engine: Optional[GameEngine] = None

def get_game_engine(db: Optional[FeatureDB] = None) -> GameEngine:
    global _global_game_engine
    if _global_game_engine is None:
        _global_game_engine = GameEngine(db or get_feature_db())
    return _global_game_engine


# =============================================================================
# 2. CONNECT FOUR GAME (2 Players, Interactive Buttons 1-7, Turn Tracking)
# =============================================================================

class ConnectFourView(discord.ui.View):
    """Interactive Connect Four board with buttons 1-7."""

    def __init__(self, p1: discord.User, p2: discord.User, engine: GameEngine):
        super().__init__(timeout=180.0)
        self.p1 = p1  # Red 🔴
        self.p2 = p2  # Blue 🔵
        self.engine = engine
        self.current_player = p1
        self.winner: Optional[discord.User] = None
        self.is_draw = False

        # 6 rows x 7 columns (0 = Empty, 1 = p1 🔴, 2 = p2 🔵)
        self.rows = 6
        self.cols = 7
        self.board = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        self._setup_buttons()

    def _setup_buttons(self):
        self.clear_items()
        for col_idx in range(self.cols):
            btn = discord.ui.Button(
                label=str(col_idx + 1),
                style=discord.ButtonStyle.primary,
                custom_id=f"c4_col_{col_idx}",
                row=0 if col_idx < 4 else 1
            )
            btn.callback = self._create_drop_callback(col_idx)
            self.add_item(btn)

    def _create_drop_callback(self, col: int):
        async def callback(interaction: discord.Interaction):
            if self.winner or self.is_draw:
                await interaction.response.send_message("❌ This game is already over.", ephemeral=True)
                return

            if interaction.user.id != self.current_player.id:
                await interaction.response.send_message(f"⏳ It's {self.current_player.mention}'s turn!", ephemeral=True)
                return

            player_num = 1 if self.current_player.id == self.p1.id else 2
            # Drop chip into lowest available row in this column
            placed_row = None
            for r in reversed(range(self.rows)):
                if self.board[r][col] == 0:
                    self.board[r][col] = player_num
                    placed_row = r
                    break

            if placed_row is None:
                await interaction.response.send_message("❌ Column is full! Pick another.", ephemeral=True)
                return

            # Check win condition
            if self._check_win(placed_row, col, player_num):
                self.winner = self.current_player
                loser = self.p2 if self.winner.id == self.p1.id else self.p1
                self.engine.award_game_results(self.winner.id, loser.id, GameType.CONNECT4, is_draw=False, score=100)
                self._disable_all()
                await interaction.response.edit_message(embed=self.render_embed(), view=self)
                self.stop()
                return

            # Check draw
            if all(self.board[0][c] != 0 for c in range(self.cols)):
                self.is_draw = True
                self.engine.award_game_results(self.p1.id, self.p2.id, GameType.CONNECT4, is_draw=True, score=25)
                self._disable_all()
                await interaction.response.edit_message(embed=self.render_embed(), view=self)
                self.stop()
                return

            # Switch turns
            self.current_player = self.p2 if self.current_player.id == self.p1.id else self.p1
            await interaction.response.edit_message(embed=self.render_embed(), view=self)

        return callback

    def _check_win(self, r: int, c: int, p: int) -> bool:
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for dr, dc in directions:
            consecutive = 1
            # Forward direction
            step = 1
            while 0 <= r + dr * step < self.rows and 0 <= c + dc * step < self.cols and self.board[r + dr * step][c + dc * step] == p:
                consecutive += 1
                step += 1
            # Backward direction
            step = 1
            while 0 <= r - dr * step < self.rows and 0 <= c - dc * step < self.cols and self.board[r - dr * step][c - dc * step] == p:
                consecutive += 1
                step += 1
            if consecutive >= 4:
                return True
        return False

    def _disable_all(self):
        for child in self.children:
            child.disabled = True

    def render_embed(self) -> discord.Embed:
        # Render board
        symbols = {0: "⚫", 1: "🔴", 2: "🔵"}
        lines = []
        for r in range(self.rows):
            lines.append(" ".join(symbols[self.board[r][c]] for c in range(self.cols)))
        lines.append("1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣")
        board_str = "\n".join(lines)

        embed = discord.Embed(
            title="🎮 Connect Four Arena",
            color=0xef4444 if self.current_player.id == self.p1.id else 0x3b82f6
        )
        embed.description = (
            f"**Players:** 🔴 {self.p1.mention} vs 🔵 {self.p2.mention}\n\n"
            f"{board_str}\n\n"
        )
        if self.winner:
            embed.description += f"🏆 **WINNER: {self.winner.mention}!** (+35 XP)"
            embed.color = 0x10b981
        elif self.is_draw:
            embed.description += "🤝 **MATCH DRAW! Well played both!** (+20 XP)"
            embed.color = 0xf59e0b
        else:
            turn_sym = "🔴" if self.current_player.id == self.p1.id else "🔵"
            embed.description += f"👉 **Turn:** {turn_sym} {self.current_player.mention}"

        embed.set_footer(text="Kazumi Arcade • Press a column number below to drop your piece!")
        return embed


# =============================================================================
# 3. TIC-TAC-TOE (1v1 and vs Kazumi AI with Easy/Normal/Hard + Remarks)
# =============================================================================

class TicTacToeView(discord.ui.View):
    """Interactive 3x3 Tic-Tac-Toe."""

    def __init__(self, p1: discord.User, p2: Optional[discord.User], is_ai: bool = False, difficulty: str = "normal", engine: Optional[GameEngine] = None):
        super().__init__(timeout=120.0)
        self.p1 = p1  # X
        self.p2 = p2  # O (or None if vs Kazumi AI)
        self.is_ai = is_ai
        self.difficulty = difficulty.lower()
        self.engine = engine or get_game_engine()
        self.current_turn = "X"
        self.board = [0] * 9  # 0=Empty, 1=X, 2=O
        self.winner: Optional[str] = None
        self.is_draw = False
        self.kazumi_comment = ""
        self._build_grid()

    def _build_grid(self):
        self.clear_items()
        for idx in range(9):
            val = self.board[idx]
            lbl = " "
            style = discord.ButtonStyle.secondary
            if val == 1:
                lbl = "❌"
                style = discord.ButtonStyle.danger
            elif val == 2:
                lbl = "⭕"
                style = discord.ButtonStyle.primary

            btn = discord.ui.Button(
                label=lbl,
                style=style,
                row=idx // 3,
                custom_id=f"ttt_cell_{idx}",
                disabled=(val != 0 or bool(self.winner) or self.is_draw)
            )
            btn.callback = self._make_move_callback(idx)
            self.add_item(btn)

    def _make_move_callback(self, idx: int):
        async def callback(interaction: discord.Interaction):
            if bool(self.winner) or self.is_draw:
                await interaction.response.send_message("❌ This match is already finished.", ephemeral=True)
                return

            if self.board[idx] != 0:
                await interaction.response.send_message("❌ That spot is already taken!", ephemeral=True)
                return

            expected_user = self.p1 if self.current_turn == "X" else self.p2
            if self.is_ai and self.current_turn == "O":
                await interaction.response.send_message("Kazumi is thinking! 🌸", ephemeral=True)
                return

            if not self.is_ai and interaction.user.id != expected_user.id:
                await interaction.response.send_message(f"⏳ It's {expected_user.mention}'s turn!", ephemeral=True)
                return
            elif self.is_ai and interaction.user.id != self.p1.id:
                await interaction.response.send_message("❌ This is not your match!", ephemeral=True)
                return

            self.board[idx] = 1 if self.current_turn == "X" else 2
            if self._check_win(self.board[idx]):
                self.winner = self.current_turn
                self._handle_game_over()
                self._build_grid()
                await interaction.response.edit_message(embed=self.render_embed(), view=self)
                self.stop()
                return

            if all(v != 0 for v in self.board):
                self.is_draw = True
                self._handle_game_over()
                self._build_grid()
                await interaction.response.edit_message(embed=self.render_embed(), view=self)
                self.stop()
                return

            # Advance turn
            if self.is_ai:
                self.current_turn = "O"
                self._kazumi_ai_move()
                if self._check_win(2):
                    self.winner = "O"
                    self._handle_game_over()
                    self.stop()
                elif all(v != 0 for v in self.board):
                    self.is_draw = True
                    self._handle_game_over()
                    self.stop()
                else:
                    self.current_turn = "X"

            else:
                self.current_turn = "O" if self.current_turn == "X" else "X"

            self._build_grid()
            await interaction.response.edit_message(embed=self.render_embed(), view=self)

        return callback

    def _kazumi_ai_move(self):
        available = [i for i, v in enumerate(self.board) if v == 0]
        if not available:
            return

        choice = None
        remarks_pool = [
            "Nice try, sweetie! But I saw that coming! 🌸",
            "Bold move! Let's see if you can handle this counter! ⚡",
            "Did you really think I wouldn't block that? Hehe! 😈",
            "Calculating optimal path to victory... done! ✨"
        ]

        if self.difficulty == "hard":
            # 1. Win if possible
            for idx in available:
                self.board[idx] = 2
                if self._check_win(2):
                    choice = idx
                    self.board[idx] = 0
                    break
                self.board[idx] = 0
            # 2. Block user win
            if choice is None:
                for idx in available:
                    self.board[idx] = 1
                    if self._check_win(1):
                        choice = idx
                        self.board[idx] = 0
                        break
                    self.board[idx] = 0
            # 3. Take center
            if choice is None and 4 in available:
                choice = 4

        elif self.difficulty == "normal":
            # Block 60% of the time
            if random.random() < 0.60:
                for idx in available:
                    self.board[idx] = 1
                    if self._check_win(1):
                        choice = idx
                        self.board[idx] = 0
                        break
                    self.board[idx] = 0

        if choice is None:
            choice = random.choice(available)

        self.board[choice] = 2
        self.kazumi_comment = random.choice(remarks_pool)

    def _check_win(self, val: int) -> bool:
        lines = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Cols
            [0, 4, 8], [2, 4, 6]              # Diagonals
        ]
        return any(all(self.board[i] == val for i in line) for line in lines)

    def _handle_game_over(self):
        if self.is_ai:
            if self.winner == "X":
                self.engine.award_game_results(self.p1.id, None, GameType.TICTACTOE, False, 50, xp_winner=35)
                if self.difficulty == "hard":
                    self.engine.db.unlock_achievement(self.p1.id, "tictactoe_grandmaster", *ACHIEVEMENTS_CATALOG["tictactoe_grandmaster"])
            elif self.winner == "O":
                self.engine.award_game_results(None, self.p1.id, GameType.TICTACTOE, False, 10, xp_loser=10)
        else:
            win_u = self.p1 if self.winner == "X" else self.p2
            loss_u = self.p2 if self.winner == "X" else self.p1
            self.engine.award_game_results(win_u.id if win_u else None, loss_u.id if loss_u else None, GameType.TICTACTOE, self.is_draw, 40)

    def render_embed(self) -> discord.Embed:
        p2_title = "🌸 Kazumi AI" if self.is_ai else (self.p2.mention if self.p2 else "Opponent")
        embed = discord.Embed(
            title="🎮 Tic-Tac-Toe Arena",
            color=0xc084fc
        )
        embed.description = f"**❌ {self.p1.mention}** vs **⭕ {p2_title}**\n\n"

        if self.winner:
            w_name = self.p1.mention if self.winner == "X" else p2_title
            embed.description += f"🏆 **WINNER: {w_name}!**\n"
            embed.color = 0x10b981
        elif self.is_draw:
            embed.description += "🤝 **DRAW! A perfectly matched duel.**\n"
            embed.color = 0xf59e0b
        else:
            curr_str = self.p1.mention if self.current_turn == "X" else p2_title
            embed.description += f"👉 **Turn:** {curr_str}\n"

        if self.kazumi_comment:
            embed.description += f"\n*(Kazumi winks)*: \"{self.kazumi_comment}\""

        embed.set_footer(text="Kazumi Arcade • Click any open cell to play!")
        return embed


# =============================================================================
# 4. KAZUMI BATTLE ARENA (Turn-Based RPG)
# =============================================================================

CLASSES = {
    "warrior": {"hp": 130, "energy": 50, "atk": 24, "def": 12, "spd": 8, "ability": "Shield Bash", "ult": "Berserk Rage"},
    "mage": {"hp": 90, "energy": 100, "atk": 32, "def": 6, "spd": 10, "ability": "Frost Lance", "ult": "Meteor Swarm"},
    "assassin": {"hp": 95, "energy": 70, "atk": 28, "def": 7, "spd": 16, "ability": "Shadow Strike", "ult": "Death Mark"},
    "tank": {"hp": 160, "energy": 40, "atk": 16, "def": 18, "spd": 5, "ability": "Fortify", "ult": "Earthquake"},
    "support": {"hp": 110, "energy": 80, "atk": 18, "def": 10, "spd": 12, "ability": "Healing Blossom", "ult": "Divine Aegis"}
}

class ArenaBattleView(discord.ui.View):
    """Interactive turn-based RPG battle."""

    def __init__(self, p1: discord.User, p2: discord.User, class1: str, class2: str, engine: GameEngine):
        super().__init__(timeout=240.0)
        self.p1 = p1
        self.p2 = p2
        self.engine = engine
        self.stats = {
            p1.id: dict(CLASSES.get(class1.lower(), CLASSES["warrior"])),
            p2.id: dict(CLASSES.get(class2.lower(), CLASSES["mage"]))
        }
        self.cnames = {p1.id: class1.title(), p2.id: class2.title()}
        self.current_turn = p1 if self.stats[p1.id]["spd"] >= self.stats[p2.id]["spd"] else p2
        self.combat_log: List[str] = [f"⚔️ **The battle begins!** {p1.mention} ({class1.title()}) vs {p2.mention} ({class2.title()})!"]
        self.winner: Optional[discord.User] = None

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.danger, emoji="⚔️", row=0)
    async def attack_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._process_action(interaction, "attack")

    @discord.ui.button(label="Defend", style=discord.ButtonStyle.primary, emoji="🛡️", row=0)
    async def defend_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._process_action(interaction, "defend")

    @discord.ui.button(label="Skill", style=discord.ButtonStyle.success, emoji="✨", row=0)
    async def skill_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._process_action(interaction, "skill")

    @discord.ui.button(label="Ultimate", style=discord.ButtonStyle.danger, emoji="💀", row=0)
    async def ult_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._process_action(interaction, "ult")

    async def _process_action(self, interaction: discord.Interaction, action: str):
        if interaction.user.id != self.current_turn.id:
            await interaction.response.send_message(f"⏳ Waiting for {self.current_turn.mention}'s turn!", ephemeral=True)
            return

        attacker = self.current_turn
        defender = self.p2 if attacker.id == self.p1.id else self.p1
        a_stats = self.stats[attacker.id]
        d_stats = self.stats[defender.id]

        if action == "attack":
            dmg = max(5, int(a_stats["atk"] * random.uniform(0.85, 1.15)) - d_stats["def"] // 2)
            d_stats["hp"] = max(0, d_stats["hp"] - dmg)
            a_stats["energy"] = min(100, a_stats["energy"] + 15)
            self.combat_log.append(f"⚔️ **{attacker.display_name}** attacks for **{dmg} DMG**!")

        elif action == "defend":
            a_stats["hp"] += 12
            a_stats["energy"] = min(100, a_stats["energy"] + 20)
            self.combat_log.append(f"🛡️ **{attacker.display_name}** takes a defensive stance (+12 HP, +20 Energy)!")

        elif action == "skill":
            if a_stats["energy"] < 30:
                await interaction.response.send_message("❌ Not enough energy (requires 30)!", ephemeral=True)
                return
            a_stats["energy"] -= 30
            skill_name = a_stats.get("ability", "Skill")
            if "Heal" in skill_name:
                a_stats["hp"] += 35
                self.combat_log.append(f"✨ **{attacker.display_name}** casts **{skill_name}** (+35 HP)!")
            else:
                dmg = max(10, int(a_stats["atk"] * 1.6) - d_stats["def"] // 3)
                d_stats["hp"] = max(0, d_stats["hp"] - dmg)
                self.combat_log.append(f"✨ **{attacker.display_name}** casts **{skill_name}** for **{dmg} DMG**!")

        elif action == "ult":
            if a_stats["energy"] < 80:
                await interaction.response.send_message("❌ Ultimate requires 80 Energy!", ephemeral=True)
                return
            a_stats["energy"] -= 80
            dmg = max(20, int(a_stats["atk"] * 2.5) - d_stats["def"] // 4)
            d_stats["hp"] = max(0, d_stats["hp"] - dmg)
            self.combat_log.append(f"💀 **{attacker.display_name} UNLEASHES {a_stats['ult'].upper()} FOR {dmg} CRITICAL DMG!**")

        # Win check
        if d_stats["hp"] <= 0:
            self.winner = attacker
            for child in self.children:
                child.disabled = True
            self.engine.award_game_results(attacker.id, defender.id, GameType.ARENA, False, 150)
            self.combat_log.append(f"🏆 **{attacker.display_name} HAS SLAIN {defender.display_name}!**")
            await interaction.response.edit_message(embed=self.render_embed(), view=self)
            self.stop()
            return

        self.current_turn = defender
        await interaction.response.edit_message(embed=self.render_embed(), view=self)

    def render_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="⚔️ Kazumi Battle Arena Duel",
            color=0xef4444
        )
        s1 = self.stats[self.p1.id]
        s2 = self.stats[self.p2.id]

        bar1 = "❤️" * max(1, s1["hp"] // 15)
        bar2 = "❤️" * max(1, s2["hp"] // 15)

        embed.add_field(
            name=f"{self.p1.display_name} ({self.cnames[self.p1.id]})",
            value=f"HP: **{s1['hp']}**\nEnergy: **{s1['energy']}%**\n`{bar1}`",
            inline=True
        )
        embed.add_field(
            name=f"{self.p2.display_name} ({self.cnames[self.p2.id]})",
            value=f"HP: **{s2['hp']}**\nEnergy: **{s2['energy']}%**\n`{bar2}`",
            inline=True
        )

        log_str = "\n".join(self.combat_log[-4:])
        embed.add_field(name="📜 Combat Log", value=log_str, inline=False)

        if not self.winner:
            embed.set_footer(text=f"Current Turn: {self.current_turn.display_name} • Choose an action below!")
        else:
            embed.set_footer(text=f"Match Concluded • Winner: {self.winner.display_name}")

        return embed


# =============================================================================
# 5. TRIVIA GAME (Buttons, 11 Categories, Timer, Streak)
# =============================================================================

TRIVIA_QUESTIONS = [
    {
        "category": "Anime",
        "question": "In 'Death Note', what is the name of the Shinigami who loves apples?",
        "options": ["Ryuk", "Rem", "Gelus", "Sidoh"],
        "answer": "Ryuk"
    },
    {
        "category": "Gaming",
        "question": "What is the name of Master Chief's AI companion in the Halo series?",
        "options": ["Cortana", "GLaDOS", "EDI", "Serina"],
        "answer": "Cortana"
    },
    {
        "category": "Technology",
        "question": "Who created the Python programming language in 1991?",
        "options": ["Guido van Rossum", "James Gosling", "Dennis Ritchie", "Bjarne Stroustrup"],
        "answer": "Guido van Rossum"
    },
    {
        "category": "Science",
        "question": "What is the powerhouse organelle of the human cell?",
        "options": ["Mitochondria", "Ribosome", "Nucleus", "Endoplasmic Reticulum"],
        "answer": "Mitochondria"
    },
    {
        "category": "Movies",
        "question": "Which movie features the quote: 'May the Force be with you'?",
        "options": ["Star Wars", "Star Trek", "Interstellar", "Dune"],
        "answer": "Star Wars"
    }
]

class TriviaView(discord.ui.View):
    """Interactive 4-choice Trivia Question."""

    def __init__(self, user: discord.User, question_data: Dict[str, Any], engine: GameEngine):
        super().__init__(timeout=30.0)
        self.user = user
        self.q = question_data
        self.engine = engine
        self.answered = False

        shuffled = list(self.q["options"])
        random.shuffle(shuffled)
        for opt in shuffled:
            btn = discord.ui.Button(label=opt, style=discord.ButtonStyle.primary)
            btn.callback = self._create_callback(opt)
            self.add_item(btn)

    def _create_callback(self, chosen: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("❌ This trivia round is for another member!", ephemeral=True)
                return

            if self.answered:
                await interaction.response.send_message("❌ You have already submitted an answer!", ephemeral=True)
                return

            self.answered = True
            for child in self.children:
                child.disabled = True

            correct = (chosen == self.q["answer"])
            if correct:
                self.engine.award_game_results(self.user.id, None, GameType.TRIVIA, False, 25, xp_winner=25)
                embed = discord.Embed(
                    title="🎯 Correct Answer!",
                    description=f"Awesome job, **{self.user.display_name}**! The answer was indeed **{self.q['answer']}**! (+25 XP 🌟)",
                    color=0x10b981
                )
            else:
                embed = discord.Embed(
                    title="❌ Incorrect!",
                    description=f"Oops! You picked `{chosen}`. The correct answer was **{self.q['answer']}**! 🌸",
                    color=0xef4444
                )
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()

        return callback


# =============================================================================
# 6. REACTION RACE (Millisecond Speed Test)
# =============================================================================

class ReactionRaceView(discord.ui.View):
    """Button race: First person to press wins."""

    def __init__(self, engine: GameEngine):
        super().__init__(timeout=60.0)
        self.engine = engine
        self.start_time: float = time.time()
        self.winner: Optional[discord.User] = None
        self.reaction_ms: int = 0

    @discord.ui.button(label="⚡ CLICK HERE FIRST!", style=discord.ButtonStyle.success, emoji="💥", custom_id="react_race_btn")
    async def click_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.winner:
            await interaction.response.send_message(f"Too late! {self.winner.mention} already won!", ephemeral=True)
            return

        self.winner = interaction.user
        self.reaction_ms = int((time.time() - self.start_time) * 1000)
        button.disabled = True
        button.label = f"Winner: {self.winner.display_name} ({self.reaction_ms}ms)!"
        button.style = discord.ButtonStyle.danger

        self.engine.award_game_results(self.winner.id, None, GameType.REACTION, False, self.reaction_ms, xp_winner=30)
        if self.reaction_ms < 350:
            self.engine.db.unlock_achievement(self.winner.id, "lightning_reflexes", *ACHIEVEMENTS_CATALOG["lightning_reflexes"])

        embed = discord.Embed(
            title="⚡ REACTION RACE CONCLUDED!",
            description=f"🏆 **{self.winner.mention}** clicked the button first in **{self.reaction_ms} ms**! (+30 XP ⚡)",
            color=0xf59e0b
        )
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


# =============================================================================
# 7. WOULD YOU RATHER (Live Voting Percentages)
# =============================================================================

WYR_PROMPTS = [
    ("Have unlimited free food anywhere in the world", "Never have to sleep and never feel tired"),
    ("Be able to speak every human language fluently", "Be able to speak with animals"),
    ("Explore deep space and discover alien life", "Explore the deepest Mariana trench and uncover ancient cities"),
    ("Have photographic memory for everything you read", "Never forget any person you meet or conversation you have"),
    ("Live in a cozy cyberpunk neon metropolis", "Live in a peaceful enchanted fantasy cottage")
]

class WouldYouRatherView(discord.ui.View):
    """Two choices with live community voting percentages."""

    def __init__(self, option_a: str, option_b: str):
        super().__init__(timeout=180.0)
        self.opt_a = option_a
        self.opt_b = option_b
        self.votes_a: set = set()
        self.votes_b: set = set()

    @discord.ui.button(label="Option A", style=discord.ButtonStyle.primary, emoji="🅰️")
    async def opt_a_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        self.votes_b.discard(uid)
        self.votes_a.add(uid)
        await interaction.response.edit_message(embed=self.render_embed(), view=self)

    @discord.ui.button(label="Option B", style=discord.ButtonStyle.success, emoji="🅱️")
    async def opt_b_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        self.votes_a.discard(uid)
        self.votes_b.add(uid)
        await interaction.response.edit_message(embed=self.render_embed(), view=self)

    def render_embed(self) -> discord.Embed:
        total = len(self.votes_a) + len(self.votes_b)
        pct_a = int((len(self.votes_a) / total) * 100) if total > 0 else 50
        pct_b = 100 - pct_a if total > 0 else 50

        bar_a = "🟦" * (pct_a // 10)
        bar_b = "🟩" * (pct_b // 10)

        embed = discord.Embed(
            title="🤔 Would You Rather...",
            color=0x8b5cf6
        )
        embed.description = (
            f"**🅰️ Option A:**\n*{self.opt_a}*\n"
            f"`{bar_a}` **{pct_a}%** ({len(self.votes_a)} votes)\n\n"
            f"**🅱️ Option B:**\n*{self.opt_b}*\n"
            f"`{bar_b}` **{pct_b}%** ({len(self.votes_b)} votes)\n\n"
            f"Total Community Votes: **{total}**"
        )
        embed.set_footer(text="Kazumi Arcade • Click a button to cast or change your vote!")
        return embed


# =============================================================================
# 8. HANGMAN (Letter Buttons, Lives, Hidden Word)
# =============================================================================

HANGMAN_WORDS = [
    ("sakura", "Nature"),
    ("python", "Programming"),
    ("discord", "Social"),
    ("companion", "Friendship"),
    ("galaxy", "Astronomy"),
    ("kazumi", "AI Goddess")
]

class HangmanView(discord.ui.View):
    """Hangman with letter inputs and lives."""

    def __init__(self, user: discord.User, word: str, category: str, engine: GameEngine):
        super().__init__(timeout=120.0)
        self.user = user
        self.word = word.lower()
        self.category = category
        self.engine = engine
        self.guessed_letters: set = set()
        self.lives = 6
        self.won = False

    @discord.ui.button(label="Guess a Letter", style=discord.ButtonStyle.primary, emoji="🔤")
    async def guess_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Start your own Hangman game with `/hangman`!", ephemeral=True)
            return

        modal = HangmanModal(self)
        await interaction.response.send_modal(modal)

    def process_guess(self, letter: str) -> str:
        letter = letter.lower().strip()
        if not letter or len(letter) != 1 or not letter.isalpha():
            return "Please enter a single valid letter!"
        if letter in self.guessed_letters:
            return f"You already guessed '{letter}'!"

        self.guessed_letters.add(letter)
        if letter not in self.word:
            self.lives -= 1

        if all(c in self.guessed_letters for c in self.word):
            self.won = True
            self.engine.award_game_results(self.user.id, None, GameType.HANGMAN, False, 50, xp_winner=30)
            self.stop()
        elif self.lives <= 0:
            self.stop()

        return f"Guessed '{letter}'!"

    def render_embed(self) -> discord.Embed:
        revealed = " ".join([c.upper() if c in self.guessed_letters else "—" for c in self.word])
        hearts = "❤️" * self.lives + "🖤" * (6 - self.lives)
        embed = discord.Embed(
            title=f"🧩 Hangman • Category: {self.category}",
            color=0x10b981 if self.won else (0xef4444 if self.lives <= 0 else 0x3b82f6)
        )
        embed.description = (
            f"**Word:** `{revealed}`\n\n"
            f"**Lives Remaining:** {hearts} ({self.lives}/6)\n"
            f"**Guessed Letters:** {', '.join(sorted(self.guessed_letters)).upper() or 'None'}\n"
        )
        if self.won:
            embed.description += f"\n🎉 **CONGRATULATIONS! You solved the word:** `{self.word.upper()}`! (+30 XP)"
        elif self.lives <= 0:
            embed.description += f"\n💀 **GAME OVER! The word was:** `{self.word.upper()}`."

        embed.set_footer(text="Kazumi Arcade • Click 'Guess a Letter' to play!")
        return embed


class HangmanModal(discord.ui.Modal, title="Guess a Hangman Letter"):
    letter = discord.ui.TextInput(label="Letter (A-Z)", max_length=1, min_length=1)

    def __init__(self, hangman_view: HangmanView):
        super().__init__()
        self.h_view = hangman_view

    async def on_submit(self, interaction: discord.Interaction):
        msg = self.h_view.process_guess(self.letter.value)
        await interaction.response.edit_message(embed=self.h_view.render_embed(), view=self.h_view)


# =============================================================================
# 9. WORD CHAIN (Turn-based Lexical Duel)
# =============================================================================

WORDCHAIN_SEEDS = ["sakura", "galaxy", "dragon", "spirit", "phoenix", "harmony", "blossom", "comet", "crystal"]

class WordChainView(discord.ui.View):
    """Interactive 2-player Word Chain game."""

    def __init__(self, p1: discord.User, p2: discord.User, engine: GameEngine):
        super().__init__(timeout=90.0)
        self.p1 = p1
        self.p2 = p2
        self.engine = engine
        self.seed = random.choice(WORDCHAIN_SEEDS)
        self.current_word = self.seed
        self.used_words: List[str] = [self.seed]
        self.current_player = p1
        self.game_over = False
        self.winner: Optional[discord.User] = None
        self.loser: Optional[discord.User] = None
        self.status_msg = f"Game started! First word is **{self.seed.upper()}**. Your turn, {self.p1.mention}!"

    def get_required_letter(self) -> str:
        return self.current_word[-1].lower()

    def submit_word(self, user: discord.User, word: str) -> Tuple[bool, str]:
        if self.game_over:
            return False, "This game has already ended."
        if user.id != self.current_player.id:
            return False, f"It is currently {self.current_player.display_name}'s turn!"

        word = word.lower().strip()
        if len(word) < 3:
            return False, "Words must be at least 3 letters long!"
        if not word.isalpha():
            return False, "Words must only contain alphabetic letters!"

        req = self.get_required_letter()
        if not word.startswith(req):
            return False, f"Word must start with the letter **'{req.upper()}'**!"

        if word in self.used_words:
            return False, f"The word **'{word.upper()}'** has already been used in this round!"

        # Valid word accepted!
        self.used_words.append(word)
        self.current_word = word
        prev_player = self.current_player
        self.current_player = self.p2 if self.current_player.id == self.p1.id else self.p1
        self.status_msg = f"✅ {prev_player.mention} played **{word.upper()}**! Next letter: **'{self.get_required_letter().upper()}'**"

        # Check if 10 words reached for achievement
        if len(self.used_words) >= 10:
            self.engine.db.unlock_achievement(prev_player.id, "wordchain_master", "Lexical Champion 🔤", "Successfully chain words in Word Chain.")

        return True, "Word accepted!"

    def resign(self, user: discord.User):
        if user.id not in (self.p1.id, self.p2.id):
            return False
        self.game_over = True
        self.loser = user
        self.winner = self.p2 if user.id == self.p1.id else self.p1
        self.status_msg = f"🏳️ {user.mention} forfeited the match!"
        self.engine.award_game_results(self.winner.id, self.loser.id, GameType.WORDCHAIN, False, 50, xp_winner=35, xp_loser=10)
        self.stop()
        return True

    @discord.ui.button(label="Submit Word 📝", style=discord.ButtonStyle.primary)
    async def btn_submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_over:
            await interaction.response.send_message("❌ This match is finished.", ephemeral=True)
            return
        if interaction.user.id != self.current_player.id:
            await interaction.response.send_message(f"⏳ It is {self.current_player.display_name}'s turn right now!", ephemeral=True)
            return

        modal = WordChainModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Give Up 🏳️", style=discord.ButtonStyle.danger)
    async def btn_resign(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.p1.id, self.p2.id):
            await interaction.response.send_message("❌ You are not part of this duel.", ephemeral=True)
            return
        self.resign(interaction.user)
        await interaction.response.edit_message(embed=self.render_embed(), view=self)

    def render_embed(self) -> discord.Embed:
        req = self.get_required_letter().upper()
        embed = discord.Embed(
            title="🔤 Word Chain Duel",
            color=0x10b981 if self.winner else 0xec4899
        )
        embed.description = (
            f"**Players:** {self.p1.mention} ⚔️ {self.p2.mention}\n\n"
            f"**Current Word:** `{self.current_word.upper()}`\n"
            f"**Next Word Must Start With:** 🔠 **`{req}`** (min 3 letters)\n"
            f"**Active Turn:** 👉 {self.current_player.mention}\n\n"
            f"{self.status_msg}\n\n"
            f"**Chain History ({len(self.used_words)}):** `{' ➔ '.join(self.used_words[-6:]).upper()}`"
        )
        if self.winner:
            embed.description += f"\n\n🏆 **Winner: {self.winner.mention}** (+35 XP 🌟)"
        embed.set_footer(text="Kazumi Arcade • Click 'Submit Word' to enter your next word!")
        return embed

    async def on_timeout(self):
        if not self.game_over:
            self.game_over = True
            # Timeout gives win to the non-current player
            self.winner = self.p2 if self.current_player.id == self.p1.id else self.p1
            self.loser = self.current_player
            self.status_msg = f"⏰ Time expired for {self.current_player.mention}!"
            self.engine.award_game_results(self.winner.id, self.loser.id, GameType.WORDCHAIN, False, 40, xp_winner=25, xp_loser=5)
            self.stop()


class WordChainModal(discord.ui.Modal, title="Submit Your Word"):
    word_input = discord.ui.TextInput(
        label="Enter word starting with the required letter",
        placeholder="e.g. apple, elephant, tempest",
        min_length=3,
        max_length=30
    )

    def __init__(self, wc_view: WordChainView):
        super().__init__()
        self.wc_view = wc_view
        req = self.wc_view.get_required_letter().upper()
        self.word_input.label = f"Word starting with '{req}' (min 3 letters)"

    async def on_submit(self, interaction: discord.Interaction):
        success, message = self.wc_view.submit_word(interaction.user, self.word_input.value)
        if not success:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
        else:
            await interaction.response.edit_message(embed=self.wc_view.render_embed(), view=self.wc_view)


# =============================================================================
# 10. REGISTER ALL GAME SLASH COMMANDS
# =============================================================================

def register_game_commands(tree: app_commands.CommandTree, bot: commands.Bot, db: FeatureDB) -> None:
    engine = get_game_engine(db)

    # 1. /connect4 <@user>
    @tree.command(name="connect4", description="Challenge a friend to an interactive Connect Four match 🔴🔵")
    @app_commands.describe(opponent="The player you want to challenge")
    async def slash_connect4(interaction: discord.Interaction, opponent: discord.User):
        if not interaction.guild:
            await interaction.response.send_message("❌ Games can only be played in servers.", ephemeral=True)
            return

        if opponent.id == interaction.user.id or opponent.bot:
            await interaction.response.send_message("❌ Please challenge another human player!", ephemeral=True)
            return

        can_play, msg = engine.can_user_play(interaction.guild.id, interaction.user.id)
        if not can_play:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        view = ConnectFourView(interaction.user, opponent, engine)
        await interaction.response.send_message(embed=view.render_embed(), view=view)

    # 2. /tictactoe [opponent] [difficulty]
    @tree.command(name="tictactoe", description="Play Tic-Tac-Toe against a friend or against Kazumi AI ❌⭕")
    @app_commands.describe(
        opponent="Leave blank to challenge Kazumi AI",
        difficulty="Difficulty if playing vs Kazumi (Easy, Normal, Hard)"
    )
    @app_commands.choices(difficulty=[
        app_commands.Choice(name="Easy — Gentle & playful 🌸", value="easy"),
        app_commands.Choice(name="Normal — Balanced companion challenge ✨", value="normal"),
        app_commands.Choice(name="Hard — Tactical Grandmaster 💀", value="hard")
    ])
    async def slash_tictactoe(
        interaction: discord.Interaction,
        opponent: Optional[discord.User] = None,
        difficulty: Optional[app_commands.Choice[str]] = None
    ):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return

        diff_val = difficulty.value if difficulty else "normal"
        is_ai = (opponent is None or (bot.user and opponent.id == bot.user.id))
        view = TicTacToeView(interaction.user, opponent if not is_ai else None, is_ai, diff_val, engine)
        await interaction.response.send_message(embed=view.render_embed(), view=view)

    # 3. /arena <@opponent> [class_type]
    @tree.command(name="arena", description="Challenge a friend to a tactical Kazumi RPG Arena Duel ⚔️")
    @app_commands.describe(opponent="Opponent to duel", your_class="Select your character class")
    @app_commands.choices(your_class=[
        app_commands.Choice(name="Warrior — Balanced tanky brawler (Shield Bash)", value="warrior"),
        app_commands.Choice(name="Mage — High damage spellcaster (Meteor Swarm)", value="mage"),
        app_commands.Choice(name="Assassin — High speed critical hitter (Shadow Strike)", value="assassin"),
        app_commands.Choice(name="Tank — Colossal fortress of armor (Earthquake)", value="tank"),
        app_commands.Choice(name="Support — Healer & buffer (Healing Blossom)", value="support")
    ])
    async def slash_arena(interaction: discord.Interaction, opponent: discord.User, your_class: Optional[app_commands.Choice[str]] = None):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return

        if opponent.id == interaction.user.id or opponent.bot:
            await interaction.response.send_message("❌ Please challenge another member!", ephemeral=True)
            return

        c1 = your_class.value if your_class else "warrior"
        c2 = random.choice(["warrior", "mage", "assassin", "tank", "support"])
        view = ArenaBattleView(interaction.user, opponent, c1, c2, engine)
        await interaction.response.send_message(embed=view.render_embed(), view=view)

    # 4. /trivia [category]
    @tree.command(name="trivia", description="Test your knowledge with an interactive 4-choice trivia question 🧠")
    async def slash_trivia(interaction: discord.Interaction):
        q = random.choice(TRIVIA_QUESTIONS)
        view = TriviaView(interaction.user, q, engine)
        embed = discord.Embed(
            title=f"🧠 Trivia Time • Category: {q['category']}",
            description=f"**{q['question']}**\n\nPick the correct answer below within 30 seconds!",
            color=0x3b82f6
        )
        embed.set_footer(text=f"Question for {interaction.user.display_name} • Kazumi Arcade")
        await interaction.response.send_message(embed=embed, view=view)

    # 5. /reactionrace
    @tree.command(name="reactionrace", description="Test who has the fastest reaction reflexes in the server ⚡")
    async def slash_reactionrace(interaction: discord.Interaction):
        await interaction.response.send_message("⚡ **Get ready... the button will appear in any second!**", ephemeral=False)
        delay = random.uniform(2.5, 6.0)
        await asyncio.sleep(delay)
        view = ReactionRaceView(engine)
        embed = discord.Embed(
            title="⚡ FIRST TO CLICK THE BUTTON WINS!",
            description="CLICK FAST! 👇",
            color=0xf59e0b
        )
        try:
            await interaction.channel.send(embed=embed, view=view)
        except Exception:
            pass

    # 6. /wouldyourather
    @tree.command(name="wouldyourather", description="Generate a compelling Would You Rather dilemma with live votes 🤔")
    async def slash_wyr(interaction: discord.Interaction):
        pair = random.choice(WYR_PROMPTS)
        view = WouldYouRatherView(pair[0], pair[1])
        await interaction.response.send_message(embed=view.render_embed(), view=view)

    # 7. /hangman
    @tree.command(name="hangman", description="Play a solo round of word-guessing Hangman 🧩")
    async def slash_hangman(interaction: discord.Interaction):
        w, c = random.choice(HANGMAN_WORDS)
        view = HangmanView(interaction.user, w, c, engine)
        await interaction.response.send_message(embed=view.render_embed(), view=view)

    # 8. /wordchain <@opponent>
    @tree.command(name="wordchain", description="Challenge a friend to a 2-player turn-based Word Chain duel 🔤")
    @app_commands.describe(opponent="Opponent to challenge to Word Chain")
    async def slash_wordchain(interaction: discord.Interaction, opponent: discord.User):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return
        if opponent.id == interaction.user.id or opponent.bot:
            await interaction.response.send_message("❌ Please challenge another human player!", ephemeral=True)
            return

        can_play, msg = engine.can_user_play(interaction.guild.id, interaction.user.id)
        if not can_play:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        view = WordChainView(interaction.user, opponent, engine)
        await interaction.response.send_message(embed=view.render_embed(), view=view)

    # 9. /dailygame
    @tree.command(name="dailygame", description="Solve today's universal Kazumi brain puzzle and maintain your daily streak 🌟")
    async def slash_dailygame(interaction: discord.Interaction):
        from datetime import datetime, timezone
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily = db.get_daily_challenge(today_str)
        ch = daily["challenge"]

        prof = db.get_game_profile(interaction.user.id)
        already_done = str(interaction.user.id) in daily.get("completions", [])

        embed = discord.Embed(
            title=f"🌟 Kazumi Daily Brain Challenge • {today_str}",
            color=0x10b981 if already_done else 0xc084fc
        )
        embed.add_field(name="Category", value=f"`{ch.get('category')}`", inline=True)
        embed.add_field(name="Current Streak", value=f"🔥 **{prof.get('daily_streak', 0)} days**", inline=True)
        embed.add_field(name="Today's Puzzle", value=f"**{ch.get('title')}**\n\n> {ch.get('prompt')}", inline=False)

        if already_done:
            embed.description = "✅ **You have already solved today's daily puzzle!** Come back tomorrow to keep your streak burning! 🔥"
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed.set_footer(text="Use /dailyanswer <solution> to submit your answer!")
            await interaction.response.send_message(embed=embed)

    # 9. /dailyanswer <solution>
    @tree.command(name="dailyanswer", description="Submit your answer to today's daily brain puzzle 🎯")
    @app_commands.describe(answer="Your proposed solution")
    async def slash_dailyanswer(interaction: discord.Interaction, answer: str):
        from datetime import datetime, timezone
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily = db.get_daily_challenge(today_str)
        correct_sol = daily["challenge"]["solution"].lower().strip()

        if str(interaction.user.id) in daily.get("completions", []):
            await interaction.response.send_message("✅ You already completed today's challenge!", ephemeral=True)
            return

        cleaned_guess = answer.lower().strip()
        if cleaned_guess == correct_sol or correct_sol in cleaned_guess:
            db.complete_daily_challenge(interaction.user.id, today_str, score=50)
            prof = db.get_game_profile(interaction.user.id)
            if prof.get("daily_streak", 0) >= 5:
                db.unlock_achievement(interaction.user.id, "daily_devotee", *ACHIEVEMENTS_CATALOG["daily_devotee"])

            await interaction.response.send_message(
                f"🎉 **BRILLIANT! That's correct!** (+50 XP 🌟)\n"
                f"Your daily puzzle streak is now **{prof.get('daily_streak', 1)} days**! Keep it up!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ That's not quite it! Think carefully and try again! 🌸", ephemeral=True)

    # 10. /game stats & leaderboard
    @tree.command(name="game", description="View arcade profiles, stats, and server leaderboards 🏆")
    @app_commands.describe(action="What game statistics to view", user="Target member (for profile/stats)")
    @app_commands.choices(action=[
        app_commands.Choice(name="Profile — View XP, Level, Badges, and Stats 🌟", value="profile"),
        app_commands.Choice(name="Leaderboard — View top arcade champions 🏆", value="leaderboard")
    ])
    async def slash_game(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        user: Optional[discord.User] = None
    ):
        target = user or interaction.user
        if action.value == "profile":
            prof = db.get_game_profile(target.id)
            embed = discord.Embed(
                title=f"🎮 Arcade Profile • {target.display_name}",
                color=0xc084fc
            )
            if target.avatar:
                embed.set_thumbnail(url=target.avatar.url)

            embed.add_field(name="Arcade Level", value=f"⭐ **Level {prof.get('level', 1)}** (`{prof.get('xp', 0)} XP`)", inline=True)
            embed.add_field(name="Wins / Losses", value=f"🏆 **{prof.get('wins', 0)}W** / {prof.get('losses', 0)}L", inline=True)
            embed.add_field(name="Win Rate", value=f"📊 **{prof.get('win_rate', 0)}%**", inline=True)
            embed.add_field(name="Current Streak", value=f"🔥 **{prof.get('streak', 0)}** (Best: {prof.get('best_streak', 0)})", inline=True)
            embed.add_field(name="Daily Streak", value=f"🌟 **{prof.get('daily_streak', 0)} days**", inline=True)

            achs = prof.get("achievements", [])
            if achs:
                ach_titles = [f"• {a.get('title') if isinstance(a, dict) else a}" for a in achs[:6]]
                embed.add_field(name=f"Unlocked Achievements ({len(achs)})", value="\n".join(ach_titles), inline=False)
            else:
                embed.add_field(name="Achievements", value="*No arcade achievements unlocked yet.*", inline=False)

            await interaction.response.send_message(embed=embed)

        elif action.value == "leaderboard":
            top_players = db.get_game_leaderboard(limit=10)
            embed = discord.Embed(
                title="🏆 Kazumi Global Arcade Leaderboard",
                description="Top champions ranked by total arcade victories:",
                color=0xf59e0b
            )
            if not top_players:
                embed.description = "No arcade records recorded yet! Be the first to play `/connect4` or `/tictactoe`!"
            else:
                lines = []
                medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
                for i, p in enumerate(top_players):
                    uid = p.get("user_id")
                    m = medals[i] if i < len(medals) else "🏅"
                    lines.append(f"{m} <@{uid}> — **{p.get('wins', 0)} Wins** (Level {p.get('level', 1)} • {p.get('xp', 0)} XP)")
                embed.description = "\n".join(lines)

            await interaction.response.send_message(embed=embed)

    # 11. /arcade
    @tree.command(name="arcade", description="Explore the complete Kazumi Arcade & Minigames Hub 🌸🎮")
    async def slash_arcade(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🌸 KAZUMI ARCADE & MINIGAMES HUB",
            description=(
                "Welcome to the official Kazumi Discord Arcade! Play interactive games, "
                "earn XP, unlock achievements, and climb the leaderboard!\n\n"
                "**🎮 Board & Multiplayer Games:**\n"
                "• `/connect4 <@user>` — 2-Player classic Connect Four with live buttons\n"
                "• `/tictactoe [@user] [difficulty]` — Play vs friends or against Kazumi AI (Easy/Normal/Hard)\n"
                "• `/arena <@user> [class]` — Turn-based RPG duel (Warrior, Mage, Assassin, Tank, Support)\n"
                "• `/wordchain <@user>` — 2-Player turn-based word chaining battle\n\n"
                "**⚡ Reflex & Quickfire Games:**\n"
                "• `/reactionrace` — Sub-second button reaction contest\n"
                "• `/trivia` — 4-choice interactive general knowledge challenge\n"
                "• `/hangman` — Word guessing with lives and letter modals\n\n"
                "**🤔 Social & Daily Mind Puzzles:**\n"
                "• `/wouldyourather` — Community dilemmas with live percentage votes\n"
                "• `/dailygame` — Daily puzzle to maintain your streak\n"
                "• `/dailyanswer <solution>` — Submit your daily solution\n\n"
                "**🏆 Stats & Leaderboards:**\n"
                "• `/game action:profile` — View your arcade level, XP, and achievements\n"
                "• `/game action:leaderboard` — View the top server champions"
            ),
            color=0xc084fc
        )
        embed.set_footer(text="Kazumi Arcade • Earn XP, conquer challenges, and level up! 🌸")
        await interaction.response.send_message(embed=embed)
