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
import json
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

# Persistent storage directory resolution
ISA_MEMORY_DIR = os.environ.get("ISA_MEMORY_DIR") or os.environ.get("DATA_DIR") or os.path.join(ROOT_DIR, "isa_memory")
HEALTH_STATUS_FILE = os.path.join(ISA_MEMORY_DIR, "bot_health.json")
BOT_START_TIME = time.time()
_tree_synced = False
_background_feature_task: Optional[asyncio.Task] = None

def get_git_commit() -> str:
    """Safe build identifier returning current Git commit hash or fallback without secrets."""
    commit = os.environ.get("GIT_COMMIT") or os.environ.get("COMMIT_SHA")
    if commit:
        return commit.strip()
    try:
        import subprocess
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=3
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    try:
        head_path = os.path.join(ROOT_DIR, ".git", "HEAD")
        if os.path.exists(head_path):
            with open(head_path, "r", encoding="utf-8") as f:
                ref = f.read().strip()
            if ref.startswith("ref: "):
                ref_file = os.path.join(ROOT_DIR, ".git", ref[5:].replace("/", os.sep))
                if os.path.exists(ref_file):
                    with open(ref_file, "r", encoding="utf-8") as f:
                        return f.read().strip()
            else:
                return ref
    except Exception:
        pass
    return "unknown"

def write_health_status(status: str, connected: bool = False, extra: Optional[dict] = None):
    """Atomically records bot health telemetry for HTTP monitoring endpoints."""
    try:
        os.makedirs(ISA_MEMORY_DIR, exist_ok=True)
        payload = {
            "status": status,
            "connected": connected,
            "last_heartbeat": time.time(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": DEPLOY_ENV.get("name", "Unknown"),
            "pid": os.getpid(),
            "uptime_seconds": round(time.time() - BOT_START_TIME, 1),
            "commit": get_git_commit()
        }
        if extra:
            payload.update(extra)
        try:
            from openai_reliability import get_reliability_guard
            payload["openai_telemetry"] = get_reliability_guard().get_health_telemetry()
        except Exception:
            pass
        tmp_file = f"{HEALTH_STATUS_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        if os.path.exists(tmp_file):
            if hasattr(os, "replace"):
                os.replace(tmp_file, HEALTH_STATUS_FILE)
            else:
                if os.path.exists(HEALTH_STATUS_FILE):
                    os.remove(HEALTH_STATUS_FILE)
                os.rename(tmp_file, HEALTH_STATUS_FILE)
    except Exception as e:
        logger.warning(f"Failed to write bot health telemetry: {e}")

from discord_features.config import SanitizedLogFormatter, install_global_redactor, register_secret, KazumiConfig
install_global_redactor()

# Import Kazumi Core
try:
    from kazumi import Kazumi, FolderLock
    logger.info("[STARTUP] Initializing Kazumi core cognitive engine...")
    kazumi_core = Kazumi()
    # Ensure pure chat bot mode
    kazumi_core.voice_enabled = False
    logger.info("[STARTUP] Kazumi core engine loaded successfully.")
    try:
        from openai_reliability import get_reliability_guard
        guard = get_reliability_guard()
        if guard.is_valid:
            logger.info(f"[STARTUP] OpenAI Cognitive Engine: {guard.validation_msg}")
        else:
            logger.warning(f"[STARTUP] OpenAI Cognitive Engine: {guard.validation_msg} (Kazumi will utilize rich local personality fallbacks).")
    except Exception as e:
        logger.warning(f"[STARTUP] Could not inspect OpenAI status: {e}")
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
if DISCORD_BOT_TOKEN:
    register_secret(DISCORD_BOT_TOKEN)
DISCORD_CHANNEL_ID = (args.channel or os.environ.get("DISCORD_CHANNEL_ID", "")).strip()
PREFIX = args.prefix or os.environ.get("DISCORD_PREFIX", "!k ")
CREATOR_USER_IDS = set(x.strip() for x in os.environ.get("CREATOR_USER_IDS", "").split(",") if x.strip())
AAMIR_USER_IDS = set(x.strip() for x in os.environ.get("AAMIR_USER_IDS", "").split(",") if x.strip())
SHAN_USER_IDS = set(x.strip() for x in os.environ.get("SHAN_USER_IDS", "1203721997805424650").split(",") if x.strip())

# Bot Intents
intents = discord.Intents.default()
intents.message_content = True  # Required to read message content for chat
intents.members = True          # Required for on_member_join, welcome poems, and autorole

# Enforce IPv4 preference for Discord gateway and external cloud APIs
try:
    import socket
    _orig_getaddrinfo = socket.getaddrinfo
    def _prefer_ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if family == 0 or family == socket.AF_UNSPEC:
            family = socket.AF_INET
        return _orig_getaddrinfo(host, port, family, type, proto, flags)
    socket.getaddrinfo = _prefer_ipv4_getaddrinfo
except Exception:
    pass

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(PREFIX),
    intents=intents,
    help_command=None
)
bot.kazumi_core = kazumi_core

# Ensure bot._connection.user has a safe placeholder so get_context never crashes offline or during tests
try:
    from unittest.mock import MagicMock
    if getattr(bot._connection, "user", None) is None:
        _placeholder_user = MagicMock(id=0, bot=True)
        _placeholder_user.name = "Kazumi"
        _placeholder_user.discriminator = "0000"
        bot._connection.user = _placeholder_user
except Exception:
    pass

@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    """Sanitizes command errors to ensure no secrets or stack traces leak to Discord."""
    logger.error(f"Command error in {getattr(ctx, 'command', 'unknown')}: {error}", exc_info=error)
    try:
        await ctx.send("🌸 An unexpected error occurred while processing this command. The issue has been safely logged.")
    except Exception:
        pass

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Sanitizes slash command errors to ensure no secrets or stack traces leak to Discord."""
    logger.error(f"Slash command error in {getattr(interaction, 'command', 'unknown')}: {error}", exc_info=error)
    try:
        msg = "🌸 An unexpected error occurred while executing this command. The issue has been safely logged."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Cloud Deployment Health Check Server (Hugging Face Spaces / Render / VPS)
# ---------------------------------------------------------------------------
import http.server
import threading
import json

class CloudHealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        is_conn = False
        try:
            if "bot" in globals() and bot and bot.is_ready():
                is_conn = True
        except Exception:
            pass

        # Retrieve monitoring health state if available
        health_data = {}
        try:
            if "kazumi_features" in globals() and kazumi_features and kazumi_features.get("monitoring"):
                health_data = kazumi_features["monitoring"].get_health_status()
        except Exception:
            pass

        is_ready = bool(is_conn and health_data.get("readiness", is_conn))
        overall_status = "healthy" if is_ready else ("degraded" if is_conn else ("starting" if DISCORD_BOT_TOKEN else "offline"))
        path_clean = getattr(self, "path", "/").split("?")[0]
        if path_clean in ("/version", "/commit", "/build"):
            payload = {
                "status": overall_status,
                "commit": get_git_commit(),
                "version": "2.4.0",
                "uptime_seconds": round(time.time() - BOT_START_TIME, 1)
            }
            self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))
            return

        payload = {
            "status": overall_status,
            "liveness": health_data.get("liveness", True),
            "readiness": is_ready,
            "uptime_seconds": round(time.time() - BOT_START_TIME, 1)
        }
        self.wfile.write(json.dumps(payload, indent=2).encode("utf-8"))

    def log_message(self, format, *args):
        # Suppress routine health check polling noise from cloud probes
        pass

def start_cloud_health_servers():
    ports_to_bind = []
    for var in ("PORT", "SERVER_PORT"):
        val = os.environ.get(var)
        if val:
            try:
                p = int(val.strip())
                if p not in ports_to_bind:
                    ports_to_bind.append(p)
            except ValueError:
                pass
    for p in (7860, 10000):
        if p not in ports_to_bind:
            ports_to_bind.append(p)

    for p in ports_to_bind:
        try:
            server = http.server.ThreadingHTTPServer(("0.0.0.0", p), CloudHealthCheckHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True, name=f"HealthCheck-{p}")
            thread.start()
            logger.info(f"[HEALTH] Multi-cloud HTTP health server active on 0.0.0.0:{p}")
        except Exception as e:
            logger.warning(f"[HEALTH] Port {p} could not be bound (may already be in use): {e}")

start_cloud_health_servers()

async def setup_health_server():
    """Compatibility hook for discord.py setup_hook and remote startup loop."""
    pass

bot.setup_hook = setup_health_server

# Initialize Kazumi Advanced Feature Suite (Moderation, Logging, Tickets, Giveaways, Music, etc.)
import discord_features
kazumi_features = discord_features.setup_all_features(bot, bot.tree)

# Central Channel Policy Gatekeeper for Slash Commands (Phase 3)
async def global_channel_policy_check(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not interaction.channel:
        return True

    cmd_name = interaction.command.name if interaction.command else ""
    channel_policy_mgr = kazumi_features.get("channel_policy")
    if not channel_policy_mgr:
        return True

    from discord_features.channel_policy import ChannelPolicyType, FeatureGroup
    policy = channel_policy_mgr.get_policy_for_channel(interaction.channel, interaction.guild.id)

    # Allow staging and testing commands in dedicated #bot-testing channel
    is_testing_channel = "testing" in getattr(interaction.channel, "name", "").lower()
    if is_testing_channel and (policy.is_staff_only or interaction.user.guild_permissions.manage_guild):
        return True

    # 1. Read-only channels block all interactive slash commands
    if policy.name == ChannelPolicyType.READ_ONLY:
        await interaction.response.send_message("❌ This channel is read-only. Commands cannot be run here.", ephemeral=True)
        return False

    # 2. Staff management commands
    staff_cmds = {"automod", "logging", "security", "case", "cases", "modnote", "modnotes", "modhistory", "modqueue", "quarantine", "unquarantine", "raidmode", "channel_policy"}
    if cmd_name in staff_cmds:
        if not policy.is_staff_only and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Staff management commands can only be executed in private staff channels.", ephemeral=True)
            return False

    # 3. Game commands
    game_cmds = {"game", "dailygame", "arcade", "trivia", "tictactoe", "connect4", "hangman", "wordchain", "wouldyourather", "reactionrace", "arena", "dailyanswer"}
    if cmd_name in game_cmds:
        if not policy.is_feature_allowed(FeatureGroup.GAMES) and not is_testing_channel:
            await interaction.response.send_message("❌ Game commands are only allowed in #kazumi-games or #bot-testing! 🎮", ephemeral=True)
            return False

    # 4. Music commands
    music_cmds = {"play", "pause", "resume", "skip", "stop", "queue", "nowplaying", "shuffle", "loop", "volume", "clearqueue", "previous", "lyrics", "disconnect", "seek", "remove", "join", "leave", "musicstatus"}
    if cmd_name in music_cmds:
        if not policy.is_feature_allowed(FeatureGroup.MUSIC) and not is_testing_channel:
            await interaction.response.send_message("❌ Music commands are only allowed in #music-commands or #bot-testing! 🎶", ephemeral=True)
            return False

    # 5. Giveaway commands
    if cmd_name == "giveaway":
        if not policy.is_feature_allowed(FeatureGroup.GIVEAWAYS) and not policy.is_staff_only and not is_testing_channel:
            await interaction.response.send_message("❌ Giveaways are only allowed in #giveaways or staff channels! 🎉", ephemeral=True)
            return False

    return True

bot.tree.interaction_check = global_channel_policy_check

# Active conversational sessions: (channel_id, user_id) -> last_active_timestamp
from discord_features.conversation_context import get_conversation_manager
convo_manager = get_conversation_manager()
from kazumi_emotions import get_emotional_analyzer
emotional_analyzer = get_emotional_analyzer()

active_conversations = {}
CONVERSATION_TIMEOUT_SECONDS = 180  # Stays attentive for 180 seconds for natural multi-turn conversation

import collections
# Cache of recent message IDs sent by Kazumi to accurately detect replies
recent_bot_message_ids = set()
_processed_message_ids_lock = asyncio.Lock()
_processed_message_ids_set: set[int] = set()
_processed_message_ids_deque: collections.deque[int] = collections.deque(maxlen=3000)
_processed_message_ids = _processed_message_ids_set

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
    """Returns True if the channel is permitted for Kazumi conversations under Central Channel Policy."""
    if isinstance(channel, discord.DMChannel):
        return True
    if DISCORD_CHANNEL_ID and str(getattr(channel, "id", 0)) == str(DISCORD_CHANNEL_ID):
        return True
    mgr = kazumi_features.get("channel_policy") if 'kazumi_features' in globals() else None
    if mgr:
        gid = channel.guild.id if hasattr(channel, "guild") and channel.guild else None
        policy = mgr.get_policy_for_channel(channel, gid)
        return policy.allow_ai_chat
    ch_name = getattr(channel, "name", "").lower()
    return "kazumi-chat" in ch_name or ("kazumi" in ch_name and "command" not in ch_name and "log" not in ch_name)


def find_kazumi_channel_in_guild(guild: Optional[discord.Guild]) -> Optional[discord.TextChannel]:
    """Finds a dedicated Kazumi channel in the guild if one exists."""
    if not guild or not hasattr(guild, "text_channels"):
        return None
    for ch in guild.text_channels:
        if "kazumi-chat" in ch.name.lower():
            return ch
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
    Identifies whether the Discord user is one of Kazumi's verified creators and fathers.
    Uses stable Discord user IDs first, with exact name matching as a secondary check.
    """
    uid_str = str(getattr(user, "id", "")).strip()

    # 1. Primary verification: stable Discord user IDs
    if uid_str in AAMIR_USER_IDS:
        return ("Aamir the Chad", "Aamir the Chad (your creator and father)")
    if uid_str in SHAN_USER_IDS:
        return ("Sir Shan D. First", "Sir Shan D. First (your creator and father)")
    if uid_str in CREATOR_USER_IDS:
        return ("Creator", "Creator and Father")

    # 2. Secondary verification: exact full creator handles / names
    raw_names = {
        getattr(user, "name", "").lower(),
        getattr(user, "display_name", "").lower(),
        getattr(user, "global_name", "").lower()
    } - {""}

    exact_aamir_matches = {"aamir the chad", "aamir", "amir_the_chad"}
    exact_shan_matches = {"shan2157", "sir shan", "sir shan d. first", "sir shan d first", "shan d. first", "shan d first"}

    if any(n in exact_aamir_matches for n in raw_names):
        return ("Aamir the Chad", "Aamir the Chad (your creator and father)")
    if any(n in exact_shan_matches for n in raw_names):
        return ("Sir Shan D. First", "Sir Shan D. First (your creator and father)")

    return (None, None)


