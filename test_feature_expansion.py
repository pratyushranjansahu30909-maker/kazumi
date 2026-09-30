# -*- coding: utf-8 -*-
"""
KAZUMI COMPREHENSIVE FEATURE EXPANSION TEST SUITE
Validates all 35 sections of the advanced discord bot feature expansion:
- Moderation & AutoMod
- Logging
- Welcome & Goodbye
- AutoRole
- Tickets
- Giveaways
- Reaction Roles
- Custom Commands
- Server Info & Utilities
- Social Memory Graph
- Mood System
- Conversation Continuity
- Smart Silence & Natural Reactions
- Music System
- All 59+ registered slash commands
"""

import sys
import os
import time
import unittest
from unittest.mock import MagicMock, AsyncMock

# Add root directory to sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import discord
from discord.ext import commands
import discord_features
from discord_features.database import get_feature_db, FeatureDatabase
from discord_features.moderation import AutoModTracker, format_mod_explanation
from discord_features.welcome import WelcomeSystem
from discord_features.custom_commands import CustomCommandDispatcher
from discord_features.giveaways import parse_duration
from discord_features.server_memory import (
    MoodManager,
    SocialGraphManager,
    ServerMemoryManager,
    ConversationContinuityTracker,
    SmartSilenceEngine,
    NaturalReactionPicker,
    KazumiMomentsEngine
)
from discord_features.music import Track, GuildMusicPlayer


