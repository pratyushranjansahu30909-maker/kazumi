"""
================================================================================
🌸 KAZUMI ANNOUNCEMENT SYSTEM & SCHEDULER
================================================================================
Comprehensive announcements engine:
- Full layout presets: simple, embed, event, update, maintenance, giveaway, rules, welcome, custom
- Interactive Preview & Confirmation views (Publish, Edit, Cancel)
- Scheduled & recurring announcements with restart persistence
- Guild-isolated reusable templates (/announce template ...)
- Audit history, in-place edit, and bot announcement deletion
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

import discord
from discord import app_commands
from discord.ext import commands

from .giveaways import parse_duration
from .permissions import PermissionService

logger = logging.getLogger("KazumiAnnouncements")


# Preset Layout Definitions
PRESET_COLORS = {
    "simple": 0x94a3b8,        # Slate Gray
    "embed": 0xf43f5e,         # Kazumi Rose
    "event": 0x8b5cf6,         # Purple Lavender
    "update": 0x3b82f6,        # Sapphire Blue
    "maintenance": 0xf59e0b,   # Amber Warning
    "giveaway": 0xec4899,      # Pink Sparkle
    "rules": 0xef4444,         # Ruby Red
    "welcome": 0x10b981,       # Emerald Green
    "custom": 0xc084fc         # Light Violet
}


def parse_color_input(color_input: Optional[Any], default_color: int = 0xf43f5e) -> int:
    """Parses hex code string, preset name, or integer into integer color."""
    if color_input is None:
        return default_color
    if isinstance(color_input, int):
        return color_input
    clean = str(color_input).strip().lower()
    if clean in PRESET_COLORS:
        return PRESET_COLORS[clean]
    clean = clean.lstrip("#")
    try:
        return int(clean, 16)
    except ValueError:
        return default_color


def build_announcement_embed(
    title: str,
    message: str,
    preset: str = "embed",
    color: Optional[str] = None,
    image_url: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    footer: Optional[str] = None,
    author_name: Optional[str] = None,
    event_time: Optional[str] = None
) -> discord.Embed:
    """Builds a rich, styled Discord Embed based on parameters and layout preset."""
    embed_color = parse_color_input(color, PRESET_COLORS.get(preset, 0xf43f5e))
    
    preset_icons = {
        "event": "📅 ",
        "update": "🚀 ",
        "maintenance": "🛠️ ",
        "giveaway": "🎉 ",
        "rules": "📜 ",
        "welcome": "🌸 "
    }
    icon_prefix = preset_icons.get(preset, "📢 ")
    display_title = f"{icon_prefix}{title}" if not title.startswith(("📢", "📅", "🚀", "🛠️", "🎉", "📜", "🌸")) else title

    embed = discord.Embed(
        title=display_title,
        description=message,
        color=embed_color
    )

    if author_name:
        embed.set_author(name=author_name)
    if image_url:
        embed.set_image(url=image_url)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    if event_time:
        embed.add_field(name="⏰ Scheduled Time / Date", value=f"**{event_time}**", inline=False)

    default_footer = "Official Announcement • Kazumi Companion 🌸"
    embed.set_footer(text=footer or default_footer)
    embed.timestamp = datetime.now(timezone.utc)
    return embed


class AnnouncementPreviewView(discord.ui.View):
    """Interactive preview and confirmation workflow with buttons."""

    def __init__(
        self,
        embed: discord.Embed,
        target_channel: discord.TextChannel,
        author: discord.Member,
        outside_text: Optional[str] = None,
        link_button_url: Optional[str] = None,
        link_button_label: Optional[str] = None,
        db: Any = None
    ):
        super().__init__(timeout=300)
        self.embed = embed
        self.target_channel = target_channel
        self.author = author
        self.outside_text = outside_text
        self.link_button_url = link_button_url
        self.link_button_label = link_button_label
        self.db = db

        if link_button_url:
            self.add_item(discord.ui.Button(
                label=link_button_label or "More Info",
                url=link_button_url,
                style=discord.ButtonStyle.link
            ))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ Only the announcement author can confirm this preview.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Publish Announcement", style=discord.ButtonStyle.success, emoji="🚀")
    async def publish_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Broad mention safeguard
        is_broad_mention = False
        if self.outside_text and ("@everyone" in self.outside_text or "@here" in self.outside_text):
            is_broad_mention = True
            if not interaction.user.guild_permissions.mention_everyone:
                await interaction.response.send_message("❌ You lack permission to mention `@everyone` or `@here`.", ephemeral=True)
                return

        # Build view with link button for destination channel if provided
        dest_view = None
        if self.link_button_url:
            dest_view = discord.ui.View()
            dest_view.add_item(discord.ui.Button(
                label=self.link_button_label or "More Info",
                url=self.link_button_url,
                style=discord.ButtonStyle.link
            ))

        try:
            sent_msg = await self.target_channel.send(
                content=self.outside_text if self.outside_text else None,
                embed=self.embed,
                view=dest_view
            )

            # Store in announcement audit records
            if self.db:
                record = {
                    "id": str(sent_msg.id),
                    "guild_id": str(interaction.guild_id),
                    "channel_id": str(self.target_channel.id),
                    "author_id": str(self.author.id),
                    "title": self.embed.title,
                    "published_at": time.time()
                }
                self.db.record_announcement(record)

            self.stop()
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(
                content=f"✅ **Announcement published successfully!** Check {self.target_channel.mention}.",
                embed=None,
                view=None
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to publish announcement: {e}", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(
            content="🗑️ Announcement cancelled and discarded.",
            embed=None,
            view=None
        )


class AnnouncementScheduler:
    """Manages background checking and execution of scheduled announcements."""

    def __init__(self, bot: commands.Bot, db: Any):
        self.bot = bot
        self.db = db
        self._task: Optional[asyncio.Task] = None

    def start(self):
        try:
            loop = asyncio.get_running_loop()
            if not self._task or self._task.done():
                self._task = loop.create_task(self._scheduler_loop())
        except RuntimeError:
            # Event loop not started yet (e.g. module import/setup phase)
            pass

    async def check_and_execute_due_posts(self):
        """Processes all currently due scheduled announcements (test-friendly and on-demand)."""
        now = time.time()
        scheduled_items = self.db.get_scheduled_announcements()
        for item in scheduled_items:
            exec_time = item.get("execute_at") or item.get("scheduled_at", 0)
            if exec_time <= now and not item.get("executed", False):
                await self._execute_announcement(item)

    async def _scheduler_loop(self):
        await self.bot.wait_until_ready()
        logger.info("[Scheduler] Announcement background worker started.")
        while not self.bot.is_closed():
            try:
                await self.check_and_execute_due_posts()
            except Exception as e:
                logger.error(f"[Scheduler] Error processing scheduled announcements: {e}")
            await asyncio.sleep(15)

    async def _execute_announcement(self, item: Dict[str, Any]):
        channel_id = item.get("channel_id")
        try:
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                channel = await self.bot.fetch_channel(int(channel_id))

            embed_data = item.get("embed_data", {})
            title = embed_data.get("title") or item.get("title", "Announcement")
            description = embed_data.get("description") or item.get("message", "")
            color = embed_data.get("color") or item.get("color", 0xf43f5e)

            embed = discord.Embed(
                title=title,
                description=description,
                color=color
            )
            if embed_data.get("footer") or item.get("footer"):
                embed.set_footer(text=embed_data.get("footer") or item.get("footer"))
            if embed_data.get("image_url") or item.get("image_url"):
                embed.set_image(url=embed_data.get("image_url") or item.get("image_url"))
            embed.timestamp = datetime.now(timezone.utc)

            content = item.get("content") or item.get("text_outside")
            sent_msg = await channel.send(content=content, embed=embed)

            # Record in history
            if self.db:
                record = {
                    "id": str(getattr(sent_msg, "id", item["id"])),
                    "guild_id": str(item.get("guild_id", "default")),
                    "channel_id": str(channel_id),
                    "author_id": str(item.get("author_id", "scheduler")),
                    "title": title,
                    "published_at": time.time()
                }
                self.db.record_announcement(record)

            # Handle recurrence
            repeat = item.get("repeat") or item.get("recurrence")
            if repeat in {"daily", "weekly", "monthly"}:
                delta = 86400 if repeat == "daily" else (604800 if repeat == "weekly" else 2592000)
                item["execute_at"] = time.time() + delta
                item["scheduled_at"] = item["execute_at"]
                item["last_sent"] = time.time()
                self.db.save_scheduled_announcement(item["id"], item)
            else:
                item["executed"] = True
                item["executed_at"] = time.time()
                self.db.delete_scheduled_announcement(item["id"])

            logger.info(f"[Scheduler] Executed scheduled announcement {item['id']} in #{getattr(channel, 'name', channel_id)}")
        except Exception as e:
            logger.error(f"[Scheduler] Failed to send scheduled announcement {item['id']}: {e}")
            item["error"] = str(e)
            item["executed"] = True
            self.db.delete_scheduled_announcement(item["id"])


def setup_announcement_commands(tree: app_commands.CommandTree, bot: commands.Bot, db: Any) -> AnnouncementScheduler:
    """Registers full announcement command suite under /announce."""
    scheduler = AnnouncementScheduler(bot, db)
    scheduler.start()

    announce_group = app_commands.Group(
        name="announce",
        description="Create, schedule, and manage server announcements 📢"
    )
    template_group = app_commands.Group(
        name="template",
        description="Manage reusable announcement templates 📜",
        parent=announce_group
    )

    # 1. /announce post (or create rich embed)
    @announce_group.command(name="post", description="Create and publish an announcement 📢")
    @app_commands.describe(
        channel="Channel to post into",
        title="Title of the announcement",
        message="Main text content / description",
        preset="Layout preset (embed, event, update, maintenance, giveaway, rules, simple)",
        color="Custom color hex (e.g. #8B5CF6) or preset name",
        image_url="Optional banner image URL",
        ping_role="Optional role to notify/mention",
        link_button_url="Optional URL for a link button",
        link_button_label="Label for the link button"
    )
    @app_commands.choices(preset=[
        app_commands.Choice(name="Rich Embed (Default)", value="embed"),
        app_commands.Choice(name="Event Details", value="event"),
        app_commands.Choice(name="Development Update", value="update"),
        app_commands.Choice(name="Maintenance Notice", value="maintenance"),
        app_commands.Choice(name="Giveaway Alert", value="giveaway"),
        app_commands.Choice(name="Rules / Policy", value="rules"),
        app_commands.Choice(name="Welcome Greeting", value="welcome"),
        app_commands.Choice(name="Simple Text", value="simple"),
        app_commands.Choice(name="Fully Custom", value="custom")
    ])
    async def slash_post(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        message: str,
        preset: Optional[app_commands.Choice[str]] = None,
        color: Optional[str] = None,
        image_url: Optional[str] = None,
        ping_role: Optional[discord.Role] = None,
        link_button_url: Optional[str] = None,
        link_button_label: Optional[str] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You require **Manage Messages** permission to post announcements.", ephemeral=True)
            return

        preset_val = preset.value if preset else "embed"
        embed = build_announcement_embed(
            title=title,
            message=message,
            preset=preset_val,
            color=color,
            image_url=image_url,
            author_name=interaction.user.display_name
        )

        outside_text = ping_role.mention if ping_role else None

        preview_view = AnnouncementPreviewView(
            embed=embed,
            target_channel=channel,
            author=interaction.user,
            outside_text=outside_text,
            link_button_url=link_button_url,
            link_button_label=link_button_label,
            db=db
        )

        await interaction.response.send_message(
            content=f"🔍 **Announcement Preview** (Target: {channel.mention})\nReview your announcement and click **Publish Announcement** to send!",
            embed=embed,
            view=preview_view,
            ephemeral=True
        )

    # 2. /announce preview
    @announce_group.command(name="preview", description="Preview an announcement without publishing 🔍")
    @app_commands.describe(
        title="Title of the announcement",
        message="Main announcement content",
        preset="Layout preset",
        color="Hex color"
    )
    async def slash_preview(
        interaction: discord.Interaction,
        title: str,
        message: str,
        preset: Optional[str] = "embed",
        color: Optional[str] = None
    ):
        embed = build_announcement_embed(title=title, message=message, preset=preset or "embed", color=color)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # 3. /announce schedule
    @announce_group.command(name="schedule", description="Schedule an announcement for future publication ⏰")
    @app_commands.describe(
        channel="Destination channel",
        time_or_duration="When to publish (e.g. 10m, 2h, 1d)",
        title="Announcement title",
        message="Announcement text",
        preset="Layout preset"
    )
    async def slash_schedule(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        time_or_duration: str,
        title: str,
        message: str,
        preset: Optional[str] = "embed"
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You require **Manage Messages** permission.", ephemeral=True)
            return

        secs = parse_duration(time_or_duration)
        if not secs or secs < 10:
            await interaction.response.send_message("❌ Invalid time/duration format. Examples: `10m`, `2h`, `1d`.", ephemeral=True)
            return

        exec_at = time.time() + secs
        item_id = f"sch_{int(time.time())}_{interaction.user.id}"
        item = {
            "id": item_id,
            "guild_id": str(interaction.guild_id),
            "channel_id": str(channel.id),
            "author_id": str(interaction.user.id),
            "execute_at": exec_at,
            "repeat": None,
            "executed": False,
            "embed_data": {
                "title": title,
                "description": message,
                "color": PRESET_COLORS.get(preset, 0xf43f5e)
            }
        }
        db.save_scheduled_announcement(item_id, item)

        await interaction.response.send_message(
            f"⏰ **Announcement Scheduled!** ID: `{item_id}`\nDestination: {channel.mention}\nPublishes: <t:{int(exec_at)}:R> (<t:{int(exec_at)}:f>)",
            ephemeral=True
        )

    # 4. /announce repeat
    @announce_group.command(name="repeat", description="Schedule a recurring announcement (daily, weekly, monthly) 🔁")
    @app_commands.describe(
        channel="Destination channel",
        interval="Recurrence frequency (daily, weekly, monthly)",
        title="Announcement title",
        message="Announcement message"
    )
    @app_commands.choices(interval=[
        app_commands.Choice(name="Daily (every 24 hours)", value="daily"),
        app_commands.Choice(name="Weekly (every 7 days)", value="weekly"),
        app_commands.Choice(name="Monthly (every 30 days)", value="monthly")
    ])
    async def slash_repeat(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        interval: app_commands.Choice[str],
        title: str,
        message: str
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You require **Manage Server** permission to configure recurring announcements.", ephemeral=True)
            return

        delta = 86400 if interval.value == "daily" else (604800 if interval.value == "weekly" else 2592000)
        exec_at = time.time() + delta
        item_id = f"rep_{int(time.time())}"
        item = {
            "id": item_id,
            "guild_id": str(interaction.guild_id),
            "channel_id": str(channel.id),
            "author_id": str(interaction.user.id),
            "execute_at": exec_at,
            "repeat": interval.value,
            "executed": False,
            "embed_data": {
                "title": title,
                "description": message,
                "color": 0x3b82f6
            }
        }
        db.save_scheduled_announcement(item_id, item)

        await interaction.response.send_message(
            f"🔁 **Recurring Announcement Configured!** (`{interval.name}`)\nNext run: <t:{int(exec_at)}:R> in {channel.mention}\nID: `{item_id}`",
            ephemeral=True
        )

    # 5. /announce list
    @announce_group.command(name="list", description="List upcoming scheduled announcements for this server 📋")
    async def slash_list(interaction: discord.Interaction):
        items = [i for i in db.get_scheduled_announcements() if str(i.get("guild_id")) == str(interaction.guild_id) and not i.get("executed")]
        if not items:
            await interaction.response.send_message("No scheduled announcements currently pending for this server! 🌸", ephemeral=True)
            return

        lines = []
        for i in items:
            rep_str = f" • Repeat: `{i.get('repeat')}`" if i.get("repeat") else ""
            lines.append(f"• **{i.get('embed_data', {}).get('title')}** (ID: `{i['id']}`)\n  Channel: <#{i['channel_id']}> • <t:{int(i['execute_at'])}:R>{rep_str}")

        embed = discord.Embed(
            title="⏰ Scheduled Announcements",
            description="\n\n".join(lines),
            color=0x8b5cf6
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # 6. /announce cancel
    @announce_group.command(name="cancel", description="Cancel a scheduled announcement 🚫")
    @app_commands.describe(announcement_id="ID of the scheduled announcement to cancel")
    async def slash_cancel(interaction: discord.Interaction, announcement_id: str):
        if not interaction.guild or not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You require **Manage Messages** permission.", ephemeral=True)
            return

        success = db.delete_scheduled_announcement(announcement_id)
        if success:
            await interaction.response.send_message(f"✅ Scheduled announcement `{announcement_id}` has been cancelled.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Scheduled announcement `{announcement_id}` not found.", ephemeral=True)

    # 7. /announce edit
    @announce_group.command(name="edit", description="Edit an existing announcement message posted by Kazumi ✏️")
    @app_commands.describe(
        channel="Channel where announcement was posted",
        message_id="Message ID of the announcement",
        title="Updated title",
        message="Updated message text",
        color="Optional updated color"
    )
    async def slash_edit(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message_id: str,
        title: str,
        message: str,
        color: Optional[str] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You require **Manage Messages** permission.", ephemeral=True)
            return

        try:
            target_msg = await channel.fetch_message(int(message_id))
            if target_msg.author.id != bot.user.id:
                await interaction.response.send_message("❌ I can only edit announcements posted by Kazumi.", ephemeral=True)
                return

            embed = build_announcement_embed(title=title, message=message, color=color, author_name=interaction.user.display_name)
            await target_msg.edit(embed=embed)
            await interaction.response.send_message(f"✅ Announcement in {channel.mention} has been updated!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to edit announcement: {e}", ephemeral=True)

    # 8. /announce delete
    @announce_group.command(name="delete", description="Delete an announcement message posted by Kazumi 🗑️")
    @app_commands.describe(
        channel="Channel where announcement was posted",
        message_id="Message ID to delete"
    )
    async def slash_delete(interaction: discord.Interaction, channel: discord.TextChannel, message_id: str):
        if not interaction.guild or not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You require **Manage Messages** permission.", ephemeral=True)
            return

        try:
            target_msg = await channel.fetch_message(int(message_id))
            if target_msg.author.id != bot.user.id:
                await interaction.response.send_message("❌ I can only delete announcements authored by Kazumi.", ephemeral=True)
                return

            await target_msg.delete()
            await interaction.response.send_message("✅ Announcement deleted successfully.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to delete announcement: {e}", ephemeral=True)

    # 9. /announce history
    @announce_group.command(name="history", description="View recent published announcement history 📜")
    async def slash_history(interaction: discord.Interaction):
        records = db.get_announcement_history(str(interaction.guild_id))
        if not records:
            await interaction.response.send_message("No announcements have been recorded yet in this server! 🌸", ephemeral=True)
            return

        lines = []
        for r in records[-10:][::-1]:
            d_str = f"<t:{int(r.get('published_at', 0))}:R>"
            lines.append(f"• **{r.get('title')}** in <#{r.get('channel_id')}> ({d_str}) — ID: `{r.get('id')}`")

        embed = discord.Embed(
            title="📢 Recent Announcement History",
            description="\n".join(lines),
            color=0xf43f5e
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # =========================================================================
    # Reusable Templates Subgroup (/announce template ...)
    # =========================================================================
    @template_group.command(name="create", description="Save a reusable announcement template 💾")
    @app_commands.describe(
        name="Short identifier for template (e.g. weekly-update)",
        title="Default title",
        description="Default template description/body",
        color="Default hex color",
        footer="Default footer text"
    )
    async def slash_tpl_create(
        interaction: discord.Interaction,
        name: str,
        title: str,
        description: str,
        color: Optional[str] = None,
        footer: Optional[str] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You require **Manage Server** permission to create templates.", ephemeral=True)
            return

        tpl = {
            "name": name.lower().strip(),
            "title": title,
            "description": description,
            "color": color or "#f43f5e",
            "footer": footer or "Kazumi Template 🌸",
            "author_id": str(interaction.user.id),
            "updated_at": time.time()
        }
        db.save_announcement_template(str(interaction.guild_id), tpl["name"], tpl)
        await interaction.response.send_message(f"✅ Template **{tpl['name']}** created successfully!", ephemeral=True)

    @template_group.command(name="list", description="List available announcement templates in this server 📜")
    async def slash_tpl_list(interaction: discord.Interaction):
        tpls = db.get_announcement_templates(str(interaction.guild_id))
        if not tpls:
            await interaction.response.send_message("No saved templates found for this server! Create one with `/announce template create` 🌸", ephemeral=True)
            return

        lines = [f"• **{k}**: {v.get('title')}" for k, v in tpls.items()]
        embed = discord.Embed(
            title="📜 Server Announcement Templates",
            description="\n".join(lines),
            color=0xc084fc
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @template_group.command(name="delete", description="Delete a saved announcement template 🗑️")
    @app_commands.describe(name="Template identifier to delete")
    async def slash_tpl_delete(interaction: discord.Interaction, name: str):
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You require **Manage Server** permission.", ephemeral=True)
            return

        deleted = db.delete_announcement_template(str(interaction.guild_id), name.lower().strip())
        if deleted:
            await interaction.response.send_message(f"✅ Template **{name}** deleted.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Template **{name}** not found.", ephemeral=True)

    @template_group.command(name="use", description="Publish an announcement using a saved template 🚀")
    @app_commands.describe(
        name="Template name to use",
        channel="Channel to post into",
        custom_message="Optional custom text override"
    )
    async def slash_tpl_use(
        interaction: discord.Interaction,
        name: str,
        channel: discord.TextChannel,
        custom_message: Optional[str] = None
    ):
        if not interaction.guild or not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You require **Manage Messages** permission.", ephemeral=True)
            return

        tpl = db.get_announcement_template(str(interaction.guild_id), name.lower().strip())
        if not tpl:
            await interaction.response.send_message(f"❌ Template **{name}** not found.", ephemeral=True)
            return

        embed = build_announcement_embed(
            title=tpl.get("title", "Announcement"),
            message=custom_message or tpl.get("description", ""),
            color=tpl.get("color"),
            footer=tpl.get("footer"),
            author_name=interaction.user.display_name
        )

        preview_view = AnnouncementPreviewView(
            embed=embed,
            target_channel=channel,
            author=interaction.user,
            db=db
        )

        await interaction.response.send_message(
            content=f"🔍 Template **{name}** loaded! Click **Publish Announcement** to send to {channel.mention}.",
            embed=embed,
            view=preview_view,
            ephemeral=True
        )

    tree.add_command(announce_group)
    logger.info("Announcement system slash commands registered successfully.")
    return scheduler
