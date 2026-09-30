# -*- coding: utf-8 -*-
"""
KAZUMI ADVANCED SOCIAL & SERVER INTELLIGENCE
- Mood System (8 states: happy, calm, excited, curious, sleepy, playful, concerned, neutral)
- Social Memory Graph (inter-member relationships, interests, interaction frequencies)
- Server Memory (channel roles, community jokes, projects, events)
- Conversation Continuity (thread tracking & context resumption across breaks)
- Smart Silence Engine (calculates whether Kazumi should reply, react, or stay silent)
- Natural Reaction Predictor (context-aware emoji selection with cooldowns)
- Personal Interaction Levels (New, Recognised, Familiar, Regular, Very Familiar)
- Kazumi Moments & Server Events (spontaneous community milestones with strict throttling)
"""

import re
import time
import random
import logging
from typing import Dict, List, Optional, Tuple
from .database import FeatureDB

logger = logging.getLogger("KazumiSocial")

# 1. MOOD SYSTEM
MOODS = ["happy", "calm", "excited", "curious", "sleepy", "playful", "concerned", "neutral"]

class MoodManager:
    """Manages Kazumi's dynamic internal emotional state."""
    
    def __init__(self, db: FeatureDB):
        self.db = db

    def get_guild_mood(self, guild_id: int) -> str:
        data = self.db.get_server_memory(guild_id)
        return data.get("current_mood", "calm")

    def update_mood(self, guild_id: int, message_content: str, is_active_chat: bool = True) -> str:
        """Subtly adjust mood based on interaction context."""
        current = self.get_guild_mood(guild_id)
        content_lower = message_content.lower()
        
        target_mood = current
        # Contextual shifts
        if any(w in content_lower for w in ["haha", "lmao", "lol", "joke", "funny", "pfft", "xd"]):
            target_mood = random.choice(["playful", "happy"])
        elif any(w in content_lower for w in ["sad", "depressed", "hurt", "crying", "lost", "bad day", "tired"]):
            target_mood = "concerned"
        elif any(w in content_lower for w in ["hype", "congrats", "won", "yay", "amazing", "finally", "omg", "lets go"]):
            target_mood = "excited"
        elif any(w in content_lower for w in ["why", "how", "what if", "theory", "explain", "curious", "code", "bug"]):
            target_mood = "curious"
        elif any(w in content_lower for w in ["goodnight", "gn", "sleep", "bed", "late", "yawn", "nap"]):
            target_mood = "sleepy"
        elif any(w in content_lower for w in ["peace", "calm", "relax", "chill", "music", "lofi"]):
            target_mood = "calm"
        else:
            # Subtle random decay towards calm/neutral or playful
            if random.random() < 0.15:
                target_mood = random.choice(["calm", "neutral", "playful"])
                
        # Persist if changed
        if target_mood != current:
            self.db.update_server_memory(guild_id, {"current_mood": target_mood})
            logger.debug(f"[Mood] Guild {guild_id} shifted mood from {current} to {target_mood}")
            
        return target_mood

    def get_mood_prompt_modifier(self, mood: str) -> str:
        """Returns a subtle prompt injection describing Kazumi's mood."""
        modifiers = {
            "happy": "You are feeling cheerful, bright, and warmly affectionate.",
            "calm": "You are feeling relaxed, gentle, serene, and grounded.",
            "excited": "You are feeling energetic, enthusiastic, and easily hyped!",
            "curious": "You are feeling intrigued, inquisitive, and eager to learn or understand details.",
            "sleepy": "You are feeling a bit cozy, drowsy, sweet, and low-energy.",
            "playful": "You are feeling mischievous, witty, teasing, and playful.",
            "concerned": "You are feeling deeply caring, empathetic, supportive, and protective.",
            "neutral": "You are composed, observant, and naturally attentive."
        }
        return modifiers.get(mood, "You are calm and attentive.")


# 2. SOCIAL MEMORY GRAPH & INTERACTION LEVELS
INTERACTION_LEVELS = [
    (0, "New"),
    (5, "Recognised"),
    (25, "Familiar"),
    (80, "Regular"),
    (250, "Very Familiar")
]