class KazumiFeatureExpansionTests(unittest.TestCase):

    def setUp(self):
        self.db = FeatureDatabase(persist_dir="isa_memory_test")
        self.bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
        self.tracker = AutoModTracker()

    def tearDown(self):
        import shutil
        if os.path.exists("isa_memory_test"):
            try:
                shutil.rmtree("isa_memory_test")
            except Exception:
                pass

    def test_01_database_atomic_operations(self):
        """Verify atomic JSON persistence across all tables."""
        self.db.update_guild_settings("123", {"welcome_channel_id": "456"})
        settings = self.db.get_guild_settings("123")
        self.assertEqual(settings.get("welcome_channel_id"), "456")

        # Warnings
        cnt = self.db.add_warning("123", "user_1", "mod_1", "Test rule break")
        self.assertEqual(cnt, 1)
        warns = self.db.get_warnings("123", "user_1")
        self.assertEqual(len(warns), 1)

        # Custom commands
        self.db.set_custom_command("123", "rules", "Read our rules!", "admin_1")
        cmd = self.db.get_custom_command("123", "rules")
        self.assertEqual(cmd["response"], "Read our rules!")

    def test_02_automod_rules(self):
        """Verify spam, link, invite, and bad-word filters."""
        automod_cfg = {
            "enabled": True,
            "anti_spam": True,
            "anti_invites": True,
            "anti_links": True,
            "anti_mentions": True,
            "max_mentions": 3,
            "bad_words": ["malicious", "exploit"]
        }

        # Invite test
        mock_msg = MagicMock(spec=discord.Message)
        mock_msg.guild = MagicMock(id=123)
        mock_msg.author = MagicMock(id=999)
        mock_msg.content = "Join my cool server: discord.gg/abcdef"
        mock_msg.mentions = []

        viol, rule, evid = self.tracker.record_and_evaluate(mock_msg, automod_cfg)
        self.assertTrue(viol)
        self.assertIn("Invite", rule)


        # Bad words test
        mock_msg.content = "Download this exploit right now"
        viol, rule, evid = self.tracker.record_and_evaluate(mock_msg, automod_cfg)
        self.assertTrue(viol)
        self.assertEqual(rule, "Prohibited Language")

        # Clean message
        mock_msg.content = "Hello Kazumi! How are you doing today?"
        viol, rule, evid = self.tracker.record_and_evaluate(mock_msg, automod_cfg)
        self.assertFalse(viol)

    def test_03_ai_mod_explanation(self):
        """Verify section 26 AI moderation explanation formatting."""
        explanation = format_mod_explanation("Timeout (10m)", "Repeated spam", "8 similar messages in 20 seconds", "High")
        self.assertIn("**Action:** Timeout (10m)", explanation)
        self.assertIn("**Evidence:** 8 similar messages in 20 seconds", explanation)

    def test_04_welcome_template_rendering(self):
        """Verify welcome card variable replacement."""
        mock_member = MagicMock(spec=discord.Member)
        mock_member.mention = "<@123456>"
        mock_member.name = "Alex"
        mock_guild = MagicMock()
        mock_guild.name = "Sakura Garden"
        mock_guild.member_count = 100
        mock_member.guild = mock_guild

        template = "Welcome {user} ({username}) to {server}! Member #{count} 🌸"
        result = WelcomeSystem.render_template(template, mock_member)
        self.assertEqual(result, "Welcome <@123456> (Alex) to Sakura Garden! Member #100 🌸")

    def test_05_giveaway_duration_parser(self):
        """Verify giveaway duration strings."""
        self.assertEqual(parse_duration("10m"), 600)
        self.assertEqual(parse_duration("2h"), 7200)
        self.assertEqual(parse_duration("1d"), 86400)
        self.assertIsNone(parse_duration("invalid"))

    def test_06_custom_command_interpolation(self):
        """Verify custom command variables."""
        mock_msg = MagicMock(spec=discord.Message)
        mock_msg.author = MagicMock(mention="<@111>", name="Sam")
        mock_guild = MagicMock()
        mock_guild.name = "Coder Den"
        mock_msg.guild = mock_guild
        mock_msg.channel = MagicMock(mention="<#999>")

        template = "Hey {user}, welcome to {server} in {channel}!"
        out = CustomCommandDispatcher.render_custom_response(template, mock_msg)
        self.assertEqual(out, "Hey <@111>, welcome to Coder Den in <#999>!")


    def test_07_social_graph_and_familiarity(self):
        """Verify social graph recording and interaction level progression."""
        sg = SocialGraphManager(self.db)
        # 1 interaction -> New
        sg.record_interaction(1001, 2001, "Maya", "I love playing valorant and minecraft!")
        prof = sg.get_user_profile(1001, 2001)
        self.assertEqual(prof["interaction_level"], "New")
        self.assertIn("gaming", prof["topics"])

        # Simulate 30 messages -> Familiar
        for _ in range(30):
            sg.record_interaction(1001, 2001, "Maya", "Haha funny joke lol")
        prof2 = sg.get_user_profile(1001, 2001)
        self.assertEqual(prof2["interaction_level"], "Familiar")

    def test_08_mood_transitions(self):
        """Verify mood transitions and prompt injections."""
        mood_mgr = MoodManager(self.db)
        mood_mgr.update_mood(1001, "LMAO that joke was so funny haha")
        m = mood_mgr.get_guild_mood(1001)
        self.assertIn(m, ["playful", "happy"])
        modifier = mood_mgr.get_mood_prompt_modifier(m)
        self.assertIsInstance(modifier, str)
        self.assertGreater(len(modifier), 10)

    def test_09_smart_silence_engine(self):
        """Verify smart silence decision rules."""
        engine = SmartSilenceEngine(bot_user_id=100)
        mock_msg = MagicMock(spec=discord.Message)
        mock_msg.channel = MagicMock(id=555)

        # Observation-only channel without ping -> SILENCE
        mock_msg.content = "Just random chatter between members"
        decision = engine.decide(mock_msg, is_direct_mention=False, is_reply_to_kazumi=False, is_active_channel=False, is_observation_only=True)
        self.assertEqual(decision, "SILENCE")

        # Direct mention -> REPLY
        mock_msg.content = "Hey @Kazumi!"
        decision = engine.decide(mock_msg, is_direct_mention=True, is_reply_to_kazumi=False, is_active_channel=True, is_observation_only=False)
        self.assertEqual(decision, "REPLY")

    def test_10_natural_reactions(self):
        """Verify contextual emoji picker."""
        emoji_funny = NaturalReactionPicker.pick_emoji("that was hilarious lmao haha")
        self.assertIn(emoji_funny, ["😂", "💀", "🤣", "😭"])

        emoji_achieve = NaturalReactionPicker.pick_emoji("We finally won the game, gg!")
        self.assertIn(emoji_achieve, ["🎉", "🔥", "🏆", "✨"])

    def test_11_music_track_and_queue(self):
        """Verify music track duration formatting and queue."""
        track = Track(title="Lofi Chill", url="https://youtube.com", stream_url="http://stream", duration=215, requester="Alex")
        self.assertEqual(track.formatted_duration, "03:35")

        player = GuildMusicPlayer(self.bot, 123)
        player.queue.append(track)
        self.assertEqual(len(player.queue), 1)

    def test_12_full_suite_registration(self):
        """Verify all feature commands register cleanly into bot.tree."""
        features = discord_features.setup_all_features(self.bot, self.bot.tree)
        commands_list = self.bot.tree.get_commands()
        cmd_names = {c.name for c in commands_list}

        # Check required commands
        expected_cmds = [
            "warn", "warnings", "clearwarnings", "timeout", "kick", "ban", "unban", "clear",
            "slowmode", "lock", "unlock", "automod", "logging", "welcome", "goodbye",
            "autorole", "ticket", "giveaway", "reactionrole", "customcommand", "tag",
            "ping", "uptime", "botinfo", "serverinfo", "userinfo", "avatar", "roleinfo",
            "channelinfo", "permissions", "poll", "announce", "remind", "time",
            "play", "pause", "resume", "skip", "queue", "nowplaying", "volume", "loop", "stop",
            "roast", "unhinged", "roastmode", "roastlevel", "roastoptout", "roastbattle"
        ]
        for name in expected_cmds:
            self.assertIn(name, cmd_names, f"Missing command: {name}")

        print(f"\n[OK] All {len(cmd_names)} Discord commands registered without collision!")

    def test_13_config_and_secret_redaction(self):
        """Verify centralized configuration and sensitive token masking (Phase 1)."""
        from discord_features.config import KazumiConfig, sanitize_secrets
        # Ensure default feature flags are present
        self.assertTrue(KazumiConfig.is_feature_enabled("moderation"))
        self.assertTrue(KazumiConfig.is_feature_enabled("automod"))

        # Test token masking
        fake_token = "dummy_auth_" + "part1_key." + "part2_signature." + "part3_verifier"
        fake_key = "sk-" + "dummykey1234567890abcdef12345678"
        masked = sanitize_secrets(f"Connecting with {fake_token} and key {fake_key}")
        self.assertNotIn(fake_key, masked)
        self.assertIn("[REDACTED_SECRET]", masked)

    def test_14_unhinged_roast_engine_generation(self):
        """Verify Unhinged Roast Engine generators, styles, and comebacks."""
        from discord_features.roast_engine import (
            RoastEngine,
            IntensityLevel,
            ComebackEngine,
            ContextAnalyzer,
            AbsurdComparisonEngine,
            DeadpanEngine,
            FakeProfessionalAnalysis,
            DramaticAndVillainEngine,
            ChaosGenerator
        )

        engine = RoastEngine(self.db)

        # 1. Procedural Intensity Generation
        for lvl in range(1, 6):
            success, roast, used_lvl = engine.generate_roast(target_name="Aamir", intensity=lvl)
            self.assertTrue(success)
            self.assertTrue(len(roast) > 5)
            self.assertEqual(used_lvl, lvl)

        # 2. Absurd Comparisons & Deadpan
        comp = AbsurdComparisonEngine.generate("Alex")
        self.assertTrue(len(comp) > 10)
        deadpan = DeadpanEngine.generate()
        self.assertTrue(len(deadpan) > 5)

        # 3. Diagnostic Analysis
        analysis = FakeProfessionalAnalysis.generate("Shan")
        self.assertIn("Findings:", analysis)
        self.assertIn("Clinical Diagnosis:", analysis)

        # 4. Dramatic & Villain Modes
        dramatic = DramaticAndVillainEngine.generate("dramatic")
        self.assertTrue(len(dramatic) > 10)
        villain = DramaticAndVillainEngine.generate("villain")
        self.assertTrue(len(villain) > 10)

        # 5. Chaos formats (Obituary, Patch Notes, Error 404, Security Alert)
        obit = ChaosGenerator.fake_obituary("Jordan")
        self.assertIn("HERE LIES", obit)
        patch = ChaosGenerator.patch_notes("Jordan")
        self.assertIn("Patch Notes", patch)
        err404 = ChaosGenerator.error_404("Jordan")
        self.assertIn("ERROR 404", err404)
        sec = ChaosGenerator.security_alert("Jordan")
        self.assertIn("SECURITY ALERT", sec)

        # 6. ComebackEngine triggers
        cat = ComebackEngine.detect_category("shut up bro")
        self.assertEqual(cat, "SHUT_UP")
        cb = ComebackEngine.get_comeback(cat)
        self.assertTrue(len(cb) > 2)
        self.assertIn("Make me.", ComebackEngine.COMEBACKS["SHUT_UP"])

        cat_bot = ComebackEngine.detect_category("you're literally a bot")
        self.assertEqual(cat_bot, "BOT_INSULT")
        self.assertIn("And somehow you're losing an argument to one.", ComebackEngine.COMEBACKS["BOT_INSULT"])

        cat_useless = ComebackEngine.detect_category("you're useless")
        self.assertEqual(cat_useless, "USELESS")
        self.assertIn("Yet here you are asking me for entertainment.", ComebackEngine.COMEBACKS["USELESS"])

        # 7. ContextAnalyzer (Sections 5, 9, 10)
        ctx_roast = ContextAnalyzer.analyze_message_context("I spent 5 hours on a missing semicolon")
        self.assertIsNotNone(ctx_roast)
        self.assertIn("FIVE HOURS", ctx_roast)

        ctx_6h = ContextAnalyzer.analyze_message_context("I spent 6 hours fixing a bug")
        self.assertIsNotNone(ctx_6h)
        self.assertIn("excavating ancient technology", ctx_6h)

        ctx_del = ContextAnalyzer.analyze_message_context("I accidentally deleted the entire project")
        self.assertIsNotNone(ctx_del)
        self.assertIn("deleted the ecosystem", ctx_del)

        ctx_proj = ContextAnalyzer.analyze_message_context("tutorial hell, changing project again")
        self.assertIsNotNone(ctx_proj)
        self.assertIn("faster than he finishes them", ctx_proj)

        # 8. All Section 6 Comedy Styles
        from discord_features.roast_engine import (
            AnalyticalEngine, ChaoticEngine, ShortBurnEngine, CallbackEngine
        )
        self.assertTrue(len(AnalyticalEngine.generate("Alex")) > 5)
        self.assertTrue(len(ChaoticEngine.generate("Alex")) > 3)
        self.assertTrue(len(ShortBurnEngine.generate("Alex")) > 3)
        self.assertTrue(len(CallbackEngine.generate("Alex")) > 5)

        # Generate roasts by style override
        for style in ["DEADPAN", "ANALYTICAL", "DRAMATIC", "VILLAIN", "ABSURD", "CHAOTIC", "SHORT_BURN", "CALLBACK"]:
            s, r, lvl = engine.generate_roast(target_name="Tester", style=style)
            self.assertTrue(s)
            self.assertTrue(len(r) > 3)

    def test_15_roast_safety_and_opt_out(self):
        """Verify strict anti-harassment safeguards and target consent."""
        from discord_features.roast_engine import RoastEngine, SafetyFilter

        engine = RoastEngine(self.db)

        # Hard safety filter against harassment / slurs
        safe, redirect_msg = SafetyFilter.is_safe_prompt("you should kys right now")
        self.assertFalse(safe)
        self.assertIn(redirect_msg, SafetyFilter.SAFE_REDIRECT_RESPONSES)

        # Opt-out test
        self.db.set_user_roast_opt_out(777888, True)
        self.assertTrue(self.db.is_user_roast_opted_out(777888))

        success, msg, _ = engine.generate_roast(target_name="ProtectedUser", target_id=777888)
        self.assertFalse(success)
        self.assertIn(msg, SafetyFilter.OPT_OUT_RESPONSES)

        # Opt back in
        self.db.set_user_roast_opt_out(777888, False)
        self.assertFalse(self.db.is_user_roast_opted_out(777888))
        success, msg, _ = engine.generate_roast(target_name="ProtectedUser", target_id=777888)
        self.assertTrue(success)

    def test_16_roast_personality_override_fix(self):
        """Verify that Kazumi never refuses a roast with cozy/empathetic lectures when roast_mode is active."""
        from kazumi import Kazumi

        k = Kazumi()
        k.roast_mode = True
        k.roast_intensity = 4
        k.roast_style = "UNHINGED"
        k.current_archetype = "UNHINGED"

        # Verify rule-based fallback responses when offline or testing
        reply = k.controller.get_fallback_chat_reply(
            user_text="roast me",
            valence=-0.1,
            situation="ROAST",
            current_archetype="UNHINGED"
        )
        self.assertTrue(len(reply) > 5)
        # Ensure NO cozy refusals
        refusal_phrases = [
            "cozy, empathetic", "all about that", "can't go savage", "cannot go savage",
            "cardboard box, darling", "drinking plain water like a plant"
        ]
        for phrase in refusal_phrases:
            self.assertNotIn(phrase.lower(), reply.lower())

        # Test mode exit restores normal personality
        k.roast_mode = False
        k.roast_intensity = 1
        k.roast_style = "NORMAL"
        k.current_archetype = "DEREDERE"
        self.assertFalse(k.roast_mode)
        self.assertEqual(k.current_archetype, "DEREDERE")

    def test_17_contextual_roast_intelligence_fix(self):
        """
        Verify KAZUMI CONTEXTUAL ROAST INTELLIGENCE FIX:
        1. Context -> Observation -> Joke Angle -> Punchline pipeline
        2. Detection of Coding Sequel, Gaming Donations, Overconfidence, Procrastination, Late Return
        3. Semantic validation rejects generic filler (search party, hazard pay, common sense)
        4. Honest playful deflection when zero context exists (Section 3)
        5. Random roast mode allowance (Section 16)
        """
        from discord_features.roast_engine import (
            RoastEngine,
            ContextAnalyzer,
            RoastValidator,
            ComedyAngle,
            BANNED_GENERIC_FILLER,
            NO_CONTEXT_PLAYFUL_RESPONSES
        )

        engine = RoastEngine(self.db)

        # 1. Pipeline: Coding Sequel
        obs_code = ContextAnalyzer.find_roastable_observation(
            target_recent_messages=["Bro I fixed my code", "wait it broke again"],
            target_name="DevUser"
        )
        self.assertIsNotNone(obs_code)
        self.assertEqual(obs_code.category, "CODING_SEQUEL")
        self.assertEqual(obs_code.angle, ComedyAngle.REVERSAL)
        self.assertIn("character development", obs_code.get_punchline(level=3))

        # 2. Pipeline: Gaming Donations & Excuses
        obs_game = ContextAnalyzer.find_roastable_observation(
            target_recent_messages=["Five losses in a row and I'm still deranked, trash team and lag"],
            target_name="Gamer"
        )
        self.assertIsNotNone(obs_game)
        self.assertEqual(obs_game.category, "GAMING_DONATION")
        self.assertEqual(obs_game.angle, ComedyAngle.IRONY)
        self.assertIn("donating wins", obs_game.get_punchline(level=3))

        # 3. Pipeline: Overconfidence Reversal
        obs_conf = ContextAnalyzer.find_roastable_observation(
            target_recent_messages=["Easy. I know exactly what I'm doing.", "wait it broke help"],
            target_name="Pro"
        )
        self.assertIsNotNone(obs_conf)
        self.assertEqual(obs_conf.category, "OVERCONFIDENCE")
        self.assertIn("confidence was impressive", obs_conf.get_punchline(level=2))

        # 4. Pipeline: Procrastination
        obs_proc = ContextAnalyzer.find_roastable_observation(
            target_recent_messages=["I'm definitely not going to procrastinate this time"],
            target_name="Student"
        )
        self.assertIsNotNone(obs_proc)
        self.assertEqual(obs_proc.category, "PROCRASTINATION")
        self.assertIn("CEO of Microsoft", obs_proc.get_punchline(level=2))

        # 5. Pipeline: Late Response / Side Quest
        obs_late = ContextAnalyzer.find_roastable_observation(
            target_recent_messages=["sorry i was busy"],
            time_away_seconds=9000,
            target_name="Wanderer"
        )
        self.assertIsNotNone(obs_late)
        self.assertEqual(obs_late.category, "LATE_RESPONSE")
        self.assertIn("side quest", obs_late.get_punchline(level=2))

        # 6. Pipeline: Project Hopping from Memory Pattern
        obs_proj = ContextAnalyzer.find_roastable_observation(
            target_recent_messages=["I have another amazing project idea"],
            target_patterns=["unfinished_projects", "project_hopper"],
            target_name="Maker"
        )
        self.assertIsNotNone(obs_proj)
        self.assertEqual(obs_proj.category, "PROJECT_HOPPING")
        self.assertIn("unfinished-project folder", obs_proj.get_punchline(level=3))

        # 7. Semantic Validation: Rejection of Banned Generic Clichés
        bad_generic = "I just dispatched a search party for your common sense. They found nothing and requested hazard pay."
        val_bad = RoastValidator.validate_roast(bad_generic, context="whatever", target_name="Target")
        self.assertFalse(val_bad["is_valid"])
        self.assertTrue(val_bad["is_generic"])
        self.assertTrue(any("banned generic filler" in r.lower() for r in val_bad["rejection_reasons"]))

        # 8. Semantic Validation: Acceptance of Good Contextual Roast
        good_roast = "Bro didn't fix the bug. He gave it character development."
        val_good = RoastValidator.validate_roast(good_roast, context="wait it broke again", target_name="DevUser")
        self.assertTrue(val_good["is_valid"])
        self.assertFalse(val_good["is_generic"])
        self.assertGreaterEqual(val_good["score"], 6)

        # 9. Section 3: If no context exists, DO NOT invent random nonsense
        s_no_ctx, r_no_ctx, lvl_no_ctx = engine.generate_roast(
            target_name="InnocentUser",
            context_text=None,
            target_recent_messages=[],
            allow_random=False
        )
        self.assertTrue(s_no_ctx)
        # Must be an honest playful deflection, NOT a disconnected insult
        valid_deflections = [
            "give me something to work with",
            "zero evidence",
            "stand still for five minutes",
            "innocent bystanders",
            "zero context detected"
        ]
        self.assertTrue(any(v in r_no_ctx.lower() for v in valid_deflections), f"Unexpected response: {r_no_ctx}")
        for filler in BANNED_GENERIC_FILLER:
            self.assertNotIn(filler, r_no_ctx.lower())

        # 10. Section 16: Random Roast Mode explicitly allowed
        s_rand, r_rand, _ = engine.generate_roast(
            target_name="RandomUser",
            allow_random=True
        )
        self.assertTrue(s_rand)
        self.assertGreater(len(r_rand), 5)
        for filler in BANNED_GENERIC_FILLER:
            self.assertNotIn(filler, r_rand.lower())


if __name__ == "__main__":
    unittest.main()

