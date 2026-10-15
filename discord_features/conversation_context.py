# -*- coding: utf-8 -*-
"""
🌸 Kazumi Conversation Context Manager (Phase 2 Standard)
Maintains stateful, persistent-in-memory conversation continuity for natural dialogue.
Enables multi-turn conversations without requiring repeated mentions or pings.

Context Key: (guild_id, channel_id, user_id, thread_id)
Features:
- Track recent messages and dialog history
- Identify the last question asked by Kazumi
- Detect whether Kazumi is awaiting a response
- Support short answers ("Yeah.", "Not really.", "My family.", "Exactly.", "The blue one.")
- Recognize Discord reply references (pointing to Kazumi's previous messages)
- Isolate simultaneous conversations between different members
- Expiration and closure state handling
"""

import re
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import discord


# Short answer signals commonly used in natural conversation
SHORT_ANSWER_PATTERNS = {
    r"^(?:yeah|yes|yep|yup|nah|no|nope|not really|never|sure|maybe|definitely|absolutely)$",
    r"^(?:my family|family|friends|my friends|my work|work|music|sports|gaming|coding)$",
    r"^(?:exactly|agreed|true|fair enough|totally|for real|same here|me too)$",
    r"^(?:that was fun|it was fun|loved it|enjoyed it|so cool|awesome)$",
    r"^(?:i finished it|finished it|done|all done|almost|working on it|not yet)$",
    r"^(?:the (?:blue|red|green|black|white|pink|purple|first|second|third|last) one)$",
    r"^(?:like yesterday|yesterday|today|tomorrow|last week|a few days ago|recently)$",
    r"^(?:i think so|probably|i guess so|don't think so|not sure|no idea)$",
    r"^(?:good|fine|pretty good|alright|bad|tired|sleepy|doing well)$"
}

QUESTION_EXTRACTOR_REGEX = re.compile(
    r"([^.!?\n]*\?)\s*$",
    re.IGNORECASE | re.MULTILINE
)


@dataclass
class ConversationContext:
    guild_id: int
    channel_id: int
    user_id: int
    thread_id: int = 0

    last_interaction_time: float = field(default_factory=time.time)
    last_kazumi_message_id: Optional[int] = None
    last_kazumi_text: str = ""
    last_question_asked: Optional[str] = None
    awaiting_response: bool = False

    topic: Optional[str] = None
    recent_intent: Optional[str] = None
    closure_state: str = "ACTIVE"  # "ACTIVE", "EXPIRED", "CLOSED"
    turn_count: int = 0
    recent_messages: List[Dict[str, Any]] = field(default_factory=list)

    def is_expired(self, timeout_seconds: float = 180.0) -> bool:
        if self.closure_state != "ACTIVE":
            return True
        return (time.time() - self.last_interaction_time) > timeout_seconds

    def add_message(self, speaker: str, text: str, message_id: Optional[int] = None):
        self.recent_messages.append({
            "speaker": speaker,
            "text": text,
            "message_id": message_id,
            "timestamp": time.time()
        })
        if len(self.recent_messages) > 12:
            self.recent_messages = self.recent_messages[-12:]


