# -*- coding: utf-8 -*-
"""
Finalize Euphoria Server Configuration:
1. Ensure #member-reports is a genuine Forum channel in PRIVATE STAFF.
2. Publish official rules in #rules.
3. Publish verified server guide in #server-guide.
4. Publish roles guide in #roles.
5. Send a test welcome poem into #welcome to verify end-to-end welcome generation.
6. Synchronize all channel mappings and policies in FeatureDatabase.
"""

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
from discord_features.welcome import sanitize_display_name, WelcomePoemGenerator

sys.stdout.reconfigure(encoding='utf-8')

with open('.env', 'r', encoding='utf-8') as f:
    env_content = f.read()

token_match = re.search(r'DISCORD_BOT_TOKEN\s*=\s*(.+)', env_content)
token = token_match.group(1).strip() if token_match else None
GUILD_ID = 1546919406603337809

async def main():
    print("Initiating Discord connection...", flush=True)
    conn = aiohttp.TCPConnector(family=socket.AF_INET, ssl=True)
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    client = discord.Client(intents=intents, connector=conn)

    @client.event
    async def on_ready():
        print(f"Logged in as {client.user} ({client.user.id})", flush=True)
        guild = client.get_guild(GUILD_ID)
        if not guild:
            print(f"Error: Guild {GUILD_ID} not found!", flush=True)
            await client.close()
            return

        print(f"Connected to {guild.name}!", flush=True)

        # -------------------------------------------------------------
        # 1. Ensure #member-reports is Forum in PRIVATE STAFF
        # -------------------------------------------------------------
        cat_staff = discord.utils.get(guild.categories, name="PRIVATE STAFF")
        forum_reports = None
        for ch in guild.channels:
            if ch.name == "member-reports":
                if isinstance(ch, discord.ForumChannel):
                    forum_reports = ch
                    print(f"Found existing Forum #member-reports ({ch.id})", flush=True)
                elif isinstance(ch, discord.TextChannel):
                    print(f"Legacy text channel #member-reports ({ch.id}) present.", flush=True)
                    try:
                        await ch.delete(reason="Upgrading to ForumChannel")
                        print("Deleted legacy text channel.", flush=True)
                    except Exception as e:
                        print(f"Note: Could not delete text channel ({e})", flush=True)

        if not forum_reports and cat_staff:
            try:
                forum_reports = await guild.create_forum(
                    "member-reports",
                    category=cat_staff,
                    topic="Private member reports, issue tracking & incident logs 📝"
                )
                print(f"Created genuine Forum #member-reports ({forum_reports.id})", flush=True)
            except Exception as e:
                print(f"Could not create forum member-reports: {e}", flush=True)

        # -------------------------------------------------------------
        # 2. Publish Official Rules in #rules
        # -------------------------------------------------------------
        ch_rules = discord.utils.get(guild.channels, name="rules")
        if ch_rules and isinstance(ch_rules, discord.TextChannel):
            rules_embed = discord.Embed(
                title="🌸 EUPHORIA COMMUNITY GUIDELINES & RULES 🌸",
                description=(
                    "Welcome to **Euphoria**! We are a cozy, creative, and safe community.\n"
                    "To ensure everyone has a wonderful time, please respect the following guidelines:"
                ),
                color=discord.Color.from_rgb(255, 140, 180)
            )
            rules_embed.add_field(
                name="1. Be Kind & Respectful ✨",
                value="Treat every member with empathy. Hate speech, harassment, bigotry, toxicity, or targeted attacks will not be tolerated under any circumstances.",
                inline=False
            )
            rules_embed.add_field(
                name="2. Keep Content Appropriate 🌿",
                value="No NSFW, explicit, gore, or illegal content. Keep discussions, avatars, and media safe for all community members.",
                inline=False
            )
            rules_embed.add_field(
                name="3. Respect Channel Topics 📌",
                value=(
                    "Use channels for their designated purposes:\n"
                    "• Keep general chatter in <#1546919407580876974>\n"
                    "• Chat directly with Kazumi in <#1555189316140015756>\n"
                    "• Play mini-games in <#1557699124302712912>\n"
                    "• Post questions in <#1557699282239361076> and suggestions in <#1557699285255192637>"
                ),
                inline=False
            )
            rules_embed.add_field(
                name="4. No Spam or Self-Promotion 🚫",
                value="Avoid spamming text, images, emojis, or mass mentions. Unsolicited advertising or DM promotion is strictly prohibited.",
                inline=False
            )
            rules_embed.add_field(
                name="5. Privacy & Safety 🔒",
                value="Do not share personal or sensitive information (yours or others'). Follow Discord's Terms of Service and Community Guidelines.",
                inline=False
            )
            rules_embed.set_footer(text="Euphoria Moderation Team • Questions? Open a post in #questions!")
            await ch_rules.send(embed=rules_embed)
            print("Posted official community rules to #rules!", flush=True)

        # -------------------------------------------------------------
        # 3. Publish Server Guide in #server-guide
        # -------------------------------------------------------------
        ch_guide = discord.utils.get(guild.channels, name="server-guide")
        if ch_guide and isinstance(ch_guide, discord.TextChannel):
            guide_embed1 = discord.Embed(
                title="📖 WELCOME TO EUPHORIA — SERVER GUIDE",
                description=(
                    "Welcome to the official server guide! Here is everything you need to navigate "
                    "Euphoria and interact with **Kazumi**, our companion bot."
                ),
                color=discord.Color.from_rgb(175, 120, 240)
            )
            guide_embed1.add_field(
                name="🌸 Server Navigation",
                value=(
                    "**INFORMATION**\n"
                    "• <#1557699099246071900> — Personalized welcome poems for new arrivals\n"
                    "• <#1556629631832952903> — Server rules and expectations\n"
                    "• <#1557699277512249398> — Official server announcements\n"
                    "• <#1557699104291954759> — This interactive guide\n"
                    "• <#1557699112294547507> — Notification and interest role selection\n\n"
                    "**COMMUNITY**\n"
                    "• <#1546919407580876974> — General conversation (Kazumi observes and reacts!)\n"
                    "• <#1556610885185970227> — Introduce yourself to the community\n"
                    "• <#1556611228288417902> — Art, screenshots, and visual media\n"
                    "• <#1556611697152630885> — Memes and funny content\n"
                    "• <#1557699282239361076> — Forum for community help and questions\n"
                    "• <#1557699285255192637> — Forum for suggestions and feedback\n\n"
                    "**ENTERTAINMENT & KAZUMI**\n"
                    "• <#1555189316140015756> — Dedicated companion chat with Kazumi\n"
                    "• <#1556626012022775849> — Slash commands & utilities\n"
                    "• <#1557699124302712912> — Mini-games, trivia, and leaderboards\n"
                    "• <#1557699127897493554> — Server giveaways and contests\n"
                    "• <#1557699130850279475> — Community events and schedules"
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
            await ch_guide.send(embed=guide_embed2)
            print("Posted verified server guide to #server-guide!", flush=True)

        # -------------------------------------------------------------
        # 4. Publish Roles Info in #roles
        # -------------------------------------------------------------
        ch_roles = discord.utils.get(guild.channels, name="roles")
        if ch_roles and isinstance(ch_roles, discord.TextChannel):
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
            print("Posted roles information to #roles!", flush=True)

        # -------------------------------------------------------------
        # 5. Live Test Welcome Poem in #welcome
        # -------------------------------------------------------------
        ch_welcome = discord.utils.get(guild.channels, name="welcome")
        if ch_welcome and isinstance(ch_welcome, discord.TextChannel):
            test_name = "Alex"
            line1, line2 = await WelcomePoemGenerator.generate_poem(test_name, guild.name)
            welcome_text = (
                f"**{line1}\n{line2}**\n\n"
                f"Please review our rules in <#1556629631832952903>, grab your roles in <#1557699112294547507>, "
                f"and introduce yourself in <#1556610885185970227>! 🌸"
            )
            await ch_welcome.send(welcome_text)
            print(f"Verified live welcome poem delivered to #welcome:\n{welcome_text}", flush=True)

        # -------------------------------------------------------------
        # 6. Synchronize FeatureDatabase Guild Settings
        # -------------------------------------------------------------
        print("\nSynchronizing FeatureDatabase guild settings...", flush=True)
        db = get_feature_db()
        gid_str = str(guild.id)
        g_settings = db.get_guild_settings(gid_str)

        # Map channel IDs
        channel_mapping = {}
        for c in guild.channels:
            channel_mapping[c.name] = c.id

        g_settings["welcome_channel_id"] = str(ch_welcome.id) if ch_welcome else None
        g_settings["welcome_enabled"] = True
        mod_logs_ch = discord.utils.get(guild.channels, name="mod-logs")
        g_settings["logging_channel_id"] = str(mod_logs_ch.id) if mod_logs_ch else None
        g_settings["channel_mapping"] = channel_mapping

        # Strict channel policy map
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
        print("FeatureDatabase synchronized successfully!", flush=True)

        await client.close()

    await client.start(token)

if __name__ == "__main__":
    asyncio.run(main())
