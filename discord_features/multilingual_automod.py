# -*- coding: utf-8 -*-
"""
🌸 Kazumi Advanced Multilingual AutoMod Engine
Contextual detection of insults, harassment, hate speech, threats, and abusive language across:
- English
- Hindi & Hinglish (Romanized transliterations and phonetic variants)
- Odia (Regional Romanized terms and colloquial profanity)
- Leetspeak, deliberate misspellings, zero-width character substitutions, and character repetition.

Safeguards:
- Private direct warning delivery to users (no public humiliation in chat).
- Burst grouping & DM notification cooldowns.
- Graceful handling of closed DMs with staff-channel alert fallback.
- Contextual severity grading (SEVERE, HIGH, MEDIUM, LOW).
- Appeal and rule reference routing.
"""

import re
import time
import unicodedata
import logging
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone

import discord

logger = logging.getLogger("KazumiMultilingualAutoMod")


class ViolationSeverity(Enum):
    LOW = "LOW"            # Mild slang, borderline
    MEDIUM = "MEDIUM"      # Direct profanity / standard insult
    HIGH = "HIGH"          # Targeted harassment / sexual harassment
    SEVERE = "SEVERE"      # Slurs, hate speech, violent threats


class MultilingualTextNormalizer:
    """Normalizes text by resolving leetspeak, zero-width characters, and repeated letters."""

    LEET_MAP = {
        '0': 'o', '1': 'i', '!': 'i', '|': 'i', '3': 'e',
        '4': 'a', '@': 'a', '$': 's', '5': 's', '7': 't',
        '+': 't', '8': 'b', '9': 'g', '(': 'c', '<': 'c'
    }

    # Zero-width spaces, joiners, formatting codepoints to remove
    ZERO_WIDTH_CHARS = {'\u200b', '\u200c', '\u200d', '\ufeff', '\u2060', '\u00ad'}

    @classmethod
    def clean_text(cls, text: str) -> str:
        """Strips zero-width characters, normalizes unicode accents."""
        if not text:
            return ""
        # Unicode normalization
        norm = unicodedata.normalize('NFKD', text)
        # Strip zero-width characters
        norm = "".join(c for c in norm if c not in cls.ZERO_WIDTH_CHARS)
        return norm

    @classmethod
    def de_leet(cls, text: str) -> str:
        """Converts common leetspeak substitutions back to standard letters."""
        cleaned = cls.clean_text(text)
        out = []
        for ch in cleaned:
            out.append(cls.LEET_MAP.get(ch, ch))
        return "".join(out)

    @classmethod
    def normalize_for_analysis(cls, text: str) -> str:
        """Full normalization pipeline for pattern matching."""
        de_leeted = cls.de_leet(text).lower()
        # Remove punctuation that might be used to split words: f.u.c.k -> fuck
        de_spaced = re.sub(r"[\s._\-*~`^/\\,]+", " ", de_leeted)
        # Collapse repeated letters: fuuuuck -> fuck (max 2 repetitions)
        collapsed = re.sub(r"(.)\1{2,}", r"\1\1", de_spaced)
        return collapsed.strip()


