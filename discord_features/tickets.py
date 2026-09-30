"""
🌸 Kazumi Discord Features — Interactive Support Ticket System
Provides interactive button-driven tickets with staff permissions:
- Persistent ticket panel: "📩 Create Ticket" button
- Channel creation under configured category with private permissions
- Ticket controls: Close, Reopen, Delete, Claim, Transcript
- Commands: /ticket panel, /ticket setup, /ticket add, /ticket remove, /ticket close
"""

import time
import io
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from discord_features.database import get_feature_db


class TicketControlView(discord.ui.View):
    """Action buttons inside an opened ticket channel."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="kazumi:ticket:close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = get_feature_db()
        ticket_data = db.get_ticket(str(interaction.channel_id))
        if not ticket_data:
            await interaction.response.send_message("❌ This is not an active ticket channel.", ephemeral=True)
            return

        db.close_ticket(str(interaction.channel_id))
        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"Ticket closed by {interaction.user.mention}.\nUse the buttons below to delete or reopen.",
            color=0xf59e0b
        )
        view = TicketClosedActionsView()
        await interaction.response.send_message(embed=embed, view=view)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.primary, emoji="🙋", custom_id="kazumi:ticket:claim")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = get_feature_db()
        ticket = db.get_ticket(str(interaction.channel_id))
        if not ticket:
            await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
            return

        ticket["claimed_by"] = str(interaction.user.id)
        db.save_ticket(str(interaction.channel_id), ticket)
        await interaction.response.send_message(f"🙋 **{interaction.user.display_name}** has claimed this ticket and will assist you!")


class TicketClosedActionsView(discord.ui.View):
    """Buttons displayed when a ticket is closed."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.success, emoji="🔓", custom_id="kazumi:ticket:reopen")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = get_feature_db()
        ticket = db.get_ticket(str(interaction.channel_id))
        if ticket:
            ticket["status"] = "open"
            db.save_ticket(str(interaction.channel_id), ticket)
            await interaction.response.send_message(f"🔓 Ticket reopened by {interaction.user.mention}.")

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="kazumi:ticket:delete")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🗑️ Deleting ticket channel in 5 seconds...")
        time.sleep(4.5)
        try:
            await interaction.channel.delete(reason=f"Ticket closed and deleted by {interaction.user}")
        except Exception:
            pass