def sync_kazumi_reply(
    text: str,
    session_id: str,
    user_name: Optional[str] = None,
    creator_identity: Optional[str] = None,
    person_directive: Optional[str] = None,
    archetype: Optional[str] = None,
    is_roast: bool = False
) -> str:
    """Thread-safe scoped call to Kazumi's sync reply function."""
    if not kazumi_core:
        return "I'm having a little trouble connecting to my thoughts right now. Please try again in a moment! 🌸"
    with kazumi_lock:
        prev_creator = getattr(kazumi_core, "creator_context", None)
        prev_directive = getattr(kazumi_core, "person_directive", None)
        prev_user_name = getattr(kazumi_core, "current_user_name", None)
        prev_archetype = getattr(kazumi_core, "current_archetype", "DEREDERE")
        prev_roast_mode = getattr(kazumi_core, "roast_mode", False)
        prev_roast_intensity = getattr(kazumi_core, "roast_intensity", 1)
        prev_roast_style = getattr(kazumi_core, "roast_style", "CASUAL")

        try:
            kazumi_core.creator_context = creator_identity
            kazumi_core.person_directive = person_directive
            kazumi_core.current_user_name = user_name

            if is_roast:
                kazumi_core.roast_mode = True
                kazumi_core.roast_intensity = 4
                kazumi_core.roast_style = "UNHINGED"
                kazumi_core.current_archetype = "UNHINGED"
            elif archetype:
                kazumi_core.current_archetype = archetype
                kazumi_core.roast_mode = False

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

            res = kazumi_core.reply(text, session_id=session_id)
            return res if res else "I'm right here with you! 🌸 (Kazumi smiles warmly.)"
        finally:
            kazumi_core.creator_context = prev_creator
            kazumi_core.person_directive = prev_directive
            kazumi_core.current_user_name = prev_user_name
            kazumi_core.current_archetype = prev_archetype
            kazumi_core.roast_mode = prev_roast_mode
            kazumi_core.roast_intensity = prev_roast_intensity
            kazumi_core.roast_style = prev_roast_style


async def ask_kazumi(
    text: str,
    session_id: str,
    user_name: Optional[str] = None,
    creator_identity: Optional[str] = None,
    person_directive: Optional[str] = None,
    archetype: Optional[str] = None,
    is_roast: bool = False
) -> str:
    """Non-blocking asynchronous wrapper over Kazumi's core reply."""
    try:
        # If archetype is not explicitly provided, look up from user session
        if archetype is None and kazumi_core and hasattr(kazumi_core, "memory") and hasattr(kazumi_core.memory, "profile"):
            with kazumi_lock:
                s_state = kazumi_core.memory.profile.get("session_game_states", {}).get(session_id, {})
                archetype = s_state.get("archetype")

        reply = await asyncio.to_thread(
            sync_kazumi_reply,
            text,
            session_id,
            user_name,
            creator_identity,
            person_directive,
            archetype,
            is_roast
        )
        return (reply or "").strip() or "I'm right here with you! 🌸"
    except Exception as e:
        logger.error(f"Error in ask_kazumi wrapper: {e}", exc_info=True)
        return "I'm right here with you! 🌸 (Kazumi nods softly.) How are you feeling today?"


async def send_kazumi_response(message: discord.Message, text: str) -> bool:
    """Reliably delivers messages to the user/channel with automatic fallback."""
    text = (text or "").strip()
    if not text:
        text = "I'm right here with you! 🌸 (Kazumi smiles warmly.)"
    chunks = split_message(text)
    any_sent = False
    first_sent_msg = None
    for idx, chunk in enumerate(chunks):
        sent_msg = None
        if idx == 0:
            try:
                sent_msg = await message.reply(chunk, mention_author=False)
                any_sent = True
                first_sent_msg = sent_msg
            except Exception:
                try:
                    sent_msg = await message.channel.send(chunk)
                    any_sent = True
                    first_sent_msg = sent_msg
                except Exception as send_err:
                    logger.error(f"Failed to send reply chunk: {send_err}")
        else:
            try:
                sent_msg = await message.channel.send(chunk)
                any_sent = True
            except Exception as send_err:
                logger.error(f"Failed to send followup chunk: {send_err}")

        if sent_msg and hasattr(sent_msg, "id"):
            recent_bot_message_ids.add(sent_msg.id)
            if len(recent_bot_message_ids) > 1000:
                try:
                    recent_bot_message_ids.pop()
                except Exception:
                    pass

    # Record bot response in conversation context manager for natural multi-turn tracking
    if any_sent and convo_manager:
        try:
            bot_msg_id = first_sent_msg.id if first_sent_msg and hasattr(first_sent_msg, "id") else None
            convo_manager.record_kazumi_response(message, text, bot_msg_id)
        except Exception as ctx_err:
            logger.debug(f"Error recording response in convo_manager: {ctx_err}")

    return any_sent


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
async def on_connect():
    logger.info("[CONNECTION] Discord Gateway connection established.")
    if "kazumi_features" in globals() and kazumi_features and kazumi_features.get("monitoring"):
        kazumi_features["monitoring"].record_connect()


@bot.event
async def on_disconnect():
    logger.info("[CONNECTION] Discord Gateway disconnected. Automatic reconnection managed by discord.py...")
    if "kazumi_features" in globals() and kazumi_features and kazumi_features.get("monitoring"):
        kazumi_features["monitoring"].record_disconnect()


@bot.event
async def on_resumed():
    logger.info("[CONNECTION] Discord Gateway session successfully resumed.")
    if "kazumi_features" in globals() and kazumi_features and kazumi_features.get("monitoring"):
        kazumi_features["monitoring"].record_resume()


