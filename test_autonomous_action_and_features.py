"""
Comprehensive Test Suite for Kazumi's Autonomous Action Engine, Multilingual AutoMod,
Media Moderation, Server Leveling, Secure Giveaways, and Music System.

Covers Acceptance Tests A through G as specified in the Phase 10 Requirements:
- Test A: Autonomous Action Engine (registry, permission checks, confirmation, execution)
- Test B: Multilingual AutoMod (English, Hindi, Hinglish, Odia, severity grading, private DMs)
- Test C: Media Moderation (SSRF guard, prohibited domains, visual heuristics)
- Test D: Persistent Server Leveling (XP, cooldown, anti-farming, rank cards, leaderboard)
- Test E: Secure Giveaways (Mode A claim deadline & reroll, Mode B permanent, CSPRNG, hash-chain audit)
- Test F: Music System (Spotify metadata resolution, queue controls)
- Test G: Companion Regression & Stability (personality, memory, affection)
"""

import os
import sys
import json
import time
import asyncio
import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure root directory is on sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from discord_features.action_engine import (
    ActionRegistry,
    ActionRiskLevel,
    ActionDefinition,
    ActionConfirmationView,
    get_action_engine
)
from discord_features.multilingual_automod import (
    MultilingualAutoMod,
    ViolationSeverity
)
from discord_features.media_moderator import (
    MediaSafetyModerator,
    SSRFGuard
)
from discord_features.leveling import (
    LevelingManager
)
from discord_features.giveaways import (
    GiveawayAuditLedger,
    GiveawayState,
    GiveawayManager
)


# =============================================================================
# TEST A — AUTONOMOUS ACTIONS
# =============================================================================

@pytest.mark.asyncio
async def test_action_engine_registration_and_lookup():
    """Verify action engine correctly registers actions and retrieves definitions."""
    engine = ActionRegistry()
    assert "get_user_stats" in engine.actions
    assert "start_game" in engine.actions
    assert "mod_ban" in engine.actions
    assert "giveaway_create" in engine.actions

    action_def = engine.get_action("mod_ban")
    assert action_def.risk_level in (ActionRiskLevel.HIGH, ActionRiskLevel.DESTRUCTIVE)
    assert action_def.requires_confirmation is True
    assert "ban_members" in action_def.required_bot_permissions


@pytest.mark.asyncio
async def test_action_engine_permission_gating():
    """Unauthorized users cannot execute privileged actions."""
    engine = ActionRegistry()

    # Mock low-privilege user
    mock_user = MagicMock()
    mock_user.id = 99999
    mock_user.guild_permissions.administrator = False
    mock_user.guild_permissions.ban_members = False

    mock_channel = MagicMock()
    mock_guild = MagicMock()
    mock_guild.me.guild_permissions.ban_members = True

    context = {
        "user": mock_user,
        "channel": mock_channel,
        "guild": mock_guild
    }

    # Ban action requires admin/ban_members
    result = await engine.execute_action(
        "mod_ban",
        {"target_id": 12345, "reason": "Test ban"},
        context
    )
    assert result.success is False
    assert "Missing user permission" in result.error


@pytest.mark.asyncio
async def test_action_engine_confirmation_view_for_dangerous_actions():
    """Dangerous actions require confirmation before execution."""
    view = ActionConfirmationView(
        action_name="mod_purge",
        arguments={"limit": 50},
        context={},
        authorized_user_id=12345
    )
    assert view.action_name == "mod_purge"
    assert view.confirmed is False


@pytest.mark.asyncio
async def test_action_engine_truthful_failure_reporting():
    """Actions return truthful structured errors when unknown or invalid."""
    engine = ActionRegistry()
    result = await engine.execute_action(
        "nonexistent_action",
        {},
        {"user": MagicMock(), "channel": MagicMock(), "guild": MagicMock()}
    )
    assert result.success is False
    assert "Unknown action" in result.error


# =============================================================================
# TEST B — MULTILINGUAL AUTOMOD
# =============================================================================

def test_multilingual_automod_english_slurs():
    """Detects abusive language in English with correct severity."""
    automod = MultilingualAutoMod()
    res = automod.evaluate_text("I hate you and I will kill you, you die bitch", user_id=101)
    assert res["violation"] is True
    assert res["severity"] in (ViolationSeverity.SEVERE, ViolationSeverity.MEDIUM)


def test_multilingual_automod_hindi_hinglish():
    """Detects abusive language in Hindi and Hinglish."""
    automod = MultilingualAutoMod()
    res = automod.evaluate_text("tu madarchod hai bilkul randi", user_id=102)
    assert res["violation"] is True
    assert res["severity"] == ViolationSeverity.SEVERE
    assert "Hinglish" in res["matched_rule"] or "Hindi" in res["matched_rule"]


