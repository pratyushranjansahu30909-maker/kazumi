# -*- coding: utf-8 -*-
"""
🌸 Kazumi Discord Features — Welcome & Goodbye Poetry System
============================================================
Features:
- Personalized 4–8 Line Welcome Poetry for newcomers in configured welcome channel
- Personalized 4–8 Line Farewell Poetry for departing members in farewell/welcome channel
- Untrusted display name sanitization (injection prevention, mention stripping)
- High-reliability OpenAI gpt-4o-mini generation with cozy Kazumi personality
- Varied, safe local fallback poems when API is unavailable or times out
- Multi-layer join and leave deduplication (180s sliding window)
- Automatic fallback channel resolution: farewell -> welcome -> system channel
- Interactive slash commands: /welcome and /goodbye (channel, test, toggle, status)
"""

import os
import re
import time
import random
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, Set, Dict, Any, List

import discord
from discord import app_commands
from discord.ext import commands

from discord_features.database import get_feature_db
from discord_features.config import KazumiConfig

logger = logging.getLogger("KazumiWelcome")

# In-memory deduplication caches: (guild_id, member_id) -> timestamp
_PROCESSED_JOINS: Dict[Tuple[int, int], float] = {}
_JOIN_LOCK = asyncio.Lock()

_PROCESSED_LEAVES: Dict[Tuple[int, int], float] = {}
_LEAVE_LOCK = asyncio.Lock()


# ==============================================================================
# NAME SANITIZATION & SAFETY ENGINE
# ==============================================================================
def sanitize_display_name(name: Optional[str]) -> str:
    """
    Safely sanitizes untrusted member display names.
    Guarantees:
    - Strips Discord mass mentions (@everyone, @here, <@...>, <@&...>, <#...>)
    - Strips URLs and invite links
    - Strips markdown formatting characters (`, *, _, ~, |, >)
    - Replaces control characters and non-printable bytes
    - Limits length to 32 characters
    - Provides safe fallback for empty/pure-symbol names
    """
    if not name:
        return "Friend"

    clean = str(name).strip()

    # 1. Strip mentions
    clean = re.sub(r"@(?:everyone|here)", "friend", clean, flags=re.IGNORECASE)
    clean = re.sub(r"<@!?\d+>", "", clean)
    clean = re.sub(r"<@&\d+>", "", clean)
    clean = re.sub(r"<#\d+>", "", clean)

    # 2. Strip URLs and invites
    clean = re.sub(r"https?://\S+", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"discord\.(?:gg|io|me|li)/\S+", "", clean, flags=re.IGNORECASE)

    # 3. Strip dangerous Discord markdown syntax
    clean = re.sub(r"[`*_~|>]", "", clean)

    # 4. Collapse extra spaces
    clean = re.sub(r"\s+", " ", clean).strip()

    # 5. Length limit
    if len(clean) > 32:
        clean = clean[:32].strip()

    # 6. Fallback if empty or purely non-alphanumeric
    if not clean or not re.search(r"[a-zA-Z0-9\u0080-\uffff]", clean):
        return "Friend"

    return clean