@bot.event
async def on_error(event_method, *args, **kwargs):
    logger.error(f"[EVENT_ERROR] Unhandled exception in event handler '{event_method}'", exc_info=sys.exc_info())


@bot.event
async def on_ready():
    global _tree_synced, _background_feature_task
    bot_name = bot.user.name if bot.user else "Kazumi"
    bot_disc = bot.user.discriminator if bot.user else "0000"
    bot_id = bot.user.id if bot.user else 0
    logger.info(f"[CONNECTION] Discord Gateway connected as {bot_name}#{bot_disc} (ID: {bot_id})")
    logger.info(f"[CONNECTION] Connected to {len(bot.guilds) if getattr(bot, 'guilds', None) else 0} server(s).")
    logger.info(f"[BUILD] Kazumi active build commit: {get_git_commit()}")

    # Clear rapid startup failure history after healthy gateway connection
    try:
        from restart_protector import RestartLoopProtector
        state_file = os.path.join(ISA_MEMORY_DIR, ".crash_loop_state.json")
        RestartLoopProtector(state_file=state_file).record_healthy()
    except Exception:
        pass

    # Record Gateway Ready & Launch Background Health Monitor Loop (initial startup only)
    if "kazumi_features" in globals() and kazumi_features and kazumi_features.get("monitoring"):
        kazumi_features["monitoring"].record_ready()
        if not _tree_synced and (kazumi_features["monitoring"].monitoring_task is None or kazumi_features["monitoring"].monitoring_task.done()):
            try:
                await kazumi_features["monitoring"].start_background_monitor()
            except Exception as mon_err:
                logger.warning(f"Failed to start monitoring task: {mon_err}")
    
    # Set status presence
    if bot.user:
        try:
            activity = discord.Activity(
                type=discord.ActivityType.listening,
                name="@Kazumi or /chat 🌸"
            )
            await bot.change_presence(status=discord.Status.online, activity=activity)
        except Exception as pres_err:
            logger.debug(f"Presence update error: {pres_err}")

    # Sync Slash Application Commands (only once on startup to prevent Discord rate limits)
    if not _tree_synced:
        try:
            guild_id_str = os.environ.get("TEST_GUILD_ID") or os.environ.get("DISCORD_GUILD_ID")
            if guild_id_str:
                try:
                    guild_obj = discord.Object(id=int(guild_id_str))
                    bot.tree.copy_global_to(guild=guild_obj)
                    synced_guild = await bot.tree.sync(guild=guild_obj)
                    logger.info(f"[STARTUP] Instantly synced {len(synced_guild)} slash command(s) to test guild {guild_id_str}.")
                except Exception as g_err:
                    logger.warning(f"Guild-specific slash command sync failed: {g_err}")

            # Ensure LAPEACE has dedicated guild commands (including /join, /leave, /musicstatus) synced
            target_guild_id = 1554152397327044729
            try:
                discord_features.music.setup_music_commands(bot.tree, bot, guild_id=target_guild_id)
                synced_guild_cmds = await bot.tree.sync(guild=discord.Object(id=target_guild_id))
                target_g = bot.get_guild(target_guild_id)
                target_name = target_g.name if target_g else "LAPEACE"
                logger.info(f"[STARTUP] Synced {len(synced_guild_cmds)} guild command(s) to {target_name} ({target_guild_id}).")
            except Exception as g_err:
                logger.warning(f"Target guild slash command sync failed: {g_err}")

            synced = await bot.tree.sync()
            logger.info(f"[STARTUP] Globally synced {len(synced)} slash command(s).")
            _tree_synced = True
        except Exception as e:
            logger.warning(f"Slash command sync failed: {e}")

    # Launch Kazumi background feature task (Giveaways, Reminders, Server Moments) - singleton guard
    if _background_feature_task is None or _background_feature_task.done():
        _background_feature_task = asyncio.create_task(kazumi_background_feature_loop())

    write_health_status(
        "online",
        connected=True,
        extra={
            "bot_user": str(bot.user),
            "guilds": len(bot.guilds),
            "latency_ms": round(bot.latency * 1000, 1) if bot.latency else 0.0,
            "prefix": PREFIX
        }
    )

    print("\n" + "=" * 60)
    print("🌸 KAZUMI DISCORD BOT IS READY AND LISTENING!")
    print(f"Host: {DEPLOY_ENV['name']}")
    print(f"Bot Tag: {bot.user}")
    print("Mention Kazumi in any server channel or use /chat to speak!")
    print("=" * 60 + "\n")


@bot.event
async def on_disconnect():
    logger.warning("[RECONNECT] Discord Gateway connection dropped. Retrying automatically...")
    if "kazumi_features" in globals() and kazumi_features and kazumi_features.get("monitoring"):
        kazumi_features["monitoring"].record_disconnect()
    write_health_status("disconnected", connected=False, extra={"warning": "Gateway connection dropped"})


@bot.event
async def on_resumed():
    logger.info("[RECOVERY] Discord Gateway session successfully resumed! Kazumi is back listening.")
    if "kazumi_features" in globals() and kazumi_features and kazumi_features.get("monitoring"):
        kazumi_features["monitoring"].record_resumed()
    write_health_status(
        "online",
        connected=True,
        extra={
            "latency_ms": round(bot.latency * 1000, 1) if bot.latency else 0.0,
            "resumed": True
        }
    )


@bot.event
async def on_interaction(interaction: discord.Interaction):
    """Global interaction dispatcher ensuring persistent button handling across restarts."""
    if interaction.type == discord.InteractionType.component:
        custom_id = str(getattr(interaction, "data", {}).get("custom_id", ""))
        if custom_id.startswith("kazumi:role:"):
            from discord_features.reaction_roles import handle_role_toggle_interaction
            await handle_role_toggle_interaction(interaction)
            if "kazumi_features" in globals() and kazumi_features and kazumi_features.get("monitoring"):
                kazumi_features["monitoring"].record_api_interaction()


