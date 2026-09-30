"""
🌸 Kazumi Person Memory — Behaviour-Based Person Recognition & Adaptive Interaction
"""

from person_memory.person_profile import PersonProfile, CommunicationStyle
from person_memory.behaviour_analyzer import BehaviourAnalyzer
from person_memory.behaviour_tracker import BehaviourTracker, CONFIDENCE_THRESHOLD
from person_memory.relationship_manager import RelationshipManager
from person_memory.memory_manager import PersonMemoryManager
from person_memory.reaction_engine import ReactionEngine
from person_memory.observation_manager import ObservationManager, BEHAVIOUR_CONFIDENCE_THRESHOLD

_global_observation_manager = None

def get_observation_manager(persist_dir: str = "isa_memory") -> ObservationManager:
    """Returns the singleton ObservationManager instance."""
    global _global_observation_manager
    if _global_observation_manager is None:
        _global_observation_manager = ObservationManager(persist_dir=persist_dir)
    return _global_observation_manager

__all__ = [
    "PersonProfile",
    "CommunicationStyle",
    "BehaviourAnalyzer",
    "BehaviourTracker",
    "RelationshipManager",
    "PersonMemoryManager",
    "ReactionEngine",
    "ObservationManager",
    "get_observation_manager",
    "BEHAVIOUR_CONFIDENCE_THRESHOLD"
]
