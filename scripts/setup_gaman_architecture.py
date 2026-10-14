# -*- coding: utf-8 -*-
"""
Setup and Provisioning script for Gaman Discord Server (ID: 1554152397327044729)
Phase 2 — Advanced Channel Architecture
Guarantees:
- Strict scope isolation: Only touches guild ID 1554152397327044729
- Preserves existing channels, messages, and roles
- Creates genuine Discord News, Stage, and Forum channels
- Configures precise permissions and role overwrites
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import os
import asyncio
import logging
from typing import Dict, Optional, Any

import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TARGET_GUILD_ID = 1554152397327044729

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GamanSetup")

async def setup_gaman():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            guild = client.get_guild(TARGET_GUILD_ID)
            if not guild:
                logger.error(f"Guild {TARGET_GUILD_ID} not found!")
                await client.close()
                return

            assert guild.id == TARGET_GUILD_ID, f"CRITICAL: Scope mismatch! {guild.id} != {TARGET_GUILD_ID}"
            logger.info(f"Connected to target guild: {guild.name} ({guild.id})")

            # Roles lookup
            roles_by_name = {r.name: r for r in guild.roles}
            everyone_role = guild.default_role
            admin_role = roles_by_name.get("Administrator")
            mod_role = roles_by_name.get("Moderator")
            trial_mod_role = roles_by_name.get("Trial Moderator")
            event_host_role = roles_by_name.get("Event Host")
            member_role = roles_by_name.get("Member")
            newcomer_role = roles_by_name.get("Newcomer")
            kazumi_bot_member = guild.me

            # Assign Member role to all existing human members who don't have it
            if member_role:
                for member in guild.members:
                    if not member.bot and member_role not in member.roles:
                        try:
                            await member.add_roles(member_role, reason="Gaman onboarding baseline")
                            logger.info(f"Assigned Member role to {member.display_name}")
                        except Exception as e:
                            logger.warning(f"Could not assign Member role to {member.display_name}: {e}")

            # Overwrite presets
            staff_roles = [r for r in [admin_role, mod_role, trial_mod_role] if r]

            def staff_only_overwrites():
                ow = {
                    everyone_role: discord.PermissionOverwrite(view_channel=False),
                    kazumi_bot_member: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True, read_message_history=True)
                }
                for sr in staff_roles:
                    ow[sr] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
                return ow

            def read_only_public_overwrites(allow_reactions=True):
                ow = {
                    everyone_role: discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True, add_reactions=allow_reactions),
                    kazumi_bot_member: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True, read_message_history=True)
                }
                for sr in staff_roles:
                    ow[sr] = discord.PermissionOverwrite(send_messages=True)
                return ow

            def public_chat_overwrites():
                return {
                    everyone_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, embed_links=True, attach_files=True, add_reactions=True),
                    kazumi_bot_member: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, attach_files=True, read_message_history=True, add_reactions=True)
                }

            # Map existing categories
            categories = {c.name.strip(): c for c in guild.categories}
            
            # Reuse/rename existing categories if present
            cat_start = categories.get("✨ START HERE") or categories.get("Text channels")
            if cat_start and cat_start.name != "✨ START HERE":
                await cat_start.edit(name="✨ START HERE", position=0)
            elif not cat_start:
                cat_start = await guild.create_category("✨ START HERE", position=0)

            cat_comm = categories.get("🌐 GAMAN COMMUNITY")
            if not cat_comm:
                cat_comm = await guild.create_category("🌐 GAMAN COMMUNITY", position=1)

            cat_kazumi = categories.get("🌸 KAZUMI AI SPACE")
            if not cat_kazumi:
                cat_kazumi = await guild.create_category("🌸 KAZUMI AI SPACE", position=2)

            cat_games = categories.get("🎮 GAMES & ACTIVITIES")
            if not cat_games:
                cat_games = await guild.create_category("🎮 GAMES & ACTIVITIES", position=3)

            cat_voice = categories.get("🎙️ VOICE & LIVE") or categories.get("Voice channels")
            if cat_voice and cat_voice.name != "🎙️ VOICE & LIVE":
                await cat_voice.edit(name="🎙️ VOICE & LIVE", position=4)
            elif not cat_voice:
                cat_voice = await guild.create_category("🎙️ VOICE & LIVE", position=4)

            cat_events = categories.get("📅 EVENTS")
            if not cat_events:
                cat_events = await guild.create_category("📅 EVENTS", position=5)

            cat_support = categories.get("🛡️ MODERATION & SUPPORT")
            if not cat_support:
                cat_support = await guild.create_category("🛡️ MODERATION & SUPPORT", position=6)

            cat_staff = categories.get("🔐 STAFF CONTROL ROOM")
            if not cat_staff:
                cat_staff = await guild.create_category(
                    "🔐 STAFF CONTROL ROOM",
                    position=7,
                    overwrites=staff_only_overwrites()
                )
            else:
                await cat_staff.edit(overwrites=staff_only_overwrites())

            logger.info("All 8 Categories provisioned.")

            # Existing channels lookup by type
            existing_text = {ch.name.lower(): ch for ch in guild.text_channels}
            existing_voice = {ch.name.lower(): ch for ch in guild.voice_channels}
            existing_stage = {ch.name.lower(): ch for ch in guild.stage_channels}
            existing_forum = {ch.name.lower(): ch for ch in guild.forums}

            async def ensure_text_channel(name, category, topic="", news=False, overwrites=None):
                clean = name.lower()
                if clean in existing_text:
                    ch = existing_text[clean]
                    logger.info(f"Reusing existing text channel #{ch.name} (id: {ch.id})")
                    if ch.category != category:
                        await ch.edit(category=category)
                    if topic and getattr(ch, "topic", None) != topic:
                        await ch.edit(topic=topic)
                    if overwrites:
                        await ch.edit(overwrites=overwrites)
                    return ch
                else:
                    logger.info(f"Creating channel #{name} in {category.name}")
                    kwargs = {"category": category, "topic": topic, "news": news}
                    if overwrites:
                        kwargs["overwrites"] = overwrites
                    ch = await guild.create_text_channel(name, **kwargs)
                    existing_text[name.lower()] = ch
                    return ch

            async def ensure_voice_channel(name, category, user_limit=0):
                clean = name.lower()
                if clean in existing_voice:
                    ch = existing_voice[clean]
                    if ch.category != category:
                        await ch.edit(category=category)
                    return ch
                logger.info(f"Creating voice channel '{name}' in {category.name}")
                ch = await guild.create_voice_channel(name, category=category, user_limit=user_limit)
                existing_voice[name.lower()] = ch
                return ch

            async def ensure_stage_channel(name, category):
                clean = name.lower()
                if clean in existing_stage:
                    ch = existing_stage[clean]
                    if ch.category != category:
                        await ch.edit(category=category)
                    return ch
                logger.info(f"Creating Stage channel '{name}' in {category.name}")
                try:
                    ch = await guild.create_stage_channel(name, category=category)
                    existing_stage[name.lower()] = ch
                    return ch
                except Exception as e:
                    logger.warning(f"Could not create stage channel: {e}")
                    return None

            async def ensure_forum_channel(name, category, topic=""):
                clean = name.lower()
                if clean in existing_forum:
                    ch = existing_forum[clean]
                    if ch.category != category:
                        await ch.edit(category=category)
                    return ch
                logger.info(f"Creating Forum channel '{name}' in {category.name}")
                try:
                    ch = await guild.create_forum(name, category=category, topic=topic)
                    existing_forum[name.lower()] = ch
                    return ch
                except Exception as e:
                    logger.warning(f"Could not create forum channel {name}: {e}, falling back to text channel")
                    return await ensure_text_channel(name, category, topic=topic)

            # 1. ✨ START HERE
            welcome_ch = await ensure_text_channel("welcome", cat_start, topic="Welcome to Gaman! Meet new friends and receive Kazumi's welcome poem 🌸", overwrites=read_only_public_overwrites())
            rules_ch = await ensure_text_channel("rules", cat_start, topic="Official Gaman Community Rules and Guidelines. Please read thoroughly 📜", overwrites=read_only_public_overwrites())
            announcements_ch = await ensure_text_channel("announcements", cat_start, topic="Official announcements and major updates for Gaman 📢", news=True, overwrites=read_only_public_overwrites())
            guide_ch = await ensure_text_channel("server-guide", cat_start, topic="Complete server navigation directory and bot guide 🗺️", overwrites=read_only_public_overwrites())
            roles_ch = await ensure_text_channel("choose-roles", cat_start, topic="Self-service role selection and notification preferences 🎭", overwrites=read_only_public_overwrites(allow_reactions=True))
            intro_ow = public_chat_overwrites()
            intros_ch = await ensure_text_channel("introductions", cat_start, topic="Introduce yourself to the Gaman community! Tell us your hobbies and passions ✨", overwrites=intro_ow)
            faq_ch = await ensure_text_channel("faq", cat_start, topic="Frequently Asked Questions about Gaman and Kazumi ❓", overwrites=read_only_public_overwrites())

            # 2. 🌐 GAMAN COMMUNITY
            general_ch = await ensure_text_channel("general", cat_comm, topic="Main conversation hub for Gaman. Be kind, welcoming, and enjoy your stay 💬")
            daily_q_ch = await ensure_text_channel("daily-question", cat_comm, topic="Daily community questions and conversation starters 💡")
            gallery_ch = await ensure_text_channel("media-gallery", cat_comm, topic="Share your artwork, photos, captures, and media 📸")
            memes_ch = await ensure_text_channel("memes", cat_comm, topic="Share laughs, jokes, and top-tier memes 🐸")
            showcase_forum = await ensure_forum_channel("showcase", cat_comm, topic="Share your projects, creations, coding, hobbies, and interests!")
            qa_forum = await ensure_forum_channel("questions-and-help", cat_comm, topic="Community Q&A and help requests.")
            suggestions_forum = await ensure_forum_channel("suggestions", cat_comm, topic="Share your suggestions, ideas, and feature requests for Gaman.")
            polls_ch = await ensure_text_channel("polls", cat_comm, topic="Community votes and official decision polls 📊")

            # 3. 🌸 KAZUMI AI SPACE
            kazumi_chat_ch = await ensure_text_channel("kazumi-chat", cat_kazumi, topic="Direct AI companion sanctuary. Chat, explore ideas, and bond with Kazumi 🌸")
            kazumi_cmd_ch = await ensure_text_channel("kazumi-commands", cat_kazumi, topic="Slash command execution and utility headquarters ⚡")
            kazumi_games_ch = await ensure_text_channel("kazumi-games", cat_kazumi, topic="Play trivia, connect4, tictactoe, word games, and earn XP 🎲")
            kazumi_events_ch = await ensure_text_channel("kazumi-events", cat_kazumi, topic="Kazumi server events, reminders, and activities 🔔")
            kazumi_feedback_ch = await ensure_text_channel("kazumi-feedback", cat_kazumi, topic="Feedback, suggestions, and companion bug reports 📝")

            # 4. 🎮 GAMES & ACTIVITIES
            gaming_chat_ch = await ensure_text_channel("gaming-chat", cat_games, topic="Gaming discussion, strategies, clips, and game recommendations 🎮")
            game_rooms_ch = await ensure_text_channel("game-rooms", cat_games, topic="Find party members and organize co-op or multiplayer sessions 🕹️")
            leaderboards_ch = await ensure_text_channel("leaderboards", cat_games, topic="Server XP, arcade, and gaming rankings 🏆", overwrites=read_only_public_overwrites())
            giveaways_ch = await ensure_text_channel("giveaways", cat_games, topic="Official community giveaways and lucky draws 🎁", overwrites=read_only_public_overwrites(allow_reactions=True))
            events_ch = await ensure_text_channel("events", cat_games, topic="Upcoming community events, game nights, and activities 🗓️")
            challenges_ch = await ensure_text_channel("community-challenges", cat_games, topic="Weekly and monthly server challenges 🏅")

            # 5. 🎙️ VOICE & LIVE
            # Reorganize General voice
            if "general" in existing_voice:
                gen_voice = existing_voice["general"]
                await gen_voice.edit(name="General Voice", category=cat_voice)
            else:
                await ensure_voice_channel("General Voice", cat_voice)
            await ensure_voice_channel("Gaming Lounge", cat_voice)
            await ensure_voice_channel("Chill Lounge", cat_voice)
            await ensure_voice_channel("Music Lounge", cat_voice)
            await ensure_voice_channel("AFK", cat_voice)
            await ensure_stage_channel("Community Stage", cat_voice)

            # 6. 📅 EVENTS
            await ensure_text_channel("event-announcements", cat_events, topic="Official announcements for server tournaments and live events 📣", news=True, overwrites=read_only_public_overwrites())
            await ensure_text_channel("event-chat", cat_events, topic="Live chat during active events and stage sessions 🎉")
            event_planning_ow = staff_only_overwrites()
            if event_host_role:
                event_planning_ow[event_host_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            await ensure_text_channel("event-planning", cat_events, topic="Staff and Event Host coordination channel 📋", overwrites=event_planning_ow)

            # 7. 🛡️ MODERATION & SUPPORT
            await ensure_text_channel("get-help", cat_support, topic="Need support? Ask here or open a private assistance ticket 🤝")
            await ensure_text_channel("member-reports", cat_support, topic="Private member reports and moderation triage 🛡️", overwrites=staff_only_overwrites())
            await ensure_text_channel("appeals", cat_support, topic="Restricted appeals and penalty review ⚖️", overwrites=staff_only_overwrites())
            await ensure_text_channel("mod-logs", cat_support, topic="Automated moderation case log audit trail 🔍", overwrites=staff_only_overwrites())
            await ensure_text_channel("automod-logs", cat_support, topic="Discord AutoMod and spam block incident records 🚨", overwrites=staff_only_overwrites())

            # 8. 🔐 STAFF CONTROL ROOM
            await ensure_text_channel("staff-chat", cat_staff, topic="Staff headquarters and general discussions ☕", overwrites=staff_only_overwrites())
            
            # Try to integrate or create staff-announcements
            await ensure_text_channel("staff-announcements", cat_staff, topic="Staff announcements and Discord Community notices 📢", overwrites=staff_only_overwrites())
            await ensure_text_channel("staff-planning", cat_staff, topic="Long term roadmap, rules updates, and staff planning 🎯", overwrites=staff_only_overwrites())
            await ensure_text_channel("kazumi-logs", cat_staff, topic="Real-time Kazumi AI companion telemetry, errors, and audit events 🌸", overwrites=staff_only_overwrites())
            await ensure_text_channel("bot-testing", cat_staff, topic="Staging area for testing bot commands, integrations, and updates 🧪", overwrites=staff_only_overwrites())
            await ensure_text_channel("security-alerts", cat_staff, topic="Security alerts, raid prevention, and permission audits 🛡️", overwrites=staff_only_overwrites())

            logger.info("=== ARCHITECTURE SETUP COMPLETED SUCCESSFULLY ===")

        except Exception as e:
            logger.error(f"Error provisioning Gaman architecture: {e}", exc_info=True)
        finally:
            await client.close()

    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(setup_gaman())
