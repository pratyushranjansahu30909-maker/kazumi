#!/usr/bin/env python3
"""
🌸 Kazumi Discord Bot — AI Companion Integration
Connects Kazumi's cognitive chat engine directly into Discord as a server companion bot.
"""

import os
import sys

# Force UTF-8 stdout & stderr with replacement to prevent Windows cp1252 charmap encoding crashes
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

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

# Logging setup with safe utf-8 stream handler
log_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[log_handler]
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
    async def login(self, token: str) -> None:
        try:
            self.http.connector = aiohttp.TCPConnector(family=socket.AF_INET, limit=0)
            logger.info("🌸 Configured IPv4 TCPConnector for static login.")
        except Exception as e:
            logger.warning(f"Could not configure custom IPv4 TCPConnector: {e}")
        return await super().login(token)

    async def setup_hook(self):
        try:
            # Force IPv4 TCPConnector inside the running event loop
            if self.http.connector is None or getattr(self.http.connector, '_family', None) != socket.AF_INET:
                self.http.connector = aiohttp.TCPConnector(family=socket.AF_INET, limit=0)
            logger.info("🌸 Configured IPv4 TCPConnector for Discord client.")
        except Exception as e:
            logger.warning(f"Could not configure custom IPv4 TCPConnector: {e}")

bot = KazumiBot(command_prefix=commands.when_mentioned_or(PREFIX), intents=intents, help_command=None)

# Active conversational sessions: (channel_id, user_id) -> last_active_timestamp
active_conversations = {}
# Active channel sessions: channel_id -> last_active_timestamp
active_channel_conversations = {}
CONVERSATION_TIMEOUT_SECONDS = 300  # Continuous conversation (5 minutes) without requiring repetitive @Kazumi tags
CHANNEL_CONVERSATION_TIMEOUT_SECONDS = 120  # Channel stays attentive for 2 minutes after Kazumi speaks

# Cache of recent message IDs sent by Kazumi to accurately detect replies
recent_bot_message_ids = set()


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def split_message(text: str, max_chars: int = 1950) -> List[str]:
    """Splits text cleanly by paragraphs or sentences to obey Discord's 2000-char limit."""
    text = (text or "").strip()
    if not text:
        return ["I'm right here with you! 🌸"]
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
        res = kazumi_core.reply(text, session_id=session_id)
        return res if res else "I'm right here with you! 🌸 (Kazumi smiles warmly.)"


async def ask_kazumi(text: str, session_id: str) -> str:
    """Non-blocking asynchronous wrapper over Kazumi's core reply."""
    try:
        reply = await asyncio.to_thread(sync_kazumi_reply, text, session_id)
        return (reply or "").strip() or "I'm right here with you! 🌸"
    except Exception as e:
        logger.error(f"Error in ask_kazumi wrapper: {e}", exc_info=True)
        return "I'm right here with you! 🌸 (Kazumi nods softly.) How are you feeling today?"


async def send_kazumi_response(message: discord.Message, text: str):
    """Reliably delivers messages to the user/channel with automatic fallback."""
    text = (text or "").strip()
    if not text:
        text = "I'm right here with you! 🌸 (Kazumi smiles warmly.)"
    chunks = split_message(text)
    for idx, chunk in enumerate(chunks):
        sent_msg = None
        if idx == 0:
            try:
                sent_msg = await message.reply(chunk, mention_author=False)
            except Exception:
                try:
                    sent_msg = await message.channel.send(chunk)
                except Exception as send_err:
                    logger.error(f"Failed to send reply chunk: {send_err}")
        else:
            try:
                sent_msg = await message.channel.send(chunk)
            except Exception as send_err:
                logger.error(f"Failed to send followup chunk: {send_err}")

        if sent_msg and hasattr(sent_msg, "id"):
            recent_bot_message_ids.add(sent_msg.id)
            if len(recent_bot_message_ids) > 1000:
                try:
                    recent_bot_message_ids.pop()
                except Exception:
                    pass


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
async def on_disconnect():
    logger.warning("⚠️ Discord Gateway disconnected. Automatic reconnection will occur when network is restored.")


@bot.event
async def on_resumed():
    logger.info("✨ Discord Gateway session successfully resumed! Kazumi is back listening.")


