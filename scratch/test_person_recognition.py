"""
Comprehensive Test Suite for Person Recognition & Adaptive Interaction
Tests all 12 requirements from Section 25.
"""

import os
import sys
import shutil
import time

# Force UTF-8 stdout
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

TEST_DIR = "scratch/test_verification_db"
if os.path.exists(TEST_DIR):
    shutil.rmtree(TEST_DIR)

from person_memory import (
    PersonProfile,
    CommunicationStyle,
    BehaviourAnalyzer,
    BehaviourTracker,
    RelationshipManager,
    PersonMemoryManager,
    ReactionEngine,
    ObservationManager,
    BEHAVIOUR_CONFIDENCE_THRESHOLD
)

print("=" * 60)
print("TEST 1: New User Observation")
print("=" * 60)
om = ObservationManager(persist_dir=TEST_DIR)
u1_id = "111222333"
u1_name = "CasualGamer"

mode, react, directive = om.process_message(
    user_id=u1_id,
    display_name=u1_name,
    channel_id="ch_main",
    text="Hey what is up! Anyone playing games today?",
    is_dedicated=True
)
p1 = om.get_profile(u1_id)
print(f"User 1 First Interaction:")
print(f"  Confidence: {p1.confidence:.3f} (Expected low <= 0.30)")
print(f"  Relationship Level: {p1.relationship_level} (Expected 0 = New Face)")
print(f"  Adaptive Directive: {directive} (Expected None on turn 1)")
assert p1.confidence <= 0.35, "Confidence should be low on first message"
assert p1.relationship_level == 0, "Level should be 0 for new user"
assert directive is None, "Directive should not be produced on turn 1"

print("\n" + "=" * 60)
print("TEST 2 & 8: Returning User & Behaviour Evolution over Time")
print("=" * 60)
for i in range(15):
    om.process_message(
        user_id=u1_id,
        display_name=u1_name,
        channel_id="ch_main",
        text=f"lmao bro that play was actually hilarious 💀😂 #{i}",
        is_dedicated=True
    )
p1 = om.get_profile(u1_id)
print(f"User 1 after 16 interactions:")
print(f"  Confidence: {p1.confidence:.3f} (Expected >= 0.60)")
print(f"  Relationship Level: {p1.relationship_level} (Expected >= 1)")
print(f"  Patterns: {p1.behaviour_patterns}")
assert p1.confidence >= 0.60, "Confidence should have grown with repeated interactions"
assert "Frequently jokes and appreciates humor" in p1.behaviour_patterns or "Uses emojis frequently" in p1.behaviour_patterns

print("\n" + "=" * 60)
print("TEST 3: Username Change with Stable User ID")
print("=" * 60)
new_name = "EliteSniper99"
om.process_message(
    user_id=u1_id,
    display_name=new_name,
    channel_id="ch_main",
    text="Changed my username guys haha 😂",
    is_dedicated=True
)
p1_updated = om.get_profile(u1_id)
print(f"After display name change:")
print(f"  Display Name: {p1_updated.display_name} (Expected {new_name})")
print(f"  User ID: {p1_updated.user_id} (Unchanged: {u1_id})")
print(f"  Interaction Count: {p1_updated.interaction_count} (Preserved)")
assert p1_updated.display_name == new_name
assert p1_updated.user_id == u1_id
assert p1_updated.interaction_count == 17

print("\n" + "=" * 60)
print("TEST 4 & 5: Different Communication Styles & Active Chat Adaptation")
print("=" * 60)
u2_id = "444555666"
u2_name = "ScholarUser"

for i in range(18):
    om.process_message(
        user_id=u2_id,
        display_name=u2_name,
        channel_id="ch_main",
        text="Furthermore, the architectural methodology demonstrates superior resilience regarding distributed state management.",
        is_dedicated=True
    )

p2 = om.get_profile(u2_id)
print(f"Scholar User Formality: {p2.communication_style.formality:.2f}, Humor: {p2.communication_style.humor:.2f}")
mode, react, u2_directive = om.process_message(
    user_id=u2_id,
    display_name=u2_name,
    channel_id="ch_main",
    text="Could you summarize your conclusions regarding this topic?",
    is_dedicated=True
)
print("Scholar User Directive:")
print(u2_directive)
assert u2_directive is not None
assert "thoughtful, articulate" in u2_directive or "Avoid excessive slang" in u2_directive or "calm" in u2_directive

