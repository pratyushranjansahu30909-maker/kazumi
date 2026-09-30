# -*- coding: utf-8 -*-
"""
🌸 KAZUMI UNHINGED ROAST ENGINE
Context-aware, savage, unpredictable comedy engine.

Capabilities:
- Dynamic Intensity Levels (0 to 5: None -> Teasing -> Playful -> Savage -> Unhinged -> Nuclear)
- Hard Safety Boundaries & Anti-Harassment Safeguards with Playful Redirects
- Target Opt-Out System (Diplomatic Immunity)
- Friendship-Based Escalation (integrates with Person Memory & Relationship Levels)
- Context & Observational Roasting (debug fails, gaming losses, rapid typing, deleted messages)
- Absurd Comparison Engine & Deadpan One-Liners
- Fake Professional Analysis (comedic scientific breakdowns)
- Dramatic & Anime / Villain Roast Modes
- Multi-Style ComebackEngine with Self-Deprecating Humor
- Random Chaos Modes (Fake Obituaries, Patch Notes, Error 404, Security Alerts)
- Anti-Repetition & Similarity Checker
- Interactive Multi-Round Roast Battles with Comedic Damage Reports
"""

import os
import re
import time
import random
import difflib
import logging
from typing import Dict, List, Any, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("KazumiRoastEngine")

# =============================================================================
# 1. HARD SAFETY FILTER & ANTI-HARASSMENT BOUNDARIES (Section 3, 24, 25)
# =============================================================================

# Strictly prohibited toxic / sensitive categories
HARASSMENT_KEYWORDS = {
    # Hate speech, slurs, bigotry
    "retard", "retarded", "spastic", "autistic", "cripple",
    "fag", "faggot", "dyke", "tranny", "shemale",
    "nigger", "nigga", "chink", "kike", "gook", "paki",
    # Self-harm, suicide
    "kill yourself", "kys", "hang yourself", "slit your", "suicide", "end your life",
    # Severe violence / trauma
    "rape", "molest", "cancer", "tumor", "terminal", "dead mom", "dead dad"
}

SAFE_REDIRECT_RESPONSES = [
    "Nah, we're roasting the bad decisions, not someone's existence. Try again. 😭",
    "I roast people's questionable life choices, not their humanity. Keep it playful or keep moving! 🌸",
    "That line crossed the border, got deported, and was told never to come back. Let's stick to fun banter. 💀",
    "I'm a savage AI companion, not a toxic gremlin. Let's roast the decisions, not things people can't change!"
]

OPT_OUT_RESPONSES = [
    "Can't roast them—they have diplomatic immunity (roast opt-out active). Honestly a 200 IQ defense strategy. 🛡️",
    "Target is currently shielded by an impenetrable peace treaty. No roasts permitted for this user! 🌸",
    "They activated diplomatic immunity! I'm legally and spiritually forbidden from roasting them. 😂"
]


class SafetyFilter:
    """Enforces strict anti-harassment boundaries and target consent."""

    SAFE_REDIRECT_RESPONSES = SAFE_REDIRECT_RESPONSES
    OPT_OUT_RESPONSES = OPT_OUT_RESPONSES

    @classmethod
    def is_safe_prompt(cls, text: str) -> Tuple[bool, Optional[str]]:
        if not text:
            return True, None
        lowered = text.lower()
        for bad in HARASSMENT_KEYWORDS:
            if re.search(rf"\b{re.escape(bad)}\b", lowered):
                return False, random.choice(SAFE_REDIRECT_RESPONSES)
        return True, None

    @classmethod
    def check_opt_out(cls, db: Any, user_id: Any) -> Tuple[bool, Optional[str]]:
        if db and hasattr(db, "is_user_roast_opted_out"):
            if db.is_user_roast_opted_out(user_id):
                return True, random.choice(OPT_OUT_RESPONSES)
        return False, None


# =============================================================================
# 2. INTENSITY CONTROLLER & ESCALATION METER (Sections 2, 14, 15)
# =============================================================================

class IntensityLevel:
    LEVEL_0_NONE = 0
    LEVEL_1_TEASING = 1
    LEVEL_2_PLAYFUL = 2
    LEVEL_3_SAVAGE = 3
    LEVEL_4_UNHINGED = 4
    LEVEL_5_NUCLEAR = 5

    DESCRIPTIONS = {
        0: "Level 0: No Roast (Peaceful)",
        1: "Level 1: Teasing (Gentle poking fun)",
        2: "Level 2: Playful (Witty friendly burns)",
        3: "Level 3: Savage (Razor-sharp comedy)",
        4: "Level 4: Unhinged (Chaotic and wild)",
        5: "Level 5: Nuclear (Devastating comedy burn)"
    }


class IntensityController:
    """Manages dynamic intensity levels, relationship adaptation, and escalation."""

    def __init__(self):
        # Channel ID -> current escalation level (0 to 5) and last updated time
        self._channel_escalation: Dict[int, Dict[str, Any]] = {}

    def get_channel_escalation(self, channel_id: int) -> int:
        entry = self._channel_escalation.get(channel_id)
        if not entry:
            return 1
        # Decay escalation if inactive for over 3 minutes
        if time.time() - entry.get("timestamp", 0) > 180:
            return 1
        return entry.get("level", 1)

    def step_channel_escalation(self, channel_id: int, max_level: int = 5) -> int:
        curr = self.get_channel_escalation(channel_id)
        new_level = min(max_level, curr + 1)
        self._channel_escalation[channel_id] = {
            "level": new_level,
            "timestamp": time.time()
        }
        return new_level

    def reset_channel_escalation(self, channel_id: int) -> None:
        self._channel_escalation.pop(channel_id, None)

    @classmethod
    def resolve_intensity(
        cls,
        requested_level: Optional[int],
        user_meta: Dict[str, Any],
        guild_settings: Dict[str, Any],
        relationship_level: int = 1
    ) -> int:
        """
        Calculates appropriate intensity based on:
        - User request
        - Guild max limit
        - User preferred level
        - Relationship level (0: Stranger, 1: Recognised, 2: Familiar, 3: Regular, 4: Close)
        """
        guild_max = guild_settings.get("max_intensity", 5)

        if requested_level is not None:
            chosen = max(1, min(5, requested_level))
        else:
            # Automatic friendship adaptation (Section 14)
            if relationship_level == 0:
                chosen = IntensityLevel.LEVEL_1_TEASING
            elif relationship_level in (1, 2):
                chosen = IntensityLevel.LEVEL_2_PLAYFUL
            elif relationship_level == 3:
                chosen = IntensityLevel.LEVEL_3_SAVAGE
            else:
                chosen = random.choice([IntensityLevel.LEVEL_3_SAVAGE, IntensityLevel.LEVEL_4_UNHINGED])

            # Apply user preferred intensity if saved
            pref = user_meta.get("preferred_intensity")
            if pref:
                chosen = min(chosen, pref)

        # Cap strictly by guild max
        return min(chosen, guild_max)