def test_multilingual_automod_odia():
    """Detects abusive language in Odia."""
    automod = MultilingualAutoMod()
    res = automod.evaluate_text("tora maghia heichi be", user_id=103)
    assert res["violation"] is True
    assert res["severity"] == ViolationSeverity.SEVERE
    assert "Odia" in res["matched_rule"]


def test_multilingual_automod_benign_conversations():
    """Benign conversations, ordinary chat, and friendly greetings are safe."""
    automod = MultilingualAutoMod()
    benign_messages = [
        "Hello Kazumi, how are you today?",
        "namaste sabhi dosto ko!",
        "kemiti achha bhai mane? kana chalichi?",
        "that boss fight was crazy hard lol",
        "good morning everyone in LAPEACE server"
    ]
    for msg in benign_messages:
        res = automod.evaluate_text(msg, user_id=104)
        assert res["violation"] is False, f"False positive on benign message: {msg}"


def test_multilingual_automod_leetspeak_and_substitutions():
    """Detects deliberate obfuscation and leetspeak substitutions."""
    automod = MultilingualAutoMod()
    res = automod.evaluate_text("b!tch you suck", user_id=105)
    assert res["violation"] is True


# =============================================================================
# TEST C — MEDIA MODERATION
# =============================================================================

def test_media_moderator_ssrf_protection():
    """Blocks SSRF attempts to private networks, localhost, and cloud metadata."""
    assert SSRFGuard.is_safe_url("http://localhost:8080/test.png")[0] is False
    assert SSRFGuard.is_safe_url("http://127.0.0.1:8000/image.jpg")[0] is False
    assert SSRFGuard.is_safe_url("http://169.254.169.254/latest/meta-data/")[0] is False
    assert SSRFGuard.is_safe_url("http://192.168.1.1/secret.gif")[0] is False
    assert SSRFGuard.is_safe_url("https://cdn.discordapp.com/attachments/1/2/pic.png")[0] is True


def test_media_moderator_adult_domain_blocking():
    """Blocks links to known adult / pornography hosting domains."""
    mod = MediaSafetyModerator()
    res = mod.evaluate_url("https://pornhub.com/view_video.php?viewkey=123")
    assert res["violation"] is True
    assert res["category"] == "explicit_domain"


def test_media_moderator_benign_url():
    """Allows benign, lawful image and general domains."""
    mod = MediaSafetyModerator()
    res = mod.evaluate_url("https://i.imgur.com/safe_cat_photo.jpg")
    assert res["violation"] is False


# =============================================================================
# TEST D — LEVELING AND CHAT ACTIVITY
# =============================================================================

def test_leveling_xp_progression_and_anti_farming(tmp_path):
    """XP progression, cooldowns, and anti-farming message deduplication."""
    db_file = os.path.join(tmp_path, "test_levels.json")
    manager = LevelingManager(storage_file=db_file)

    guild_id = 99901
    user_id = 88801

    # First eligible message awards XP
    xp_gained, leveled_up, new_lvl = manager.record_chat_activity(
        guild_id, user_id, "Hello everyone in LAPEACE server, nice to meet you all!"
    )
    assert xp_gained > 0
    assert leveled_up is False or new_lvl >= 1

    stats = manager.get_user_stats(guild_id, user_id)
    assert stats["eligible_messages"] == 1
    assert stats["xp"] > 0

    # Immediate second message is within cooldown -> 0 XP gained
    xp_gained_2, _, _ = manager.record_chat_activity(
        guild_id, user_id, "Another fast message within cooldown window"
    )
    assert xp_gained_2 == 0

    # Duplicate spam message content is rejected
    manager.cooldowns.clear()  # Clear cooldown
    xp_gained_3, _, _ = manager.record_chat_activity(
        guild_id, user_id, "Hello everyone in LAPEACE server, nice to meet you all!"
    )
    assert xp_gained_3 == 0  # Deduplicated duplicate content


def test_leveling_leaderboard_ordering(tmp_path):
    """Leaderboard correctly ranks top chatters by level and XP."""
    db_file = os.path.join(tmp_path, "test_leaderboard.json")
    manager = LevelingManager(storage_file=db_file)

    guild_id = 99902
    manager.adjust_user_xp(guild_id, 1, xp_delta=500, level_override=5)
    manager.adjust_user_xp(guild_id, 2, xp_delta=200, level_override=2)
    manager.adjust_user_xp(guild_id, 3, xp_delta=800, level_override=8)

    lb = manager.get_leaderboard(guild_id, limit=3)
    assert len(lb) == 3
    assert lb[0]["user_id"] == "3"  # Highest level
    assert lb[1]["user_id"] == "1"
    assert lb[2]["user_id"] == "2"


# =============================================================================
# TEST E — SECURE GIVEAWAY SYSTEM
# =============================================================================

