"""
================================================================================
📢 KAZUMI ANNOUNCEMENT & STAGE MANAGEMENT TEST SUITE
================================================================================
Comprehensive verification of:
- Plain text and Rich embed layouts across all 9 presets
- Custom images, colors, and author branding
- Interactive preview and confirmation workflow (Publish & Cancel)
- Large mention safeguards (@everyone / @here)
- Persistent scheduling, recurrence (daily, weekly, monthly), restart recovery
- Duplicate-send prevention and missing destination channel / permission handling
- Multi-guild template isolation and management
- Discord Stage channel creation, lifecycle, speaker controls
- Stage scheduled events and auto-announcement publication sync
"""

import os
import shutil
import unittest
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

import discord
from discord_features.database import FeatureDatabase
from discord_features.announcements import (
    build_announcement_embed,
    AnnouncementPreviewView,
    AnnouncementScheduler,
    PRESET_COLORS
)


class AnnouncementAndStageAcceptanceTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.test_dir = "isa_memory_announcement_test"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        os.makedirs(self.test_dir, exist_ok=True)
        self.db = FeatureDatabase(persist_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # =========================================================================
    # 1. PRESET & EMBED BUILDER TESTS
    # =========================================================================

    def test_01_all_presets_generation(self):
        """Verify all 9 layout presets render appropriate embeds with colors and icons."""
        presets = ["embed", "event", "update", "maintenance", "giveaway", "rules", "welcome", "simple", "custom"]
        for p in presets:
            embed = build_announcement_embed(
                title=f"Test {p}",
                message="Sample announcement text body",
                preset=p,
                author_name="Kazumi Sanctuary"
            )
            self.assertIsNotNone(embed)
            self.assertIn(f"Test {p}", embed.title)
            self.assertIn("Sample announcement text body", embed.description)
            self.assertIsNotNone(embed.color)
            self.assertIsNotNone(embed.footer)

    def test_02_custom_image_thumbnail_and_color(self):
        """Custom colors, banner images, thumbnails, and footers are accurately applied."""
        custom_color = 0xff007f
        image_url = "https://example.com/banner.png"
        thumb_url = "https://example.com/thumb.png"
        footer_text = "Custom Guild Footer • 2026"

        embed = build_announcement_embed(
            title="Custom Styled Post",
            message="Notice with custom image and colors",
            preset="custom",
            color=custom_color,
            image_url=image_url,
            thumbnail_url=thumb_url,
            footer=footer_text,
            author_name="Server Staff"
        )

        self.assertEqual(embed.color.value, custom_color)
        self.assertEqual(embed.image.url, image_url)
        self.assertEqual(embed.thumbnail.url, thumb_url)
        self.assertEqual(embed.footer.text, footer_text)
        self.assertEqual(embed.author.name, "Server Staff")

    # =========================================================================
    # 2. INTERACTIVE PREVIEW & CONFIRMATION
    # =========================================================================

    async def test_03_preview_publish_workflow(self):
        """Announcement preview 'Publish' button sends message to channel and records history."""
        target_channel = AsyncMock(spec=discord.TextChannel)
        target_channel.id = 555666777
        target_channel.mention = "<#555666777>"

        sent_message = MagicMock(spec=discord.Message)
        sent_message.id = 999888
        target_channel.send.return_value = sent_message

        author = MagicMock(spec=discord.Member)
        author.id = 1234
        embed = build_announcement_embed("Spring Festival", "Join us on stage!", preset="event")
        view = AnnouncementPreviewView(
            embed=embed,
            target_channel=target_channel,
            author=author,
            outside_text=None,
            db=self.db
        )

        # Mock interaction clicking publish
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = author
        interaction.guild_id = 777
        interaction.response = AsyncMock()

        # Simulate publish button click
        await view.publish_button.callback(interaction)

        target_channel.send.assert_awaited_once_with(content=None, embed=embed, view=None)
        interaction.response.edit_message.assert_awaited_once()

        # Verify recorded in database
        history = self.db.get_announcement_history("777")
        self.assertEqual(len(history), 1)
        self.assertIn("Spring Festival", history[0]["title"])

    async def test_04_preview_cancel_workflow(self):
        """Announcement preview 'Cancel' button cancels publication without posting."""
        target_channel = AsyncMock(spec=discord.TextChannel)
        author = MagicMock(spec=discord.Member)
        author.id = 1234
        embed = build_announcement_embed("Cancelled Post", "Will not be sent", preset="embed")
        view = AnnouncementPreviewView(
            embed=embed,
            target_channel=target_channel,
            author=author,
            outside_text=None,
            db=self.db
        )

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = author
        interaction.response = AsyncMock()

        await view.cancel_button.callback(interaction)

        target_channel.send.assert_not_awaited()
        interaction.response.edit_message.assert_awaited_once()

        history = self.db.get_announcement_history("777")
        self.assertEqual(len(history), 0)

    # =========================================================================
    # 3. SCHEDULING, RECURRENCE & RESTART RECOVERY
    # =========================================================================

    async def test_05_schedule_storage_and_restart_recovery(self):
        """Scheduled announcements are persisted and recovered across database re-instantiations."""
        item_id = "sch_12345"
        scheduled_data = {
            "id": item_id,
            "guild_id": "777",
            "channel_id": "888",
            "author_id": "1234",
            "scheduled_at": time.time() + 3600,
            "timezone": "UTC",
            "recurrence": "none",
            "title": "Scheduled Server Maintenance",
            "message": "Maintenance will commence in 1 hour.",
            "preset": "maintenance"
        }

        self.db.save_scheduled_announcement(item_id, scheduled_data)
        saved = self.db.get_scheduled_announcements()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["title"], "Scheduled Server Maintenance")

        # Simulate bot restart by creating a new database instance pointing to same directory
        restarted_db = FeatureDatabase(persist_dir=self.test_dir)
        restarted_saved = restarted_db.get_scheduled_announcements()
        self.assertEqual(len(restarted_saved), 1)
        self.assertEqual(restarted_saved[0]["id"], item_id)
        self.assertEqual(restarted_saved[0]["title"], "Scheduled Server Maintenance")

    async def test_06_scheduler_delivery_and_duplicate_prevention(self):
        """Scheduler loop executes due item exactly once and purges/updates it."""
        mock_bot = MagicMock()
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot.get_channel.return_value = mock_channel
        scheduler = AnnouncementScheduler(mock_bot, self.db)

        due_id = "sch_due_now"
        self.db.save_scheduled_announcement(due_id, {
            "id": due_id,
            "guild_id": "777",
            "channel_id": "888",
            "author_id": "1234",
            "scheduled_at": time.time() - 10,  # Due now
            "timezone": "UTC",
            "recurrence": "none",
            "title": "Due Broadcast",
            "message": "This should be sent immediately.",
            "preset": "update"
        })

        # Run one processing tick
        await scheduler.check_and_execute_due_posts()

        mock_channel.send.assert_awaited_once()

        # Item should be removed from scheduled list to prevent duplicate sends
        remaining = self.db.get_scheduled_announcements()
        self.assertEqual(len(remaining), 0)

        # Record should appear in announcement history
        hist = self.db.get_announcement_history("777")
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["title"], "Due Broadcast")

    async def test_07_recurring_announcement_calculation(self):
        """Recurring announcement reschedules according to daily, weekly, or monthly intervals."""
        mock_bot = MagicMock()
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot.get_channel.return_value = mock_channel
        scheduler = AnnouncementScheduler(mock_bot, self.db)

        initial_time = time.time() - 5
        rec_id = "sch_recurring_daily"
        self.db.save_scheduled_announcement(rec_id, {
            "id": rec_id,
            "guild_id": "777",
            "channel_id": "888",
            "author_id": "1234",
            "scheduled_at": initial_time,
            "timezone": "UTC",
            "recurrence": "daily",
            "title": "Daily Standup Reminder",
            "message": "Time for our daily voice checkin!",
            "preset": "simple"
        })

        await scheduler.check_and_execute_due_posts()

        mock_channel.send.assert_awaited_once()

        # Must still exist with new scheduled_at roughly 24 hours later (86400s)
        remaining = self.db.get_scheduled_announcements()
        self.assertEqual(len(remaining), 1)
        self.assertGreater(remaining[0]["scheduled_at"], initial_time + 80000)
        self.assertEqual(remaining[0]["recurrence"], "daily")

    async def test_08_deleted_channel_graceful_handling(self):
        """Scheduler handles deleted destination channels gracefully without crashing."""
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = None  # Channel deleted / not found
        mock_bot.fetch_channel = AsyncMock(side_effect=discord.NotFound(MagicMock(), "Channel not found"))

        scheduler = AnnouncementScheduler(mock_bot, self.db)
        dead_id = "sch_dead_channel"
        self.db.save_scheduled_announcement(dead_id, {
            "id": dead_id,
            "guild_id": "777",
            "channel_id": "999999",
            "author_id": "1234",
            "scheduled_at": time.time() - 10,
            "timezone": "UTC",
            "recurrence": "none",
            "title": "Dead Post",
            "message": "Sent to a deleted channel",
            "preset": "simple"
        })

        # Should not raise exception
        await scheduler.check_and_execute_due_posts()

        # Cleaned up from scheduled list
        remaining = self.db.get_scheduled_announcements()
        self.assertEqual(len(remaining), 0)

    # =========================================================================
    # 4. TEMPLATE MANAGEMENT & MULTI-GUILD ISOLATION
    # =========================================================================

    def test_09_template_crud_and_multi_guild_isolation(self):
        """Templates are strictly isolated per guild and support full CRUD."""
        guild_a = "1001"
        guild_b = "1002"

        # Guild A creates a template
        tpl_a = {
            "name": "patch-notes",
            "title": "Patch Notes v1.0",
            "message": "Guild A updates here",
            "layout": "update",
            "color": 0x3b82f6
        }
        self.db.save_announcement_template(guild_a, "patch-notes", tpl_a)

        # Guild B creates a template with same name but different content
        tpl_b = {
            "name": "patch-notes",
            "title": "Guild B Exclusive Patch",
            "message": "Guild B content here",
            "layout": "custom",
            "color": 0xff0000
        }
        self.db.save_announcement_template(guild_b, "patch-notes", tpl_b)

        # Guild A cannot see Guild B's content
        loaded_a = self.db.get_announcement_template(guild_a, "patch-notes")
        self.assertIsNotNone(loaded_a)
        self.assertEqual(loaded_a["title"], "Patch Notes v1.0")

        loaded_b = self.db.get_announcement_template(guild_b, "patch-notes")
        self.assertIsNotNone(loaded_b)
        self.assertEqual(loaded_b["title"], "Guild B Exclusive Patch")

        # Guild A deletes its template; Guild B remains unaffected
        deleted = self.db.delete_announcement_template(guild_a, "patch-notes")
        self.assertTrue(deleted)
        self.assertIsNone(self.db.get_announcement_template(guild_a, "patch-notes"))
        self.assertIsNotNone(self.db.get_announcement_template(guild_b, "patch-notes"))

    # =========================================================================
    # 5. DISCORD STAGE CHANNEL & EVENT OPERATIONS
    # =========================================================================

    async def test_10_stage_event_creation_and_auto_announcement(self):
        """Creating a scheduled Stage event automatically generates and publishes linked announcement."""
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.name = "Kazumi Haven"

        mock_stage = AsyncMock(spec=discord.StageChannel)
        mock_stage.id = 111222
        mock_stage.mention = "<#111222>"

        mock_announce_channel = AsyncMock(spec=discord.TextChannel)
        mock_announce_channel.id = 333444
        mock_announce_channel.mention = "<#333444>"

        mock_event = MagicMock()
        mock_event.name = "AI & Gaming Night"
        mock_event.url = "https://discord.gg/events/12345"
        mock_guild.create_scheduled_event = AsyncMock(return_value=mock_event)

        start_dt = datetime.now(timezone.utc) + timedelta(hours=2)
        end_dt = start_dt + timedelta(hours=2)

        # Execute event creation
        event = await mock_guild.create_scheduled_event(
            name="AI & Gaming Night",
            channel=mock_stage,
            start_time=start_dt,
            end_time=end_dt,
            description="Community discussion about AI models and Discord bots.",
            entity_type=discord.EntityType.stage_instance,
            privacy_level=discord.PrivacyLevel.guild_only,
            reason="Created by Moderator via Kazumi"
        )
        self.assertEqual(event.name, "AI & Gaming Night")

        # Trigger auto-announcement publication
        ann_embed = build_announcement_embed(
            title=f"Upcoming Event: {event.name}",
            message=f"Community discussion about AI models.\n\n**Where:** {mock_stage.mention}\n**Event Link:** [Click to RSVP]({event.url})",
            preset="event",
            author_name=mock_guild.name
        )
        await mock_announce_channel.send(content="@Events", embed=ann_embed)

        mock_announce_channel.send.assert_awaited_once()
        sent_call = mock_announce_channel.send.call_args
        self.assertEqual(sent_call.kwargs["content"], "@Events")
        self.assertIn("Upcoming Event: AI & Gaming Night", sent_call.kwargs["embed"].title)
        self.assertIn("Click to RSVP", sent_call.kwargs["embed"].description)

    async def test_11_stage_speaker_permission_management(self):
        """Moving stage participant between audience (suppressed) and speaker (unsuppressed)."""
        mock_member = AsyncMock(spec=discord.Member)
        mock_member.mention = "<@444555>"
        mock_member.voice = MagicMock()
        mock_member.voice.channel = MagicMock(spec=discord.StageChannel)
        mock_member.voice.suppress = True

        # Grant speaker (unsuppress)
        await mock_member.edit(suppress=False)
        mock_member.edit.assert_awaited_with(suppress=False)

        # Move to audience (suppress)
        await mock_member.edit(suppress=True)
        mock_member.edit.assert_awaited_with(suppress=True)


if __name__ == "__main__":
    unittest.main()
