# -*- coding: utf-8 -*-
"""
Publish Onboarding, Rules, Server Guide, Role Selection, and FAQ for Gaman.
Guild ID: 1554152397327044729
"""

import os
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import asyncio
import logging
from typing import List

import discord
from dotenv import load_dotenv

from discord_features.database import get_feature_db
from discord_features.reaction_roles import DynamicRolePanelView
from discord_features.tickets import TicketLaunchView

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TARGET_GUILD_ID = 1554152397327044729

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("GamanOnboarding")

async def publish_onboarding():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            guild = client.get_guild(TARGET_GUILD_ID)
            if not guild:
                logger.error(f"Target guild {TARGET_GUILD_ID} not found!")
                await client.close()
                return

            assert guild.id == TARGET_GUILD_ID
            logger.info(f"Connected to {guild.name} ({guild.id})")

            # 1. Create Self-Assignable Notification / Interest Roles (0 privileges)
            existing_roles = {r.name: r for r in guild.roles}
            desired_roles = [
                ("Announcements Ping", discord.Color.blue()),
                ("Events Ping", discord.Color.purple()),
                ("Giveaways Ping", discord.Color.gold()),
                ("Gamer", discord.Color.orange()),
            ]
            selectable_roles: List[discord.Role] = []
            for rname, rcolor in desired_roles:
                if rname in existing_roles:
                    selectable_roles.append(existing_roles[rname])
                else:
                    try:
                        role = await guild.create_role(
                            name=rname,
                            color=rcolor,
                            permissions=discord.Permissions.none(),
                            mentionable=True,
                            reason="Gaman self-assignable notification role"
                        )
                        selectable_roles.append(role)
                        logger.info(f"Created role: {role.name}")
                    except Exception as e:
                        logger.warning(f"Could not create role {rname}: {e}")

            # 2. Publish #rules (1560031026477142057)
            rules_ch = guild.get_channel(1560031026477142057)
            if rules_ch and isinstance(rules_ch, discord.TextChannel):
                # Clean prior bot messages if any
                embed1 = discord.Embed(
                    title="📜 GAMAN COMMUNITY RULES & CODE OF CONDUCT",
                    description=(
                        "Welcome to **Gaman**! To ensure a friendly, safe, respectful, and engaging environment "
                        "for all members, please review and abide by our core server guidelines."
                    ),
                    color=discord.Color.from_rgb(244, 114, 182)
                )
                embed1.add_field(
                    name="1. Treat Everyone With Respect",
                    value="Harassment, hate speech, bullying, toxicity, doxxing, or personal attacks of any kind are strictly prohibited.",
                    inline=False
                )
                embed1.add_field(
                    name="2. Keep Channels On-Topic",
                    value="Use designated channels for their intended purposes. AI companion conversations belong in <#1560034107306680460>, slash commands in <#1560034109701496896>, and games in <#1560034112088047658>.",
                    inline=False
                )
                embed1.add_field(
                    name="3. No Spamming or Excessive Mentions",
                    value="Avoid spamming text, repeated emoji walls, disruptive caps, mass mentions (@everyone/@here), or raiding. Automated protections will filter violations.",
                    inline=False
                )
                embed1.add_field(
                    name="4. No Unauthorized Promotion",
                    value="Unsolicited DM advertising, server invite links, commercial solicitations, or self-promotion outside of dedicated showcase channels are disallowed.",
                    inline=False
                )
                embed1.add_field(
                    name="5. Safe For Work & Age Appropriateness",
                    value="All public channels are SFW. No NSFW, explicit, gore, or illegal content. Keep avatars, nicknames, and profile banners appropriate.",
                    inline=False
                )
                embed1.add_field(
                    name="6. Follow Discord Terms of Service",
                    value="All members must adhere to Discord's [Community Guidelines](https://discord.com/guidelines) and [Terms of Service](https://discord.com/terms).",
                    inline=False
                )
                embed1.set_footer(text="Gaman Moderation Team • Harmony & Excellence")
                await rules_ch.send(embed=embed1)
                logger.info("Published #rules")

            # 3. Publish #server-guide (1560033834450423818)
            guide_ch = guild.get_channel(1560033834450423818)
            if guide_ch and isinstance(guide_ch, discord.TextChannel):
                embed_dir = discord.Embed(
                    title="🗺️ GAMAN SERVER DIRECTORY & NAVIGATION",
                    description="Explore Gaman's curated spaces and connect with our community!",
                    color=discord.Color.from_rgb(129, 140, 248)
                )
                embed_dir.add_field(
                    name="✨ START HERE",
                    value=(
                        "• <#1560033823960334396> — Personalized welcome poems for every new friend\n"
                        "• <#1560031026477142057> — Server rules and expectations\n"
                        "• <#1560033832378433557> — Official announcements and major updates\n"
                        "• <#1560033834450423818> — Complete server directory and handbook\n"
                        "• <#1560033836564484239> — Interactive button role selection\n"
                        "• <#1560033839563145337> — Member introductions\n"
                        "• <#1560033841920479254> — Frequently asked questions"
                    ),
                    inline=False
                )
                embed_dir.add_field(
                    name="🌐 GAMAN COMMUNITY",
                    value=(
                        "• <#1554152397830357004> — Main public chat (Kazumi observes & reacts!)\n"
                        "• <#1560034086603591732> — Daily questions & conversation prompts\n"
                        "• <#1560034089262649445> — Media, photography, and screenshot sharing\n"
                        "• <#1560034091825500244> — Memes and humor\n"
                        "• <#1560034094396608602> — Community project & creation showcase (Forum)\n"
                        "• <#1560034096338706537> — Questions & community help (Forum)\n"
                        "• <#1560034099429769311> — Suggestions & server feedback (Forum)\n"
                        "• <#1560034102080438352> — Server decision polls"
                    ),
                    inline=False
                )
                embed_dir.add_field(
                    name="🌸 KAZUMI AI SPACE",
                    value=(
                        "• <#1560034107306680460> — Dedicated companion chat with Kazumi\n"
                        "• <#1560034109701496896> — Slash command utilities and tools\n"
                        "• <#1560034112088047658> — Interactive games, trivia, and XP\n"
                        "• <#1560034114294517761> — Kazumi activities and reminders\n"
                        "• <#1560034117268144149> — Bot feedback & bug reports"
                    ),
                    inline=False
                )
                embed_dir.add_field(
                    name="🎮 GAMES & ACTIVITIES",
                    value=(
                        "• <#1560034120275595294> — Gaming discussion & game chat\n"
                        "• <#1560034123366801560> — Co-op and party matchmaking\n"
                        "• <#1560034125627523174> — XP and game leaderboards\n"
                        "• <#1560034128227733615> — Official community giveaways\n"
                        "• <#1560034130828202014> — Server events and tournaments"
                    ),
                    inline=False
                )
                embed_dir.add_field(
                    name="🎙️ VOICE & LIVE",
                    value=(
                        "• **General Voice** — Main voice lounge\n"
                        "• **Gaming Lounge** — Team voice chat for gaming\n"
                        "• **Chill Lounge** — Relaxed ambient voice room\n"
                        "• **Music Lounge** — Listen with Jockie Music\n"
                        "• **Community Stage** — Live audio sessions, podcasts, and events"
                    ),
                    inline=False
                )
                await guide_ch.send(embed=embed_dir)

                embed_bot = discord.Embed(
                    title="🤖 KAZUMI AI COMPANION HANDBOOK",
                    description="Kazumi is an intelligent AI companion tailored specifically for Gaman.",
                    color=discord.Color.from_rgb(236, 72, 153)
                )
                embed_bot.add_field(
                    name="💬 Natural Companion Chat",
                    value="Talk with Kazumi anytime in <#1560034107306680460>! She remembers conversations, learns your interests, and expresses genuine emotions.",
                    inline=False
                )
                embed_bot.add_field(
                    name="🎮 Verified Commands",
                    value=(
                        "`/ping` — Check bot response latency\n"
                        "`/uptime` — View bot uptime\n"
                        "`/botinfo` — Bot system specs and stats\n"
                        "`/serverinfo` — Server overview and metrics\n"
                        "`/userinfo` — Member profile and roles\n"
                        "`/avatar` — View user profile photo\n"
                        "`/poll` — Create an interactive community poll\n"
                        "`/game` — Play interactive mini-games\n"
                        "`/leaderboard` — View server game rankings\n"
                        "`/roast` — Friendly, comedic banter and roasts"
                    ),
                    inline=False
                )
                embed_bot.set_footer(text="Kazumi Companion 🌸 • Always here for Gaman")
                await guide_ch.send(embed=embed_bot)
                logger.info("Published #server-guide")

            # 4. Publish #choose-roles (1560033836564484239)
            roles_ch = guild.get_channel(1560033836564484239)
            if roles_ch and isinstance(roles_ch, discord.TextChannel):
                embed_roles = discord.Embed(
                    title="🎭 SELF-SERVICE ROLE SELECTION",
                    description=(
                        "Customize your experience in Gaman! Click the buttons below to toggle "
                        "notification pings and interest roles. You can click again anytime to remove them."
                    ),
                    color=discord.Color.from_rgb(52, 211, 153)
                )
                embed_roles.add_field(
                    name="📢 Notification Pings",
                    value=(
                        "• **Announcements Ping** — Stay updated on major server news\n"
                        "• **Events Ping** — Get notified when stage events & game nights happen\n"
                        "• **Giveaways Ping** — Never miss a server lucky draw or giveaway"
                    ),
                    inline=False
                )
                embed_roles.add_field(
                    name="🕹️ Interests",
                    value="• **Gamer** — Connect with other players for gaming sessions",
                    inline=False
                )
                embed_roles.set_footer(text="Role buttons update immediately • 100% self-service")
                if selectable_roles:
                    view = DynamicRolePanelView(selectable_roles)
                    await roles_ch.send(embed=embed_roles, view=view)
                else:
                    await roles_ch.send(embed=embed_roles)
                logger.info("Published #choose-roles")

            # 5. Publish #faq (1560033841920479254)
            faq_ch = guild.get_channel(1560033841920479254)
            if faq_ch and isinstance(faq_ch, discord.TextChannel):
                embed_faq = discord.Embed(
                    title="❓ FREQUENTLY ASKED QUESTIONS",
                    description="Common questions about Gaman and our features.",
                    color=discord.Color.from_rgb(251, 191, 36)
                )
                embed_faq.add_field(
                    name="What is Gaman?",
                    value="Gaman is a vibrant, welcoming community space for conversations, games, creative sharing, and connecting with friends.",
                    inline=False
                )
                embed_faq.add_field(
                    name="Who is Kazumi?",
                    value="Kazumi is our AI companion bot! She welcomes new arrivals with personalized two-line poems, observes community chat, hosts interactive games, and chats 1-on-1 in <#1560034107306680460>.",
                    inline=False
                )
                embed_faq.add_field(
                    name="Where can I play games and earn XP?",
                    value="Head over to <#1560034112088047658> to play trivia, tictactoe, connect4, hangman, and climb the <#1560034125627523174>!",
                    inline=False
                )
                embed_faq.add_field(
                    name="How do I get help or report an issue?",
                    value="Visit <#1560034254350721195> or message a staff member. For urgent safety concerns, staff will handle reports confidentially.",
                    inline=False
                )
                embed_faq.set_footer(text="Have another question? Ask in #questions-and-help!")
                await faq_ch.send(embed=embed_faq)
                logger.info("Published #faq")

            # 6. Publish #get-help (1560034254350721195)
            help_ch = guild.get_channel(1560034254350721195)
            if help_ch and isinstance(help_ch, discord.TextChannel):
                embed_help = discord.Embed(
                    title="🤝 COMMUNITY SUPPORT & HELP DESK",
                    description=(
                        "Need assistance, have a server question, or need staff intervention? "
                        "We are here to assist you!"
                    ),
                    color=discord.Color.from_rgb(56, 189, 248)
                )
                embed_help.add_field(
                    name="💡 General Help & Questions",
                    value="For non-confidential questions, post in our Q&A forum at <#1560034096338706537>.",
                    inline=False
                )
                embed_help.add_field(
                    name="📩 Support Tickets",
                    value="Click the button below to open a private ticket with our moderation team.",
                    inline=False
                )
                embed_help.set_footer(text="Gaman Support Team • Respectful & Prompt Assistance")
                ticket_view = TicketLaunchView()
                await help_ch.send(embed=embed_help, view=ticket_view)
                logger.info("Published #get-help with TicketLaunchView")

            logger.info("=== ONBOARDING PUBLICATION COMPLETE ===")

        except Exception as e:
            logger.error(f"Error publishing onboarding: {e}", exc_info=True)
        finally:
            await client.close()

    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(publish_onboarding())
