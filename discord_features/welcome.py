"""
🌸 Kazumi Discord Features — Welcome & Goodbye System
Greets new members with Kazumi's warm companion personality and customizable cards:
- Supports variables: {user}, {username}, {server}, {count}
- Configurable welcome & goodbye channels and messages
"""

from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import logging
from discord_features.database import get_feature_db

logger = logging.getLogger("KazumiWelcome")


class WelcomeSystem:
    """Handles dispatching welcome and goodbye messages when members join or leave."""

    @staticmethod
    def render_template(template: str, member: discord.Member) -> str:
        text = str(template or "")
        text = text.replace("{user}", str(getattr(member, "mention", "")))
        text = text.replace("{username}", str(getattr(member, "name", "Friend")))
        text = text.replace("{server}", str(getattr(member.guild, "name", "Server") if hasattr(member, "guild") else "Server"))
        count_val = getattr(member.guild, "member_count", "many") if hasattr(member, "guild") else "many"
        text = text.replace("{count}", str(count_val))
        return text

    @classmethod
    def resolve_welcome_channel(cls, member: discord.Member, settings: dict) -> Optional[discord.TextChannel]:
        """Resolves the best channel to send welcome greetings into."""
        guild = getattr(member, "guild", None)
        if not guild or not hasattr(guild, "text_channels"):
            return None

        me = getattr(guild, "me", None)

        def can_send(ch):
            if not ch or not isinstance(ch, discord.TextChannel):
                return False
            if me:
                perms = ch.permissions_for(me)
                return perms.send_messages and perms.embed_links
            return True

        # 1. Configured channel via /welcome
        cid = settings.get("welcome_channel_id")
        if cid:
            try:
                ch = guild.get_channel(int(cid))
                if can_send(ch):
                    return ch
            except Exception:
                pass

        # 2. Guild's designated system channel
        if can_send(guild.system_channel):
            return guild.system_channel

        # 3. Dedicated Kazumi channel in the guild
        for ch in guild.text_channels:
            if "kazumi" in ch.name.lower() and can_send(ch):
                return ch

        # 4. Standard welcome / general channels
        target_names = ["welcome", "joins", "arrivals", "general", "main", "chat", "lounge"]
        for target in target_names:
            for ch in guild.text_channels:
                if target in ch.name.lower() and can_send(ch):
                    return ch

        # 5. First available channel with permissions
        for ch in guild.text_channels:
            if can_send(ch):
                return ch

        return None

    @classmethod
    def resolve_goodbye_channel(cls, member: discord.Member, settings: dict) -> Optional[discord.TextChannel]:
        """Resolves channel for goodbye notes."""
        guild = getattr(member, "guild", None)
        if not guild or not hasattr(guild, "text_channels"):
            return None

        cid = settings.get("goodbye_channel_id") or settings.get("welcome_channel_id")
        if cid:
            try:
                ch = guild.get_channel(int(cid))
                if ch and isinstance(ch, discord.TextChannel):
                    return ch
            except Exception:
                pass

        if guild.system_channel:
            return guild.system_channel
        return None

    @classmethod
    async def on_member_join(cls, member: discord.Member):
        """Dispatched when a new member joins the server."""
        await cls.send_welcome(member)

    @classmethod
    async def on_member_remove(cls, member: discord.Member):
        """Dispatched when a member leaves the server."""
        await cls.send_goodbye(member)

    @classmethod
    async def send_welcome(cls, member: discord.Member):
        """Tags the new member and posts Kazumi's warm welcome card."""
        if not member or not hasattr(member, "guild") or member.bot:
            return

        db = get_feature_db()
        settings = db.get_guild_settings(str(member.guild.id))
        if settings.get("welcome_enabled") is False:
            return

        channel = cls.resolve_welcome_channel(member, settings)
        if not channel:
            logger.info(f"No suitable welcome channel found in {member.guild.name} ({member.guild.id})")
            return

        try:
            default_template = (
                "Welcome to **{server}**, {user}! 🌸 We're so excited to have you here with us.\n\n"
                "Make yourself at home, feel free to introduce yourself, and let me know if you ever want to chat or play a game! ✨"
            )
            raw_msg = settings.get("welcome_message") or default_template
            rendered = cls.render_template(raw_msg, member)

            embed = discord.Embed(
                title=f"🌸 Welcome to {member.guild.name}!",
                description=rendered,
                color=0xf472b6
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="✨ Member Count", value=f"You are member **#{member.guild.member_count}**!", inline=True)
            embed.set_footer(text="Kazumi Companion Welcome 🌸 • Sweet & Cozy")
            embed.timestamp = datetime.now(timezone.utc)

            # Tag the member directly in message content so Discord triggers a notification/mention
            tag_content = f"🌸 Welcome {member.mention}! ✨"
            await channel.send(content=tag_content, embed=embed)
            logger.info(f"Successfully welcomed and tagged {member.name} ({member.id}) in #{channel.name}")
        except Exception as e:
            logger.warning(f"Failed to send welcome message in {channel.name}: {e}")

    @classmethod
    async def send_goodbye(cls, member: discord.Member):
        if not member or not hasattr(member, "guild") or member.bot:
            return

        db = get_feature_db()
        settings = db.get_guild_settings(str(member.guild.id))
        if not settings.get("goodbye_enabled", False):
            return

        channel = cls.resolve_goodbye_channel(member, settings)
        if not channel:
            return

        try:
            raw_msg = settings.get("goodbye_message", "{user} has left the server. Take care! 🌸")
            rendered = cls.render_template(raw_msg, member)

            embed = discord.Embed(
                title="🍃 Goodbye for now",
                description=rendered,
                color=0x94a3b8
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Kazumi Companion 🌸")
            embed.timestamp = datetime.now(timezone.utc)

            await channel.send(embed=embed)
        except Exception as e:
            logger.warning(f"Failed to send goodbye message in {channel.name}: {e}")


def register_welcome_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    @tree.command(name="welcome", description="Configure member welcome greeting channel and message 🌸")
    @app_commands.describe(
        action="Configure welcome system (channel, message, toggle, status)",
        channel="Channel to send welcome greetings into",
        message="Custom welcome message (Variables: {user}, {username}, {server}, {count})",
        enabled="Enable or disable welcome greetings"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set Welcome Channel", value="channel"),
        app_commands.Choice(name="Set Welcome Message", value="message"),
        app_commands.Choice(name="Toggle Enabled / Disabled", value="toggle"),
        app_commands.Choice(name="View Current Status", value="status"),
    ])
    async def slash_welcome(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        channel: Optional[discord.TextChannel] = None,
        message: Optional[str] = None,
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
            await interaction.response.send_message(f"🌸 Welcome channel set to {channel.mention} (Welcome enabled)!")

        elif action.value == "message":
            if not message:
                await interaction.response.send_message("❌ Please provide a message template (e.g. `Welcome to {server}, {user}! 🌸`).", ephemeral=True)
                return
            db.update_guild_settings(gid, {"welcome_message": message})
            await interaction.response.send_message(f"🌸 Welcome message template updated:\n>>> {message}")

        elif action.value == "toggle":
            is_en = enabled if enabled is not None else not settings.get("welcome_enabled", False)
            db.update_guild_settings(gid, {"welcome_enabled": is_en})
            await interaction.response.send_message(f"🌸 Welcome greeting system is now **{'Enabled' if is_en else 'Disabled'}**.")

        elif action.value == "status":
            ch_id = settings.get("welcome_channel_id")
            ch_str = f"<#{ch_id}>" if ch_id else "`None`"
            embed = discord.Embed(
                title="🌸 Welcome Greeting Status",
                description=f"**Status:** {'✅ Enabled' if settings.get('welcome_enabled') else '❌ Disabled'}\n"
                            f"**Channel:** {ch_str}\n"
                            f"**Template:**\n>>> {settings.get('welcome_message')}",
                color=0xf472b6
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="goodbye", description="Configure member leave / goodbye messages 🍃")
    @app_commands.describe(
        action="Configure goodbye system (channel, message, toggle)",
        channel="Channel to send goodbye notes into",
        message="Custom goodbye message (Variables: {user}, {username}, {server}, {count})",
        enabled="Enable or disable goodbye messages"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set Goodbye Channel", value="channel"),
        app_commands.Choice(name="Set Goodbye Message", value="message"),
        app_commands.Choice(name="Toggle Enabled / Disabled", value="toggle"),
    ])
    async def slash_goodbye(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        channel: Optional[discord.TextChannel] = None,
        message: Optional[str] = None,
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

        elif action.value == "message":
            if not message:
                await interaction.response.send_message("❌ Please provide a message template.", ephemeral=True)
                return
            db.update_guild_settings(gid, {"goodbye_message": message})
            await interaction.response.send_message(f"🍃 Goodbye template updated:\n>>> {message}")

        elif action.value == "toggle":
            is_en = enabled if enabled is not None else not settings.get("goodbye_enabled", False)
            db.update_guild_settings(gid, {"goodbye_enabled": is_en})
            await interaction.response.send_message(f"🍃 Goodbye notes are now **{'Enabled' if is_en else 'Disabled'}**.")
