#!/usr/bin/env python3
"""
🌸 Kazumi Discord Bot — AI Companion Integration
Connects Kazumi's cognitive chat engine directly into Discord as a server companion bot.
"""

import os
import sys
import re
import asyncio
import threading
import logging
import time
from typing import List, Optional

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import socket
# Robust IPv4 resolution filter for cloud/Docker environments without IPv6 routing
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        # Enforce AF_INET to prevent IPv6 DNS lookups that fail or hang in IPv4-only networks
        return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
    except Exception:
        try:
            return _orig_getaddrinfo(host, port, family, type, proto, flags)
        except Exception:
            return []
socket.getaddrinfo = _ipv4_getaddrinfo

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("KazumiDiscordBot")
# Silence voice-related warnings since Kazumi is pure chat bot
logging.getLogger("discord.client").setLevel(logging.ERROR)

# Root directory setup
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# Import Kazumi Core
try:
    from kazumi import Kazumi, FolderLock
    logger.info("Initializing Kazumi core engine for Discord...")
    kazumi_core = Kazumi()
    # Ensure pure chat bot mode
    kazumi_core.voice_enabled = False
    logger.info("Kazumi core engine loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load Kazumi core engine: {e}")
    kazumi_core = None

kazumi_lock = threading.Lock()

import argparse

# Parse CLI arguments if provided
parser = argparse.ArgumentParser(description="Kazumi Discord Companion Bot")
parser.add_argument("--token", type=str, default=None, help="Discord Bot Token")
parser.add_argument("--channel", type=str, default=None, help="Dedicated Channel ID")
parser.add_argument("--prefix", type=str, default=None, help="Command prefix (default: !k )")
args, _ = parser.parse_known_args()

# Discord Configuration
DISCORD_BOT_TOKEN = (args.token or os.environ.get("DISCORD_BOT_TOKEN", "")).strip()
DISCORD_CHANNEL_ID = (args.channel or os.environ.get("DISCORD_CHANNEL_ID", "")).strip()
PREFIX = args.prefix or os.environ.get("DISCORD_PREFIX", "!k ")

# Bot Intents
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content for chat

class KazumiBot(commands.Bot):
    async def setup_hook(self):
        try:
            # Force IPv4 TCPConnector inside the running event loop
            self.http.connector = aiohttp.TCPConnector(family=socket.AF_INET)
            logger.info("🌸 Configured IPv4 TCPConnector for Discord client.")
        except Exception as e:
            logger.warning(f"Could not configure custom IPv4 TCPConnector: {e}")

bot = KazumiBot(command_prefix=commands.when_mentioned_or(PREFIX), intents=intents, help_command=None)

# Active conversational sessions: (channel_id, user_id) -> last_active_timestamp
active_conversations = {}
CONVERSATION_TIMEOUT_SECONDS = 120  # Continuous conversation without requiring repetitive @Kazumi tags


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def split_message(text: str, max_chars: int = 1950) -> List[str]:
    """Splits text cleanly by paragraphs or sentences to obey Discord's 2000-char limit."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= max_chars:
            current_chunk += (para + "\n\n") if current_chunk else (para + "\n\n")
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
                current_chunk = ""
            if len(para) <= max_chars:
                current_chunk = para + "\n\n"
            else:
                # Sub-split long paragraph by sentences or words
                words = para.split(" ")
                sub_chunk = ""
                for word in words:
                    if len(sub_chunk) + len(word) + 1 <= max_chars:
                        sub_chunk += (word + " ") if sub_chunk else (word + " ")
                    else:
                        if sub_chunk.strip():
                            chunks.append(sub_chunk.strip())
                        sub_chunk = word + " "
                if sub_chunk.strip():
                    current_chunk = sub_chunk + "\n\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text[:max_chars]]


def get_user_session_id(user: discord.User | discord.Member) -> str:
    """Returns a unique session ID per Discord user for persistent individual memory & affection."""
    return f"discord_user_{user.id}"


def sync_kazumi_reply(text: str, session_id: str) -> str:
    """Thread-safe call to Kazumi's sync reply function."""
    if not kazumi_core:
        return "I'm having a little trouble connecting to my thoughts right now. Please try again in a moment! 🌸"
    with kazumi_lock:
        return kazumi_core.reply(text, session_id=session_id)


