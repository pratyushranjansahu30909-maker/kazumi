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
import random
import time
from datetime import datetime, timezone
from typing import List, Optional

from text_recognition import get_text_recognition_engine
from kazumi_emotions import get_emotion_engine

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import socket

# Deployment Environment Detection
def get_deployment_environment() -> dict:
    """Detects whether running locally or on a remote cloud container."""
    is_docker = os.path.exists("/.dockerenv") or os.environ.get("CONTAINER", "") == "docker"
    space_id = os.environ.get("SPACE_ID") or os.environ.get("HF_SPACE_ID")
    render_id = os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID")

    if space_id:
        env_name = f"Hugging Face Spaces ({space_id})"
        is_remote = True
    elif render_id:
        env_name = "Render Cloud Service"
        is_remote = True
    elif is_docker:
        env_name = "Docker Container (Remote)"
        is_remote = True
    else:
        env_name = f"Local PC Host ({sys.platform})"
        is_remote = False

    return {
        "name": env_name,
        "is_remote": is_remote,
        "platform": sys.platform
    }

DEPLOY_ENV = get_deployment_environment()

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

from discord_features.config import SanitizedLogFormatter
log_handler.setFormatter(SanitizedLogFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

# Import Kazumi Core
try:
    from kazumi import Kazumi, FolderLock
    logger.info("[STARTUP] Initializing Kazumi core cognitive engine...")
    kazumi_core = Kazumi()
    # Ensure pure chat bot mode
    kazumi_core.voice_enabled = False
    logger.info("[STARTUP] Kazumi core engine loaded successfully.")
except Exception as e:
    logger.error(f"[STARTUP] Failed to load Kazumi core engine: {e}")
    kazumi_core = None

kazumi_lock = threading.Lock()

# Person Memory & Behaviour Observation System
try:
    from person_memory import get_observation_manager, BEHAVIOUR_CONFIDENCE_THRESHOLD
    obs_manager = get_observation_manager()
    profile_count = len(obs_manager.memory_mgr._profiles_cache) if obs_manager else 0
    logger.info(f"[MEMORY] Persistent memory loaded: {profile_count} person profile(s) initialized.")
except Exception as e:
    logger.error(f"[MEMORY] Failed to initialize person memory system: {e}")
    obs_manager = None

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
CREATOR_USER_IDS = set(x.strip() for x in os.environ.get("CREATOR_USER_IDS", "").split(",") if x.strip())
AAMIR_USER_IDS = set(x.strip() for x in os.environ.get("AAMIR_USER_IDS", "").split(",") if x.strip())
SHAN_USER_IDS = set(x.strip() for x in os.environ.get("SHAN_USER_IDS", "1203721997805424650").split(",") if x.strip())

# Bot Intents
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content for chat

# Robust IPv4 TCP Connector for Discord Gateway
def create_discord_connector():
    try:
        return aiohttp.TCPConnector(family=socket.AF_INET, ssl=True)
    except Exception:
        return None

bot_connector = create_discord_connector()
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(PREFIX),
    intents=intents,
    help_command=None,
    connector=bot_connector
)
bot.kazumi_core = kazumi_core

# Initialize Kazumi Advanced Feature Suite (Moderation, Logging, Tickets, Giveaways, Music, etc.)
import discord_features
kazumi_features = discord_features.setup_all_features(bot, bot.tree)

# Active conversational sessions: (channel_id, user_id) -> last_active_timestamp
active_conversations = {}
CONVERSATION_TIMEOUT_SECONDS = 90  # Stays attentive for 90 seconds after direct interaction


# Cache of recent message IDs sent by Kazumi to accurately detect replies
recent_bot_message_ids = set()

# Observational Roasting & Message Activity Tracking (Sections 5 & 21)
user_rapid_typing: dict[int, list[float]] = {}
recent_messages_for_delete_observation: dict[int, float] = {}

# Stop / silence phrases in English and Hindi / Hinglish
STOP_PHRASES = {
    "stop", "shut up", "stfu", "quiet", "silent", "silence",
    "leave me alone", "go away", "stop talking", "dont talk",
    "don't talk", "dont reply", "don't reply", "stop replying",
    "stop spamming", "dont spam", "don't spam", "stop bot",
    "chup", "chup kar", "chup ho ja", "chup chap", "chupkr",
    "spam mat kar", "message spam mat kar", "mat bol", "mat bolo",
    "bas kar", "band kar", "ruk ja", "shh", "shhh", "shutup",
    "die", "u die", "you die", "abe u die"
}

# Chat slang, laughter, and reaction words that should NEVER trigger an unprompted bot reply
CHAT_REACTIONS_AND_SLANG = {
    "lol", "lmao", "lmfao", "lawl", "haha", "hahaha", "hahahaha", "xd",
    "rofl", "kek", "gg", "w", "l", "fr", "nah", "bruh", "damn", "wtf",
    "omg", "no way", "oof", "yea", "yeah", "ok", "okay", "k", "die",
    "rip", "f", "cope", "ratio", "pog", "poggers", "cap", "no cap",
    "crazy", "wild", "real", "idk", "smh", "tbh", "wth", "yep", "yup",
    "abe u die", "u die", "you die", "ye kya hai", "kya hai ye", "kya hai",
    "wait", "what", "bro", "dude", "man"
}


def is_kazumi_channel(channel) -> bool:
    """Returns True if the channel is permitted for Kazumi conversations."""
    if isinstance(channel, discord.DMChannel):
        return True
    if DISCORD_CHANNEL_ID and str(channel.id) == str(DISCORD_CHANNEL_ID):
        return True
    ch_name = getattr(channel, "name", "").lower()
    return "kazumi" in ch_name


def find_kazumi_channel_in_guild(guild: Optional[discord.Guild]) -> Optional[discord.TextChannel]:
    """Finds a dedicated Kazumi channel in the guild if one exists."""
    if not guild or not hasattr(guild, "text_channels"):
        return None
    for ch in guild.text_channels:
        if is_kazumi_channel(ch):
            return ch
    return None


def is_stop_command(text: str) -> bool:
    """Detects if user is asking Kazumi to be quiet, stop talking, or stop spamming."""
    if not text:
        return False
    norm = re.sub(r"[^\w\s]", " ", text.lower()).strip()
    norm = re.sub(r"\s+", " ", norm)
    if not norm:
        return False
    if norm in STOP_PHRASES:
        return True
    for phrase in STOP_PHRASES:
        if norm.startswith(phrase + " ") or norm.endswith(" " + phrase) or f" {phrase} " in f" {norm} ":
            return True
    return False


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


