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
    def __init__(self, message_id: str = "pending"):
        super().__init__(timeout=None)
        self.message_id = str(message_id)

    @discord.ui.button(label="Enter Giveaway", style=discord.ButtonStyle.success, emoji="🎉", custom_id="kazumi:giveaway:enter")
    async def enter_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = get_feature_db()
        giveaway = db.get_giveaway(str(interaction.message.id))
        if not giveaway or giveaway.get("ended", False):
            await interaction.response.send_message("❌ This giveaway has already ended.", ephemeral=True)
            return

        if giveaway.get("paused", False):
            await interaction.response.send_message("⏸️ This giveaway is currently paused by staff.", ephemeral=True)
            return

        # Check required role
        req_role_id = giveaway.get("required_role_id")
        if req_role_id:
            role = interaction.guild.get_role(int(req_role_id))
            if role and role not in interaction.user.roles:
                await interaction.response.send_message(f"❌ You require the {role.mention} role to enter this giveaway.", ephemeral=True)
                return

        # Check minimum account age
        min_acc_days = giveaway.get("min_account_days", 0)
        if min_acc_days > 0:
            now_dt = datetime.now(timezone.utc)
            acc_age_days = (now_dt - interaction.user.created_at).total_seconds() / 86400
            if acc_age_days < min_acc_days:
                await interaction.response.send_message(f"❌ Your Discord account must be at least **{min_acc_days} days** old to enter (yours is {int(acc_age_days)} days).", ephemeral=True)
                return

        # Check minimum server membership age
        min_srv_days = giveaway.get("min_server_days", 0)
        if min_srv_days > 0 and hasattr(interaction.user, "joined_at") and interaction.user.joined_at:
            now_dt = datetime.now(timezone.utc)
            joined_days = (now_dt - interaction.user.joined_at).total_seconds() / 86400
            if joined_days < min_srv_days:
                await interaction.response.send_message(f"❌ You must be a member of this server for at least **{min_srv_days} days** to enter (you have been here {int(joined_days)} days).", ephemeral=True)
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
            await interaction.response.send_message(f"🎉 You have entered the giveaway for **{giveaway['prize']}**! Total entries: **{len(entries)}**", ephemeral=True)


class GiveawayManager:
    """Manages active giveaways, background timer loops, and winner picks."""

    def __init__(self, bot: Any = None, db: Any = None):
        self.bot = bot
        self.db = db or get_feature_db()

    @staticmethod
    def enter_giveaway(guild_id: str, message_id: str, user_id: Any, db: Any = None, member: Any = None) -> Tuple[bool, str]:
        if db is None:
            db = get_feature_db()
        giveaway = db.get_giveaway(message_id)
        if not giveaway:
            return False, "Giveaway not found."
        if giveaway.get("ended", False):
            return False, "This giveaway has already ended."
        if giveaway.get("paused", False):
            return False, "This giveaway is currently paused."

        req_role_id = giveaway.get("required_role_id")
        if req_role_id and member:
            has_role = any(str(r.id) == str(req_role_id) for r in getattr(member, "roles", []))
            if not has_role:
                return False, "You lack the required role to enter."

        entries = list(giveaway.get("entries", []))
        uid = str(user_id)
        if uid in entries:
            return False, "You have already entered this giveaway."

        entries.append(uid)
        giveaway["entries"] = entries
        db.save_giveaway(message_id, giveaway)
        return True, f"Successfully entered the giveaway for {giveaway.get('prize')}!"

    async def end_giveaway(self, message_id: str) -> List[str]:
        db = self.db or get_feature_db()
        giveaway = db.get_giveaway(message_id)
        if not giveaway or giveaway.get("ended", False):
            return []

        giveaway["ended"] = True
        entries = list(giveaway.get("entries", []))
        num_winners = max(1, giveaway.get("winners_count", 1))

        if not entries:
            db.save_giveaway(message_id, giveaway)
            return []

        winners = random.sample(entries, min(num_winners, len(entries)))
        giveaway["winners"] = winners
        db.save_giveaway(message_id, giveaway)
        return winners

    async def reroll_giveaway(self, message_id: str) -> List[str]:
        db = self.db or get_feature_db()
        giveaway = db.get_giveaway(message_id)
        if not giveaway:
            return []

        entries = list(giveaway.get("entries", []))
        previous_winners = set(giveaway.get("winners", []))
        eligible = [uid for uid in entries if uid not in previous_winners]

        if not eligible:
            return []

        num_winners = max(1, giveaway.get("winners_count", 1))
        new_winners = random.sample(eligible, min(num_winners, len(eligible)))
        giveaway["winners"] = new_winners
        db.save_giveaway(message_id, giveaway)
        return new_winners

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
        giveaway["winners"] = winner_ids
        db.save_giveaway(message_id, giveaway)
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
            if g.get("end_time", 0) <= now and not g.get("ended", False) and not g.get("paused", False):
                await GiveawayManager.finish_giveaway(bot, g["message_id"])