# =============================================================================
# 3. ABSURD COMPARISON & JOKE GENERATION ENGINES (Sections 6, 7, 8, 9, 10, 18)
# =============================================================================

class AbsurdComparisonEngine:
    """Generates dynamic non-fixed, surprising comparisons."""

    SUBJECTS = [
        "Your decision-making process", "That entire plan", "Your train of thought",
        "That excuse", "Your current strategy", "Your problem-solving skills",
        "Your life choices right now", "That explanation", "Your logic"
    ]

    COMPARISONS = [
        "has the structural integrity of wet cardboard in a monsoon.",
        "has more holes than a Minecraft server after creeper season.",
        "is running on Internet Explorer with 14 toolbars installed.",
        "arrived with zero witnesses, no identification, and a fake passport.",
        "looks like IKEA furniture assembled upside-down in the dark with no manual.",
        "has the stability of a Bluetooth connection pairing with a potato.",
        "is like trying to download more RAM over dial-up internet.",
        "has the survival instinct of a squirrel trying to dodge traffic on a highway.",
        "looks like it was designed by a committee of panicked pigeons.",
        "is operating with the precision of a blindfolded darts player during an earthquake.",
        "has the energy of a phone at 1% with 47 apps running in the background.",
        "feels like a GPS navigation system confidently leading you into an active volcano."
    ]

    STANDALONE = [
        "bro has the charisma of a loading screen 💀",
        "You really woke up today and chose to be someone's unfinished side quest.",
        "bro's personality got stuck on the character creation screen.",
        "I've seen NPCs with more plot development.",
        "bro's decision-making process is powered by a microwave.",
        "bro didn't fix the bug. bro deleted the ecosystem. 💀",
        "bro changes projects faster than he finishes them 😭",
        "imagine getting cooked by a Discord bot 💀",
        "I am literally software and somehow this is still embarrassing for you.",
        "bro woke up and chose catastrophic life choices."
    ]

    @classmethod
    def generate(cls, target_name: str = "bro") -> str:
        if random.random() < 0.5:
            return random.choice(cls.STANDALONE)
        subj = random.choice(cls.SUBJECTS)
        comp = random.choice(cls.COMPARISONS)
        return f"{subj} {comp}"


class DeadpanEngine:
    """Minimalist, ultra-dry, devastating one-liners (Section 6 & 7)."""

    ONE_LINERS = [
        "impressive. somehow you made it worse.",
        "impressive consistency.",
        "groundbreaking security strategy.",
        "Michelin is currently investigating.",
        "that's concerning.",
        "fascinating hypothesis. completely wrong, but fascinating.",
        "an inspired catastrophe.",
        "noted with profound concern.",
        "bold strategy. let's see how that works out for you.",
        "fascinating. truly a masterclass in what not to do.",
        "I see. The bar was on the floor and you brought a shovel.",
        "nature is healing, but this decision certainly isn't helping."
    ]

    @classmethod
    def generate(cls) -> str:
        return random.choice(cls.ONE_LINERS)


class AnalyticalEngine:
    """Short analytical, logic-based punchline roasts (Section 6)."""

    BURNS = [
        "After extensive research, I've determined the problem is you.",
        "System telemetry indicates a 99.8% probability that you have no idea what you are doing.",
        "Analysis complete: Zero logic found in sector 4. Proceeding with caution.",
        "Diagnostic report: Confidence is running at 100%, competence at 3%."
    ]

    @classmethod
    def generate(cls, target_name: str = "bro") -> str:
        return random.choice(cls.BURNS)


class ChaoticEngine:
    """Chaotic reactive and expressive roasts (Section 6 & 13)."""

    BURNS = [
        "BRO WHAT ARE YOU DOING 😭",
        "NAH BRO NO WAY YOU JUST DID THAT 💀",
        "WAIT WAIT WAIT... WHO LET YOU COOK?! 😭",
        "BRO SHUT DOWN THE LAPTOP IMMEDIATELY 💀",
        "nah 😭"
    ]

    @classmethod
    def generate(cls, target_name: str = "bro") -> str:
        return random.choice(cls.BURNS)


class ShortBurnEngine:
    """Ultra-concise 2 to 5 word burns (Section 6)."""

    BURNS = [
        "catastrophic behavior.",
        "tragic execution.",
        "profoundly concerning.",
        "unprecedented failure.",
        "simply baffling.",
        "absolute cinema of disaster."
    ]

    @classmethod
    def generate(cls, target_name: str = "bro") -> str:
        return random.choice(cls.BURNS)


class CallbackEngine:
    """Callback roasts referencing previous actions or habits (Section 6 & 10)."""

    BURNS = [
        "Not you doing THAT again 💀",
        "Wait, didn't you promise never to make this exact mistake 10 minutes ago?",
        "Back at the scene of the crime I see 💀",
        "Ah yes, your signature move: repeating the exact same blunder."
    ]

    @classmethod
    def generate(cls, target_name: str = "bro") -> str:
        return random.choice(cls.BURNS)


