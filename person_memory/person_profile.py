"""
🌸 Kazumi Person Memory — Person Profile Schema
Defines the persistent behavioral profile structure for individual users.
"""

import time
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

@dataclass
class CommunicationStyle:
    formality: float = 0.0      # 0.0 (very casual/slang) to 1.0 (formal, proper grammar/punctuation)
    humor: float = 0.0          # 0.0 (serious) to 1.0 (jokes, memes, laughs)
    sarcasm: float = 0.0        # 0.0 (direct/earnest) to 1.0 (ironic/teasing)
    verbosity: float = 0.0      # 0.0 (short/terse) to 1.0 (long/elaborate)
    emoji_usage: float = 0.0    # 0.0 (none) to 1.0 (emoji-heavy)
    energy: float = 0.0         # 0.0 (calm/chill) to 1.0 (hyped/all-caps/exclamations)

    def to_dict(self) -> Dict[str, float]:
        return {
            "formality": round(self.formality, 3),
            "humor": round(self.humor, 3),
            "sarcasm": round(self.sarcasm, 3),
            "verbosity": round(self.verbosity, 3),
            "emoji_usage": round(self.emoji_usage, 3),
            "energy": round(self.energy, 3)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommunicationStyle":
        if not data:
            return cls()
        return cls(
            formality=float(data.get("formality", 0.0)),
            humor=float(data.get("humor", 0.0)),
            sarcasm=float(data.get("sarcasm", 0.0)),
            verbosity=float(data.get("verbosity", 0.0)),
            emoji_usage=float(data.get("emoji_usage", 0.0)),
            energy=float(data.get("energy", 0.0))
        )


@dataclass
class PersonProfile:
    user_id: str
    display_name: str

    interaction_count: int = 0
    first_seen: str = ""
    last_seen: str = ""

    communication_style: CommunicationStyle = field(default_factory=CommunicationStyle)

    behaviour_patterns: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    conversation_preferences: List[str] = field(default_factory=list)

    relationship_level: int = 0  # 0=New person, 1=Recognised, 2=Familiar, 3=Regular interaction, 4=Strong familiarity

    # Persistent Individual Affection & Progression (Phase 4)
    affection_level: int = 10
    cozy_points: int = 100
    lifetime_affection: int = 10
    turn_count: int = 0
    archetype: Optional[str] = None
    last_affection_gain_time: float = 0.0
    daily_affection_earned: int = 0
    daily_affection_date: str = ""

    known_preferences: List[str] = field(default_factory=list)
    positive_patterns: List[str] = field(default_factory=list)
    negative_patterns: List[str] = field(default_factory=list)

    confidence: float = 0.0
    last_observations: List[Dict[str, Any]] = field(default_factory=list)

    # Internal tracking for decay and updates
    last_decay_time: float = field(default_factory=time.time)

    def __post_init__(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        if not self.first_seen:
            self.first_seen = now_iso
        if not self.last_seen:
            self.last_seen = now_iso
        if self.lifetime_affection < self.affection_level:
            self.lifetime_affection = self.affection_level

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": str(self.user_id),
            "display_name": self.display_name,
            "interaction_count": self.interaction_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "communication_style": self.communication_style.to_dict(),
            "behaviour_patterns": list(self.behaviour_patterns),
            "interests": list(self.interests),
            "conversation_preferences": list(self.conversation_preferences),
            "relationship_level": int(self.relationship_level),
            "affection_level": int(self.affection_level),
            "cozy_points": int(self.cozy_points),
            "lifetime_affection": int(self.lifetime_affection),
            "turn_count": int(self.turn_count),
            "archetype": self.archetype,
            "last_affection_gain_time": float(self.last_affection_gain_time),
            "daily_affection_earned": int(self.daily_affection_earned),
            "daily_affection_date": str(self.daily_affection_date),
            "known_preferences": list(self.known_preferences),
            "positive_patterns": list(self.positive_patterns),
            "negative_patterns": list(self.negative_patterns),
            "confidence": round(float(self.confidence), 3),
            "last_observations": self.last_observations[-10:]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonProfile":
        style_raw = data.get("communication_style", {})
        comm_style = CommunicationStyle.from_dict(style_raw) if isinstance(style_raw, dict) else CommunicationStyle()

        aff = int(data.get("affection_level", 10))
        life_aff = int(data.get("lifetime_affection", aff))
        return cls(
            user_id=str(data.get("user_id", "")),
            display_name=str(data.get("display_name", "Unknown")),
            interaction_count=int(data.get("interaction_count", 0)),
            first_seen=str(data.get("first_seen", "")),
            last_seen=str(data.get("last_seen", "")),
            communication_style=comm_style,
            behaviour_patterns=list(data.get("behaviour_patterns", [])),
            interests=list(data.get("interests", [])),
            conversation_preferences=list(data.get("conversation_preferences", [])),
            relationship_level=int(data.get("relationship_level", 0)),
            affection_level=aff,
            cozy_points=int(data.get("cozy_points", 100)),
            lifetime_affection=max(aff, life_aff),
            turn_count=int(data.get("turn_count", 0)),
            archetype=data.get("archetype"),
            last_affection_gain_time=float(data.get("last_affection_gain_time", 0.0)),
            daily_affection_earned=int(data.get("daily_affection_earned", 0)),
            daily_affection_date=str(data.get("daily_affection_date", "")),
            known_preferences=list(data.get("known_preferences", [])),
            positive_patterns=list(data.get("positive_patterns", [])),
            negative_patterns=list(data.get("negative_patterns", [])),
            confidence=float(data.get("confidence", 0.0)),
            last_observations=list(data.get("last_observations", []))
        )
