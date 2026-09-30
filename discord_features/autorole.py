"""
🌸 Kazumi Discord Features — Auto Role System
Automatically assigns designated starter roles to new members on joining.
Adheres strictly to Discord role hierarchy limits.
"""

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from discord_features.database import get_feature_db


class AutoRoleSystem:
    """Manages automatic role assignment upon member joining."""

    @staticmethod
    async def assign_autoroles(member: discord.Member):
        db = get_feature_db()
        settings = db.get_guild_settings(str(member.guild.id))
        role_ids = settings.get("autorole_ids", [])
        if not role_ids:
            return

        roles_to_add = []
        for rid in role_ids:
            role = member.guild.get_role(int(rid))
            if role and member.guild.me.top_role > role:
                roles_to_add.append(role)

        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="Kazumi AutoRole on join")
            except Exception:
                pass


def register_autorole_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    @tree.command(name="autorole", description="Configure automatic roles assigned to new members 🎭")
    @app_commands.describe(
        action="Action (set, remove, status, clear)",
        role="The server role to assign or remove"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add / Set AutoRole", value="set"),
        app_commands.Choice(name="Remove AutoRole", value="remove"),
        app_commands.Choice(name="View Current AutoRoles", value="status"),
        app_commands.Choice(name="Clear All AutoRoles", value="clear"),
    ])
    async def slash_autorole(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        role: Optional[discord.Role] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You require **Manage Roles** permission.", ephemeral=True)
            return

        gid = str(interaction.guild_id)
        settings = db.get_guild_settings(gid)
        current_roles = list(settings.get("autorole_ids", []))

        if action.value == "set":
            if not role:
                await interaction.response.send_message("❌ Please specify a role to add.", ephemeral=True)
                return

            if interaction.guild.me.top_role <= role:
                await interaction.response.send_message("❌ Kazumi's highest role is lower than or equal to this role. Please move Kazumi's role higher in Server Settings -> Roles.", ephemeral=True)
                return

            if str(role.id) not in current_roles:
                current_roles.append(str(role.id))
                db.update_guild_settings(gid, {"autorole_ids": current_roles})

            await interaction.response.send_message(f"🎭 New members will automatically receive {role.mention} on joining!")

        elif action.value == "remove":
            if not role:
                await interaction.response.send_message("❌ Please specify a role to remove.", ephemeral=True)
                return
            if str(role.id) in current_roles:
                current_roles.remove(str(role.id))
                db.update_guild_settings(gid, {"autorole_ids": current_roles})
                await interaction.response.send_message(f"🎭 Removed {role.mention} from AutoRoles.")
            else:
                await interaction.response.send_message(f"❌ {role.mention} is not in the AutoRole list.", ephemeral=True)

        elif action.value == "clear":
            db.update_guild_settings(gid, {"autorole_ids": []})
            await interaction.response.send_message("🎭 Cleared all configured AutoRoles.")

        elif action.value == "status":
            if not current_roles:
                await interaction.response.send_message("🎭 No AutoRoles are currently configured for this server.", ephemeral=True)
                return
            mentions = [f"<@&{rid}>" for rid in current_roles]
            embed = discord.Embed(
                title="🎭 Configured AutoRoles",
                description="New members automatically receive:\n" + "\n".join([f"• {m}" for m in mentions]),
                color=0x818cf8
            )
            embed.set_footer(text="Kazumi AutoRole System 🌸")
            await interaction.response.send_message(embed=embed, ephemeral=True)