def detect_creator_relationship(user: discord.User | discord.Member) -> tuple[Optional[str], Optional[str]]:
    """
    Identifies whether the Discord user is one of Kazumi's creators and fathers:
    - 'Aamir the Chad'
    - 'Sir Shan D. First'
    Returns (creator_title, creator_context_description) or (None, None).
    """
    uid_str = str(getattr(user, "id", ""))
    combined = f"{getattr(user, 'name', '')} {getattr(user, 'display_name', '')} {getattr(user, 'global_name', '')}".lower()
    
    # 1. Check Aamir first (by name keyword or explicit Aamir UID)
    if uid_str in AAMIR_USER_IDS or any(w in combined for w in ["aamir the chad", "aamir", "amir"]):
        return ("Aamir the Chad", "Aamir the Chad (your creator and father)")
        
    # 2. Check Shan (by name keyword or explicit Shan UID)
    if uid_str in SHAN_USER_IDS or any(w in combined for w in ["shan2157", "sir shan", "shan d. first", "shan d first", "shan"]):
        return ("Sir Shan D. First", "Sir Shan D. First (your creator and father)")
        
    # 3. Check general CREATOR_USER_IDS if configured
    if uid_str in CREATOR_USER_IDS:
        return ("Creator", "Creator and Father")

    return (None, None)


def sync_kazumi_reply(text: str, session_id: str, user_name: Optional[str] = None, creator_identity: Optional[str] = None, person_directive: Optional[str] = None) -> str:
    """Thread-safe call to Kazumi's sync reply function."""
    if not kazumi_core:
        return "I'm having a little trouble connecting to my thoughts right now. Please try again in a moment! 🌸"
    with kazumi_lock:
        if creator_identity:
            kazumi_core.creator_context = creator_identity
        else:
            kazumi_core.creator_context = None

        if person_directive:
            kazumi_core.person_directive = person_directive
        else:
            kazumi_core.person_directive = None

        if user_name:
            kazumi_core.load_game_states(session_id)
            kazumi_core.current_user_name = user_name
            if hasattr(kazumi_core, "memory") and hasattr(kazumi_core.memory, "profile"):
                profile = kazumi_core.memory.profile
                session_game_states = profile.setdefault("session_game_states", {})
                game_state = session_game_states.setdefault(session_id, {})
                game_state["user_name"] = user_name
                if creator_identity:
                    profile["name"] = user_name
                elif not profile.get("name") or profile.get("name").strip().lower() in ("friend", "user", "sweetie", "none"):
                    profile["name"] = user_name

        res = kazumi_core.reply(text, session_id=session_id)
        kazumi_core.creator_context = None
        kazumi_core.person_directive = None
        kazumi_core.current_user_name = None
        return res if res else "I'm right here with you! 🌸 (Kazumi smiles warmly.)"


async def ask_kazumi(text: str, session_id: str, user_name: Optional[str] = None, creator_identity: Optional[str] = None, person_directive: Optional[str] = None) -> str:
    """Non-blocking asynchronous wrapper over Kazumi's core reply."""
    try:
        reply = await asyncio.to_thread(sync_kazumi_reply, text, session_id, user_name, creator_identity, person_directive)
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
    """Creates a stylized embed card matching Kazumi's aesthetic."""
    embed = discord.Embed(title=title, description=description, color=color)
    is_unhinged = False
    if kazumi_core and getattr(kazumi_core, "current_archetype", "") == "UNHINGED":
        is_unhinged = True
    footer_text = "Kazumi AI • Unhinged Savage Mode 💀🔥" if is_unhinged else "Kazumi AI Companion • Cozy & Caring 🌸"
    embed.set_footer(text=footer_text, icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None)
    return embed


# ---------------------------------------------------------------------------
# Discord Bot Events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    logger.info(f"[CONNECTION] Discord Gateway connected as {bot.user.name}#{bot.user.discriminator} (ID: {bot.user.id})")
    logger.info(f"[CONNECTION] Connected to {len(bot.guilds)} server(s).")
    
    # Set status presence
    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name="@Kazumi or /chat 🌸"
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)

    # Sync Slash Application Commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"[STARTUP] Synced {len(synced)} slash command(s).")
    except Exception as e:
        logger.warning(f"Slash command sync failed: {e}")

    # Launch Kazumi background feature task (Giveaways, Reminders, Server Moments)
    bot.loop.create_task(kazumi_background_feature_loop())

    print("\n" + "=" * 60)
    print("🌸 KAZUMI DISCORD BOT IS READY AND LISTENING!")
    print(f"Host: {DEPLOY_ENV['name']}")
    print(f"Bot Tag: {bot.user}")
    print("Mention Kazumi in any server channel or use /chat to speak!")
    print("=" * 60 + "\n")



@bot.event
async def on_disconnect():
    logger.warning("[RECONNECT] Discord Gateway connection dropped. Retrying automatically...")


@bot.event
async def on_resumed():
    logger.info("[RECOVERY] Discord Gateway session successfully resumed! Kazumi is back listening.")


@bot.event
async def on_message_delete(message: discord.Message):
    """Observational Roasting: Catch quick message deletes (Section 5)."""
    if not message or not message.author or message.author.bot:
        return
    send_time = recent_messages_for_delete_observation.pop(message.id, None)
    if send_time and (time.time() - send_time <= 12.0):
        if is_kazumi_channel(message.channel) or isinstance(message.channel, discord.DMChannel):
            db_inst = kazumi_features.get("db")
            if db_inst and not db_inst.is_user_roast_opted_out(message.author.id):
                if random.random() < 0.40:
                    try:
                        await message.channel.send("too late. the digital crime scene has been secured. 📸💀")
                    except Exception:
                        pass