@bot.event
async def on_message_delete(message: discord.Message):
    """Unified Message Deletion Handler: Observational Roasting & Server Audit Logging."""
    if not message or not message.author or message.author.bot:
        return

    # 1. Observational Roasting: Catch quick message deletes (Section 5)
    send_time = recent_messages_for_delete_observation.pop(message.id, None)
    if send_time and (time.time() - send_time <= 12.0):
        if is_kazumi_channel(message.channel) or isinstance(message.channel, discord.DMChannel):
            db_inst = kazumi_features.get("db") if kazumi_features else None
            if db_inst and not db_inst.is_user_roast_opted_out(message.author.id):
                if random.random() < 0.40:
                    try:
                        await message.channel.send("too late. the digital crime scene has been secured. 📸💀")
                    except Exception:
                        pass

    # 2. Server Audit Logging
    if message.guild and kazumi_features and kazumi_features.get("logging"):
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
async def on_message(message: discord.Message):
    # Ignore self and other bots
    if message.author.bot or (bot.user and message.author.id == bot.user.id):
        return

    # Deduplication Guard: atomic, thread-safe, bounded FIFO deduplication
    async with _processed_message_ids_lock:
        if message.id in _processed_message_ids_set:
            logger.debug(f"[DEDUP] Dropping duplicate message delivery: {message.id}")
            return
        _processed_message_ids_set.add(message.id)
        if len(_processed_message_ids_deque) == _processed_message_ids_deque.maxlen:
            evicted = _processed_message_ids_deque.popleft()
            _processed_message_ids_set.discard(evicted)
        _processed_message_ids_deque.append(message.id)

    correlation_id = f"msg_{message.id}"
    start_time = time.time()

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
    # 0A. MULTILINGUAL AUTOMOD & MEDIA SAFETY (PHASES 3 & 4)
    # =========================================================================
    if message.guild:
        is_staff = False
        if hasattr(message.author, "guild_permissions"):
            is_staff = message.author.guild_permissions.manage_messages or message.author.guild_permissions.administrator

        # 1. Media Safety Moderation (Images, Videos, GIFs, External Links, SSRF)
        media_mod = kazumi_features.get("media_moderator")
        if media_mod and not is_staff:
            is_media_violation, media_reason, media_conf = await media_mod.evaluate_message_media(message)
            if is_media_violation:
                await media_mod.handle_media_violation(message, media_reason, media_conf)
                if kazumi_features.get("logging"):
                    log_embed = discord.Embed(
                        title="🛡️ Media AutoMod Enforced",
                        description=f"**User:** {message.author.mention} (`{message.author.id}`)\n**Reason:** `{media_reason}`\n**Channel:** {message.channel.mention}",
                        color=0xf43f5e
                    )
                    log_embed.timestamp = datetime.now(timezone.utc)
                    await kazumi_features["logging"].log_event(message.guild, log_embed)
                return

        # 2. Advanced Multilingual AutoMod (English, Hindi, Hinglish, Odia, Slang)
        multi_automod = kazumi_features.get("multilingual_automod")
        if multi_automod and not is_staff:
            violated, cat, sample, severity = multi_automod.evaluate_message(raw_content)
            if violated:
                mod_res = await multi_automod.handle_violation(message, cat, severity, sample)
                if kazumi_features.get("logging"):
                    case_id = mod_res.get("case_id", 0)
                    log_embed = discord.Embed(
                        title=f"🛡️ Multilingual AutoMod Enforced • Case #{case_id}",
                        description=f"**User:** {message.author.mention} (`{message.author.id}`)\n**Category:** `{cat}`\n**Severity:** `{severity.value}`\n**Channel:** {message.channel.mention}",
                        color=0xf43f5e
                    )
                    log_embed.timestamp = datetime.now(timezone.utc)
                    await kazumi_features["logging"].log_event(message.guild, log_embed)
                return

        # 3. Standard AutoMod Tracker (Invites, Mention Limits, Anti-Spam)
        automod_tracker = kazumi_features.get("automod")
        db_inst = kazumi_features.get("db")
        if automod_tracker and db_inst and not is_staff:
            g_settings = db_inst.get_guild_settings(str(message.guild.id))
            automod_cfg = g_settings.get("automod", {})
            if automod_cfg.get("enabled", False):
                violated, rule_name, evidence = automod_tracker.record_and_evaluate(message, automod_cfg)
                if violated:
                    case_id = db_inst.create_case(message.guild.id, message.author.id, bot.user.id if bot.user else 0, "AUTOMOD", rule_name, evidence=evidence)
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    # Private DM warning to respect privacy without public embarrassment
                    try:
                        await message.author.send(
                            f"Hey, please keep the chat respectful. 🌸 Your message in **{message.guild.name}** violated the rule `{rule_name}` and was removed. Let's keep the server welcoming for everyone."
                        )
                    except Exception:
                        pass
                    if kazumi_features.get("logging"):
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
                    return

    # =========================================================================
    # 0A-2. PERSISTENT SERVER LEVELING & CHAT ACTIVITY (PHASE 5)
    # =========================================================================
    if message.guild and kazumi_features.get("leveling"):
        try:
            level_res = await kazumi_features["leveling"].process_message_activity(message)
            if level_res:
                new_lvl, reward_role_id = level_res
                cfg = kazumi_features["leveling"].get_guild_config(message.guild.id)
                target_ch_id = cfg.get("announcement_channel_id")
                ann_ch = message.guild.get_channel(int(target_ch_id)) if target_ch_id else message.channel
                congrats_text = f"Hey, congrats {message.author.mention}! You've reached **Level {new_lvl}**. Keep hanging out with us! 🌸"
                try:
                    await ann_ch.send(congrats_text)
                except Exception:
                    pass
        except Exception as lvl_err:
            logger.debug(f"Error in leveling tracker: {lvl_err}")

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
    # 0D. CENTRAL COMMAND DISPATCHER (PHASE 2)
    # Commands must be recognized and processed BEFORE Channel Policy AI blocks
    # or Human Interaction silence suppresses them!
    # =========================================================================
    ctx = None
    try:
        ctx = await bot.get_context(message)
    except Exception as ctx_err:
        logger.debug(f"[{correlation_id}] Failed to get context: {ctx_err}")

    if ctx and ctx.valid:
        logger.info(f"[{correlation_id}] ⚡ [COMMAND] Dispatching prefix command '{ctx.command.name}' for {message.author}")
        try:
            await bot.invoke(ctx)
        except Exception as cmd_err:
            logger.error(f"[{correlation_id}] Error executing command '{ctx.command.name}': {cmd_err}", exc_info=True)
            await message.channel.send(f"⚠️ Error executing command: {cmd_err}")
        # Always return: A recognized command NEVER falls through to AI conversation!
        return

    # Check explicit prefix command attempt:
    if is_prefix_called:
        clean_pfx = re.sub(r"^\s*!(?:k|kazumi)\b[:,]?", "", raw_content, flags=re.IGNORECASE)
        clean_pfx = re.sub(r"^\s*k!\b[:,]?", "", clean_pfx, flags=re.IGNORECASE)
        if prefix_clean:
            clean_pfx = re.sub(r"^\s*" + re.escape(prefix_clean) + r"\b[:,]?", "", clean_pfx, flags=re.IGNORECASE)
        clean_pfx = clean_pfx.strip()
        tokens = clean_pfx.split()
        if tokens:
            cmd_token = tokens[0].lower()
            cmd_candidate = bot.get_command(cmd_token)
            if cmd_candidate:
                message.content = f"{PREFIX}{cmd_token} {' '.join(tokens[1:])}"
                try:
                    new_ctx = await bot.get_context(message)
                    if new_ctx and new_ctx.valid:
                        logger.info(f"[{correlation_id}] ⚡ [COMMAND] Dispatching resolved command '{cmd_candidate.name}' for {message.author}")
                        await bot.invoke(new_ctx)
                        return
                except Exception as invoke_err:
                    logger.debug(f"[{correlation_id}] Error invoking resolved command: {invoke_err}")
            elif len(tokens) == 1 and not re.search(r"[?!.,]", cmd_token) and cmd_token not in CHAT_REACTIONS_AND_SLANG and cmd_token not in {"hi", "hello", "hey", "sup", "yo", "gm", "gn", "bye", "cya", "morning", "night", "hola"}:
                # Explicit command keyword attempted that does not exist
                await message.channel.send(f"I don't recognize the command `!k {cmd_token}`. Type `!k help` or `/help` to see everything I can do! 🌸")
                return

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

    # =========================================================================
    # 🌸 CENTRAL CHANNEL POLICY GATEKEEPER & ENFORCEMENT (PHASE 3)
    # =========================================================================
    channel_policy_mgr = kazumi_features.get("channel_policy")
    current_policy = None
    if channel_policy_mgr:
        gid = message.guild.id if message.guild else None
        current_policy = channel_policy_mgr.get_policy_for_channel(channel, gid)

    if current_policy:
        from discord_features.channel_policy import ChannelPolicyType

        # 1. READ_ONLY (#rules) — completely silent
        if current_policy.name == ChannelPolicyType.READ_ONLY:
            return

        # 2. STAFF_ONLY (#staff-chat, #mod-logs, #kazumi-logs, #bot-testing)
        if current_policy.is_staff_only:
            is_staff = False
            if hasattr(message.author, "guild_permissions"):
                perms = message.author.guild_permissions
                is_staff = perms.administrator or perms.manage_guild or perms.manage_messages
            if not is_staff:
                return

        # 3. OBSERVATION_ONLY (#general)
        if current_policy.name == ChannelPolicyType.OBSERVATION_ONLY:
            if react_emoji and current_policy.allow_reactions:
                try:
                    await message.add_reaction(react_emoji)
                except Exception:
                    pass

            if is_addressed:
                clean_inquiry = raw_content
                if bot.user:
                    clean_inquiry = re.sub(rf"<@!?{bot.user.id}>", "", clean_inquiry)
                clean_inquiry = re.sub(r"^\s*@?(?:kazumi|kasumi|zumi|kazzy)\b", "", clean_inquiry, flags=re.IGNORECASE).strip()
                # If it's a bare ping without any content, send polite redirect
                if not clean_inquiry:
                    gid_val = message.guild.id if message.guild else 0
                    if channel_policy_mgr.should_redirect_mention(gid_val, channel.id, message.author.id):
                        redirect_msg = channel_policy_mgr.get_mention_redirect_message(message.guild)
                        try:
                            await message.reply(redirect_msg, mention_author=False)
                        except Exception:
                            try:
                                await message.channel.send(redirect_msg)
                            except Exception:
                                pass
                    return
                # If addressed with an action request, question, or greeting, proceed to natural single response
            else:
                return

        # 4. Other Non-AI-Chat Channels (#welcome, #announcements, #server-guide, #roles, #games, #giveaways, #music-commands)
        if not current_policy.allow_ai_chat and not is_dm:
            if react_emoji and current_policy.allow_reactions:
                try:
                    await message.add_reaction(react_emoji)
                except Exception:
                    pass
            # Never send normal conversational AI text in these channels
            return

    # Fallback Mode 2: Legacy OBSERVATION_ONLY
    if channel_mode == "OBSERVATION_ONLY":
        if react_emoji:
            try:
                await message.add_reaction(react_emoji)
            except Exception:
                pass
        return

    # =========================================================================
    # 🧠 RULE 2: CONVERSATIONAL INTELLIGENCE & HUMAN INTERACTION DECISION LAYER
    # =========================================================================
    session_key = (message.channel.id, message.author.id)

    # A. Check for STOP / SILENCE command
    if is_stop_command(raw_content):
        active_conversations.pop(session_key, None)
        if convo_manager:
            try:
                convo_manager.close_session(message)
            except Exception:
                pass
        if is_mentioned or is_reply_to_kazumi:
            try:
                await message.reply(
                    "(Kazumi nods softly and goes quiet) 🌸 Understood! I'll stay quiet. Just mention me or say my name when you'd like to chat again!",
                    mention_author=False
                )
            except Exception:
                pass
        return

    # Check conversation continuity (Phase 2: Natural Conversation Without Repeated Pings)
    is_continuation = False
    cont_reason = ""
    convo_ctx = None
    if convo_manager:
        try:
            is_continuation, cont_reason, convo_ctx = convo_manager.is_continuation(
                message, timeout_seconds=CONVERSATION_TIMEOUT_SECONDS
            )
        except Exception as c_err:
            logger.debug(f"Error checking convo continuation: {c_err}")

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
            relationship_level=rel_level,
            is_continuation=is_continuation,
            continuation_reason=cont_reason
        )
        if hi_decision.value in ("IGNORE", "OBSERVE", "WAIT"):
            return
        elif hi_decision.value == "REACT" and hi_extra:
            try:
                await message.add_reaction(hi_extra)
            except Exception:
                pass
            return

    # B. Check ongoing conversational session with THIS specific user
    now = time.time()
    is_active_convo = False
    if session_key in active_conversations:
        if now - active_conversations[session_key] <= CONVERSATION_TIMEOUT_SECONDS:
            is_active_convo = True
        else:
            active_conversations.pop(session_key, None)

    # Filter chat slang, laughter, and short reaction noise (unless actively continuing or conversing with Kazumi)
    norm_reaction = re.sub(r"[^\w\s]", "", raw_content).lower().strip()
    if norm_reaction in CHAT_REACTIONS_AND_SLANG and not is_mentioned and not is_prefix_called and not is_continuation and not is_active_convo:
        # User is just reacting/laughing in chat (e.g. LAWL, haha, bruh) without active conversation
        if is_active_convo or is_continuation:
            try:
                if norm_reaction in {"lol", "lmao", "lmfao", "lawl", "haha", "hahaha", "xd", "rofl"}:
                    await message.add_reaction("😂")
                elif norm_reaction in {"die", "u die", "abe u die"}:
                    await message.add_reaction("👀")
            except Exception:
                pass
        return

    # D. Ignore other bot commands (e.g. !play, ?ban, /skip, $price, -p)
    is_other_bot_cmd = False
    if raw_content and raw_content[0] in "!?.$-/" and not is_prefix_called:
        if len(raw_content) > 1 and (raw_content[1].isalpha() or raw_content[1] in "!?.$-/"):
            is_other_bot_cmd = True

    # E. If user explicitly tags someone else (and not Kazumi), they are talking to that other person
    is_talking_to_other = bool(message.mentions) and not is_user_mentioned

    # Evaluate intelligent response conditions:
    # 1. In DMs: Respond naturally to ongoing conversation.
    # 2. In Server Channels: Respond when summoned, replied to, prefix called, OR continuing an active conversation.
    # 3. Yield to silence when user is conversing with someone else or executing external bot commands.
    if is_dm:
        should_respond = not is_other_bot_cmd
    elif is_mentioned or is_reply_to_kazumi or is_prefix_called or is_directly_addressed:
        should_respond = True
    elif (is_continuation or is_active_convo) and not is_talking_to_other and not is_other_bot_cmd:
        should_respond = True
    else:
        should_respond = False

    if not should_respond:
        return

    # Record user message in conversation context manager
    if convo_manager:
        try:
            convo_ctx = convo_manager.record_user_message(message)
        except Exception as rec_err:
            logger.debug(f"Error recording user message in convo_manager: {rec_err}")

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
        # =========================================================================
        # 🧠 AUTONOMOUS KAZUMI ACTION ENGINE & INTENT DISPATCHER (PHASE 2)
        # =========================================================================
        action_engine = kazumi_features.get("action_engine")
        if action_engine:
            parsed_action = action_engine.parse_action_intent(clean_text, message)
            if parsed_action:
                act_name, act_params = parsed_action
                action_res = await action_engine.execute_action(act_name, act_params, message)
                logger.info(
                    f"[ROUTER_DIAGNOSTIC] msg_id={message.id} author_id={message.author.id} "
                    f"channel=#{getattr(message.channel, 'name', 'DM')} handler=action_engine "
                    f"action={act_name} success={action_res.success} needs_conf={action_res.needs_confirmation}"
                )
                if action_res.needs_confirmation:
                    from discord_features.action_engine import ActionConfirmationView
                    confirm_view = ActionConfirmationView(
                        engine=action_engine,
                        action_name=act_name,
                        params=act_params,
                        requester_id=message.author.id,
                        original_message=message
                    )
                    active_conversations[session_key] = time.time()
                    await message.reply(
                        action_res.message,
                        view=confirm_view,
                        mention_author=False
                    )
                    return
                elif action_res.success:
                    active_conversations[session_key] = time.time()
                    if action_res.embed:
                        await message.reply(content=action_res.message or None, embed=action_res.embed, mention_author=False)
                    elif action_res.message:
                        await message.reply(action_res.message, mention_author=False)
                    return
                elif action_res.error:
                    active_conversations[session_key] = time.time()
                    await message.reply(f"⚠️ {action_res.error}", mention_author=False)
                    return

        intent_router = kazumi_features.get("intent_router")
        if intent_router:
            detected_intent = intent_router.detect_intent(clean_text, message)
            if detected_intent:
                handled, reply_text, reply_embed = await intent_router.execute_intent(detected_intent, message)
                logger.info(
                    f"[ROUTER_DIAGNOSTIC] msg_id={message.id} author_id={message.author.id} "
                    f"channel=#{getattr(message.channel, 'name', 'DM')} handler=intent_router "
                    f"intent={detected_intent.name} handled={handled}"
                )
                if handled:
                    active_conversations[session_key] = time.time()
                    if reply_embed:
                        await message.reply(embed=reply_embed, mention_author=False)
                    elif reply_text:
                        await message.reply(reply_text, mention_author=False)
                    return

        logger.info(
            f"[ROUTER_DIAGNOSTIC] msg_id={message.id} author_id={message.author.id} "
            f"channel=#{getattr(message.channel, 'name', 'DM')} handler=conversational_ai intent=CONVERSATION"
        )

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

        # Conversational Continuity & Context Injection (Phase 2 & Phase 5)
        if convo_manager and convo_ctx:
            try:
                convo_prompt_ctx = convo_manager.get_prompt_context_injection(convo_ctx)
                if convo_prompt_ctx:
                    social_directives.append(convo_prompt_ctx)
            except Exception as ctx_inj_err:
                logger.debug(f"Error injecting convo context: {ctx_inj_err}")

        # Human-Like Emotional Tone Analyzer & Directives (Phase 3.3)
        if emotional_analyzer:
            try:
                tone_cat, tone_conf, tone_reason = emotional_analyzer.analyze(clean_text)
                tone_directive = emotional_analyzer.get_tone_prompt_directive(tone_cat)
                if tone_directive:
                    social_directives.append(tone_directive)
            except Exception as emo_err:
                logger.debug(f"Error in emotional analysis: {emo_err}")

        if adaptive_directive:
            social_directives.append(adaptive_directive)

        combined_directive = "\n".join(social_directives) if social_directives else None

        reply_text = None
        reply_delivered = False
        # Safely trigger typing indicator while generating reply
        try:
            async with message.channel.typing():
                reply_text = await asyncio.wait_for(
                    ask_kazumi(
                        clean_text,
                        session_id,
                        display_author,
                        creator_ctx,
                        person_directive=combined_directive,
                        is_roast=is_roast_active
                    ),
                    timeout=35.0
                )
        except Exception as typing_err:
            if not reply_text:
                try:
                    reply_text = await asyncio.wait_for(
                        ask_kazumi(
                            clean_text,
                            session_id,
                            display_author,
                            creator_ctx,
                            person_directive=combined_directive,
                            is_roast=is_roast_active
                        ),
                        timeout=25.0
                    )
                except Exception as core_err:
                    logger.error(f"Error querying Kazumi core: {core_err}", exc_info=True)
                    reply_text = "I'm right here with you! 🌸 (Kazumi smiles warmly.) What's on your mind?"


        reply_text = (reply_text or "").strip() or "I'm right here with you! 🌸"
        if kazumi_core and hasattr(kazumi_core, "controller") and hasattr(kazumi_core.controller, "fix_unprompted_how_are_you"):
            reply_text = kazumi_core.controller.fix_unprompted_how_are_you(reply_text, clean_text)
        logger.info(f"💬 Replying to {message.author}: '{reply_text[:60]}...'")

        # Update active conversation timestamp (user-level only)
        active_conversations[session_key] = time.time()

        # If user explicitly says goodbye, end the continuous session
        farewell_words = {"bye", "goodbye", "cya", "see ya", "gn", "goodnight", "good night", "gotta go", "stop", "exit"}
        norm_clean = re.sub(r"[^\w\s]", "", clean_text).lower().strip()
        if norm_clean in farewell_words or any(norm_clean.startswith(fw + " ") for fw in farewell_words):
            active_conversations.pop(session_key, None)
            if convo_manager:
                try:
                    convo_manager.close_session(message)
                except Exception:
                    pass

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
        reply_delivered = await send_kazumi_response(message, reply_text)

    except Exception as e:
        logger.error(f"❌ Error in on_message: {e}", exc_info=True)
        if not reply_delivered:
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


