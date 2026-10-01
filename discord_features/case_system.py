# -*- coding: utf-8 -*-
"""
🌸 Kazumi Case Management & Moderator Utilities
Provides:
- Moderation Case System (Case #1001, #1002...) with full tracking & search
- Private Staff Notes (/modnote, /modnotes) hidden from normal members
- Message & Member Reporting System (/report, Context Menu, Report Queue)
- User Appeals System (/appeal, Appeal Review Queue)
- Complete Moderator History (/modhistory)
"""

import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import discord
from discord import app_commands
from discord.ext import commands

from .database import FeatureDB, get_feature_db

logger = logging.getLogger("KazumiCaseSystem")


class CaseManager:
    """Manages creation, retrieval, and formatting of moderation cases."""

    def __init__(self, db: FeatureDB):
        self.db = db

    def log_case(
        self,
        guild_id: int,
        user_id: int,
        moderator_id: int,
        action: str,
        reason: str,
        duration: Optional[str] = None,
        evidence: Optional[str] = None
    ) -> int:
        case_id = self.db.create_case(
            guild_id=guild_id,
            user_id=user_id,
            moderator_id=moderator_id,
            action=action,
            reason=reason,
            duration=duration,
            evidence=evidence
        )
        logger.info(f"[CASE #{case_id}] Guild {guild_id}: {action} on User {user_id} by Mod {moderator_id}")
        return case_id

    def format_case_embed(self, case_data: Dict[str, Any], user: Optional[discord.User] = None, mod: Optional[discord.User] = None) -> discord.Embed:
        action = case_data.get("action", "ACTION").upper()
        case_id = case_data.get("case_id", 0)
        
        # Color coding by severity
        colors = {
            "WARN": 0xf59e0b,
            "TIMEOUT": 0xf97316,
            "UNTIMEOUT": 0x10b981,
            "KICK": 0xef4444,
            "SOFTBAN": 0xb91c1c,
            "BAN": 0x991b1b,
            "UNBAN": 0x10b981,
            "QUARANTINE": 0x8b5cf6,
            "UNQUARANTINE": 0x10b981,
            "VOICEKICK": 0x3b82f6,
            "CLEAR": 0x64748b,
            "SLOWMODE": 0x64748b,
            "LOCK": 0xef4444,
            "UNLOCK": 0x10b981
        }
        color = colors.get(action, 0xc084fc)

        user_str = f"{user.mention} (`{user.id}`)" if user else f"<@{case_data.get('user_id')}> (`{case_data.get('user_id')}`)"
        mod_str = f"{mod.mention} (`{mod.id}`)" if mod else f"<@{case_data.get('moderator_id')}> (`{case_data.get('moderator_id')}`)"

        embed = discord.Embed(
            title=f"📋 Case #{case_id} • {action}",
            color=color,
            timestamp=datetime.fromtimestamp(case_data.get("timestamp", time.time()), tz=timezone.utc)
        )
        embed.add_field(name="Target User", value=user_str, inline=True)
        embed.add_field(name="Moderator", value=mod_str, inline=True)
        if case_data.get("duration"):
            embed.add_field(name="Duration", value=f"`{case_data['duration']}`", inline=True)
        
        embed.add_field(name="Reason", value=case_data.get("reason", "No reason provided"), inline=False)
        if case_data.get("evidence"):
            embed.add_field(name="Evidence / Details", value=f"```{case_data['evidence'][:500]}```", inline=False)

        status = case_data.get("status", "active").capitalize()
        embed.set_footer(text=f"Status: {status} • Kazumi Guard Security Suite 🛡️")
        return embed


class ReportManager:
    """Handles member reports and moderation queue."""

    def __init__(self, db: FeatureDB):
        self.db = db

    def submit_report(
        self,
        guild_id: int,
        reporter_id: int,
        reported_id: int,
        channel_id: int,
        reason: str,
        message_id: Optional[int] = None,
        details: str = ""
    ) -> int:
        return self.db.create_report(
            guild_id=guild_id,
            reporter_id=reporter_id,
            reported_id=reported_id,
            channel_id=channel_id,
            message_id=message_id,
            reason=reason,
            details=details
        )


class AppealManager:
    """Handles moderation action appeals by penalized users."""

    def __init__(self, db: FeatureDB):
        self.db = db

    def submit_appeal(self, guild_id: int, user_id: int, case_id: int, reason: str) -> int:
        return self.db.create_appeal(
            guild_id=guild_id,
            user_id=user_id,
            case_id=case_id,
            reason=reason
        )


# =============================================================================
# Interactive UI Views for Cases, Reports, Appeals
# =============================================================================

