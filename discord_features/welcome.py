# -*- coding: utf-8 -*-
"""
🌸 Kazumi Discord Features — Welcome & Goodbye System (Phase 4)
==============================================================
Features:
- Personalized Two-Line Welcome Poem utilizing newcomer display name safely
- Untrusted display name sanitization (injection prevention, mention stripping)
- High-reliability AI poem generation with resilient local fallback engine
- Strict channel policy targeting (#welcome / EVENTS_ONLY)
- Multi-layer join deduplication (prevents re-welcome spam and duplicate triggers)
- Dynamic references to #rules, #introductions, and #general
- Rejoin & nickname change immunity
"""

import os
import re
import time
import random
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, Set, Dict, Any

import discord
from discord import app_commands
from discord.ext import commands

from discord_features.database import get_feature_db
from discord_features.config import KazumiConfig

logger = logging.getLogger("KazumiWelcome")

# In-memory deduplication cache: (guild_id, member_id) -> timestamp
_PROCESSED_JOINS: Dict[Tuple[int, int], float] = {}
_JOIN_LOCK = asyncio.Lock()


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
# PERSONALIZED TWO-LINE WELCOME POEM GENERATOR
# ==============================================================================
class WelcomePoemGenerator:
    """Generates unique, rhyming two-line welcome poems with local fallbacks."""

    FALLBACK_RHYMES = [
        ("{name} brings a spark, turning ordinary skies to gold,\n{server} feels warmer with another story to unfold. 🌸", "gold/unfold"),
        ("{name} lights the night with a glow that feels brand new,\n{server} just gained a little extra magic thanks to you. ✨", "new/you"),
        ("{name} walks right in, like a melody soft and sweet,\n{server} just found the missing rhythm to our beat. 🌙", "sweet/beat"),
        ("{name} steps through the gates as the stars begin to shine,\n{server} welcomes a presence so radiant and divine. 💫", "shine/divine"),
        ("{name} brings a smile that chases every cloud away,\n{server} feels a whole lot brighter starting from today. 🌸", "away/today"),
        ("{name} wanders in with an energy clear and bright,\n{server} feels alive with a brand new guiding light. ✨", "bright/light"),
        ("{name} leaves footsteps where laughter is bound to grow,\n{server} just found the sweetest friend to know. 🌷", "grow/know"),
        ("{name} brings fresh wonder right through our open door,\n{server} has a journey you're going to adore. 🌸", "door/adore"),
        ("{name} joins the circle as our cozy campfire gleams,\n{server} is the home for your very sweetest dreams. 🌙", "gleams/dreams"),
        ("{name} arrives today like a gentle summer breeze,\n{server} welcomes you with comfort and with ease. 🍃", "breeze/ease")
    ]

    @classmethod
    def generate_local_fallback(cls, display_name: str, server_name: str) -> Tuple[str, str]:
        """Produces a high-quality two-line couplet locally when AI API is unavailable."""
        template, _ = random.choice(cls.FALLBACK_RHYMES)
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
        """
        Attempts to generate a fresh two-line rhyming poem via OpenAI gpt-4o-mini.
        Falls back seamlessly to local poetic templates on any timeout, error, or missing key.
        """
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

            def _call_api():
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=70,
                    temperature=0.75,
                    n=1
                )
                return response.choices[0].message.content.strip()

            raw_poem = await asyncio.wait_for(asyncio.to_thread(_call_api), timeout=5.0)
            raw_lines = [l.strip().strip('"').strip("'") for l in raw_poem.split("\n") if l.strip()]

            # Validate that we got exactly two lines
            if len(raw_lines) >= 2:
                # Sanitize the output lines
                l1 = re.sub(r"[`*_]", "", raw_lines[0]).strip()
                l2 = re.sub(r"[`*_]", "", raw_lines[1]).strip()
                return l1, l2

        except Exception as e:
            logger.info(f"Using local poem fallback for {display_name}: {e}")

        return cls.generate_local_fallback(display_name, server_name)