@bot.event
async def on_message(message: discord.Message):
    # Ignore self and other bots
    if message.author.bot or (bot.user and message.author.id == bot.user.id):
        return

    raw_content = (message.content or "").strip()
    channel = message.channel
    is_dm = isinstance(channel, discord.DMChannel)
    in_kazumi_channel = is_kazumi_channel(channel)

    # Record message for quick deletion observation (Section 5)
    recent_messages_for_delete_observation[message.id] = time.time()
    if len(recent_messages_for_delete_observation) > 500:
        try:
            recent_messages_for_delete_observation.pop(next(iter(recent_messages_for_delete_observation)))
        except Exception:
            pass

    # Observational Roasting: Rapid-fire messages (Section 5)
    user_times = user_rapid_typing.setdefault(message.author.id, [])
    now_t = time.time()
    user_times.append(now_t)
    user_rapid_typing[message.author.id] = [t for t in user_times if now_t - t <= 8.0]
    if len(user_rapid_typing[message.author.id]) >= 5:
        user_rapid_typing[message.author.id].clear()
        db_inst = kazumi_features.get("db")
        if (is_dm or in_kazumi_channel) and (not db_inst or not db_inst.is_user_roast_opted_out(message.author.id)):
            try:
                await message.channel.send("bro is typing like the FBI just gave him 30 seconds to explain himself 💀")
                return
            except Exception:
                pass

    # =========================================================================
    # 0A. AUTOMOD ENFORCEMENT (Section 2)
    # =========================================================================
    if message.guild and kazumi_features.get("automod"):
        gid_str = str(message.guild.id)
        db_inst = kazumi_features["db"]
        g_settings = db_inst.get_guild_settings(gid_str)
        automod_cfg = g_settings.get("automod", {})
        if automod_cfg.get("enabled", False):
            is_staff = False
            if hasattr(message.author, "guild_permissions"):
                is_staff = message.author.guild_permissions.manage_messages or message.author.guild_permissions.administrator
            if not is_staff:
                violated, rule_name, evidence = kazumi_features["automod"].record_and_evaluate(message, automod_cfg)
                if violated:
                    case_id = db_inst.create_case(message.guild.id, message.author.id, bot.user.id if bot.user else 0, "AUTOMOD", rule_name, evidence=evidence)
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    mod_embed = discord.Embed(
                        title=f"🛡️ AutoMod Rule Enforced • Case #{case_id}",
                        description=(
                            f"**User:** {message.author.mention} (`{message.author.id}`)\n"
                            f"**Rule Violated:** `{rule_name}`\n"
                            f"**Evidence:** {evidence}\n"
                            f"**Case ID:** `#{case_id}`\n"
                            f"**Channel:** {message.channel.mention}"
                        ),
                        color=0xf43f5e
                    )
                    mod_embed.timestamp = datetime.now(timezone.utc)
                    await kazumi_features["logging"].log_event(message.guild, mod_embed)
                    try:
                        await message.channel.send(
                            f"⚠️ {message.author.mention}, your message violated server rules (**{rule_name}** - Case `#{case_id}`) and was removed.",
                            delete_after=8
                        )
                    except Exception:
                        pass
                    return

    # =========================================================================
    # 0B. CUSTOM COMMANDS DISPATCHER (Section 9)
    # =========================================================================
    if await kazumi_features["custom_commands"].maybe_handle_message(message):
        return

    # =========================================================================
    # 0C. SOCIAL GRAPH & SERVER MEMORY OBSERVATION (Sections 17 & 18)
    # =========================================================================
    if message.guild:
        author_name_str = getattr(message.author, "display_name", "") or getattr(message.author, "name", "")
        kazumi_features["social_graph"].record_interaction(
            message.guild.id,
            message.author.id,
            author_name_str,
            raw_content
        )
        kazumi_features["mood"].update_mood(message.guild.id, raw_content)
        if hasattr(message.channel, "name"):
            kazumi_features["server_memory"].learn_channel_purpose(
                message.guild.id,
                message.channel.id,
                message.channel.name
            )
        kazumi_features["continuity"].record_subject(message.guild.id, message.author.id, raw_content)

    # 1. Check if user or role mentioned Kazumi
    is_user_mentioned = bot.user in message.mentions if bot.user else False
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

    # 2. Check if reply to Kazumi
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

    # 3. Check if directly addressed by name at start of message
    is_directly_addressed = bool(
        re.search(r'^\s*(?:hey|hi|hello|yo|dear)?\s*@?(?:kazumi|kasumi|zumi|kazzy)\b', raw_content, re.IGNORECASE)
    )

    # 4. Check if prefix is called
    is_prefix_called = False
    prefix_clean = PREFIX.strip().lower()
    if raw_content:
        cl = raw_content.lower()
        if cl.startswith("!k") or cl.startswith("!kazumi") or cl.startswith("k!") or (prefix_clean and cl.startswith(prefix_clean)):
            is_prefix_called = True

    # 5. Check if directly addressed or pinged
    is_addressed = is_user_mentioned or is_role_mentioned or is_reply_to_kazumi or is_directly_addressed or is_prefix_called

    # =========================================================================
    # 🌸 PERSON OBSERVATION & ADAPTIVE INTERACTION PIPELINE
    # =========================================================================
    author_name = getattr(message.author, "display_name", "") or getattr(message.author, "name", "")
    author_id_str = str(message.author.id)

    channel_mode = "ACTIVE_CHAT" if (is_dm or in_kazumi_channel) else "OBSERVATION_ONLY"
    react_emoji = None
    adaptive_directive = None

    if obs_manager:
        try:
            channel_mode, react_emoji, adaptive_directive = obs_manager.process_message(
                user_id=author_id_str,
                display_name=author_name,
                channel_id=str(channel.id),
                text=raw_content,
                is_dm=is_dm,
                is_dedicated=in_kazumi_channel,
                is_direct_address=is_addressed
            )
        except Exception as obs_err:
            logger.warning(f"Error in person observation manager: {obs_err}")

    # Mode 1: DISABLED — channel is completely ignored
    if channel_mode == "DISABLED":
        return

    # Mode 2: OBSERVATION_ONLY — secondary chats (Section 2B & 11)
    # - Silently observe and update behavioral profile
    # - NEVER send normal conversational text replies
    # - React with context-aware emoji if appropriate (cooldown & probability enforced)
    if channel_mode == "OBSERVATION_ONLY":
        if react_emoji:
            try:
                await message.add_reaction(react_emoji)
            except Exception:
                pass

        # If user explicitly pinged/addressed Kazumi in an observation channel, politely redirect once
        if is_addressed:
            kazumi_ch = find_kazumi_channel_in_guild(message.guild)
            if kazumi_ch and kazumi_ch.id != channel.id:
                try:
                    await message.reply(
                        f"🌸 Hi {message.author.mention}! To keep this channel clean for everyone, I only chat in <#{kazumi_ch.id}> or DMs! Come talk with me over there! ✨",
                        mention_author=False
                    )
                except Exception:
                    pass
            elif not kazumi_ch:
                try:
                    await message.reply(
                        f"🌸 Hi {message.author.mention}! Please create a dedicated `#kazumi` channel for me to chat in, or DM me directly! ✨",
                        mention_author=False
                    )
                except Exception:
                    pass
        # Never send normal text in observation-only channels
        return

    # =========================================================================
    # 🧠 RULE 2: CONVERSATIONAL INTELLIGENCE & HUMAN INTERACTION DECISION LAYER
    # =========================================================================
    rel_level = 1
    if obs_manager and hasattr(obs_manager, "memory_mgr"):
        try:
            prof = obs_manager.memory_mgr.get_profile(author_id_str)
            rel_level = prof.get("relationship_level", 1)
        except Exception:
            rel_level = 1

    if "human_interaction" in kazumi_features:
        hi_decision, hi_extra, hi_reason = kazumi_features["human_interaction"].evaluate(
            message=message,
            is_dm=is_dm,
            is_dedicated_channel=in_kazumi_channel,
            is_mentioned=is_mentioned,
            is_reply_to_kazumi=is_reply_to_kazumi,
            is_directly_addressed=is_directly_addressed,
            is_prefix_called=is_prefix_called,
            channel_mode=channel_mode,
            relationship_level=rel_level
        )
        if hi_decision.value in ("IGNORE", "OBSERVE", "WAIT"):
            return
        elif hi_decision.value == "REACT" and hi_extra:
            try:
                await message.add_reaction(hi_extra)
            except Exception:
                pass
            return

    session_key = (message.channel.id, message.author.id)

    # A. Check for STOP / SILENCE command
    if is_stop_command(raw_content):
        active_conversations.pop(session_key, None)
        if is_mentioned or is_reply_to_kazumi:
            try:
                await message.reply(
                    "(Kazumi nods softly and goes quiet) 🌸 Understood! I'll stay quiet. Just mention me or say my name when you'd like to chat again!",
                    mention_author=False
                )
            except Exception:
                pass
        return

    # B. Filter chat slang, laughter, and short reaction noise
    norm_reaction = re.sub(r"[^\w\s]", "", raw_content).lower().strip()
    if norm_reaction in CHAT_REACTIONS_AND_SLANG and not is_mentioned and not is_prefix_called:
        # User is just reacting/laughing in chat (e.g. LAWL, haha, bruh)
        # React with an emoji if recent conversation was active, but NEVER send a text message
        if session_key in active_conversations:
            try:
                if norm_reaction in {"lol", "lmao", "lmfao", "lawl", "haha", "hahaha", "xd", "rofl"}:
                    await message.add_reaction("😂")
                elif norm_reaction in {"die", "u die", "abe u die"}:
                    await message.add_reaction("👀")
            except Exception:
                pass
        return

    # C. Check ongoing conversational session with THIS specific user
    now = time.time()
    is_active_convo = False
    if session_key in active_conversations:
        if now - active_conversations[session_key] <= CONVERSATION_TIMEOUT_SECONDS:
            is_active_convo = True
        else:
            active_conversations.pop(session_key, None)

    # D. Ignore other bot commands (e.g. !play, ?ban, /skip, $price, -p)
    is_other_bot_cmd = False
    if raw_content and raw_content[0] in "!?.$-/" and not is_prefix_called:
        if len(raw_content) > 1 and (raw_content[1].isalpha() or raw_content[1] in "!?.$-/"):
            is_other_bot_cmd = True

    # E. If user explicitly tags someone else (and not Kazumi), they are talking to that other person
    is_talking_to_other = bool(message.mentions) and not is_user_mentioned

    # F. In a server channel, require direct address or clear question to avoid eavesdropping on multi-user chat
    words_count = len(raw_content.split())
    has_question = "?" in raw_content

    # Evaluate intelligent response conditions:
    # 1. In DMs: Respond naturally to ongoing conversation.
    # 2. In Server Channels: ONLY respond when directly addressed (ping, reply, prefix, or starting with her name).
    #    NEVER eavesdrop or auto-reply to unprompted multi-user chat/banter!
    if is_dm:
        should_respond = not is_other_bot_cmd
    elif is_mentioned or is_reply_to_kazumi or is_prefix_called or is_directly_addressed:
        should_respond = True
    else:
        should_respond = False

    if not should_respond:
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

        # --- Text Recognition System for Image & Document Attachments ---
        attachment_texts = []
        if message.attachments:
            try:
                rec_engine = get_text_recognition_engine()
                for att in message.attachments[:3]:
                    try:
                        att_bytes = await att.read()
                        res = rec_engine.extract_text_from_bytes(
                            att_bytes,
                            filename=att.filename,
                            mime_type=att.content_type or "image/png",
                            user_query=clean_text if clean_text else None
                        )
                        if res.get("success") and res.get("text"):
                            attachment_texts.append(f"[Recognized Text from '{att.filename}']:\n{res['text']}")
                    except Exception as att_err:
                        logger.warning(f"Error processing attachment {att.filename}: {att_err}")
            except Exception as rec_err:
                logger.warning(f"Error accessing text recognition engine: {rec_err}")

        if attachment_texts:
            rec_block = "\n\n".join(attachment_texts)
            if clean_text:
                clean_text = f"{clean_text}\n\n[Attached Content - Recognized Text]:\n{rec_block}"
            else:
                clean_text = f"I am sharing an image or document with you. Please read the recognized text and talk with me about it:\n\n{rec_block}"
        elif not clean_text:
            if message.attachments:
                clean_text = "I shared a photo or attachment with you! 🌸"
            elif message.stickers:
                clean_text = "I sent you a cute sticker! 🌸"
            else:
                # User called her name or pinged her! Let Kazumi respond naturally with personality!
                clean_text = "Hey! (The user called your name or pinged you warmly to say hi)"

        session_id = get_user_session_id(message.author)
        logger.info(f"🧠 Processing message from {message.author} in #{getattr(message.channel, 'name', 'DM')}: '{clean_text}' (session: {session_id})")

        author_name = getattr(message.author, "display_name", "") or getattr(message.author, "name", "")
        creator_title, creator_ctx = detect_creator_relationship(message.author)
        display_author = creator_title if creator_title else author_name
        if creator_title:
            logger.info(f"👑 Creator interaction detected! Author: {message.author} -> {creator_title}")

        # Check Unhinged Comeback Engine (Sections 11, 12, 13)
        roast_engine = kazumi_features.get("roast_engine")
        db_inst = kazumi_features.get("db")
        if roast_engine and db_inst and not db_inst.is_user_roast_opted_out(message.author.id):
            comeback_cat = discord_features.ComebackEngine.detect_category(clean_text)
            is_unhinged_active = (getattr(kazumi_core, "current_archetype", "") == "UNHINGED")
            if comeback_cat and (is_unhinged_active or random.random() < 0.65):
                comeback = discord_features.ComebackEngine.get_comeback(comeback_cat)
                active_conversations[session_key] = time.time()
                await send_kazumi_response(message, comeback)
                return

        # Build multi-dimensional social & contextual directive (Sections 13, 14, 16, 17, 18, 19)
        g_roast = db_inst.get_guild_roast_settings(message.guild.id) if (db_inst and message.guild) else {}
        is_roast_active = (
            getattr(kazumi_core, "roast_mode", False)
            or getattr(kazumi_core, "current_archetype", "") == "UNHINGED"
            or g_roast.get("unhinged_mode", False)
        )
        if is_roast_active and kazumi_core:
            kazumi_core.roast_mode = True
            kazumi_core.roast_intensity = 4
            kazumi_core.roast_style = "UNHINGED"
            kazumi_core.current_archetype = "UNHINGED"

        social_directives = []
        if is_roast_active:
            social_directives.append(
                "[UNHINGED SAVAGE ROAST PERSONALITY ACTIVE: Your normal sweet/cozy rules are benched. "
                "Deliver a razor-sharp, hilarious, sarcastic punchline roast (3 to 20 words max!). "
                "Never apologize. Never say you're all about cozy empathetic vibes. Never refuse to roast.]"
            )
        else:
            if message.guild:
                mood_val = kazumi_features["mood"].get_guild_mood(message.guild.id)
                mood_desc = kazumi_features["mood"].get_mood_prompt_modifier(mood_val)
                fam_desc = kazumi_features["social_graph"].get_familiarity_context(message.guild.id, message.author.id)
                server_desc = kazumi_features["server_memory"].get_server_context_summary(message.guild.id)
                resumed_ctx = kazumi_features["continuity"].get_resumed_context(message.guild.id, message.author.id)

                social_directives.append(f"[Current Internal Mood: {mood_val} - {mood_desc}]")
                if fam_desc:
                    social_directives.append(f"[{fam_desc}]")
                if resumed_ctx:
                    social_directives.append(f"[{resumed_ctx}]")
                if server_desc:
                    social_directives.append(f"[{server_desc}]")

        if adaptive_directive:
            social_directives.append(adaptive_directive)

        combined_directive = "\n".join(social_directives) if social_directives else None

        reply_text = None
        # Safely trigger typing indicator while generating reply
        try:
            async with message.channel.typing():
                reply_text = await asyncio.wait_for(ask_kazumi(clean_text, session_id, display_author, creator_ctx, person_directive=combined_directive), timeout=35.0)
        except Exception as typing_err:
            if not reply_text:
                try:
                    reply_text = await asyncio.wait_for(ask_kazumi(clean_text, session_id, display_author, creator_ctx, person_directive=combined_directive), timeout=25.0)
                except Exception as core_err:
                    logger.error(f"Error querying Kazumi core: {core_err}", exc_info=True)
                    reply_text = "I'm right here with you! 🌸 (Kazumi smiles warmly.) What's on your mind?"


        reply_text = (reply_text or "").strip() or "I'm right here with you! 🌸"
        logger.info(f"💬 Replying to {message.author}: '{reply_text[:60]}...'")

        # Update active conversation timestamp (user-level only)
        active_conversations[session_key] = time.time()

        # If user explicitly says goodbye, end the continuous session
        farewell_words = {"bye", "goodbye", "cya", "see ya", "gn", "goodnight", "good night", "gotta go", "stop", "exit"}
        norm_clean = re.sub(r"[^\w\s]", "", clean_text).lower().strip()
        if norm_clean in farewell_words or any(norm_clean.startswith(fw + " ") for fw in farewell_words):
            active_conversations.pop(session_key, None)

        # Spontaneous human girl emotion reaction on Discord message (~45% chance)
        try:
            emo_engine = get_emotion_engine()
            if random.random() < 0.45:
                emo_emoji = emo_engine.get_random_reaction_emoji()
                try:
                    await message.add_reaction(emo_emoji)
                except Exception:
                    pass
        except Exception:
            pass

        # Deliver message reliably with fallback
        await send_kazumi_response(message, reply_text)

    except Exception as e:
        logger.error(f"❌ Error in on_message: {e}", exc_info=True)
        await send_kazumi_response(
            message,
            "I'm right here with you! 🌸 (Kazumi nods warmly.) Something went a little fuzzy for a second, but I'm listening now!"
        )