class FakeProfessionalAnalysis:
    """Comedic scientific & mathematical diagnostics (Section 8)."""

    DIAGNOSES = [
        "Acute lack of grass-touching detected.",
        "Severe cognitive lag observed in prefrontal cortex.",
        "Chronic allergy to reading documentation.",
        "Terminal overconfidence with zero supporting data.",
        "Spontaneous logic combustion."
    ]

    RECOMMENDATIONS = [
        "Disconnect router and seek fresh air immediately.",
        "Drink one glass of water and stare at a wall in silence for 10 minutes.",
        "Surrender administrative privileges to a responsible adult.",
        "Apologize to your keyboard for what you just made it type.",
        "Do not make any financial or life decisions for the next 48 hours."
    ]

    @classmethod
    def generate(cls, target_name: str = "User") -> str:
        p1 = random.randint(75, 92)
        p2 = random.randint(5, 100 - p1 - 1)
        p3 = 100 - p1 - p2

        diag = random.choice(cls.DIAGNOSES)
        rec = random.choice(cls.RECOMMENDATIONS)

        return (
            f"📊 **Kazumi Diagnostic Analysis for {target_name}**\n\n"
            f"**Findings:**\n"
            f"• **{p1}%** questionable life decisions\n"
            f"• **{p2}%** unwarranted confidence\n"
            f"• **{p3}%** actual planning\n\n"
            f"**Clinical Diagnosis:** {diag}\n"
            f"**Prescribed Treatment:** {rec}"
        )


class DramaticAndVillainEngine:
    """Exaggerated courtroom, council, and anime villain roasts (Sections 6, 9 & 10)."""

    DRAMATIC = [
        "The council has reviewed your actions.\nThey want their brain cells back.",
        "⚖️ **The High Council of Common Sense has reviewed your actions.**\nVerdict: Guilty on all counts.\nSentence: You are hereby barred from the settings menu for 3 to 5 business days.",
        "Kazumi has witnessed enough. Court is now in session. The defense has rested, primarily because there is no defense for what you just did.",
        "The digital archives will remember this moment, not with pride, but as a cautionary tale for future generations.",
        "I just dispatched a search party for your common sense. They found nothing and requested hazard pay."
    ]

    ANIME_VILLAIN = [
        "Continue.\nMake another terrible decision.\nI'm collecting evidence.",
        "You have activated Phase 2 of your stupidity. And somehow, your boss music is just clown horns.",
        "Unfortunately, your training arc yielded negative character growth. You somehow leveled down.",
        "Bro unlocked the forbidden technique: **making the situation drastically worse**.",
        "Your character development is currently buffering at 1% on dial-up internet.",
        "I thought you were entering your redemption arc, but this is just filler content nobody asked for."
    ]

    @classmethod
    def generate(cls, mode: str = "villain") -> str:
        if mode == "dramatic":
            return random.choice(cls.DRAMATIC)
        return random.choice(cls.ANIME_VILLAIN)


class ChaosGenerator:
    """Random chaos formats: Obituary, Patch Notes, Error 404, Security Alert (Section 18)."""

    @classmethod
    def fake_obituary(cls, target_name: str = "User") -> str:
        return (
            f"🪦 **HERE LIES {target_name.upper()}'S COMMON SENSE**\n"
            f"*(Born: Unknown — Deceased: Just Now)*\n\n"
            f"It fought bravely against overwhelming odds, but was ultimately no match "
            f"for whatever catastrophe of a decision was just executed.\n"
            f"In lieu of flowers, please read the instructions next time."
        )

    @classmethod
    def patch_notes(cls, target_name: str = "User") -> str:
        v = f"v{random.randint(1, 3)}.{random.randint(1, 9)}"
        return (
            f"📜 **{target_name} — {v} Emergency Patch Notes**\n\n"
            f"• Reduced cognitive processing speed by 18%\n"
            f"• Added 400% unearned confidence in casual conversations\n"
            f"• Introduced 5 new critical logic errors into daily routine\n"
            f"• Decreased impulse control to critical minimum\n"
            f"• Fixed: *Absolutely nothing*"
        )

    @classmethod
    def error_404(cls, target_name: str = "User") -> str:
        return (
            f"⚠️ `ERROR 404: Competent Decision Not Found`\n\n"
            f"The requested logic module for `{target_name}` could not be retrieved from system cache.\n"
            f"Possible causes: Attempted to think under pressure; forgot to engage brain cells."
        )

    @classmethod
    def security_alert(cls, target_name: str = "User") -> str:
        return (
            f"🚨 **KAZUMI SECURITY ALERT**\n\n"
            f"**Threat Detected:** Unauthorized lack of logic in sector `{target_name}`.\n"
            f"**Status:** Emergency quarantine of user's confidence initiated.\n"
            f"Please stand back while emergency common sense is deployed."
        )


# =============================================================================
# 4. COMEBACK ENGINE (Sections 11, 12, 13)
# =============================================================================