class SocialGraphManager:
    """Tracks member relationships, discussion topics, and familiarity."""
    
    def __init__(self, db: FeatureDB):
        self.db = db

    def get_user_profile(self, guild_id: int, user_id: int) -> dict:
        graph = self.db.get_social_graph(guild_id)
        user_key = str(user_id)
        return graph.get("users", {}).get(user_key, {
            "total_messages": 0,
            "first_seen": int(time.time()),
            "last_seen": int(time.time()),
            "topics": [],
            "style_tags": [],
            "interaction_level": "New"
        })

    def record_interaction(self, guild_id: int, user_id: int, username: str, content: str, topic_candidate: Optional[str] = None):
        """Record an observed message to update the social graph."""
        graph = self.db.get_social_graph(guild_id)
        if "users" not in graph:
            graph["users"] = {}
        
        user_key = str(user_id)
        now = int(time.time())
        user_data = graph["users"].get(user_key, {
            "username": username,
            "total_messages": 0,
            "first_seen": now,
            "last_seen": now,
            "topics": [],
            "style_tags": [],
            "interaction_level": "New"
        })

        user_data["username"] = username
        user_data["total_messages"] = user_data.get("total_messages", 0) + 1
        user_data["last_seen"] = now

        # Calculate interaction level
        count = user_data["total_messages"]
        level = "New"
        for threshold, lvl_name in INTERACTION_LEVELS:
            if count >= threshold:
                level = lvl_name
        user_data["interaction_level"] = level

        # Detect topic tags
        content_lower = content.lower()
        topic_keywords = {
            "gaming": ["game", "gaming", "steam", "fps", "rpg", "valorant", "minecraft", "roblox", "elden ring", "genshin"],
            "coding": ["code", "programming", "python", "javascript", "developer", "bug", "git", "api", "backend", "linux"],
            "anime": ["anime", "manga", "weeb", "episode", "season", "crunchyroll", "waifu"],
            "music": ["music", "song", "album", "band", "guitar", "piano", "track", "spotify"],
            "art": ["art", "drawing", "sketch", "blender", "design", "render", "artist"],
            "fitness": ["gym", "workout", "cardio", "lifting", "run", "diet"],
            "study": ["exam", "homework", "college", "uni", "school", "assignment", "thesis"]
        }

        topics = set(user_data.get("topics", []))
        for topic, keywords in topic_keywords.items():
            if any(k in content_lower for k in keywords):
                topics.add(topic)
        if topic_candidate:
            topics.add(topic_candidate.lower())
        user_data["topics"] = list(topics)[:10]

        # Style tags (e.g. all-caps hype, formal, brief, emoji-heavy)
        style_tags = set(user_data.get("style_tags", []))
        if content.isupper() and len(content) > 6:
            style_tags.add("loud/hype")
        if any(c in content for c in ["🌸", "✨", "😭", "💀", "🥺", "❤️", "🔥"]):
            style_tags.add("expressive")
        if len(content.split()) < 4:
            style_tags.add("concise")
        elif len(content.split()) > 25:
            style_tags.add("detailed")
        user_data["style_tags"] = list(style_tags)[:6]

        graph["users"][user_key] = user_data
        self.db.update_social_graph(guild_id, graph)

    def get_familiarity_context(self, guild_id: int, user_id: int) -> str:
        """Returns brief descriptive text of user familiarity for the prompt."""
        profile = self.get_user_profile(guild_id, user_id)
        level = profile.get("interaction_level", "New")
        topics = ", ".join(profile.get("topics", [])) or "general topics"
        styles = ", ".join(profile.get("style_tags", [])) or "natural"
        return f"Interaction Level: {level}. Known interests: [{topics}]. Style habits: [{styles}]."


