"""
🌸 Kazumi Person Memory — Reaction Engine
Generates context-aware, subtle emoji reactions for observation channels.
Adheres strictly to cooldowns, probability thresholds (0.10-0.30),
and never spams reactions.
"""

import time
import random
from typing import Dict, List, Optional, Tuple, Any

REACTION_COOLDOWN_SECONDS = 60.0
BASE_REACTION_PROBABILITY = 0.15
EMOTIONAL_PROBABILITY_BOOST = 0.20

# Reaction emoji pools categorized by context
REACTION_POOLS = {
    "achievement": ["🎉", "❤️", "✨", "👏", "🏆"],
    "funny": ["😂", "💀", "🤣", "😭"],
    "sad": ["❤️", "🥺", "🫂", "😢"],
    "surprise": ["😳", "😮", "👀", "😲"],
    "agreement": ["👍", "💖", "✨", "🙌", "💯"]
}

DEFAULT_WARM_REACTIONS = ["🌸", "✨", "❤️", "👍"]


class ReactionEngine:
    """
    Evaluates whether Kazumi should add an emoji reaction to a message.
    Never sends text replies.
    """

    def __init__(self, cooldown_seconds: float = REACTION_COOLDOWN_SECONDS):
        self.cooldown_seconds = cooldown_seconds
        # (channel_id, user_id) -> last_reaction_timestamp
        self._last_user_reaction: Dict[Tuple[str, str], float] = {}
        # channel_id -> last_channel_reaction_timestamp
        self._last_channel_reaction: Dict[str, float] = {}

    def should_react(
        self,
        channel_id: str,
        user_id: str,
        observation: Dict[str, Any],
        is_direct_address: bool = False
    ) -> Optional[str]:
        """
        Determines if Kazumi should react with an emoji, and returns the emoji or None.
        Enforces cooldown and probability.
        """
        now = time.time()
        chan_key = str(channel_id)
        user_key = (chan_key, str(user_id))

        # Check channel cooldown (minimum 25s between any reaction in this channel)
        if chan_key in self._last_channel_reaction:
            if now - self._last_channel_reaction[chan_key] < 25.0:
                return None

        # Check user cooldown (minimum 60s per user)
        if user_key in self._last_user_reaction:
            if now - self._last_user_reaction[user_key] < self.cooldown_seconds:
                return None

        intent = observation.get("emotional_intent")
        intensity = observation.get("emotional_intensity", 0.0)
        style = observation.get("style", {})
        humor = style.get("humor", 0.0)

        # Calculate dynamic reaction probability
        prob = BASE_REACTION_PROBABILITY

        if intent:
            prob += EMOTIONAL_PROBABILITY_BOOST
            if intensity >= 0.8:
                prob += 0.15

        if is_direct_address:
            # If directly mentioned or addressed in secondary chat, higher chance to react
            prob += 0.35

        # Cap probability between 0.10 and 0.65
        prob = max(0.10, min(0.65, prob))

        # Roll the dice
        if random.random() > prob:
            return None

        # Select appropriate emoji
        chosen_emoji = None
        if intent and intent in REACTION_POOLS:
            chosen_emoji = random.choice(REACTION_POOLS[intent])
        elif humor >= 0.5:
            chosen_emoji = random.choice(REACTION_POOLS["funny"])
        elif is_direct_address:
            chosen_emoji = random.choice(DEFAULT_WARM_REACTIONS)
        else:
            chosen_emoji = random.choice(DEFAULT_WARM_REACTIONS)

        # Update cooldown timestamps
        self._last_channel_reaction[chan_key] = now
        self._last_user_reaction[user_key] = now

        return chosen_emoji