# ==============================================================================
# PERSONALIZED WELCOME & FAREWELL POEM GENERATOR
# ==============================================================================
class WelcomePoemGenerator:
    """Generates unique, emotional 4–8 line rhyming poems with resilient local fallbacks."""

    # Legacy two-line fallbacks for backwards compatibility with existing test suites
    FALLBACK_RHYMES_TWO_LINE = [
        ("{name} brings a spark, turning ordinary skies to gold,\n{server} feels warmer with another story to unfold. 🌸", "gold/unfold"),
        ("{name} lights the night with a glow that feels brand new,\n{server} just gained a little extra magic thanks to you. ✨", "new/you"),
        ("{name} walks right in, like a melody soft and sweet,\n{server} just found the missing rhythm to our beat. 🌙", "sweet/beat"),
        ("{name} steps through the gates as the stars begin to shine,\n{server} welcomes a presence so radiant and divine. 💫", "shine/divine"),
        ("{name} brings a smile that chases every cloud away,\n{server} feels a whole lot brighter starting from today. 🌸", "away/today")
    ]

    # Varied 4–6 line welcome poems with Kazumi's affectionate, cozy tone
    WELCOME_FALLBACK_POEMS = [
        (
            "Welcome, {name}, beneath our skies, 🌸\n"
            "A little new star where a friendship may rise.\n"
            "May laughter find you and good moments stay,\n"
            "May {server} brighten your ordinary day. 💜"
        ),
        (
            "Softly the blossoms sway in the breeze, 🌸\n"
            "Welcoming {name} with comfort and ease.\n"
            "Step in and rest where the starlight gleams bright,\n"
            "Here in {server}, you bring a sweet light. ✨"
        ),
        (
            "A brand new journey begins right here, ✨\n"
            "With warmth to share and friends held dear.\n"
            "{name}, we are glad you found {server} today,\n"
            "May happiness follow you all the way. 💜"
        ),
        (
            "Leaves may dance and the quiet winds sing, 🌸\n"
            "Bringing the hope that new friendships bring.\n"
            "Welcome to {server}, dear {name}, take your place,\n"
            "Surrounded by kindness, good cheer, and grace. 🌙"
        ),
        (
            "The lanterns are glowing, the fires are lit, ✨\n"
            "A circle of friends where you naturally fit.\n"
            "Welcome, {name}, to our cozy retreat,\n"
            "Every kind greeting makes {server} complete. 💜"
        ),
        (
            "From miles away to our open door, 🌸\n"
            "A wonderful story to tell once more.\n"
            "{name}, welcome to {server}, so bright,\n"
            "Guided by warmth and soft glowing light. ✨"
        ),
    ]

    # Varied 4–6 line bittersweet farewell poems wishing them well without guilt/shame
    FAREWELL_FALLBACK_POEMS = [
        (
            "{name}, the room feels quieter today, 🌙\n"
            "A familiar light has drifted away.\n"
            "May kinder roads unfold wherever you roam,\n"
            "And may you find joy wherever you call home. 💜"
        ),
        (
            "A chapter softly closes its page, 🌙\n"
            "Leaving warm memories upon our stage.\n"
            "{name}, your presence was treasured and dear,\n"
            "May peace walk beside you year after year. ✨"
        ),
        (
            "Like petals carried on an evening breeze, 🌸\n"
            "You wander off under different trees.\n"
            "Thank you for every moment you shared,\n"
            "{name}, please know that we always cared. 💜"
        ),
        (
            "The footsteps fade, but the echoes remain, 🌙\n"
            "Gentle and sweet as the summer rain.\n"
            "Farewell, {name}, may your future be bright,\n"
            "With happiness guiding you into the light. ✨"
        ),
        (
            "Stars will still shine in the quiet dusk air, 🌙\n"
            "Carrying memories of having you there.\n"
            "Wherever your journey takes you from now,\n"
            "{name}, we wish you the best with a gentle bow. 💜"
        ),
        (
            "Paths may diverge as the seasons change, 🌙\n"
            "Across new horizons so wide and strange.\n"
            "Thank you for walking with us for a while,\n"
            "May every tomorrow bring {name} a smile. ✨"
        ),
    ]

    # --------------------------------------------------------------------------
    # Backward-compatible 2-line couplet generators (Preserves existing tests)
    # --------------------------------------------------------------------------
    @classmethod
    def generate_local_fallback(cls, display_name: str, server_name: str) -> Tuple[str, str]:
        """Produces a high-quality two-line couplet locally (preserved for existing tests)."""
        template, _ = random.choice(cls.FALLBACK_RHYMES_TWO_LINE)
        rendered = template.format(name=display_name, server=server_name)
        lines = [line.strip() for line in rendered.split("\n") if line.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]
        return (
            f"{display_name} brings a spark, turning ordinary skies to gold,",
            f"{server_name} feels warmer with another story to unfold. 🌸"
        )

    @classmethod
    async def generate_poem(cls, display_name: str, server_name: str) -> Tuple[str, str]:
        """Legacy 2-line generator preserved for backwards compatibility with tests."""
        api_key = KazumiConfig.OPENAI_API_KEY
        if not api_key:
            return cls.generate_local_fallback(display_name, server_name)

        system_prompt = (
            "You are Kazumi, a sweet, warm, companion anime girl welcoming a new friend to the Discord server. "
            "Write a unique, playful, rhyming two-line welcome poem for them.\n"
            "STRICT RULES:\n"
            "1. Output EXACTLY TWO LINES separated by a newline.\n"
            "2. Line 1 must rhyme naturally with Line 2 (AABB couplet).\n"
            "3. Naturally incorporate the member's display name into line 1.\n"
            "4. Mention or evoke the server name.\n"
            "5. Friendly, respectful, cheerful tone. Add 1 tasteful emoji at the end.\n"
            "6. Output ONLY the two lines. No titles, no quotes, no markdown headers, no preamble."
        )
        user_prompt = f"Member name: {display_name}\nServer name: {server_name}"

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, timeout=4.5)

            def _call():
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=70,
                    temperature=0.75,
                    n=1
                )
                return resp.choices[0].message.content.strip()

            raw_poem = await asyncio.wait_for(asyncio.to_thread(_call), timeout=5.0)
            raw_lines = [l.strip().strip('"').strip("'") for l in raw_poem.split("\n") if l.strip()]
            if len(raw_lines) >= 2:
                l1 = re.sub(r"[`*_]", "", raw_lines[0]).strip()
                l2 = re.sub(r"[`*_]", "", raw_lines[1]).strip()
                return l1, l2
        except Exception as e:
            logger.info(f"Using local 2-line poem fallback for {display_name}: {e}")

        return cls.generate_local_fallback(display_name, server_name)

    # --------------------------------------------------------------------------
    # 4–8 Line Welcome Poetry Engine
    # --------------------------------------------------------------------------
    @classmethod
    def generate_local_welcome_fallback(cls, display_name: str, server_name: str) -> str:
        """Selects a polished 4–6 line welcome poem locally."""
        template = random.choice(cls.WELCOME_FALLBACK_POEMS)
        return template.format(name=display_name, server=server_name)

    @classmethod
    async def generate_welcome_poem(cls, display_name: str, server_name: str) -> str:
        """
        Generates a 4–8 line personalized, warm, rhyming welcome poem using gpt-4o-mini.
        Falls back seamlessly to handcrafted poems on error or timeout.
        """
        api_key = KazumiConfig.OPENAI_API_KEY
        if not api_key:
            return cls.generate_local_welcome_fallback(display_name, server_name)

        system_prompt = (
            "You are Kazumi, a sweet, warm, feminine anime companion welcoming a new member to the Discord server. "
            "Write a beautiful, personalized, rhyming welcome poem for them.\n"
            "STRICT RULES:\n"
            "1. Length: EXACTLY 4 to 6 lines (separated by newlines).\n"
            "2. Rhyme naturally (e.g. AABB or ABAB couplets).\n"
            "3. Address the member by their display name.\n"
            "4. Mention or evoke the server name.\n"
            "5. Warm, cozy, emotionally engaging tone; make them feel noticed and valued.\n"
            "6. Use tasteful emojis sparingly (🌸, ✨, 🌙, 💜).\n"
            "7. Never invent personal facts or private details about the member.\n"
            "8. Output ONLY the poem lines. No title, preamble, quotes, or markdown backticks."
        )
        user_prompt = f"Member name: {display_name}\nServer name: {server_name}"

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, timeout=5.0)

            def _call_api():
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=150,
                    temperature=0.8,
                    n=1
                )
                return resp.choices[0].message.content.strip()

            raw_poem = await asyncio.wait_for(asyncio.to_thread(_call_api), timeout=6.0)
            clean_lines = [
                re.sub(r"[`*#_]", "", line).strip()
                for line in raw_poem.split("\n")
                if line.strip() and not line.strip().startswith(("Title:", "Welcome", "---"))
            ]
            if 3 <= len(clean_lines) <= 8:
                return "\n".join(clean_lines)
            logger.info(f"AI welcome poem line count ({len(clean_lines)}) out of bounds, using local fallback.")
        except Exception as e:
            logger.info(f"Using local welcome poem fallback for {display_name}: {e}")

        return cls.generate_local_welcome_fallback(display_name, server_name)

    # --------------------------------------------------------------------------
    # 4–8 Line Farewell Poetry Engine
    # --------------------------------------------------------------------------
    @classmethod
    def generate_local_farewell_fallback(cls, display_name: str, server_name: str) -> str:
        """Selects a polished 4–6 line bittersweet farewell poem locally."""
        template = random.choice(cls.FAREWELL_FALLBACK_POEMS)
        return template.format(name=display_name, server=server_name)

    @classmethod
    async def generate_farewell_poem(cls, display_name: str, server_name: str) -> str:
        """
        Generates a 4–8 line gentle, bittersweet, rhyming farewell poem using gpt-4o-mini.
        Themes: fond memories, presence mattered, wishing them well, no guilt/blame.
        Falls back seamlessly to handcrafted poems on error or timeout.
        """
        api_key = KazumiConfig.OPENAI_API_KEY
        if not api_key:
            return cls.generate_local_farewell_fallback(display_name, server_name)

        system_prompt = (
            "You are Kazumi, a sweet, warm, feminine anime companion saying goodbye to a member leaving the Discord server. "
            "Write a gentle, bittersweet, rhyming farewell poem for them.\n"
            "STRICT RULES:\n"
            "1. Length: EXACTLY 4 to 6 lines (separated by newlines).\n"
            "2. Rhyme naturally (e.g. AABB or ABAB couplets).\n"
            "3. Address the member by their last known display name.\n"
            "4. Themes: fond memories, presence mattered, distance, wishing them joy and well on their future path.\n"
            "5. Heartfelt and gentle. NEVER guilt-trip, blame, shame, or pressure them to return.\n"
            "6. Do not assume any reason for their departure. Never invent personal facts.\n"
            "7. Use tasteful emojis sparingly (🌙, 💜, ✨, 🌸).\n"
            "8. Output ONLY the poem lines. No title, preamble, quotes, or markdown backticks."
        )
        user_prompt = f"Member display name: {display_name}\nServer name: {server_name}"

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, timeout=5.0)

            def _call_api():
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=150,
                    temperature=0.8,
                    n=1
                )
                return resp.choices[0].message.content.strip()

            raw_poem = await asyncio.wait_for(asyncio.to_thread(_call_api), timeout=6.0)
            clean_lines = [
                re.sub(r"[`*#_]", "", line).strip()
                for line in raw_poem.split("\n")
                if line.strip() and not line.strip().startswith(("Title:", "Farewell", "---"))
            ]
            if 3 <= len(clean_lines) <= 8:
                return "\n".join(clean_lines)
            logger.info(f"AI farewell poem line count ({len(clean_lines)}) out of bounds, using local fallback.")
        except Exception as e:
            logger.info(f"Using local farewell poem fallback for {display_name}: {e}")

        return cls.generate_local_farewell_fallback(display_name, server_name)