class ConversationContextManager:
    """
    Thread-safe, stateful conversation manager for Discord interactions.
    Keyed by (guild_id, channel_id, user_id, thread_id) for strict multi-user isolation.
    """

    def __init__(self, default_timeout_seconds: float = 180.0):
        self._lock = threading.RLock()
        self.default_timeout = default_timeout_seconds
        self._contexts: Dict[Tuple[int, int, int, int], ConversationContext] = {}
        # Fast lookup: kazumi_message_id -> (key)
        self._bot_message_to_key: Dict[int, Tuple[int, int, int, int]] = {}

    @staticmethod
    def make_key(message: discord.Message) -> Tuple[int, int, int, int]:
        guild_id = message.guild.id if message.guild else 0
        channel_id = message.channel.id
        thread_id = message.channel.id if isinstance(message.channel, discord.Thread) else 0
        user_id = message.author.id
        return (guild_id, channel_id, user_id, thread_id)

    def get_or_create(self, message: discord.Message) -> ConversationContext:
        key = self.make_key(message)
        with self._lock:
            ctx = self._contexts.get(key)
            if not ctx:
                ctx = ConversationContext(
                    guild_id=key[0],
                    channel_id=key[1],
                    user_id=key[2],
                    thread_id=key[3],
                    last_interaction_time=time.time()
                )
                self._contexts[key] = ctx
            return ctx

    def get_context(self, key: Tuple[int, int, int, int]) -> Optional[ConversationContext]:
        with self._lock:
            return self._contexts.get(key)

    def is_active(self, key: Tuple[int, int, int, int], timeout_seconds: Optional[float] = None) -> bool:
        timeout = timeout_seconds or self.default_timeout
        with self._lock:
            ctx = self._contexts.get(key)
            if not ctx:
                return False
            return not ctx.is_expired(timeout)

    def record_user_message(self, message: discord.Message) -> ConversationContext:
        key = self.make_key(message)
        with self._lock:
            ctx = self.get_or_create(message)
            ctx.last_interaction_time = time.time()
            ctx.closure_state = "ACTIVE"
            ctx.turn_count += 1
            ctx.add_message("user", (message.content or "").strip(), message.id)
            return ctx

    def record_kazumi_response(
        self,
        message: discord.Message,
        response_text: str,
        bot_message_id: Optional[int] = None
    ) -> ConversationContext:
        key = self.make_key(message)
        with self._lock:
            ctx = self.get_or_create(message)
            ctx.last_interaction_time = time.time()
            ctx.last_kazumi_text = response_text
            ctx.last_kazumi_message_id = bot_message_id
            ctx.closure_state = "ACTIVE"

            # Detect if Kazumi asked a question
            q_match = QUESTION_EXTRACTOR_REGEX.search(response_text.strip())
            if q_match:
                ctx.last_question_asked = q_match.group(1).strip()
                ctx.awaiting_response = True
            else:
                # If no question mark in last 50 chars, we are not actively awaiting a direct question answer
                ctx.awaiting_response = False
                ctx.last_question_asked = None

            ctx.add_message("kazumi", response_text, bot_message_id)

            if bot_message_id:
                self._bot_message_to_key[bot_message_id] = key
                if len(self._bot_message_to_key) > 500:
                    try:
                        self._bot_message_to_key.pop(next(iter(self._bot_message_to_key)))
                    except Exception:
                        pass

            return ctx

    def is_continuation(
        self,
        message: discord.Message,
        timeout_seconds: Optional[float] = None
    ) -> Tuple[bool, str, Optional[ConversationContext]]:
        """
        Determines whether an incoming message continues an ongoing Kazumi conversation.
        Returns:
            (is_continuation: bool, reason: str, context: Optional[ConversationContext])
        """
        raw_text = (message.content or "").strip()
        clean_lower = raw_text.lower().strip()
        key = self.make_key(message)
        timeout = timeout_seconds or self.default_timeout

        with self._lock:
            # 1. Discord Reply Metadata: Check if message is a Discord reply to Kazumi
            if message.reference and message.reference.message_id:
                ref_id = message.reference.message_id
                # Check if referenced message is recorded as Kazumi's message to this user
                if ref_id in self._bot_message_to_key:
                    target_key = self._bot_message_to_key[ref_id]
                    if target_key == key:
                        ctx = self._contexts.get(key)
                        if ctx:
                            return True, "discord_reply_to_kazumi", ctx

            ctx = self._contexts.get(key)
            if not ctx:
                return False, "no_active_context", None

            # 2. Check if conversation has timed out or is closed
            if ctx.is_expired(timeout):
                ctx.closure_state = "EXPIRED"
                return False, "conversation_expired", ctx

            # 3. Check for explicit closure words from the user
            farewell_words = {"bye", "goodbye", "cya", "see ya", "gn", "goodnight", "stop", "exit", "quit", "leave me alone"}
            norm_clean = re.sub(r"[^\w\s]", "", clean_lower).strip()
            if norm_clean in farewell_words or any(norm_clean.startswith(fw + " ") for fw in farewell_words):
                ctx.closure_state = "CLOSED"
                return False, "conversation_closed_by_user", ctx

            # 4. Check if Kazumi was awaiting a response to her question
            if ctx.awaiting_response and ctx.last_question_asked:
                # User sent a message within timeout window following Kazumi's question!
                return True, f"answering_kazumi_question: '{ctx.last_question_asked[:40]}'", ctx

            # 5. Check if user sent a short answer ("Yeah.", "Not really.", "My family.")
            if self.is_short_answer(raw_text):
                return True, "short_answer_continuation", ctx

            # 6. Active conversation window check (user continuing dialogue naturally within 120s)
            elapsed = time.time() - ctx.last_interaction_time
            if elapsed <= 120.0:
                return True, "recent_active_conversation", ctx

            return False, "outside_continuation_window", ctx

    @staticmethod
    def is_short_answer(text: str) -> bool:
        clean = text.lower().strip()
        norm = re.sub(r"[^\w\s]", "", clean).strip()
        words = norm.split()
        if not words:
            return False

        # Match regex patterns
        for pattern in SHORT_ANSWER_PATTERNS:
            if re.search(pattern, norm, re.IGNORECASE):
                return True

        # Short length check: 1 to 5 words without external bot prefix
        if len(words) <= 4 and clean[0] not in "!?.$-/":
            return True

        return False

    def close_session(self, message: discord.Message, reason: str = "user_closed"):
        key = self.make_key(message)
        with self._lock:
            ctx = self._contexts.get(key)
            if ctx:
                ctx.closure_state = "CLOSED"
                ctx.awaiting_response = False

    def get_prompt_context_injection(self, ctx: Optional[ConversationContext]) -> Optional[str]:
        """Builds an informative prompt context string for the AI generator."""
        if not ctx:
            return None

        lines = ["[CONVERSATION CONTINUITY ACTIVE:"]
        if ctx.last_question_asked and ctx.awaiting_response:
            lines.append(f"  - You previously asked: \"{ctx.last_question_asked}\"")
            lines.append("  - The user is answering your question. Directly acknowledge and build on their answer.")
        elif ctx.last_kazumi_text:
            last_snippet = ctx.last_kazumi_text.strip().replace("\n", " ")[:100]
            lines.append(f"  - Your last message: \"{last_snippet}...\"")
            lines.append("  - The user is continuing the existing dialogue naturally without needing to ping you.")

        lines.append("  - Do NOT greet them again with 'Hello' or 'Nice to hear from you'. Keep the conversation flowing smoothly.")
        lines.append("]")
        return "\n".join(lines)


# Global singleton instance
_conversation_manager = ConversationContextManager(default_timeout_seconds=180.0)

def get_conversation_manager() -> ConversationContextManager:
    return _conversation_manager
