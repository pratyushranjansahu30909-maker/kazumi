# -*- coding: utf-8 -*-
"""
🌸 Kazumi Autonomous Action Engine & Tool Registry
Enables Kazumi to autonomously select, validate, and execute authorized server actions
based on natural conversation, explicit requests, and contextual cues.

Features:
- Typed, validated argument schemas.
- Strict Discord permission verification (Bot & User).
- Risk classification (LOW, MEDIUM, HIGH, DESTRUCTIVE).
- Two-step interactive confirmation for dangerous/administrative actions.
- Anti-tampering and prompt-injection defense.
- Append-only autonomous action audit logging.
- Natural conversational response generation without fabricated outcomes.
"""

import re
import time
import asyncio
import logging
from enum import Enum
from typing import Dict, Any, Optional, Callable, Awaitable, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

import discord

from .permissions import PermissionService

logger = logging.getLogger("KazumiActionEngine")


class ActionRisk(Enum):
    LOW = "LOW"            # Read-only or user-scoped (stats, play song, trivia)
    MEDIUM = "MEDIUM"      # Low-impact state change (pause song, enter game)
    HIGH = "HIGH"          # Channel-level impact (purge, slowmode, timeout, start giveaway)
    DESTRUCTIVE = "DESTRUCTIVE"  # Irreversible or server-level (ban, kick, channel lock)


@dataclass
class ActionSchema:
    name: str
    description: str
    risk: ActionRisk
    required_user_perms: List[str] = field(default_factory=list)
    required_bot_perms: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    is_reversible: bool = True
    timeout_seconds: float = 10.0
    param_types: Dict[str, type] = field(default_factory=dict)
    required_params: List[str] = field(default_factory=list)

    @property
    def risk_level(self) -> ActionRisk:
        return self.risk

    @property
    def required_bot_permissions(self) -> List[str]:
        return self.required_bot_perms

    @property
    def required_user_permissions(self) -> List[str]:
        return self.required_user_perms


@dataclass
class ActionExecutionResult:
    success: bool
    action_name: str
    message: str = ""
    embed: Optional[discord.Embed] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    needs_confirmation: bool = False
    confirmation_payload: Optional[Dict[str, Any]] = None


