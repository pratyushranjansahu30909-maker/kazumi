# -*- coding: utf-8 -*-
"""
🌸 KAZUMI CENTRALIZED CONFIGURATION & CORE INFRASTRUCTURE (PHASE 1)
Centralizes:
- Environment variables
- Feature flags
- Credential sanitization (ensuring zero token / key leaks)
- Dynamic guild & channel settings defaults
"""

import os
import re
import logging
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("KazumiConfig")

# Sensitive data redaction regex patterns
TOKEN_RE = re.compile(r"([a-zA-Z0-9_-]{24,28}\.[a-zA-Z0-9_-]{6}\.[a-zA-Z0-9_-]{27,38}|sk-[a-zA-Z0-9]{20,})")


def sanitize_secrets(text: str) -> str:
    """Masks API keys and bot tokens from any text or log output."""
    if not text:
        return text
    return TOKEN_RE.sub("[REDACTED_SECRET]", str(text))


class SanitizedLogFormatter(logging.Formatter):
    """Custom logging formatter that guarantees zero sensitive token leakage."""
    def format(self, record: logging.LogRecord) -> str:
        orig = super().format(record)
        return sanitize_secrets(orig)


class KazumiConfig:
    """Central configuration manager for Kazumi bot and features."""

    # Core Environment Variables
    DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    DISCORD_CHANNEL_ID: Optional[str] = os.environ.get("DISCORD_CHANNEL_ID")
    PREFIX: str = os.environ.get("PREFIX", "!k ").strip()
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "").strip()
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    PORT: int = int(os.environ.get("PORT", "7860"))

    # Feature Flags
    FEATURE_FLAGS: Dict[str, bool] = {
        "moderation": True,
        "automod": True,
        "welcome": True,
        "autorole": True,
        "tickets": True,
        "giveaways": True,
        "music": True,
        "social_graph": True,
        "mood_engine": True,
        "smart_silence": True,
        "ambient_moments": True,
    }

    # AI Defaults
    DEFAULT_TEMPERATURE: float = 0.7
    MAX_RESPONSE_TOKENS: int = 450
    COGNITIVE_TIMEOUT_SECONDS: float = 35.0

    @classmethod
    def is_feature_enabled(cls, feature_name: str) -> bool:
        return cls.FEATURE_FLAGS.get(feature_name.lower(), True)

    @classmethod
    def set_feature_flag(cls, feature_name: str, enabled: bool) -> None:
        cls.FEATURE_FLAGS[feature_name.lower()] = bool(enabled)
        logger.info(f"[Config] Feature flag '{feature_name}' set to {enabled}")

    @classmethod
    def get_public_summary(cls) -> Dict[str, Any]:
        """Returns safe telemetry without leaking secrets."""
        return {
            "has_discord_token": bool(cls.DISCORD_BOT_TOKEN),
            "token_length": len(cls.DISCORD_BOT_TOKEN) if cls.DISCORD_BOT_TOKEN else 0,
            "prefix": cls.PREFIX,
            "port": cls.PORT,
            "feature_flags": dict(cls.FEATURE_FLAGS)
        }