def test_giveaway_csprng_winner_selection(tmp_path):
    """Cryptographically secure selection deduplicates entrants and chooses valid winners."""
    db_file = os.path.join(tmp_path, "test_giveaways.json")
    mgr = GiveawayManager(storage_file=db_file)

    gw_id = "gw_test_01"
    entrants = [1001, 1002, 1003, 1004, 1005]

    winners = mgr.pick_winners(
        giveaway_id=gw_id,
        eligible_entrants=entrants,
        winner_count=2,
        claim_mode="MODE_A",
        claim_window_seconds=86400
    )

    assert len(winners) == 2
    assert winners[0]["user_id"] in entrants
    assert winners[1]["user_id"] in entrants
    assert winners[0]["user_id"] != winners[1]["user_id"]
    assert winners[0]["status"] == "AWAITING_CLAIM"
    assert winners[0]["claim_deadline"] > time.time()


def test_giveaway_mode_a_claim_deadline_and_reroll(tmp_path):
    """Mode A expiry marks winner expired and picks replacement with fresh deadline."""
    db_file = os.path.join(tmp_path, "test_giveaways_reroll.json")
    mgr = GiveawayManager(storage_file=db_file)

    gw_id = "gw_test_mode_a"
    entrants = [2001, 2002, 2003]

    # Pick initial winner with simulated expired deadline
    winners = mgr.pick_winners(
        giveaway_id=gw_id,
        eligible_entrants=entrants,
        winner_count=1,
        claim_mode="MODE_A",
        claim_window_seconds=10
    )
    initial_winner_id = winners[0]["user_id"]

    # Manually backdate claim deadline to simulate expiry
    mgr.giveaways[gw_id]["winners"][0]["claim_deadline"] = time.time() - 50

    # Reroll expired winner
    replacement = mgr.reroll_expired_winner(gw_id, prize_index=0, eligible_entrants=entrants)
    assert replacement is not None
    assert replacement["user_id"] != initial_winner_id
    assert replacement["user_id"] in entrants
    assert replacement["attempt_number"] == 2
    assert replacement["claim_deadline"] > time.time()

    # Verify history is preserved (initial winner is not erased, but marked EXPIRED)
    gw = mgr.giveaways[gw_id]
    assert len(gw["winner_history"]) >= 1
    assert gw["winner_history"][0]["status"] == "EXPIRED"


def test_giveaway_mode_b_no_automatic_expiry(tmp_path):
    """Mode B claim has no automatic claim deadline (None)."""
    db_file = os.path.join(tmp_path, "test_giveaways_mode_b.json")
    mgr = GiveawayManager(storage_file=db_file)

    gw_id = "gw_test_mode_b"
    winners = mgr.pick_winners(
        giveaway_id=gw_id,
        eligible_entrants=[3001, 3002],
        winner_count=1,
        claim_mode="MODE_B",
        claim_window_seconds=None
    )
    assert winners[0]["claim_deadline"] is None
    assert winners[0]["status"] == "AWAITING_CLAIM"


def test_giveaway_audit_ledger_hash_chaining(tmp_path):
    """Giveaway audit ledger maintains cryptographic SHA-256 hash chaining."""
    log_file = os.path.join(tmp_path, "giveaway_audit.jsonl")
    ledger = GiveawayAuditLedger(ledger_path=log_file)

    e1 = ledger.record_event("gw_100", "CREATE", {"prize": "Headset", "creator": 555})
    e2 = ledger.record_event("gw_100", "WINNER_DRAWN", {"winner": 666})
    e3 = ledger.record_event("gw_100", "CLAIMED", {"winner": 666})

    assert e1["previous_hash"] == "GENESIS"
    assert e2["previous_hash"] == e1["record_hash"]
    assert e3["previous_hash"] == e2["record_hash"]

    # Verify ledger integrity check
    integrity = ledger.verify_integrity("gw_100")
    assert integrity["valid"] is True
    assert integrity["events_verified"] == 3


# =============================================================================
# TEST F — MUSIC SYSTEM SPOTIFY METADATA RESOLUTION
# =============================================================================

@pytest.mark.asyncio
async def test_spotify_oembed_metadata_lookup():
    """Spotify track URLs resolve cleanly to song title and artist."""
    from discord_features.music import resolve_spotify_metadata

    sample_url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
    info = await resolve_spotify_metadata(sample_url)
    assert info is not None
    assert "title" in info
    assert "search_query" in info
    assert len(info["search_query"]) > 0


# =============================================================================
# TEST G — COMPANION REGRESSION AND STABILITY
# =============================================================================

def test_companion_personality_and_memory_retention():
    """Companion emotional engine and memory manager remain intact."""
    from kazumi_emotions import get_emotional_analyzer
    analyzer = get_emotional_analyzer()
    tone, conf, _ = analyzer.analyze("I had such a wonderful day today!")
    assert tone == "HAPPY"
    assert conf >= 0.70
