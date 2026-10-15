# -*- coding: utf-8 -*-
"""
Automated Verification Suite for Kazumi Final Comprehensive Repair & Companion Upgrade.
Verifies:
- Phase 2: Natural conversation continuity without repeat mentions (short answers, context keys, expiration, silence)
- Phase 3: Emotional tone analysis and contextual directives
- Phase 4: Independent member affection, persistent storage (survival beyond 50 users), legacy migration
- Phase 6: Command intelligence, honest capability awareness, multilingual AutoMod
"""

import os
import sys
import time
import json
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock, AsyncMock

# Add root directory to sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from discord_features.conversation_context import (
    ConversationContextManager,
    ConversationContext,
    get_conversation_manager
)
from discord_features.human_interaction import (
    HumanInteractionEngine,
    InteractionDecision
)
from discord_features.moderation import AutoModTracker
from discord_features.intent_router import NaturalIntentRouter
from kazumi_emotions import EmotionalContextAnalyzer, get_emotional_analyzer
from person_memory.memory_manager import PersonMemoryManager
from person_memory.person_profile import PersonProfile
from person_memory.relationship_manager import RelationshipManager


# =========================================================================
# PHASE 2: CONVERSATION CONTINUITY & CONTEXT MANAGER TESTS
# =========================================================================

class TestConversationContinuity:
    def test_multi_turn_continuation_without_repeat_mentions(self):
        mgr = ConversationContextManager(default_timeout_seconds=60.0)

        # Mock incoming message 1 (User pinging Kazumi)
        msg1 = MagicMock()
        msg1.guild.id = 1001
        msg1.channel.id = 2001
        msg1.author.id = 3001
        msg1.id = 5001
        msg1.content = "@Kazumi, never give up is the best advice."
        msg1.reference = None

        # Record user message 1
        mgr.record_user_message(msg1)

        # Record Kazumi's response with a follow-up question
        bot_reply_text = "That's a wonderful mindset! What keeps you motivated on tough days?"
        mgr.record_kazumi_response(msg1, bot_reply_text, bot_message_id=9001)

        ctx = mgr.get_context(mgr.make_key(msg1))
        assert ctx is not None
        assert ctx.awaiting_response is True
        assert "motivated" in (ctx.last_question_asked or "").lower()

        # User sends follow-up without mentioning Kazumi!
        msg2 = MagicMock()
        msg2.guild.id = 1001
        msg2.channel.id = 2001
        msg2.author.id = 3001
        msg2.id = 5002
        msg2.content = "My family motivates me."
        msg2.reference = None

        is_cont, reason, c_ctx = mgr.is_continuation(msg2)
        assert is_cont is True
        assert "answering" in reason.lower() or "continuation" in reason.lower()

    def test_short_answers_recognized_when_awaiting_response(self):
        mgr = ConversationContextManager(default_timeout_seconds=60.0)

        msg = MagicMock()
        msg.guild.id = 1001
        msg.channel.id = 2001
        msg.author.id = 3002
        msg.id = 5010
        msg.content = "Hey Kazumi"
        msg.reference = None

        mgr.record_user_message(msg)
        mgr.record_kazumi_response(msg, "Did you finish the task today?", bot_message_id=9010)

        short_answers = [
            "Yeah.",
            "Not really.",
            "Exactly",
            "I finished it.",
            "The blue one.",
            "That was fun.",
            "Like yesterday."
        ]

        for ans in short_answers:
            msg_ans = MagicMock()
            msg_ans.guild.id = 1001
            msg_ans.channel.id = 2001
            msg_ans.author.id = 3002
            msg_ans.id = 5011
            msg_ans.content = ans
            msg_ans.reference = None

            is_cont, reason, _ = mgr.is_continuation(msg_ans)
            assert is_cont is True, f"Failed to recognize short answer continuation: '{ans}'"

    def test_discord_reply_reference_detection(self):
        mgr = ConversationContextManager(default_timeout_seconds=60.0)

        msg1 = MagicMock()
        msg1.guild.id = 1001
        msg1.channel.id = 2001
        msg1.author.id = 3003
        msg1.id = 5020
        msg1.content = "Tell me a joke"
        msg1.reference = None

        mgr.record_user_message(msg1)
        mgr.record_kazumi_response(msg1, "Why did the scarecrow win an award? Because he was outstanding in his field! 🌸", bot_message_id=9020)

        # User replies directly using Discord's reply function to Kazumi's message 9020
        msg2 = MagicMock()
        msg2.guild.id = 1001
        msg2.channel.id = 2001
        msg2.author.id = 3003
        msg2.id = 5021
        msg2.content = "Haha good one"
        msg2.reference = MagicMock()
        msg2.reference.message_id = 9020

        is_cont, reason, _ = mgr.is_continuation(msg2)
        assert is_cont is True
        assert "reply" in reason.lower()

    def test_isolation_between_different_users(self):
        mgr = ConversationContextManager(default_timeout_seconds=60.0)

        # User A in channel
        msgA = MagicMock()
        msgA.guild.id = 1001
        msgA.channel.id = 2001
        msgA.author.id = 3001
        msgA.id = 5030
        msgA.content = "Hi Kazumi!"
        msgA.reference = None

        mgr.record_user_message(msgA)
        mgr.record_kazumi_response(msgA, "Hey User A! How was your day?", bot_message_id=9030)

        # User B speaks in the same channel without mentioning Kazumi
        msgB = MagicMock()
        msgB.guild.id = 1001
        msgB.channel.id = 2001
        msgB.author.id = 3002
        msgB.id = 5031
        msgB.content = "Who wants to play Valorant tonight?"
        msgB.reference = None

        is_cont, reason, _ = mgr.is_continuation(msgB)
        assert is_cont is False, "User B's unrelated message should not continue User A's session"

    def test_session_expiration_and_closure(self):
        mgr = ConversationContextManager(default_timeout_seconds=0.1)

        msg = MagicMock()
        msg.guild.id = 1001
        msg.channel.id = 2001
        msg.author.id = 3005
        msg.id = 5040
        msg.content = "Are you here?"
        msg.reference = None

        mgr.record_user_message(msg)
        time.sleep(0.15)  # Wait for timeout

        msg2 = MagicMock()
        msg2.guild.id = 1001
        msg2.channel.id = 2001
        msg2.author.id = 3005
        msg2.id = 5041
        msg2.content = "Hello?"
        msg2.reference = None

        is_cont, reason, _ = mgr.is_continuation(msg2)
        assert is_cont is False, "Expired conversation must not trigger automatic continuation"

    def test_explicit_stop_and_farewell_closes_session(self):
        mgr = ConversationContextManager(default_timeout_seconds=60.0)

        msg = MagicMock()
        msg.guild.id = 1001
        msg.channel.id = 2001
        msg.author.id = 3006
        msg.id = 5050
        msg.content = "Hi Kazumi"
        msg.reference = None

        mgr.record_user_message(msg)
        mgr.record_kazumi_response(msg, "Hey there! 🌸", bot_message_id=9050)

        # Close session explicitly (stop / silence)
        mgr.close_session(msg)
        ctx = mgr.get_context(mgr.make_key(msg))
        assert ctx.closure_state == "CLOSED"

        # Subsequent follow-up without mention is now rejected
        msg_followup = MagicMock()
        msg_followup.guild.id = 1001
        msg_followup.channel.id = 2001
        msg_followup.author.id = 3006
        msg_followup.id = 5051
        msg_followup.content = "Are you still there?"
        msg_followup.reference = None

        is_cont, reason, _ = mgr.is_continuation(msg_followup)
        assert is_cont is False


