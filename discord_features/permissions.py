"""
Unified Permission and Security System for Kazumi.
Enforces role hierarchy, permission validation, bot capabilities, and feature-level access control.
"""

import logging
from typing import Tuple, Optional, List
import discord

logger = logging.getLogger("KazumiPermissions")


class PermissionService:
    """
    Centralized authorization service used across moderation, giveaways,
    music, and natural-language AI actions.
    """

    @staticmethod
    def is_guild_owner(member: discord.Member) -> bool:
        if not member.guild:
            return False
        return member.guild.owner_id == member.id

    @classmethod
    def check_permission(
        cls,
        member: discord.Member,
        permission: str,
        guild_settings: Optional[dict] = None
    ) -> Tuple[bool, str]:
        """
        Validates if member holds required permission either via Discord perms,
        guild ownership, or configured staff roles.
        """
        if not isinstance(member, discord.Member):
            return False, "Action must be performed within a Discord server."

        # Server owner always passes
        if cls.is_guild_owner(member):
            return True, "Authorized (Server Owner)"

        # Guild Administrator always passes
        perms = member.guild_permissions
        if perms.administrator:
            return True, "Authorized (Administrator)"

        # Check configured moderator/trusted roles
        if guild_settings:
            mod_role_ids = set()
            trusted_roles = guild_settings.get("trusted_roles", [])
            for r in trusted_roles:
                try:
                    mod_role_ids.add(int(r))
                except (ValueError, TypeError):
                    pass
            member_role_ids = {r.id for r in member.roles}
            if member_role_ids & mod_role_ids:
                return True, "Authorized (Configured Staff Role)"

        # Check standard Discord permissions
        perm_val = getattr(perms, permission, False)
        if perm_val:
            return True, f"Authorized ({permission})"

        readable_name = permission.replace("_", " ").title()
        return False, f"You require the **{readable_name}** permission or an authorized role."

    @classmethod
    def check_hierarchy(
        cls,
        executor: discord.Member,
        target: discord.Member,
        bot_member: Optional[discord.Member] = None
    ) -> Tuple[bool, str]:
        """
        Enforces strict role hierarchy between executor, target, and the bot itself.
        """
        if executor.id == target.id:
            return False, "You cannot perform moderation actions against yourself."

        if target.id == executor.guild.owner_id:
            return False, "The server owner cannot be targeted by moderation actions."

        # Executor must outrank target (unless executor is owner)
        if not cls.is_guild_owner(executor):
            if executor.top_role <= target.top_role:
                return False, f"Role hierarchy violation: **{target.display_name}** has a higher or equal role to you."

        # Bot must outrank target
        if bot_member:
            if target.id == bot_member.id:
                return False, "Kazumi cannot perform moderation actions on herself."
            if bot_member.top_role <= target.top_role:
                return False, f"I cannot moderate **{target.display_name}** because their role is higher than or equal to my highest role."

        return True, "Hierarchy check passed"

    @classmethod
    def check_bot_permissions(
        cls,
        bot_member: discord.Member,
        channel: Optional[discord.TextChannel],
        required_perms: List[str]
    ) -> Tuple[bool, str]:
        """Ensures the bot itself has the required permissions in the server/channel."""
        if not bot_member:
            return False, "Bot member context is missing."

        guild_perms = bot_member.guild_permissions
        if guild_perms.administrator:
            return True, "Bot has Administrator"

        channel_perms = channel.permissions_for(bot_member) if channel else guild_perms
        for p in required_perms:
            if not getattr(channel_perms, p, False):
                readable = p.replace("_", " ").title()
                return False, f"I lack the required **{readable}** permission in this channel."

        return True, "Bot permissions check passed"

    @classmethod
    def check_music_access(
        cls,
        member: discord.Member,
        voice_state: Optional[discord.VoiceState]
    ) -> Tuple[bool, str]:
        """Validates whether member can control or request music."""
        if not voice_state or not voice_state.channel:
            return False, "You need to be in a voice channel to use music commands."
        return True, "Music access authorized"

    @classmethod
    def check_giveaway_manage_access(
        cls,
        member: discord.Member,
        host_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Validates if member can manage or reroll a giveaway."""
        if cls.is_guild_owner(member):
            return True, "Authorized (Server Owner)"

        if member.guild_permissions.manage_guild or member.guild_permissions.administrator:
            return True, "Authorized (Manage Server)"

        if host_id and str(member.id) == str(host_id):
            return True, "Authorized (Giveaway Host)"

        return False, "You must be the giveaway host or have **Manage Server** permission."
