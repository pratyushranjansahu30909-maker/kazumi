"""
🌸 Kazumi Person Memory — Relationship Manager
Computes lightweight familiarity & relationship progression.
Adheres strictly to natural progression: does NOT assume artificial attachment.
Relationship states (P0 Standard):
  0 = UNKNOWN
  1 = NEW
  2 = FAMILIAR
  3 = REGULAR
  4 = TRUSTED
  5 = CLOSE
"""

from datetime import datetime, timezone
from typing import Optional
from person_memory.person_profile import PersonProfile


class RelationshipState:
    UNKNOWN = "UNKNOWN"
    NEW = "NEW"
    FAMILIAR = "FAMILIAR"
    REGULAR = "REGULAR"
    TRUSTED = "TRUSTED"
    CLOSE = "CLOSE"


class RelationshipManager:
    """
    Evaluates relationship familiarity based on authentic interaction count
    and interaction timespan.
    """

    def compute_relationship_level(self, profile: PersonProfile) -> int:
        """
        Determines relationship level (0 to 5):
        - 0: UNKNOWN (< 2 interactions)
        - 1: NEW (2-7 interactions)
        - 2: FAMILIAR (8-24 interactions across >= 1 day)
        - 3: REGULAR (25-59 interactions across >= 3 days)
        - 4: TRUSTED (60-119 interactions across >= 7 days with confidence >= 0.65)
        - 5: CLOSE (>= 120 interactions across >= 14 days with confidence >= 0.80)
        """
        count = profile.interaction_count

        if count < 2:
            return 0
        if count < 8:
            return 1

        # Calculate time span between first_seen and last_seen
        days_span = 0.0
        try:
            if profile.first_seen and profile.last_seen:
                t1 = datetime.fromisoformat(profile.first_seen)
                t2 = datetime.fromisoformat(profile.last_seen)
                days_span = max(0.0, (t2 - t1).total_seconds() / 86400.0)
        except Exception:
            days_span = 0.0

        if count < 25:
            return 2 if (days_span >= 0.2 or count >= 12) else 1

        if count < 60:
            return 3 if (days_span >= 1.0 or count >= 35) else 2

        if count < 120:
            return 4 if (days_span >= 3.0 and profile.confidence >= 0.60) else 3

        # Level 5: Close
        if days_span >= 7.0 and profile.confidence >= 0.75:
            return 5

        return 4

    def update_relationship(self, profile: PersonProfile) -> int:
        """Updates and returns the new relationship level on the profile."""
        new_level = self.compute_relationship_level(profile)
        profile.relationship_level = new_level
        return new_level

    @staticmethod
    def get_relationship_state_name(level: int) -> str:
        """Returns standard state name (UNKNOWN, NEW, FAMILIAR, REGULAR, TRUSTED, CLOSE)."""
        states = {
            0: RelationshipState.UNKNOWN,
            1: RelationshipState.NEW,
            2: RelationshipState.FAMILIAR,
            3: RelationshipState.REGULAR,
            4: RelationshipState.TRUSTED,
            5: RelationshipState.CLOSE
        }
        return states.get(level, RelationshipState.NEW)

    @staticmethod
    def get_relationship_title(level: int) -> str:
        """Returns a warm, friendly title for display."""
        titles = {
            0: "New Face",
            1: "Recognised Member",
            2: "Familiar Companion",
            3: "Regular Companion",
            4: "Trusted Companion",
            5: "Close Companion"
        }
        return titles.get(level, "Companion")
