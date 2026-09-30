"""
🌸 Kazumi Discord Features — Reaction & Button Roles System
Allows members to toggle server roles by clicking interactive Discord buttons.
Persists across bot restarts.
"""

from typing import Optional, List

import discord
from discord import app_commands
from discord.ext import commands

from discord_features.database import get_feature_db


class RoleToggleButton(discord.ui.Button):
    """Button representing a single assignable role."""
    def __init__(self, role_id: int, label: str, emoji: Optional[str] = None):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            emoji=emoji,
            custom_id=f"kazumi:role:{role_id}"
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return

        role = guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("❌ This role no longer exists.", ephemeral=True)
            return

        if guild.me.top_role <= role:
            await interaction.response.send_message("❌ Kazumi's role is lower than this role in the server hierarchy.", ephemeral=True)
            return

        member = interaction.user
        if role in member.roles:
            try:
                await member.remove_roles(role, reason="Kazumi Button Roles Toggle")
                await interaction.response.send_message(f"➖ Removed **{role.name}** role from you.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error removing role: {e}", ephemeral=True)
        else:
            try:
                await member.add_roles(role, reason="Kazumi Button Roles Toggle")
                await interaction.response.send_message(f"➕ Added **{role.name}** role to you!", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error adding role: {e}", ephemeral=True)


class DynamicRolePanelView(discord.ui.View):
    """Container view holding up to 5 role buttons."""
    def __init__(self, roles: List[discord.Role]):
        super().__init__(timeout=None)
        emojis = ["🌸", "✨", "🎮", "🎵", "💻"]
        for idx, role in enumerate(roles[:5]):
            btn_emoji = emojis[idx % len(emojis)]
            self.add_item(RoleToggleButton(role.id, label=role.name, emoji=btn_emoji))


def register_reaction_role_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    @tree.command(name="reactionrole", description="Create an interactive role selection panel with buttons 🌸")
    @app_commands.describe(
        title="Title of the role selection panel",
        description="Description explaining the panel to members",
        role1="First selectable role",
        role2="Second selectable role (optional)",
        role3="Third selectable role (optional)",
        role4="Fourth selectable role (optional)",
        role5="Fifth selectable role (optional)"
    )
    async def slash_reactionrole(
        interaction: discord.Interaction,
        title: str,
        description: str,
        role1: discord.Role,
        role2: Optional[discord.Role] = None,
        role3: Optional[discord.Role] = None,
        role4: Optional[discord.Role] = None,
        role5: Optional[discord.Role] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You require **Manage Roles** permission to create role panels.", ephemeral=True)
            return

        roles = [r for r in [role1, role2, role3, role4, role5] if r is not None]
        for r in roles:
            if interaction.guild.me.top_role <= r:
                await interaction.response.send_message(f"❌ Kazumi cannot manage the role {r.mention} because her role is lower or equal.", ephemeral=True)
                return

        embed = discord.Embed(
            title=f"🌸 {title}",
            description=f"{description}\n\nClick any button below to get or remove that role!",
            color=0xc084fc
        )
        embed.set_footer(text="Kazumi Role Selection • Click to toggle 🌸")

        view = DynamicRolePanelView(roles)
        msg = await interaction.channel.send(embed=embed, view=view)

        # Store in database
        role_map = {str(r.id): r.name for r in roles}
        db.save_reaction_role(str(msg.id), role_map)

        await interaction.response.send_message("✅ Role panel posted successfully!", ephemeral=True)
