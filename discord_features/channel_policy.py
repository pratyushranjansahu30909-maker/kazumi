# -*- coding: utf-8 -*-
"""
🌸 KAZUMI CENTRAL CHANNEL POLICY SYSTEM (PHASE 3)
==================================================
Architectural Flow:
Discord Event -> Identify Context -> Load Channel Policy -> Validate Permissions -> Route Feature -> Execute -> Respond or Log

Guarantees:
1. Strict channel-specific feature boundaries (not just hiding help commands).
2. Category-level defaults and channel-level overrides.
3. Configurable channel IDs with canonical fallback resolution.
4. Robust safety checks: No unsolicited AI paragraphs in #general, single redirect reply.
5. Strict protection against unauthorized moderation, staff log leaks, and AI chat in read-only channels.
"""

import re
import logging
from enum import Enum, auto
from typing import Optional, Dict, Set, Any, Tuple, Union

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("KazumiChannelPolicy")


class FeatureGroup(Enum):
    """Functional groups of bot capabilities that can be permitted or denied."""
    AI_CHAT = auto()                # Natural conversational AI (full conversation)
    AI_MENTION_REDIRECT = auto()    # Polite redirect reply when bot is mentioned in observation channels
    CONTEXTUAL_REACTIONS = auto()   # Emotion/contextual emoji reactions
    GAMES = auto()                  # Games, arcade, trivia, XP, achievements
    GIVEAWAYS = auto()              # Giveaway creation, entry, reroll, conclusion
    MUSIC = auto()                  # Voice music playback, queue controls
    MODERATION = auto()             # Warn, mute, kick, ban, purge, slowmode, automod
    ANNOUNCEMENTS = auto()          # Official announcement publishing
    WELCOME_EVENTS = auto()         # New-member greeting cards & personalized poems
    ROLE_SELECTION = auto()         # Self-service role assignment buttons/menus
    STAFF_COMMANDS = auto()         # Diagnostics, bot-testing, audit logs, cases
    STAGE_EVENTS = auto()           # Stage instance creation, speaker controls, stage events
    SERVER_INFO = auto()            # Utility commands: /help, /serverinfo, /userinfo, /ping, /uptime


class ChannelPolicyType(Enum):
    """Designated policy modes for channels across Euphoria."""
    EVENTS_ONLY = "EVENTS_ONLY"                 # #welcome, #events
    READ_ONLY = "READ_ONLY"                     # #rules
    ANNOUNCEMENTS_ONLY = "ANNOUNCEMENTS_ONLY"   # #announcements
    GUIDE_ONLY = "GUIDE_ONLY"                   # #server-guide
    ROLE_SELECTION_ONLY = "ROLE_SELECTION_ONLY" # #roles
    OBSERVATION_ONLY = "OBSERVATION_ONLY"       # #general
    INTRODUCTIONS_ONLY = "INTRODUCTIONS_ONLY"   # #introductions
    MEDIA_OBSERVATION = "MEDIA_OBSERVATION"     # #media
    HUMOR_OBSERVATION = "HUMOR_OBSERVATION"     # #memes
    FORUM_QA = "FORUM_QA"                       # #questions (Forum)
    FORUM_SUGGESTIONS = "FORUM_SUGGESTIONS"     # #suggestions (Forum)
    ACTIVE_CHAT = "ACTIVE_CHAT"                 # #kazumi-chat
    COMMANDS_ONLY = "COMMANDS_ONLY"             # #bot-commands
    GAMEPLAY_ONLY = "GAMEPLAY_ONLY"             # #games
    GIVEAWAYS_ONLY = "GIVEAWAYS_ONLY"           # #giveaways
    MUSIC_CONTROL_ONLY = "MUSIC_CONTROL_ONLY"   # #music-commands
    VOICE_FEATURES_ONLY = "VOICE_FEATURES_ONLY" # Voice channels
    STAGE_EVENT_ONLY = "STAGE_EVENT_ONLY"       # Stage channels
    STAFF_ONLY = "STAFF_ONLY"                   # #staff-chat, #mod-logs, #kazumi-logs, #bot-testing
    DM_POLICY = "DM_POLICY"                     # Direct Messages
    DEFAULT_PUBLIC = "DEFAULT_PUBLIC"           # Fallback for unrecognized public channels


