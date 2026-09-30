"""
🌸 Kazumi Discord Features — Moderation & AutoMod System
Comprehensive moderation suite adhering strictly to server permissions:
- Commands: /warn, /warnings, /clear_warnings, /timeout, /mute, /kick, /ban, /unban, /clear, /slowmode, /lock, /unlock
- AutoMod Engine: Anti-spam, flood detection, mention limits, link & invite filtering, bad-word filtering
- AI Moderation Explanation: Concise, structured reasoning for mod logs without exposing chain-of-thought
"""

import time
import re
from datetime import timedelta, datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

import discord
from discord import app_commands
from discord.ext import commands

from discord_features.database import get_feature_db

INVITE_REGEX = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.(?:gg|io|me|li)|discord(?:app)?\.com/invite)/[a-zA-Z0-9]+", re.IGNORECASE)
LINK_REGEX = re.compile(r"https?://[^\s]+", re.IGNORECASE)


class AutoModTracker:
    """Tracks message frequency, duplicates, and pings for AutoMod."""
    def __init__(self):
        # (guild_id, user_id) -> list of timestamps
        self.message_history: Dict[Tuple[str, str], List[float]] = {}
        # (guild_id, user_id) -> list of recent message hashes/texts
        self.recent_contents: Dict[Tuple[str, str], List[str]] = {}

    def record_and_evaluate(
        self,
        message: discord.Message,
        automod_config: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Evaluates message against enabled AutoMod rules.
        Returns (violated: bool, rule_name: str, evidence: str).
        """
        if not automod_config.get("enabled", False):
            return (False, None, None)

        now = time.time()
        gid = str(message.guild.id)
        uid = str(message.author.id)
        key = (gid, uid)
        text = message.content or ""

        # 1. Anti-Invite
        if automod_config.get("anti_invites", True):
            if INVITE_REGEX.search(text):
                return (True, "Discord Invite Link", "Message contained unauthorized Discord invite link.")

        # 2. Anti-Link
        if automod_config.get("anti_links", False):
            if LINK_REGEX.search(text) and not message.author.guild_permissions.manage_messages:
                return (True, "External Link", "Posting links is restricted in this server.")

        # 3. Excessive Mentions
        if automod_config.get("anti_mentions", True):
            max_pings = automod_config.get("max_mentions", 5)
            if len(message.mentions) > max_pings:
                return (True, "Excessive Mentions", f"Pinging {len(message.mentions)} members exceeds limit ({max_pings}).")

        # 4. Bad Words Filter
        bad_words = automod_config.get("bad_words", [])
        if bad_words:
            lower = text.lower()
            for bw in bad_words:
                if bw and bw.lower() in lower:
                    return (True, "Prohibited Language", f"Message contained blacklisted term.")

        # 5. Anti-Spam (Rate limiting: max 5 messages in 4 seconds)
        if automod_config.get("anti_spam", True):
            history = self.message_history.setdefault(key, [])
            history.append(now)
            # Retain timestamps from last 4 seconds
            history = [t for t in history if now - t <= 4.0]
            self.message_history[key] = history

            if len(history) >= 6:
                return (True, "Rapid Message Spam", f"Sent {len(history)} messages in 4 seconds.")

        # 6. Anti-Flood (Duplicate message repetition)
        clean_norm = re.sub(r"\s+", " ", text.strip().lower())
        if len(clean_norm) > 4:
            contents = self.recent_contents.setdefault(key, [])
            contents.append(clean_norm)
            if len(contents) > 5:
                contents = contents[-5:]
                self.recent_contents[key] = contents

            if contents.count(clean_norm) >= 3:
                return (True, "Duplicate Message Flood", "Repeated the identical message 3 times consecutively.")

        return (False, None, None)


automod_tracker = AutoModTracker()


def check_hierarchy(mod: discord.Member, target: discord.Member) -> bool:
    """Verifies that moderator outranks target member."""
    if mod.guild.owner_id == mod.id:
        return True
    return mod.top_role > target.top_role


def create_mod_embed(title: str, description: str, color: int = 0xf43f5e) -> discord.Embed:
    """Creates a standardized moderation embed card."""
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="Kazumi Moderation System 🌸")
    embed.timestamp = datetime.now(timezone.utc)
    return embed


def format_mod_explanation(action: str, reason: str, evidence: str, confidence: str = "High") -> str:
    """Generates structured moderation explanation (Section 26)."""
    return (
        f"**Action:** {action}\n"
        f"**Reason:** {reason}\n"
        f"**Evidence:** {evidence}\n"
        f"**Confidence:** {confidence}"
    )


# ---------------------------------------------------------------------------
# Slash Commands Setup
# ---------------------------------------------------------------------------

def register_moderation_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    # --- Warn ---
    @tree.command(name="warn", description="Issue a formal warning to a server member ⚠️")
    @app_commands.describe(user="The member to warn", reason="Reason for warning")
    async def slash_warn(interaction: discord.Interaction, user: discord.Member, reason: str):
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You require **Manage Messages** permission to issue warnings.", ephemeral=True)
            return

        if not check_hierarchy(interaction.user, user):
            await interaction.response.send_message("❌ You cannot moderate a member who has an equal or higher role than you.", ephemeral=True)
            return

        count = db.add_warning(str(interaction.guild_id), str(user.id), str(interaction.user.id), reason)
        db.record_mod_action(str(interaction.guild_id), "WARN", str(user.id), str(interaction.user.id), reason)

        # Notify warned user in DM if possible
        try:
            await user.send(f"⚠️ You received a warning in **{interaction.guild.name}**:\n**Reason:** {reason}\n*Total warnings: {count}*")
        except Exception:
            pass

        embed = create_mod_embed(
            title="⚠️ Member Warned",
            description=f"**Member:** {user.mention} (`{user.id}`)\n"
                        f"**Moderator:** {interaction.user.mention}\n"
                        f"**Reason:** {reason}\n"
                        f"**Total Warnings:** {count}"
        )
        await interaction.response.send_message(embed=embed)

    # --- Warnings ---
    @tree.command(name="warnings", description="View warnings for a member 📋")
    @app_commands.describe(user="The member whose warnings to inspect")
    async def slash_warnings(interaction: discord.Interaction, user: discord.Member):
        if not interaction.guild:
            return
        warns = db.get_warnings(str(interaction.guild_id), str(user.id))
        if not warns:
            await interaction.response.send_message(f"🌸 **{user.display_name}** has a clean record! (0 warnings)", ephemeral=True)
            return

        lines = [f"**#{w['id']}** | Mod: <@{w['moderator_id']}> | Reason: *{w['reason']}* (<t:{int(w['timestamp'])}:R>)" for w in warns]
        embed = create_mod_embed(
            title=f"📋 Warnings for {user.display_name} ({len(warns)})",
            description="\n".join(lines),
            color=0xfbbf24
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Clear Warnings ---
    @tree.command(name="clearwarnings", description="Clear all warnings for a member 🌿")
    @app_commands.describe(user="The member whose warnings to clear")
    async def slash_clearwarnings(interaction: discord.Interaction, user: discord.Member):
        if not interaction.guild or not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You require **Manage Messages** permission.", ephemeral=True)
            return

        removed = db.clear_warnings(str(interaction.guild_id), str(user.id))
        embed = create_mod_embed(
            title="🌿 Warnings Cleared",
            description=f"Cleared **{removed}** warning(s) for {user.mention}.",
            color=0x34d399
        )
        await interaction.response.send_message(embed=embed)

    # --- Timeout / Mute ---
    @tree.command(name="timeout", description="Temporarily timeout / mute a member ⏳")
    @app_commands.describe(user="The member to timeout", minutes="Duration in minutes (e.g. 5, 60, 1440)", reason="Reason for timeout")
    async def slash_timeout(interaction: discord.Interaction, user: discord.Member, minutes: int, reason: Optional[str] = "No reason provided"):
        if not interaction.guild or not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You require **Moderate Members** permission.", ephemeral=True)
            return

        if not check_hierarchy(interaction.user, user):
            await interaction.response.send_message("❌ You cannot moderate a member equal or higher than you.", ephemeral=True)
            return

        if minutes <= 0 or minutes > 40320:  # Discord 28-day max
            await interaction.response.send_message("❌ Duration must be between 1 and 40,320 minutes (28 days).", ephemeral=True)
            return

        duration = timedelta(minutes=minutes)
        try:
            await user.timeout(duration, reason=reason)
            db.record_mod_action(str(interaction.guild_id), "TIMEOUT", str(user.id), str(interaction.user.id), f"{minutes}m - {reason}")
            embed = create_mod_embed(
                title="⏳ Member Timed Out",
                description=f"**Member:** {user.mention}\n"
                            f"**Duration:** {minutes} minute(s)\n"
                            f"**Moderator:** {interaction.user.mention}\n"
                            f"**Reason:** {reason}"
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to timeout member: {e}", ephemeral=True)

    # --- Kick ---
    @tree.command(name="kick", description="Kick a member from the server 👢")
    @app_commands.describe(user="The member to kick", reason="Reason for kick")
    async def slash_kick(interaction: discord.Interaction, user: discord.Member, reason: Optional[str] = "No reason provided"):
        if not interaction.guild or not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ You require **Kick Members** permission.", ephemeral=True)
            return

        if not check_hierarchy(interaction.user, user):
            await interaction.response.send_message("❌ You cannot kick a member equal or higher in role hierarchy.", ephemeral=True)
            return

        try:
            await user.kick(reason=reason)
            db.record_mod_action(str(interaction.guild_id), "KICK", str(user.id), str(interaction.user.id), reason)
            embed = create_mod_embed(
                title="👢 Member Kicked",
                description=f"**Member:** {user.mention} (`{user.id}`)\n"
                            f"**Moderator:** {interaction.user.mention}\n"
                            f"**Reason:** {reason}"
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to kick member: {e}", ephemeral=True)

    # --- Ban ---
    @tree.command(name="ban", description="Ban a member from the server 🔨")
    @app_commands.describe(user="The member to ban", delete_messages_days="Days of messages to delete (0 to 7)", reason="Reason for ban")
    async def slash_ban(interaction: discord.Interaction, user: discord.Member, delete_messages_days: Optional[int] = 0, reason: Optional[str] = "No reason provided"):
        if not interaction.guild or not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ You require **Ban Members** permission.", ephemeral=True)
            return

        if not check_hierarchy(interaction.user, user):
            await interaction.response.send_message("❌ You cannot ban a member equal or higher in role hierarchy.", ephemeral=True)
            return

        del_sec = min(7, max(0, delete_messages_days or 0)) * 86400
        try:
            await user.ban(delete_message_seconds=del_sec, reason=reason)
            db.record_mod_action(str(interaction.guild_id), "BAN", str(user.id), str(interaction.user.id), reason)
            embed = create_mod_embed(
                title="🔨 Member Banned",
                description=f"**Member:** {user.mention} (`{user.id}`)\n"
                            f"**Moderator:** {interaction.user.mention}\n"
                            f"**Reason:** {reason}"
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to ban member: {e}", ephemeral=True)

    # --- Unban ---
    @tree.command(name="unban", description="Unban a previously banned user by ID 🕊️")
    @app_commands.describe(user_id="The Discord User ID to unban", reason="Reason for unban")
    async def slash_unban(interaction: discord.Interaction, user_id: str, reason: Optional[str] = "No reason provided"):
        if not interaction.guild or not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ You require **Ban Members** permission.", ephemeral=True)
            return

        try:
            user = await bot.fetch_user(int(user_id.strip()))
            await interaction.guild.unban(user, reason=reason)
            db.record_mod_action(str(interaction.guild_id), "UNBAN", str(user.id), str(interaction.user.id), reason)
            embed = create_mod_embed(
                title="🕊️ Member Unbanned",
                description=f"**User:** {user.mention} (`{user.id}`)\n"
                            f"**Moderator:** {interaction.user.mention}\n"
                            f"**Reason:** {reason}",
                color=0x34d399
            )
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to unban user ID {user_id}: {e}", ephemeral=True)

    # --- Clear (Purge Messages) ---
    @tree.command(name="clear", description="Bulk delete messages in this channel 🧹")
    @app_commands.describe(amount="Number of messages to delete (1 to 100)")
    async def slash_clear(interaction: discord.Interaction, amount: int):
        if not interaction.guild or not interaction.channel.permissions_for(interaction.user).manage_messages:
            await interaction.response.send_message("❌ You require **Manage Messages** permission.", ephemeral=True)
            return

        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=amount)
            db.record_mod_action(str(interaction.guild_id), "CLEAR", str(interaction.channel_id), str(interaction.user.id), f"Purged {len(deleted)} messages")
            await interaction.followup.send(f"🧹 Successfully cleared **{len(deleted)}** message(s)!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Purge error: {e}", ephemeral=True)

    # --- Slowmode ---
    @tree.command(name="slowmode", description="Set channel slowmode delay in seconds ⏱️")
    @app_commands.describe(seconds="Slowmode duration (0 to 21600 seconds, 0 = disabled)")
    async def slash_slowmode(interaction: discord.Interaction, seconds: int):
        if not interaction.guild or not interaction.channel.permissions_for(interaction.user).manage_channels:
            await interaction.response.send_message("❌ You require **Manage Channels** permission.", ephemeral=True)
            return

        sec = max(0, min(21600, seconds))
        try:
            await interaction.channel.edit(slowmode_delay=sec)
            status_text = f"set to **{sec}s**" if sec > 0 else "disabled"
            await interaction.response.send_message(f"⏱️ Slowmode has been {status_text} in this channel.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to update slowmode: {e}", ephemeral=True)

    # --- Lock / Unlock ---
    @tree.command(name="lock", description="Lock the current channel to prevent members from sending messages 🔒")
    async def slash_lock(interaction: discord.Interaction):
        if not interaction.guild or not interaction.channel.permissions_for(interaction.user).manage_channels:
            await interaction.response.send_message("❌ You require **Manage Channels** permission.", ephemeral=True)
            return

        try:
            overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
            overwrite.send_messages = False
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
            await interaction.response.send_message("🔒 Channel has been locked. Members cannot send messages.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to lock channel: {e}", ephemeral=True)

    @tree.command(name="unlock", description="Unlock the current channel 🔓")
    async def slash_unlock(interaction: discord.Interaction):
        if not interaction.guild or not interaction.channel.permissions_for(interaction.user).manage_channels:
            await interaction.response.send_message("❌ You require **Manage Channels** permission.", ephemeral=True)
            return

        try:
            overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
            overwrite.send_messages = None
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
            await interaction.response.send_message("🔓 Channel has been unlocked. Members can now chat.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to unlock channel: {e}", ephemeral=True)

    # --- AutoMod Configuration ---
    @tree.command(name="automod", description="Configure Kazumi's AutoMod protection settings 🛡️")
    @app_commands.describe(
        enabled="Enable or disable AutoMod protection",
        anti_spam="Block rapid-fire message spam",
        anti_invites="Block unauthorized Discord invites",
        anti_links="Block external links (except for moderators)",
        anti_mentions="Block excessive user pings (>5 mentions)"
    )
    async def slash_automod(
        interaction: discord.Interaction,
        enabled: Optional[bool] = None,
        anti_spam: Optional[bool] = None,
        anti_invites: Optional[bool] = None,
        anti_links: Optional[bool] = None,
        anti_mentions: Optional[bool] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You require **Manage Server** permission to configure AutoMod.", ephemeral=True)
            return

        gid = str(interaction.guild_id)
        settings = db.get_guild_settings(gid)
        automod = settings.setdefault("automod", {})

        if enabled is not None:
            automod["enabled"] = enabled
        if anti_spam is not None:
            automod["anti_spam"] = anti_spam
        if anti_invites is not None:
            automod["anti_invites"] = anti_invites
        if anti_links is not None:
            automod["anti_links"] = anti_links
        if anti_mentions is not None:
            automod["anti_mentions"] = anti_mentions

        db.update_guild_settings(gid, {"automod": automod})

        embed = create_mod_embed(
            title="🛡️ AutoMod Configuration Updated",
            description=(
                f"**Protection Enabled:** {'✅ On' if automod.get('enabled') else '❌ Off'}\n"
                f"• Anti-Spam: {'✅ On' if automod.get('anti_spam') else '❌ Off'}\n"
                f"• Anti-Invites: {'✅ On' if automod.get('anti_invites') else '❌ Off'}\n"
                f"• Anti-Links: {'✅ On' if automod.get('anti_links') else '❌ Off'}\n"
                f"• Anti-Mass-Mentions: {'✅ On' if automod.get('anti_mentions') else '❌ Off'}\n\n"
                "*Kazumi actively monitors chat messages and enforces these rules automatically!*"
            ),
            color=0x6366f1
        )
        await interaction.response.send_message(embed=embed)