# 3. SERVER MEMORY (COMMUNITY KNOWLEDGE)
class ServerMemoryManager:
    """Learns community terminology, active channels, milestones."""
    
    def __init__(self, db: FeatureDB):
        self.db = db

    def learn_channel_purpose(self, guild_id: int, channel_id: int, channel_name: str):
        """Map channel names to common purposes."""
        mem = self.db.get_server_memory(guild_id)
        channels = mem.get("channels", {})
        c_name = channel_name.lower()
        purpose = "general chat"
        if "bot" in c_name or "command" in c_name:
            purpose = "bot commands"
        elif "game" in c_name or "gaming" in c_name:
            purpose = "gaming & multiplayer"
        elif "code" in c_name or "dev" in c_name:
            purpose = "programming & tech discussion"
        elif "art" in c_name or "creativity" in c_name:
            purpose = "art showcase"
        elif "music" in c_name or "voice" in c_name:
            purpose = "music & hanging out"
        elif "announcement" in c_name or "news" in c_name:
            purpose = "server announcements"
        elif "mod" in c_name or "staff" in c_name:
            purpose = "staff / moderator only"

        channels[str(channel_id)] = {"name": channel_name, "purpose": purpose}
        self.db.update_server_memory(guild_id, {"channels": channels})

    def get_server_context_summary(self, guild_id: int) -> str:
        """Summarizes known server facts for the prompt."""
        mem = self.db.get_server_memory(guild_id)
        channels = mem.get("channels", {})
        known_channels = [f"#{v.get('name')}: {v.get('purpose')}" for k, v in list(channels.items())[:6]]
        jokes = mem.get("inside_jokes", [])[:3]
        return f"Known Channels: {'; '.join(known_channels) if known_channels else 'Standard'}. Server lore: {', '.join(jokes) if jokes else 'None yet'}."


# 4. CONVERSATION CONTINUITY
class ConversationContinuityTracker:
    """Remembers the last active subject discussed with a user across breaks."""
    
    def __init__(self):
        # Memory cache: (guild_id, user_id) -> {"topic": str, "last_msg": str, "timestamp": float}
        self._history: Dict[Tuple[int, int], dict] = {}

    def record_subject(self, guild_id: int, user_id: int, message: str, topic: Optional[str] = None):
        if len(message.strip()) < 5:
            return
        self._history[(guild_id, user_id)] = {
            "topic": topic or message[:80],
            "last_msg": message,
            "timestamp": time.time()
        }

    def get_resumed_context(self, guild_id: int, user_id: int, min_gap_seconds: int = 1800, max_gap_seconds: int = 86400 * 3) -> Optional[str]:
        """If a user returns after 30+ minutes, provides a callback memory if relevant."""
        entry = self._history.get((guild_id, user_id))
        if not entry:
            return None
        now = time.time()
        gap = now - entry["timestamp"]
        if min_gap_seconds <= gap <= max_gap_seconds:
            # We have a candidate context
            return f"Earlier, they were talking about: \"{entry['topic']}\""
        return None


# 5. SMART SILENCE ENGINE
class SmartSilenceEngine:
    """
    Decides whether Kazumi should reply, react with an emoji, or stay silent.
    Prevents annoying AI chatter while preserving warm companion presence.
    """

    def __init__(self, bot_user_id: int):
        self.bot_user_id = bot_user_id
        # Channel ID -> last bot response timestamp
        self._last_spoke: Dict[int, float] = {}

    def decide(
        self,
        message,
        is_direct_mention: bool,
        is_reply_to_kazumi: bool,
        is_active_channel: bool,
        is_observation_only: bool
    ) -> str:
        """
        Returns one of: 'REPLY', 'REACT', 'SILENCE'
        """
        now = time.time()
        channel_id = message.channel.id
        content = message.content.strip()

        # If channel is disabled, total silence
        if not is_active_channel and not is_observation_only:
            return "SILENCE"

        # Observation-only channels: NEVER send conversational replies, but can react occasionally
        if is_observation_only:
            if is_direct_mention or is_reply_to_kazumi:
                # Even if mentioned, in observation mode Kazumi reacts or sends a brief notice
                return "REACT"
            # 8% chance to react if funny/exciting
            tokens = set(re.findall(r"\b\w+\b", content.lower()))
            if any(w in tokens for w in ["haha", "lmao", "gg", "congrats", "rip", "omg"]):
                return "REACT" if random.random() < 0.15 else "SILENCE"
            return "SILENCE"

        # Direct mentions or direct replies are priority replies
        if is_direct_mention or is_reply_to_kazumi:
            self._last_spoke[channel_id] = now
            return "REPLY"

        # If Kazumi spoke very recently in this channel (within 10 seconds), avoid interrupting
        last_spoke_time = self._last_spoke.get(channel_id, 0)
        time_since_last_response = now - last_spoke_time

        # Check for Kazumi name mention ("kazumi")
        if "kazumi" in content.lower():
            # If someone is talking to Kazumi
            self._last_spoke[channel_id] = now
            return "REPLY"

        # If it's a general server message:
        # Avoid replying if someone is just chatting with someone else
        if len(content) < 6:
            return "SILENCE"

        # If there's an obvious question directed into the void and nobody answered
        if content.endswith("?") and any(q in content.lower() for q in ["anyone know", "does anybody", "what should i"]):
            if time_since_last_response > 45 and random.random() < 0.40:
                self._last_spoke[channel_id] = now
                return "REPLY"

        # Reaction triggers
        reaction_triggers = ["lmao", "lol", "gg", "rip", "lets go", "finally", "cute", "omg", "congrats", "w"]
        if any(trig in content.lower().split() for trig in reaction_triggers):
            if random.random() < 0.25:
                return "REACT"

        return "SILENCE"