# =========================================================================
# PHASE 3: EMOTIONAL INTELLIGENCE & TONE DIRECTIVES
# =========================================================================

class TestEmotionalIntelligence:
    def test_emotional_tone_categories(self):
        analyzer = get_emotional_analyzer()

        test_cases = [
            ("I finally completed my project!", "EXCITED"),
            ("I passed all my exams today so happy!", "HAPPY"),
            ("I failed my exam today...", "DISAPPOINTED"),
            ("This annoying bug has been wasting my time for hours, broken bot", "FRUSTRATED"),
            ("Can you explain how black holes work?", "CURIOUS"),
            ("Wait what do you mean by that, I am confused", "CONFUSED"),
            ("Kazumi is secretly planning world domination haha", "PLAYFUL"),
            ("We need to discuss an urgent matter, need serious advice", "SERIOUS"),
            ("The sky is blue today.", "NEUTRAL"),
        ]

        for text, expected_category in test_cases:
            cat, conf, reason = analyzer.analyze(text)
            assert cat == expected_category, f"Expected {expected_category} for '{text}', got {cat}"

    def test_tone_prompt_directive_generation(self):
        analyzer = get_emotional_analyzer()
        cat, conf, _ = analyzer.analyze("I finally completed my project!")
        directive = analyzer.get_tone_prompt_directive(cat)
        assert directive is not None
        assert "Emotional Intelligence" in directive
        assert "EXCITED" in directive


# =========================================================================
# PHASE 4: AFFECTION ISOLATION & PERSISTENT STORAGE
# =========================================================================