@bot.tree.command(name="status", description="Check companion affection level, relationship tier, or persistence health 💕")
@app_commands.describe(
    user="The server member whose bond and status to check (defaults to you)",
    diagnostics="Show internal memory persistence and storage health diagnostics (default: False)"
)
async def slash_status(interaction: discord.Interaction, user: Optional[discord.Member] = None, diagnostics: bool = False):
    await interaction.response.defer(thinking=True)
    if not kazumi_core:
        await interaction.followup.send("Kazumi core is currently offline.")
        return

    target_user = user or interaction.user
    session_id = get_user_session_id(target_user)
    uid_str = str(target_user.id)

    from person_memory.relationship_manager import RelationshipManager
    from person_memory import get_observation_manager
    obs = get_observation_manager()

    if diagnostics:
        total_profiles = len(obs.memory_mgr._profiles_cache) if obs and obs.memory_mgr else 0
        prof_file = obs.memory_mgr.storage_path if obs and obs.memory_mgr else "None"
        file_exists = os.path.exists(prof_file) if prof_file != "None" else False
        file_size_bytes = os.path.getsize(prof_file) if file_exists else 0

        core_sessions = 0
        with kazumi_lock:
            if kazumi_core and kazumi_core.memory:
                core_sessions = len(kazumi_core.memory.profile.get("session_game_states", {}))

        prof = obs.memory_mgr.get_profile(uid_str) if obs and obs.memory_mgr else None

        embed = create_kazumi_embed(
            title="🛡️ Companion Persistence & Memory Health Diagnostics",
            description=f"Storage health audit for **{target_user.display_name}** (`{uid_str}`):"
        )
        embed.add_field(name="Persistence Health", value="✅ **PERSISTENT & HEALTHY** (No 50-cap pruning)", inline=False)
        embed.add_field(name="Storage Store", value=f"`{os.path.basename(prof_file)}` ({file_size_bytes} bytes)", inline=True)
        embed.add_field(name="Total Person Profiles", value=f"👥 **{total_profiles} members**", inline=True)
        embed.add_field(name="Core User Sessions", value=f"💾 **{core_sessions} sessions**", inline=True)
        embed.add_field(name="Build Commit", value=f"`{get_git_commit()[:12]}`", inline=True)

        if prof:
            rel_title = RelationshipManager.get_relationship_title(prof.relationship_level)
            embed.add_field(name="Current Affection", value=f"💖 **{prof.affection_level}%**", inline=True)
            embed.add_field(name="Lifetime Affection", value=f"🌟 **{prof.lifetime_affection} pts**", inline=True)
            embed.add_field(name="Daily Earned Today", value=f"📈 **{prof.daily_affection_earned}/25 pts**", inline=True)
            embed.add_field(name="Relationship State", value=f"🤝 **{rel_title}**", inline=True)
            embed.add_field(name="Last Seen", value=f"⏱️ `{prof.last_seen or 'Never'}`", inline=True)
            embed.add_field(name="Isolated User ID", value=f"🔑 `{prof.user_id}`", inline=True)

        await interaction.followup.send(embed=embed)
        return

    # Normal Status & Bond View
    affection = 10
    cozy_points = 100
    lifetime_aff = 10
    rel_level = 1
    rel_title = "Recognised Member"
    turn_count = 0

    if obs and obs.memory_mgr:
        prof = obs.memory_mgr.get_profile(uid_str)
        affection = prof.affection_level
        cozy_points = prof.cozy_points
        lifetime_aff = prof.lifetime_affection
        rel_level = prof.relationship_level
        rel_title = RelationshipManager.get_relationship_title(rel_level)
        turn_count = prof.turn_count or prof.interaction_count

    with kazumi_lock:
        kazumi_core.load_game_states(session_id)
        s_state = kazumi_core.memory.profile.setdefault("session_game_states", {}).setdefault(session_id, {})
        persona = s_state.get("archetype", getattr(kazumi_core, "current_archetype", "DEREDERE"))
        if not turn_count:
            turn_count = s_state.get("turn_count", 0)

    # Calculate affection hearts bar
    filled_hearts = min(10, max(0, affection // 10))
    empty_hearts = 10 - filled_hearts
    heart_bar = "💖" * filled_hearts + "🤍" * empty_hearts

    is_self = (target_user.id == interaction.user.id)
    embed = create_kazumi_embed(
        title="🌸 Kazumi Companion Bond & Status",
        description=f"Companion bond metrics for **{target_user.display_name}**{' (You)' if is_self else ''}:"
    )
    embed.add_field(name="Affection Level", value=f"{heart_bar} **{affection}%**", inline=False)
    embed.add_field(name="Relationship Tier", value=f"🤝 **{rel_title}** (Tier {rel_level})", inline=True)
    embed.add_field(name="Cozy Points", value=f"✨ **{cozy_points} pts**", inline=True)
    embed.add_field(name="Lifetime Bond", value=f"🌟 **{lifetime_aff} exp**", inline=True)
    embed.add_field(name="Conversations", value=f"💬 **{turn_count} turns**", inline=True)
    embed.add_field(name="Active Persona", value=f"🌸 **{persona}**", inline=True)
    embed.set_footer(text=f"Kazumi v2.4.0 • Build: {get_git_commit()[:8]}")

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
        s_state = kazumi_core.memory.profile.setdefault("session_game_states", {}).setdefault(session_id, {})
        if archetype:
            s_state["archetype"] = archetype.value
            kazumi_core.memory.save_profile()
            if archetype.value == "UNHINGED":
                desc = f"Switched Kazumi's personality style to **{archetype.name}**! 💀🔥 All filters and sweetness are OFF—prepare for ruthless roasts!"
            else:
                desc = f"Switched Kazumi's personality style to **{archetype.name}** for our upcoming chats! 🌸"
        else:
            curr_arch = s_state.get("archetype", getattr(kazumi_core, "current_archetype", "DEREDERE"))
            desc = f"Kazumi's current active personality for you is **{curr_arch}**."

    curr_p = s_state.get("archetype", getattr(kazumi_core, "current_archetype", "DEREDERE"))
    embed = create_kazumi_embed(
        title="🎭 Companion Personality Style",
        description=desc,
        color=0xff3366 if curr_p == "UNHINGED" else 0xc084fc
    )
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="reset", description="Clear your conversation history with Kazumi for a fresh start 🌿")
async def slash_reset(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    if not kazumi_core:
        await interaction.followup.send("Kazumi core is offline.")
        return

    session_id = get_user_session_id(interaction.user)
    session_key = (interaction.channel_id, interaction.user.id)
    active_conversations.pop(session_key, None)

    with kazumi_lock:
        if hasattr(kazumi_core, "memory") and hasattr(kazumi_core.memory, "history") and isinstance(kazumi_core.memory.history, list):
            kazumi_core.memory.history = [item for item in kazumi_core.memory.history if item.get("session_id") != session_id]
            kazumi_core.memory.save_history()

        if hasattr(kazumi_core, "memory") and hasattr(kazumi_core.memory, "profile"):
            profile = kazumi_core.memory.profile
            if isinstance(profile, dict) and "session_game_states" in profile:
                profile["session_game_states"].pop(session_id, None)
                kazumi_core.memory.save_profile()
    
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
    embed.add_field(name="Companion Familiarity", value=f"💫 **{rel_title}** (Level {profile.relationship_level}/5)", inline=True)
    embed.add_field(name="Conversational Vibe", value=f"✨ **{vibe_str}**", inline=True)
    embed.add_field(name="Interactions Observed", value=f"💬 **{profile.interaction_count} messages**", inline=True)

    if profile.interests:
        embed.add_field(name="Shared Topics", value=", ".join([f"`{i.title()}`" for i in profile.interests[:4]]), inline=False)

    if profile.behaviour_patterns:
        embed.add_field(name="Observed Rhythm", value="\n".join([f"• {p}" for p in profile.behaviour_patterns[:3]]), inline=False)

    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# Prefix Commands (!k <command>)
# ---------------------------------------------------------------------------

@bot.command(name="ping", help="Check Kazumi's latency and response time 🏓")
async def cmd_ping(ctx: commands.Context):
    latency_ms = round(bot.latency * 1000, 1) if bot.latency else 0.0
    await ctx.send(f"Pong! 🏓 Latency: **{latency_ms}ms** 🌸")


@bot.command(name="uptime", help="Check Kazumi's current online uptime ⏱️")
async def cmd_uptime(ctx: commands.Context):
    uptime_sec = int(time.time() - BOT_START_TIME)
    days, rem = divmod(uptime_sec, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    uptime_str = " ".join(parts)
    embed = create_kazumi_embed(
        title="⏱️ Kazumi Uptime",
        description=f"Kazumi has been online and chatting for **{uptime_str}**! 🌸"
    )
    await ctx.send(embed=embed)


@bot.command(name="status", help="Check companion affection level, relationship tier, and stats 💕")
async def cmd_status(ctx: commands.Context, user: Optional[discord.Member] = None):
    if not kazumi_core:
        await ctx.send("Kazumi core is currently offline.")
        return
    target_user = user or ctx.author
    session_id = get_user_session_id(target_user)
    uid_str = str(target_user.id)

    from person_memory.relationship_manager import RelationshipManager
    from person_memory import get_observation_manager
    obs = get_observation_manager()

    affection = 10
    cozy_points = 100
    lifetime_aff = 10
    rel_level = 1
    rel_title = "Recognised Member"
    turn_count = 0

    if obs and obs.memory_mgr:
        prof = obs.memory_mgr.get_profile(uid_str)
        affection = prof.affection_level
        cozy_points = prof.cozy_points
        lifetime_aff = prof.lifetime_affection
        rel_level = prof.relationship_level
        rel_title = RelationshipManager.get_relationship_title(rel_level)
        turn_count = prof.turn_count or prof.interaction_count

    with kazumi_lock:
        kazumi_core.load_game_states(session_id)
        s_state = kazumi_core.memory.profile.setdefault("session_game_states", {}).setdefault(session_id, {})
        persona = s_state.get("archetype", getattr(kazumi_core, "current_archetype", "DEREDERE"))
        if not turn_count:
            turn_count = s_state.get("turn_count", 0)

    filled_hearts = min(10, max(0, affection // 10))
    empty_hearts = 10 - filled_hearts
    heart_bar = "💖" * filled_hearts + "🤍" * empty_hearts

    is_self = (target_user.id == ctx.author.id)
    embed = create_kazumi_embed(
        title="🌸 Kazumi Companion Bond & Status",
        description=f"Companion bond metrics for **{target_user.display_name}**{' (You)' if is_self else ''}:"
    )
    embed.add_field(name="Affection Level", value=f"{heart_bar} **{affection}%**", inline=False)
    embed.add_field(name="Relationship Tier", value=f"🤝 **{rel_title}** (Tier {rel_level})", inline=True)
    embed.add_field(name="Cozy Points", value=f"✨ **{cozy_points} pts**", inline=True)
    embed.add_field(name="Lifetime Bond", value=f"🌟 **{lifetime_aff} exp**", inline=True)
    embed.add_field(name="Conversations", value=f"💬 **{turn_count} turns**", inline=True)
    embed.add_field(name="Active Persona", value=f"🌸 **{persona}**", inline=True)
    await ctx.send(embed=embed)


@bot.command(name="bond", aliases=["bondhealth", "affinity"], help="Inspect companion persistence and memory health 🛡️")
async def cmd_bond(ctx: commands.Context, user: Optional[discord.Member] = None):
    from person_memory import get_observation_manager
    from person_memory.relationship_manager import RelationshipManager
    obs = get_observation_manager()

    target_user = user or ctx.author
    uid_str = str(target_user.id)
    session_id = get_user_session_id(target_user)

    total_profiles = len(obs.memory_mgr._profiles_cache) if obs and obs.memory_mgr else 0
    prof_file = obs.memory_mgr.storage_path if obs and obs.memory_mgr else "None"
    file_exists = os.path.exists(prof_file) if prof_file != "None" else False
    file_size_bytes = os.path.getsize(prof_file) if file_exists else 0

    core_sessions = 0
    with kazumi_lock:
        if kazumi_core and kazumi_core.memory:
            core_sessions = len(kazumi_core.memory.profile.get("session_game_states", {}))

    prof = obs.memory_mgr.get_profile(uid_str) if obs and obs.memory_mgr else None

    embed = create_kazumi_embed(
        title="🛡️ Companion Persistence & Memory Health Diagnostics",
        description=f"Storage health audit for **{target_user.display_name}** (`{uid_str}`):"
    )
    embed.add_field(name="Persistence Health", value="✅ **PERSISTENT & HEALTHY** (No 50-cap pruning)", inline=False)
    embed.add_field(name="Storage Store", value=f"`{os.path.basename(prof_file)}` ({file_size_bytes} bytes)", inline=True)
    embed.add_field(name="Total Person Profiles", value=f"👥 **{total_profiles} members**", inline=True)
    embed.add_field(name="Core User Sessions", value=f"💾 **{core_sessions} sessions**", inline=True)

    if prof:
        rel_title = RelationshipManager.get_relationship_title(prof.relationship_level)
        embed.add_field(name="Current Affection", value=f"💖 **{prof.affection_level}%**", inline=True)
        embed.add_field(name="Lifetime Affection", value=f"🌟 **{prof.lifetime_affection} pts**", inline=True)
        embed.add_field(name="Daily Earned Today", value=f"📈 **{prof.daily_affection_earned}/25 pts**", inline=True)
        embed.add_field(name="Relationship State", value=f"🤝 **{rel_title}**", inline=True)
        embed.add_field(name="Last Seen", value=f"⏱️ `{prof.last_seen or 'Never'}`", inline=True)
        embed.add_field(name="Isolated User ID", value=f"🔑 `{prof.user_id}`", inline=True)

    await ctx.send(embed=embed)


@bot.command(name="diary", help="Read what Kazumi wrote in her journal today 📖")
async def cmd_diary(ctx: commands.Context):
    session_id = get_user_session_id(ctx.author)
    reply_text = await ask_kazumi("/diary", session_id)
    embed = create_kazumi_embed(
        title="📖 Kazumi's Diary Entry",
        description=reply_text[:4000]
    )
    await ctx.send(embed=embed)


@bot.command(name="quests", help="View your active cozy quests and goals 🌟")
async def cmd_quests(ctx: commands.Context):
    session_id = get_user_session_id(ctx.author)
    reply_text = await ask_kazumi("/quests", session_id)
    embed = create_kazumi_embed(
        title="🌟 Cozy Quests & Goals",
        description=reply_text[:4000]
    )
    await ctx.send(embed=embed)


@bot.command(name="horoscope", help="Get a daily horoscope reading ✨")
async def cmd_horoscope(ctx: commands.Context, sign: str = "Aries"):
    if not kazumi_core:
        await ctx.send("Kazumi core is currently offline.")
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
    await ctx.send(embed=embed)


@bot.command(name="persona", help="Switch or view Kazumi's personality archetype 🎭")
async def cmd_persona(ctx: commands.Context, archetype: Optional[str] = None):
    if not kazumi_core:
        await ctx.send("Kazumi core is currently offline.")
        return
    session_id = get_user_session_id(ctx.author)
    valid_archetypes = {"DEREDERE", "TEASING", "KUUDERE", "TSUNDERE", "UNHINGED"}
    with kazumi_lock:
        s_state = kazumi_core.memory.profile.setdefault("session_game_states", {}).setdefault(session_id, {})
        if archetype and archetype.upper() in valid_archetypes:
            arch_val = archetype.upper()
            s_state["archetype"] = arch_val
            kazumi_core.memory.save_profile()
            if arch_val == "UNHINGED":
                desc = f"Switched Kazumi's personality style to **Unhinged**! 💀🔥 All filters and sweetness are OFF—prepare for ruthless roasts!"
            else:
                desc = f"Switched Kazumi's personality style to **{arch_val.title()}** for our upcoming chats! 🌸"
        else:
            curr = s_state.get("archetype", getattr(kazumi_core, "current_archetype", "DEREDERE"))
            desc = f"Kazumi's current personality for you is **{curr}**.\n\nAvailable archetypes: `Deredere`, `Teasing`, `Kuudere`, `Tsundere`, `Unhinged`."

    embed = create_kazumi_embed(
        title="🎭 Companion Personality Style",
        description=desc,
        color=0xff3366 if s_state.get("archetype") == "UNHINGED" else 0xc084fc
    )
    await ctx.send(embed=embed)


@bot.command(name="reset", help="Clear recent conversation memory for a fresh start 🌿")
async def cmd_reset(ctx: commands.Context):
    if not kazumi_core:
        await ctx.send("Kazumi core is offline.")
        return
    session_id = get_user_session_id(ctx.author)
    session_key = (ctx.channel.id, ctx.author.id)
    active_conversations.pop(session_key, None)

    with kazumi_lock:
        if hasattr(kazumi_core, "memory") and hasattr(kazumi_core.memory, "history") and isinstance(kazumi_core.memory.history, list):
            kazumi_core.memory.history = [item for item in kazumi_core.memory.history if item.get("session_id") != session_id]
            kazumi_core.memory.save_history()

        if hasattr(kazumi_core, "memory") and hasattr(kazumi_core.memory, "profile"):
            profile = kazumi_core.memory.profile
            if isinstance(profile, dict) and "session_game_states" in profile:
                profile["session_game_states"].pop(session_id, None)
                kazumi_core.memory.save_profile()
    embed = create_kazumi_embed(
        title="🌿 Fresh Start",
        description="I've cleared our recent chat history for a fresh start! I'm right here whenever you'd like to talk again. 🌸"
    )
    await ctx.send(embed=embed)


@bot.command(name="emotion", help="Check Kazumi's current spontaneous human emotion 💕")
async def cmd_emotion(ctx: commands.Context):
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
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send("I'm feeling cozy and happy to be here with you! 🌸")


@bot.command(name="vibe", help="Check your conversational vibe and familiarity level ✨")
async def cmd_vibe(ctx: commands.Context):
    if not obs_manager:
        await ctx.send("Observation manager is not initialized.")
        return
    profile = obs_manager.get_profile(str(ctx.author.id), display_name=ctx.author.display_name)
    from person_memory.relationship_manager import RelationshipManager
    rel_title = RelationshipManager.get_relationship_title(profile.relationship_level)

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
        title=f"🌸 Conversational Harmony • {ctx.author.display_name}",
        description="Here is how Kazumi experiences your shared conversational rhythm!"
    )
    embed.add_field(name="Companion Familiarity", value=f"💫 **{rel_title}** (Level {profile.relationship_level}/5)", inline=True)
    embed.add_field(name="Conversational Vibe", value=f"✨ **{vibe_str}**", inline=True)
    embed.add_field(name="Interactions Observed", value=f"💬 **{profile.interaction_count} messages**", inline=True)
    if profile.interests:
        embed.add_field(name="Shared Topics", value=", ".join([f"`{i.title()}`" for i in profile.interests[:4]]), inline=False)
    if profile.behaviour_patterns:
        embed.add_field(name="Observed Rhythm", value="\n".join([f"• {p}" for p in profile.behaviour_patterns[:3]]), inline=False)
    await ctx.send(embed=embed)


@bot.command(name="roast", help="Deliver a sharp witty or unhinged roast 💀🔥")
async def cmd_roast(ctx: commands.Context, *, target: Optional[str] = None):
    roast_engine = kazumi_features.get("roast_engine")
    db_inst = kazumi_features.get("db")
    target_str = target or ctx.author.mention
    target_user = None
    if ctx.message.mentions:
        target_user = ctx.message.mentions[0]
    elif not target:
        target_user = ctx.author

    if target_user and db_inst and db_inst.is_user_roast_opted_out(target_user.id):
        await ctx.send(f"🛡️ {target_user.display_name} has opted out of roasts.")
        return

    comeback = None
    if roast_engine and hasattr(roast_engine, "generate_roast"):
        try:
            comeback = roast_engine.generate_roast(target=target_str, intensity=3)
        except Exception:
            pass
    if not comeback:
        comeback = discord_features.ComebackEngine.get_comeback("skill_issue")
    embed = create_kazumi_embed(
        title="💀🔥 Kazumi Roast Delivery",
        description=f"**Target:** {target_str}\n\n{comeback}",
        color=0xff3366
    )
    await ctx.send(embed=embed)


@bot.command(name="unhinged", help="Toggle savage unhinged mode for the server or channel 💀🔥")
async def cmd_unhinged(ctx: commands.Context, toggle: Optional[str] = None):
    db_inst = kazumi_features.get("db")
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return
    gid = ctx.guild.id
    current_settings = db_inst.get_guild_roast_settings(gid) if db_inst else {}
    current_state = current_settings.get("unhinged_mode", False)
    
    if toggle is None:
        new_state = not current_state
    else:
        new_state = toggle.lower() in ("true", "on", "yes", "enable", "enabled", "1")
        
    if db_inst:
        current_settings["unhinged_mode"] = new_state
        db_inst.set_guild_roast_settings(gid, current_settings)

    if new_state:
        msg = "🔥 **Unhinged Mode is now ACTIVATED!** 💀 Kazumi's sweet filters are OFF. Prepare for savage burns!"
    else:
        msg = "🌸 **Unhinged Mode is now DEACTIVATED.** Kazumi is back to her sweet, cozy companion self."
    await ctx.send(msg)


@bot.command(name="connect4", help="Play Connect Four with another user 🔴🔵")
async def cmd_connect4(ctx: commands.Context, opponent: Optional[discord.Member] = None):
    if not ctx.guild:
        await ctx.send("❌ Games can only be played in servers.")
        return
    if not opponent or opponent.id == ctx.author.id or opponent.bot:
        await ctx.send("❌ Please mention a valid player to challenge (e.g. `!k connect4 @player`)!")
        return
    db_inst = kazumi_features.get("db")
    engine = discord_features.get_game_engine(db_inst) if db_inst else None
    if not engine:
        await ctx.send("Game engine is not initialized.")
        return
    can_play, msg = engine.can_user_play(ctx.guild.id, ctx.author.id)
    if not can_play:
        await ctx.send(f"❌ {msg}")
        return
    from discord_features.game_engine import ConnectFourView
    view = ConnectFourView(ctx.author, opponent, engine)
    await ctx.send(embed=view.render_embed(), view=view)


@bot.command(name="tictactoe", help="Play Tic-Tac-Toe vs another player or Kazumi AI ❌⭕")
async def cmd_tictactoe(ctx: commands.Context, opponent: Optional[discord.Member] = None, difficulty: str = "normal"):
    if not ctx.guild:
        await ctx.send("❌ Server only.")
        return
    db_inst = kazumi_features.get("db")
    engine = discord_features.get_game_engine(db_inst) if db_inst else None
    if not engine:
        await ctx.send("Game engine is not initialized.")
        return
    is_ai = (opponent is None or (bot.user and opponent.id == bot.user.id))
    from discord_features.game_engine import TicTacToeView
    view = TicTacToeView(ctx.author, opponent if not is_ai else None, is_ai, difficulty.lower(), engine)
    await ctx.send(embed=view.render_embed(), view=view)


@bot.command(name="arena", help="Challenge a friend to a tactical RPG Arena Duel ⚔️")
async def cmd_arena(ctx: commands.Context, opponent: Optional[discord.Member] = None, your_class: str = "warrior"):
    if not ctx.guild:
        await ctx.send("❌ Server only.")
        return
    if not opponent or opponent.id == ctx.author.id or opponent.bot:
        await ctx.send("❌ Please challenge another human player (e.g. `!k arena @player`)!")
        return
    db_inst = kazumi_features.get("db")
    engine = discord_features.get_game_engine(db_inst) if db_inst else None
    if not engine:
        await ctx.send("Game engine is not initialized.")
        return
    from discord_features.game_engine import ArenaDuelView
    view = ArenaDuelView(ctx.author, opponent, your_class.lower(), engine)
    await ctx.send(embed=view.render_embed(), view=view)


@bot.command(name="trivia", help="Play a round of anime, tech, gaming, or science trivia 🧠")
async def cmd_trivia(ctx: commands.Context, category: Optional[str] = None):
    db_inst = kazumi_features.get("db")
    engine = discord_features.get_game_engine(db_inst) if db_inst else None
    if not engine:
        await ctx.send("Game engine is not initialized.")
        return
    from discord_features.game_engine import TriviaView
    view = TriviaView(ctx.author, category.lower() if category else None, engine)
    await ctx.send(embed=view.render_embed(), view=view)


@bot.command(name="arcade", aliases=["game", "games"], help="Open the Master Arcade Menu 🎮")
async def cmd_arcade(ctx: commands.Context):
    db_inst = kazumi_features.get("db")
    engine = discord_features.get_game_engine(db_inst) if db_inst else None
    if not engine:
        await ctx.send("Game engine is not initialized.")
        return
    from discord_features.game_engine import ArcadeMenuView
    view = ArcadeMenuView(engine)
    embed = create_kazumi_embed(
        title="🎮 Kazumi Arcade & Entertainment Suite",
        description=(
            "Welcome to the Kazumi Arcade! Select a game from the buttons below or use commands:\n\n"
            "• `!k connect4 @player` - Connect Four 🔴🔵\n"
            "• `!k tictactoe [@player] [easy/normal/hard]` - Tic-Tac-Toe ❌⭕\n"
            "• `!k arena @player` - RPG Battle Arena ⚔️\n"
            "• `!k trivia [category]` - Trivia Challenge 🧠\n"
            "• `!k roll [dice]` - Roll dice 🎲\n"
            "• `!k coinflip` - Flip a coin 🪙"
        ),
        color=0xa855f7
    )
    await ctx.send(embed=embed, view=view)


@bot.command(name="roll", help="Roll a die (e.g., !k roll, !k roll 100, !k roll 2d6) 🎲")
async def cmd_roll(ctx: commands.Context, dice: Optional[str] = None):
    if not dice:
        result = random.randint(1, 6)
        await ctx.send(f"🎲 **{ctx.author.display_name}** rolled a **{result}** (1-6)!")
        return
    match = re.match(r"^(\d+)?d(\d+)$", dice.lower().strip())
    if match:
        count = min(int(match.group(1) or 1), 20)
        sides = max(2, min(int(match.group(2)), 1000))
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        rolls_str = ", ".join(map(str, rolls)) if count > 1 else ""
        if rolls_str:
            await ctx.send(f"🎲 **{ctx.author.display_name}** rolled `{dice}`: [{rolls_str}] = **{total}**!")
        else:
            await ctx.send(f"🎲 **{ctx.author.display_name}** rolled `{dice}`: **{total}**!")
        return
    try:
        max_val = int(dice)
        if max_val >= 2:
            result = random.randint(1, max_val)
            await ctx.send(f"🎲 **{ctx.author.display_name}** rolled a **{result}** (1-{max_val})!")
            return
    except ValueError:
        pass
    await ctx.send("🎲 Rolling a standard 6-sided die: **{}**!".format(random.randint(1, 6)))


@bot.command(name="coinflip", aliases=["flip", "coin"], help="Flip a coin (Heads or Tails) 🪙")
async def cmd_coinflip(ctx: commands.Context):
    outcome = random.choice(["Heads 🪙", "Tails 🪙"])
    await ctx.send(f"🪙 **{ctx.author.display_name}** flipped a coin and got **{outcome}**!")


@bot.command(name="help", help="Show all available Kazumi commands 🌸")
async def cmd_help(ctx: commands.Context):
    embed = create_kazumi_embed(
        title="🌸 Kazumi Commands & Features Guide",
        description=(
            "Here is a complete list of commands you can use with prefix `!k` or `/`:\n\n"
            "**💬 Conversation & Companion:**\n"
            "• `!k ping` - Check latency\n"
            "• `!k uptime` - Check bot uptime\n"
            "• `!k status` - Affection level, cozy points, turn count\n"
            "• `!k diary` - Read Kazumi's daily reflections\n"
            "• `!k quests` - Cozy quests and milestones\n"
            "• `!k horoscope [sign]` - Daily astrological reading\n"
            "• `!k persona [archetype]` - Switch persona (Deredere, Teasing, Kuudere, Tsundere, Unhinged)\n"
            "• `!k reset` - Clear conversation history for a fresh start\n"
            "• `!k emotion` - View spontaneous human emotions\n"
            "• `!k vibe` - Check conversational harmony\n"
            "• `!k roast [@user]` - Savage roast delivery\n"
            "• `!k unhinged [on/off]` - Toggle unhinged savage mode\n\n"
            "**🎮 Arcade & Games:**\n"
            "• `!k arcade` - Master arcade game menu\n"
            "• `!k connect4 @player` - Connect Four match\n"
            "• `!k tictactoe [@player] [diff]` - Tic-Tac-Toe\n"
            "• `!k arena @player` - RPG Arena Duel\n"
            "• `!k trivia [category]` - Trivia quiz\n"
            "• `!k roll [dice]` - Roll dice\n"
            "• `!k coinflip` - Flip a coin\n\n"
            "**✨ Slash Commands:**\n"
            "You can also use `/chat`, `/status`, `/roast`, `/help`, and 20+ other slash commands!"
        )
    )
    await ctx.send(embed=embed)


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


def setup_process_safety_net():
    """Installs top-level unhandled exception hooks and guarded signal handlers."""
    def handle_sys_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(f"Unhandled fatal exception in main thread: {exc_value}", exc_info=(exc_type, exc_value, exc_traceback))
        release_single_instance_lock()
        sys.exit(1)

    sys.excepthook = handle_sys_exception

    if hasattr(threading, "excepthook"):
        def handle_thread_exception(args):
            if issubclass(args.exc_type, (KeyboardInterrupt, SystemExit)):
                return
            logger.critical(
                f"Unhandled fatal exception in worker thread '{args.thread.name}': {args.exc_value}",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
            )
        threading.excepthook = handle_thread_exception

    import signal
    def handle_shutdown_signal(signum, frame):
        sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        logger.info(f"[SHUTDOWN] Received signal {sig_name}. Performing clean shutdown...")
        release_single_instance_lock()
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, handle_shutdown_signal)
    except Exception:
        pass
    try:
        signal.signal(signal.SIGTERM, handle_shutdown_signal)
    except Exception:
        pass
    if hasattr(signal, "SIGBREAK"):
        try:
            signal.signal(signal.SIGBREAK, handle_shutdown_signal)
        except Exception:
            pass


def main():
    global DISCORD_BOT_TOKEN
    setup_process_safety_net()

    # Persistent crash-loop protection across restarts
    try:
        from restart_protector import RestartLoopProtector
        state_file = os.path.join(ISA_MEMORY_DIR, ".crash_loop_state.json")
        protector = RestartLoopProtector(state_file=state_file)
        startup_delay = protector.record_boot_and_get_delay()
        if startup_delay > 0:
            logger.warning(f"⚠️ [RESTART_DELAY] Backing off for {startup_delay:.2f}s due to recent rapid crashes...")
            time.sleep(startup_delay)
    except Exception as prot_err:
        logger.warning(f"Failed to check restart loop protection: {prot_err}")

    logger.info(f"[HOST] Runtime Host: {DEPLOY_ENV['name']} (Remote: {DEPLOY_ENV['is_remote']})")
    logger.info(f"[STARTUP] Kazumi Discord Bot process started. DISCORD_BOT_TOKEN configured: {bool(DISCORD_BOT_TOKEN)}")
    is_valid_cfg, config_errors = KazumiConfig.validate_startup_config()
    if not is_valid_cfg:
        for err in config_errors:
            logger.error(f"❌ [STARTUP_CONFIG_ERROR] {err}")
        print_discord_setup_guide()
        if DEPLOY_ENV["is_remote"]:
            logger.info("🌸 Running on remote cloud host. Starting HTTP health server and waiting for DISCORD_BOT_TOKEN...")
            async def wait_for_token_loop():
                global DISCORD_BOT_TOKEN
                await setup_health_server()
                while not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "your_discord_bot_token_here":
                    await asyncio.sleep(5)
                    try:
                        from dotenv import load_dotenv
                        load_dotenv(override=True)
                    except Exception:
                        pass
                    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
            try:
                asyncio.run(wait_for_token_loop())
                logger.info("🔑 DISCORD_BOT_TOKEN detected! Proceeding with Discord connection...")
            except (KeyboardInterrupt, SystemExit):
                sys.exit(0)
        else:
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
            logger.info("[SHUTDOWN] Discord bot run loop finished cleanly.")
            break
        except discord.errors.LoginFailure as lf:
            logger.error(f"❌ Fatal login failure: Invalid Discord Bot Token: {lf}")
            sys.exit(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("[SHUTDOWN] Kazumi Discord Bot stopped by user signal.")
            release_single_instance_lock()
            sys.exit(0)
        except Exception as e:
            logger.error(f"[GATEWAY_FAILURE] Discord connection terminated: {e}. Auto-reconnecting in {retry_delay}s...", exc_info=True)
            time.sleep(retry_delay)
            retry_delay = min(max_delay, int(retry_delay * 1.5))


if __name__ == "__main__":
    main()

