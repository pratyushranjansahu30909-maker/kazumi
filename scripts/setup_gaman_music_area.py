# -*- coding: utf-8 -*-
"""
Setup Dedicated Music Area for Gaman Server (ID: 1554152397327044729)
- Category: MUSIC & LISTENING
- Text channel: #music-commands
- Voice channel: Music Lounge (reuses existing Music Lounge if present, moves into category)
- Configures precise permissions (No Administrator for Kazumi)
- Updates isa_memory/guild_settings.json
"""

import os
import sys
import json
import logging
import discord
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TARGET_GUILD_ID = 1554152397327044729

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GamanMusicSetup")

async def run_setup():
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        logger.info(f"Connected as {client.user} (ID: {client.user.id})")
        guild = client.get_guild(TARGET_GUILD_ID)
        if not guild:
            logger.error(f"Target guild {TARGET_GUILD_ID} not found!")
            await client.close()
            return

        logger.info(f"Target Guild: {guild.name} ({guild.id})")

        # Roles lookup
        admin_role = discord.utils.get(guild.roles, name="Administrator")
        mod_role = discord.utils.get(guild.roles, name="Moderator")
        bot_member = guild.me

        # 1. Check or Create Category 'MUSIC & LISTENING'
        music_cat = discord.utils.get(guild.categories, name="MUSIC & LISTENING")
        if not music_cat:
            # Also check case-insensitive or emoji variations
            for c in guild.categories:
                if "MUSIC" in c.name.upper():
                    music_cat = c
                    break

        if not music_cat:
            logger.info("Creating category 'MUSIC & LISTENING'...")
            cat_overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    send_messages=True,
                    read_message_history=True
                )
            }
            if admin_role:
                cat_overwrites[admin_role] = discord.PermissionOverwrite(manage_channels=True)
            if mod_role:
                cat_overwrites[mod_role] = discord.PermissionOverwrite(manage_channels=True)
            if bot_member:
                cat_overwrites[bot_member] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True,
                    connect=True,
                    speak=True,
                    use_voice_activation=True
                )
            music_cat = await guild.create_category("MUSIC & LISTENING", overwrites=cat_overwrites)
            logger.info(f"Created category 'MUSIC & LISTENING' (ID: {music_cat.id})")
        else:
            logger.info(f"Found existing category '{music_cat.name}' (ID: {music_cat.id})")

        # 2. Check or Create Text Channel '#music-commands'
        music_text = discord.utils.get(guild.text_channels, name="music-commands")
        if not music_text:
            logger.info("Creating text channel '#music-commands'...")
            text_overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    use_application_commands=True,
                    embed_links=True,
                    attach_files=True,
                    manage_channels=False,
                    manage_messages=False
                )
            }
            if admin_role:
                text_overwrites[admin_role] = discord.PermissionOverwrite(manage_channels=True, manage_messages=True)
            if mod_role:
                text_overwrites[mod_role] = discord.PermissionOverwrite(manage_channels=True, manage_messages=True)
            if bot_member:
                text_overwrites[bot_member] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    embed_links=True,
                    attach_files=True,
                    read_message_history=True,
                    manage_messages=True
                )
            music_text = await guild.create_text_channel(
                "music-commands",
                category=music_cat,
                topic="🎵 Music commands, queue controls, and music playback requests with Kazumi.",
                overwrites=text_overwrites
            )
            logger.info(f"Created text channel '#music-commands' (ID: {music_text.id})")
        else:
            logger.info(f"Found existing text channel '#{music_text.name}' (ID: {music_text.id})")
            if music_text.category != music_cat:
                await music_text.edit(category=music_cat)
                logger.info(f"Moved #{music_text.name} to category '{music_cat.name}'")

        # 3. Check or Create Voice Channel 'Music Lounge'
        music_voice = discord.utils.get(guild.voice_channels, name="Music Lounge")
        if not music_voice:
            logger.info("Creating voice channel 'Music Lounge'...")
            voice_overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    manage_channels=False
                )
            }
            if admin_role:
                voice_overwrites[admin_role] = discord.PermissionOverwrite(manage_channels=True, mute_members=True, deafen_members=True, move_members=True)
            if mod_role:
                voice_overwrites[mod_role] = discord.PermissionOverwrite(manage_channels=True, mute_members=True, deafen_members=True, move_members=True)
            if bot_member:
                voice_overwrites[bot_member] = discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    use_voice_activation=True,
                    priority_speaker=True
                )
            music_voice = await guild.create_voice_channel(
                "Music Lounge",
                category=music_cat,
                overwrites=voice_overwrites
            )
            logger.info(f"Created voice channel 'Music Lounge' (ID: {music_voice.id})")
        else:
            logger.info(f"Found existing voice channel '{music_voice.name}' (ID: {music_voice.id})")
            if music_voice.category != music_cat:
                await music_voice.edit(category=music_cat)
                logger.info(f"Moved voice channel '{music_voice.name}' into category '{music_cat.name}'")

        # 4. Update isa_memory/guild_settings.json
        settings_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "isa_memory", "guild_settings.json")
        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            
            gaman_data = settings.setdefault(str(TARGET_GUILD_ID), {})
            channel_mapping = gaman_data.setdefault("channel_mapping", {})
            channel_policies = gaman_data.setdefault("channel_policies", {})

            channel_mapping["music-commands"] = music_text.id
            channel_mapping["music-voice"] = music_voice.id
            channel_policies[str(music_text.id)] = "MUSIC_CONTROL_ONLY"
            channel_policies[str(music_voice.id)] = "VOICE_FEATURES_ONLY"

            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
            logger.info("Updated isa_memory/guild_settings.json with music channels and policies.")

        # Post initial music guide message in #music-commands
        messages = [m async for m in music_text.history(limit=5)]
        if not messages:
            embed = discord.Embed(
                title="🌸 Kazumi Jockie Music Lounge",
                description=(
                    "Welcome to the official music lounge for **Gaman**!\n"
                    "Join the **Music Lounge** voice channel and use the slash commands below to queue and enjoy high-fidelity music with Kazumi."
                ),
                color=0xFFB6C1
            )
            embed.add_field(
                name="🎵 Core Playback Commands",
                value=(
                    "`/play <query>` — Play audio or search YouTube/Soundcloud\n"
                    "`/pause` — Pause current audio\n"
                    "`/resume` — Resume paused audio\n"
                    "`/skip` — Skip to the next track\n"
                    "`/stop` — Stop playback, clear queue, and leave voice\n"
                    "`/nowplaying` — Display current track progress\n"
                    "`/queue` — View the upcoming track queue"
                ),
                inline=False
            )
            embed.add_field(
                name="🎛️ Queue & Sound Controls",
                value=(
                    "`/volume <1-100>` — Adjust playback volume\n"
                    "`/loop` — Toggle repeat mode for current song\n"
                    "`/shuffle` — Randomize upcoming queue order\n"
                    "`/remove <#>` — Remove a specific song from queue\n"
                    "`/clearqueue` — Clear all queued songs\n"
                    "`/join` — Connect Kazumi to your voice channel\n"
                    "`/leave` — Disconnect Kazumi from voice\n"
                    "`/musicstatus` — View audio system diagnostics"
                ),
                inline=False
            )
            embed.set_footer(text="Gaman Community Music System • Built with FFmpeg & Opus 🌸")
            await music_text.send(embed=embed)
            logger.info("Posted initial music guide embed in #music-commands.")

        print(json.dumps({
            "status": "SUCCESS",
            "category_id": music_cat.id,
            "category_name": music_cat.name,
            "text_channel_id": music_text.id,
            "text_channel_name": music_text.name,
            "voice_channel_id": music_voice.id,
            "voice_channel_name": music_voice.name
        }, indent=2))

        await client.close()

    await client.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_setup())
