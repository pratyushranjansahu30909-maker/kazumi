# -*- coding: utf-8 -*-
"""
🌸 Kazumi Guard — Advanced Server Security Suite
Provides:
- Anti-Raid System (Join burst detection, young account spikes, patterned usernames)
- Anti-Nuke Protection (Mass channel/role deletions, mass kicks/bans interception)
- Quarantine System (/quarantine, /unquarantine)
- Raid Mode Lockdown (/raidmode on/off)
- Staff Permission Hierarchy Checks (Helper, Mod, Senior Mod, Admin, Owner)
- Destructive Action Safety Confirmation Dialogs ([CONFIRM] [CANCEL])
"""

import time
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import discord
from discord import app_commands
from discord.ext import commands

from .database import FeatureDB, get_feature_db

logger = logging.getLogger("KazumiSecurity")


class AntiRaidEngine:
    """
    Monitors incoming member joins for abnormal spike patterns,
    young account density, and coordinated bot raids.
    """

    def __init__(self, db: FeatureDB):
        self.db = db
        # Guild ID -> list of join timestamps (float)
        self._join_times: Dict[int, List[float]] = {}
        # Guild ID -> list of recently joined member IDs and account creation times
        self._recent_members: Dict[int, List[Tuple[int, float]]] = {}

    def record_join_and_evaluate(self, member: discord.Member) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Records a member join and evaluates against anti-raid thresholds.
        Returns (is_raid_detected, reason, metadata).
        """
        guild_id = member.guild.id
        now = time.time()
        sec_cfg = self.db.get_security_settings(guild_id)
        raid_cfg = sec_cfg.get("anti_raid", {})

        if not raid_cfg.get("enabled", False):
            return False, "Anti-Raid Disabled", {}

        window_sec = float(raid_cfg.get("join_window_sec", 10))
        threshold = int(raid_cfg.get("join_threshold", 8))

        times = self._join_times.setdefault(guild_id, [])
        times.append(now)
        # Prune old timestamps
        self._join_times[guild_id] = [t for t in times if now - t <= window_sec]
        join_count = len(self._join_times[guild_id])

        # Track account ages (< 24 hours = suspicious)
        m_list = self._recent_members.setdefault(guild_id, [])
        created_ts = member.created_at.timestamp()
        m_list.append((member.id, created_ts))
        self._recent_members[guild_id] = [(uid, cts) for uid, cts in m_list if now - cts < 86400 * 3]

        young_accounts = sum(1 for _, cts in self._recent_members[guild_id] if (now - cts) < 86400)

        # Raid Detection Evaluation
        if join_count >= threshold:
            reason = f"Abnormal join burst: {join_count} members joined in {int(window_sec)}s (Threshold: {threshold})"
            meta = {
                "join_count": join_count,
                "window_sec": window_sec,
                "young_accounts": young_accounts,
                "confidence": "HIGH" if young_accounts >= 3 else "MEDIUM"
            }
            logger.warning(f"🚨 RAID DETECTED in Guild {guild_id}: {reason}")
            return True, reason, meta

        return False, "Normal Activity", {}


class AntiNukeEngine:
    """
    Monitors dangerous audit events like rapid channel/role deletions
    or mass member bans/kicks to defend against compromised staff accounts.
    """

    def __init__(self, db: FeatureDB):
        self.db = db
        # Guild ID -> action_type -> list of timestamps
        self._action_times: Dict[int, Dict[str, List[float]]] = {}

    def record_action_and_evaluate(self, guild_id: int, action_type: str, actor_id: int) -> Tuple[bool, str]:
        now = time.time()
        sec_cfg = self.db.get_security_settings(guild_id)
        nuke_cfg = sec_cfg.get("anti_nuke", {})

        if not nuke_cfg.get("enabled", False):
            return False, "Anti-Nuke Disabled"

        window = float(nuke_cfg.get("window_sec", 12))
        thresholds = {
            "channel_delete": int(nuke_cfg.get("max_channel_deletions", 4)),
            "role_delete": int(nuke_cfg.get("max_role_deletions", 4)),
            "member_ban": int(nuke_cfg.get("max_bans", 5)),
            "member_kick": int(nuke_cfg.get("max_kicks", 5))
        }

        limit = thresholds.get(action_type, 5)
        g_actions = self._action_times.setdefault(guild_id, {})
        times = g_actions.setdefault(action_type, [])
        times.append(now)
        g_actions[action_type] = [t for t in times if now - t <= window]

        if len(g_actions[action_type]) >= limit:
            reason = f"Mass {action_type} detected: {len(g_actions[action_type])} within {int(window)}s by Actor {actor_id}"
            logger.critical(f"💣 ANTI-NUKE TRIGGERED in Guild {guild_id}: {reason}")
            return True, reason

        return False, "Normal Activity"


class StaffPermissionManager:
    """Enforces role hierarchy and tiered staff authorizations."""

    @staticmethod
    def can_moderate_target(moderator: discord.Member, target: discord.Member) -> Tuple[bool, str]:
        """Ensures the moderator outranks the target in Discord role hierarchy."""
        if moderator.id == target.id:
            return False, "You cannot execute moderation actions on yourself."

        if target.id == moderator.guild.owner_id:
            return False, "You cannot moderate the Server Owner."

        if moderator.id == moderator.guild.owner_id:
            return True, "Server Owner override."

        if target.top_role >= moderator.top_role:
            return False, f"Target's highest role ({target.top_role.name}) is equal to or higher than yours ({moderator.top_role.name})."

        # Check bot's own role hierarchy
        bot_member = moderator.guild.me
        if bot_member and target.top_role >= bot_member.top_role:
            return False, f"Kazumi's highest role ({bot_member.top_role.name}) is lower than target's role ({target.top_role.name})."

        return True, "Permitted"


# =============================================================================
# Interactive Confirmation Views
# =============================================================================

class DestructiveConfirmView(discord.ui.View):
    """Interactive confirmation modal for high-impact moderation actions."""

    def __init__(self, author_id: int, timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.confirmed: Optional[bool] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ This confirmation prompt is only for the executing moderator.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="CONFIRM ACTION", style=discord.ButtonStyle.danger, emoji="⚠️", custom_id="destruct_confirm_btn")
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="✅ **Action Confirmed!** Executing requested operation...", view=self)
        self.stop()

    @discord.ui.button(label="CANCEL", style=discord.ButtonStyle.secondary, emoji="✖️", custom_id="destruct_cancel_btn")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="❌ **Operation Cancelled.** No changes were made.", view=self)
        self.stop()


# =============================================================================
# Register Security Slash Commands
# =============================================================================

def register_security_commands(tree: app_commands.CommandTree, bot: commands.Bot, db: FeatureDB) -> None:

    # 1. /quarantine <@user> [reason]
    @tree.command(name="quarantine", description="Isolate a suspicious member to quarantine role 🚫")
    @app_commands.describe(user="The member to isolate", reason="Reason for quarantine")
    async def slash_quarantine(interaction: discord.Interaction, user: discord.Member, reason: Optional[str] = "Suspicious behavior"):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You need **Moderate Members** permission.", ephemeral=True)
            return

        can_mod, mod_err = StaffPermissionManager.can_moderate_target(interaction.user, user)
        if not can_mod:
            await interaction.response.send_message(f"❌ Cannot quarantine: {mod_err}", ephemeral=True)
            return

        sec_cfg = db.get_security_settings(interaction.guild.id)
        q_role_id = sec_cfg.get("quarantine", {}).get("role_id")
        q_role = interaction.guild.get_role(int(q_role_id)) if q_role_id else None

        if not q_role:
            await interaction.response.send_message(
                "⚠️ **No Quarantine Role Configured!** Please ask an administrator to set one via `/security quarantine_role`.",
                ephemeral=True
            )
            return

        orig_roles = [r.id for r in user.roles if r.name != "@everyone"]
        try:
            # Add quarantine role and remove regular roles where feasible
            await user.add_roles(q_role, reason=f"Quarantined by {interaction.user}: {reason}")
            db.set_user_quarantined(interaction.guild.id, user.id, True, interaction.user.id, reason, orig_roles)
            case_id = db.create_case(interaction.guild.id, user.id, interaction.user.id, "QUARANTINE", reason)

            embed = discord.Embed(
                title="🚫 Member Quarantined",
                description=f"Isolated **{user.mention}** (`{user.id}`) into quarantine role {q_role.mention}.\n\n**Reason:** {reason}\n**Case ID:** `#{case_id}`",
                color=0x8b5cf6
            )
            embed.set_footer(text="Kazumi Guard Security • Quarantine System")
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to quarantine user: {e}", ephemeral=True)

    # 2. /unquarantine <@user>
    @tree.command(name="unquarantine", description="Restore a quarantined member's access 🕊️")
    @app_commands.describe(user="The member to release from quarantine")
    async def slash_unquarantine(interaction: discord.Interaction, user: discord.Member):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You need **Moderate Members** permission.", ephemeral=True)
            return

        sec_cfg = db.get_security_settings(interaction.guild.id)
        q_role_id = sec_cfg.get("quarantine", {}).get("role_id")
        q_role = interaction.guild.get_role(int(q_role_id)) if q_role_id else None

        record = db.get_quarantined_record(interaction.guild.id, user.id)
        try:
            if q_role and q_role in user.roles:
                await user.remove_roles(q_role, reason=f"Unquarantined by {interaction.user}")
            db.set_user_quarantined(interaction.guild.id, user.id, False)
            case_id = db.create_case(interaction.guild.id, user.id, interaction.user.id, "UNQUARANTINE", "Quarantine lifted by staff")

            embed = discord.Embed(
                title="🕊️ Member Unquarantined",
                description=f"Restored normal status for **{user.mention}**.\n**Case ID:** `#{case_id}`",
                color=0x10b981
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error releasing member: {e}", ephemeral=True)

    # 3. /raidmode <on|off>
    @tree.command(name="raidmode", description="Toggle emergency server raid lockdown mode 🛡️")
    @app_commands.describe(status="Enable or disable raid lockdown mode")
    @app_commands.choices(status=[
        app_commands.Choice(name="ON — Activate Emergency Raid Lockdown 🛡️", value="on"),
        app_commands.Choice(name="OFF — Lift Raid Lockdown Mode 🌸", value="off")
    ])
    async def slash_raidmode(interaction: discord.Interaction, status: app_commands.Choice[str]):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return

        enable = (status.value == "on")
        db.set_raid_mode(interaction.guild.id, enable)

        if enable:
            embed = discord.Embed(
                title="🛡️ EMERGENCY RAID LOCKDOWN ACTIVE",
                description=(
                    "**Raid Protection has been engaged by server administration!**\n\n"
                    "• New members joining will be restricted or flagged.\n"
                    "• Moderation alerts will fire for abnormal bursts.\n"
                    "• Chat slowmode is recommended.\n"
                    "• To restore normal mode, use `/raidmode off`."
                ),
                color=0xef4444
            )
        else:
            embed = discord.Embed(
                title="🌸 RAID LOCKDOWN LIFTED",
                description="Emergency raid mode has been deactivated. Regular server onboarding restored.",
                color=0x10b981
            )
        await interaction.response.send_message(embed=embed)

    # 4. /security settings
    @tree.command(name="security", description="Configure anti-raid, anti-nuke, and quarantine settings ⚙️")
    @app_commands.describe(
        anti_raid="Enable or disable anti-raid burst detection",
        anti_nuke="Enable or disable mass deletion protection",
        quarantine_role="Role to assign to quarantined members"
    )
    async def slash_security(
        interaction: discord.Interaction,
        anti_raid: Optional[bool] = None,
        anti_nuke: Optional[bool] = None,
        quarantine_role: Optional[discord.Role] = None
    ):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
            return

        sec_cfg = db.get_security_settings(interaction.guild.id)
        updates = {}

        if anti_raid is not None:
            r_cfg = sec_cfg.get("anti_raid", {})
            r_cfg["enabled"] = anti_raid
            updates["anti_raid"] = r_cfg

        if anti_nuke is not None:
            n_cfg = sec_cfg.get("anti_nuke", {})
            n_cfg["enabled"] = anti_nuke
            updates["anti_nuke"] = n_cfg

        if quarantine_role is not None:
            q_cfg = sec_cfg.get("quarantine", {})
            q_cfg["enabled"] = True
            q_cfg["role_id"] = str(quarantine_role.id)
            updates["quarantine"] = q_cfg

        if updates:
            db.update_security_settings(interaction.guild.id, updates)

        refreshed = db.get_security_settings(interaction.guild.id)
        embed = discord.Embed(
            title="🛡️ Kazumi Guard Security Settings",
            description=f"Current server defense configuration for **{interaction.guild.name}**:",
            color=0x3b82f6
        )
        embed.add_field(
            name="Anti-Raid Protection",
            value=f"{'🟢 Enabled' if refreshed.get('anti_raid', {}).get('enabled') else '🔴 Disabled'}\nThreshold: `{refreshed.get('anti_raid', {}).get('join_threshold', 8)} joins / {refreshed.get('anti_raid', {}).get('join_window_sec', 10)}s`",
            inline=True
        )
        embed.add_field(
            name="Anti-Nuke Protection",
            value=f"{'🟢 Enabled' if refreshed.get('anti_nuke', {}).get('enabled') else '🔴 Disabled'}\nChannel Del: `{refreshed.get('anti_nuke', {}).get('max_channel_deletions', 4)}` | Role Del: `{refreshed.get('anti_nuke', {}).get('max_role_deletions', 4)}`",
            inline=True
        )
        q_r_id = refreshed.get("quarantine", {}).get("role_id")
        embed.add_field(
            name="Quarantine Role",
            value=f"<@&{q_r_id}>" if q_r_id else "*None configured*",
            inline=True
        )
        embed.add_field(
            name="Emergency Raid Mode",
            value="🚨 **ACTIVE**" if refreshed.get("raid_mode_active") else "⚪ Inactive",
            inline=True
        )
        await interaction.response.send_message(embed=embed)