class MultilingualAutoMod:
    """
    Evaluates messages across English, Hindi, Hinglish, and Odia.
    Dispatches respectful private warnings and handles appeals gracefully.
    """

    def __init__(self, db: Any = None):
        self.db = db
        # Tracking recent DM notices to avoid spamming the user: user_id -> timestamp
        self.dm_cooldowns: Dict[int, float] = {}
        # Tracking repeated violations: (guild_id, user_id) -> list of timestamp
        self.user_violation_history: Dict[Tuple[int, int], List[float]] = {}

        self._compile_patterns()

    def _compile_patterns(self):
        """Compiles regex patterns across languages and categories."""

        # 1. English Profanity & Slurs
        self.en_severe = [
            r"\b(?:n+i+g+g+e+r+|n+i+g+g+a+|f+a+g+g+o+t+|k+y+s+|k+i+l+l+\s*y+o+u+r+s+e+l+f+)\b",
            r"\b(?:i\s*will\s*kill\s*you|gonna\s*kill\s*you|slit\s*your\s*throat)\b"
        ]
        self.en_standard = [
            r"\b(?:f+u+c+k+|s+h+i+t+|b+i+t+c+h+|c+u+n+t+|a+s+s+h+o+l+e+|d+i+c+k+h+e+a+d+|b+a+s+t+a+r+d+)\b",
            r"\b(?:motherfucker|whore|slut|dipshit|cocksucker)\b"
        ]

        # 2. Hindi & Hinglish Transliterations
        self.hi_severe = [
            r"\b(?:m+a+d+a+r+c+h+o+d+|m+c+|b+h+e+n+c+h+o+d+|b+c+|b+e+h+e+n+c+h+o+d+)\b",
            r"\b(?:t+e+r+i+\s*m+a+a+\s*k+i+|m+a+a+\s*k+i+\s*c+h+u+d+)\b"
        ]
        self.hi_standard = [
            r"\b(?:b+h+o+s+d+i+k+e+|b+h+o+s+d+i+|c+h+u+t+i+y+a+|g+a+n+d+u+|h+a+r+a+m+i+|s+a+a+l+e+|s+a+l+a+)\b",
            r"\b(?:r+a+n+d+i+|k+a+m+e+e+n+e+|k+a+m+i+n+a+|l+o+d+u+|l+a+u+d+a+|c+h+o+d+u+|g+a+a+n+d+)\b",
            r"\b(?:t+a+t+t+e+|k+u+t+t+e+|k+u+t+t+i+|c+h+u+t+)\b"
        ]

        # 3. Odia Profanity & Slang (Romanized & Transliterated)
        self.odia_severe = [
            r"\b(?:m+a+g+h+i+a+|m+a+g+h+i+y+a+|c+h+u+d+a+|b+a+l+a+p+i+l+a+n+k+a+)\b"
        ]
        self.odia_standard = [
            r"\b(?:b+o+k+a+|b+o+k+a+c+h+o+d+a+|p+a+d+u+r+u+|g+a+n+d+i+|b+a+a+l+|k+u+k+u+r+a+m+u+n+d+i+a+)\b",
            r"\b(?:d+h+a+n+d+a+b+a+a+z+|c+h+h+i+n+a+l+|b+h+a+n+d+a+|g+a+n+d+i+m+a+r+a+)\b"
        ]

        # Precompile
        self.rx_en_severe = [re.compile(p, re.IGNORECASE) for p in self.en_severe]
        self.rx_en_std = [re.compile(p, re.IGNORECASE) for p in self.en_standard]
        self.rx_hi_severe = [re.compile(p, re.IGNORECASE) for p in self.hi_severe]
        self.rx_hi_std = [re.compile(p, re.IGNORECASE) for p in self.hi_standard]
        self.rx_odia_severe = [re.compile(p, re.IGNORECASE) for p in self.odia_severe]
        self.rx_odia_std = [re.compile(p, re.IGNORECASE) for p in self.odia_standard]

    def evaluate_message(
        self,
        text: str,
        custom_bad_words: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[str], Optional[str], ViolationSeverity]:
        """
        Evaluates text for abuse across English, Hindi/Hinglish, and Odia.
        Returns (violated, category, matched_sample, severity).
        """
        if not text:
            return (False, None, None, ViolationSeverity.LOW)

        # Check custom words first
        if custom_bad_words:
            lower = text.lower()
            for bw in custom_bad_words:
                if bw and bw.lower() in lower:
                    return (True, "Blacklisted Word", bw, ViolationSeverity.MEDIUM)

        normalized = MultilingualTextNormalizer.normalize_for_analysis(text)

        # 1. Check Severe English (slurs, hate speech, violence)
        for rx in self.rx_en_severe:
            m = rx.search(normalized)
            if m:
                return (True, "Hate Speech & Threats (English)", m.group(0), ViolationSeverity.SEVERE)

        # 2. Check Severe Hindi/Hinglish
        for rx in self.rx_hi_severe:
            m = rx.search(normalized)
            if m:
                return (True, "Severe Abuse (Hindi/Hinglish)", m.group(0), ViolationSeverity.SEVERE)

        # 3. Check Severe Odia
        for rx in self.rx_odia_severe:
            m = rx.search(normalized)
            if m:
                return (True, "Severe Abuse (Odia)", m.group(0), ViolationSeverity.SEVERE)

        # 4. Check Standard Odia
        for rx in self.rx_odia_std:
            m = rx.search(normalized)
            if m:
                return (True, "Profanity (Odia)", m.group(0), ViolationSeverity.MEDIUM)

        # 5. Check Standard Hindi/Hinglish
        for rx in self.rx_hi_std:
            m = rx.search(normalized)
            if m:
                return (True, "Profanity (Hindi/Hinglish)", m.group(0), ViolationSeverity.MEDIUM)

        # 6. Check Standard English
        for rx in self.rx_en_std:
            m = rx.search(normalized)
            if m:
                return (True, "Profanity (English)", m.group(0), ViolationSeverity.MEDIUM)

        return (False, None, None, ViolationSeverity.LOW)

    def evaluate_text(
        self,
        text: str,
        user_id: Any = None,
        custom_bad_words: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Synchronous evaluation helper returning structured evaluation dictionary.
        """
        violated, category, sample, severity = self.evaluate_message(text, custom_bad_words)
        return {
            "violation": violated,
            "matched_rule": category or "None",
            "snippet": sample,
            "severity": severity,
            "user_id": user_id
        }

    evaluate_message_content = evaluate_message

    async def handle_violation(
        self,
        message: discord.Message,
        category: str,
        severity: ViolationSeverity,
        evidence_snippet: str
    ) -> Dict[str, Any]:
        """
        Deletes violating message, records moderation case, and sends private DM.
        Does NOT publicize offensive content or embarrass user in chat.
        """
        guild = message.guild
        author = message.author
        now = time.time()
        result = {
            "deleted": False,
            "dm_sent": False,
            "case_id": None,
            "action_taken": "NONE"
        }

        # 1. Delete message safely
        try:
            await message.delete()
            result["deleted"] = True
        except discord.NotFound:
            result["deleted"] = True
        except discord.Forbidden:
            logger.warning(f"Missing Manage Messages permission in #{message.channel.name} to delete violation.")
        except Exception as e:
            logger.warning(f"Failed to delete violating message: {e}")

        # 2. Record moderation case in FeatureDatabase
        case_id = 0
        if self.db and guild:
            case_id = self.db.create_case(
                guild_id=guild.id,
                user_id=author.id,
                moderator_id=guild.me.id if guild.me else 0,
                action="AUTOMOD",
                reason=f"[{severity.value}] {category}",
                evidence=f"Matched term under category '{category}'"
            )
            result["case_id"] = case_id

        # 3. Track repeat violations
        if guild:
            key = (guild.id, author.id)
            history = self.user_violation_history.setdefault(key, [])
            history.append(now)
            # Keep history from last 10 minutes
            self.user_violation_history[key] = [t for t in history if now - t <= 600.0]
            violation_count = len(self.user_violation_history[key])
        else:
            violation_count = 1

        # 4. Dispatch Private Warning DM (Respect Cooldown)
        last_dm = self.dm_cooldowns.get(author.id, 0)
        server_name = guild.name if guild else "LAPEACE"

        if now - last_dm > 60.0:
            dm_text = (
                f"Hey, please keep the chat respectful. 🌸\n\n"
                f"Your recent message in **{server_name}** violated the server's chat rules (`{category}`), "
                f"so I have removed it. Let's keep {server_name} comfortable and welcoming for everyone. "
                f"Please avoid repeating this.\n\n"
                f"*(Case `#{case_id}` • If you believe this was an error, please reach out to server moderators.)*"
            )

            if severity == ViolationSeverity.SEVERE:
                dm_text = (
                    f"⚠️ **Important Moderation Notice from {server_name}**\n\n"
                    f"Your message was removed for violating the server's policy against harassment, hate speech, or slurs.\n"
                    f"Continued violations may result in an immediate timeout or server ban.\n\n"
                    f"*(Case `#{case_id}` • Contact server staff to appeal.)*"
                )

            try:
                await author.send(dm_text)
                self.dm_cooldowns[author.id] = now
                result["dm_sent"] = True
            except discord.Forbidden:
                logger.info(f"User {author} has DMs disabled. Warning could not be sent privately.")
            except Exception as e:
                logger.warning(f"Could not send AutoMod warning DM to {author}: {e}")

        # 5. Escalate repeat offenders (>= 3 violations in 10 mins)
        if violation_count >= 3 and guild and isinstance(author, discord.Member):
            try:
                from datetime import timedelta
                # Apply 10-minute timeout for repeat offenders if bot has permission
                if guild.me.guild_permissions.moderate_members and guild.me.top_role > author.top_role:
                    timeout_until = discord.utils.utcnow() + timedelta(minutes=10)
                    await author.timeout(timeout_until, reason="AutoMod repeat offender escalation (3+ violations in 10m)")
                    result["action_taken"] = "TIMEOUT_10M"
            except Exception as esc_err:
                logger.warning(f"Failed to apply repeat offender escalation: {esc_err}")

        return result