# ==============================================================================
# WELCOME & GOODBYE SYSTEM DISPATCHER & LIFECYCLE
# ==============================================================================
class WelcomeSystem:
    """Dispatches personalized welcome greetings and farewell messages."""

    @classmethod
    def resolve_welcome_channel(cls, guild: discord.Guild, settings: dict) -> Optional[discord.TextChannel]:
        """
        Resolves the dedicated welcome channel obeying server architecture.
        Prioritizes:
        1. Explicitly configured welcome_channel_id in settings
        2. Channel named 'welcome' with send permissions
        3. Guild designated system channel
        4. Safe text channel with permissions
        """
        if not guild or not hasattr(guild, "text_channels"):
            return None

        me = getattr(guild, "me", None)

        def can_send(ch):
            if not ch or not hasattr(ch, "send"):
                return False
            if me and hasattr(ch, "permissions_for"):
                perms = ch.permissions_for(me)
                return getattr(perms, "send_messages", True) and getattr(perms, "embed_links", True)
            return True

        # 1. Configured channel ID via /welcome
        cid = settings.get("welcome_channel_id")
        if cid:
            try:
                ch = guild.get_channel(int(cid))
                if can_send(ch):
                    return ch
            except Exception:
                pass

        # 2. Channel named 'welcome'
        for ch in guild.text_channels:
            if "welcome" in ch.name.lower() and can_send(ch):
                return ch

        # 3. System channel
        if can_send(guild.system_channel):
            return guild.system_channel

        # 4. First available permitted channel
        for ch in guild.text_channels:
            if can_send(ch):
                return ch

        return None

    @classmethod
    def resolve_goodbye_channel(cls, guild: discord.Guild, settings: dict) -> Optional[discord.TextChannel]:
        """
        Resolves the dedicated farewell/goodbye channel obeying server architecture.
        Hierarchy:
        1. Explicitly configured goodbye_channel_id in settings
        2. Channel named 'farewell' or 'goodbye' with send permissions
        3. Explicitly configured welcome_channel_id in settings
        4. Channel named 'welcome' with send permissions
        5. Guild designated system channel
        6. First available permitted channel
        """
        if not guild or not hasattr(guild, "text_channels"):
            return None

        me = getattr(guild, "me", None)

        def can_send(ch):
            if not ch or not hasattr(ch, "send"):
                return False
            if me and hasattr(ch, "permissions_for"):
                perms = ch.permissions_for(me)
                return getattr(perms, "send_messages", True) and getattr(perms, "embed_links", True)
            return True

        # 1. Explicitly configured goodbye_channel_id
        cid = settings.get("goodbye_channel_id")
        if cid:
            try:
                ch = guild.get_channel(int(cid))
                if can_send(ch):
                    return ch
            except Exception:
                pass

        # 2. Channel named 'farewell' or 'goodbye'
        for ch in guild.text_channels:
            name_lower = ch.name.lower()
            if ("farewell" in name_lower or "goodbye" in name_lower) and can_send(ch):
                return ch

        # 3. Fallback to configured welcome_channel_id
        w_cid = settings.get("welcome_channel_id")
        if w_cid:
            try:
                ch = guild.get_channel(int(w_cid))
                if can_send(ch):
                    return ch
            except Exception:
                pass

        # 4. Channel named 'welcome'
        for ch in guild.text_channels:
            if "welcome" in ch.name.lower() and can_send(ch):
                return ch

        # 5. Guild system channel
        if can_send(guild.system_channel):
            return guild.system_channel

        # 6. First permitted text channel
        for ch in guild.text_channels:
            if can_send(ch):
                return ch

        return None

    @classmethod
    def _find_channel_mention(cls, guild: discord.Guild, target_names: List[str]) -> str:
        """Finds a clickable channel mention like <#id> or falls back to #name."""
        if guild and hasattr(guild, "text_channels"):
            for name in target_names:
                for ch in guild.text_channels:
                    clean_name = re.sub(r"[^\w\-]", "", ch.name.lower())
                    if name in clean_name:
                        return f"<#{ch.id}>"
        return f"#{target_names[0]}"

    @classmethod
    async def on_member_join(cls, member: discord.Member):
        """Triggered strictly when a member joins the guild."""
        await cls.send_welcome(member)

    @classmethod
    async def on_member_remove(cls, member: discord.Member):
        """Triggered strictly when a member leaves or is removed from the guild."""
        await cls.send_goodbye(member)

    @classmethod
    def render_template(cls, template: str, member: discord.Member) -> str:
        """Renders welcome message template with safe variable interpolation."""
        if not template:
            return ""
        user_mention = getattr(member, "mention", "") or f"<@{getattr(member, 'id', 0)}>"
        username = getattr(member, "name", "Friend")
        guild = getattr(member, "guild", None)
        server_name = getattr(guild, "name", "Server") if guild else "Server"
        member_count = getattr(guild, "member_count", 0) if guild else 0

        rendered = template.replace("{user}", user_mention)
        rendered = rendered.replace("{username}", username)
        rendered = rendered.replace("{server}", server_name)
        rendered = rendered.replace("{count}", str(member_count))
        return rendered

    @classmethod
    async def send_welcome(cls, member: discord.Member):
        """Executes the personalized welcome greeting with 4–8 line poetry."""
        if not member or not hasattr(member, "guild") or member.bot:
            return

        guild = member.guild
        db = get_feature_db()
        settings = db.get_guild_settings(str(guild.id))

        if settings.get("welcome_enabled") is False:
            return

        # Deduplication Check (In-memory + sliding time window of 180s)
        now_time = time.time()
        dedup_key = (guild.id, member.id)

        async with _JOIN_LOCK:
            last_welcomed = _PROCESSED_JOINS.get(dedup_key, 0.0)
            if now_time - last_welcomed < 180.0:
                logger.info(f"Skipping duplicate welcome for {member.name} ({member.id}) in {guild.name}")
                return
            _PROCESSED_JOINS[dedup_key] = now_time

            # Cleanup dedup cache if too large
            if len(_PROCESSED_JOINS) > 2000:
                _PROCESSED_JOINS.clear()
                _PROCESSED_JOINS[dedup_key] = now_time

        channel = cls.resolve_welcome_channel(guild, settings)
        if not channel:
            logger.warning(f"No suitable welcome channel found in {guild.name} ({guild.id})")
            return

        try:
            # Safe Display Name Sanitization
            raw_display_name = getattr(member, "display_name", "") or getattr(member, "name", "Friend")
            safe_name = sanitize_display_name(raw_display_name)
            server_name = guild.name

            # Generate the personalized 4–8 line welcome poem
            poem = await WelcomePoemGenerator.generate_welcome_poem(safe_name, server_name)

            # Resolve navigation channel links
            rules_ref = cls._find_channel_mention(guild, ["rules", "rule"])
            intro_ref = cls._find_channel_mention(guild, ["introduction", "introductions", "intro"])
            general_ref = cls._find_channel_mention(guild, ["general", "chat", "lounge"])

            onboarding_text = f"Welcome to **{server_name}**! Check out {rules_ref} and say hello in {intro_ref}. ✨"

            embed = discord.Embed(
                title=f"🌸 Welcome to {server_name}, {safe_name}! ✨",
                description=f"{poem}\n\n{onboarding_text}",
                color=0xf472b6
            )
            if hasattr(member, "display_avatar") and member.display_avatar:
                embed.set_thumbnail(url=member.display_avatar.url)
            elif hasattr(member, "avatar") and member.avatar:
                embed.set_thumbnail(url=member.avatar.url)

            embed.add_field(
                name="✨ Member Count",
                value=f"You are member **#{guild.member_count}**!",
                inline=True
            )
            embed.add_field(
                name="💬 Say Hello",
                value=f"Chat in {general_ref} or spend time with me!",
                inline=True
            )
            embed.set_footer(text="Kazumi Companion 🌸 • Personalized Welcome Poetry")
            embed.timestamp = datetime.now(timezone.utc)

            # Mention member directly in content tag for push notification
            mention_tag = f"🌸 Welcome {member.mention}! ✨"
            await channel.send(content=mention_tag, embed=embed)
            logger.info(f"Delivered personalized welcome poem for {safe_name} ({member.id}) in #{channel.name}")

        except Exception as e:
            logger.error(f"Failed to deliver welcome poem in #{channel.name}: {e}", exc_info=True)

    @classmethod
    async def send_goodbye(cls, member: discord.Member):
        """Executes the personalized farewell greeting with 4–8 line poetry."""
        if not member or not hasattr(member, "guild") or member.bot:
            return

        guild = member.guild
        db = get_feature_db()
        settings = db.get_guild_settings(str(guild.id))

        # Farewell is enabled by default unless explicitly disabled
        if settings.get("goodbye_enabled") is False:
            return

        # Deduplication Check (In-memory + sliding time window of 180s)
        now_time = time.time()
        dedup_key = (guild.id, member.id)

        async with _LEAVE_LOCK:
            last_left = _PROCESSED_LEAVES.get(dedup_key, 0.0)
            if now_time - last_left < 180.0:
                logger.info(f"Skipping duplicate farewell for {member.name} ({member.id}) in {guild.name}")
                return
            _PROCESSED_LEAVES[dedup_key] = now_time

            # Cleanup dedup cache if too large
            if len(_PROCESSED_LEAVES) > 2000:
                _PROCESSED_LEAVES.clear()
                _PROCESSED_LEAVES[dedup_key] = now_time

        channel = cls.resolve_goodbye_channel(guild, settings)
        if not channel:
            logger.warning(f"No suitable farewell channel found in {guild.name} ({guild.id})")
            return

        try:
            raw_display_name = getattr(member, "display_name", "") or getattr(member, "name", "Friend")
            safe_name = sanitize_display_name(raw_display_name)
            server_name = guild.name

            # Generate the personalized 4–8 line farewell poem
            poem = await WelcomePoemGenerator.generate_farewell_poem(safe_name, server_name)

            embed = discord.Embed(
                title=f"🌙 A Fond Farewell to {safe_name}",
                description=f"{poem}\n\nThank you for having been a part of **{server_name}**. We wish you warm roads ahead! 💜",
                color=0xa855f7
            )
            if hasattr(member, "display_avatar") and member.display_avatar:
                embed.set_thumbnail(url=member.display_avatar.url)
            elif hasattr(member, "avatar") and member.avatar:
                embed.set_thumbnail(url=member.avatar.url)

            remaining_count = getattr(guild, "member_count", None)
            if remaining_count:
                embed.set_footer(text=f"Kazumi Companion 💜 • Remaining members: {remaining_count}")
            else:
                embed.set_footer(text="Kazumi Companion 💜 • Always remembered")
            embed.timestamp = datetime.now(timezone.utc)

            await channel.send(embed=embed)
            logger.info(f"Delivered personalized farewell poem for {safe_name} ({member.id}) in #{channel.name}")

        except Exception as e:
            logger.error(f"Failed to deliver farewell poem in #{channel.name}: {e}", exc_info=True)