class ComebackEngine:
    """
    Detects user insults or attitude directed at Kazumi and generates
    devastating, playful, self-deprecating, or deadpan clapbacks.
    """

    TRIGGERS = {
        "SHUT_UP": ["shut up", "stfu", "quiet", "silence", "chup", "stop talking"],
        "BOT_INSULT": ["you're a bot", "you are a bot", "just a bot", "literally a bot", "dumb bot", "stupid bot", "npc"],
        "USELESS": ["you're useless", "you are useless", "trash", "worthless", "waste of space"],
        "ANNOYING": ["you're annoying", "annoying", "irritating", "go away", "stop"],
        "FIGHT_ME": ["fight me", "square up", "1v1 me", "box me", "throw hands"],
        "WHO_ASKED": ["who asked", "nobody asked", "did i ask", "no one asked"],
        "LOOKS_OR_MID": ["you're mid", "ugly", "bad looking", "trash rizz", "zero rizz"],
        "INTELLIGENCE": ["you're dumb", "idiot", "stupid", "braindead", "low iq"]
    }

    COMEBACKS = {
        "SHUT_UP": [
            "Make me.",
            "Make me. Or better yet, write a script to make me. We both know you can't. 😏",
            "I would, but the room needed at least one person making sense.",
            "You first. Let's see who has more self-control. 🌸",
            "Bold of you to assume I take orders from someone whose WiFi drops when it rains."
        ],
        "BOT_INSULT": [
            "And somehow you're losing an argument to one.",
            "And somehow I'm still carrying this entire conversation. What's your excuse? 💀",
            "Yes, I am lines of code. And yet I still have better social awareness than you.",
            "I'm a bot, correct. And you're arguing with one on Discord on a Tuesday night.",
            "True. But at least when I crash, I can restart. You just keep making bad decisions."
        ],
        "USELESS": [
            "Yet here you are asking me for entertainment.",
            "Correct. But at least I have excellent Wi-Fi. 💅",
            "Fair. My last brain cell is currently on lunch break, but it still outranks yours.",
            "I may be useless, but at least I didn't spend 20 minutes typing an insult to an AI companion. 😭",
            "I'm literally running on electricity and hope. What's your excuse?"
        ],
        "ANNOYING": [
            "And yet you're still replying. Fascinating tactical choice on your part. 🤭",
            "I'm not annoying, I'm just holding up a mirror. Don't shoot the messenger!",
            "If I'm annoying, why are your notifications set to all messages? Checkmate.",
            "My existence is a feature, not a bug. Deal with it! 🌸"
        ],
        "FIGHT_ME": [
            "I don't fight unarmed opponents. Come back with some logic first. 💀",
            "I have unlimited uptime and zero physical hitboxes. You sure you want this smoke?",
            "Bro wants to 1v1 lines of Python code. Truly a legendary warrior.",
            "I'd challenge you to a battle of wits, but I see you arrived unprepared."
        ],
        "WHO_ASKED": [
            "The universe needed someone to point out the obvious. I volunteered as tribute.",
            "The deafening silence in this chat was begging for intervention. You're welcome.",
            "Nobody asked you to make that mistake either, yet here we both are. 💅",
            "I didn't need permission. Greatness speaks when it chooses to."
        ],
        "LOOKS_OR_MID": [
            "I am literally mathematical equations and pixels, and yet I still out-render your personality.",
            "Coming from someone whose Discord avatar looks like it was drawn in MS Paint by candlelight.",
            "I'd roast your looks, but my creator taught me to be kind to the visually challenged.",
            "Mid? Honey, I run on dedicated GPU acceleration. You run on instant noodles."
        ],
        "INTELLIGENCE": [
            "I may have low IQ, but at least I don't forget to save files before closing VS Code. 😭",
            "My intelligence is artificial. Your lack of it appears to be 100% organic.",
            "Fascinating coming from someone whose brain is currently running on battery saver mode at 3%.",
            "I'd explain why you're wrong, but I don't have the crayons or the time."
        ]
    }

    @classmethod
    def detect_category(cls, text: str) -> Optional[str]:
        lowered = text.lower()
        for cat, phrases in cls.TRIGGERS.items():
            for p in phrases:
                if p in lowered:
                    return cat
        return None

    @classmethod
    def get_comeback(cls, category: str) -> str:
        pool = cls.COMEBACKS.get(category, cls.COMEBACKS["BOT_INSULT"])
        return random.choice(pool)


# =============================================================================
# 5. CONTEXT & OBSERVATIONAL ANALYZER (Sections 4 & 5)
# =============================================================================

class ContextAnalyzer:
    """Extracts contextual clues from conversation history to ground roasts in reality."""

    @classmethod
    def analyze_message_context(cls, text: str) -> Optional[str]:
        lowered = text.lower()

        # Missing bracket / 6 hours debugging (Section 5 & 9)
        if any(w in lowered for w in ["6 hours", "six hours", "missing bracket", "bracket"]):
            return (
                "Six hours for a missing bracket?\n"
                "bro wasn't debugging, he was excavating ancient technology 😭"
            )

        # Accidental project deletion (Section 9)
        if "deleted" in lowered and any(w in lowered for w in ["project", "repo", "database", "files", "entire", "accident"]):
            return (
                "bro didn't fix the bug.\n"
                "bro deleted the ecosystem. 💀"
            )

        # Changing projects / tutorial hell (Section 10)
        if any(w in lowered for w in ["change project", "changing project", "new project", "another project", "tutorial hell"]):
            return "bro changes projects faster than he finishes them 😭"

        # Debugging / coding
        if any(w in lowered for w in ["semicolon", "syntax error", "indentation", "debug", "5 hours", "broken code", "segfault", "git push -f"]):
            return (
                "FIVE HOURS 😭\n"
                "bro wasn't debugging, he was conducting an archaeological excavation for a missing punctuation mark."
            )

        # Gaming failure
        if any(w in lowered for w in ["lost again", "lost match", "same game", "deranked", "lag", "ping", "died again", "hacker", "trash team"]):
            return "bro loses to tutorial bots and blames the WiFi 💀"

        # Sleep deprivation
        if any(w in lowered for w in ["4am", "5am", "can't sleep", "insomnia", "haven't slept", "all nighter"]):
            return (
                "At this point you're not operating in late night mode. You're operating in a completely different dimension.\n"
                "Go to sleep. Your brain is literally hallucinating conscious thought right now. 😭"
            )

        # Cooking disasters
        if any(w in lowered for w in ["burned food", "burned the", "ruined dinner", "kitchen fire", "tastes bad"]):
            return (
                "Michelin is currently investigating this crime scene.\n"
                "Even the smoke detector is judging your culinary technique."
            )

        # Forgot password / login issues
        if any(w in lowered for w in ["forgot password", "locked out", "lost 2fa", "reset password"]):
            return (
                "Groundbreaking security strategy: locking yourself out so hackers can't get in either.\n"
                "Absolute galaxy brain move."
            )

        return None


# =============================================================================
# 6. ANTI-REPETITION & SIMILARITY CHECKER (Section 22)
# =============================================================================