class ChannelPolicy:
    """Defines permission rules, allowed features, and constraints for a channel policy."""

    def __init__(
        self,
        name: ChannelPolicyType,
        allowed_features: Set[FeatureGroup],
        allow_ai_chat: bool = False,
        allow_mentions: bool = False,
        prohibit_unsolicited: bool = True,
        allow_reactions: bool = False,
        allow_games: bool = False,
        allow_moderation: bool = False,
        allow_automated_messages: bool = False,
        is_staff_only: bool = False,
        preferred_redirect_channel: Optional[str] = "kazumi-chat",
        description: str = ""
    ):
        self.name = name
        self.allowed_features = allowed_features
        self.allow_ai_chat = allow_ai_chat
        self.allow_mentions = allow_mentions
        self.prohibit_unsolicited = prohibit_unsolicited
        self.allow_reactions = allow_reactions
        self.allow_games = allow_games
        self.allow_moderation = allow_moderation
        self.allow_automated_messages = allow_automated_messages
        self.is_staff_only = is_staff_only
        self.preferred_redirect_channel = preferred_redirect_channel
        self.description = description

    def is_feature_allowed(self, feature: FeatureGroup) -> bool:
        return feature in self.allowed_features


# ==============================================================================
# CANONICAL POLICY DEFINITION MATRIX (Phase 3 Specification)
# ==============================================================================
POLICY_DEFINITIONS: Dict[ChannelPolicyType, ChannelPolicy] = {
    # A. #welcome — EVENTS_ONLY
    ChannelPolicyType.EVENTS_ONLY: ChannelPolicy(
        name=ChannelPolicyType.EVENTS_ONLY,
        allowed_features={FeatureGroup.WELCOME_EVENTS},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=True,
        preferred_redirect_channel="kazumi-chat",
        description="Dedicated solely to newcomer welcome messages, welcome poems, and server instructions."
    ),

    # B. #rules — READ_ONLY
    ChannelPolicyType.READ_ONLY: ChannelPolicy(
        name=ChannelPolicyType.READ_ONLY,
        allowed_features=set(),
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        description="Strict read-only server rules. AI chat, games, and reactions completely prohibited."
    ),

    # C. #announcements — ANNOUNCEMENTS_ONLY
    ChannelPolicyType.ANNOUNCEMENTS_ONLY: ChannelPolicy(
        name=ChannelPolicyType.ANNOUNCEMENTS_ONLY,
        allowed_features={FeatureGroup.ANNOUNCEMENTS},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=True,
        description="Official server broadcasts and verified notices only. Requires staff authorization."
    ),

    # D. #server-guide — GUIDE_ONLY
    ChannelPolicyType.GUIDE_ONLY: ChannelPolicy(
        name=ChannelPolicyType.GUIDE_ONLY,
        allowed_features={FeatureGroup.SERVER_INFO},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        description="Server navigation directory and instructions. No conversational AI or games."
    ),

    # E. #roles — ROLE_SELECTION_ONLY
    ChannelPolicyType.ROLE_SELECTION_ONLY: ChannelPolicy(
        name=ChannelPolicyType.ROLE_SELECTION_ONLY,
        allowed_features={FeatureGroup.ROLE_SELECTION, FeatureGroup.SERVER_INFO},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        description="Self-service role menus and role explanation cards only. Strict allowlist enforced."
    ),

    # F. #general — OBSERVATION_ONLY
    ChannelPolicyType.OBSERVATION_ONLY: ChannelPolicy(
        name=ChannelPolicyType.OBSERVATION_ONLY,
        allowed_features={FeatureGroup.AI_MENTION_REDIRECT, FeatureGroup.CONTEXTUAL_REACTIONS},
        allow_ai_chat=False,
        allow_mentions=True, # Triggers polite redirect only
        prohibit_unsolicited=True,
        allow_reactions=True,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        preferred_redirect_channel="kazumi-chat",
        description="Community main chat. Kazumi passively observes, gives sparse reactions, and redirects direct pings to #kazumi-chat."
    ),

    # G. #introductions — INTRODUCTIONS_ONLY
    ChannelPolicyType.INTRODUCTIONS_ONLY: ChannelPolicy(
        name=ChannelPolicyType.INTRODUCTIONS_ONLY,
        allowed_features={FeatureGroup.CONTEXTUAL_REACTIONS, FeatureGroup.AI_MENTION_REDIRECT},
        allow_ai_chat=False,
        allow_mentions=True,
        prohibit_unsolicited=True,
        allow_reactions=True,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        preferred_redirect_channel="kazumi-chat",
        description="Member introductions only. Contextual reactions permitted; no welcome poems or unsolicited AI chat."
    ),

    # H. #media — MEDIA_OBSERVATION
    ChannelPolicyType.MEDIA_OBSERVATION: ChannelPolicy(
        name=ChannelPolicyType.MEDIA_OBSERVATION,
        allowed_features={FeatureGroup.CONTEXTUAL_REACTIONS},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=True,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        description="Media and art sharing. Normal media sharing and reactions permitted. No automatic OCR spam."
    ),

    # I. #memes — HUMOR_OBSERVATION
    ChannelPolicyType.HUMOR_OBSERVATION: ChannelPolicy(
        name=ChannelPolicyType.HUMOR_OBSERVATION,
        allowed_features={FeatureGroup.CONTEXTUAL_REACTIONS},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=True,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        description="Meme and humor channel. Sparse reactions allowed; unsolicited AI paragraphs and game starts prohibited."
    ),

    # J. #questions — FORUM_QA
    ChannelPolicyType.FORUM_QA: ChannelPolicy(
        name=ChannelPolicyType.FORUM_QA,
        allowed_features={FeatureGroup.SERVER_INFO},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        description="Organized Q&A forum. Dedicated help commands only when explicitly requested; no thread spam."
    ),

    # K. #suggestions — FORUM_SUGGESTIONS
    ChannelPolicyType.FORUM_SUGGESTIONS: ChannelPolicy(
        name=ChannelPolicyType.FORUM_SUGGESTIONS,
        allowed_features={FeatureGroup.CONTEXTUAL_REACTIONS, FeatureGroup.SERVER_INFO},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=True,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        description="Community feedback and suggestions. Voting reactions permitted; no AI arguing or games."
    ),

    # L. #kazumi-chat — ACTIVE_CHAT (Primary Home)
    ChannelPolicyType.ACTIVE_CHAT: ChannelPolicy(
        name=ChannelPolicyType.ACTIVE_CHAT,
        allowed_features={
            FeatureGroup.AI_CHAT,
            FeatureGroup.CONTEXTUAL_REACTIONS,
            FeatureGroup.SERVER_INFO
        },
        allow_ai_chat=True,
        allow_mentions=True,
        prohibit_unsolicited=False,
        allow_reactions=True,
        allow_games=False, # Direct games to #games
        allow_moderation=False,
        allow_automated_messages=False,
        description="Kazumi's primary AI companion sanctuary. Natural conversation, emotions, affection, and memory."
    ),

    # M. #bot-commands — COMMANDS_ONLY
    ChannelPolicyType.COMMANDS_ONLY: ChannelPolicy(
        name=ChannelPolicyType.COMMANDS_ONLY,
        allowed_features={
            FeatureGroup.SERVER_INFO,
            FeatureGroup.GAMES,
            FeatureGroup.MUSIC,
            FeatureGroup.ROLE_SELECTION
        },
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=True,
        allow_moderation=False,
        allow_automated_messages=False,
        description="Slash command utility hub. Explicit commands only; ordinary conversational replies disabled."
    ),

    # N. #games — GAMEPLAY_ONLY
    ChannelPolicyType.GAMEPLAY_ONLY: ChannelPolicy(
        name=ChannelPolicyType.GAMEPLAY_ONLY,
        allowed_features={FeatureGroup.GAMES, FeatureGroup.SERVER_INFO},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=True,
        allow_games=True,
        allow_moderation=False,
        allow_automated_messages=False,
        description="Arcade, trivia, connect4, tictactoe, XP, and leaderboards. AI conversation disabled."
    ),

    # O. #giveaways — GIVEAWAYS_ONLY
    ChannelPolicyType.GIVEAWAYS_ONLY: ChannelPolicy(
        name=ChannelPolicyType.GIVEAWAYS_ONLY,
        allowed_features={FeatureGroup.GIVEAWAYS, FeatureGroup.SERVER_INFO},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=True,
        description="Giveaway cards, entries, winner draws, and rerolls only."
    ),

    # P. #events — EVENTS_ONLY (Alias / Shared with Scheduled Events)
    # Uses EVENTS_ONLY definition.

    # Q. #music-commands — MUSIC_CONTROL_ONLY
    ChannelPolicyType.MUSIC_CONTROL_ONLY: ChannelPolicy(
        name=ChannelPolicyType.MUSIC_CONTROL_ONLY,
        allowed_features={FeatureGroup.MUSIC, FeatureGroup.SERVER_INFO},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        description="Voice music queue, play, skip, and volume commands only."
    ),

    # R. Voice channels — VOICE_FEATURES_ONLY
    ChannelPolicyType.VOICE_FEATURES_ONLY: ChannelPolicy(
        name=ChannelPolicyType.VOICE_FEATURES_ONLY,
        allowed_features={FeatureGroup.MUSIC},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        description="Voice channels for music audio and authorized voice connections."
    ),

    # S. Community Stage — STAGE_EVENT_ONLY
    ChannelPolicyType.STAGE_EVENT_ONLY: ChannelPolicy(
        name=ChannelPolicyType.STAGE_EVENT_ONLY,
        allowed_features={FeatureGroup.STAGE_EVENTS},
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        description="Community Stage event coordination. Host commands only."
    ),

    # T. Private Staff Channels — STAFF_ONLY
    ChannelPolicyType.STAFF_ONLY: ChannelPolicy(
        name=ChannelPolicyType.STAFF_ONLY,
        allowed_features={
            FeatureGroup.STAFF_COMMANDS,
            FeatureGroup.MODERATION,
            FeatureGroup.SERVER_INFO,
            FeatureGroup.ANNOUNCEMENTS
        },
        allow_ai_chat=False,
        allow_mentions=False,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=False,
        allow_moderation=True,
        allow_automated_messages=True,
        is_staff_only=True,
        description="Private moderation, audit logs, kazumi-logs, and testing. Strict staff access only."
    ),

    # Direct Messages — DM_POLICY
    ChannelPolicyType.DM_POLICY: ChannelPolicy(
        name=ChannelPolicyType.DM_POLICY,
        allowed_features={
            FeatureGroup.AI_CHAT,
            FeatureGroup.CONTEXTUAL_REACTIONS,
            FeatureGroup.SERVER_INFO,
            FeatureGroup.GAMES
        },
        allow_ai_chat=True,
        allow_mentions=True,
        prohibit_unsolicited=False,
        allow_reactions=True,
        allow_games=True,
        allow_moderation=False,
        allow_automated_messages=False,
        is_staff_only=False,
        description="Direct 1-on-1 private companion chat with Kazumi. Never inherits staff privileges."
    ),

    # Fallback Default Public Channel
    ChannelPolicyType.DEFAULT_PUBLIC: ChannelPolicy(
        name=ChannelPolicyType.DEFAULT_PUBLIC,
        allowed_features={FeatureGroup.SERVER_INFO, FeatureGroup.AI_MENTION_REDIRECT},
        allow_ai_chat=False,
        allow_mentions=True,
        prohibit_unsolicited=True,
        allow_reactions=False,
        allow_games=False,
        allow_moderation=False,
        allow_automated_messages=False,
        preferred_redirect_channel="kazumi-chat",
        description="Default safe public policy for unmapped channels."
    )
}


