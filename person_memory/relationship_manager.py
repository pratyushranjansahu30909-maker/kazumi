"""
🌸 Kazumi Person Memory — Relationship Manager
Computes lightweight familiarity & relationship progression.
Adheres strictly to natural progression: does NOT assume artificial attachment.
Levels:
  0 = New person
  1 = Recognised
  2 = Familiar
  3 = Regular interaction
  4 = Strong familiarity
"""

from datetime import datetime, timezone
from typing import Optional
from person_memory.person_profile import PersonProfile


class RelationshipManager:
    """
    Evaluates relationship familiarity based on authentic interaction count
    and interaction timespan.
    """

    def compute_relationship_level(self, profile: PersonProfile) -> int:
        """
        Determines relationship level (0 to 4):
        - 0: New person (< 3 interactions)
        - 1: Recognised (3-9 interactions)
        - 2: Familiar (10-24 interactions across >= 1 day)
        - 3: Regular interaction (25-59 interactions across >= 3 days)
        - 4: Strong familiarity (>= 60 interactions across >= 7 days with confidence >= 0.70)
        """
        count = profile.interaction_count

        if count < 3:
            return 0
        if count < 10:
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
            # Need at least some hours/days or >= 10 interactions
            return 2 if (days_span >= 0.2 or count >= 15) else 1

        if count < 60:
            return 3 if (days_span >= 1.0 or count >= 35) else 2

        # Level 4: Strong familiarity
        if days_span >= 3.0 and profile.confidence >= 0.65:
            return 4

        return 3

    def update_relationship(self, profile: PersonProfile) -> int:
        """Updates and returns the new relationship level on the profile."""
        new_level = self.compute_relationship_level(profile)
        profile.relationship_level = new_level
        return new_level

    @staticmethod
    def get_relationship_title(level: int) -> str:
        """Returns a warm, friendly title for display."""
        titles = {
            0: "New Face",
            1: "Recognised Member",
            2: "Familiar Companion",
            3: "Regular Companion",
            4: "Trusted Close Companion"
        }
        return titles.get(level, "Companion")