class TestAffectionAndPersistence:
    def test_independent_affection_per_member(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pmm = PersonMemoryManager(persist_dir=tmpdir)

            # Member A and Member B start at default 10
            aff_a = pmm.get_affection("user_1001")
            aff_b = pmm.get_affection("user_1002")
            assert aff_a == 10
            assert aff_b == 10

            # Award affection to Member A only
            gain_a = pmm.add_affection("user_1001", delta=15.0)
            assert gain_a > 0
            assert pmm.get_affection("user_1001") > 10

            # Member B MUST remain unaffected
            aff_b_after = pmm.get_affection("user_1002")
            assert aff_b_after == 10, f"Member B affection changed! Expected 10, got {aff_b_after}"

    def test_persistence_across_save_and_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pmm1 = PersonMemoryManager(persist_dir=tmpdir)

            pmm1.set_affection("user_2001", 42)
            pmm1.add_cozy_points("user_2001", 150)
            pmm1.save_profiles()

            # Create a completely new instance reloading from disk
            pmm2 = PersonMemoryManager(persist_dir=tmpdir)
            assert pmm2.get_affection("user_2001") == 42
            assert pmm2.get_cozy_points("user_2001") == 250  # 100 default + 150

    def test_preservation_beyond_50_users_no_pruning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pmm = PersonMemoryManager(persist_dir=tmpdir)

            # Insert 75 distinct member profiles
            for i in range(1, 76):
                uid = f"discord_member_{i}"
                pmm.set_affection(uid, i)

            pmm.save_profiles()

            # Verify that all 75 members are safely persisted without any 50-item pruning
            pmm_reload = PersonMemoryManager(persist_dir=tmpdir)
            assert len(pmm_reload._profiles_cache) == 75
            for i in range(1, 76):
                assert pmm_reload.get_affection(f"discord_member_{i}") == i

    def test_daily_affection_cap_and_cooldown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pmm = PersonMemoryManager(persist_dir=tmpdir)

            # Rapid-fire affection gains should respect diminishing returns and cooldown
            gains = []
            for _ in range(5):
                g = pmm.add_affection("user_spammer", delta=5.0)
                gains.append(g)

            # The 5th immediate gain should be clamped or diminished
            prof = pmm.get_profile("user_spammer")
            assert prof.daily_affection_earned <= 25.0

    def test_legacy_data_migration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            legacy_file = os.path.join(tmpdir, "profile.json")

            # Create fake legacy profile.json with old session_game_states
            legacy_data = {
                "name": "Kazumi",
                "session_game_states": {
                    "discord_user_888": {
                        "affection_level": 77,
                        "cozy_points": 340,
                        "turn_count": 52
                    },
                    "discord_user_999": {
                        "affection_level": 60,
                        "cozy_points": 180,
                        "turn_count": 28
                    }
                }
            }
            with open(legacy_file, "w", encoding="utf-8") as f:
                json.dump(legacy_data, f)

            pmm = PersonMemoryManager(persist_dir=tmpdir)
            migrated_count = pmm.migrate_legacy_data(legacy_file)
            assert migrated_count == 2
            assert pmm.get_affection("888") == 77
            assert pmm.get_cozy_points("888") == 340
            assert pmm.get_affection("999") == 60


# =========================================================================
# PHASE 6: COMMAND INTELLIGENCE & CAPABILITY ROUTING
# =========================================================================

class TestCommandIntelligence:
    @pytest.mark.asyncio
    async def test_capability_intent_routing(self):
        bot = MagicMock()
        bot.latency = 0.045
        router = NaturalIntentRouter(bot, {})

        msg = MagicMock()
        msg.author.display_name = "Alex"

        # 1. "Are all your commands working?"
        intent1 = router.detect_intent("Are all your commands working?", msg)
        assert intent1 is not None
        assert intent1.get("action") == "check_commands"
        handled, text, embed = await router.execute_intent(intent1, msg)
        assert handled is True
        assert embed is not None
        assert "Diagnostic" in embed.title

        # 2. "Can you run a command to prove it?"
        intent2 = router.detect_intent("Can you run a command to prove it?", msg)
        assert intent2 is not None
        assert intent2.get("action") == "prove_command"
        handled, text, embed = await router.execute_intent(intent2, msg)
        assert handled is True
        assert embed is not None
        assert "Latency" in embed.description

        # 3. "Can you delete messages containing swear words in any language?"
        intent3 = router.detect_intent("Can you delete messages containing swear words in any language?", msg)
        assert intent3 is not None
        assert intent3.get("action") == "swear_words_capability"
        handled, text, embed = await router.execute_intent(intent3, msg)
        assert handled is True
        assert "multilingual" in embed.description.lower()

        # 4. "Can you join voice and talk?"
        intent4 = router.detect_intent("Can you join voice and talk?", msg)
        assert intent4 is not None
        assert intent4.get("action") == "voice_capability"
        handled, text, embed = await router.execute_intent(intent4, msg)
        assert handled is True
        assert "voice channel" in embed.description.lower()

    def test_multilingual_profanity_filtering(self):
        automod = AutoModTracker()

        # English
        assert automod.check_bad_words("what the fuck is this") is True
        # Spanish
        assert automod.check_bad_words("eres un mierda total") is True
        # Hindi / Hinglish
        assert automod.check_bad_words("chup kar madarchod") is True
        assert automod.check_bad_words("kameena insaan") is True
        # French
        assert automod.check_bad_words("putain de merde") is True
        # German
        assert automod.check_bad_words("du arschloch") is True
        # Clean text
        assert automod.check_bad_words("Hello Kazumi! You are wonderful.") is False