# ==============================================================================
# SLASH COMMAND REGISTRATION
# ==============================================================================
def register_welcome_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    @tree.command(name="welcome", description="Configure or test member welcome greeting and poetry 🌸")
    @app_commands.describe(
        action="Configure welcome system (channel, test, toggle, status)",
        channel="Channel to send welcome greetings into",
        enabled="Enable or disable welcome greetings"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set Welcome Channel", value="channel"),
        app_commands.Choice(name="Test Welcome Poem (Sample Run)", value="test"),
        app_commands.Choice(name="Toggle Enabled / Disabled", value="toggle"),
        app_commands.Choice(name="View Current Status", value="status"),
    ])
    async def slash_welcome(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        channel: Optional[discord.TextChannel] = None,
        enabled: Optional[bool] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You require **Manage Server** permission.", ephemeral=True)
            return

        gid = str(interaction.guild_id)
        settings = db.get_guild_settings(gid)

        if action.value == "channel":
            if not channel:
                await interaction.response.send_message("❌ Please specify a channel.", ephemeral=True)
                return
            db.update_guild_settings(gid, {"welcome_channel_id": str(channel.id), "welcome_enabled": True})
            await interaction.response.send_message(f"🌸 Welcome channel set to {channel.mention} (Welcome system enabled)!")

        elif action.value == "test":
            await interaction.response.defer(ephemeral=True)
            safe_name = sanitize_display_name(interaction.user.display_name)
            poem = await WelcomePoemGenerator.generate_welcome_poem(safe_name, interaction.guild.name)
            rules_ref = WelcomeSystem._find_channel_mention(interaction.guild, ["rules", "rule"])
            intro_ref = WelcomeSystem._find_channel_mention(interaction.guild, ["introduction", "introductions", "intro"])

            embed = discord.Embed(
                title=f"🌸 Welcome to {interaction.guild.name}, {safe_name}! [TEST PREVIEW]",
                description=f"{poem}\n\nWelcome to **{interaction.guild.name}**! Check out {rules_ref} and introduce yourself in {intro_ref}. ✨",
                color=0xf472b6
            )
            if interaction.user.display_avatar:
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.set_footer(text="Kazumi Welcome Preview • Test Mode")
            await interaction.followup.send("✅ Test welcome poem generated:", embed=embed, ephemeral=True)

        elif action.value == "toggle":
            is_en = enabled if enabled is not None else not settings.get("welcome_enabled", True)
            db.update_guild_settings(gid, {"welcome_enabled": is_en})
            await interaction.response.send_message(f"🌸 Welcome greeting system is now **{'Enabled' if is_en else 'Disabled'}**.")

        elif action.value == "status":
            ch_id = settings.get("welcome_channel_id")
            ch_str = f"<#{ch_id}>" if ch_id else "`Default (#welcome)`"
            embed = discord.Embed(
                title="🌸 Welcome Greeting Status",
                description=(
                    f"**Status:** {'✅ Enabled' if settings.get('welcome_enabled', True) else '❌ Disabled'}\n"
                    f"**Channel:** {ch_str}\n"
                    f"**Engine:** Personalized 4–8 Line Welcome Poetry (`gpt-4o-mini` with local fallback)"
                ),
                color=0xf472b6
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="goodbye", description="Configure or test member farewell / goodbye poetry 🌙")
    @app_commands.describe(
        action="Configure goodbye system (channel, test, toggle, status)",
        channel="Channel to send goodbye notes into",
        enabled="Enable or disable goodbye messages"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set Goodbye Channel", value="channel"),
        app_commands.Choice(name="Test Farewell Poem (Sample Run)", value="test"),
        app_commands.Choice(name="Toggle Enabled / Disabled", value="toggle"),
        app_commands.Choice(name="View Current Status", value="status"),
    ])
    async def slash_goodbye(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        channel: Optional[discord.TextChannel] = None,
        enabled: Optional[bool] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You require **Manage Server** permission.", ephemeral=True)
            return

        gid = str(interaction.guild_id)
        settings = db.get_guild_settings(gid)

        if action.value == "channel":
            if not channel:
                await interaction.response.send_message("❌ Please specify a channel.", ephemeral=True)
                return
            db.update_guild_settings(gid, {"goodbye_channel_id": str(channel.id), "goodbye_enabled": True})
            await interaction.response.send_message(f"🍃 Goodbye channel set to {channel.mention} (Goodbye system enabled)!")

        elif action.value == "test":
            await interaction.response.defer(ephemeral=True)
            safe_name = sanitize_display_name(interaction.user.display_name)
            poem = await WelcomePoemGenerator.generate_farewell_poem(safe_name, interaction.guild.name)

            embed = discord.Embed(
                title=f"🌙 A Fond Farewell to {safe_name} [TEST PREVIEW]",
                description=f"{poem}\n\nThank you for having been a part of **{interaction.guild.name}**. We wish you warm roads ahead! 💜",
                color=0xa855f7
            )
            if interaction.user.display_avatar:
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.set_footer(text="Kazumi Farewell Preview • Test Mode")
            await interaction.followup.send("✅ Test farewell poem generated:", embed=embed, ephemeral=True)

        elif action.value == "toggle":
            is_en = enabled if enabled is not None else not settings.get("goodbye_enabled", True)
            db.update_guild_settings(gid, {"goodbye_enabled": is_en})
            await interaction.response.send_message(f"🍃 Goodbye / Farewell system is now **{'Enabled' if is_en else 'Disabled'}**.")

        elif action.value == "status":
            ch_id = settings.get("goodbye_channel_id")
            w_id = settings.get("welcome_channel_id")
            ch_str = f"<#{ch_id}>" if ch_id else (f"<#{w_id}> (Welcome Fallback)" if w_id else "`Default (#farewell / #welcome)`")
            embed = discord.Embed(
                title="🌙 Goodbye / Farewell Greeting Status",
                description=(
                    f"**Status:** {'✅ Enabled' if settings.get('goodbye_enabled', True) else '❌ Disabled'}\n"
                    f"**Channel:** {ch_str}\n"
                    f"**Engine:** Personalized 4–8 Line Farewell Poetry (`gpt-4o-mini` with local fallback)"
                ),
                color=0xa855f7
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