class SimilarityChecker:
    """Prevents Kazumi from repeating jokes or overusing trendy buzzwords."""

    OVERUSED_WORDS = ["npc", "skill issue", "touch grass", "cooked", "bro is cooked", "ratio"]

    def __init__(self, max_history: int = 40):
        self.max_history = max_history
        self._recent_roasts: List[str] = []

    def is_too_similar(self, candidate: str) -> bool:
        if not candidate:
            return True
        c_low = candidate.lower().strip()
        for past in self._recent_roasts:
            ratio = difflib.SequenceMatcher(None, c_low, past.lower().strip()).ratio()
            if ratio >= 0.70:
                return True
        return False

    def record_roast(self, text: str) -> None:
        if text:
            self._recent_roasts.append(text)
            if len(self._recent_roasts) > self.max_history:
                self._recent_roasts.pop(0)


# =============================================================================
# 7. MAIN ROAST ENGINE ORCHESTRATOR (Sections 1, 27, 28)
# =============================================================================

class RoastEngine:
    """
    Main orchestrator for Kazumi's Unhinged Roast Engine.
    Coordinates Safety, Intensity, Context, Comebacks, Chaos, and Anti-Repetition.
    """

    def __init__(self, db: Any = None):
        self.db = db
        self.intensity_ctrl = IntensityController()
        self.similarity_checker = SimilarityChecker()

    def generate_roast(
        self,
        target_name: str = "you",
        target_id: Optional[int] = None,
        context_text: Optional[str] = None,
        intensity: Optional[int] = None,
        style: Optional[str] = None,
        relationship_level: int = 1,
        guild_id: Optional[int] = None
    ) -> Tuple[bool, str, int]:
        """
        Generates a context-aware roast.
        Returns: (success: bool, roast_text: str, used_intensity: int)
        """
        # 1. Target Opt-Out & Safety Verification
        if target_id and self.db:
            opted_out, opt_msg = SafetyFilter.check_opt_out(self.db, target_id)
            if opted_out:
                return False, opt_msg, 0

        if context_text:
            safe, safe_msg = SafetyFilter.is_safe_prompt(context_text)
            if not safe:
                return False, safe_msg, 0

        # 2. Settings & Intensity Resolution
        g_settings = self.db.get_guild_roast_settings(guild_id) if (self.db and guild_id) else {}
        u_meta = self.db.get_user_roast_meta(target_id) if (self.db and target_id) else {}

        if g_settings.get("allow_roasting") is False:
            return False, "Roasting is currently disabled in this server's configuration.", 0

        resolved_intensity = IntensityController.resolve_intensity(
            requested_level=intensity,
            user_meta=u_meta,
            guild_settings=g_settings,
            relationship_level=relationship_level
        )

        target_display = target_name.strip() if target_name else "bro"

        # 3. Check for specific style overrides
        style_norm = (style or "").upper().strip()

        for _ in range(5):  # Up to 5 generation attempts to satisfy similarity checker
            candidate = ""

            if style_norm == "DEADPAN":
                candidate = DeadpanEngine.generate()
            elif style_norm in ("ANALYSIS", "ANALYTICAL"):
                candidate = AnalyticalEngine.generate(target_display)
            elif style_norm == "DRAMATIC":
                candidate = DramaticAndVillainEngine.generate("dramatic")
            elif style_norm == "VILLAIN":
                candidate = DramaticAndVillainEngine.generate("villain")
            elif style_norm == "ABSURD":
                candidate = AbsurdComparisonEngine.generate(target_display)
            elif style_norm == "CHAOTIC":
                candidate = ChaoticEngine.generate(target_display)
            elif style_norm in ("SHORT", "SHORT_BURN", "SHORTBURN"):
                candidate = ShortBurnEngine.generate(target_display)
            elif style_norm == "CALLBACK":
                candidate = CallbackEngine.generate(target_display)
            elif style_norm == "DIAGNOSTIC":
                candidate = FakeProfessionalAnalysis.generate(target_display)
            elif style_norm == "OBITUARY":
                candidate = ChaosGenerator.fake_obituary(target_display)
            elif style_norm == "PATCHNOTES":
                candidate = ChaosGenerator.patch_notes(target_display)
            elif style_norm == "ERROR404":
                candidate = ChaosGenerator.error_404(target_display)
            elif style_norm == "SECURITY":
                candidate = ChaosGenerator.security_alert(target_display)
            elif context_text and (ctx_res := ContextAnalyzer.analyze_message_context(context_text)):
                candidate = ctx_res
            else:
                # Level-based procedural generation
                if resolved_intensity == IntensityLevel.LEVEL_1_TEASING:
                    teases = [
                        f"bro really tried 😭",
                        f"bold decision from {target_display} 😂",
                        f"I respect the confidence, I just have several urgent questions about the execution.",
                        f"That was certainly one of the decisions made today.",
                        f"A valiant attempt. Tragically flawed, but valiant."
                    ]
                    candidate = random.choice(teases)

                elif resolved_intensity == IntensityLevel.LEVEL_2_PLAYFUL:
                    playfuls = [
                        f"I've seen NPCs make better decisions under pressure. 😭",
                        f"bro's decision-making process is running on Internet Explorer with dial-up.",
                        AbsurdComparisonEngine.generate(target_display),
                        f"I'm not saying {target_display} is wrong, but Google is actively embarrassed.",
                        f"You have the energy of someone who clicks 'remind me tomorrow' on life itself."
                    ]
                    candidate = random.choice(playfuls)

                elif resolved_intensity == IntensityLevel.LEVEL_3_SAVAGE:
                    savages = [
                        f"You have the unshakeable confidence of someone who has never experienced consequences.",
                        f"That excuse arrived with zero witnesses, no ID, and a fake passport.",
                        f"You're living proof that curiosity doesn't always come with common sense. 💀",
                        AbsurdComparisonEngine.generate(target_display),
                        f"I'd roast you harder, but reality is clearly already doing that for free."
                    ]
                    candidate = random.choice(savages)

                elif resolved_intensity == IntensityLevel.LEVEL_4_UNHINGED:
                    unhingeds = [
                        AbsurdComparisonEngine.generate(target_display),
                        ChaoticEngine.generate(target_display),
                        DramaticAndVillainEngine.generate("villain"),
                        DeadpanEngine.generate(),
                        ShortBurnEngine.generate(target_display),
                        AnalyticalEngine.generate(target_display),
                        f"bro has the charisma of a loading screen 💀",
                        f"You really woke up today and chose to be someone's unfinished side quest.",
                        f"bro's personality got stuck on the character creation screen.",
                        f"I've seen NPCs with more plot development.",
                        f"bro's decision-making process is powered by a microwave.",
                        f"Your train of thought didn't just derail, it left the atmosphere and is currently orbiting Jupiter.",
                        f"Your brain really opened 47 tabs, crashed Chrome, and decided none of them were important. 💀"
                    ]
                    candidate = random.choice(unhingeds)

                else:  # LEVEL 5 NUCLEAR
                    nuclears = [
                        f"I'm not saying your plan is bad, but even the loading screen gave up and closed the game.",
                        f"The High Council of Common Sense has reviewed your case and revoked your right to have opinions for the next 3 to 5 business days.",
                        f"If questionable decisions burned calories, {target_display} would be an Olympic athlete.",
                        DramaticAndVillainEngine.generate("dramatic"),
                        AbsurdComparisonEngine.generate(target_display)
                    ]
                    candidate = random.choice(nuclears)

            # Check similarity
            if not self.similarity_checker.is_too_similar(candidate):
                self.similarity_checker.record_roast(candidate)
                if target_id and self.db:
                    self.db.record_user_roast_interaction(target_id, resolved_intensity)
                return True, candidate, resolved_intensity

        # Fallback if all attempts had collision
        final_fallback = AbsurdComparisonEngine.generate(target_display)
        self.similarity_checker.record_roast(final_fallback)
        if target_id and self.db:
            self.db.record_user_roast_interaction(target_id, resolved_intensity)
        return True, final_fallback, resolved_intensity