class ReportResolutionView(discord.ui.View):
    """Buttons for staff to quickly resolve or dismiss a user report."""

    def __init__(self, guild_id: int, report_id: int, db: FeatureDB):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.report_id = report_id
        self.db = db

    @discord.ui.button(label="Investigate & Resolve", style=discord.ButtonStyle.success, emoji="✅", custom_id="report_resolve_btn")
    async def resolve_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You lack permission to resolve reports.", ephemeral=True)
            return

        self.db.resolve_report(self.guild_id, self.report_id, "resolved", interaction.user.id, "Staff investigated and resolved.")
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"✅ **Report #{self.report_id} Marked as RESOLVED** by {interaction.user.mention}.", view=self)

    @discord.ui.button(label="Dismiss Report", style=discord.ButtonStyle.secondary, emoji="❌", custom_id="report_dismiss_btn")
    async def dismiss_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You lack permission to dismiss reports.", ephemeral=True)
            return

        self.db.resolve_report(self.guild_id, self.report_id, "dismissed", interaction.user.id, "Dismissed as non-actionable.")
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"❌ **Report #{self.report_id} DISMISSED** by {interaction.user.mention}.", view=self)


class AppealReviewView(discord.ui.View):
    """Buttons for staff to approve or reject a moderation appeal."""

    def __init__(self, guild_id: int, appeal_id: int, db: FeatureDB):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.appeal_id = appeal_id
        self.db = db

    @discord.ui.button(label="Approve Appeal", style=discord.ButtonStyle.success, emoji="🕊️", custom_id="appeal_approve_btn")
    async def approve_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You lack permission to review appeals.", ephemeral=True)
            return

        self.db.review_appeal(self.guild_id, self.appeal_id, "approved", interaction.user.id, "Appeal accepted by moderation staff.")
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"🕊️ **Appeal #{self.appeal_id} APPROVED** by {interaction.user.mention}. Please revoke punishments accordingly.", view=self)

    @discord.ui.button(label="Reject Appeal", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="appeal_reject_btn")
    async def reject_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You lack permission to review appeals.", ephemeral=True)
            return

        self.db.review_appeal(self.guild_id, self.appeal_id, "rejected", interaction.user.id, "Appeal denied by moderation staff.")
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"🚫 **Appeal #{self.appeal_id} REJECTED** by {interaction.user.mention}.", view=self)


# =============================================================================
# Slash Commands Registration for Cases, Reports, Appeals, Notes
# =============================================================================

