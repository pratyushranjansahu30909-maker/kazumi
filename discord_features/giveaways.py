"""
🌸 Kazumi Discord Features — Persistent Giveaway System
Full-featured giveaway manager with interactive entry buttons and restart persistence:
- Commands: /giveaway create, /giveaway end, /giveaway reroll, /giveaway cancel
- Interactive "🎉 Enter Giveaway" button with instant feedback
- Persistent background checker that cleanly finishes giveaways after bot restarts
"""

import time
import random
import re
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

from discord_features.database import get_feature_db


def parse_duration(duration_str: str) -> Optional[float]:
    """Parses duration strings like 10m, 2h, 1d, 30s into seconds."""
    match = re.match(r"^(\d+)\s*([smhd])$", duration_str.strip().lower())
    if not match:
        return None
    val = int(match.group(1))
    unit = match.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return float(val * multipliers[unit])


class GiveawayEntryView(discord.ui.View):
    """Interactive button allowing members to enter the giveaway."""
    def __init__(self, message_id: str):
        super().__init__(timeout=None)
        self.message_id = str(message_id)

    @discord.ui.button(label="Enter Giveaway", style=discord.ButtonStyle.success, emoji="🎉", custom_id="kazumi:giveaway:enter")
    async def enter_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = get_feature_db()
        giveaway = db.get_giveaway(str(interaction.message.id))
        if not giveaway or giveaway.get("ended", False):
            await interaction.response.send_message("❌ This giveaway has already ended.", ephemeral=True)
            return

        # Check required role
        req_role_id = giveaway.get("required_role_id")
        if req_role_id:
            role = interaction.guild.get_role(int(req_role_id))
            if role and role not in interaction.user.roles:
                await interaction.response.send_message(f"❌ You require the {role.mention} role to enter this giveaway.", ephemeral=True)
                return

        entries = list(giveaway.get("entries", []))
        uid = str(interaction.user.id)
        if uid in entries:
            entries.remove(uid)
            giveaway["entries"] = entries
            db.save_giveaway(str(interaction.message.id), giveaway)
            await interaction.response.send_message("👋 You left the giveaway. Click again anytime to re-enter!", ephemeral=True)
        else:
            entries.append(uid)
            giveaway["entries"] = entries
            db.save_giveaway(str(interaction.message.id), giveaway)
            await interaction.response.send_message(f"🎉 You have entered the giveaway for **{giveaway['prize']}**! Good luck!", ephemeral=True)


class GiveawayManager:
    """Manages active giveaways, background timer loops, and winner picks."""

    @staticmethod
    async def finish_giveaway(bot: commands.Bot, message_id: str):
        db = get_feature_db()
        giveaway = db.get_giveaway(message_id)
        if not giveaway or giveaway.get("ended", False):
            return

        giveaway["ended"] = True
        db.save_giveaway(message_id, giveaway)

        try:
            guild = bot.get_guild(int(giveaway["guild_id"]))
            if not guild:
                return
            channel = guild.get_channel(int(giveaway["channel_id"]))
            if not channel:
                return
            message = await channel.fetch_message(int(message_id))
        except Exception:
            return

        entries = giveaway.get("entries", [])
        num_winners = max(1, giveaway.get("winners_count", 1))
        prize = giveaway.get("prize", "Gift")

        if not entries:
            embed = discord.Embed(
                title=f"🎉 Giveaway Ended: {prize}",
                description="Unfortunately, no eligible members entered the giveaway.",
                color=0x94a3b8
            )
            embed.set_footer(text="Kazumi Giveaway System 🌸")
            try:
                await message.edit(embed=embed, view=None)
                await channel.send(f"🎉 The giveaway for **{prize}** ended with no entries.")
            except Exception:
                pass
            return

        # Select random winners
        winner_ids = random.sample(entries, min(num_winners, len(entries)))
        winner_mentions = [f"<@{uid}>" for uid in winner_ids]

        embed = discord.Embed(
            title=f"🎉 Giveaway Winner(s): {prize}!",
            description=f"**Congratulations:** {', '.join(winner_mentions)}!\n"
                        f"**Hosted by:** <@{giveaway['host_id']}>\n"
                        f"**Total Entries:** {len(entries)}",
            color=0xf59e0b
        )
        embed.set_footer(text="Kazumi Giveaway System 🌸")

        try:
            await message.edit(embed=embed, view=None)
            await channel.send(f"🎉 Congratulations {', '.join(winner_mentions)}! You won **{prize}**! 🌸")
        except Exception:
            pass

    @staticmethod
    async def check_active_giveaways(bot: commands.Bot):
        db = get_feature_db()
        now = time.time()
        for g in db.get_active_giveaways():
            if g.get("end_time", 0) <= now and not g.get("ended", False):
                await GiveawayManager.finish_giveaway(bot, g["message_id"])