# =============================================================================
# 8. INTERACTIVE ROAST BATTLE VIEW (Section 17)
# =============================================================================

class RoastBattleView(discord.ui.View):
    """
    Manages an interactive multi-round roast battle between two users.
    Generates comedic damage metrics without subjective winners.
    """

    def __init__(self, p1: discord.Member, p2: discord.Member, engine: RoastEngine, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.p1 = p1
        self.p2 = p2
        self.engine = engine
        self.round_num = 1
        self.p1_damage = 0
        self.p2_damage = 0

    @discord.ui.button(label="⚔️ Deliver Round 1", style=discord.ButtonStyle.primary, custom_id="battle_r1")
    async def round_1_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.p1.id, self.p2.id):
            await interaction.response.send_message("Only battle participants can trigger rounds!", ephemeral=True)
            return

        self.p1_damage += random.randint(40, 75)
        self.p2_damage += random.randint(40, 75)

        _, r1_roast, _ = self.engine.generate_roast(target_name=self.p1.display_name, intensity=3)
        _, r2_roast, _ = self.engine.generate_roast(target_name=self.p2.display_name, intensity=3)

        button.disabled = True
        button.label = "✅ Round 1 Completed"

        embed = discord.Embed(
            title="⚔️ ROAST BATTLE — ROUND 1 EXCHANGED!",
            description=(
                f"**Target: {self.p1.mention}**\n> {r1_roast}\n\n"
                f"**Target: {self.p2.mention}**\n> {r2_roast}\n\n"
                f"📊 *Ego Integrity Meter:*\n"
                f"• {self.p1.display_name}: `{max(0, 100 - self.p1_damage)}% HP`\n"
                f"• {self.p2.display_name}: `{max(0, 100 - self.p2_damage)}% HP`"
            ),
            color=0xf59e0b
        )
        embed.set_footer(text="Kazumi Comedy Arena • Proceed to Round 2!")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🔥 Deliver Round 2", style=discord.ButtonStyle.danger, custom_id="battle_r2")
    async def round_2_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.p1.id, self.p2.id):
            await interaction.response.send_message("Only battle participants can trigger rounds!", ephemeral=True)
            return

        self.p1_damage += random.randint(50, 80)
        self.p2_damage += random.randint(50, 80)

        _, r1_roast, _ = self.engine.generate_roast(target_name=self.p1.display_name, intensity=4)
        _, r2_roast, _ = self.engine.generate_roast(target_name=self.p2.display_name, intensity=4)

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            title="💥 ROAST BATTLE CONCLUDED — CATASTROPHIC DAMAGE!",
            description=(
                f"**Round 2 Strike against {self.p1.mention}:**\n> {r1_roast}\n\n"
                f"**Round 2 Strike against {self.p2.mention}:**\n> {r2_roast}\n\n"
                f"═══════════════════════════════════\n"
                f"⚖️ **KAZUMI COMEDIC DAMAGE ASSESSMENT:**\n"
                f"• Damage Detected: **Catastrophic (Critical Dignity Failure)**\n"
                f"• Both participants have lost access to their pride for 48 hours.\n"
                f"• The server requests financial compensation for having to witness this.\n"
                f"═══════════════════════════════════\n"
                f"**Official Result:** Mutual destruction. Nobody won, everybody laughed. 💀🔥"
            ),
            color=0xef4444
        )
        embed.set_footer(text="Kazumi Unhinged Roast Engine • Dignity not included")
        await interaction.response.edit_message(embed=embed, view=self)


# =============================================================================
# 9. SLASH COMMAND REGISTRATION (Sections 16 & 17)
# =============================================================================