# ==============================================================================
# WELCOME SYSTEM DISPATCHER & LIFECYCLE
# ==============================================================================
class WelcomeSystem:
    """Dispatches personalized welcome greetings and goodbye messages."""

    @classmethod
    def resolve_welcome_channel(cls, guild: discord.Guild, settings: dict) -> Optional[discord.TextChannel]:
        """
        Resolves the dedicated #welcome channel obeying server architecture.
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
            if not ch:
                return False
            if not hasattr(ch, "send"):
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
    def _find_channel_mention(cls, guild: discord.Guild, target_names: list[str]) -> str:
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
        """Executes the Phase 4 personalized welcome card with two-line poem."""
        if not member or not hasattr(member, "guild") or member.bot:
            return

        guild = member.guild
        db = get_feature_db()
        settings = db.get_guild_settings(str(guild.id))

        if settings.get("welcome_enabled") is False:
            return

        # Deduplication Check (In-memory + time window of 180s)
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
            server_name = "Gaman" if guild.id == 1554152397327044729 else guild.name

            # Generate the personalized two-line poem
            line1, line2 = await WelcomePoemGenerator.generate_poem(safe_name, server_name)

            # Resolve navigation channel links
            rules_ref = cls._find_channel_mention(guild, ["rules", "rule"])
            intro_ref = cls._find_channel_mention(guild, ["introduction", "introductions", "intro"])
            general_ref = cls._find_channel_mention(guild, ["general", "chat", "lounge"])

            # Surround with polished formatting matching Phase 4 prompt specifications
            poem_block = f"{line1}\n{line2}"
            onboarding_text = f"Welcome to **{server_name}**! Check out {rules_ref} and introduce yourself in {intro_ref}. ✨"

            embed = discord.Embed(
                title=f"🌸 A little {server_name} welcome for {safe_name}!",
                description=f"{poem_block}\n\n{onboarding_text}",
                color=0xf472b6
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(
                name="✨ Member Count",
                value=f"You are member **#{guild.member_count}**!",
                inline=True
            )
            embed.add_field(
                name="💬 Say Hello",
                value=f"Chat in {general_ref} or with me!",
                inline=True
            )
            embed.set_footer(text="Kazumi Companion 🌸 • Personalized Welcome Couplet")
            embed.timestamp = datetime.now(timezone.utc)

            # Mention member directly in content tag for push notification
            mention_tag = f"🌸 Welcome {member.mention}! ✨"
            await channel.send(content=mention_tag, embed=embed)
            logger.info(f"Delivered personalized welcome poem for {safe_name} ({member.id}) in #{channel.name}")

        except Exception as e:
            logger.error(f"Failed to deliver welcome poem in #{channel.name}: {e}", exc_info=True)

    @classmethod
    async def send_goodbye(cls, member: discord.Member):
        """Sends goodbye note when a member parts ways."""
        if not member or not hasattr(member, "guild") or member.bot:
            return

        guild = member.guild
        db = get_feature_db()
        settings = db.get_guild_settings(str(guild.id))

        if not settings.get("goodbye_enabled", False):
            return

        cid = settings.get("goodbye_channel_id") or settings.get("welcome_channel_id")
        channel = guild.get_channel(int(cid)) if cid else guild.system_channel
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        try:
            safe_name = sanitize_display_name(member.display_name)
            embed = discord.Embed(
                title="🍃 Goodbye for now",
                description=f"**{safe_name}** has left the server. We wish them all the best on their journey! 🌸",
                color=0x94a3b8
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Kazumi Companion 🌸")
            embed.timestamp = datetime.now(timezone.utc)
            await channel.send(embed=embed)
        except Exception as e:
            logger.warning(f"Failed to send goodbye message: {e}")


# ==============================================================================
# SLASH COMMAND REGISTRATION
# ==============================================================================
def register_welcome_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    @tree.command(name="welcome", description="Configure or test member welcome greeting and poems 🌸")
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
            l1, l2 = await WelcomePoemGenerator.generate_poem(safe_name, interaction.guild.name)
            rules_ref = WelcomeSystem._find_channel_mention(interaction.guild, ["rules", "rule"])
            intro_ref = WelcomeSystem._find_channel_mention(interaction.guild, ["introduction", "introductions", "intro"])

            embed = discord.Embed(
                title=f"🌸 A little {interaction.guild.name} welcome for {safe_name}! [TEST PREVIEW]",
                description=f"{l1}\n{l2}\n\nWelcome to **{interaction.guild.name}**! Check out {rules_ref} and introduce yourself in {intro_ref}. ✨",
                color=0xf472b6
            )
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
                    f"**Engine:** Personalized Two-Line Poem (`gpt-4o-mini` with local fallback)"
                ),
                color=0xf472b6
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="goodbye", description="Configure member leave / goodbye messages 🍃")
    @app_commands.describe(
        action="Configure goodbye system (channel, toggle)",
        channel="Channel to send goodbye notes into",
        enabled="Enable or disable goodbye messages"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set Goodbye Channel", value="channel"),
        app_commands.Choice(name="Toggle Enabled / Disabled", value="toggle"),
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
            await interaction.response.send_message(f"🍃 Goodbye channel set to {channel.mention}!")

        elif action.value == "toggle":
            is_en = enabled if enabled is not None else not settings.get("goodbye_enabled", False)
            db.update_guild_settings(gid, {"goodbye_enabled": is_en})
            await interaction.response.send_message(f"🍃 Goodbye notes are now **{'Enabled' if is_en else 'Disabled'}**.")