# ===========================================================================
# 🌸 BACKGROUND FEATURE WORKER LOOP (Giveaways, Reminders, Server Moments)
# ===========================================================================

async def kazumi_background_feature_loop():
    """Periodic worker for giveaways, scheduled reminders, and server intelligence."""
    await bot.wait_until_ready()
    logger.info("[Background] Kazumi background feature task loop started.")
    iteration = 0
    while not bot.is_closed():
        try:
            # 1. Check giveaways every 15s
            if kazumi_features.get("giveaways"):
                await kazumi_features["giveaways"].check_active_giveaways(bot)

            # 2. Check scheduled reminders
            if kazumi_features.get("db"):
                due = kazumi_features["db"].get_due_reminders()
                for rem in due:
                    try:
                        channel_id = int(rem.get("channel_id", 0))
                        user_id = int(rem.get("user_id", 0))
                        ch = bot.get_channel(channel_id)
                        user = bot.get_user(user_id)
                        embed = discord.Embed(
                            title="⏰ Kazumi Reminder 🌸",
                            description=f"Hey {user.mention if user else 'there'}!\nYou asked me to remind you:\n\n**{rem.get('text')}**",
                            color=0xc084fc
                        )
                        embed.set_footer(text="Kazumi Reminders • Never miss a moment! 🌸")
                        embed.timestamp = datetime.now(timezone.utc)
                        if ch:
                            await ch.send(content=f"{user.mention if user else ''}", embed=embed)
                        elif user:
                            await user.send(embed=embed)
                    except Exception as rem_err:
                        logger.warning(f"Error dispatching reminder: {rem_err}")

            # 3. Server Moments & Community Questions (every ~4 hours)
            iteration += 1
            if iteration % 960 == 0:  # 960 * 15s = 4 hours
                for guild in bot.guilds:
                    if kazumi_features.get("moments") and kazumi_features["moments"].can_trigger_moment(guild.id, min_interval_hours=24):
                        k_channel = find_kazumi_channel_in_guild(guild)
                        if k_channel:
                            q = kazumi_features["moments"].get_daily_question()
                            embed = discord.Embed(
                                title="🌸 Kazumi Daily Community Question",
                                description=q,
                                color=0xffb6c1
                            )
                            embed.set_footer(text="Feel free to answer or chat with Kazumi anytime! 💕")
                            try:
                                await k_channel.send(embed=embed)
                                kazumi_features["moments"].mark_moment_triggered(guild.id)
                            except Exception:
                                pass

        except Exception as bg_err:
            logger.error(f"[Background] Error in background feature loop: {bg_err}")

        await asyncio.sleep(15)