# ==============================================================================
# CHANNEL POLICY MANAGER & RESOLUTION ENGINE
# ==============================================================================
class ChannelPolicyManager:
    """
    Resolves, enforces, and manages channel policies across Discord servers.
    Handles ID mappings, category inheritance, and fallback canonical naming.
    """

    # Default canonical channel names to Policy Type mapping
    NAME_HEURISTIC_MAP = {
        "welcome": ChannelPolicyType.EVENTS_ONLY,
        "rules": ChannelPolicyType.READ_ONLY,
        "announcements": ChannelPolicyType.ANNOUNCEMENTS_ONLY,
        "announcement": ChannelPolicyType.ANNOUNCEMENTS_ONLY,
        "server-guide": ChannelPolicyType.GUIDE_ONLY,
        "guide": ChannelPolicyType.GUIDE_ONLY,
        "roles": ChannelPolicyType.ROLE_SELECTION_ONLY,
        "role-selection": ChannelPolicyType.ROLE_SELECTION_ONLY,
        "general": ChannelPolicyType.OBSERVATION_ONLY,
        "introductions": ChannelPolicyType.INTRODUCTIONS_ONLY,
        "introduction": ChannelPolicyType.INTRODUCTIONS_ONLY,
        "media": ChannelPolicyType.MEDIA_OBSERVATION,
        "memes": ChannelPolicyType.HUMOR_OBSERVATION,
        "meme": ChannelPolicyType.HUMOR_OBSERVATION,
        "questions": ChannelPolicyType.FORUM_QA,
        "suggestions": ChannelPolicyType.FORUM_SUGGESTIONS,
        "kazumi-chat": ChannelPolicyType.ACTIVE_CHAT,
        "kazumi": ChannelPolicyType.ACTIVE_CHAT,
        "bot-commands": ChannelPolicyType.COMMANDS_ONLY,
        "commands": ChannelPolicyType.COMMANDS_ONLY,
        "games": ChannelPolicyType.GAMEPLAY_ONLY,
        "game": ChannelPolicyType.GAMEPLAY_ONLY,
        "arcade": ChannelPolicyType.GAMEPLAY_ONLY,
        "giveaways": ChannelPolicyType.GIVEAWAYS_ONLY,
        "giveaway": ChannelPolicyType.GIVEAWAYS_ONLY,
        "events": ChannelPolicyType.EVENTS_ONLY,
        "music-commands": ChannelPolicyType.MUSIC_CONTROL_ONLY,
        "music": ChannelPolicyType.MUSIC_CONTROL_ONLY,
        "community-stage": ChannelPolicyType.STAGE_EVENT_ONLY,
        "stage": ChannelPolicyType.STAGE_EVENT_ONLY,
        "staff-chat": ChannelPolicyType.STAFF_ONLY,
        "mod-logs": ChannelPolicyType.STAFF_ONLY,
        "moderator-only": ChannelPolicyType.STAFF_ONLY,
        "member-reports": ChannelPolicyType.STAFF_ONLY,
        "staff-announcements": ChannelPolicyType.STAFF_ONLY,
        "kazumi-logs": ChannelPolicyType.STAFF_ONLY,
        "bot-testing": ChannelPolicyType.STAFF_ONLY,
    }

    def __init__(self, db: Optional[Any] = None):
        self.db = db
        # Cache for #general redirect cooldown to prevent reply loops: (guild_id, channel_id, user_id) -> last_time
        self._redirect_cooldowns: Dict[Tuple[int, int, int], float] = {}

    def _clean_channel_name(self, name: str) -> str:
        """Strips emojis and trailing symbols from channel names for heuristic lookup."""
        if not name:
            return ""
        # Remove common unicode emojis and non-alphanumeric trailing symbols
        clean = re.sub(r"[^\w\-]", "", name.lower()).strip("-")
        return clean

    def get_policy_for_channel(
        self,
        channel: Union[discord.abc.GuildChannel, discord.Thread, discord.DMChannel],
        guild_id: Optional[int] = None
    ) -> ChannelPolicy:
        """
        Resolves the authoritative ChannelPolicy for any Discord channel or DM.
        Hierarchy:
        1. DMChannel -> DM_POLICY
        2. Channel ID Explicit Override in DB
        3. Category ID Explicit Override in DB
        4. Canonical Name Matching
        5. Channel Type Defaults (Stage -> STAGE_EVENT_ONLY, Voice -> VOICE_FEATURES_ONLY)
        6. DEFAULT_PUBLIC safe fallback
        """
        # 1. DMs
        if isinstance(channel, discord.DMChannel):
            return POLICY_DEFINITIONS[ChannelPolicyType.DM_POLICY]

        gid = str(guild_id or (channel.guild.id if hasattr(channel, "guild") and channel.guild else 0))
        cid_str = str(getattr(channel, "id", 0))

        # 2. Check Database Overrides for this Guild
        if self.db and gid != "0":
            g_settings = self.db.get_guild_settings(gid)
            policy_overrides = g_settings.get("channel_policies", {})
            if cid_str in policy_overrides:
                p_name = policy_overrides[cid_str]
                try:
                    p_type = ChannelPolicyType(p_name)
                    return POLICY_DEFINITIONS[p_type]
                except ValueError:
                    pass

            # 3. Check Category Level Overrides
            cat_id = str(getattr(channel, "category_id", 0) or 0)
            cat_overrides = g_settings.get("category_policies", {})
            if cat_id in cat_overrides:
                p_name = cat_overrides[cat_id]
                try:
                    p_type = ChannelPolicyType(p_name)
                    return POLICY_DEFINITIONS[p_type]
                except ValueError:
                    pass

        # 4. Canonical Name Matching
        raw_name = getattr(channel, "name", "")
        cleaned_name = self._clean_channel_name(raw_name)

        if cleaned_name in self.NAME_HEURISTIC_MAP:
            return POLICY_DEFINITIONS[self.NAME_HEURISTIC_MAP[cleaned_name]]

        # Substring heuristics for common names (e.g. general-chat -> general)
        for key, p_type in self.NAME_HEURISTIC_MAP.items():
            if key in cleaned_name:
                return POLICY_DEFINITIONS[p_type]

        # 5. Channel Type Fallbacks
        if isinstance(channel, discord.StageChannel):
            return POLICY_DEFINITIONS[ChannelPolicyType.STAGE_EVENT_ONLY]
        if isinstance(channel, discord.VoiceChannel):
            return POLICY_DEFINITIONS[ChannelPolicyType.VOICE_FEATURES_ONLY]
        if isinstance(channel, discord.ForumChannel):
            if "suggest" in cleaned_name:
                return POLICY_DEFINITIONS[ChannelPolicyType.FORUM_SUGGESTIONS]
            return POLICY_DEFINITIONS[ChannelPolicyType.FORUM_QA]

        # 6. Default Safe Fallback
        return POLICY_DEFINITIONS[ChannelPolicyType.DEFAULT_PUBLIC]

    def can_execute(
        self,
        channel: Union[discord.abc.GuildChannel, discord.Thread, discord.DMChannel],
        feature: FeatureGroup,
        user: Union[discord.Member, discord.User],
        message: Optional[discord.Message] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Gatekeeper check validating whether a feature is permitted to execute in this channel context.
        Returns (is_allowed, denial_reason).
        """
        policy = self.get_policy_for_channel(channel)

        # Check Staff-Only Isolation
        if policy.is_staff_only:
            # DMs cannot inherit staff permissions
            if isinstance(channel, discord.DMChannel):
                return False, "❌ Staff operations cannot be performed in Direct Messages."

            # Must have administrator or manage_guild or manage_messages in the guild
            is_staff = False
            if hasattr(user, "guild_permissions"):
                perms = user.guild_permissions
                is_staff = perms.administrator or perms.manage_guild or perms.manage_messages

            if not is_staff:
                return False, "❌ This channel is restricted to server staff members."

        # Check Feature Group membership
        if not policy.is_feature_allowed(feature):
            target_ch_name = policy.preferred_redirect_channel or "the designated channel"
            reason = (
                f"❌ Feature **{feature.name}** is not allowed in #{getattr(channel, 'name', 'this channel')} "
                f"(Policy: `{policy.name.value}`). Please use `#{target_ch_name}`."
            )
            return False, reason

        return True, None

    def get_mention_redirect_message(self, guild: Optional[discord.Guild]) -> str:
        """
        Generates the exact polite redirect message required for #general:
        “Hey! 🌸 Let's keep this channel flowing. For a proper chat with me, come find me in #kazumi-chat! ✨”
        With safe fallback if #kazumi-chat is not found.
        """
        target_channel_mention = None
        if guild and hasattr(guild, "text_channels"):
            for ch in guild.text_channels:
                if "kazumi-chat" in ch.name.lower() or "kazumi" in ch.name.lower():
                    target_channel_mention = f"<#{ch.id}>"
                    break

        if target_channel_mention:
            return f"Hey! 🌸 Let's keep this channel flowing. For a proper chat with me, come find me in {target_channel_mention}! ✨"
        else:
            return "Hey! 🌸 Let's keep this channel flowing. For a proper chat with me, come find me in #kazumi-chat! ✨"

    def should_redirect_mention(
        self,
        guild_id: int,
        channel_id: int,
        user_id: int,
        cooldown_seconds: float = 30.0
    ) -> bool:
        """Rate limits the polite redirect in #general to at most once per user per window."""
        import time
        now = time.time()
        key = (guild_id, channel_id, user_id)
        last_sent = self._redirect_cooldowns.get(key, 0.0)

        # Cleanup old entries if cache grows
        if len(self._redirect_cooldowns) > 1000:
            self._redirect_cooldowns = {k: v for k, v in self._redirect_cooldowns.items() if now - v <= 120.0}

        if now - last_sent >= cooldown_seconds:
            self._redirect_cooldowns[key] = now
            return True
        return False


# Singleton Policy Manager instance
_policy_manager: Optional[ChannelPolicyManager] = None

def get_channel_policy_manager(db: Optional[Any] = None) -> ChannelPolicyManager:
    global _policy_manager
    if _policy_manager is None:
        _policy_manager = ChannelPolicyManager(db=db)
    elif db and not _policy_manager.db:
        _policy_manager.db = db
    return _policy_manager


def register_channel_policy_commands(tree: app_commands.CommandTree, bot: commands.Bot, db: Any):
    """Registers slash commands for viewing and configuring channel policies."""
    policy_group = app_commands.Group(
        name="channel_policy",
        description="View and configure channel policy modes and boundaries 🛡️"
    )

    @policy_group.command(name="status", description="Inspect active policy and allowed features for a channel 📋")
    @app_commands.describe(channel="Target channel to inspect (defaults to current channel)")
    async def slash_policy_status(
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        target = channel or interaction.channel
        mgr = get_channel_policy_manager(db)
        policy = mgr.get_policy_for_channel(target, interaction.guild_id)

        features_str = ", ".join(f"`{f.name}`" for f in sorted(policy.allowed_features, key=lambda x: x.name)) or "*None*"

        embed = discord.Embed(
            title=f"🛡️ Channel Policy: #{getattr(target, 'name', 'Channel')}",
            description=policy.description,
            color=0x8b5cf6
        )
        embed.add_field(name="Policy Mode", value=f"`{policy.name.value}`", inline=True)
        embed.add_field(name="AI Chat Permitted", value="✅ Yes" if policy.allow_ai_chat else "❌ No", inline=True)
        embed.add_field(name="Games Permitted", value="✅ Yes" if policy.allow_games else "❌ No", inline=True)
        embed.add_field(name="Reactions Allowed", value="✅ Yes" if policy.allow_reactions else "❌ No", inline=True)
        embed.add_field(name="Staff Only", value="🔒 Yes" if policy.is_staff_only else "🌐 Public", inline=True)
        embed.add_field(name="Allowed Feature Groups", value=features_str, inline=False)
        embed.set_footer(text="Kazumi Channel Policy Enforcement")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @policy_group.command(name="set", description="Assign an explicit policy override to a channel (Staff only) ⚙️")
    @app_commands.describe(
        channel="Target channel to configure",
        policy="Policy mode to enforce"
    )
    @app_commands.choices(policy=[
        app_commands.Choice(name=p.value, value=p.value)
        for p in ChannelPolicyType
    ])
    async def slash_policy_set(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        policy: app_commands.Choice[str]
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You require **Manage Server** permission.", ephemeral=True)
            return

        gid = str(interaction.guild_id)
        cid = str(channel.id)

        g_settings = db.get_guild_settings(gid)
        channel_policies = g_settings.get("channel_policies", {})
        channel_policies[cid] = policy.value
        g_settings["channel_policies"] = channel_policies
        db.set_guild_settings(gid, g_settings)

        await interaction.response.send_message(
            f"✅ Channel {channel.mention} policy updated to **`{policy.value}`**!",
            ephemeral=True
        )

    @policy_group.command(name="list", description="List all known channel policies for this server 📜")
    async def slash_policy_list(interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
            return

        mgr = get_channel_policy_manager(db)
        lines = []
        for ch in interaction.guild.text_channels:
            p = mgr.get_policy_for_channel(ch, interaction.guild.id)
            lines.append(f"• {ch.mention} (`#{ch.name}`) -> `{p.name.value}`")

        embed = discord.Embed(
            title=f"📜 Channel Policies • {interaction.guild.name}",
            description="\n".join(lines[:30]) or "No text channels found.",
            color=0x8b5cf6
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    tree.add_command(policy_group)