def register_giveaway_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    @tree.command(name="giveaway", description="Create and manage server giveaways 🎉")
    @app_commands.describe(
        action="Action (create, end, reroll, cancel)",
        duration="Duration for giveaway (e.g. 10m, 2h, 1d)",
        prize="Prize description",
        winners="Number of winners (default 1)",
        required_role="Role required to participate (optional)",
        message_id="Message ID of the giveaway (for end, reroll, cancel)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Create Giveaway", value="create"),
        app_commands.Choice(name="End Giveaway Early", value="end"),
        app_commands.Choice(name="Reroll Winners", value="reroll"),
        app_commands.Choice(name="Cancel Giveaway", value="cancel"),
    ])
    async def slash_giveaway(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        duration: Optional[str] = None,
        prize: Optional[str] = None,
        winners: Optional[int] = 1,
        required_role: Optional[discord.Role] = None,
        message_id: Optional[str] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You require **Manage Server** permission.", ephemeral=True)
            return

        if action.value == "create":
            if not duration or not prize:
                await interaction.response.send_message("❌ Please specify both `duration` (e.g. `10m`) and `prize`.", ephemeral=True)
                return

            seconds = parse_duration(duration)
            if not seconds or seconds < 10:
                await interaction.response.send_message("❌ Invalid duration. Examples: `30s`, `10m`, `2h`, `1d`.", ephemeral=True)
                return

            end_timestamp = time.time() + seconds
            num_w = max(1, min(20, winners or 1))

            req_role_text = f"\n**Required Role:** {required_role.mention}" if required_role else ""
            embed = discord.Embed(
                title=f"🎉 GIVEAWAY: {prize}!",
                description=f"Click **Enter Giveaway** below to enter!\n\n"
                            f"**Winners:** {num_w}\n"
                            f"**Ends:** <t:{int(end_timestamp)}:R> (<t:{int(end_timestamp)}:f>)\n"
                            f"**Hosted by:** {interaction.user.mention}"
                            f"{req_role_text}",
                color=0xf43f5e
            )
            embed.set_footer(text="Kazumi Giveaway System 🌸")

            view = GiveawayEntryView("pending")
            msg = await interaction.channel.send(embed=embed, view=view)

            # Store in database
            giveaway_data = {
                "message_id": str(msg.id),
                "channel_id": str(interaction.channel_id),
                "guild_id": str(interaction.guild_id),
                "host_id": str(interaction.user.id),
                "prize": prize,
                "winners_count": num_w,
                "end_time": end_timestamp,
                "required_role_id": str(required_role.id) if required_role else None,
                "entries": [],
                "ended": False
            }
            db.save_giveaway(str(msg.id), giveaway_data)
            await interaction.response.send_message("✅ Giveaway created successfully!", ephemeral=True)

        elif action.value == "end":
            if not message_id:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway.", ephemeral=True)
                return
            await GiveawayManager.finish_giveaway(bot, message_id.strip())
            await interaction.response.send_message("✅ Giveaway ended.", ephemeral=True)

        elif action.value == "reroll":
            if not message_id:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway.", ephemeral=True)
                return
            g = db.get_giveaway(message_id.strip())
            if not g or not g.get("entries"):
                await interaction.response.send_message("❌ No eligible entries found to reroll.", ephemeral=True)
                return
            winner = random.choice(g["entries"])
            await interaction.channel.send(f"🎉 **Reroll Winner:** Congratulations <@{winner}>! You won **{g['prize']}**! 🌸")
            await interaction.response.send_message("✅ Reroll complete!", ephemeral=True)

        elif action.value == "cancel":
            if not message_id:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway.", ephemeral=True)
                return
            g = db.get_giveaway(message_id.strip())
            if g:
                g["ended"] = True
                db.save_giveaway(message_id.strip(), g)
            await interaction.response.send_message("✅ Giveaway cancelled.", ephemeral=True)
