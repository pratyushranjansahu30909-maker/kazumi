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
        "bro has the conversational presence of a CAPTCHA code 💀",
        "You really woke up today and chose to be someone's unfinished side quest.",
        "bro's personality got stuck on the character creation screen.",
        "I've seen background characters with more character development.",
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
        "The council has reviewed your actions.\nThey have unanimously declined to acknowledge them.",
        "First you made the mistake. Then you doubled down. Then you explained it. That's not a mistake anymore, that's a development roadmap.",
        "Kazumi has witnessed enough. Court is now in session. The defense has rested, primarily because there is no defense for what you just did.",
        "The digital archives will remember this moment as a cautionary tale for future generations.",
        "The confidence was impressive. The results were not."
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
            f"🪦 **HERE LIES {target_name.upper()}'S DIGNITY**\n"
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
            f"Possible causes: Attempted to think under pressure; forgot to engage logic modules."
        )

    @classmethod
    def security_alert(cls, target_name: str = "User") -> str:
        return (
            f"🚨 **KAZUMI SECURITY ALERT**\n\n"
            f"**Threat Detected:** Unauthorized lack of logic in sector `{target_name}`.\n"
            f"**Status:** Emergency quarantine of user's confidence initiated.\n"
            f"Please stand back while emergency reality checks are deployed."
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
# =============================================================================
# 5. CONTEXT & OBSERVATIONAL INTELLIGENCE PIPELINE (Sections 1, 2, 3, 4, 10, 17)
# =============================================================================

class ComedyAngle:
    """Primary comedy angles (Section 4). One angle selected per roast."""
    ABSURDITY = "ABSURDITY"
    OVERCONFIDENCE = "OVERCONFIDENCE"
    IRONY = "IRONY"
    EXAGGERATION = "EXAGGERATION"
    CALLBACK = "CALLBACK"
    DEADPAN = "DEADPAN"
    WORDPLAY = "WORDPLAY"
    COMPARISON = "COMPARISON"
    REVERSAL = "REVERSAL"
    SARCASM = "SARCASM"
    MISSED_EXPECTATION = "MISSED_EXPECTATION"
    CHAOTIC = "CHAOTIC"


# Banned generic filler phrases with heavy repetition penalties (Section 13)
BANNED_GENERIC_FILLER = [
    "common sense",
    "search party",
    "hazard pay",
    "damp sock",
    "loading screen",
    "npc",
    "brain cells",
    "touch grass",
    "skill issue",
    "built different"
]

# Playful honest deflections when zero context is present (Section 3)
NO_CONTEXT_PLAYFUL_RESPONSES = [
    "Give me something to work with 😭",
    "You want a roast with zero evidence? Bold.",
    "Stand still for five minutes and I'm sure you'll provide material.",
    "I roast bad decisions, not innocent bystanders. Give me something to work with first!",
    "Zero context detected. Do something questionable and come back 💀"
]


class RoastObservation:
    """Encapsulates a concrete contextual finding and comedy angle."""
    def __init__(
        self,
        category: str,
        angle: str,
        summary: str,
        punchlines_by_level: Dict[int, str],
        confidence: float = 1.0
    ):
        self.category = category
        self.angle = angle
        self.summary = summary
        self.punchlines_by_level = punchlines_by_level
        self.confidence = confidence

    def get_punchline(self, level: int = 3, target_name: str = "bro") -> str:
        lvl = max(1, min(5, level))
        punch = self.punchlines_by_level.get(lvl)
        if not punch:
            available = sorted(self.punchlines_by_level.keys())
            closest = min(available, key=lambda x: abs(x - lvl))
            punch = self.punchlines_by_level[closest]
        return punch.replace("{target}", target_name)


class ContextAnalyzer:
    """
    Extracts contextual clues from conversation history, target messages, and memory.
    Implements Priority Pipeline (Section 17):
    1. Current message / target recent statements
    2. Surrounding conversation flow
    3. Recent interactions / time gap
    4. Known harmless behavior patterns (habits, projects)
    5. Previous funny callbacks
    """

    @classmethod
    def find_roastable_observation(
        cls,
        target_recent_messages: Optional[List[str]] = None,
        all_context_messages: Optional[List[str]] = None,
        target_patterns: Optional[List[str]] = None,
        time_away_seconds: Optional[float] = None,
        target_name: str = "bro"
    ) -> Optional[RoastObservation]:
        """Scans context for roastable observations according to Section 1 & 2."""
        raw_target_text = " ".join(target_recent_messages or []).lower().strip()
        all_text = " ".join(all_context_messages or []).lower().strip()
        combined_text = f"{raw_target_text} {all_text}".strip()
        patterns_lowered = [p.lower() for p in (target_patterns or [])]

        # 1. CODING SEQUEL (Section 5: fixed it, then broke again)
        if ("fix" in raw_target_text or "fixed" in raw_target_text) and any(b in raw_target_text for b in ["broke", "broken", "again", "sequel"]) and not any(h in raw_target_text for h in ["6 hours", "six hours", "5 hours", "five hours"]):
            return RoastObservation(
                category="CODING_SEQUEL",
                angle=ComedyAngle.REVERSAL,
                summary="Target fixed code but it immediately broke again",
                punchlines_by_level={
                    1: "You fixed it so well you created a sequel 😂",
                    2: "You fixed it so hard you created a sequel 💀",
                    3: "Bro didn't fix the bug. He gave it character development.",
                    4: "Bro really looked at a working build and said 'this lacks dramatic tension' 😭",
                    5: "Bro didn't fix the bug. He gave it character development, a tragic backstory, and a multi-season franchise deal 💀"
                }
            )

        # 2. CODING ARCHAEOLOGY (6 Hours / Bracket)
        if any(w in raw_target_text for w in ["6 hours", "six hours", "missing bracket", "bracket"]):
            return RoastObservation(
                category="CODING_ARCHAEOLOGY_6H",
                angle=ComedyAngle.EXAGGERATION,
                summary="Spending six hours looking for a single bracket",
                punchlines_by_level={
                    1: "All that time for a punctuation mark? bro really went on an expedition 😭",
                    2: "Six hours for a missing bracket?\nbro wasn't debugging, he was excavating ancient technology 😭",
                    3: "Five hours looking for a missing bracket when the compiler was screaming at line 4 the whole time.",
                    4: "Bro spent six hours conducting an archaeological dig just to find out he forgot to close a parenthesis 💀",
                    5: "Bro didn't debug the script. He performed a multi-hour spiritual pilgrimage for a single punctuation mark and still lost."
                }
            )

        # 3. CODING ARCHAEOLOGY (5 Hours / Semicolon / Debugging)
        if any(w in raw_target_text for w in ["semicolon", "syntax error", "indentation", "debug", "5 hours", "five hours", "broken code", "segfault", "git push -f", "missing comma"]):
            return RoastObservation(
                category="CODING_ARCHAEOLOGY_5H",
                angle=ComedyAngle.EXAGGERATION,
                summary="Spending five hours debugging a syntax error",
                punchlines_by_level={
                    1: "Five hours for syntax? bro really went on a journey 😭",
                    2: "FIVE HOURS 😭\nbro wasn't debugging, he was conducting an archaeological excavation for a missing punctuation mark.",
                    3: "Five hours looking for a missing semicolon when the linter told you where it was immediately.",
                    4: "Bro spent five hours on a single line of code just to discover he mistyped a punctuation mark 💀",
                    5: "Five hours conducting an excavation for a syntax error. A masterclass in weaponized stubbornness."
                }
            )

        # 3. ACCIDENTAL PROJECT DELETION / SCORCHED EARTH
        if "deleted" in raw_target_text and any(w in raw_target_text for w in ["project", "repo", "database", "files", "folder", "prod", "entire", "accident"]):
            return RoastObservation(
                category="CODING_DELETION",
                angle=ComedyAngle.ABSURDITY,
                summary="Accidental deletion of a codebase or database",
                punchlines_by_level={
                    1: "Accidentally wiped it? Character development incoming 😭",
                    2: "bro didn't fix the bug.\nbro deleted the ecosystem. 💀",
                    3: "Accidentally deleting the whole project is certainly one way to resolve the merge conflict.",
                    4: "Bro really solved the bug by eliminating the universe it lived in 💀",
                    5: "Bro achieved zero bugs by achieving zero files. A devastatingly efficient scorched-earth policy."
                }
            )

        # 4. GAMING LOSS STREAK & DONATIONS (Section 6)
        if any(w in raw_target_text for w in ["lost", "loss", "losing", "deranked"]) and any(w in raw_target_text for w in ["again", "in a row", "5", "five", "matchmaking", "ping", "lag", "trash team", "died again"]):
            return RoastObservation(
                category="GAMING_DONATION",
                angle=ComedyAngle.IRONY,
                summary="Losing multiple gaming matches in a row while blaming team/matchmaking",
                punchlines_by_level={
                    1: "Another match down? You're being awfully generous to the other team today 😂",
                    2: "Five losses in a row and bro is still blaming matchmaking 😭",
                    3: "At this point you're not playing the game. You're personally donating wins.",
                    4: "Bro is treating competitive ranked like a registered charity for the enemy team 💀",
                    5: "Five losses in a row, zero objectives secured, and bro is still typing a thesis in chat blaming matchmaking."
                }
            )

        # 5. OVERCONFIDENCE REVERSAL (Section 7)
        if any(w in raw_target_text for w in ["easy", "ez", "i know what i'm doing", "i know exactly", "trust me", "handled it", "i got this", "watch this"]) and any(w in raw_target_text for w in ["wait", "broke", "failed", "died", "oops", "nevermind", "help"]):
            return RoastObservation(
                category="OVERCONFIDENCE",
                angle=ComedyAngle.OVERCONFIDENCE,
                summary="Display of absolute certainty followed by immediate blunder",
                punchlines_by_level={
                    1: "The confidence was there. The results were... taking notes.",
                    2: "The confidence was impressive. The results were not.",
                    3: "I respect your confidence. I just wish reality did too.",
                    4: "Bro walked in with 100% swagger and walked out with a 404 error code 💀",
                    5: "First you had the confidence. Then reality made contact. And now we have a full incident review."
                }
            )

        # 6. PROCRASTINATION & BROKEN PROMISES (Section 2 & 12)
        if any(w in raw_target_text for w in ["not going to procrastinate", "won't procrastinate", "procrastinating", "procrastination", "i'll do it later", "tomorrow for sure", "deadline tomorrow", "started late"]):
            return RoastObservation(
                category="PROCRASTINATION",
                angle=ComedyAngle.MISSED_EXPECTATION,
                summary="Claims of not procrastinating or postponing work until the deadline",
                punchlines_by_level={
                    1: "Starting right now? Sure, and I believe you completely 😂",
                    2: "Sure. And I'm the CEO of Microsoft.",
                    3: "Yeah, you've said that before. Your procrastination has a longer history than some countries.",
                    4: "At this point procrastination isn't a habit. It's your default operating system.",
                    5: "You really waited until the final hour. Procrastination isn't just your habit anymore, it's a fully funded lifestyle."
                }
            )

        # 7. LATE RESPONSE / SIDE QUEST (Section 8)
        if (time_away_seconds is not None and time_away_seconds >= 7200) or any(w in raw_target_text for w in ["sorry was busy", "sorry i was busy", "fell asleep", "lost track of time", "i'm back", "sorry for late reply"]):
            return RoastObservation(
                category="LATE_RESPONSE",
                angle=ComedyAngle.DEADPAN,
                summary="Returning after hours of silence with a casual excuse",
                punchlines_by_level={
                    1: "Look who decided to rejoin society 😂",
                    2: "bro took a side quest and came back like nothing happened 💀",
                    3: "Did you get lost in Narnia or did you just remember this conversation exists?",
                    4: "Bro disappeared for hours like an anime character training in the mountains, only to return with zero buffs.",
                    5: "Disappearing for eight hours and casually saying 'sorry busy' is a level of unbothered diplomacy that should be studied by historians."
                }
            )

        # 8. PROJECT HOPPING / TUTORIAL HELL (Section 10)
        if any(w in raw_target_text for w in ["change project", "changing project", "new project", "another project", "tutorial hell", "abandoned"]) or any("project" in p for p in patterns_lowered):
            return RoastObservation(
                category="PROJECT_HOPPING",
                angle=ComedyAngle.CALLBACK,
                summary="Habitual project starter who rarely finishes anything",
                punchlines_by_level={
                    1: "Another new project? Where do the old ones go to retire? 😂",
                    2: "bro changes projects faster than he finishes them 😭",
                    3: "Another one? Your unfinished-project folder is about to need its own server.",
                    4: "Bro has started 12 projects this month and finished exactly zero of them. The GitHub cemetery is full.",
                    5: "Your graveyard of abandoned projects has formed its own independent territory with its own local government."
                }
            )

        # 9. SLEEP DEPRIVATION / 4 AM DISASTERS
        if any(w in raw_target_text for w in ["4am", "5am", "3am", "all nighter", "haven't slept", "sleep is for the weak", "can't sleep"]):
            return RoastObservation(
                category="SLEEP_DEPRIVATION",
                angle=ComedyAngle.EXAGGERATION,
                summary="Operating on zero sleep at ungodly hours",
                punchlines_by_level={
                    1: "Go to sleep before your keyboard starts answering for you 😭",
                    2: "At this point you're not operating in late night mode. You're operating in a completely different dimension.",
                    3: "It's 4 AM and you're making life decisions. Go to sleep, your brain is currently running on emergency backup power.",
                    4: "Bro is hallucinating conscious thoughts at 4 AM and wondering why everything is breaking 💀",
                    5: "You are actively negotiating with hallucinations at this hour. Close the laptop before you commit to another disaster."
                }
            )

        # 10. COOKING DISASTER
        if any(w in raw_target_text for w in ["burned food", "burned the", "ruined dinner", "kitchen fire", "tastes bad", "burnt"]):
            return RoastObservation(
                category="COOKING_DISASTER",
                angle=ComedyAngle.SARCASM,
                summary="Catastrophic culinary attempt",
                punchlines_by_level={
                    1: "The kitchen survived, right? That's what counts 😂",
                    2: "Michelin is currently investigating this crime scene.\nEven the smoke detector is judging your culinary technique.",
                    3: "That wasn't cooking, that was a high-heat exorcism of edible matter.",
                    4: "Bro turned basic ingredients into hazardous waste and called it dinner 😭",
                    5: "Even the smoke detector filed an emergency complaint regarding your culinary technique."
                }
            )

        # 11. PASSWORD LOCKOUT / 2FA
        if any(w in raw_target_text for w in ["forgot password", "locked out", "lost 2fa", "reset password"]):
            return RoastObservation(
                category="PASSWORD_LOCKOUT",
                angle=ComedyAngle.DEADPAN,
                summary="User locked themselves out of their own account",
                punchlines_by_level={
                    1: "Locked out again? Classic move 😂",
                    2: "Groundbreaking security strategy: locking yourself out so hackers can't get in either.\nAbsolute galaxy brain move.",
                    3: "The ultimate firewall: your own memory.",
                    4: "Bro secured the account so aggressively that even he doesn't have access anymore 💀",
                    5: "A masterclass in zero-trust architecture. You don't even trust yourself with the credentials."
                }
            )

        # 12. DOUBLING DOWN ON A MISTAKE (Section 12 Escalation)
        if any(w in raw_target_text for w in ["no but see", "actually it works", "i meant to do that", "it's a feature", "trust the process"]):
            return RoastObservation(
                category="DOUBLING_DOWN",
                angle=ComedyAngle.EXAGGERATION,
                summary="Explaining or justifying an obvious failure",
                punchlines_by_level={
                    1: "Explaining it definitely made it look intentional 😂",
                    2: "You really doubled down on that? Bold choice.",
                    3: "Remember when you said you learned from that mistake? Neither does the mistake apparently.",
                    4: "First you made the mistake. Then you doubled down. Then you explained it. That's not a mistake anymore, that's a development roadmap.",
                    5: "You didn't misunderstand the assignment. You misunderstood reality. And now you're defending it with a PowerPoint presentation."
                }
            )

        # 13. RECENT TARGET STATEMENT (General contextual statement)
        if target_recent_messages and len(raw_target_text) >= 6:
            return RoastObservation(
                category="QUESTIONABLE_STATEMENT",
                angle=ComedyAngle.DEADPAN,
                summary="Recent statement made by the target",
                punchlines_by_level={
                    1: "That was certainly one of the statements of all time 😂",
                    2: "bro really typed that out, looked at it, and hit send anyway 💀",
                    3: "bro really looked at that decision and said 'yeah this'll work' 😭",
                    4: "You didn't misunderstand the assignment. You misunderstood reality.",
                    5: "Impressive. Not positively, but undeniably impressive in scope."
                }
            )

        # No roastable context found
        return None

    @classmethod
    def analyze_message_context(cls, text: str) -> Optional[str]:
        """Backward-compatible helper for legacy single-string context inspection."""
        obs = cls.find_roastable_observation(target_recent_messages=[text])
        if obs:
            return obs.get_punchline(level=2, target_name="bro")
        return None


# =============================================================================
# 6. SEMANTIC VALIDATION & ANTI-REPETITION CHECKER (Sections 13, 14, 21)
# =============================================================================

class RoastValidator:
    """
    Semantic validation before sending any roast.
    Enforces context connection, punchline clarity, natural phrasing,
    and the 8-point quality test (Sections 14 & 21).
    """

    BANNED_FILLER = BANNED_GENERIC_FILLER

    CORPORATE_AI_PHRASES = [
        "demonstrates a remarkable lack of",
        "resembles that of a",
        "it is imperative that",
        "upon closer inspection",
        "an analytical breakdown reveals",
        "this indicates a suboptimal",
        "is indicative of",
        "it would appear that"
    ]

    @classmethod
    def validate_roast(
        cls,
        roast: str,
        context: Optional[str] = None,
        target_name: str = "bro",
        allow_generic: bool = False,
        level: int = 3
    ) -> Dict[str, Any]:
        result = {
            "is_valid": False,
            "has_context_connection": False,
            "has_clear_punchline": False,
            "is_understandable": False,
            "is_natural": True,
            "is_repetitive": False,
            "is_generic": False,
            "is_overwritten": False,
            "score": 0,
            "rejection_reasons": []
        }

        if not roast or not roast.strip():
            result["rejection_reasons"].append("Roast is empty")
            return result

        clean_text = roast.strip()
        lowered = clean_text.lower()

        # 1. Banned Generic Filler check (Section 13)
        for filler in cls.BANNED_FILLER:
            if re.search(rf"\b{re.escape(filler)}\b", lowered):
                result["is_generic"] = True
                result["rejection_reasons"].append(f"Contains banned generic filler: '{filler}'")

        # 2. Length / Overwritten check (Section 19: default 1-3 sentences)
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", clean_text) if s.strip()]
        sentence_count = len(sentences)
        if sentence_count > 4 or len(clean_text) > 350:
            result["is_overwritten"] = True
            result["rejection_reasons"].append(f"Roast is overwritten ({sentence_count} sentences / {len(clean_text)} chars)")

        # 3. Understandable check
        if 8 <= len(clean_text) <= 350:
            result["is_understandable"] = True

        # 4. Natural phrasing check (Section 20)
        for corp in cls.CORPORATE_AI_PHRASES:
            if corp in lowered:
                result["is_natural"] = False
                result["rejection_reasons"].append(f"Contains corporate AI phrasing: '{corp}'")
                break

        # 5. Internal repetition check
        words = re.findall(r"\b[a-zA-Z]{4,}\b", lowered)
        word_counts = {}
        for w in words:
            if w not in ("bro", "your", "that", "this", "like", "with", "have", "more", "than", "what", "from"):
                word_counts[w] = word_counts.get(w, 0) + 1
                if word_counts[w] >= 3:
                    result["is_repetitive"] = True
                    result["rejection_reasons"].append(f"Repeats word '{w}' {word_counts[w]} times")
                    break

        # 6. Clear punchline check
        has_punctuation = any(clean_text.endswith(p) for p in [".", "!", "?", "💀", "😭", "😂", "😏", "💅", "'", '"', ")"])
        has_multiline_punch = "\n" in clean_text or sentence_count >= 2 or any(e in clean_text for e in ["💀", "😭", "😂"])
        if has_punctuation or has_multiline_punch:
            result["has_clear_punchline"] = True

        # 7. Context connection check (Sections 14 & 17)
        if any(resp.lower() in lowered for resp in NO_CONTEXT_PLAYFUL_RESPONSES):
            result["has_context_connection"] = True
        elif allow_generic:
            result["has_context_connection"] = True
        elif context:
            ctx_lowered = context.lower()
            ctx_tokens = set(re.findall(r"\b[a-zA-Z]{3,}\b", ctx_lowered))
            roast_tokens = set(re.findall(r"\b[a-zA-Z]{3,}\b", lowered))
            stopwords = {"the", "and", "that", "this", "with", "from", "your", "have", "what", "just", "like", "they", "will", "been", "were", "there"}
            meaningful_overlap = (ctx_tokens & roast_tokens) - stopwords
            thematic_keywords = [
                "code", "bug", "broke", "broken", "fix", "fixed", "lost", "loss", "losing",
                "game", "match", "sleep", "project", "later", "tomorrow", "busy", "lock",
                "4am", "mistake", "statement", "excuse", "blunder"
            ]
            has_thematic_match = any(k in ctx_lowered for k in thematic_keywords)
            if target_name.lower() in lowered or meaningful_overlap or has_thematic_match:
                result["has_context_connection"] = True
            else:
                result["rejection_reasons"].append("No semantic connection found between roast and target context")
        else:
            result["rejection_reasons"].append("Context connection required but no context was provided")

        # 8-Point Quality Score (Section 21)
        score = 0
        if result["has_context_connection"]: score += 1
        if (target_name.lower() in lowered or result["has_context_connection"]) and not result["is_generic"]: score += 1
        if result["has_clear_punchline"]: score += 1
        if result["is_understandable"] and not result["is_overwritten"]: score += 1
        if result["is_natural"]: score += 1
        if not result["is_repetitive"]: score += 1
        if not result["is_overwritten"]: score += 1
        if not result["is_generic"]: score += 1

        result["score"] = score

        passes_connection = result["has_context_connection"] or allow_generic
        passes_generic = not result["is_generic"] or allow_generic
        result["is_valid"] = (score >= 6) and passes_connection and passes_generic and not result["is_overwritten"]

        return result


class SimilarityChecker:
    """Prevents Kazumi from repeating jokes or overusing trendy buzzwords."""

    OVERUSED_WORDS = BANNED_GENERIC_FILLER + ["cooked", "bro is cooked", "ratio"]

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
# 7. MAIN ROAST ENGINE ORCHESTRATOR (Sections 1, 3, 11, 14, 15, 21)
# =============================================================================

class RoastEngine:
    """
    Main orchestrator for Kazumi's Contextual Roast Intelligence Engine.
    Coordinates Safety, Intensity, Context Observation, Validation, and Anti-Repetition.
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
        target_recent_messages: Optional[List[str]] = None,
        target_behaviour_patterns: Optional[List[str]] = None,
        time_away_seconds: Optional[float] = None,
        intensity: Optional[int] = None,
        style: Optional[str] = None,
        allow_random: bool = False,
        relationship_level: int = 1,
        guild_id: Optional[int] = None
    ) -> Tuple[bool, str, int]:
        """
        Generates a context-grounded roast.
        Returns: (success: bool, roast_text: str, used_intensity: int)
        """
        # 1. Target Opt-Out & Safety Verification
        if target_id and self.db:
            opted_out, opt_msg = SafetyFilter.check_opt_out(self.db, target_id)
            if opted_out:
                return False, opt_msg, 0

        # Safety check on context text
        all_eval_text = " ".join(filter(None, [context_text] + (target_recent_messages or [])))
        if all_eval_text:
            safe, safe_msg = SafetyFilter.is_safe_prompt(all_eval_text)
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
        is_style_override = bool(style_norm and style_norm not in ("DEFAULT", "CONTEXT"))

        for _ in range(5):
            candidate = ""

            if style_norm == "DEADPAN":
                candidate = DeadpanEngine.generate()
            elif style_norm in ("ANALYSIS", "ANALYTICAL"):
                candidate = AnalyticalEngine.generate(target_display)
            elif style_norm == "DRAMATIC":
                candidate = DramaticAndVillainEngine.generate("dramatic")
            elif style_norm == "VILLAIN":
                candidate = DramaticAndVillainEngine.generate("villain")
            elif style_norm in ("ABSURD", "RANDOM"):
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
            else:
                # 4. Contextual Observation Pipeline (Sections 1, 2, 3, 11)
                effective_target_msgs = target_recent_messages or ([context_text] if context_text else None)
                observation = ContextAnalyzer.find_roastable_observation(
                    target_recent_messages=effective_target_msgs,
                    all_context_messages=[context_text] if context_text else None,
                    target_patterns=target_behaviour_patterns,
                    time_away_seconds=time_away_seconds,
                    target_name=target_display
                )

                if observation:
                    # Observation found -> Level 1 to 5 punchline
                    candidate = observation.get_punchline(level=resolved_intensity, target_name=target_display)
                elif allow_random:
                    # Random roast requested explicitly
                    candidate = AbsurdComparisonEngine.generate(target_display)
                else:
                    # Section 3: If there is nothing to roast, don't invent something!
                    no_ctx_pool = [
                        "Give me something to work with 😭",
                        f"You want a roast for {target_display} with zero evidence? Bold.",
                        "Stand still for five minutes and I'm sure you'll provide material.",
                        f"I roast bad decisions, but {target_display} hasn't made one in front of me yet. Give it a minute.",
                        "Zero context detected. Do something questionable and come back 💀"
                    ]
                    candidate = random.choice(no_ctx_pool)

            # 5. Semantic Validation & 8-point check (Section 14 & 21)
            val = RoastValidator.validate_roast(
                roast=candidate,
                context=context_text,
                target_name=target_display,
                allow_generic=(allow_random or is_style_override),
                level=resolved_intensity
            )

            if val["is_valid"] and not self.similarity_checker.is_too_similar(candidate):
                self.similarity_checker.record_roast(candidate)
                if target_id and self.db:
                    self.db.record_user_roast_interaction(target_id, resolved_intensity)
                return True, candidate, resolved_intensity

        # Fallback to guaranteed valid playful response (Section 3)
        fallback = f"You want a roast for {target_display} with zero evidence? Bold."
        self.similarity_checker.record_roast(fallback)
        if target_id and self.db:
            self.db.record_user_roast_interaction(target_id, resolved_intensity)
        return True, fallback, resolved_intensity


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
        style="Roast format (default, deadpan, analysis, dramatic, villain, obituary, patchnotes, error404, random)",
        random="Allow generic random roast if no context exists (default: False)"
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
            app_commands.Choice(name="System Error 404", value="error404"),
            app_commands.Choice(name="Random Absurdity", value="random")
        ]
    )
    async def slash_roast(
        interaction: discord.Interaction,
        target: Optional[str] = None,
        intensity: Optional[int] = None,
        style: Optional[str] = None,
        random: Optional[bool] = False
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

        # Determine relationship level and memory patterns if target member is present
        rel_level = 2
        target_patterns = []
        try:
            from person_memory import get_observation_manager
            obs = get_observation_manager()
            if obs and target_id:
                prof = obs.memory_mgr.get_profile(str(target_id), target_name or "")
                rel_level = obs.rel_mgr.compute_relationship_level(prof)
                if hasattr(prof, "habits") and prof.habits:
                    target_patterns.extend(prof.habits)
                if hasattr(prof, "traits") and prof.traits:
                    target_patterns.extend(prof.traits)
                if hasattr(prof, "notes") and prof.notes:
                    target_patterns.extend(prof.notes)
        except Exception:
            rel_level = 2

        # Extract recent conversation context isolating target messages (Section 18)
        target_recent_msgs = []
        channel_context_msgs = []
        time_away_seconds = None

        if interaction.channel and hasattr(interaction.channel, "history"):
            try:
                now_ts = time.time()
                async for m in interaction.channel.history(limit=15):
                    if not m.content or m.author.bot:
                        continue
                    channel_context_msgs.append(m.content)
                    if (target_id and m.author.id == target_id) or (not target_id and target_name and target_name.lower() in m.author.name.lower()):
                        target_recent_msgs.append(m.content)
                        if time_away_seconds is None and hasattr(m, "created_at"):
                            time_away_seconds = max(0.0, now_ts - m.created_at.timestamp())
            except Exception:
                pass

        context_text = " | ".join(reversed(channel_context_msgs)) if channel_context_msgs else None

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

        allow_random_mode = bool(random or (style and style.lower() == "random"))

        success, roast_text, used_intensity = engine.generate_roast(
            target_name=target_name or "you",
            target_id=target_id,
            context_text=context_text,
            target_recent_messages=list(reversed(target_recent_msgs)),
            target_behaviour_patterns=target_patterns,
            time_away_seconds=time_away_seconds,
            intensity=intensity,
            style=style,
            allow_random=allow_random_mode,
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