# 6. NATURAL REACTIONS
EMOJI_CATEGORIES = {
    "funny": ["😂", "💀", "🤣", "😭"],
    "achievement": ["🎉", "🔥", "🏆", "✨"],
    "surprise": ["😳", "😮", "👀"],
    "cute": ["🥹", "🌸", "💖", "✨"],
    "agreement": ["👍", "💯", "🤝"],
    "support": ["❤️", "🫂", "✨", "🌸"]
}

class NaturalReactionPicker:
    """Picks appropriate contextual reaction emoji."""
    
    @staticmethod
    def pick_emoji(content: str) -> Optional[str]:
        content_lower = content.lower()
        if any(w in content_lower for w in ["haha", "lmao", "lol", "xd", "dead", "pfft", "meme"]):
            return random.choice(EMOJI_CATEGORIES["funny"])
        if any(w in content_lower for w in ["win", "won", "gg", "finally", "done", "passed", "fixed it", "promotion"]):
            return random.choice(EMOJI_CATEGORIES["achievement"])
        if any(w in content_lower for w in ["whaaat", "no way", "wtf", "wait what", "shock", "fr?"]):
            return random.choice(EMOJI_CATEGORIES["surprise"])
        if any(w in content_lower for w in ["cat", "dog", "puppy", "kitten", "aww", "cute", "sweet", "kazumi"]):
            return random.choice(EMOJI_CATEGORIES["cute"])
        if any(w in content_lower for w in ["agree", "true", "facts", "based", "real", "valid"]):
            return random.choice(EMOJI_CATEGORIES["agreement"])
        if any(w in content_lower for w in ["sad", "rough", "hurts", "failed", "exhausted", "hug", "depressed"]):
            return random.choice(EMOJI_CATEGORIES["support"])
        return None


# 7. SERVER EVENTS & KAZUMI MOMENTS
DAILY_QUESTIONS = [
    "Random thought of the day: What's one game or show you could experience for the first time again? 🌸",
    "Quick question for everyone: What's your go-to comfort food when you've had a long day? 🍜",
    "Community check-in: What project, hobby, or goal are you working on right now? ✨",
    "If you could have instant mastery over any single skill, what would you choose? 🧠",
    "What's the best piece of advice someone has ever given you that actually stuck? 💡",
    "Is cereal technically a soup or a salad? Please defend your thesis. 🥣",
    "What soundtrack or album has zero skips for you? 🎶"
]

class KazumiMomentsEngine:
    """Manages spontaneous interactions with strict cooldowns."""

    def __init__(self, db: FeatureDB):
        self.db = db
        # Guild ID -> last moment timestamp
        self._last_moment: Dict[int, float] = {}

    def can_trigger_moment(self, guild_id: int, min_interval_hours: int = 12) -> bool:
        last = self._last_moment.get(guild_id, 0)
        return (time.time() - last) > (min_interval_hours * 3600)

    def mark_moment_triggered(self, guild_id: int):
        self._last_moment[guild_id] = time.time()

    def get_daily_question(self) -> str:
        return random.choice(DAILY_QUESTIONS)

    def check_silence_break(self, guild_id: int, channel_quiet_hours: float) -> Optional[str]:
        """If server has been unusually quiet for 12+ hours."""
        if channel_quiet_hours >= 12 and self.can_trigger_moment(guild_id, min_interval_hours=24):
            self.mark_moment_triggered(guild_id)
            options = [
                "It's suspiciously quiet in here... what is everyone up to today? 🌸",
                "Hope everyone is having a good day out there. Sending cozy energy to the chat ✨",
                "Just checking in on you all... don't forget to drink some water! 🥤"
            ]
            return random.choice(options)
        return None