# ===========================================================================
# 🌸 SERVER AUDIT & COMMUNITY EVENT LISTENERS (Sections 3, 4, 5)
# ===========================================================================

@bot.event
async def on_member_join(member: discord.Member):
    try:
        if kazumi_features.get("welcome"):
            await kazumi_features["welcome"].on_member_join(member)
        if kazumi_features.get("autorole"):
            await kazumi_features["autorole"].assign_autoroles(member)

        # Anti-Raid Evaluation
        if kazumi_features.get("anti_raid"):
            is_raid, raid_reason, raid_meta = kazumi_features["anti_raid"].record_join_and_evaluate(member)
            if is_raid:
                raid_embed = discord.Embed(
                    title="🚨 SECURITY ALERT • RAID DETECTED",
                    description=(
                        f"**Threat:** {raid_reason}\n"
                        f"**Trigger Member:** {member.mention} (`{member.id}`)\n"
                        f"**Recent Joins:** `{raid_meta.get('join_count')}`\n"
                        f"**Confidence:** `{raid_meta.get('confidence')}`"
                    ),
                    color=0xef4444
                )
                raid_embed.timestamp = datetime.now(timezone.utc)
                await kazumi_features["logging"].log_event(member.guild, raid_embed)

        # Log event
        embed = discord.Embed(
            title="📥 Member Joined",
            description=f"{member.mention} (`{member.name}` - ID: `{member.id}`)\nAccount created: <t:{int(member.created_at.timestamp())}:R>",
            color=0x10b981
        )
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        embed.set_footer(text=f"Total Members: {member.guild.member_count}")
        embed.timestamp = datetime.now(timezone.utc)
        await kazumi_features["logging"].log_event(member.guild, embed)
    except Exception as e:
        logger.warning(f"Error in on_member_join handler: {e}")