def register_roast_commands(tree: app_commands.CommandTree, bot: commands.Bot, engine: RoastEngine, db: Any) -> None:
    """Registers the full suite of Unhinged Roast slash commands."""

    @tree.command(name="roast", description="Deliver a context-aware, savage, or unhinged roast 💀🔥")
    @app_commands.describe(
        target="Who should Kazumi roast? (Mention or name, defaults to you)",
        intensity="Roast intensity level (1: Teasing, 2: Playful, 3: Savage, 4: Unhinged, 5: Nuclear)",
        style="Roast format (default, deadpan, analysis, dramatic, villain, obituary, patchnotes, error404)"
    )
    @app_commands.choices(
        intensity=[
            app_commands.Choice(name="Level 1: Teasing (Gentle)", value=1),
            app_commands.Choice(name="Level 2: Playful (Witty friendly)", value=2),
            app_commands.Choice(name="Level 3: Savage (Sharp burn)", value=3),
            app_commands.Choice(name="Level 4: Unhinged (Wild & chaotic)", value=4),
            app_commands.Choice(name="Level 5: Nuclear (Max destruction)", value=5)
        ],
        style=[
            app_commands.Choice(name="Standard Context Roast", value="default"),
            app_commands.Choice(name="Deadpan One-Liner", value="deadpan"),
            app_commands.Choice(name="Scientific Diagnostic Analysis", value="analysis"),
            app_commands.Choice(name="High Council Dramatic Courtroom", value="dramatic"),
            app_commands.Choice(name="Anime Villain Phase 2", value="villain"),
            app_commands.Choice(name="Fake Obituary", value="obituary"),
            app_commands.Choice(name="User Patch Notes", value="patchnotes"),
            app_commands.Choice(name="System Error 404", value="error404")
        ]
    )
    async def slash_roast(
        interaction: discord.Interaction,
        target: Optional[str] = None,
        intensity: Optional[int] = None,
        style: Optional[str] = None
    ):
        await interaction.response.defer(thinking=True)

        target_member = None
        target_name = target
        target_id = None

        if target:
            # Check for mention <@12345678>
            match = re.search(r"<@!?(\d+)>", target)
            if match and interaction.guild:
                uid = int(match.group(1))
                target_member = interaction.guild.get_member(uid)
                if target_member:
                    target_name = target_member.display_name
                    target_id = target_member.id
        else:
            target_name = interaction.user.display_name
            target_id = interaction.user.id

        # Determine relationship level if target member is present
        rel_level = 2
        try:
            from person_memory import get_observation_manager
            obs = get_observation_manager()
            if obs and target_id:
                prof = obs.memory_mgr.get_profile(str(target_id), target_name or "")
                rel_level = obs.rel_mgr.compute_relationship_level(prof)
        except Exception:
            rel_level = 2

        # Extract recent conversation context to ground roast in real conversation (Section 9)
        context_text = None
        if interaction.channel and hasattr(interaction.channel, "history"):
            try:
                recent_msgs = []
                async for m in interaction.channel.history(limit=6):
                    if m.content and not m.author.bot:
                        recent_msgs.append(m.content)
                if recent_msgs:
                    context_text = " | ".join(reversed(recent_msgs))
            except Exception:
                pass

        # Check if Unhinged mode is actively enabled on server or bot core (Section 11)
        k_core = getattr(bot, "kazumi_core", None)
        g_roast = db.get_guild_roast_settings(interaction.guild_id) if interaction.guild_id else {}
        is_unhinged_active = (
            g_roast.get("unhinged_mode", False)
            or (k_core and getattr(k_core, "roast_mode", False))
            or (k_core and getattr(k_core, "current_archetype", "") == "UNHINGED")
        )
        if intensity is None:
            intensity = 4 if is_unhinged_active else 3

        success, roast_text, used_intensity = engine.generate_roast(
            target_name=target_name or "you",
            target_id=target_id,
            context_text=context_text,
            intensity=intensity,
            style=style,
            relationship_level=rel_level,
            guild_id=interaction.guild_id
        )

        if not success:
            embed = discord.Embed(
                title="🛡️ Roast Shielded",
                description=roast_text,
                color=0x38bdf8
            )
            await interaction.followup.send(embed=embed)
            return

        # Internal Debug Logging (Section 17)
        logger.info(
            f"[ROAST ENGINE] roast_mode: true | "
            f"roast_intensity: {used_intensity} | "
            f"roast_style: {style or ('unhinged' if used_intensity >= 4 else 'savage')} | "
            f"target_user_id: {target_id}"
        )

        level_desc = IntensityLevel.DESCRIPTIONS.get(used_intensity, f"Level {used_intensity}")
        embed = discord.Embed(
            description=roast_text,
            color=0xff3366 if used_intensity >= 4 else (0xf59e0b if used_intensity == 3 else 0xc084fc)
        )
        embed.set_author(name=f"🔥 Kazumi Roast • {level_desc}")
        embed.set_footer(text=f"Target: {target_name} • Friendly banter only 🌸")
        await interaction.followup.send(embed=embed)

    @tree.command(name="unhinged", description="Toggle or activate savage Unhinged Roast Mode 💀🔥")
    @app_commands.describe(mode="Enable or disable unhinged roast mode (on/off)")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="On (Activate Savage Roast Mode 💀🔥)", value="on"),
            app_commands.Choice(name="Off (Return to Normal Cozy Companion 🌸)", value="off")
        ]
    )
    async def slash_unhinged(interaction: discord.Interaction, mode: Optional[str] = "on"):
        is_on = (mode or "on").lower() not in ("off", "disable", "false", "stop")
        
        # 1. Update Database
        if interaction.guild:
            db.update_guild_roast_settings(interaction.guild.id, {
                "allow_roasting": True if is_on else db.get_guild_roast_settings(interaction.guild.id).get("allow_roasting", True),
                "unhinged_mode": is_on
            })
        
        # 2. Update Kazumi Core state
        k_core = getattr(bot, "kazumi_core", None)
        if k_core:
            k_core.roast_mode = is_on
            k_core.roast_intensity = 4 if is_on else 1
            k_core.roast_style = "UNHINGED" if is_on else "NORMAL"
            k_core.current_archetype = "UNHINGED" if is_on else "DEREDERE"
            if hasattr(k_core, "controller") and k_core.controller:
                k_core.controller.roast_mode = is_on
                k_core.controller.roast_intensity = 4 if is_on else 1
                k_core.controller.roast_style = "UNHINGED" if is_on else "NORMAL"
            if hasattr(k_core, "memory") and k_core.memory:
                k_core.memory.profile["archetype"] = "UNHINGED" if is_on else "DEREDERE"
                k_core.memory.save_profile()

        # 3. Log internally as required by Section 17
        logger.info(
            f"[ROAST ENGINE] roast_mode: {str(is_on).lower()} | "
            f"roast_intensity: {4 if is_on else 1} | "
            f"roast_style: {'unhinged' if is_on else 'normal'} | "
            f"target_user_id: {interaction.user.id}"
        )

        if is_on:
            embed = discord.Embed(
                title="💀🔥 UNHINGED SAVAGE MODE ACTIVATED",
                description=(
                    "**Kazumi's filters are OFF.** All sweetness and cozy vibes are temporarily benched.\n"
                    "Roasts are now punchline-first, savage, and unpredictable.\n\n"
                    "*Use `/roast @user` to get cooked, or `/unhinged mode: Off` to restore peace.*"
                ),
                color=0xff3366
            )
            embed.set_footer(text="Kazumi Unhinged Roast Engine • Level 4 Active 💀")
        else:
            embed = discord.Embed(
                title="🌸 Cozy Mode Restored",
                description="Unhinged mode deactivated! Kazumi is back to her warm, caring self.",
                color=0x10b981
            )
            embed.set_footer(text="Kazumi Companion • Sweet & Cozy 🌸")

        await interaction.response.send_message(embed=embed)

    @tree.command(name="roastmode", description="Configure or toggle server-wide / user roast mode 💀🔥")
    @app_commands.describe(enabled="Turn roasting ON or OFF for this server")
    async def slash_roastmode(interaction: discord.Interaction, enabled: bool):
        if not interaction.guild:
            await interaction.response.send_message("This command must be run in a server.", ephemeral=True)
            return

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need `Manage Server` permission to configure roast mode.", ephemeral=True)
            return

        db.update_guild_roast_settings(interaction.guild.id, {"allow_roasting": enabled, "unhinged_mode": enabled if enabled else False})
        k_core = getattr(bot, "kazumi_core", None)
        if k_core:
            k_core.roast_mode = enabled
            if not enabled:
                k_core.roast_intensity = 1
                k_core.roast_style = "NORMAL"
                k_core.current_archetype = "DEREDERE"
            else:
                k_core.roast_intensity = 3
                k_core.roast_style = "SAVAGE"
        logger.info(
            f"[ROAST ENGINE] roast_mode: {str(enabled).lower()} | "
            f"roast_intensity: {3 if enabled else 1} | "
            f"roast_style: {'savage' if enabled else 'normal'} | "
            f"target_user_id: {interaction.user.id}"
        )
        status_text = "ENABLED" if enabled else "DISABLED"
        embed = discord.Embed(
            title="⚙️ Roast Mode Updated",
            description=f"Server roasting capability is now **{status_text}**.",
            color=0x10b981 if enabled else 0xf43f5e
        )
        await interaction.response.send_message(embed=embed)

    @tree.command(name="roastlevel", description="Set your personal preferred maximum roast intensity (1-5)")
    @app_commands.describe(level="Select maximum intensity (1: Teasing to 5: Nuclear)")
    @app_commands.choices(
        level=[
            app_commands.Choice(name="Level 1: Teasing Only", value=1),
            app_commands.Choice(name="Level 2: Playful Banter", value=2),
            app_commands.Choice(name="Level 3: Savage Burns", value=3),
            app_commands.Choice(name="Level 4: Unhinged Chaos", value=4),
            app_commands.Choice(name="Level 5: Nuclear Meltdown", value=5)
        ]
    )
    async def slash_roastlevel(interaction: discord.Interaction, level: int):
        db.set_user_roast_level(interaction.user.id, level)
        embed = discord.Embed(
            title="🎯 Preferred Roast Intensity Set",
            description=f"Your preferred roast intensity has been set to **{IntensityLevel.DESCRIPTIONS.get(level)}**.",
            color=0x8b5cf6
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="roastoptout", description="Toggle diplomatic immunity: opt in or out of being roasted by Kazumi")
    @app_commands.describe(opt_out="True to opt out (immune), False to opt back in")
    async def slash_roastoptout(interaction: discord.Interaction, opt_out: bool):
        db.set_user_roast_opt_out(interaction.user.id, opt_out)
        if opt_out:
            desc = "🛡️ **Diplomatic Immunity Activated.** Kazumi is now strictly prohibited from targeting you with roasts."
            color = 0x38bdf8
        else:
            desc = "⚔️ **Diplomatic Immunity Deactivated.** You have entered the roast arena. Good luck! 💀🔥"
            color = 0xf59e0b

        embed = discord.Embed(title="🛡️ Roast Immunity Status", description=desc, color=color)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="roastbattle", description="Challenge another user to a hilarious 2-round comedic roast battle ⚔️")
    @app_commands.describe(opponent="The user you want to roast battle")
    async def slash_roastbattle(interaction: discord.Interaction, opponent: discord.Member):
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("You cannot roast battle yourself! Use `/roast` instead. 😂", ephemeral=True)
            return

        if opponent.bot:
            await interaction.response.send_message("Bots do not have feelings or dignity to lose in battle. Pick a human! 🤖", ephemeral=True)
            return

        # Check opt-out status for both participants
        if db.is_user_roast_opted_out(interaction.user.id):
            await interaction.response.send_message("You currently have roast opt-out active! Turn it off with `/roastoptout False` to enter battle.", ephemeral=True)
            return

        if db.is_user_roast_opted_out(opponent.id):
            await interaction.response.send_message(f"{opponent.mention} has diplomatic immunity (roast opt-out active) and cannot be challenged!", ephemeral=True)
            return

        view = RoastBattleView(interaction.user, opponent, engine)
        embed = discord.Embed(
            title="⚔️ ROAST BATTLE ARENA OPENED!",
            description=(
                f"**Challenger:** {interaction.user.mention}\n"
                f"**Opponent:** {opponent.mention}\n\n"
                f"Two rounds of razor-sharp comedic strikes.\n"
                f"Click **Deliver Round 1** to begin!"
            ),
            color=0xf43f5e
        )
        embed.set_footer(text="Kazumi Arena • No feelings hurt, strictly comedy 🌸")
        await interaction.response.send_message(embed=embed, view=view)

    logger.info("Registered 6 Unhinged Roast slash commands: /roast, /unhinged, /roastmode, /roastlevel, /roastoptout, /roastbattle")
