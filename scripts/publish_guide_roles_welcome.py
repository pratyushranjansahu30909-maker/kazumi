# -*- coding: utf-8 -*-
import os
import sys

workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

import asyncio
import re
import socket
import aiohttp
import discord
from discord_features.database import get_feature_db
from discord_features.welcome import WelcomePoemGenerator

sys.stdout.reconfigure(encoding='utf-8')

with open('.env', 'r', encoding='utf-8') as f:
    env_content = f.read()

token_match = re.search(r'DISCORD_BOT_TOKEN\s*=\s*(.+)', env_content)
token = token_match.group(1).strip() if token_match else None
GUILD_ID = 1546919406603337809

async def main():
    print("Connecting to Discord...", flush=True)
    conn = aiohttp.TCPConnector(family=socket.AF_INET, ssl=True)
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    client = discord.Client(intents=intents, connector=conn)

    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}", flush=True)
        guild = client.get_guild(GUILD_ID)

        # 1. Clean #server-guide and post comprehensive guide
        ch_guide = discord.utils.get(guild.channels, name="server-guide")
        if ch_guide:
            guide_embed1 = discord.Embed(
                title="📖 WELCOME TO EUPHORIA — SERVER GUIDE",
                description=(
                    "Welcome to the official server guide! Here is everything you need to navigate "
                    "Euphoria and interact with **Kazumi**, our companion bot."
                ),
                color=discord.Color.from_rgb(175, 120, 240)
            )
            guide_embed1.add_field(
                name="🌸 Information Channels",
                value=(
                    "• <#1557699099246071900> — Personalized welcome poems for new arrivals\n"
                    "• <#1556629631832952903> — Community guidelines and safety expectations\n"
                    "• <#1557699277512249398> — Official server broadcasts and updates\n"
                    "• <#1557699104291954759> — Server navigation and command handbook\n"
                    "• <#1557699112294547507> — Notification and self-assignable roles"
                ),
                inline=False
            )
            guide_embed1.add_field(
                name="💬 Community Spaces",
                value=(
                    "• <#1546919407580876974> — General discussion (Kazumi observes & reacts!)\n"
                    "• <#1556610885185970227> — Say hello and introduce yourself\n"
                    "• <#1556611228288417902> — Art, media, screenshots, and visual creations\n"
                    "• <#1556611697152630885> — Memes, jokes, and community humor\n"
                    "• <#1557699282239361076> — Forum for community questions and support\n"
                    "• <#1557699285255192637> — Forum for suggestions and server ideas"
                ),
                inline=False
            )
            guide_embed1.add_field(
                name="🎮 Kazumi & Entertainment",
                value=(
                    "• <#1555189316140015756> — Dedicated 1-on-1 AI companion chat with Kazumi\n"
                    "• <#1556626012022775849> — Slash commands, tools, and diagnostics\n"
                    "• <#1557699124302712912> — Mini-games, arcade challenges, and leaderboards\n"
                    "• <#1557699127897493554> — Server giveaways and lucky draws\n"
                    "• <#1557699130850279475> — Scheduled events, stages, and reminders"
                ),
                inline=False
            )

            guide_embed2 = discord.Embed(
                title="✨ KAZUMI COMPANION COMMANDS",
                description="Interact with Kazumi using these verified slash commands:",
                color=discord.Color.from_rgb(120, 200, 255)
            )
            guide_embed2.add_field(
                name="💬 Conversation & Companion",
                value=(
                    "`/persona` — View Kazumi's current personality & mood\n"
                    "`/diary` — Read Kazumi's daily reflections\n"
                    "`/cozy_points` — View your cozy relationship points\n"
                    "`/hug`, `/pat`, `/feed`, `/coffee`, `/tea` — Interactive cozy gestures\n"
                    "`/horoscope`, `/fortune`, `/affirmation` — Daily positivity"
                ),
                inline=False
            )
            guide_embed2.add_field(
                name="🎮 Games & Arcade (<#1557699124302712912>)",
                value=(
                    "`/game` — Launch a mini-game (Tic-Tac-Toe, Trivia, Word Chain)\n"
                    "`/daily_game` — Play today's daily challenge\n"
                    "`/leaderboard` — View top players\n"
                    "`/profile` & `/achievements` — View your gaming stats"
                ),
                inline=False
            )
            guide_embed2.add_field(
                name="⚙️ Utilities & Tools",
                value=(
                    "`/status` — View Kazumi's latency, uptime, and system status\n"
                    "`/remind` — Set personal reminders\n"
                    "`/recognize_text` — Extract text from uploaded images\n"
                    "`/my_data` & `/reset_memory` — Manage your personal data & memory privacy"
                ),
                inline=False
            )
            guide_embed2.set_footer(text="Have fun exploring Euphoria! 🌸")

            await ch_guide.send(embed=guide_embed1)
            await asyncio.sleep(1)
            await ch_guide.send(embed=guide_embed2)
            print("SUCCESS: Published server guide to #server-guide", flush=True)

        # 2. Publish #roles
        ch_roles = discord.utils.get(guild.channels, name="roles")
        if ch_roles:
            roles_embed = discord.Embed(
                title="🎭 EUPHORIA ROLES & NOTIFICATIONS",
                description=(
                    "Personalize your Euphoria experience! Roles help you stay notified "
                    "about events, giveaways, and updates.\n\n"
                    "**Role Hierarchy:**\n"
                    "👑 **Owner**\n"
                    "🛡️ **Administrator**\n"
                    "⚔️ **Moderator**\n"
                    "🔰 **Trial Moderator**\n"
                    "🎪 **Event Host**\n"
                    "🌸 **Kazumi** *(Companion Bot)*\n"
                    "🌟 **Member**\n"
                    "🌱 **Newcomer**\n\n"
                    "*(Privileged roles like Staff, Admin, or Moderator can only be granted by the Server Owner)*"
                ),
                color=discord.Color.from_rgb(100, 220, 180)
            )
            roles_embed.set_footer(text="Welcome to the family! 🌿")
            await ch_roles.send(embed=roles_embed)
            print("SUCCESS: Published roles info to #roles", flush=True)

        # 3. Publish personalized welcome poem in #welcome
        ch_welcome = discord.utils.get(guild.channels, name="welcome")
        if ch_welcome:
            test_name = "Alex"
            line1, line2 = await WelcomePoemGenerator.generate_poem(test_name, guild.name)
            welcome_text = (
                f"**{line1}\n{line2}**\n\n"
                f"Please review our rules in <#1556629631832952903>, grab your roles in <#1557699112294547507>, "
                f"and introduce yourself in <#1556610885185970227>! 🌸"
            )
            await ch_welcome.send(welcome_text)
            print("SUCCESS: Published live welcome poem to #welcome", flush=True)

        # 4. Synchronize database guild settings
        print("Synchronizing FeatureDatabase...", flush=True)
        db = get_feature_db()
        gid_str = str(guild.id)
        g_settings = db.get_guild_settings(gid_str)

        channel_map = {}
        for c in guild.channels:
            channel_map[c.name] = c.id

        g_settings["welcome_channel_id"] = str(ch_welcome.id) if ch_welcome else None
        g_settings["welcome_enabled"] = True
        mod_logs_ch = discord.utils.get(guild.channels, name="mod-logs")
        g_settings["logging_channel_id"] = str(mod_logs_ch.id) if mod_logs_ch else None
        g_settings["channel_mapping"] = channel_map

        # Explicit channel policies
        policies = {}
        for c in guild.channels:
            c_str = str(c.id)
            if c.name == "welcome":
                policies[c_str] = "EVENTS_ONLY"
            elif c.name == "rules":
                policies[c_str] = "READ_ONLY"
            elif c.name == "announcements":
                policies[c_str] = "ANNOUNCEMENTS_ONLY"
            elif c.name == "server-guide":
                policies[c_str] = "GUIDE_ONLY"
            elif c.name == "roles":
                policies[c_str] = "ROLE_SELECTION_ONLY"
            elif "general" in c.name:
                policies[c_str] = "OBSERVATION_ONLY"
            elif "introduction" in c.name:
                policies[c_str] = "INTRODUCTIONS_ONLY"
            elif "media" in c.name:
                policies[c_str] = "MEDIA_OBSERVATION"
            elif "meme" in c.name:
                policies[c_str] = "HUMOR_OBSERVATION"
            elif c.name == "questions":
                policies[c_str] = "FORUM_QA"
            elif c.name == "suggestions":
                policies[c_str] = "FORUM_SUGGESTIONS"
            elif c.name == "kazumi-chat":
                policies[c_str] = "ACTIVE_CHAT"
            elif c.name == "bot-commands":
                policies[c_str] = "COMMANDS_ONLY"
            elif c.name == "games":
                policies[c_str] = "GAMEPLAY_ONLY"
            elif c.name == "giveaways":
                policies[c_str] = "GIVEAWAYS_ONLY"
            elif c.name == "events":
                policies[c_str] = "EVENTS_ONLY"
            elif c.name == "music-commands":
                policies[c_str] = "MUSIC_CONTROL_ONLY"
            elif c.name == "Community Stage":
                policies[c_str] = "STAGE_EVENT_ONLY"
            elif c.category and "PRIVATE STAFF" in c.category.name:
                policies[c_str] = "STAFF_ONLY"

        g_settings["channel_policies"] = policies
        db.set_guild_settings(gid_str, g_settings)
        print("SUCCESS: FeatureDatabase synchronized!", flush=True)

        await client.close()

    await client.start(token)

if __name__ == "__main__":
    asyncio.run(main())
