"""
🌸 Kazumi Person Memory — Behaviour Tracker
Manages gradual learning, exponential moving averages (EMA),
confidence calculations, time decay, and behavioral pattern synthesis.
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from person_memory.person_profile import PersonProfile, CommunicationStyle

CONFIDENCE_THRESHOLD = 0.70
DECAY_RATE_PER_DAY = 0.03  # Gradual decay of confidence when inactive


class BehaviourTracker:
    """
    Updates a PersonProfile with new observations over time.
    Guarantees gradual learning, avoids snap judgments, and applies time decay.
    """

    def apply_decay(self, profile: PersonProfile) -> None:
        """Applies time-based decay so old behavior doesn't permanently define someone."""
        now = time.time()
        elapsed_seconds = max(0.0, now - profile.last_decay_time)
        elapsed_days = elapsed_seconds / 86400.0

        if elapsed_days >= 1.0:
            decay_factor = max(0.0, elapsed_days * DECAY_RATE_PER_DAY)
            profile.confidence = max(0.15, profile.confidence - decay_factor)
            profile.last_decay_time = now

    def update_profile(self, profile: PersonProfile, observation: Dict[str, Any], display_name: Optional[str] = None) -> PersonProfile:
        """
        Updates the profile with a new message observation.
        """
        self.apply_decay(profile)

        # 1. Update display name if changed (preserving stable platform ID)
        if display_name and display_name.strip() and display_name != profile.display_name:
            profile.display_name = display_name.strip()

        # 2. Update interaction counts and timestamps
        profile.interaction_count += 1
        now_iso = datetime.now(timezone.utc).isoformat()
        if not profile.first_seen:
            profile.first_seen = now_iso
        profile.last_seen = now_iso

        obs_style = observation.get("style", {})
        curr_style = profile.communication_style

        # 3. Adaptive learning rate (alpha)
        # Early on (interactions <= 5), updates are slightly faster (0.25).
        # Later, updates stabilize (0.10) for high stability.
        if profile.interaction_count <= 5:
            alpha = 0.25
        elif profile.interaction_count <= 20:
            alpha = 0.15
        else:
            alpha = 0.08

        # 4. Smooth EMA update for communication dimensions
        curr_style.formality = (1 - alpha) * curr_style.formality + alpha * float(obs_style.get("formality", 0.5))
        curr_style.humor = (1 - alpha) * curr_style.humor + alpha * float(obs_style.get("humor", 0.0))
        curr_style.sarcasm = (1 - alpha) * curr_style.sarcasm + alpha * float(obs_style.get("sarcasm", 0.0))
        curr_style.verbosity = (1 - alpha) * curr_style.verbosity + alpha * float(obs_style.get("verbosity", 0.3))
        curr_style.emoji_usage = (1 - alpha) * curr_style.emoji_usage + alpha * float(obs_style.get("emoji_usage", 0.0))
        curr_style.energy = (1 - alpha) * curr_style.energy + alpha * float(obs_style.get("energy", 0.2))

        # 5. Gradual confidence growth
        # Starts at ~0.20 on interaction 1.
        # Climbs to ~0.62 after repeated interactions (8-12), and ~0.85+ after 18+ interactions.
        target_confidence = min(0.95, 0.18 + (profile.interaction_count * 0.04))
        if profile.interaction_count == 1:
            profile.confidence = target_confidence
        else:
            profile.confidence = (0.80 * profile.confidence) + (0.20 * target_confidence)

        # 6. Update interests (non-sensitive whitelist only)
        new_interests = observation.get("interests", [])
        for interest in new_interests:
            if interest not in profile.interests and len(profile.interests) < 8:
                profile.interests.append(interest)

        # 7. Update conversation preferences
        new_behaviors = observation.get("behaviors", [])
        for b in new_behaviors:
            if b not in profile.conversation_preferences and len(profile.conversation_preferences) < 6:
                profile.conversation_preferences.append(b)

        # 8. Synthesize observable behavioral patterns (only when confidence is reasonable >= 0.40)
        self._synthesize_patterns(profile)

        # 9. Record observation snapshot in ring buffer (max 10)
        snapshot = {
            "timestamp": now_iso,
            "word_count": observation.get("word_count", 0),
            "emotional_intent": observation.get("emotional_intent"),
            "formality": round(float(obs_style.get("formality", 0.5)), 2),
            "humor": round(float(obs_style.get("humor", 0.0)), 2),
            "emoji_usage": round(float(obs_style.get("emoji_usage", 0.0)), 2)
        }
        profile.last_observations.append(snapshot)
        if len(profile.last_observations) > 10:
            profile.last_observations = profile.last_observations[-10:]

        return profile

    def _synthesize_patterns(self, profile: PersonProfile) -> None:
        """
        Translates numerical metrics into human-readable behavioral patterns.
        Only generates strong patterns when confidence is sufficient.
        """
        patterns = []
        style = profile.communication_style

        # Formality vs Casual
        if profile.confidence >= 0.35:
            if style.formality >= 0.65:
                patterns.append("Speaks formally and articulately")
            elif style.formality <= 0.42:
                patterns.append("Communicates casually with informal language")

        # Humor & Sarcasm
        if profile.confidence >= 0.40:
            if style.humor >= 0.45 and style.sarcasm >= 0.35:
                patterns.append("Enjoys witty banter, sarcasm, and memes")
            elif style.humor >= 0.45:
                patterns.append("Frequently jokes and appreciates humor")
            elif style.humor <= 0.20 and style.formality >= 0.55:
                patterns.append("Prefers serious, grounded conversations")

        # Verbosity
        if profile.confidence >= 0.35:
            if style.verbosity <= 0.25:
                patterns.append("Prefers brief, concise messages")
            elif style.verbosity >= 0.70:
                patterns.append("Gives detailed, elaborate messages")

        # Emojis & Energy
        if profile.confidence >= 0.40:
            if style.emoji_usage >= 0.30:
                patterns.append("Uses emojis frequently")
            elif style.emoji_usage <= 0.10:
                patterns.append("Rarely uses emojis")

            if style.energy >= 0.60:
                patterns.append("Expresses high energy and enthusiasm")
            elif style.energy <= 0.25:
                patterns.append("Maintains a calm, relaxed demeanor")

        profile.behaviour_patterns = patterns