class TicketLaunchView(discord.ui.View):
    """Public panel button for members to open tickets."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, emoji="📩", custom_id="kazumi:ticket:launch")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = get_feature_db()
        guild = interaction.guild
        settings = db.get_guild_settings(str(guild.id))

        category = None
        cat_id = settings.get("ticket_category_id")
        if cat_id:
            category = guild.get_channel(int(cat_id))

        # Check existing ticket count
        clean_name = f"ticket-{interaction.user.name.lower()[:15]}"

        # Channel permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }

        # Grant support role access if configured
        support_role_id = settings.get("ticket_support_role_id")
        if support_role_id:
            s_role = guild.get_role(int(support_role_id))
            if s_role:
                overwrites[s_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            ch = await guild.create_text_channel(
                name=clean_name,
                category=category if isinstance(category, discord.CategoryChannel) else None,
                overwrites=overwrites,
                topic=f"Support ticket for {interaction.user} (ID: {interaction.user.id})"
            )

            # Persist ticket
            ticket_data = {
                "channel_id": str(ch.id),
                "guild_id": str(guild.id),
                "user_id": str(interaction.user.id),
                "created_at": time.time(),
                "status": "open",
                "claimed_by": None
            }
            db.save_ticket(str(ch.id), ticket_data)

            # Post control embed inside ticket channel
            embed = discord.Embed(
                title=f"🌸 Support Ticket • #{ch.name}",
                description=f"Hello {interaction.user.mention}! Welcome to your support ticket.\n\n"
                            "Please describe your question or issue in detail, and a staff member will be with you shortly!\n"
                            "Click **Close Ticket** when your inquiry has been resolved.",
                color=0xc084fc
            )
            embed.set_footer(text="Kazumi Support Tickets 🌸")
            embed.timestamp = datetime.now(timezone.utc)

            control_view = TicketControlView()
            await ch.send(content=f"{interaction.user.mention}", embed=embed, view=control_view)

            await interaction.response.send_message(f"✅ Your ticket has been created: {ch.mention}!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to create ticket: {e}", ephemeral=True)


def register_ticket_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    @tree.command(name="ticket", description="Manage Kazumi's support ticket system 📩")
    @app_commands.describe(
        action="Action (panel, setup, add, remove, transcript, close)",
        category="Category to place new tickets under (for setup)",
        support_role="Staff role permitted to manage tickets (for setup)",
        user="Member to add or remove from ticket"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Post Ticket Panel", value="panel"),
        app_commands.Choice(name="Setup Ticket Category & Staff Role", value="setup"),
        app_commands.Choice(name="Add Member to Ticket", value="add"),
        app_commands.Choice(name="Remove Member from Ticket", value="remove"),
        app_commands.Choice(name="Generate Ticket Transcript", value="transcript"),
        app_commands.Choice(name="Close Current Ticket", value="close"),
    ])
    async def slash_ticket(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        category: Optional[discord.CategoryChannel] = None,
        support_role: Optional[discord.Role] = None,
        user: Optional[discord.Member] = None
    ):
        if not interaction.guild:
            return

        gid = str(interaction.guild_id)

        if action.value == "setup":
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ You require **Manage Server** permission.", ephemeral=True)
                return
            updates = {}
            if category:
                updates["ticket_category_id"] = str(category.id)
            if support_role:
                updates["ticket_support_role_id"] = str(support_role.id)
            db.update_guild_settings(gid, updates)
            await interaction.response.send_message(f"✅ Ticket settings updated! Category: {category.name if category else 'None'} | Support Role: {support_role.mention if support_role else 'None'}")

        elif action.value == "panel":
            if not interaction.user.guild_permissions.manage_channels:
                await interaction.response.send_message("❌ You require **Manage Channels** permission.", ephemeral=True)
                return
            embed = discord.Embed(
                title="📩 Need Support?",
                description="Click the button below to create a private support ticket with our server staff team! 🌸\n\n"
                            "Our team will assist you as soon as possible.",
                color=0xa855f7
            )
            embed.set_footer(text="Kazumi Support Tickets 🌸")
            view = TicketLaunchView()
            await interaction.channel.send(embed=embed, view=view)
            await interaction.response.send_message("✅ Ticket panel posted!", ephemeral=True)

        elif action.value == "add":
            if not user:
                await interaction.response.send_message("❌ Specify a member to add.", ephemeral=True)
                return
            await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
            await interaction.response.send_message(f"✅ Added {user.mention} to this ticket.")

        elif action.value == "remove":
            if not user:
                await interaction.response.send_message("❌ Specify a member to remove.", ephemeral=True)
                return
            await interaction.channel.set_permissions(user, overwrite=None)
            await interaction.response.send_message(f"✅ Removed {user.mention} from this ticket.")

        elif action.value == "close":
            db.close_ticket(str(interaction.channel_id))
            embed = discord.Embed(
                title="🔒 Ticket Closed",
                description=f"Ticket closed by {interaction.user.mention}.",
                color=0xf59e0b
            )
            view = TicketClosedActionsView()
            await interaction.response.send_message(embed=embed, view=view)

        elif action.value == "transcript":
            await interaction.response.defer()
            messages = []
            async for m in interaction.channel.history(limit=500, oldest_first=True):
                time_str = m.created_at.strftime("%Y-%m-%d %H:%M:%S")
                messages.append(f"[{time_str}] {m.author}: {m.content}")

            transcript_text = "\n".join(messages)
            file_data = io.BytesIO(transcript_text.encode("utf-8"))
            discord_file = discord.File(file_data, filename=f"transcript-{interaction.channel.name}.txt")
            await interaction.followup.send("📜 Here is the complete transcript for this ticket:", file=discord_file)


class TicketManager:
    """Helper facade for Ticket operations."""
    @staticmethod
    def get_ticket(channel_id: str):
        return get_feature_db().get_ticket(str(channel_id))

    @staticmethod
    def is_ticket_channel(channel_id: str) -> bool:
        t = get_feature_db().get_ticket(str(channel_id))
        return t is not None