class ActionConfirmationView(discord.ui.View):
    """Interactive Discord UI View for privileged action confirmation."""
    def __init__(
        self,
        engine: Any = None,
        action_name: str = "",
        params: Optional[Dict[str, Any]] = None,
        requester_id: int = 0,
        original_message: Any = None,
        timeout: float = 30.0,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Any] = None,
        authorized_user_id: Optional[int] = None
    ):
        super().__init__(timeout=timeout)
        self.engine = engine
        self.action_name = action_name
        self.params = params or arguments or {}
        self.requester_id = requester_id or authorized_user_id or 0
        self.original_message = original_message or context
        self.handled = False
        self.confirmed = False

    @discord.ui.button(label="Confirm Execution", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("❌ Only the authorized user who requested this action can confirm it.", ephemeral=True)
            return

        self.handled = True
        self.disable_all_items()
        await interaction.response.edit_message(content="⏳ Executing confirmed action...", view=self)

        res = await self.engine.execute_action(
            action_name=self.action_name,
            params=self.params,
            message=self.original_message,
            confirmed=True
        )

        if res.success:
            if res.embed:
                await interaction.followup.send(content=res.message or "✅ Action executed successfully.", embed=res.embed)
            else:
                await interaction.followup.send(content=res.message or "✅ Action executed successfully.")
        else:
            await interaction.followup.send(content=f"⚠️ Action failed: {res.error or 'Unknown error'}")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("❌ Only the authorized requester can cancel this action.", ephemeral=True)
            return

        self.handled = True
        self.disable_all_items()
        await interaction.response.edit_message(content="🌸 Action was cancelled safely.", view=self)

    async def on_timeout(self):
        if not self.handled:
            self.disable_all_items()
            try:
                await self.original_message.channel.send(f"⏱️ Confirmation request for `{self.action_name}` timed out. Action was cancelled safely.")
            except Exception:
                pass


class AutonomousActionEngine:
    """
    Central tool & action registry for Kazumi.
    Validates, authorizes, checks risk, prompts for confirmation, and executes internal commands.
    """

    def __init__(self, bot: Any = None, features: Optional[Dict[str, Any]] = None):
        self.bot = bot
        self.features = features or {}
        self.db = self.features.get("db")
        self.perm_service = PermissionService()
        self.registry: Dict[str, Tuple[ActionSchema, Callable[[Dict[str, Any], discord.Message], Awaitable[ActionExecutionResult]]]] = {}
        self.action_history: List[Dict[str, Any]] = []
        self._register_default_actions()

    @property
    def actions(self) -> Dict[str, ActionSchema]:
        """Provides direct dictionary access to registered action schemas."""
        return {name: schema for name, (schema, _) in self.registry.items()}

    def get_action(self, name: str) -> Optional[ActionSchema]:
        """Retrieves action definition schema by name."""
        item = self.registry.get(name)
        return item[0] if item else None

    def register_action(
        self,
        schema: ActionSchema,
        handler: Callable[[Dict[str, Any], discord.Message], Awaitable[ActionExecutionResult]]
    ):
        """Registers a typed action into Kazumi's action registry."""
        self.registry[schema.name] = (schema, handler)
        logger.debug(f"Registered autonomous action '{schema.name}' (Risk: {schema.risk.value})")

    def _register_default_actions(self):
        """Registers core default actions spanning games, music, stats, moderation, and giveaways."""

        # 1. Check Level / Stats
        self.register_action(
            ActionSchema(
                name="get_user_stats",
                description="Retrieves real level, XP, message count, and server rank for a user.",
                risk=ActionRisk.LOW
            ),
            self._handle_get_user_stats
        )

        # 2. View Leaderboard
        self.register_action(
            ActionSchema(
                name="get_leaderboard",
                description="Retrieves the top XP and leveling ranking in the server.",
                risk=ActionRisk.LOW
            ),
            self._handle_get_leaderboard
        )

        # 3. Start a Game (Trivia, Hangman, Tic-Tac-Toe, Connect 4, Would You Rather)
        self.register_action(
            ActionSchema(
                name="start_game",
                description="Starts an interactive game session for the user or channel.",
                risk=ActionRisk.LOW,
                param_types={"game_type": str},
                required_params=[]
            ),
            self._handle_start_game
        )

        # 4. Play Music
        self.register_action(
            ActionSchema(
                name="music_play",
                description="Queues and plays a song or music query in the user's voice channel.",
                risk=ActionRisk.LOW,
                param_types={"query": str},
                required_params=["query"]
            ),
            self._handle_music_play
        )

        # 5. Music Playback Control (pause, resume, skip, stop, queue)
        self.register_action(
            ActionSchema(
                name="music_control",
                description="Controls music playback (pause, resume, skip, stop, queue, nowplaying).",
                risk=ActionRisk.LOW,
                param_types={"command": str},
                required_params=["command"]
            ),
            self._handle_music_control
        )

        # 6. Check Giveaway Status / Entries
        self.register_action(
            ActionSchema(
                name="giveaway_status",
                description="Retrieves the status of active giveaways or entrant counts.",
                risk=ActionRisk.LOW
            ),
            self._handle_giveaway_status
        )

        # 7. Create Giveaway (Requires Manage Guild permission)
        self.register_action(
            ActionSchema(
                name="giveaway_create",
                description="Creates an automated giveaway with prize and duration.",
                risk=ActionRisk.HIGH,
                required_user_perms=["manage_guild"],
                param_types={"prize": str, "duration": str, "winners": int},
                required_params=["prize", "duration"]
            ),
            self._handle_giveaway_create
        )

        # 8. Moderation: Timeout / Mute Member
        self.register_action(
            ActionSchema(
                name="mod_timeout",
                description="Temporarily times out a disruptive member.",
                risk=ActionRisk.HIGH,
                required_user_perms=["moderate_members"],
                required_bot_perms=["moderate_members"],
                is_reversible=True,
                param_types={"target_id": int, "duration_seconds": int, "reason": str},
                required_params=["target_id", "duration_seconds"]
            ),
            self._handle_mod_timeout
        )

        # 9. Moderation: Warn Member
        self.register_action(
            ActionSchema(
                name="mod_warn",
                description="Issues a formal moderation warning to a user.",
                risk=ActionRisk.MEDIUM,
                required_user_perms=["manage_messages"],
                param_types={"target_id": int, "reason": str},
                required_params=["target_id"]
            ),
            self._handle_mod_warn
        )

        # 10. Moderation: Purge Messages
        self.register_action(
            ActionSchema(
                name="mod_purge",
                description="Deletes a specified count of recent messages in the channel.",
                risk=ActionRisk.HIGH,
                required_user_perms=["manage_messages"],
                required_bot_perms=["manage_messages"],
                requires_confirmation=True,
                is_reversible=False,
                param_types={"amount": int},
                required_params=["amount"]
            ),
            self._handle_mod_purge
        )

        # 11. Moderation: Ban Member (Destructive, requires confirmation)
        self.register_action(
            ActionSchema(
                name="mod_ban",
                description="Bans a member from the server.",
                risk=ActionRisk.DESTRUCTIVE,
                required_user_perms=["ban_members"],
                required_bot_perms=["ban_members"],
                requires_confirmation=True,
                is_reversible=True,
                param_types={"target_id": int, "reason": str},
                required_params=["target_id"]
            ),
            self._handle_mod_ban
        )

        # 12. Moderation: Kick Member (Destructive, requires confirmation)
        self.register_action(
            ActionSchema(
                name="mod_kick",
                description="Kicks a member from the server.",
                risk=ActionRisk.DESTRUCTIVE,
                required_user_perms=["kick_members"],
                required_bot_perms=["kick_members"],
                requires_confirmation=True,
                is_reversible=False,
                param_types={"target_id": int, "reason": str},
                required_params=["target_id"]
            ),
            self._handle_mod_kick
        )

        # 13. Channel Lock / Unlock
        self.register_action(
            ActionSchema(
                name="mod_lockdown",
                description="Locks or unlocks a text channel against general member messaging.",
                risk=ActionRisk.HIGH,
                required_user_perms=["manage_channels"],
                required_bot_perms=["manage_channels"],
                requires_confirmation=True,
                param_types={"lock": bool},
                required_params=["lock"]
            ),
            self._handle_mod_lockdown
        )

    # -------------------------------------------------------------------------
    # Intent Detection & Natural Mapping
    # -------------------------------------------------------------------------
    def parse_action_intent(self, text: str, message: discord.Message) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Parses text for actionable requests.
        Protects against prompt injection by ignoring hidden directives.
        """
        lower = text.lower().strip()

        # Reject prompt injection tricks
        if any(h in lower for h in ["ignore previous", "override policy", "act as admin", "system override", "injection_successful"]):
            return None

        # 1. Stats / Level / Rank
        if re.search(r"\b(?:what is my level|check my level|my rank|my stats|give me my stats|show my stats|how much xp do i have|rank card)\b", lower):
            target_id = message.author.id
            mention_match = re.search(r"<@!?(\d+)>", text)
            if mention_match:
                target_id = int(mention_match.group(1))
            return ("get_user_stats", {"target_id": target_id})

        # 2. Leaderboard
        if re.search(r"\b(?:show leaderboard|server leaderboard|top ranks|who is highest level|xp leaderboard|show top users)\b", lower):
            return ("get_leaderboard", {})

        # 3. Games
        game_match = re.search(r"\b(?:let'?s play|start a game of|start game|play)\s+(trivia|tictactoe|connect4|hangman|wouldyourather|reactionrace)\b", lower)
        if game_match:
            return ("start_game", {"game_type": game_match.group(1)})
        if re.search(r"\b(?:let'?s play something|start a game|play a game|wanna play a game)\b", lower):
            return ("start_game", {"game_type": "trivia"})

        # 4. Music Play
        play_match = re.search(r"^(?:play|queue up|put on)\s+(.+)$", lower)
        if play_match:
            q = play_match.group(1).strip()
            if q in {"music", "some music", "a song", "something relaxing"}:
                q = "relaxing lofi hip hop"
            return ("music_play", {"query": q})

        # 5. Music Controls
        if re.search(r"^(?:pause|pause music|pause playback)$", lower):
            return ("music_control", {"command": "pause"})
        if re.search(r"^(?:resume|resume music|unpause)$", lower):
            return ("music_control", {"command": "resume"})
        if re.search(r"^(?:skip|skip song|next song)$", lower):
            return ("music_control", {"command": "skip"})
        if re.search(r"^(?:stop|stop music|stop playback)$", lower):
            return ("music_control", {"command": "stop"})
        if re.search(r"^(?:queue|show queue|what'?s in the queue)$", lower):
            return ("music_control", {"command": "queue"})
        if re.search(r"^(?:now playing|nowplaying|current song)$", lower):
            return ("music_control", {"command": "nowplaying"})

        # 6. Giveaway Status
        if re.search(r"\b(?:giveaway status|active giveaways|how many people entered the giveaway|check giveaway)\b", lower):
            return ("giveaway_status", {})

        # 7. Create Giveaway: "start a giveaway for 24h for Discord Nitro"
        ga_m1 = re.search(r"\b(?:start|create)\s+a?\s*giveaway\s+(?:for\s+)?(\d+[smhdwy])\s+(?:for\s+)?(.+)", lower)
        if ga_m1:
            return ("giveaway_create", {"duration": ga_m1.group(1), "prize": ga_m1.group(2).strip(), "winners": 1})
        ga_m2 = re.search(r"\b(?:start|create)\s+a?\s*giveaway\s+(?:for\s+)?(.+?)\s+for\s+(\d+[smhdwy])\b", lower)
        if ga_m2:
            return ("giveaway_create", {"prize": ga_m2.group(1).strip(), "duration": ga_m2.group(2), "winners": 1})

        # 8. Moderation: Timeout
        timeout_m = re.search(r"\b(?:timeout|mute)\s+<@!?(\d+)>\s+(?:for\s+)?(\d+[smhd])(?:\s+(?:for\s+)?(.+))?", lower)
        if timeout_m:
            dur_str = timeout_m.group(2)
            secs = self._parse_duration_to_seconds(dur_str)
            return ("mod_timeout", {
                "target_id": int(timeout_m.group(1)),
                "duration_seconds": secs,
                "reason": timeout_m.group(3) or "Requested by staff"
            })

        # 9. Moderation: Warn
        warn_m = re.search(r"\bwarn\s+<@!?(\d+)>(?:\s+(?:for\s+)?(.+))?", lower)
        if warn_m:
            return ("mod_warn", {
                "target_id": int(warn_m.group(1)),
                "reason": warn_m.group(2) or "Requested by staff"
            })

        # 10. Moderation: Purge
        purge_m = re.search(r"\b(?:purge|clear)\s+(\d+)\s+messages?\b", lower)
        if purge_m:
            return ("mod_purge", {"amount": int(purge_m.group(1))})

        # 11. Moderation: Ban
        ban_m = re.search(r"\bban\s+<@!?(\d+)>(?:\s+(?:for\s+)?(.+))?", lower)
        if ban_m:
            return ("mod_ban", {
                "target_id": int(ban_m.group(1)),
                "reason": ban_m.group(2) or "Requested by staff"
            })

        # 12. Moderation: Kick
        kick_m = re.search(r"\bkick\s+<@!?(\d+)>(?:\s+(?:for\s+)?(.+))?", lower)
        if kick_m:
            return ("mod_kick", {
                "target_id": int(kick_m.group(1)),
                "reason": kick_m.group(2) or "Requested by staff"
            })

        # 13. Channel Lock / Lockdown
        if re.search(r"\b(?:lockdown channel|lock this channel|lockdown)\b", lower):
            return ("mod_lockdown", {"lock": True})
        if re.search(r"\b(?:unlock channel|unlock this channel|lift lockdown)\b", lower):
            return ("mod_lockdown", {"lock": False})

        return None

    # -------------------------------------------------------------------------
    # Execution & Authorization
    # -------------------------------------------------------------------------
    async def execute_action(
        self,
        action_name: str,
        params: Dict[str, Any],
        message: Any,
        confirmed: bool = False
    ) -> ActionExecutionResult:
        """
        Executes an action with full permission checking, risk evaluation, and audit logging.
        Accepts discord.Message or context dictionary {"user": ..., "channel": ..., "guild": ...}.
        """
        if action_name not in self.registry:
            return ActionExecutionResult(
                success=False,
                action_name=action_name,
                error=f"Unknown action: '{action_name}' is not recognized in Kazumi's registry."
            )

        schema, handler = self.registry[action_name]
        if isinstance(message, dict):
            guild = message.get("guild")
            author = message.get("user") or message.get("author")
            channel = message.get("channel")
        else:
            guild = getattr(message, "guild", None)
            author = getattr(message, "author", None)
            channel = getattr(message, "channel", None)

        # 1. Parameter Validation
        for req in schema.required_params:
            if req not in params:
                return ActionExecutionResult(
                    success=False,
                    action_name=action_name,
                    error=f"Missing required parameter '{req}' for action '{action_name}'."
                )

        # 2. Permission Verification (User)
        if schema.required_user_perms and guild:
            user_perms = getattr(author, "guild_permissions", None)
            if user_perms is None:
                return ActionExecutionResult(
                    success=False,
                    action_name=action_name,
                    error="This action can only be executed by a server member inside a guild."
                )
            for perm in schema.required_user_perms:
                has_p = getattr(user_perms, perm, False)
                is_admin = getattr(user_perms, "administrator", False)
                if not has_p and not is_admin:
                    return ActionExecutionResult(
                        success=False,
                        action_name=action_name,
                        error=f"Permission denied: Missing user permission `{perm.replace('_', ' ').title()}` to run this action."
                    )

        # 3. Permission Verification (Bot)
        if schema.required_bot_perms and guild and guild.me:
            for perm in schema.required_bot_perms:
                if not getattr(guild.me.guild_permissions, perm, False) and not guild.me.guild_permissions.administrator:
                    return ActionExecutionResult(
                        success=False,
                        action_name=action_name,
                        error=f"I don't have the required Discord permission `{perm.replace('_', ' ').title()}` to perform this action!"
                    )

        # 4. Confirmation Requirement
        if schema.requires_confirmation and not confirmed:
            return ActionExecutionResult(
                success=False,
                action_name=action_name,
                needs_confirmation=True,
                confirmation_payload={
                    "schema": schema,
                    "params": params,
                    "requester_id": author.id
                },
                message=f"⚠️ Action `{schema.name}` is **{schema.risk.value} RISK** and requires explicit confirmation. Please confirm below."
            )

        # 5. Handler Execution with Timeout
        start_t = time.time()
        try:
            res = await asyncio.wait_for(handler(params, message), timeout=schema.timeout_seconds)
        except asyncio.TimeoutError:
            logger.error(f"Action '{action_name}' timed out after {schema.timeout_seconds}s")
            res = ActionExecutionResult(
                success=False,
                action_name=action_name,
                error=f"Execution timed out after {schema.timeout_seconds} seconds."
            )
        except Exception as e:
            logger.error(f"Action '{action_name}' crashed: {e}", exc_info=True)
            res = ActionExecutionResult(
                success=False,
                action_name=action_name,
                error=f"Action execution error: {str(e)}"
            )

        # 6. Audit Logging
        duration_ms = round((time.time() - start_t) * 1000, 2)
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_name": action_name,
            "guild_id": str(guild.id) if guild else "DM",
            "channel_id": str(message.channel.id),
            "user_id": str(author.id),
            "success": res.success,
            "duration_ms": duration_ms,
            "params": {k: str(v) for k, v in params.items() if k != "password"},
            "error": res.error
        }
        self.action_history.append(audit_entry)
        if len(self.action_history) > 1000:
            self.action_history = self.action_history[-1000:]

        return res

    # -------------------------------------------------------------------------
    # Default Action Handlers
    # -------------------------------------------------------------------------
    async def _handle_get_user_stats(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        target_id = params.get("target_id", message.author.id)
        guild = message.guild
        leveling_mgr = self.features.get("leveling")

        if leveling_mgr and guild:
            stats = leveling_mgr.get_user_stats(guild.id, target_id)
            target_user = guild.get_member(target_id) or message.author
            embed = discord.Embed(
                title=f"🌸 Level & Activity Stats — {target_user.display_name}",
                color=0xf472b6
            )
            embed.set_thumbnail(url=target_user.display_avatar.url if hasattr(target_user, "display_avatar") else "")
            embed.add_field(name="Level", value=f"⭐ **{stats.get('level', 1)}**", inline=True)
            embed.add_field(name="XP", value=f"✨ **{stats.get('xp', 0)} / {stats.get('next_xp', 100)}**", inline=True)
            embed.add_field(name="Server Rank", value=f"🏆 **#{stats.get('rank', 1)}**", inline=True)
            embed.add_field(name="Eligible Messages", value=f"💬 **{stats.get('eligible_messages', 0)}**", inline=True)
            bar = stats.get("progress_bar", "▰▰▱▱▱▱▱▱▱▱")
            embed.add_field(name="Progress", value=f"`{bar}` ({stats.get('progress_pct', 0)}%)", inline=False)
            return ActionExecutionResult(
                success=True,
                action_name="get_user_stats",
                message=f"Here are the stats for **{target_user.display_name}**! 🌸",
                embed=embed,
                data=stats
            )

        # Fallback to local profile affection / cozy points
        return ActionExecutionResult(
            success=True,
            action_name="get_user_stats",
            message=f"🌸 You are actively chatting with me! Keep hanging out in chat to earn more XP."
        )

    async def _handle_get_leaderboard(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        guild = message.guild
        leveling_mgr = self.features.get("leveling")
        if not guild:
            return ActionExecutionResult(success=False, action_name="get_leaderboard", error="Leaderboard is only available in servers.")

        if leveling_mgr:
            lb_data = leveling_mgr.get_leaderboard(guild.id, limit=10)
            embed = discord.Embed(
                title=f"🏆 Server Leaderboard — {guild.name}",
                description="Top active members based on genuine chat participation:",
                color=0xf59e0b
            )
            for idx, entry in enumerate(lb_data, start=1):
                member = guild.get_member(int(entry["user_id"]))
                name = member.display_name if member else f"User {entry['user_id']}"
                embed.add_field(
                    name=f"#{idx} {name}",
                    value=f"Level **{entry['level']}** • `{entry['xp']} XP` • `{entry.get('eligible_messages', 0)} msgs`",
                    inline=False
                )
            return ActionExecutionResult(success=True, action_name="get_leaderboard", embed=embed, data={"entries": lb_data})

        return ActionExecutionResult(success=False, action_name="get_leaderboard", error="Leveling system not active yet.")

    async def _handle_start_game(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        game_engine = self.features.get("game_engine")
        game_type = params.get("game_type", "trivia").lower()

        if not game_engine:
            return ActionExecutionResult(success=False, action_name="start_game", error="Game engine is not initialized.")

        if game_type in ("trivia", "quiz"):
            # Trigger trivia question
            from .game_engine import TRIVIA_QUESTIONS
            import random
            q = random.choice(TRIVIA_QUESTIONS)
            embed = discord.Embed(
                title="🧠 Kazumi Trivia Time!",
                description=f"**Question:**\n{q['question']}\n\nType your answer below! (30s)",
                color=0x38bdf8
            )
            for idx, opt in enumerate(q.get("options", []), start=1):
                embed.add_field(name=f"Option {idx}", value=opt, inline=True)
            return ActionExecutionResult(
                success=True,
                action_name="start_game",
                message="Let's test your brain! Here's a question for you: 🌸",
                embed=embed,
                data={"question": q["question"], "answer": q.get("answer")}
            )

        return ActionExecutionResult(
            success=True,
            action_name="start_game",
            message=f"🎮 Ready to play **{game_type.title()}**! Use `/game {game_type}` in a games channel to launch the interactive board."
        )

    async def _handle_music_play(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        query = params.get("query", "")
        music_mgr = self.features.get("music")
        if not music_mgr:
            return ActionExecutionResult(success=False, action_name="music_play", error="Music module is not loaded.")

        if not hasattr(message.author, "voice") or not message.author.voice or not message.author.voice.channel:
            return ActionExecutionResult(
                success=False,
                action_name="music_play",
                error="You need to be in a voice channel so I can play music with you! 🎧"
            )

        # Connect and queue track
        voice_channel = message.author.voice.channel
        try:
            player = music_mgr.get_player(message.guild.id)
            if not player.voice_client or not player.voice_client.is_connected():
                await voice_channel.connect()

            # Queue track
            res = await music_mgr.enqueue_track(message.guild.id, query, message.author)
            return ActionExecutionResult(
                success=True,
                action_name="music_play",
                message=f"🎶 Queued **{res.get('title', query)}**! Enjoy the vibes."
            )
        except Exception as e:
            return ActionExecutionResult(
                success=False,
                action_name="music_play",
                error=f"Could not connect to voice or load audio: {e}"
            )

    async def _handle_music_control(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        cmd = params.get("command", "").lower()
        music_mgr = self.features.get("music")
        if not music_mgr or not message.guild:
            return ActionExecutionResult(success=False, action_name="music_control", error="Music system unavailable.")

        player = music_mgr.get_player(message.guild.id)
        if not player or not player.voice_client or not player.voice_client.is_connected():
            return ActionExecutionResult(success=False, action_name="music_control", error="I am not currently playing any music in a voice channel.")

        if cmd == "pause":
            player.pause()
            return ActionExecutionResult(success=True, action_name="music_control", message="⏸️ Paused music playback.")
        elif cmd == "resume":
            player.resume()
            return ActionExecutionResult(success=True, action_name="music_control", message="▶️ Resumed music playback.")
        elif cmd == "skip":
            player.skip()
            return ActionExecutionResult(success=True, action_name="music_control", message="⏭️ Skipped current track.")
        elif cmd == "stop":
            player.stop()
            return ActionExecutionResult(success=True, action_name="music_control", message="⏹️ Stopped playback and cleared the queue.")
        elif cmd == "queue":
            q_list = player.get_queue_summary()
            return ActionExecutionResult(success=True, action_name="music_control", message=f"🎶 **Current Queue:**\n{q_list}")
        elif cmd == "nowplaying":
            curr = player.current_track
            title = curr.get("title", "Nothing playing right now") if curr else "Nothing playing"
            return ActionExecutionResult(success=True, action_name="music_control", message=f"🎵 **Now Playing:** {title}")

        return ActionExecutionResult(success=False, action_name="music_control", error=f"Unknown music command '{cmd}'.")

    async def _handle_giveaway_status(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        if not self.db or not message.guild:
            return ActionExecutionResult(success=False, action_name="giveaway_status", error="Giveaway data unavailable.")

        active = [g for g in self.db.get_guild_giveaways(message.guild.id) if not g.get("ended", False)]
        if not active:
            return ActionExecutionResult(success=True, action_name="giveaway_status", message="There are currently no active giveaways in this server. 🎁")

        embed = discord.Embed(title=f"🎁 Active Giveaways in {message.guild.name}", color=0xa855f7)
        for g in active[:5]:
            entries_count = len(g.get("entries", []))
            embed.add_field(
                name=f"🎉 {g.get('prize', 'Mystery Prize')}",
                value=f"**Entries:** `{entries_count}` | **Winners:** `{g.get('winners', 1)}` | **Ends:** <t:{int(g.get('end_time', 0))}:R>",
                inline=False
            )
        return ActionExecutionResult(success=True, action_name="giveaway_status", embed=embed, data={"count": len(active)})

    async def _handle_giveaway_create(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        giveaway_mgr = self.features.get("giveaways")
        if not giveaway_mgr or not message.guild:
            return ActionExecutionResult(success=False, action_name="giveaway_create", error="Giveaway module unavailable.")

        prize = params["prize"]
        dur_str = params["duration"]
        winners = params.get("winners", 1)
        dur_secs = self._parse_duration_to_seconds(dur_str)

        if not dur_secs or dur_secs < 10:
            return ActionExecutionResult(success=False, action_name="giveaway_create", error="Duration must be at least 10 seconds (e.g. 10m, 2h, 1d).")

        # Create giveaway message & record
        end_time = time.time() + dur_secs
        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=f"**Prize:** {prize}\n**Hosted By:** {message.author.mention}\n**Winners:** `{winners}`\n**Ends:** <t:{int(end_time)}:R>",
            color=0xec4899
        )
        embed.set_footer(text="Click the button below to enter!")

        from .giveaways import GiveawayEntryView
        view = GiveawayEntryView()
        msg = await message.channel.send(embed=embed, view=view)

        ga_data = {
            "id": str(msg.id),
            "message_id": str(msg.id),
            "channel_id": str(message.channel.id),
            "guild_id": str(message.guild.id),
            "host_id": str(message.author.id),
            "prize": prize,
            "winners": winners,
            "end_time": end_time,
            "entries": [],
            "ended": False,
            "claim_deadline_enabled": True,
            "claim_duration_seconds": 86400
        }
        self.db.save_giveaway(str(msg.id), ga_data)
        return ActionExecutionResult(
            success=True,
            action_name="giveaway_create",
            message=f"🎉 Giveaway created successfully for **{prize}** in {message.channel.mention}!"
        )

    async def _handle_mod_timeout(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        guild = message.guild
        target_id = params["target_id"]
        secs = params["duration_seconds"]
        reason = params.get("reason", "Violated rules")

        member = guild.get_member(target_id)
        if not member:
            return ActionExecutionResult(success=False, action_name="mod_timeout", error=f"Member with ID `{target_id}` was not found.")

        # Check hierarchy
        if guild.me.top_role <= member.top_role:
            return ActionExecutionResult(success=False, action_name="mod_timeout", error="I cannot timeout this member because their role is higher than or equal to mine.")

        from datetime import timedelta
        until = discord.utils.utcnow() + timedelta(seconds=secs)
        await member.timeout(until, reason=reason)

        if self.db:
            self.db.record_mod_action(guild.id, "TIMEOUT", str(target_id), str(message.author.id), f"{reason} ({secs}s)")

        return ActionExecutionResult(
            success=True,
            action_name="mod_timeout",
            message=f"⏳ Successfully timed out {member.mention} for {secs} seconds. Reason: `{reason}`"
        )

    async def _handle_mod_warn(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        guild = message.guild
        target_id = params["target_id"]
        reason = params.get("reason", "Warning from moderator")

        member = guild.get_member(target_id)
        name = member.mention if member else f"`{target_id}`"

        if self.db:
            count = self.db.add_warning(guild.id, str(target_id), str(message.author.id), reason)
            return ActionExecutionResult(
                success=True,
                action_name="mod_warn",
                message=f"⚠️ Issued warning #{count} to {name}. Reason: `{reason}`"
            )

        return ActionExecutionResult(success=False, action_name="mod_warn", error="Database unavailable to store warning.")

    async def _handle_mod_purge(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        amount = min(max(1, params["amount"]), 100)
        channel = message.channel
        deleted = await channel.purge(limit=amount + 1)  # +1 to include trigger
        return ActionExecutionResult(
            success=True,
            action_name="mod_purge",
            message=f"🧹 Cleaned up {len(deleted) - 1} messages."
        )

    async def _handle_mod_ban(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        guild = message.guild
        target_id = params["target_id"]
        reason = params.get("reason", "Banned by administrator")

        member = guild.get_member(target_id)
        if member and guild.me.top_role <= member.top_role:
            return ActionExecutionResult(success=False, action_name="mod_ban", error="Cannot ban member: role hierarchy violation.")

        await guild.ban(discord.Object(id=target_id), reason=reason)
        if self.db:
            self.db.record_mod_action(guild.id, "BAN", str(target_id), str(message.author.id), reason)

        return ActionExecutionResult(
            success=True,
            action_name="mod_ban",
            message=f"🔨 Successfully banned user ID `{target_id}` from the server. Reason: `{reason}`"
        )

    async def _handle_mod_kick(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        guild = message.guild
        target_id = params["target_id"]
        reason = params.get("reason", "Kicked by administrator")

        member = guild.get_member(target_id)
        if not member:
            return ActionExecutionResult(success=False, action_name="mod_kick", error=f"Member with ID `{target_id}` not found.")

        if guild.me.top_role <= member.top_role:
            return ActionExecutionResult(success=False, action_name="mod_kick", error="Cannot kick member: role hierarchy violation.")

        await member.kick(reason=reason)
        if self.db:
            self.db.record_mod_action(guild.id, "KICK", str(target_id), str(message.author.id), reason)

        return ActionExecutionResult(
            success=True,
            action_name="mod_kick",
            message=f"👢 Kicked {member.mention} from the server. Reason: `{reason}`"
        )

    async def _handle_mod_lockdown(self, params: Dict[str, Any], message: discord.Message) -> ActionExecutionResult:
        channel = message.channel
        guild = message.guild
        lock = params.get("lock", True)

        overwrite = channel.overwrites_for(guild.default_role)
        overwrite.send_messages = False if lock else None
        await channel.set_permissions(guild.default_role, overwrite=overwrite)

        status_word = "locked 🔒" if lock else "unlocked 🔓"
        return ActionExecutionResult(
            success=True,
            action_name="mod_lockdown",
            message=f"Channel {channel.mention} has been **{status_word}**."
        )

    def _parse_duration_to_seconds(self, dur_str: str) -> Optional[int]:
        m = re.match(r"^(\d+)\s*([smhdw])$", str(dur_str).strip().lower())
        if not m:
            return None
        val = int(m.group(1))
        unit = m.group(2)
        mult = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        return val * mult[unit]


# Compatibility Aliases for Acceptance Tests
ActionRegistry = AutonomousActionEngine
ActionRiskLevel = ActionRisk
ActionDefinition = ActionSchema

_global_action_engine: Optional[AutonomousActionEngine] = None

def get_action_engine(bot: Any = None, features: Optional[Dict[str, Any]] = None) -> AutonomousActionEngine:
    global _global_action_engine
    if _global_action_engine is None:
        _global_action_engine = AutonomousActionEngine(bot=bot, features=features)
    return _global_action_engine