@bot.event
async def on_member_remove(member: discord.Member):
    try:
        if kazumi_features.get("welcome"):
            await kazumi_features["welcome"].on_member_remove(member)
        embed = discord.Embed(
            title="📤 Member Left",
            description=f"**{member.name}** (`{member.id}`) has left the server.",
            color=0xf43f5e
        )
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        embed.set_footer(text=f"Remaining Members: {member.guild.member_count}")
        embed.timestamp = datetime.now(timezone.utc)
        await kazumi_features["logging"].log_event(member.guild, embed)
    except Exception as e:
        logger.warning(f"Error in on_member_remove handler: {e}")


@bot.event
async def on_message_delete(message: discord.Message):
    if not message.guild or message.author.bot:
        return
    try:
        embed = discord.Embed(
            title="🗑️ Message Deleted",
            description=f"**Author:** {message.author.mention} (`{message.author.id}`)\n**Channel:** {message.channel.mention}\n\n**Content:**\n{message.content or '*No text content*'}",
            color=0xef4444
        )
        embed.timestamp = datetime.now(timezone.utc)
        await kazumi_features["logging"].log_event(message.guild, embed)
    except Exception as e:
        logger.warning(f"Error in on_message_delete logging: {e}")


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if not before.guild or before.author.bot:
        return
    if before.content == after.content:
        return
    try:
        embed = discord.Embed(
            title="✏️ Message Edited",
            description=f"**Author:** {before.author.mention} (`{before.author.id}`)\n**Channel:** {before.channel.mention}\n[Jump to Message]({after.jump_url})\n\n**Before:**\n{before.content or '*Empty*'}\n\n**After:**\n{after.content or '*Empty*'}",
            color=0x3b82f6
        )
        embed.timestamp = datetime.now(timezone.utc)
        await kazumi_features["logging"].log_event(before.guild, embed)
    except Exception as e:
        logger.warning(f"Error in on_message_edit logging: {e}")


@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User | discord.Member):
    try:
        embed = discord.Embed(
            title="🔨 Member Banned",
            description=f"**User:** {user.mention} (`{user.name}` - ID: `{user.id}`)",
            color=0xb91c1c
        )
        embed.timestamp = datetime.now(timezone.utc)
        await kazumi_features["logging"].log_event(guild, embed)
    except Exception as e:
        logger.warning(f"Error in on_member_ban logging: {e}")


@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    try:
        embed = discord.Embed(
            title="🕊️ Member Unbanned",
            description=f"**User:** {user.mention} (`{user.name}` - ID: `{user.id}`)",
            color=0x10b981
        )
        embed.timestamp = datetime.now(timezone.utc)
        await kazumi_features["logging"].log_event(guild, embed)
    except Exception as e:
        logger.warning(f"Error in on_member_unban logging: {e}")


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    try:
        # Nickname change
        if before.nick != after.nick:
            embed = discord.Embed(
                title="📝 Nickname Changed",
                description=f"**Member:** {after.mention}\n**Old:** {before.nick or before.name}\n**New:** {after.nick or after.name}",
                color=0x8b5cf6
            )
            embed.timestamp = datetime.now(timezone.utc)
            await kazumi_features["logging"].log_event(after.guild, embed)
        # Role changes
        elif before.roles != after.roles:
            added = [r.mention for r in after.roles if r not in before.roles]
            removed = [r.mention for r in before.roles if r not in after.roles]
            desc = f"**Member:** {after.mention}\n"
            if added:
                desc += f"**Roles Added:** {', '.join(added)}\n"
            if removed:
                desc += f"**Roles Removed:** {', '.join(removed)}"
            embed = discord.Embed(
                title="🎭 Member Roles Updated",
                description=desc,
                color=0x8b5cf6
            )
            embed.timestamp = datetime.now(timezone.utc)
            await kazumi_features["logging"].log_event(after.guild, embed)
    except Exception as e:
        logger.warning(f"Error in on_member_update logging: {e}")


@bot.event
async def on_guild_channel_create(channel: discord.abc.GuildChannel):
    try:
        embed = discord.Embed(
            title="📁 Channel Created",
            description=f"**Channel:** {channel.name} (`{channel.id}`)",
            color=0x10b981
        )
        embed.timestamp = datetime.now(timezone.utc)
        await kazumi_features["logging"].log_event(channel.guild, embed)
    except Exception:
        pass