async def ask_kazumi(text: str, session_id: str) -> str:
    """Non-blocking asynchronous wrapper over Kazumi's core reply."""
    return await asyncio.to_thread(sync_kazumi_reply, text, session_id)


def create_kazumi_embed(title: str, description: str, color: int = 0xc084fc) -> discord.Embed:
    """Creates a stylized embed card matching Kazumi's cozy lavender aesthetic."""
    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="Kazumi AI Companion • Cozy & Caring 🌸", icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None)
    return embed


# ---------------------------------------------------------------------------
# Discord Bot Events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    logger.info(f"✨ Logged in as {bot.user.name}#{bot.user.discriminator} (ID: {bot.user.id})")
    logger.info(f"Connected to {len(bot.guilds)} server(s).")
    
    # Set status presence
    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name="@Kazumi or /chat 🌸"
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)

    # Sync Slash Application Commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        logger.warning(f"Slash command sync failed: {e}")

    print("\n" + "=" * 60)
    print("🌸 KAZUMI DISCORD BOT IS READY AND LISTENING!")
    print(f"Bot Tag: {bot.user}")
    print("Mention Kazumi in any server channel or use /chat to speak!")
    print("=" * 60 + "\n")


@bot.event
async def on_message(message: discord.Message):
    # Ignore self and other bots
    if message.author.bot or (bot.user and message.author.id == bot.user.id):
        return

    raw_content = (message.content or "").strip()
    logger.info(f"📩 New message from {message.author} in #{getattr(message.channel, 'name', 'DM')}: '{raw_content}'")

    # Check if message is in DM
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_user_mentioned = bot.user in message.mentions if bot.user else False

    # Check if any role belonging to Kazumi was mentioned (e.g. @Kazumi role)
    is_role_mentioned = False
    if message.guild and message.guild.me:
        bot_roles = {r.id for r in message.guild.me.roles if r.name != "@everyone"}
        if hasattr(message, 'role_mentions'):
            is_role_mentioned = any(
                role.id in bot_roles or "kazumi" in role.name.lower()
                for role in message.role_mentions
            )
        if not is_role_mentioned:
            raw_ids = {int(x) for x in re.findall(r'<@&(\d+)>', raw_content)}
            is_role_mentioned = bool(raw_ids & bot_roles)

    is_mentioned = is_user_mentioned or is_role_mentioned

    channel_name = getattr(message.channel, 'name', '').lower()
    is_dedicated_channel = (
        (DISCORD_CHANNEL_ID and str(message.channel.id) == str(DISCORD_CHANNEL_ID))
        or ("kazumi" in channel_name)
    )

    is_reply_to_kazumi = False
    if message.reference and message.reference.resolved:
        resolved = message.reference.resolved
        if hasattr(resolved, 'author') and bot.user and resolved.author.id == bot.user.id:
            is_reply_to_kazumi = True

    name_called = bool(re.search(r'\bkazumi\b', raw_content, re.IGNORECASE))

    # Prefix detection (e.g. !k <msg>, !kazumi <msg>, or configured prefix)
    is_prefix_called = False
    prefix_clean = PREFIX.strip().lower()
    if raw_content:
        content_lower = raw_content.lower()
        if content_lower.startswith("!k") or content_lower.startswith("!kazumi") or (prefix_clean and content_lower.startswith(prefix_clean)):
            is_prefix_called = True

    # Check if user has an active ongoing conversation in this channel
    session_key = (message.channel.id, message.author.id)
    now = time.time()
    is_active_convo = False
    if session_key in active_conversations:
        if now - active_conversations[session_key] <= CONVERSATION_TIMEOUT_SECONDS:
            is_active_convo = True
        else:
            active_conversations.pop(session_key, None)

    # If user explicitly mentions someone else (and not Kazumi), they are addressing another person
    is_talking_to_other = bool(message.mentions) and not is_user_mentioned

    # Ignore command calls intended for other bots (starting with ! or ? or $ or . or - or /) unless prefix matches Kazumi
    is_other_bot_cmd = False
    if raw_content and raw_content[0] in "!?.$-/" and not is_prefix_called:
        is_other_bot_cmd = True

    should_respond = (
        (is_dm or is_mentioned or name_called or is_dedicated_channel or is_reply_to_kazumi or is_active_convo or is_prefix_called)
        and not is_talking_to_other
        and not is_other_bot_cmd
    )

    # Only respond if criteria met
    if not should_respond:
        await bot.process_commands(message)
        return

    try:
        # Clean the message text (remove user mentions, role mentions, prefixes, and name prefix)
        clean_text = raw_content
        if bot.user:
            clean_text = re.sub(rf"<@!?{bot.user.id}>", "", clean_text)
        clean_text = re.sub(r"<@&?\d+>", "", clean_text)  # Remove all user & role mention tags
        clean_text = re.sub(r"^\s*!(?:k|kazumi)\b[:,]?", "", clean_text, flags=re.IGNORECASE)
        if prefix_clean:
            clean_text = re.sub(r"^\s*" + re.escape(prefix_clean) + r"\b[:,]?", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"^\s*@?kazumi\b[:,]?", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"^[,\s:-]+", "", clean_text).strip()

        if not clean_text:
            # User just pinged without text
            await message.reply("Hello there! 🌸 How are you doing today? You can talk to me anytime, or use `/help` to see what we can do together!")
            active_conversations[session_key] = time.time()
            return

        session_id = get_user_session_id(message.author)
        logger.info(f"🧠 Processing message from {message.author}: '{clean_text}' (session: {session_id})")

        # Display typing indicator while Kazumi processes the thought with a safety timeout
        async with message.channel.typing():
            try:
                reply_text = await asyncio.wait_for(ask_kazumi(clean_text, session_id), timeout=30.0)
            except asyncio.TimeoutError:
                reply_text = "I'm right here with you! 🌸 I took a little moment connecting to my thoughts, but I'm listening closely. Please say that again!"
            except Exception as core_err:
                logger.error(f"Error querying Kazumi core: {core_err}", exc_info=True)
                reply_text = "I'm right here with you! 🌸 (I had a quick moment gathering my thoughts, but I'm ready to chat now!)"

        logger.info(f"💬 Replying to {message.author}: '{reply_text[:60]}...'")

        # Update active conversation timestamp
        active_conversations[session_key] = time.time()

        # If user explicitly said goodbye or exit, close the active continuous window
        farewell_words = {"bye", "goodbye", "cya", "see ya", "gn", "goodnight", "good night", "gotta go", "stop", "exit"}
        norm_clean = re.sub(r"[^\w\s]", "", clean_text).lower().strip()
        if norm_clean in farewell_words or any(norm_clean.startswith(fw + " ") for fw in farewell_words):
            active_conversations.pop(session_key, None)

        # Split message into chunks if it exceeds 2,000 characters
        chunks = split_message(reply_text)
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                await message.reply(chunk, mention_author=False)
            else:
                await message.channel.send(chunk)

    except Exception as e:
        logger.error(f"❌ Error in on_message: {e}", exc_info=True)
        try:
            await message.reply("I'm right here with you! 🌸 Something went a little fuzzy for a moment, but I'm listening now!")
        except Exception:
            pass


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    if isinstance(error, commands.CommandNotFound):
        return  # Silently ignore unknown prefix commands
    logger.error(f"Command error in {ctx.command}: {error}")