def register_case_commands(tree: app_commands.CommandTree, bot: commands.Bot, db: FeatureDB) -> None:
    case_mgr = CaseManager(db)
    report_mgr = ReportManager(db)
    appeal_mgr = AppealManager(db)

    # 1. /case <id>
    @tree.command(name="case", description="Look up details of a moderation case ID 📋")
    @app_commands.describe(case_id="The case ID number (e.g. 1001)")
    async def slash_case(interaction: discord.Interaction, case_id: int):
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need **Manage Messages** permission to view moderation cases.", ephemeral=True)
            return

        c_data = db.get_case(interaction.guild.id, case_id)
        if not c_data:
            await interaction.response.send_message(f"🔍 Case **#{case_id}** was not found in this server.", ephemeral=True)
            return

        target_u = bot.get_user(int(c_data.get("user_id", 0)))
        mod_u = bot.get_user(int(c_data.get("moderator_id", 0)))
        embed = case_mgr.format_case_embed(c_data, target_u, mod_u)
        await interaction.response.send_message(embed=embed)

    # 2. /cases <@user>
    @tree.command(name="cases", description="View all moderation cases recorded for a member 📋")
    @app_commands.describe(user="The member to view cases for")
    async def slash_cases(interaction: discord.Interaction, user: discord.User):
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need **Manage Messages** permission to view cases.", ephemeral=True)
            return

        u_cases = db.get_user_cases(interaction.guild.id, user.id)
        if not u_cases:
            await interaction.response.send_message(f"✨ No moderation cases found for **{user.display_name}**.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📋 Moderation Cases • {user.display_name}",
            description=f"Showing latest {min(len(u_cases), 10)} of **{len(u_cases)}** case(s) on file:",
            color=0x3b82f6
        )
        for c in u_cases[:10]:
            cid = c.get("case_id")
            act = c.get("action")
            rsn = c.get("reason", "No reason")
            t_str = f"<t:{int(c.get('timestamp', time.time()))}:R>"
            embed.add_field(
                name=f"Case #{cid} • {act}",
                value=f"**Reason:** {rsn}\n**Date:** {t_str}\n**Mod:** <@{c.get('moderator_id')}>",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    # 3. /modnote <@user> <content>
    @tree.command(name="modnote", description="Add a private staff note to a user profile 📝")
    @app_commands.describe(user="User to add note for", content="The private note text")
    async def slash_modnote(interaction: discord.Interaction, user: discord.User, content: str):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        entry = db.add_mod_note(interaction.guild.id, user.id, interaction.user.id, content)
        embed = discord.Embed(
            title="📝 Staff Note Added",
            description=f"Added Note **#{entry['note_id']}** to {user.mention}:\n\n> {entry['content']}",
            color=0x8b5cf6
        )
        embed.set_footer(text="Private note • Visible only to authorized moderators")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # 4. /modnotes <@user>
    @tree.command(name="modnotes", description="View all private staff notes for a user 📝")
    @app_commands.describe(user="The member to view notes for")
    async def slash_modnotes(interaction: discord.Interaction, user: discord.User):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        notes = db.get_mod_notes(interaction.guild.id, user.id)
        if not notes:
            await interaction.response.send_message(f"📝 No private staff notes on file for **{user.display_name}**.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📝 Staff Notes • {user.display_name} (`{user.id}`)",
            description=f"Found **{len(notes)}** private note(s):",
            color=0x8b5cf6
        )
        for n in notes:
            nid = n.get("note_id")
            mod_id = n.get("moderator_id")
            t_str = f"<t:{int(n.get('timestamp', time.time()))}:R>"
            embed.add_field(
                name=f"Note #{nid} (By <@{mod_id}> • {t_str})",
                value=f"> {n.get('content')}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # 5. /modhistory <@user>
    @tree.command(name="modhistory", description="Comprehensive breakdown of member moderation history 🛡️")
    @app_commands.describe(user="The member to inspect")
    async def slash_modhistory(interaction: discord.Interaction, user: discord.User):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        cases = db.get_user_cases(interaction.guild.id, user.id)
        notes = db.get_mod_notes(interaction.guild.id, user.id)
        warns = db.get_warnings(interaction.guild.id, user.id)
        appeals = db.get_user_appeals(interaction.guild.id, user.id)
        is_quarantined = db.is_user_quarantined(interaction.guild.id, user.id)

        # Categorize actions
        warn_cnt = len(warns)
        timeout_cnt = sum(1 for c in cases if c.get("action") == "TIMEOUT")
        kick_cnt = sum(1 for c in cases if c.get("action") == "KICK")
        ban_cnt = sum(1 for c in cases if c.get("action") in ("BAN", "SOFTBAN"))

        embed = discord.Embed(
            title=f"🛡️ Complete Moderation History • {user.display_name}",
            description=f"Summary of all recorded infractions, notes, and staff actions for {user.mention} (`{user.id}`):",
            color=0xef4444 if (ban_cnt or is_quarantined) else 0x3b82f6
        )
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)

        embed.add_field(name="Warnings", value=f"⚠️ **{warn_cnt}**", inline=True)
        embed.add_field(name="Timeouts", value=f"⏳ **{timeout_cnt}**", inline=True)
        embed.add_field(name="Kicks / Bans", value=f"🔨 **{kick_cnt}k / {ban_cnt}b**", inline=True)
        embed.add_field(name="Total Cases", value=f"📋 **{len(cases)}**", inline=True)
        embed.add_field(name="Staff Notes", value=f"📝 **{len(notes)}**", inline=True)
        embed.add_field(name="Quarantine Status", value="🚨 **QUARANTINED**" if is_quarantined else "✅ Clean", inline=True)

        if cases:
            recent_cases = "\n".join([f"• `#{c['case_id']}` {c['action']}: {c.get('reason', '')[:40]}" for c in cases[:4]])
            embed.add_field(name="Recent Cases", value=recent_cases, inline=False)

        if notes:
            recent_notes = "\n".join([f"• Note #{n['note_id']}: {n['content'][:50]}" for n in notes[:3]])
            embed.add_field(name="Private Notes (Staff Only)", value=recent_notes, inline=False)

        embed.set_footer(text="Kazumi Guard • Confidential Staff Audit Report")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # 6. /report <@user> <reason> [details]
    @tree.command(name="report", description="Report a member or message violating server rules 🚩")
    @app_commands.describe(user="The member you are reporting", reason="Rule violated", details="Optional extra context")
    async def slash_report(interaction: discord.Interaction, user: discord.User, reason: str, details: Optional[str] = None):
        if not interaction.guild:
            await interaction.response.send_message("❌ Reports can only be made in servers.", ephemeral=True)
            return

        report_id = report_mgr.submit_report(
            guild_id=interaction.guild.id,
            reporter_id=interaction.user.id,
            reported_id=user.id,
            channel_id=interaction.channel_id,
            reason=reason,
            details=details or ""
        )

        # Notify user ephemerally
        await interaction.response.send_message(
            f"✅ **Report #{report_id} Submitted!** Our server moderators have been alerted and will review this matter. Thank you for keeping the community safe! 🌸",
            ephemeral=True
        )

        # Send alert card to logging / mod channel if configured
        g_settings = db.get_guild_settings(interaction.guild.id)
        log_ch_id = g_settings.get("log_channel_id")
        if log_ch_id:
            ch = interaction.guild.get_channel(int(log_ch_id))
            if ch:
                embed = discord.Embed(
                    title=f"🚨 New User Report #{report_id}",
                    color=0xf43f5e,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Reported User", value=f"{user.mention} (`{user.id}`)", inline=True)
                embed.add_field(name="Reporter", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
                embed.add_field(name="Channel", value=f"<#{interaction.channel_id}>", inline=True)
                embed.add_field(name="Violation / Reason", value=f"**{reason}**", inline=False)
                if details:
                    embed.add_field(name="Details", value=f"> {details}", inline=False)
                embed.set_footer(text=f"Report #{report_id} • Pending Review")
                view = ReportResolutionView(interaction.guild.id, report_id, db)
                try:
                    await ch.send(embed=embed, view=view)
                except Exception:
                    pass

    # 7. /appeal <case_id> <reason>
    @tree.command(name="appeal", description="Submit an appeal against a moderation punishment ⚖️")
    @app_commands.describe(case_id="The Case ID number you are appealing", reason="Why your punishment should be lifted")
    async def slash_appeal(interaction: discord.Interaction, case_id: int, reason: str):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return

        c_data = db.get_case(interaction.guild.id, case_id)
        if not c_data:
            await interaction.response.send_message(f"❌ Case **#{case_id}** was not found in this server.", ephemeral=True)
            return

        if str(c_data.get("user_id")) != str(interaction.user.id):
            await interaction.response.send_message("❌ You can only appeal cases issued against yourself.", ephemeral=True)
            return

        appeal_id = appeal_mgr.submit_appeal(interaction.guild.id, interaction.user.id, case_id, reason)
        await interaction.response.send_message(
            f"⚖️ **Appeal #{appeal_id} Received!** Your appeal for Case #{case_id} has been submitted to the moderation team for review.",
            ephemeral=True
        )

        # Notify mod log
        g_settings = db.get_guild_settings(interaction.guild.id)
        log_ch_id = g_settings.get("log_channel_id")
        if log_ch_id:
            ch = interaction.guild.get_channel(int(log_ch_id))
            if ch:
                embed = discord.Embed(
                    title=f"⚖️ New Moderation Appeal #{appeal_id}",
                    color=0x3b82f6,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Appellant", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
                embed.add_field(name="Case Appealed", value=f"`#{case_id}` ({c_data.get('action')})", inline=True)
                embed.add_field(name="Appellant's Explanation", value=f"> {reason}", inline=False)
                view = AppealReviewView(interaction.guild.id, appeal_id, db)
                try:
                    await ch.send(embed=embed, view=view)
                except Exception:
                    pass

    # 8. /modqueue
    @tree.command(name="modqueue", description="Inspect pending reports and appeals in the moderation queue 📥")
    async def slash_modqueue(interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        reports = db.get_pending_reports(interaction.guild.id)
        appeals = db.get_pending_appeals(interaction.guild.id)

        embed = discord.Embed(
            title="📥 Moderation Queue Overview",
            description=f"**Pending Reports:** `{len(reports)}` | **Pending Appeals:** `{len(appeals)}`",
            color=0xf59e0b
        )

        if reports:
            rep_lines = [f"• **Report #{r['report_id']}**: <@{r['reported_id']}> ({r['reason'][:30]})" for r in reports[:5]]
            embed.add_field(name="🚨 Reports Awaiting Review", value="\n".join(rep_lines), inline=False)

        if appeals:
            app_lines = [f"• **Appeal #{a['appeal_id']}**: <@{a['user_id']}> for Case `#{a['case_id']}`" for a in appeals[:5]]
            embed.add_field(name="⚖️ Appeals Awaiting Review", value="\n".join(app_lines), inline=False)

        if not reports and not appeals:
            embed.description = "✨ **Queue is completely clear!** No pending reports or appeals."

        await interaction.response.send_message(embed=embed, ephemeral=True)
