"""
🌸 Kazumi Discord Features — Server Info & Utility Commands Suite
Clean, stylized Discord embeds for server information and everyday utilities:
- Server Info: /serverinfo, /userinfo, /avatar, /roleinfo, /channelinfo, /permissions
- Utilities: /ping, /uptime, /botinfo, /poll, /announce, /remind, /time
"""

import time
import platform
from datetime import datetime, timezone
from typing import Optional, List

import discord
from discord import app_commands
from discord.ext import commands

from discord_features.database import get_feature_db

BOT_START_TIME = time.time()


def parse_simple_duration(time_str: str) -> Optional[float]:
    import re
    m = re.match(r"^(\d+)\s*([smhd])$", time_str.strip().lower())
    if not m:
        return None
    val = int(m.group(1))
    unit = m.group(2)
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return float(val * mult[unit])


def register_info_and_utility_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    # --- Ping ---
    @tree.command(name="ping", description="Check Kazumi's latency and gateway heartbeat 🏓")
    async def slash_ping(interaction: discord.Interaction):
        latency_ms = round(bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"**Gateway Latency:** `{latency_ms}ms`\n**Status:** Online & Attentive 🌸",
            color=0x34d399
        )
        await interaction.response.send_message(embed=embed)

    # --- Uptime ---
    @tree.command(name="uptime", description="Check how long Kazumi has been continuously online ⏱️")
    async def slash_uptime(interaction: discord.Interaction):
        elapsed = int(time.time() - BOT_START_TIME)
        days = elapsed // 86400
        hours = (elapsed % 86400) // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60

        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s" if days > 0 else f"{hours}h {minutes}m {seconds}s"
        embed = discord.Embed(
            title="⏱️ Kazumi System Uptime",
            description=f"Online continuously for: **{uptime_str}**\nStarted: <t:{int(BOT_START_TIME)}:R>",
            color=0xa855f7
        )
        embed.set_footer(text="Kazumi Companion 24/7 🌸")
        await interaction.response.send_message(embed=embed)

    # --- Bot Info ---
    @tree.command(name="botinfo", description="View technical information and statistics about Kazumi 🌸")
    async def slash_botinfo(interaction: discord.Interaction):
        total_members = sum(g.member_count or 0 for g in bot.guilds)
        embed = discord.Embed(
            title="🌸 Kazumi AI Companion • System Information",
            description="Kazumi is an intelligent, emotionally adaptive AI companion bot designed for cozy chat, intelligent server moderation, and community engagement.",
            color=0xc084fc
        )
        embed.add_field(name="Servers Connected", value=f"🏰 **{len(bot.guilds)}**", inline=True)
        embed.add_field(name="Total Members", value=f"👥 **{total_members}**", inline=True)
        embed.add_field(name="Gateway Latency", value=f"⚡ **{round(bot.latency * 1000)}ms**", inline=True)
        embed.add_field(name="Python Runtime", value=f"🐍 **{platform.python_version()}**", inline=True)
        embed.add_field(name="Discord.py", value=f"📦 **{discord.__version__}**", inline=True)
        embed.add_field(name="System OS", value=f"💻 **{platform.system()} {platform.release()}**", inline=True)
        embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user else None)
        embed.set_footer(text="Developed with love for Discord communities 🌸")
        await interaction.response.send_message(embed=embed)

    # --- Server Info ---
    @tree.command(name="serverinfo", description="View detailed server information and statistics 🏰")
    async def slash_serverinfo(interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        g = interaction.guild
        embed = discord.Embed(
            title=f"🏰 {g.name}",
            description=f"**Server ID:** `{g.id}`\n**Owner:** <@{g.owner_id}>\n**Created:** <t:{int(g.created_at.timestamp())}:D> (<t:{int(g.created_at.timestamp())}:R>)",
            color=0x38bdf8
        )
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)

        embed.add_field(name="Members", value=f"👥 **{g.member_count}**", inline=True)
        embed.add_field(name="Roles", value=f"🎭 **{len(g.roles)}**", inline=True)
        embed.add_field(name="Channels", value=f"💬 **{len(g.channels)}**", inline=True)
        embed.add_field(name="Boost Level", value=f"🚀 **Level {g.premium_tier}** ({g.premium_subscription_count} boosts)", inline=True)
        embed.add_field(name="Verification Level", value=f"🛡️ **{str(g.verification_level).capitalize()}**", inline=True)
        await interaction.response.send_message(embed=embed)

    # --- User Info ---
    @tree.command(name="userinfo", description="View profile details, roles, and join dates for a member 👤")
    @app_commands.describe(user="The member to inspect (defaults to yourself)")
    async def slash_userinfo(interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or (interaction.user if isinstance(interaction.user, discord.Member) else None)
        if not target or not interaction.guild:
            await interaction.response.send_message("Please use this command within a server.", ephemeral=True)
            return

        roles_list = [r.mention for r in target.roles if r.name != "@everyone"]
        roles_str = ", ".join(roles_list[:10]) if roles_list else "None"

        embed = discord.Embed(
            title=f"👤 {target.display_name} ({target.name})",
            description=f"**User ID:** `{target.id}`\n**Mention:** {target.mention}",
            color=0xf472b6
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Account Created", value=f"<t:{int(target.created_at.timestamp())}:f>\n(<t:{int(target.created_at.timestamp())}:R>)", inline=True)
        if target.joined_at:
            embed.add_field(name="Joined Server", value=f"<t:{int(target.joined_at.timestamp())}:f>\n(<t:{int(target.joined_at.timestamp())}:R>)", inline=True)
        embed.add_field(name=f"Roles ({len(roles_list)})", value=roles_str, inline=False)
        await interaction.response.send_message(embed=embed)

    # --- Avatar ---
    @tree.command(name="avatar", description="Display the full-resolution avatar of a user 🖼️")
    @app_commands.describe(user="The user whose avatar to view")
    async def slash_avatar(interaction: discord.Interaction, user: Optional[discord.User] = None):
        target = user or interaction.user
        embed = discord.Embed(
            title=f"🖼️ {target.display_name}'s Avatar",
            color=0xc084fc
        )
        embed.set_image(url=target.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name} 🌸")
        await interaction.response.send_message(embed=embed)

    # --- Role Info ---
    @tree.command(name="roleinfo", description="View information about a server role 🎭")
    @app_commands.describe(role="The role to inspect")
    async def slash_roleinfo(interaction: discord.Interaction, role: discord.Role):
        embed = discord.Embed(
            title=f"🎭 Role: {role.name}",
            description=f"**Role ID:** `{role.id}`\n**Mention:** {role.mention}\n**Color:** `{role.color}`",
            color=role.color if role.color.value != 0 else 0x818cf8
        )
        embed.add_field(name="Members with Role", value=f"👥 **{len(role.members)}**", inline=True)
        embed.add_field(name="Position in Hierarchy", value=f"📊 **{role.position}**", inline=True)
        embed.add_field(name="Hoisted / Separate", value=f"{'✅ Yes' if role.hoist else '❌ No'}", inline=True)
        embed.add_field(name="Mentionable", value=f"{'✅ Yes' if role.mentionable else '❌ No'}", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(role.created_at.timestamp())}:R>", inline=True)
        await interaction.response.send_message(embed=embed)

    # --- Channel Info ---
    @tree.command(name="channelinfo", description="View information about a channel 💬")
    @app_commands.describe(channel="The channel to inspect (defaults to current channel)")
    async def slash_channelinfo(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        ch = channel or interaction.channel
        embed = discord.Embed(
            title=f"💬 #{ch.name}",
            description=f"**Channel ID:** `{ch.id}`\n**Mention:** {ch.mention}\n**Topic:** {getattr(ch, 'topic', 'None') or 'None'}",
            color=0x38bdf8
        )
        embed.add_field(name="Category", value=f"📁 **{ch.category.name if ch.category else 'None'}**", inline=True)
        embed.add_field(name="Position", value=f"📊 **{ch.position}**", inline=True)
        embed.add_field(name="Slowmode Delay", value=f"⏱️ **{getattr(ch, 'slowmode_delay', 0)}s**", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(ch.created_at.timestamp())}:R>", inline=True)
        await interaction.response.send_message(embed=embed)

    # --- Permissions ---
    @tree.command(name="permissions", description="View key permissions for a member in this channel 🔑")
    @app_commands.describe(user="The member to check (defaults to yourself)")
    async def slash_permissions(interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or (interaction.user if isinstance(interaction.user, discord.Member) else None)
        if not target or not interaction.guild:
            await interaction.response.send_message("Please use this command in a server channel.", ephemeral=True)
            return

        perms = interaction.channel.permissions_for(target)
        checks = [
            ("Administrator", perms.administrator),
            ("Manage Server", perms.manage_guild),
            ("Manage Channels", perms.manage_channels),
            ("Manage Messages", perms.manage_messages),
            ("Moderate Members", perms.moderate_members),
            ("Kick Members", perms.kick_members),
            ("Ban Members", perms.ban_members),
            ("Send Messages", perms.send_messages),
            ("Attach Files", perms.attach_files),
            ("Embed Links", perms.embed_links)
        ]
        lines = [f"{'✅' if val else '❌'} {name}" for name, val in checks]
        embed = discord.Embed(
            title=f"🔑 Channel Permissions • {target.display_name}",
            description="\n".join(lines),
            color=0x6366f1
        )
        embed.set_footer(text=f"Channel: #{interaction.channel.name} 🌸")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Poll ---
    @tree.command(name="poll", description="Create an interactive reaction poll 📊")
    @app_commands.describe(
        question="Poll question to ask",
        option1="Option 1",
        option2="Option 2",
        option3="Option 3 (optional)",
        option4="Option 4 (optional)",
        option5="Option 5 (optional)"
    )
    async def slash_poll(
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: Optional[str] = None,
        option4: Optional[str] = None,
        option5: Optional[str] = None
    ):
        options = [o for o in [option1, option2, option3, option4, option5] if o]
        emoji_numbers = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

        lines = [f"{emoji_numbers[i]} **{options[i]}**" for i in range(len(options))]
        embed = discord.Embed(
            title=f"📊 Poll: {question}",
            description="\n\n".join(lines),
            color=0x38bdf8
        )
        embed.set_footer(text=f"Poll created by {interaction.user.display_name} 🌸 • Vote below!")
        embed.timestamp = datetime.now(timezone.utc)

        msg = await interaction.channel.send(embed=embed)
        for i in range(len(options)):
            try:
                await msg.add_reaction(emoji_numbers[i])
            except Exception:
                pass

        await interaction.response.send_message("✅ Poll created!", ephemeral=True)


    # --- Remind ---
    @tree.command(name="remind", description="Set a reminder for yourself ⏰")
    @app_commands.describe(duration="When to remind you (e.g. 10m, 2h, 1d)", text="What should Kazumi remind you of?")
    async def slash_remind(interaction: discord.Interaction, duration: str, text: str):
        seconds = parse_simple_duration(duration)
        if not seconds or seconds < 10:
            await interaction.response.send_message("❌ Please provide a valid duration (e.g. `5m`, `1h`, `2d`). Minimum 10 seconds.", ephemeral=True)
            return

        due_timestamp = time.time() + seconds
        db.add_reminder(str(interaction.user.id), str(interaction.channel_id), due_timestamp, text)

        embed = discord.Embed(
            title="⏰ Reminder Set!",
            description=f"I will remind you <t:{int(due_timestamp)}:R>:\n>>> **{text}**",
            color=0xf59e0b
        )
        embed.set_footer(text="Kazumi Reminders 🌸")
        await interaction.response.send_message(embed=embed)

    # --- Time ---
    @tree.command(name="time", description="Check current UTC and global server time 🌍")
    async def slash_time(interaction: discord.Interaction):
        now_utc = datetime.now(timezone.utc)
        embed = discord.Embed(
            title="🌍 Current Time",
            description=f"**UTC:** `{now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}`\n"
                        f"**Discord Timestamp:** <t:{int(now_utc.timestamp())}:F>\n"
                        f"**Relative:** <t:{int(now_utc.timestamp())}:R>",
            color=0x38bdf8
        )
        await interaction.response.send_message(embed=embed)