@bot.event
async def on_message(message: discord.Message):
    # Ignore self and other bots
    if message.author.bot or (bot.user and message.author.id == bot.user.id):
        return

    raw_content = (message.content or "").strip()
    logger.info(f"📩 New message from {message.author} in #{getattr(message.channel, 'name', 'DM')}: '{raw_content}'")

    # 1. Check if message is in DM (Direct Message)
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_user_mentioned = bot.user in message.mentions if bot.user else False

    # 2. Check role mentions belonging to Kazumi
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

    # 3. Check if reply to Kazumi
    is_reply_to_kazumi = False
    if message.reference:
        ref_id = message.reference.message_id
        if ref_id and ref_id in recent_bot_message_ids:
            is_reply_to_kazumi = True
        elif message.reference.resolved:
            resolved = message.reference.resolved
            if hasattr(resolved, 'author') and bot.user and resolved.author.id == bot.user.id:
                is_reply_to_kazumi = True
        elif ref_id:
            try:
                ref_msg = await message.channel.fetch_message(ref_id)
                if ref_msg and bot.user and ref_msg.author.id == bot.user.id:
                    is_reply_to_kazumi = True
                    recent_bot_message_ids.add(ref_id)
            except Exception:
                pass

    # 4. Check if calling name in text (Kazumi, Kasumi, Zumi, Kazzy, Kaz)
    name_called = bool(re.search(r'(?:kazumi|kasumi|kazum1|zumi|kazzy|\bkaz\b)', raw_content, re.IGNORECASE))

    # 5. Check if prefix is called
    is_prefix_called = False
    prefix_clean = PREFIX.strip().lower()
    if raw_content:
        cl = raw_content.lower()
        if cl.startswith("!k") or cl.startswith("!kazumi") or cl.startswith("k!") or (prefix_clean and cl.startswith(prefix_clean)):
            is_prefix_called = True

    # 6. Check dedicated bot channel
    channel_name = getattr(message.channel, 'name', '').lower()
    dedicated_keywords = ["kazumi", "companion", "ai-chat", "talk-to-kazumi", "bot-chat", "chat-with-kazumi"]
    is_dedicated_channel = (
        (DISCORD_CHANNEL_ID and str(message.channel.id) == str(DISCORD_CHANNEL_ID))
        or any(k in channel_name for k in dedicated_keywords)
        or (message.guild and len(message.guild.text_channels) <= 2)  # Focused servers like EUPHORIA with 1-2 channels
    )

    # 7. Check ongoing conversational session with this user
    session_key = (message.channel.id, message.author.id)
    now = time.time()
    is_active_convo = False
    if session_key in active_conversations:
        if now - active_conversations[session_key] <= CONVERSATION_TIMEOUT_SECONDS:
            is_active_convo = True
        else:
            active_conversations.pop(session_key, None)

    # 8. Check recent channel-level interaction (stays attentive for 2 mins)
    is_active_channel = False
    if message.channel.id in active_channel_conversations:
        if now - active_channel_conversations[message.channel.id] <= CHANNEL_CONVERSATION_TIMEOUT_SECONDS:
            is_active_channel = True
        else:
            active_channel_conversations.pop(message.channel.id, None)

    # If user explicitly tags someone else (and not Kazumi), they are conversing with that person
    is_talking_to_other = bool(message.mentions) and not is_user_mentioned

    # Filter out commands intended for other bots (like !play, ?ban, /skip, $price) in shared channels
    is_other_bot_cmd = False
    if raw_content and raw_content[0] in "!?.$-/" and not is_prefix_called:
        if len(raw_content) > 1 and raw_content[1].isalpha():
            is_other_bot_cmd = True

    # Evaluate response condition:
    # In DMs, direct mentions, replies, or prefixes -> ALWAYS RESPOND (never blocked by is_other_bot_cmd)
    if is_dm or is_mentioned or is_reply_to_kazumi or is_prefix_called:
        should_respond = True
    elif (name_called or is_dedicated_channel or is_active_convo or is_active_channel) and not is_talking_to_other and not is_other_bot_cmd:
        should_respond = True
    else:
        should_respond = False

    if not should_respond:
        await bot.process_commands(message)
        return

    try:
        # Clean text
        clean_text = raw_content
        if bot.user:
            clean_text = re.sub(rf"<@!?{bot.user.id}>", "", clean_text)
        clean_text = re.sub(r"<@&?\d+>", "", clean_text)
        clean_text = re.sub(r"^\s*!(?:k|kazumi)\b[:,]?", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"^\s*k!\b[:,]?", "", clean_text, flags=re.IGNORECASE)
        if prefix_clean:
            clean_text = re.sub(r"^\s*" + re.escape(prefix_clean) + r"\b[:,]?", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"^\s*@?(?:kazumi|kasumi|zumi|kazzy|\bkaz\b)\b[:,]?", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"^[,\s:-]+", "", clean_text).strip()

        if not clean_text:
            if message.attachments:
                clean_text = "I shared a photo or attachment with you! 🌸"
            elif message.stickers:
                clean_text = "I sent you a cute sticker! 🌸"
            else:
                # User pinged Kazumi without extra text
                await send_kazumi_response(
                    message,
                    "Hello there! 🌸 How are you doing today? You can talk to me anytime, or use `/help` to see what we can do together!"
                )
                active_conversations[session_key] = time.time()
                active_channel_conversations[message.channel.id] = time.time()
                return

        session_id = get_user_session_id(message.author)
        logger.info(f"🧠 Processing message from {message.author}: '{clean_text}' (session: {session_id})")

        reply_text = None
        # Safely trigger typing indicator while generating reply
        try:
            async with message.channel.typing():
                reply_text = await asyncio.wait_for(ask_kazumi(clean_text, session_id), timeout=35.0)
        except Exception as typing_err:
            if not reply_text:
                try:
                    reply_text = await asyncio.wait_for(ask_kazumi(clean_text, session_id), timeout=25.0)
                except Exception as core_err:
                    logger.error(f"Error querying Kazumi core: {core_err}", exc_info=True)
                    reply_text = "I'm right here with you! 🌸 (Kazumi smiles warmly.) What's on your mind?"

        reply_text = (reply_text or "").strip() or "I'm right here with you! 🌸"
        logger.info(f"💬 Replying to {message.author}: '{reply_text[:60]}...'")

        # Update active conversation timestamps (user-level and channel-level)
        active_conversations[session_key] = time.time()
        active_channel_conversations[message.channel.id] = time.time()

        # If user explicitly says goodbye, end the continuous session
        farewell_words = {"bye", "goodbye", "cya", "see ya", "gn", "goodnight", "good night", "gotta go", "stop", "exit"}
        norm_clean = re.sub(r"[^\w\s]", "", clean_text).lower().strip()
        if norm_clean in farewell_words or any(norm_clean.startswith(fw + " ") for fw in farewell_words):
            active_conversations.pop(session_key, None)

        # Deliver message reliably with fallback
        await send_kazumi_response(message, reply_text)

    except Exception as e:
        logger.error(f"❌ Error in on_message: {e}", exc_info=True)
        await send_kazumi_response(
            message,
            "I'm right here with you! 🌸 (Kazumi nods warmly.) Something went a little fuzzy for a second, but I'm listening now!"
        )


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
    try:
        reply_text = await asyncio.wait_for(ask_kazumi(message, session_id), timeout=35.0)
    except Exception as e:
        logger.error(f"Error in slash_chat: {e}", exc_info=True)
        reply_text = "I'm right here with you! 🌸 (Kazumi smiles warmly.) Please ask me again, I'm ready to chat!"

    reply_text = (reply_text or "").strip() or "I'm right here with you! 🌸"
    chunks = split_message(reply_text)
    await interaction.followup.send(chunks[0])
    for chunk in chunks[1:]:
        try:
            await interaction.channel.send(chunk)
        except Exception:
            pass


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


