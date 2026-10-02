"""
================================================================================
🎙️ KAZUMI DISCORD STAGE & EVENT MANAGEMENT SYSTEM
================================================================================
Comprehensive Stage channel operations and scheduled Discord event management:
- Stage channel creation & instance lifecycle (start, topic, end)
- Speaker permissions (speaker add/unsuppress, speaker remove/suppress, invite)
- Scheduled Discord events integration on Stage channels
- Automatic announcement generation when scheduled events are published
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any

import discord
from discord import app_commands
from discord.ext import commands

from .giveaways import parse_duration
from .announcements import build_announcement_embed

logger = logging.getLogger("KazumiStage")


def setup_stage_commands(tree: app_commands.CommandTree, bot: commands.Bot, db: Any):
    """Registers full Stage and Event management command suite under /stage."""

    stage_group = app_commands.Group(
        name="stage",
        description="Manage Discord Stage channels, speakers, and events 🎙️"
    )
    speaker_subgroup = app_commands.Group(
        name="speaker",
        description="Manage stage speakers and permissions 🎤",
        parent=stage_group
    )
    event_subgroup = app_commands.Group(
        name="event",
        description="Manage scheduled Discord Stage events 📅",
        parent=stage_group
    )

    # 1. /stage create
    @stage_group.command(name="create", description="Create a new Discord Stage channel 🎙️")
    @app_commands.describe(
        name="Name for the Stage channel (e.g. community-stage)",
        category="Category to place Stage in (optional)",
        topic="Initial topic for the Stage (optional)"
    )
    async def slash_stage_create(
        interaction: discord.Interaction,
        name: str,
        category: Optional[discord.CategoryChannel] = None,
        topic: Optional[str] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ You require **Manage Channels** permission to create Stage channels.", ephemeral=True)
            return

        bot_member = interaction.guild.me
        if not bot_member.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ I lack the **Manage Channels** permission to create Stage channels.", ephemeral=True)
            return

        try:
            stage_ch = await interaction.guild.create_stage_channel(
                name=name,
                category=category,
                topic=topic or "Community Discussion",
                reason=f"Created by {interaction.user} via Kazumi"
            )
            embed = discord.Embed(
                title="🎙️ Stage Channel Created",
                description=f"Successfully created {stage_ch.mention}!\n\nUse `/stage start` when you are ready to open the Stage for speakers and listeners.",
                color=0x8b5cf6
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to create Stage channel: {e}", ephemeral=True)

    # 2. /stage start
    @stage_group.command(name="start", description="Start an active Stage instance on a stage channel 🚀")
    @app_commands.describe(
        channel="The Stage channel to start",
        topic="Topic for the Stage instance"
    )
    async def slash_stage_start(
        interaction: discord.Interaction,
        channel: discord.StageChannel,
        topic: str
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ You require **Manage Channels** permission.", ephemeral=True)
            return

        if channel.instance:
            await interaction.response.send_message(f"⚠️ A Stage instance is already active in {channel.mention}: **{channel.instance.topic}**", ephemeral=True)
            return

        try:
            instance = await channel.create_instance(
                topic=topic,
                privacy_level=discord.StagePrivacyLevel.guild_only,
                reason=f"Stage started by {interaction.user}"
            )
            embed = discord.Embed(
                title="🎙️ Stage is Now LIVE!",
                description=f"**Topic:** {topic}\n**Channel:** {channel.mention}\n**Host:** {interaction.user.mention}\n\nMembers can now tune in as listeners or request to speak!",
                color=0x10b981
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to start Stage instance: {e}", ephemeral=True)

    # 3. /stage topic
    @stage_group.command(name="topic", description="Update the topic of an active Stage instance 📝")
    @app_commands.describe(
        channel="The Stage channel",
        new_topic="New topic for the Stage"
    )
    async def slash_stage_topic(
        interaction: discord.Interaction,
        channel: discord.StageChannel,
        new_topic: str
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ You require **Manage Channels** permission.", ephemeral=True)
            return

        if not channel.instance:
            await interaction.response.send_message(f"❌ No active Stage instance is currently running in {channel.mention}.", ephemeral=True)
            return

        try:
            await channel.instance.edit(topic=new_topic)
            await interaction.response.send_message(f"✅ Stage topic updated to: **{new_topic}**", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to edit Stage topic: {e}", ephemeral=True)

    # 4. /stage invite
    @stage_group.command(name="invite", description="Invite a member to speak on Stage 💌")
    @app_commands.describe(
        member="Member to invite as a speaker",
        channel="The Stage channel"
    )
    async def slash_stage_invite(
        interaction: discord.Interaction,
        member: discord.Member,
        channel: discord.StageChannel
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ You require **Manage Channels** permission.", ephemeral=True)
            return

        try:
            await member.send(f"🎙️ You have been invited to speak on Stage in **{interaction.guild.name}** ({channel.mention}) by {interaction.user.display_name}!")
            await interaction.response.send_message(f"✅ Invitation sent to {member.mention}!", ephemeral=True)
        except Exception:
            await interaction.response.send_message(f"⚠️ Sent notice in channel: {member.mention}, you've been invited to speak on Stage in {channel.mention}!", ephemeral=False)

    # 5. /stage speaker add (unsuppress)
    @speaker_subgroup.command(name="add", description="Promote a listener to speaker status 🎤")
    @app_commands.describe(member="Member in stage channel to promote to speaker")
    async def slash_speaker_add(interaction: discord.Interaction, member: discord.Member):
        if not interaction.guild or not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ You require **Manage Channels** permission.", ephemeral=True)
            return

        if not member.voice or not isinstance(member.voice.channel, discord.StageChannel):
            await interaction.response.send_message(f"❌ {member.mention} is not currently connected to a Stage channel.", ephemeral=True)
            return

        try:
            await member.edit(suppress=False)
            await interaction.response.send_message(f"🎤 {member.mention} is now a speaker on Stage!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to set speaker status: {e}", ephemeral=True)

    # 6. /stage speaker remove (suppress)
    @speaker_subgroup.command(name="remove", description="Move a speaker back to audience/listener status 👥")
    @app_commands.describe(member="Member in stage to move to audience")
    async def slash_speaker_remove(interaction: discord.Interaction, member: discord.Member):
        if not interaction.guild or not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ You require **Manage Channels** permission.", ephemeral=True)
            return

        if not member.voice or not isinstance(member.voice.channel, discord.StageChannel):
            await interaction.response.send_message(f"❌ {member.mention} is not in a Stage channel.", ephemeral=True)
            return

        try:
            await member.edit(suppress=True)
            await interaction.response.send_message(f"👥 {member.mention} has been moved to the audience.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to move to audience: {e}", ephemeral=True)

    # 7. /stage audience
    @stage_group.command(name="audience", description="View current audience statistics and speaker roster 📊")
    @app_commands.describe(channel="The Stage channel to check")
    async def slash_stage_audience(interaction: discord.Interaction, channel: discord.StageChannel):
        members = channel.members
        speakers = [m for m in members if m.voice and not m.voice.suppress]
        listeners = [m for m in members if m.voice and m.voice.suppress]

        embed = discord.Embed(
            title=f"🎙️ Stage Audience: #{channel.name}",
            description=f"**Active Topic:** {channel.instance.topic if channel.instance else 'No active instance'}\n\n"
                        f"**🎤 Speakers ({len(speakers)}):** {', '.join(m.display_name for m in speakers) or 'None'}\n"
                        f"**👥 Listeners ({len(listeners)}):** {len(listeners)} listening",
            color=0x8b5cf6
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # 8. /stage end
    @stage_group.command(name="end", description="End the active Stage instance ⏹️")
    @app_commands.describe(channel="The Stage channel to end")
    async def slash_stage_end(interaction: discord.Interaction, channel: discord.StageChannel):
        if not interaction.guild or not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ You require **Manage Channels** permission.", ephemeral=True)
            return

        if not channel.instance:
            await interaction.response.send_message(f"❌ No active Stage instance found in {channel.mention}.", ephemeral=True)
            return

        try:
            await channel.instance.delete(reason=f"Ended by {interaction.user}")
            embed = discord.Embed(
                title="⏹️ Stage Session Ended",
                description=f"The Stage session in {channel.mention} has concluded. Thank you to all speakers and listeners! 🌸",
                color=0x94a3b8
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to end Stage: {e}", ephemeral=True)

    # =========================================================================
    # Scheduled Event Subgroup (/stage event ...)
    # =========================================================================
    @event_subgroup.command(name="create", description="Schedule a Discord event on a Stage channel 📅")
    @app_commands.describe(
        title="Event name / title",
        channel="Stage channel where event will occur",
        start_time_offset="When event starts (e.g. 2h, 1d, 3d)",
        description="Event description",
        announce_to="Optional channel to post an announcement",
        ping_role="Optional role to mention in announcement"
    )
    async def slash_event_create(
        interaction: discord.Interaction,
        title: str,
        channel: discord.StageChannel,
        start_time_offset: str,
        description: str,
        announce_to: Optional[discord.TextChannel] = None,
        ping_role: Optional[discord.Role] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_events:
            await interaction.response.send_message("❌ You require **Manage Events** permission to schedule events.", ephemeral=True)
            return

        secs = parse_duration(start_time_offset)
        if not secs or secs < 60:
            await interaction.response.send_message("❌ Invalid start time format. Examples: `2h`, `1d`, `3d`.", ephemeral=True)
            return

        start_dt = datetime.now(timezone.utc) + timedelta(seconds=secs)
        end_dt = start_dt + timedelta(hours=2)

        try:
            event = await interaction.guild.create_scheduled_event(
                name=title,
                channel=channel,
                start_time=start_dt,
                end_time=end_dt,
                description=description,
                entity_type=discord.EntityType.stage_instance,
                privacy_level=discord.PrivacyLevel.guild_only,
                reason=f"Created by {interaction.user} via Kazumi"
            )

            response_msg = f"📅 **Stage Event Created!**\n**Event:** [{event.name}]({event.url})\n**Starts:** <t:{int(start_dt.timestamp())}:R> (<t:{int(start_dt.timestamp())}:f>)"

            # Auto-announcement integration
            if announce_to:
                ann_embed = build_announcement_embed(
                    title=f"Upcoming Event: {title}",
                    message=f"{description}\n\n**Where:** {channel.mention}\n**When:** <t:{int(start_dt.timestamp())}:F> (<t:{int(start_dt.timestamp())}:R>)\n**Event Link:** [Click to RSVP]({event.url})",
                    preset="event",
                    author_name=interaction.guild.name
                )
                outside = ping_role.mention if ping_role else None
                await announce_to.send(content=outside, embed=ann_embed)
                response_msg += f"\n📢 **Announcement published in** {announce_to.mention}!"

            await interaction.response.send_message(response_msg, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to schedule Stage event: {e}", ephemeral=True)

    @event_subgroup.command(name="list", description="List upcoming scheduled events in this server 📋")
    async def slash_event_list(interaction: discord.Interaction):
        events = interaction.guild.scheduled_events
        if not events:
            await interaction.response.send_message("No scheduled events currently scheduled in this server! 🌸", ephemeral=True)
            return

        lines = []
        for ev in sorted(events, key=lambda x: x.start_time):
            start_ts = int(ev.start_time.timestamp())
            lines.append(f"• **[{ev.name}]({ev.url})**\n  Starts: <t:{start_ts}:R> (<t:{start_ts}:f>)\n  Channel: {ev.channel.mention if ev.channel else 'External'}")

        embed = discord.Embed(
            title="📅 Upcoming Server Events",
            description="\n\n".join(lines),
            color=0x8b5cf6
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @event_subgroup.command(name="cancel", description="Cancel a scheduled Discord event 🚫")
    @app_commands.describe(event_id="The ID of the scheduled event to cancel")
    async def slash_event_cancel(interaction: discord.Interaction, event_id: str):
        if not interaction.guild or not interaction.user.guild_permissions.manage_events:
            await interaction.response.send_message("❌ You require **Manage Events** permission.", ephemeral=True)
            return

        try:
            event = interaction.guild.get_scheduled_event(int(event_id))
            if not event:
                await interaction.response.send_message(f"❌ Event with ID `{event_id}` not found.", ephemeral=True)
                return

            await event.cancel()
            await interaction.response.send_message(f"✅ Event **{event.name}** has been cancelled.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to cancel event: {e}", ephemeral=True)

    tree.add_command(stage_group)
    logger.info("Stage and event management slash commands registered successfully.")