# ---------------------------------------------------------------------------
# Slash Commands
# ---------------------------------------------------------------------------

@bot.tree.command(name="chat", description="Have a cozy conversation with Kazumi 🌸")
@app_commands.describe(message="What would you like to say to Kazumi?")
async def slash_chat(interaction: discord.Interaction, message: str):
    await interaction.response.defer(thinking=True)
    session_id = get_user_session_id(interaction.user)
    reply_text = await ask_kazumi(message, session_id)
    chunks = split_message(reply_text)
    
    await interaction.followup.send(chunks[0])
    for chunk in chunks[1:]:
        await interaction.channel.send(chunk)


@bot.tree.command(name="status", description="Check Kazumi's affection level, mood, and cozy points 💕")
async def slash_status(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    if not kazumi_core:
        await interaction.followup.send("Kazumi core is currently offline.")
        return

    session_id = get_user_session_id(interaction.user)
    with kazumi_lock:
        kazumi_core.load_game_states(session_id)
        profile = kazumi_core.memory.profile
        affection = profile.get("affection_level", 10)
        cozy_points = profile.get("cozy_points", 100)
        persona = kazumi_core.current_archetype
        turn_count = getattr(kazumi_core, "turn_count", 0)

    # Calculate affection hearts bar
    filled_hearts = min(10, max(0, affection // 10))
    empty_hearts = 10 - filled_hearts
    heart_bar = "💖" * filled_hearts + "🤍" * empty_hearts

    embed = create_kazumi_embed(
        title="🌸 Kazumi Companion Status",
        description=f"Here is our current companion bond and cozy stats, **{interaction.user.display_name}**!"
    )
    embed.add_field(name="Affection Level", value=f"{heart_bar} **{affection}%**", inline=False)
    embed.add_field(name="Cozy Points", value=f"✨ **{cozy_points} pts**", inline=True)
    embed.add_field(name="Active Persona", value=f"🌸 **{persona}**", inline=True)
    embed.add_field(name="Conversations", value=f"💬 **{turn_count} turns**", inline=True)
    
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="diary", description="Read what Kazumi wrote in her diary today 📖")
async def slash_diary(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    session_id = get_user_session_id(interaction.user)
    reply_text = await ask_kazumi("/diary", session_id)
    embed = create_kazumi_embed(
        title="📖 Kazumi's Diary Entry",
        description=reply_text[:4000]
    )
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="quests", description="View your active cozy quests and achievements 🌟")
async def slash_quests(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    session_id = get_user_session_id(interaction.user)
    reply_text = await ask_kazumi("/quests", session_id)
    embed = create_kazumi_embed(
        title="🌟 Cozy Quests & Goals",
        description=reply_text[:4000]
    )
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="horoscope", description="Receive a personalized daily cosmic horoscope from Kazumi ✨")
@app_commands.describe(sign="Your zodiac sign (e.g., Aries, Taurus, Gemini, Cancer, Leo, Virgo, Libra, Scorpio, Sagittarius, Capricorn, Aquarius, Pisces)")
async def slash_horoscope(interaction: discord.Interaction, sign: str = "Aries"):
    await interaction.response.defer(thinking=True)
    if not kazumi_core:
        await interaction.followup.send("Kazumi core is currently offline.")
        return
    
    with kazumi_lock:
        horo = kazumi_core.get_daily_horoscope(sign.strip().title())

    embed = create_kazumi_embed(
        title=f"✨ Daily Cosmic Reading for {sign.strip().title()}",
        description=horo.get("prediction", "May your day be filled with warm smiles and calm moments! 🌸")
    )
    embed.add_field(name="Lucky Gift", value=f"🎁 {horo.get('lucky_gift', 'Cherry Blossoms')}", inline=True)
    embed.add_field(name="Lucky Decor", value=f"🖼️ {horo.get('lucky_decor', 'Soft Cushion')}", inline=True)
    embed.add_field(name="Cosmic Affinity", value=f"💫 **{horo.get('affinity', 85)}%**", inline=True)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="persona", description="Check or switch Kazumi's personality archetype 🎭")
@app_commands.choices(archetype=[
    app_commands.Choice(name="Deredere (Loving & Sweet)", value="DEREDERE"),
    app_commands.Choice(name="Teasing (Playful & Mischievous)", value="TEASING"),
    app_commands.Choice(name="Kuudere (Cool & Composed)", value="KUUDERE"),
    app_commands.Choice(name="Tsundere (Feisty & Protective)", value="TSUNDERE"),
])
async def slash_persona(interaction: discord.Interaction, archetype: Optional[app_commands.Choice[str]] = None):
    await interaction.response.defer(thinking=True)
    if not kazumi_core:
        await interaction.followup.send("Kazumi core is currently offline.")
        return

    session_id = get_user_session_id(interaction.user)
    with kazumi_lock:
        if archetype:
            kazumi_core.current_archetype = archetype.value
            desc = f"Switched Kazumi's personality style to **{archetype.name}** for our upcoming chats! 🌸"
        else:
            desc = f"Kazumi's current active personality is **{kazumi_core.current_archetype}**."

    embed = create_kazumi_embed(
        title="🎭 Companion Personality Style",
        description=desc
    )
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="reset", description="Clear your conversation history with Kazumi for a fresh start 🌿")
async def slash_reset(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    if not kazumi_core:
        await interaction.followup.send("Kazumi core is offline.")
        return

    session_id = get_user_session_id(interaction.user)
    with kazumi_lock:
        kazumi_core.memory.history = []
        kazumi_core.memory.save_history(session_id)
    
    embed = create_kazumi_embed(
        title="🌿 Fresh Start",
        description="I've cleared our recent chat history for a fresh start! I'm right here whenever you'd like to talk again. 🌸"
    )
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="help", description="How to interact with Kazumi in your server 🌸")
async def slash_help(interaction: discord.Interaction):
    embed = create_kazumi_embed(
        title="🌸 How to Talk with Kazumi",
        description=(
            "Kazumi is an empathetic, caring AI companion bot designed to bring cozy, uplifting conversations to your server!\n\n"
            "**Ways to Chat:**\n"
            "• **Mention her:** Type `@Kazumi Hello!` anywhere in the server.\n"
            "• **Direct Message:** Send a DM directly to Kazumi.\n"
            "• **Slash Command:** Use `/chat <message>`.\n\n"
            "**Available Commands:**\n"
            "• `/status` - Check affection score, cozy points, and mood.\n"
            "• `/diary` - Read her journal reflections.\n"
            "• `/quests` - View active quests and challenges.\n"
            "• `/reset` - Start a fresh conversation session.\n"
            "• `/help` - Show this helpful guide."
        )
    )
    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# Runner & Setup Guidance