@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    try:
        embed = discord.Embed(
            title="🗑️ Channel Deleted",
            description=f"**Channel:** #{channel.name} (`{channel.id}`)",
            color=0xef4444
        )
        embed.timestamp = datetime.now(timezone.utc)
        await kazumi_features["logging"].log_event(channel.guild, embed)
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
    author_name = getattr(interaction.user, "display_name", "") or getattr(interaction.user, "name", "")
    author_id_str = str(interaction.user.id)
    creator_title, creator_ctx = detect_creator_relationship(interaction.user)
    display_author = creator_title if creator_title else author_name

    adaptive_directive = None
    if obs_manager:
        try:
            _, _, adaptive_directive = obs_manager.process_message(
                user_id=author_id_str,
                display_name=author_name,
                channel_id=str(interaction.channel_id),
                text=message,
                is_dm=interaction.guild is None,
                is_dedicated=True,
                is_direct_address=True
            )
        except Exception as obs_err:
            logger.warning(f"Error in slash_chat observation: {obs_err}")

    try:
        reply_text = await asyncio.wait_for(ask_kazumi(message, session_id, display_author, creator_ctx, person_directive=adaptive_directive), timeout=35.0)
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
    app_commands.Choice(name="Unhinged (Savage & Ruthless 💀🔥)", value="UNHINGED"),
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
            kazumi_core.memory.profile["archetype"] = archetype.value
            kazumi_core.memory.save_profile()
            if archetype.value == "UNHINGED":
                desc = f"Switched Kazumi's personality style to **{archetype.name}**! 💀🔥 All filters and sweetness are OFF—prepare for ruthless roasts!"
            else:
                desc = f"Switched Kazumi's personality style to **{archetype.name}** for our upcoming chats! 🌸"
        else:
            desc = f"Kazumi's current active personality is **{kazumi_core.current_archetype}**."

    embed = create_kazumi_embed(
        title="🎭 Companion Personality Style",
        description=desc,
        color=0xff3366 if getattr(kazumi_core, "current_archetype", "") == "UNHINGED" else 0xc084fc
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


@bot.tree.command(name="recognize_text", description="Extract and read text from an image, document, or screenshot 🔍")
@app_commands.describe(
    image="Upload an image, photo, screenshot, or document to extract text from",
    query="Optional question or instructions about the text/image"
)
async def slash_recognize_text(interaction: discord.Interaction, image: discord.Attachment, query: Optional[str] = None):
    await interaction.response.defer(thinking=True)
    try:
        rec_engine = get_text_recognition_engine()
        img_bytes = await image.read()
        res = rec_engine.extract_text_from_bytes(
            img_bytes,
            filename=image.filename,
            mime_type=image.content_type or "image/png",
            user_query=query
        )
        if not res.get("success"):
            err_msg = res.get("error", "Unable to process image.")
            await interaction.followup.send(f"🌸 I couldn't read the text from that image: {err_msg}")
            return

        extracted = res.get("text", "").strip()
        if not extracted or not res.get("has_text", True):
            embed = create_kazumi_embed(
                title="🔍 Text Recognition Result",
                description="I examined your image carefully, but I couldn't find any readable text in it! 🌸"
            )
            embed.set_thumbnail(url=image.url)
            await interaction.followup.send(embed=embed)
            return

        char_count = res.get("char_count", len(extracted))
        line_count = len(extracted.splitlines())

        embed = create_kazumi_embed(
            title=f"🔍 Recognized Text: {image.filename}",
            description=f"**Characters:** {char_count} | **Lines:** {line_count}\n\n```\n{extracted[:1800]}\n```"
        )
        embed.set_thumbnail(url=image.url)
        if len(extracted) > 1800:
            embed.set_footer(text=f"Showing first 1,800 characters of {char_count} total characters.")

        await interaction.followup.send(embed=embed)

        # Generate Kazumi's personal thoughts on what she read
        session_id = get_user_session_id(interaction.user)
        prompt_for_kazumi = (
            f"The user uploaded an image containing this text:\n\n{extracted[:1500]}\n\n"
            f"User's question/comment: {query if query else 'What do you think of this text or document?'}"
        )
        commentary = await ask_kazumi(prompt_for_kazumi, session_id)
        if commentary:
            await interaction.followup.send(f"🌸 **Kazumi's Thoughts:**\n{commentary}")

    except Exception as e:
        logger.error(f"Error in slash_recognize_text: {e}", exc_info=True)
        await interaction.followup.send(f"I had a little trouble reading that image: {e} 🌸")


@bot.tree.command(name="ocr", description="Quick shortcut to extract text from an image or screenshot 🔍")
@app_commands.describe(image="Image to extract text from", question="Optional question about the text")
async def slash_ocr(interaction: discord.Interaction, image: discord.Attachment, question: Optional[str] = None):
    await slash_recognize_text(interaction, image, question)


@bot.tree.command(name="emotion", description="Check Kazumi's current human girl emotion and feelings 💕")
async def slash_emotion(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        emo_engine = get_emotion_engine()
        curr_emo = emo_engine.get_current_emotion()
        cue = emo_engine.get_random_cue()

        embed = create_kazumi_embed(
            title=f"{curr_emo['emoji']} Kazumi's Current Emotion: {curr_emo['name']}",
            description=(
                f"*{cue}*\n\n"
                f"**Current Vibe:** {curr_emo['vibe_description']}\n\n"
                f"Kazumi experiences spontaneous human girl emotions during chats—feeling shy, teasing, "
                f"affectionate, pouty, excited, thoughtful, or sleepy depending on the moment! 🌸"
            )
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"Error in slash_emotion: {e}", exc_info=True)
        await interaction.followup.send("I'm feeling cozy and happy to be here with you! 🌸")


@bot.tree.command(name="help", description="How to interact with Kazumi in your server 🌸")
async def slash_help(interaction: discord.Interaction):
    embed = create_kazumi_embed(
        title="🌸 How to Talk with Kazumi",
        description=(
            "Kazumi is an empathetic, caring AI companion bot designed to bring cozy conversations (or savage burns!) to your server!\n\n"
            "**Ways to Chat:**\n"
            "• **Mention her:** Type `@Kazumi Hello!` anywhere in the server.\n"
            "• **Direct Message:** Send a DM directly to Kazumi.\n"
            "• **Slash Command:** Use `/chat <message>`.\n"
            "• **Send Images/Screenshots:** Attach any picture with text and Kazumi will read it!\n\n"
            "**Available Commands:**\n"
            "• `/recognize_text` (or `/ocr`) - Read & extract text from images/screenshots 🔍\n"
            "• `/emotion` - View Kazumi's current human girl emotion & feelings 💕\n"
            "• `/roast [target]` - Deliver an unapologetically savage roast 💀🔥\n"
            "• `/unhinged [True/False]` - Toggle savage unhinged mode 💀🔥\n"
            "• `/persona [archetype]` - Switch between Deredere, Teasing, Kuudere, Tsundere, and Unhinged\n"
            "• `/status` - Check affection score, cozy points, and mood\n"
            "• `/diary` - Read her journal reflections\n"
            "• `/quests` - View active quests and challenges\n"
            "• `/horoscope` - Get your daily astrological reading\n"
            "• `/reset` - Start a fresh conversation session\n"
            "• `/vibe` - Check your conversational vibe and familiarity with Kazumi ✨\n"
            "• `/channel_mode [mode]` - Set channel mode (Active Chat, Observation Only, or Disabled) ⚙️\n"
            "• `/reset_person [user]` - Reset behavioral profile and learned patterns (Privacy) 🔒\n"
            "• `/help` - Show this helpful guide"
        )
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="channel_mode", description="Configure Kazumi's mode in this channel (ACTIVE_CHAT, OBSERVATION_ONLY, or DISABLED)")
@app_commands.describe(mode="Active Chat (talks), Observation Only (reactions only, no text), or Disabled")
@app_commands.choices(mode=[
    app_commands.Choice(name="Active Chat (Replies & talks normally)", value="ACTIVE_CHAT"),
    app_commands.Choice(name="Observation Only (Watches & reacts with emojis, NO text)", value="OBSERVATION_ONLY"),
    app_commands.Choice(name="Disabled (Completely ignores this channel)", value="DISABLED"),
])
async def slash_channel_mode(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    # Permissions check: Require manage_channels or admin in guilds
    if interaction.guild:
        perms = interaction.channel.permissions_for(interaction.user)
        if not (perms.manage_channels or perms.administrator or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("❌ You need the **Manage Channels** or **Administrator** permission to change channel modes.", ephemeral=True)
            return

    if obs_manager:
        obs_manager.set_channel_mode(str(interaction.channel_id), mode.value)
        embed = create_kazumi_embed(
            title="🌸 Channel Mode Updated",
            description=(
                f"This channel (<#{interaction.channel_id}>) has been set to **{mode.name}**!\n\n"
                f"• **Active Chat**: Kazumi speaks and answers conversations normally.\n"
                f"• **Observation Only**: Kazumi observes context and occasionally adds natural emoji reactions (probability & cooldown limited), but **never** sends text messages.\n"
                f"• **Disabled**: Kazumi completely ignores this channel."
            )
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("Observation manager is not initialized.", ephemeral=True)


@bot.tree.command(name="reset_person", description="Reset learned behavior profile (Privacy & Safety)")
@app_commands.describe(user="The user whose profile to reset (defaults to yourself)")
async def slash_reset_person(interaction: discord.Interaction, user: Optional[discord.User] = None):
    target = user or interaction.user
    # If resetting someone else, require manage_guild or admin
    if target.id != interaction.user.id and interaction.guild:
        perms = interaction.channel.permissions_for(interaction.user)
        if not (perms.manage_guild or perms.administrator or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("❌ You can only reset your own profile unless you have **Administrator** or **Manage Server** permissions.", ephemeral=True)
            return

    if obs_manager:
        obs_manager.reset_user(str(target.id))
        embed = create_kazumi_embed(
            title="🌸 Behavioral Profile Reset",
            description=f"The learned behavioral observations and communication profile for **{target.display_name}** have been completely reset.\n\nKazumi will start observing fresh from scratch."
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("Observation manager is not initialized.", ephemeral=True)


@bot.tree.command(name="vibe", description="Check your conversational vibe and familiarity with Kazumi 🌸")
async def slash_vibe(interaction: discord.Interaction):
    if not obs_manager:
        await interaction.response.send_message("Observation manager is not initialized.", ephemeral=True)
        return

    profile = obs_manager.get_profile(str(interaction.user.id), display_name=interaction.user.display_name)
    from person_memory.relationship_manager import RelationshipManager
    rel_title = RelationshipManager.get_relationship_title(profile.relationship_level)

    # Stylistic Vibe
    style = profile.communication_style
    vibes = []
    if style.humor >= 0.5:
        vibes.append("Playful & Witty 😂")
    elif style.formality >= 0.6:
        vibes.append("Thoughtful & Articulate 📜")
    else:
        vibes.append("Casual & Warm 🌸")

    if style.energy >= 0.6:
        vibes.append("High Energy ✨")
    elif style.energy <= 0.3:
        vibes.append("Calm & Chill ☕")

    vibe_str = " • ".join(vibes)

    embed = create_kazumi_embed(
        title=f"🌸 Conversational Harmony • {interaction.user.display_name}",
        description=f"Here is how Kazumi experiences your shared conversational rhythm!"
    )
    embed.add_field(name="Companion Familiarity", value=f"💫 **{rel_title}** (Level {profile.relationship_level}/4)", inline=True)
    embed.add_field(name="Conversational Vibe", value=f"✨ **{vibe_str}**", inline=True)
    embed.add_field(name="Interactions Observed", value=f"💬 **{profile.interaction_count} messages**", inline=True)

    if profile.interests:
        embed.add_field(name="Shared Topics", value=", ".join([f"`{i.title()}`" for i in profile.interests[:4]]), inline=False)

    if profile.behaviour_patterns:
        embed.add_field(name="Observed Rhythm", value="\n".join([f"• {p}" for p in profile.behaviour_patterns[:3]]), inline=False)

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


import subprocess

INSTANCE_LOCK_PORT = 49281
_instance_socket = None
_instance_mutex = None

def acquire_single_instance_lock(timeout: float = 6.0) -> bool:
    """
    Ensures only a single bot process runs locally to prevent gateway session conflicts.
    Uses Windows Named Mutex on Windows (kernel-managed, auto-freed instantly on process termination),
    and a non-blocking TCP socket lock on other platforms, with retry capability during respawn.
    """
    global _instance_socket, _instance_mutex
    start_time = time.time()

    # Windows kernel Named Mutex
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            ERROR_ALREADY_EXISTS = 183

            while True:
                mutex = kernel32.CreateMutexW(None, False, "Global\\KazumiDiscordBotRunningMutex")
                last_err = kernel32.GetLastError()
                if mutex and last_err != ERROR_ALREADY_EXISTS:
                    _instance_mutex = mutex
                    return True
                if mutex:
                    kernel32.CloseHandle(mutex)

                if time.time() - start_time >= timeout:
                    return False
                time.sleep(0.5)
        except Exception as e:
            logger.warning(f"Windows Named Mutex check failed, falling back to socket lock: {e}")

    # Cross-platform socket lock with retry
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", INSTANCE_LOCK_PORT))
            _instance_socket = s
            return True
        except socket.error:
            if time.time() - start_time >= timeout:
                return False
            time.sleep(0.5)


def release_single_instance_lock():
    """Explicitly releases any single-instance mutex or socket lock."""
    global _instance_socket, _instance_mutex
    if _instance_socket:
        try:
            _instance_socket.close()
        except Exception:
            pass
        _instance_socket = None

    if _instance_mutex and sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(_instance_mutex)
        except Exception:
            pass
        _instance_mutex = None


def respawn_process():
    """Cleanly releases lock and respawns the bot process safely across platforms."""
    release_single_instance_lock()
    try:
        if sys.platform == "win32":
            subprocess.Popen([sys.executable] + sys.argv, close_fds=True)
            sys.exit(0)
        else:
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        logger.error(f"Failed to respawn process: {e}")
        time.sleep(5)


def main():
    logger.info(f"[HOST] Runtime Host: {DEPLOY_ENV['name']} (Remote: {DEPLOY_ENV['is_remote']})")
    logger.info(f"[STARTUP] Kazumi Discord Bot process started. DISCORD_BOT_TOKEN configured: {bool(DISCORD_BOT_TOKEN)}")
    if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "your_discord_bot_token_here":
        logger.error("❌ DISCORD_BOT_TOKEN is missing or empty! Bot cannot connect to Discord.")
        print_discord_setup_guide()
        sys.exit(1)

    if not acquire_single_instance_lock(timeout=5.0):
        logger.warning("🌸 Another instance of Kazumi Discord Bot is already running on this machine. Exiting cleanly to avoid duplicate gateway conflicts.")
        sys.exit(0)

    retry_delay = 5
    max_delay = 60

    while True:
        logger.info(f"[STARTUP] Connecting to Discord Gateway (prefix: {PREFIX}, channel: {DISCORD_CHANNEL_ID or 'all'})...")
        try:
            bot.run(DISCORD_BOT_TOKEN, log_handler=None)
            logger.info("[RECONNECT] Discord bot run loop finished. Respawning in 5 seconds...")
            time.sleep(5)
            respawn_process()
        except discord.errors.LoginFailure as lf:
            logger.error(f"❌ Fatal login failure: Invalid Discord Bot Token: {lf}")
            sys.exit(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("[SHUTDOWN] Kazumi Discord Bot stopped by user signal.")
            release_single_instance_lock()
            sys.exit(0)
        except Exception as e:
            logger.error(f"[RECONNECT] Discord connection dropped or failed: {e}. Auto-reconnecting in {retry_delay}s...", exc_info=True)
            time.sleep(retry_delay)
            retry_delay = min(max_delay, int(retry_delay * 1.5))
            respawn_process()


if __name__ == "__main__":
    main()

