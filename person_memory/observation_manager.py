"""
🌸 Kazumi Person Memory — Observation Manager
Central coordinator integrating:
- BehaviourAnalyzer (local, zero-LLM text heuristics)
- BehaviourTracker (gradual Bayesian/EMA updates & decay)
- RelationshipManager (0-4 progressive familiarity)
- PersonMemoryManager (atomic JSON persistence)
- ReactionEngine (context-aware emoji reactions)
"""

import time
import logging
from typing import Dict, List, Optional, Tuple, Any

from person_memory.person_profile import PersonProfile
from person_memory.behaviour_analyzer import BehaviourAnalyzer
from person_memory.behaviour_tracker import BehaviourTracker
from person_memory.relationship_manager import RelationshipManager
from person_memory.memory_manager import PersonMemoryManager
from person_memory.reaction_engine import ReactionEngine

logger = logging.getLogger("KazumiObservationManager")

BEHAVIOUR_CONFIDENCE_THRESHOLD = 0.70
MEMORY_UPDATE_COOLDOWN = 300  # Debounce period in seconds for bulk save


class ObservationManager:
    """
    Coordinates message observation, behavioral profile updates,
    channel modes, and reaction decisions.
    """

    def __init__(self, persist_dir: str = "isa_memory"):
        self.analyzer = BehaviourAnalyzer()
        self.tracker = BehaviourTracker()
        self.relationship_mgr = RelationshipManager()
        self.memory_mgr = PersonMemoryManager(persist_dir=persist_dir)
        self.reaction_engine = ReactionEngine()

        # Rolling channel message buffer for context awareness: channel_id -> list of recent message texts
        self._channel_recent_messages: Dict[str, List[str]] = {}
        self._last_save_time = time.time()
        self._pending_updates = 0

    def get_channel_mode(self, channel_id: str, is_dm: bool = False, is_dedicated: bool = False) -> str:
        """
        Determines the mode for a channel:
        - If configured in memory, returns configured mode.
        - DMs and dedicated Kazumi channels default to ACTIVE_CHAT.
        - Other server channels default to OBSERVATION_ONLY.
        """
        cid = str(channel_id)
        default_mode = "ACTIVE_CHAT" if (is_dm or is_dedicated) else "OBSERVATION_ONLY"
        return self.memory_mgr.get_channel_mode(cid, default=default_mode)

    def set_channel_mode(self, channel_id: str, mode: str) -> None:
        """Configures the channel mode."""
        self.memory_mgr.set_channel_mode(channel_id, mode)

    def reset_user(self, user_id: str) -> bool:
        """Resets user's behavioral profile (Privacy / Safety feature)."""
        return self.memory_mgr.reset_person(user_id)

    def get_profile(self, user_id: str, display_name: Optional[str] = None) -> PersonProfile:
        """Retrieves user's profile."""
        return self.memory_mgr.get_profile(user_id, display_name=display_name)

    def record_channel_message(self, channel_id: str, text: str) -> None:
        """Maintains a sliding window of recent messages in the channel for context."""
        cid = str(channel_id)
        if cid not in self._channel_recent_messages:
            self._channel_recent_messages[cid] = []
        clean = (text or "").strip()
        if clean:
            self._channel_recent_messages[cid].append(clean)
            if len(self._channel_recent_messages[cid]) > 5:
                self._channel_recent_messages[cid] = self._channel_recent_messages[cid][-5:]

    def process_message(
        self,
        user_id: str,
        display_name: str,
        channel_id: str,
        text: str,
        is_dm: bool = False,
        is_dedicated: bool = False,
        is_direct_address: bool = False
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Processes an incoming message through the observation pipeline.

        Returns:
            Tuple of:
            - channel_mode: "ACTIVE_CHAT", "OBSERVATION_ONLY", or "DISABLED"
            - reaction_emoji: Optional emoji string if reaction is decided for observation channel
            - adaptive_style_directive: Optional prompt string to adapt Kazumi's tone in active chat
        """
        cid = str(channel_id)
        uid = str(user_id)
        mode = self.get_channel_mode(cid, is_dm=is_dm, is_dedicated=is_dedicated)

        # If DISABLED, do nothing at all
        if mode == "DISABLED":
            return ("DISABLED", None, None)

        clean_text = (text or "").strip()
        if not clean_text:
            return (mode, None, None)

        # Context from recent messages in this channel
        recent_ctx = self._channel_recent_messages.get(cid, [])

        # 1. Analyze message with fast local heuristics
        observation = self.analyzer.analyze(clean_text, context=recent_ctx)

        # Update context buffer
        self.record_channel_message(cid, clean_text)

        # 2. Retrieve & update profile
        profile = self.memory_mgr.get_profile(uid, display_name=display_name)
        self.tracker.update_profile(profile, observation, display_name=display_name)
        self.relationship_mgr.update_relationship(profile)

        # 3. Handle debounced disk persistence
        self._pending_updates += 1
        now = time.time()
        if self._pending_updates >= 3 or (now - self._last_save_time >= 30.0):
            self.memory_mgr.save_all()
            self._last_save_time = now
            self._pending_updates = 0

        # 4. Mode-specific action
        reaction_emoji = None
        adaptive_directive = None

        if mode == "OBSERVATION_ONLY":
            # NEVER send text. Decide if reaction emoji is warranted.
            reaction_emoji = self.reaction_engine.should_react(
                channel_id=cid,
                user_id=uid,
                observation=observation,
                is_direct_address=is_direct_address
            )
        elif mode == "ACTIVE_CHAT":
            # Generate subtle tone adaptation directive if confidence is sufficient
            adaptive_directive = self.generate_adaptive_directive(profile)

        return (mode, reaction_emoji, adaptive_directive)

    def generate_adaptive_directive(self, profile: PersonProfile) -> Optional[str]:
        """
        Creates an invisible prompt adaptation guideline when confidence is high enough.
        Adheres strictly to Anti-Creepy Rules (Section 8 & 18):
        Never says 'I know your profile' or 'I have been monitoring you'.
        """
        # Only adapt when we have sufficient evidence
        if profile.confidence < BEHAVIOUR_CONFIDENCE_THRESHOLD or profile.interaction_count < 5:
            return None

        style = profile.communication_style
        guidelines = []

        # Formality & Tone
        if style.formality >= 0.65:
            guidelines.append("Respond in a thoughtful, articulate, and well-structured manner. Avoid excessive slang.")
        elif style.formality <= 0.35:
            guidelines.append("Respond casually and naturally with relaxed language. Do not sound stiff or overly formal.")

        # Humor & Banter
        if style.humor >= 0.55 and style.sarcasm >= 0.40:
            guidelines.append("Embrace witty banter, playful teasing, and humorous comebacks.")
        elif style.humor >= 0.55:
            guidelines.append("Incorporate lighthearted warmth and gentle humor into your reply.")
        elif style.humor <= 0.20 and style.formality >= 0.55:
            guidelines.append("Keep your tone calm, grounded, and sincere.")

        # Verbosity
        if style.verbosity <= 0.30:
            guidelines.append("Keep your response concise, brief, and punchy (1-2 sentences).")
        elif style.verbosity >= 0.70:
            guidelines.append("Feel free to provide a slightly more detailed and thorough response.")

        # Emojis & Energy
        if style.emoji_usage >= 0.60:
            guidelines.append("Use a warm emoji naturally to match their expressive vibe.")
        elif style.emoji_usage <= 0.20:
            guidelines.append("Use minimal or no emojis to match their understated style.")

        if not guidelines:
            return None

        directive = (
            "\n[SUBTLE COMMUNICATION STYLE ADAPTATION:\n"
            + "\n".join([f"- {g}" for g in guidelines])
            + "\n- CRITICAL ANTI-CREEPY RULE: Never mention that you monitor, track, or analyzed their personality. "
            "Simply adapt your communication tone naturally and invisibly.]\n"
        )
        return directive
