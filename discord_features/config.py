# -*- coding: utf-8 -*-
"""
🌸 KAZUMI CENTRALIZED CONFIGURATION & CORE INFRASTRUCTURE (PHASE 1)
Centralizes:
- Environment variables & precedence rules
- Startup validation & sanitized error reporting
- Feature flags
- Secret registration, redaction filter, and formatter (ensuring zero token / key leaks)
- Dynamic guild & channel settings defaults
"""

import os
import re
import threading
import logging
from typing import Dict, Any, Optional, Set, Tuple, List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("KazumiConfig")

# Thread-safe in-memory registry of exact known secrets to sanitize
_REGISTERED_SECRETS: Set[str] = set()
_REGISTRY_LOCK = threading.RLock()


def register_secret(secret: Optional[str]) -> None:
    """
    Safely registers an exact active secret string in memory for output redaction.
    Only values with length >= 8 are stored to avoid over-redacting common words.
    Never logs or exposes registered values.
    """
    if not secret:
        return
    clean = str(secret).strip()
    # Guard against accidental registration of trivial words or placeholders
    if len(clean) >= 8 and not clean.startswith("your_") and clean.lower() not in ("placeholder", "none", "null", "false", "true"):
        with _REGISTRY_LOCK:
            _REGISTERED_SECRETS.add(clean)


# Sensitive data redaction regex patterns
OPENAI_RE = re.compile(r"\bsk-(?:proj-|admin-)?[a-zA-Z0-9_\-]{15,}\b")
DISCORD_TOKEN_RE = re.compile(r"\b[a-zA-Z0-9_-]{24,32}\.[a-zA-Z0-9_-]{6,12}\.[a-zA-Z0-9_-]{10,45}\b")
BEARER_RE = re.compile(r"(?:Bearer\s+|authorization:\s+)[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE)
HF_RE = re.compile(r"\bhf_[a-zA-Z0-9]{20,}\b")
CRED_URL_RE = re.compile(r"(https?://)[^:\s]+:[^@\s]+@")
WEBHOOK_RE = re.compile(r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[a-zA-Z0-9_-]+")
ASSIGNMENT_RE = re.compile(r"(?i)\b(OPENAI_API_KEY|API_KEY|DISCORD_BOT_TOKEN|DISCORD_TOKEN)\s*=\s*['\"]?[^\s'\"#\r\n]{8,}['\"]?")


def sanitize_secrets(text: Any) -> str:
    """Masks API keys, bot tokens, auth headers, and webhook URLs from any text or log output."""
    if text is None:
        return ""
    clean = str(text)

    # 1. Redact exact registered secret values first (longest first)
    with _REGISTRY_LOCK:
        if _REGISTERED_SECRETS:
            for sec in sorted(_REGISTERED_SECRETS, key=len, reverse=True):
                if sec in clean:
                    clean = clean.replace(sec, "[REDACTED_SECRET]")

    # 2. Redact patterns
    clean = CRED_URL_RE.sub(r"\1[REDACTED_AUTH]@", clean)
    clean = WEBHOOK_RE.sub("[REDACTED_WEBHOOK_URL]", clean)
    clean = BEARER_RE.sub("Bearer [REDACTED_SECRET]", clean)
    clean = OPENAI_RE.sub("[REDACTED_SECRET]", clean)
    clean = HF_RE.sub("[REDACTED_SECRET]", clean)
    clean = DISCORD_TOKEN_RE.sub("[REDACTED_SECRET]", clean)
    clean = ASSIGNMENT_RE.sub(r"\1=[REDACTED_SECRET]", clean)
    return clean


class SanitizedLogFormatter(logging.Formatter):
    """Custom logging formatter that guarantees zero sensitive token leakage in messages, exceptions, and stacks."""
    def format(self, record: logging.LogRecord) -> str:
        orig = super().format(record)
        return sanitize_secrets(orig)

    def formatException(self, ei) -> str:
        orig = super().formatException(ei)
        return sanitize_secrets(orig)

    def formatStack(self, stack_info: str) -> str:
        orig = super().formatStack(stack_info)
        return sanitize_secrets(orig)


class RedactionFilter(logging.Filter):
    """Logging filter that sanitizes record.msg and record.args directly."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: (sanitize_secrets(v) if isinstance(v, str) else v) for k, v in record.args.items()}
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(sanitize_secrets(v) if isinstance(v, str) else v for v in record.args)
        return True


def install_global_redactor() -> None:
    """Attaches redaction filter and sanitized formatter to root logger and handlers."""
    root_logger = logging.getLogger()
    redaction_filter = RedactionFilter()

    # Register known environment secrets
    for env_var in ("DISCORD_BOT_TOKEN", "OPENAI_API_KEY", "API_KEY", "ANTHROPIC_API_KEY"):
        val = os.environ.get(env_var, "").strip()
        if val and len(val) >= 8:
            register_secret(val)

    if not any(isinstance(f, RedactionFilter) for f in root_logger.filters):
        root_logger.addFilter(redaction_filter)

    for handler in root_logger.handlers:
        if not any(isinstance(f, RedactionFilter) for f in handler.filters):
            handler.addFilter(redaction_filter)
        if handler.formatter:
            fmt_str = getattr(handler.formatter, "_fmt", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            handler.setFormatter(SanitizedLogFormatter(fmt_str))
        else:
            handler.setFormatter(SanitizedLogFormatter())


class KazumiConfig:
    """Central configuration manager for Kazumi bot and features."""

    # Core Environment Variables
    DISCORD_BOT_TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    DISCORD_CHANNEL_ID: Optional[str] = os.environ.get("DISCORD_CHANNEL_ID")
    PREFIX: str = os.environ.get("PREFIX", "!k ").strip()
    OPENAI_API_KEY: str = (os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY", "")).strip()
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    PORT: int = int(os.environ.get("PORT", "10000"))

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
    def get_openai_key(cls) -> Tuple[Optional[str], str]:
        """
        Enforces OpenAI key precedence:
        1. Non-empty OPENAI_API_KEY
        2. Non-empty API_KEY (with deprecation warning)
        Never logs key values.
        """
        k = os.environ.get("OPENAI_API_KEY", "").strip()
        if k:
            return k, "OPENAI_API_KEY"
        legacy = os.environ.get("API_KEY", "").strip()
        if legacy:
            logger.warning("API_KEY is deprecated; use OPENAI_API_KEY instead.")
            return legacy, "API_KEY (deprecated alias)"
        return None, "missing"

    @classmethod
    def validate_startup_config(cls) -> Tuple[bool, List[str]]:
        """
        Validates required configuration at startup.
        Missing variables produce sanitized errors naming the variable.
        """
        errors = []
        token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
        if not token or token == "your_discord_bot_token_here":
            errors.append("DISCORD_BOT_TOKEN is missing or unconfigured placeholder.")
        return len(errors) == 0, errors

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