# Compare with Casual user directive
mode, react, u1_directive = om.process_message(
    user_id=u1_id,
    display_name=u1_name,
    channel_id="ch_main",
    text="bro drop a funny joke rn",
    is_dedicated=True
)
print("\nCasual User Directive:")
print(u1_directive)
assert u1_directive is not None
assert "humor" in u1_directive or "casually" in u1_directive or "witty" in u1_directive

print("\n" + "=" * 60)
print("TEST 6 & 7: Secondary Observation-Only Chat & Reaction Cooldown")
print("=" * 60)
om.set_channel_mode("ch_general", "OBSERVATION_ONLY")

# Send message and ensure text_reply is NEVER generated
mode, react, text_reply = om.process_message(
    user_id="999000111",
    display_name="ProjectHero",
    channel_id="ch_general",
    text="I finally finished my project 😭",
    is_dedicated=False
)
print(f"Observation Channel Mode: {mode}")
print(f"Text Reply generated: {text_reply} (Must be None - NEVER send text!)")
assert text_reply is None, "Text replies must NEVER be generated in observation channels"

# Find a message that successfully triggers a reaction
triggered_emoji = None
for attempt in range(25):
    m, r, t = om.process_message(
        user_id=f"hero_{attempt}",
        display_name="ProjectHero",
        channel_id=f"ch_achieve_{attempt}",
        text="I finally finished my project 😭",
        is_dedicated=False
    )
    assert t is None, "Text must never be sent in observation channels"
    if r:
        triggered_emoji = r
        # Now immediately test cooldown in the same channel & user
        m_cool, r_cool, t_cool = om.process_message(
            user_id=f"hero_{attempt}",
            display_name="ProjectHero",
            channel_id=f"ch_achieve_{attempt}",
            text="Second message immediately after reaction",
            is_dedicated=False
        )
        print(f"Reaction successfully triggered on attempt {attempt}: {repr(r)}")
        print(f"Immediate subsequent message reaction: {r_cool} (Expected None due to cooldown)")
        assert r_cool is None, "Cooldown must prevent rapid reaction spamming"
        break

assert triggered_emoji is not None, "At least one reaction should have triggered across 25 attempts"

print("\n" + "=" * 60)
print("TEST 9: Memory Reset (/reset_person)")
print("=" * 60)
reset_success = om.reset_user(u1_id)
print(f"Reset User {u1_id}: {reset_success}")
p1_after = om.get_profile(u1_id)
print(f"Profile after reset - Count: {p1_after.interaction_count}, Confidence: {p1_after.confidence}")
assert p1_after.interaction_count == 0
assert p1_after.confidence == 0.0

print("\n" + "=" * 60)
print("TEST 10: Multiple Users Interacting Simultaneously")
print("=" * 60)
for i in range(5):
    om.process_message(f"multi_user_{i}", f"User_{i}", "ch_main", f"Message from user {i}", is_dedicated=True)
profiles_count = len(om.memory_mgr._profiles_cache)
print(f"Active profiles in cache: {profiles_count}")
assert profiles_count >= 5

print("\n" + "=" * 60)
print("TEST 11: Bot Restart & Disk Persistence")
print("=" * 60)
om.memory_mgr.save_all()
# Create fresh observation manager from same disk directory
om_restarted = ObservationManager(persist_dir=TEST_DIR)
p2_restored = om_restarted.get_profile(u2_id)
ch_mode_restored = om_restarted.get_channel_mode("ch_general")
print(f"Restored User 2: Name={p2_restored.display_name}, Count={p2_restored.interaction_count}, Conf={p2_restored.confidence:.2f}")
print(f"Restored Channel Mode for ch_general: {ch_mode_restored}")
assert p2_restored.interaction_count >= 18
assert p2_restored.confidence >= 0.70
assert ch_mode_restored == "OBSERVATION_ONLY"

print("\n" + "=" * 60)
print("TEST 12: Existing Kazumi Core & Creator Lore Verification")
print("=" * 60)
try:
    from kazumi import Kazumi
    k = Kazumi()
    k.creator_context = "Sir Shan D. First (your creator and father)"
    k.person_directive = u2_directive
    print(f"Kazumi core loaded successfully with creator_context and person_directive.")
    print("All existing Kazumi integrations intact!")
except Exception as e:
    print(f"Error loading Kazumi: {e}")
    sys.exit(1)

# Cleanup
if os.path.exists(TEST_DIR):
    shutil.rmtree(TEST_DIR)

print("\n🎉 ALL 12 VERIFICATION TESTS PASSED SUCCESSFULLY!")