# ---------------------------------------------------------------------------

def print_discord_setup_guide():
    """Prints a clear step-by-step setup guide if token is missing."""
    print("\n" + "=" * 68)
    print("🌸 KAZUMI DISCORD BOT SETUP GUIDE")
    print("=" * 68)
    print("No DISCORD_BOT_TOKEN was found in your environment or .env file.")
    print("\nTo add Kazumi to your Discord server, follow these quick steps:")
    print("1. Go to Discord Developer Portal: https://discord.com/developers/applications")
    print("2. Click 'New Application', enter 'Kazumi', and create it.")
    print("3. In the left sidebar, click 'Bot' -> 'Add Bot'.")
    print("4. Scroll down to 'Privileged Gateway Intents' and turn ON:")
    print("   ✓ MESSAGE CONTENT INTENT (Crucial for reading messages)")
    print("5. Click 'Reset Token' and copy your bot token.")
    print("6. Paste the token into your .env file:")
    print("   DISCORD_BOT_TOKEN=your_token_here")
    print("7. Invite Kazumi to your server using this OAuth2 URL:")
    print("   Go to 'OAuth2' -> 'URL Generator' in Developer Portal:")
    print("   • Scopes: 'bot', 'applications.commands'")
    print("   • Bot Permissions: 'Send Messages', 'Read Message History',")
    print("     'Embed Links', 'Attach Files', 'Use Slash Commands'")
    print("8. Run this script again: python discord_bot.py")
    print("=" * 68 + "\n")


def main():
    logger.info(f"🌸 Main entrypoint reached! DISCORD_BOT_TOKEN length: {len(DISCORD_BOT_TOKEN)}")
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "your_discord_bot_token_here":
        logger.error("❌ DISCORD_BOT_TOKEN is missing or empty! Bot cannot connect to Discord.")
        print_discord_setup_guide()
        sys.exit(1)

    logger.info(f"🌸 Connecting to Discord Gateway (prefix: {PREFIX}, channel: {DISCORD_CHANNEL_ID or 'all'})...")
    try:
        bot.run(DISCORD_BOT_TOKEN, log_handler=None)
        logger.info("🌸 Discord bot run loop finished cleanly.")
    except discord.errors.LoginFailure as lf:
        logger.error(f"❌ Login failure: Invalid Discord Bot Token: {lf}")
        sys.exit(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("🌸 Bot stopped by signal.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"⚠️ Discord connection dropped or failed: {e}", exc_info=True)
        # Exit with status 1 so start.sh restarts a clean Python process with fresh aiohttp session
        sys.exit(1)


if __name__ == "__main__":
    main()