INSTANCE_LOCK_PORT = 49281
_instance_socket = None

def acquire_single_instance_lock() -> bool:
    """Ensures only a single bot process runs locally to prevent gateway session conflicts."""
    global _instance_socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        s.bind(("127.0.0.1", INSTANCE_LOCK_PORT))
        _instance_socket = s
        return True
    except socket.error:
        return False


def respawn_process():
    """Cleanly releases lock and respawns the bot process."""
    global _instance_socket
    if _instance_socket:
        try:
            _instance_socket.close()
        except Exception:
            pass
    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv)
        sys.exit(0)


def main():
    logger.info(f"🌸 Main entrypoint reached! DISCORD_BOT_TOKEN length: {len(DISCORD_BOT_TOKEN)}")
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "your_discord_bot_token_here":
        logger.error("❌ DISCORD_BOT_TOKEN is missing or empty! Bot cannot connect to Discord.")
        print_discord_setup_guide()
        sys.exit(1)

    if not acquire_single_instance_lock():
        logger.warning("🌸 Another instance of Kazumi Discord Bot is already running on this machine. Exiting cleanly to avoid duplicate gateway conflicts.")
        sys.exit(0)

    retry_delay = 5
    max_delay = 60

    while True:
        logger.info(f"🌸 Connecting to Discord Gateway (prefix: {PREFIX}, channel: {DISCORD_CHANNEL_ID or 'all'})...")
        try:
            bot.run(DISCORD_BOT_TOKEN, log_handler=None)
            logger.info("🌸 Discord bot run loop finished. Respawning in 5 seconds...")
            time.sleep(5)
            respawn_process()
        except discord.errors.LoginFailure as lf:
            logger.error(f"❌ Fatal login failure: Invalid Discord Bot Token: {lf}")
            sys.exit(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("🌸 Bot stopped by user signal.")
            sys.exit(0)
        except Exception as e:
            logger.error(f"⚠️ Discord connection dropped or failed: {e}. Auto-reconnecting in {retry_delay}s...", exc_info=True)
            time.sleep(retry_delay)
            retry_delay = min(max_delay, int(retry_delay * 1.5))
            respawn_process()


if __name__ == "__main__":
    main()