def register_giveaway_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    @tree.command(name="giveaway", description="Create and manage server giveaways 🎉")
    @app_commands.describe(
        action="Action (create, end, reroll, pause, resume, cancel, list, info)",
        duration="Duration for giveaway (e.g. 10m, 2h, 1d) [create]",
        prize="Prize description [create]",
        winners="Number of winners (default 1) [create]",
        channel="Target channel for announcement (default: current) [create]",
        required_role="Role required to participate (optional) [create]",
        min_account_days="Minimum Discord account age in days (optional) [create]",
        min_server_days="Minimum server membership in days (optional) [create]",
        message_id="Message ID of the giveaway (for end, reroll, pause, resume, cancel, info)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Create Giveaway", value="create"),
        app_commands.Choice(name="End Giveaway Early", value="end"),
        app_commands.Choice(name="Reroll Winners", value="reroll"),
        app_commands.Choice(name="Pause Giveaway", value="pause"),
        app_commands.Choice(name="Resume Giveaway", value="resume"),
        app_commands.Choice(name="Cancel Giveaway", value="cancel"),
        app_commands.Choice(name="List Giveaways", value="list"),
        app_commands.Choice(name="Giveaway Info", value="info"),
    ])
    async def slash_giveaway(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        duration: Optional[str] = None,
        prize: Optional[str] = None,
        winners: Optional[int] = 1,
        channel: Optional[discord.TextChannel] = None,
        required_role: Optional[discord.Role] = None,
        min_account_days: Optional[int] = 0,
        min_server_days: Optional[int] = 0,
        message_id: Optional[str] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You require **Manage Server** permission to manage giveaways.", ephemeral=True)
            return

        target_channel = channel or interaction.channel

        if action.value == "create":
            if not duration or not prize:
                await interaction.response.send_message("❌ Please specify both `duration` (e.g. `10m`, `2h`, `1d`) and `prize`.", ephemeral=True)
                return

            seconds = parse_duration(duration)
            if not seconds or seconds < 10:
                await interaction.response.send_message("❌ Invalid duration. Examples: `30s`, `10m`, `2h`, `1d`.", ephemeral=True)
                return

            end_timestamp = time.time() + seconds
            num_w = max(1, min(20, winners or 1))

            req_role_text = f"\n**Required Role:** {required_role.mention}" if required_role else ""
            acc_age_text = f"\n**Min Account Age:** {min_account_days} days" if min_account_days and min_account_days > 0 else ""
            srv_age_text = f"\n**Min Server Membership:** {min_server_days} days" if min_server_days and min_server_days > 0 else ""

            embed = discord.Embed(
                title=f"🎉 GIVEAWAY: {prize}!",
                description=f"Click **Enter Giveaway** below to participate!\n\n"
                            f"**Winners:** {num_w}\n"
                            f"**Ends:** <t:{int(end_timestamp)}:R> (<t:{int(end_timestamp)}:f>)\n"
                            f"**Hosted by:** {interaction.user.mention}"
                            f"{req_role_text}{acc_age_text}{srv_age_text}",
                color=0xf43f5e
            )
            embed.set_footer(text="Kazumi Giveaway System 🌸")

            view = GiveawayEntryView("pending")
            msg = await target_channel.send(embed=embed, view=view)

            # Store in database
            giveaway_data = {
                "message_id": str(msg.id),
                "channel_id": str(target_channel.id),
                "guild_id": str(interaction.guild_id),
                "host_id": str(interaction.user.id),
                "prize": prize,
                "winners_count": num_w,
                "end_time": end_timestamp,
                "required_role_id": str(required_role.id) if required_role else None,
                "min_account_days": min_account_days or 0,
                "min_server_days": min_server_days or 0,
                "entries": [],
                "winners": [],
                "ended": False,
                "paused": False
            }
            db.save_giveaway(str(msg.id), giveaway_data)
            await interaction.response.send_message(f"✅ Giveaway created successfully in {target_channel.mention}!", ephemeral=True)

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
            
            existing_winners = set(g.get("winners", []))
            eligible_candidates = [uid for uid in g["entries"] if uid not in existing_winners]
            if not eligible_candidates:
                eligible_candidates = g["entries"] # fallback if everyone won
            
            winner = random.choice(eligible_candidates)
            g.setdefault("winners", []).append(winner)
            db.save_giveaway(message_id.strip(), g)

            ch = bot.get_channel(int(g["channel_id"]))
            if ch:
                await ch.send(f"🎉 **Reroll Winner:** Congratulations <@{winner}>! You won **{g['prize']}**! 🌸")
            await interaction.response.send_message(f"✅ Rerolled new winner: <@{winner}>!", ephemeral=True)

        elif action.value == "pause":
            if not message_id:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway.", ephemeral=True)
                return
            g = db.get_giveaway(message_id.strip())
            if not g:
                await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True)
                return
            g["paused"] = True
            db.save_giveaway(message_id.strip(), g)
            await interaction.response.send_message("⏸️ Giveaway paused. Entries and auto-completion are halted.", ephemeral=True)

        elif action.value == "resume":
            if not message_id:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway.", ephemeral=True)
                return
            g = db.get_giveaway(message_id.strip())
            if not g:
                await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True)
                return
            g["paused"] = False
            db.save_giveaway(message_id.strip(), g)
            await interaction.response.send_message("▶️ Giveaway resumed.", ephemeral=True)

        elif action.value == "cancel":
            if not message_id:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway.", ephemeral=True)
                return
            g = db.get_giveaway(message_id.strip())
            if g:
                g["ended"] = True
                db.save_giveaway(message_id.strip(), g)
            await interaction.response.send_message("✅ Giveaway cancelled.", ephemeral=True)

        elif action.value == "list":
            guild_giveaways = db.get_guild_giveaways(str(interaction.guild_id))
            if not guild_giveaways:
                await interaction.response.send_message("ℹ️ No giveaways recorded in this server.", ephemeral=True)
                return
            embed = discord.Embed(title=f"🎉 Giveaways • {interaction.guild.name}", color=0xf43f5e)
            active_lines = []
            ended_lines = []
            for g in guild_giveaways[-10:]:
                mid = g.get("message_id", "?")
                prize_name = g.get("prize", "Gift")
                entries_cnt = len(g.get("entries", []))
                t_str = f"<t:{int(g.get('end_time', 0))}:R>"
                if g.get("ended", False):
                    ended_lines.append(f"• `{mid}`: **{prize_name}** ({entries_cnt} entries) — Ended")
                else:
                    status = "⏸️ Paused" if g.get("paused") else f"Ends {t_str}"
                    active_lines.append(f"• `{mid}`: **{prize_name}** ({entries_cnt} entries) — {status}")

            if active_lines:
                embed.add_field(name="🌟 Active Giveaways", value="\n".join(active_lines), inline=False)
            if ended_lines:
                embed.add_field(name="📜 Concluded Giveaways", value="\n".join(ended_lines), inline=False)
            embed.set_footer(text="Kazumi Giveaway System 🌸")
            await interaction.response.send_message(embed=embed)

        elif action.value == "info":
            if not message_id:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway.", ephemeral=True)
                return
            g = db.get_giveaway(message_id.strip())
            if not g:
                await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True)
                return
            embed = discord.Embed(title=f"🎉 Giveaway Info: {g.get('prize')}", color=0x38bdf8)
            embed.add_field(name="Message ID", value=f"`{g.get('message_id')}`", inline=True)
            embed.add_field(name="Host", value=f"<@{g.get('host_id')}>", inline=True)
            embed.add_field(name="Winners Count", value=f"**{g.get('winners_count', 1)}**", inline=True)
            embed.add_field(name="Total Entries", value=f"👥 **{len(g.get('entries', []))}**", inline=True)
            embed.add_field(name="Status", value="Ended" if g.get("ended") else ("Paused" if g.get("paused") else "Active"), inline=True)
            embed.add_field(name="End Time", value=f"<t:{int(g.get('end_time', 0))}:f>", inline=True)
            if g.get("required_role_id"):
                embed.add_field(name="Required Role", value=f"<@&{g['required_role_id']}>", inline=True)
            if g.get("winners"):
                w_str = ", ".join([f"<@{w}>" for w in g["winners"]])
                embed.add_field(name="Selected Winners", value=w_str, inline=False)
            embed.set_footer(text="Kazumi Giveaway System 🌸")
            await interaction.response.send_message(embed=embed)

