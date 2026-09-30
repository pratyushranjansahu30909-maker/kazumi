"""
🌸 Kazumi Discord Features — Server Audit Logging System
Tracks server events and posts stylized audit embeds into a configured log channel:
- Member joined & left
- Message deleted & edited
- Warnings, timeouts, kicks, bans, unbans
- Role changes & nickname updates
- Channel creations, edits, and deletions
"""

from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from discord_features.database import get_feature_db


class ServerLogging:
    """Dispatches stylized audit embeds to the configured moderation log channel."""

    @staticmethod
    async def get_log_channel(guild: discord.Guild) -> Optional[discord.TextChannel]:
        db = get_feature_db()
        settings = db.get_guild_settings(str(guild.id))
        chan_id = settings.get("log_channel_id")
        if chan_id:
            try:
                ch = guild.get_channel(int(chan_id))
                if isinstance(ch, discord.TextChannel):
                    return ch
            except Exception:
                pass
        return None

    @classmethod
    async def log_event(cls, guild: discord.Guild, embed: discord.Embed):
        ch = await cls.get_log_channel(guild)
        if ch:
            try:
                await ch.send(embed=embed)
            except Exception:
                pass


def register_logging_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    @tree.command(name="logging", description="Configure server audit & moderation logging channel 📜")
    @app_commands.describe(
        action="Action to perform (set, status, disable)",
        channel="The text channel for audit logs (required if action is set)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Set Log Channel", value="set"),
        app_commands.Choice(name="View Logging Status", value="status"),
        app_commands.Choice(name="Disable Logging", value="disable"),
    ])
    async def slash_logging(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        channel: Optional[discord.TextChannel] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You require **Manage Server** permission to configure logging.", ephemeral=True)
            return

        gid = str(interaction.guild_id)
        settings = db.get_guild_settings(gid)

        if action.value == "set":
            if not channel:
                await interaction.response.send_message("❌ Please specify a channel to set as the log channel.", ephemeral=True)
                return
            db.update_guild_settings(gid, {"log_channel_id": str(channel.id)})
            embed = discord.Embed(
                title="📜 Audit Logging Configured",
                description=f"Server audit events will now be logged to {channel.mention}!",
                color=0x38bdf8
            )
            embed.set_footer(text="Kazumi Logging System 🌸")
            await interaction.response.send_message(embed=embed)

        elif action.value == "disable":
            db.update_guild_settings(gid, {"log_channel_id": None})
            await interaction.response.send_message("📜 Audit logging has been **disabled** for this server.")

        elif action.value == "status":
            current_id = settings.get("log_channel_id")
            ch_mention = f"<#{current_id}>" if current_id else "`None (Disabled)`"
            embed = discord.Embed(
                title="📜 Audit Logging Status",
                description=f"**Current Log Channel:** {ch_mention}\n\n"
                            "**Monitored Events:**\n"
                            "• Member Joins & Leaves\n"
                            "• Message Edits & Deletions\n"
                            "• Warnings, Mutes, Kicks, Bans\n"
                            "• Role & Nickname Changes\n"
                            "• Channel Creations & Deletions",
                color=0xa855f7
            )
            embed.set_footer(text="Kazumi Logging System 🌸")
            await interaction.response.send_message(embed=embed, ephemeral=True)
