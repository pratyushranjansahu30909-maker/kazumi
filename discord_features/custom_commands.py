"""
🌸 Kazumi Discord Features — Custom Commands System
Enables server administrators to create custom text or embed commands with variables:
- Variables: {user}, {username}, {server}, {channel}
- Commands: /customcommand add, /customcommand delete, /customcommand list, /tag <name>
"""

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from discord_features.database import get_feature_db


class CustomCommandDispatcher:
    """Dispatches custom commands invoked via prefix or slash command."""

    @staticmethod
    def render_custom_response(template: str, message: discord.Message) -> str:
        text = str(template or "")
        text = text.replace("{user}", str(getattr(message.author, "mention", "")))
        text = text.replace("{username}", str(getattr(message.author, "name", "User")))
        text = text.replace("{server}", str(getattr(message.guild, "name", "Server") if getattr(message, "guild", None) else "Server"))
        chan_mention = getattr(message.channel, "mention", "") if hasattr(message, "channel") else ""
        text = text.replace("{channel}", str(chan_mention))
        return text


    @classmethod
    async def maybe_handle_message(cls, message: discord.Message) -> bool:
        if not message.guild or message.author.bot:
            return False

        content = (message.content or "").strip()
        if not content.startswith("!"):
            return False

        cmd_trigger = content[1:].split()[0].lower()
        db = get_feature_db()
        custom = db.get_custom_command(str(message.guild.id), cmd_trigger)
        if not custom:
            return False

        reply_content = cls.render_custom_response(custom["response"], message)
        try:
            await message.channel.send(reply_content)
            return True
        except Exception:
            return False


def register_custom_command_slash(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    @tree.command(name="customcommand", description="Create or manage custom server commands ⚙️")
    @app_commands.describe(
        action="Action (add, delete, list)",
        name="Trigger word for the command (e.g. rules, website)",
        response="Response message (Variables: {user}, {username}, {server}, {channel})"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add Custom Command", value="add"),
        app_commands.Choice(name="Delete Custom Command", value="delete"),
        app_commands.Choice(name="List Custom Commands", value="list"),
    ])
    async def slash_customcommand(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        name: Optional[str] = None,
        response: Optional[str] = None
    ):
        if not interaction.guild:
            return

        gid = str(interaction.guild_id)

        if action.value == "add":
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ You require **Manage Server** permission.", ephemeral=True)
                return

            if not name or not response:
                await interaction.response.send_message("❌ Please provide both `name` and `response`.", ephemeral=True)
                return

            clean_name = name.strip().lower().lstrip("!")
            db.add_custom_command(gid, clean_name, response, str(interaction.user.id))
            await interaction.response.send_message(f"✅ Custom command `!{clean_name}` has been created!\n>>> {response}")

        elif action.value == "delete":
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("❌ You require **Manage Server** permission.", ephemeral=True)
                return

            if not name:
                await interaction.response.send_message("❌ Specify the command name to delete.", ephemeral=True)
                return

            clean_name = name.strip().lower().lstrip("!")
            deleted = db.delete_custom_command(gid, clean_name)
            if deleted:
                await interaction.response.send_message(f"✅ Custom command `!{clean_name}` was deleted.")
            else:
                await interaction.response.send_message(f"❌ Command `!{clean_name}` does not exist.", ephemeral=True)

        elif action.value == "list":
            cmds = db.list_custom_commands(gid)
            if not cmds:
                await interaction.response.send_message("⚙️ No custom commands are configured in this server.", ephemeral=True)
                return

            lines = [f"• `!{c}`" for c in cmds]
            embed = discord.Embed(
                title=f"⚙️ Custom Server Commands ({len(cmds)})",
                description="\n".join(lines),
                color=0x38bdf8
            )
            embed.set_footer(text="Kazumi Custom Commands 🌸")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @tree.command(name="tag", description="Invoke a custom server tag/command 🏷️")
    @app_commands.describe(name="The name of the custom command to trigger")
    async def slash_tag(interaction: discord.Interaction, name: str):
        if not interaction.guild:
            return
        clean_name = name.strip().lower().lstrip("!")
        custom = db.get_custom_command(str(interaction.guild_id), clean_name)
        if not custom:
            await interaction.response.send_message(f"❌ Custom command `!{clean_name}` does not exist.", ephemeral=True)
            return

        text = custom["response"]
        text = text.replace("{user}", interaction.user.mention)
        text = text.replace("{username}", interaction.user.name)
        text = text.replace("{server}", interaction.guild.name)
        text = text.replace("{channel}", interaction.channel.mention if hasattr(interaction.channel, "mention") else "")
        await interaction.response.send_message(text)
