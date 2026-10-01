# -*- coding: utf-8 -*-
"""
🌸 Kazumi Human Interaction Engine (P0 Standard)
Decides whether Kazumi should:
- RESPOND: Generate an AI conversational response
- REACT: Silently add a context-aware emoji reaction
- WAIT: Stand by without interrupting ongoing fast multi-user banter
- OBSERVE: Silently learn and update behavioral/social profile without speaking
- IGNORE: Completely disregard (bots, commands, disabled channels)
- INITIATE: Spontaneous conversation check-in / milestone prompt

Considers:
- Speaker & target
- Was Kazumi mentioned or addressed?
- Is this a channel announcement, bot command, or quiet study chat?
- Has Kazumi spoken recently? (interruption dampening)
- Conversation energy & slang suppression
- Relationship tier & server context
- Silence is a valid, natural companion response.
"""

import re
import time
from enum import Enum
from typing import Optional, Tuple, Dict, Any
import discord

from .database import FeatureDB
from .server_memory import SmartSilenceEngine, NaturalReactionPicker

class InteractionDecision(Enum):
    RESPOND = "RESPOND"
    REACT = "REACT"
    WAIT = "WAIT"
    OBSERVE = "OBSERVE"
    IGNORE = "IGNORE"
    INITIATE = "INITIATE"


class HumanInteractionEngine:
    """
    Central socially-aware decision layer for all conversational events in Kazumi.
    """

    def __init__(self, db: FeatureDB, bot_user_id: int):
        self.db = db
        self.bot_user_id = bot_user_id
        self.silence_engine = SmartSilenceEngine(bot_user_id)
        self.reaction_picker = NaturalReactionPicker()

        # Channel ID -> timestamp of last Kazumi message
        self._last_spoke_channel: Dict[int, float] = {}
        # Channel ID -> timestamp of last observed user message
        self._last_user_activity: Dict[int, float] = {}

    def record_bot_spoke(self, channel_id: int) -> None:
        self._last_spoke_channel[channel_id] = time.time()

    def evaluate(
        self,
        message: discord.Message,
        is_dm: bool,
        is_dedicated_channel: bool,
        is_mentioned: bool,
        is_reply_to_kazumi: bool,
        is_directly_addressed: bool,
        is_prefix_called: bool,
        channel_mode: str = "ACTIVE_CHAT",
        relationship_level: int = 1
    ) -> Tuple[InteractionDecision, Optional[str], str]:
        """
        Evaluates a Discord message through Kazumi's social awareness filters.
        Returns:
            (InteractionDecision, optional_emoji_or_directive, reason)
        """
        # 1. Ignore bots and self
        if message.author.bot or (self.bot_user_id and message.author.id == self.bot_user_id):
            return InteractionDecision.IGNORE, None, "Author is a bot or self"

        raw_text = (message.content or "").strip()
        now = time.time()
        ch_id = message.channel.id

        # Update activity tracking
        self._last_user_activity[ch_id] = now
        time_since_last_spoke = now - self._last_spoke_channel.get(ch_id, 0.0)

        # 2. Disabled Channel -> IGNORE
        if channel_mode == "DISABLED":
            return InteractionDecision.IGNORE, None, "Channel mode is DISABLED"

        # 3. Quarantined member -> IGNORE
        if message.guild and self.db.is_user_quarantined(message.guild.id, message.author.id):
            return InteractionDecision.IGNORE, None, "User is quarantined"

        # 4. Raid mode active -> IGNORE unless administrator
        if message.guild and self.db.is_raid_mode_active(message.guild.id):
            if not getattr(message.author.guild_permissions, "administrator", False):
                return InteractionDecision.IGNORE, None, "Emergency raid mode active"

        # 5. Non-Kazumi Bot Commands (e.g. !play, /ban, $price) -> IGNORE
        if raw_text and raw_text[0] in "!?.$-/" and not is_prefix_called:
            if len(raw_text) > 1 and (raw_text[1].isalpha() or raw_text[1] in "!?.$-/"):
                return InteractionDecision.IGNORE, None, "External bot command prefix detected"

        # 6. STOP / SILENCE command -> OBSERVE silently
        stop_phrases = {"stop", "shut up", "stfu", "quiet", "silence", "chup", "leave me alone"}
        norm_lower = re.sub(r"[^\w\s]", "", raw_text.lower()).strip()
        if any(sp == norm_lower or norm_lower.startswith(sp + " ") for sp in stop_phrases):
            return InteractionDecision.OBSERVE, None, "User requested silence"

        # 7. Check if user is talking to someone else (tagged another member, not Kazumi)
        if message.mentions and not is_mentioned:
            # Users are having a private back-and-forth
            return InteractionDecision.OBSERVE, None, "User is directly conversing with another member"

        # 8. OBSERVATION_ONLY Channels -> OBSERVE or REACT with emoji, never send chat text
        if channel_mode == "OBSERVATION_ONLY":
            if is_mentioned or is_reply_to_kazumi or is_directly_addressed:
                # Direct ping in observation channel: react or soft redirect
                return InteractionDecision.REACT, "🌸", "Direct ping in observation-only channel"

            # Contextual emoji reaction chance
            emoji = self.reaction_picker.pick_emoji(raw_text)
            if emoji and time_since_last_spoke >= 30.0:
                self.record_bot_spoke(ch_id)
                return InteractionDecision.REACT, emoji, "Natural observation reaction"

            return InteractionDecision.OBSERVE, None, "Silent learning in observation channel"

        # 9. Direct Address / Mention / Reply in DMs or Active Chat -> RESPOND
        is_explicitly_summoned = is_mentioned or is_reply_to_kazumi or is_directly_addressed or is_prefix_called or is_dm
        if is_explicitly_summoned:
            self.record_bot_spoke(ch_id)
            return InteractionDecision.RESPOND, None, "Explicitly summoned or addressed by user"

        # 10. Chat Slang / Pure Laughter (e.g. "lmao", "haha", "bruh", "gg") -> REACT or WAIT
        chat_slang = {"lol", "lmao", "lmfao", "haha", "hahaha", "xd", "rofl", "bruh", "damn", "gg", "w", "rip"}
        if norm_lower in chat_slang:
            emoji = self.reaction_picker.pick_emoji(raw_text)
            if emoji and time_since_last_spoke >= 45.0:
                self.record_bot_spoke(ch_id)
                return InteractionDecision.REACT, emoji, "Laugh/slang reaction without cluttering text"
            return InteractionDecision.WAIT, None, "Chat slang noise suppressed"

        # 11. In dedicated #kazumi channel, evaluate if it's a general question directed into the void
        if is_dedicated_channel and raw_text.endswith("?"):
            if time_since_last_spoke >= 25.0:
                self.record_bot_spoke(ch_id)
                return InteractionDecision.RESPOND, None, "Question asked in dedicated companion channel"

        # 12. General unprompted server messages -> WAIT or OBSERVE (Silence is legitimate)
        return InteractionDecision.OBSERVE, None, "General server chatter; yielding to preserve natural silence"
