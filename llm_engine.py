import os
import sys
import asyncio

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ISA_MEMORY_DIR = os.path.join(ROOT_DIR, "isa_memory")
if os.environ.get("SPACE_ID") and os.path.exists("/data") and os.access("/data", os.W_OK):
    ISA_MEMORY_DIR = os.path.join("/data", "isa_memory")

os.makedirs(ISA_MEMORY_DIR, exist_ok=True)

# Add ROOT_DIR to path
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from kazumi import Kazumi

# Initialize the shared bot
kazumi_bot = Kazumi()
kazumi_bot.memory.persist_path = os.path.join(ISA_MEMORY_DIR, "conversations.json")
kazumi_bot.memory.profile_path = os.path.join(ISA_MEMORY_DIR, "profile.json")
kazumi_bot.memory.diary_path = os.path.join(ISA_MEMORY_DIR, "diary.json")

# Re-load memory with paths
kazumi_bot.memory.history = kazumi_bot.memory.load_history()
kazumi_bot.memory.profile = kazumi_bot.memory.load_profile()
kazumi_bot.active_character = kazumi_bot.memory.profile.get("character", "kazumi")
if kazumi_bot.active_character not in kazumi_bot.CHARACTERS:
    kazumi_bot.active_character = "kazumi"
kazumi_bot.current_archetype = "TEASING" if kazumi_bot.active_character == "mimi" else "DEREDERE"
kazumi_bot.load_game_states()

async def async_reply(text: str, session_id: str = "default") -> str:
    """Runs the synchronous kazumi_bot.reply inside a thread pool to avoid blocking the event loop."""
    return await asyncio.to_thread(kazumi_bot.reply, text, session_id)

def get_affection_level() -> int:
    """Returns the current affection level."""
    if hasattr(kazumi_bot, 'memory') and kazumi_bot.memory.profile:
        return kazumi_bot.memory.profile.get("affection_level", 50)
    return 50
