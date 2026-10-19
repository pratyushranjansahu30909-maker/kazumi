# -*- coding: utf-8 -*-
"""
🌸 Kazumi OpenAI Security, Key Validation & Reliability Guard
Centralizes:
- Canonical API key validation & placeholder rejection
- Safe credential synchronization (OPENAI_API_KEY <-> API_KEY)
- Distinct error categorization (401 Auth, 403 Forbidden, 429 Quota vs RateLimit, 5xx Transient, Timeout)
- Circuit breakers (Auth lock, Quota cooldown, Transient backoff)
- Bounded concurrency and per-user sliding window rate limiting
- Deduplication of incoming AI requests
- Exponential backoff with jitter (bounded, non-infinite)
- Zero secret leakage in logs, exceptions, and telemetry
"""

import os
import sys
import time
import math
import random
import logging
import threading
from typing import Optional, Dict, Any, Tuple, List, Callable

logger = logging.getLogger("OpenAIReliability")

# Known placeholder patterns
PLACEHOLDER_SUBSTRINGS = (
    "your_openai_api_key_here",
    "your_api_key_here",
    "sk-your",
    "placeholder",
    "sk-placeholder",
    "dummy",
    "sk-dummy",
    "replace_with",
    "insert_key",
    "none",
    "null",
)

def is_placeholder_key(key: Optional[str]) -> bool:
    """Detects whether an API key is a dummy or template placeholder."""
    if not key:
        return True
    key_clean = key.strip().lower()
    if len(key_clean) < 20:
        return True
    if not key_clean.startswith("sk-"):
        return True
    for p in PLACEHOLDER_SUBSTRINGS:
        if p in key_clean:
            return True
    return False


def validate_openai_config() -> Tuple[bool, str, Optional[str]]:
    """
    Validates canonical OpenAI API key configuration safely without leaking credentials.
    Synchronizes OPENAI_API_KEY and API_KEY in os.environ when valid.
    
    Returns:
        (is_valid: bool, status_message: str, resolved_key: Optional[str])
    """
    raw_key = os.environ.get("OPENAI_API_KEY")
    source = "OPENAI_API_KEY"
    if not raw_key:
        raw_key = os.environ.get("API_KEY")
        if raw_key:
            source = "API_KEY (legacy alias)"
            logger.warning("API_KEY is deprecated; use OPENAI_API_KEY instead.")

    # Fallback to local .env if not found in environment
    if not raw_key:
        for env_path in [".env", "../.env"]:
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8-sig") as f:
                        for line in f:
                            line_s = line.strip()
                            if line_s and not line_s.startswith("#") and "=" in line_s:
                                k, v = line_s.split("=", 1)
                                k_s = k.strip()
                                if k_s in ("OPENAI_API_KEY", "API_KEY"):
                                    candidate = v.strip().strip('"').strip("'")
                                    if candidate and not is_placeholder_key(candidate):
                                        raw_key = candidate
                                        source = f".env ({k_s})"
                                        if k_s == "API_KEY":
                                            logger.warning("API_KEY is deprecated; use OPENAI_API_KEY instead.")
                                        if k_s == "OPENAI_API_KEY":
                                            break
                except Exception:
                    pass
            if raw_key:
                break

    if not raw_key or not raw_key.strip():
        return False, "OpenAI API key is missing. Set OPENAI_API_KEY in environment settings.", None

    clean_key = raw_key.strip()

    if is_placeholder_key(clean_key):
        return False, f"OpenAI API key from {source} is an unconfigured placeholder value.", None

    # Harmonize canonical and legacy variables
    os.environ["OPENAI_API_KEY"] = clean_key
    os.environ["API_KEY"] = clean_key

    try:
        from discord_features.config import register_secret
        register_secret(clean_key)
    except Exception:
        pass

    masked_prefix = clean_key[:7] + "..." if len(clean_key) >= 7 else "sk-..."
    return True, f"Valid OpenAI API key configured via {source} ({masked_prefix}, len={len(clean_key)}).", clean_key


class OpenAIReliabilityGuard:
    """
    Centralized guardian for OpenAI API requests.
    Enforces concurrency bounds, rate limits, circuit breaking, bounded backoff,
    and strict secret sanitization.
    """
    _instance: Optional["OpenAIReliabilityGuard"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(OpenAIReliabilityGuard, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        # State tracking
        self._auth_broken = False
        self._quota_cooldown_until: float = 0.0
        self._transient_cooldown_until: float = 0.0
        self._consecutive_transient_failures: int = 0
        
        # Concurrency & Rate Limiting
        self._concurrency_semaphore = threading.BoundedSemaphore(3)
        self._user_requests: Dict[str, List[float]] = {}
        self._recent_signatures: Dict[str, float] = {}
        self._state_lock = threading.Lock()

        # Telemetry metrics (strictly non-sensitive)
        self.stats = {
            "total_calls": 0,
            "success_calls": 0,
            "auth_errors": 0,
            "quota_errors": 0,
            "rate_limit_errors": 0,
            "transient_errors": 0,
            "timeout_errors": 0,
            "client_errors": 0,
            "circuit_breaker_trips": 0,
            "rate_limit_drops": 0,
            "duplicate_drops": 0,
        }

        # Validate configuration
        self.is_valid, self.validation_msg, self.api_key = validate_openai_config()
        self._client = None
        if self.is_valid and self.api_key:
            self._init_client()

    def _init_client(self):
        """Initializes client safely."""
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, timeout=12.0)
            logger.info("🌸 OpenAIReliabilityGuard: OpenAI client initialized successfully.")
        except Exception as e:
            logger.warning(f"🌸 OpenAIReliabilityGuard: Client initialization deferred: {e}")
            self._client = None

    def reload_credentials(self) -> Tuple[bool, str]:
        """Reloads and validates credentials after an environment update or key rotation."""
        with self._state_lock:
            self.is_valid, self.validation_msg, self.api_key = validate_openai_config()
            self._auth_broken = False
            self._quota_cooldown_until = 0.0
            self._transient_cooldown_until = 0.0
            self._consecutive_transient_failures = 0
            if self.is_valid and self.api_key:
                self._init_client()
            else:
                self._client = None
            return self.is_valid, self.validation_msg

    def is_available(self) -> bool:
        """Returns True if the engine can accept new OpenAI API requests."""
        if not self.is_valid or self._client is None or self._auth_broken:
            return False
        now = time.time()
        if now < self._quota_cooldown_until:
            return False
        if now < self._transient_cooldown_until:
            return False
        return True

    def check_user_rate_limit(self, user_id: str, max_requests: int = 5, window_seconds: float = 10.0) -> bool:
        """
        Sliding window per-user rate limit check.
        Returns True if request is allowed, False if rate limit exceeded.
        """
        if not user_id:
            return True
        now = time.time()
        with self._state_lock:
            history = self._user_requests.setdefault(str(user_id), [])
            # Prune old timestamps
            self._user_requests[str(user_id)] = [t for t in history if now - t < window_seconds]
            if len(self._user_requests[str(user_id)]) >= max_requests:
                self.stats["rate_limit_drops"] += 1
                return False
            self._user_requests[str(user_id)].append(now)
            return True

    def is_duplicate_request(self, user_id: str, prompt: str, ttl_seconds: float = 4.0) -> bool:
        """
        Detects immediate duplicate prompt submissions from the same user to prevent race conditions.
        """
        if not user_id or not prompt:
            return False
        sig = f"{user_id}:{hash(prompt)}"
        now = time.time()
        with self._state_lock:
            # Clean expired signatures
            self._recent_signatures = {k: v for k, v in self._recent_signatures.items() if now - v < ttl_seconds}
            if sig in self._recent_signatures:
                self.stats["duplicate_drops"] += 1
                return True
            self._recent_signatures[sig] = now
            return False

    def execute_completion(
        self,
        call_fn: Callable[[], Any],
        user_id: Optional[str] = None,
        max_retries: int = 2
    ) -> Optional[Any]:
        """
        Executes an OpenAI API operation with bounded concurrency, exponential backoff,
        jitter, circuit breakers, and comprehensive error categorization.
        
        Returns result or None (triggering local fallback).
        """
        if not self.is_available():
            return None

        if user_id and not self.check_user_rate_limit(user_id):
            logger.warning(f"🌸 [RATE_LIMIT] Per-user rate limit reached for {user_id}. Using local fallback.")
            return None

        # Concurrency limit
        acquired = self._concurrency_semaphore.acquire(blocking=True, timeout=3.0)
        if not acquired:
            logger.warning("🌸 [CONCURRENCY] Maximum simultaneous OpenAI requests reached. Using local fallback.")
            return None

        try:
            return self._execute_with_retry(call_fn, max_retries=max_retries)
        finally:
            self._concurrency_semaphore.release()

    def _execute_with_retry(self, call_fn: Callable[[], Any], max_retries: int = 2) -> Optional[Any]:
        import openai

        for attempt in range(max_retries + 1):
            with self._state_lock:
                self.stats["total_calls"] += 1

            try:
                res = call_fn()
                with self._state_lock:
                    self.stats["success_calls"] += 1
                    self._consecutive_transient_failures = 0
                return res

            except openai.AuthenticationError as e:
                with self._state_lock:
                    self.stats["auth_errors"] += 1
                    should_log = not self._auth_broken
                    self._auth_broken = True
                    self.stats["circuit_breaker_trips"] += 1
                if should_log:
                    logger.error("🛑 [OPENAI_AUTH_ERROR] HTTP 401 Unauthorized. Key is invalid or revoked. Tripping circuit breaker to prevent repeated failures.")
                return None

            except openai.PermissionDeniedError as e:
                with self._state_lock:
                    self.stats["client_errors"] += 1
                logger.error("🛑 [OPENAI_PERMISSION_ERROR] HTTP 403 Forbidden. Access restricted or project policy violation.")
                return None

            except openai.RateLimitError as e:
                err_text = str(e).lower()
                is_quota = "quota" in err_text or "insufficient_quota" in err_text or getattr(e, "code", "") == "insufficient_quota"
                
                if is_quota:
                    with self._state_lock:
                        self.stats["quota_errors"] += 1
                        self._quota_cooldown_until = time.time() + 300.0  # 5 min cooldown
                        self.stats["circuit_breaker_trips"] += 1
                    logger.error("🛑 [OPENAI_QUOTA_EXHAUSTED] Account quota / billing limit reached. Entering 5-minute offline fallback mode.")
                    return None
                else:
                    with self._state_lock:
                        self.stats["rate_limit_errors"] += 1

                    # Check Retry-After
                    retry_after = 1.0
                    if hasattr(e, "response") and e.response and "retry-after" in e.response.headers:
                        try:
                            retry_after = min(float(e.response.headers["retry-after"]), 3.0)
                        except (ValueError, TypeError):
                            pass

                    if attempt < max_retries:
                        jitter = random.uniform(0.1, 0.4)
                        delay = min(retry_after + jitter, 3.5)
                        logger.warning(f"⚠️ [OPENAI_RATE_LIMIT] HTTP 429 Rate limited. Retrying in {delay:.2f}s (Attempt {attempt+1}/{max_retries})...")
                        time.sleep(delay)
                        continue
                    else:
                        logger.warning("⚠️ [OPENAI_RATE_LIMIT] Rate limit retries exhausted. Using local fallback.")
                        return None

            except (openai.APITimeoutError, TimeoutError) as e:
                with self._state_lock:
                    self.stats["timeout_errors"] += 1
                logger.warning(f"⚠️ [OPENAI_TIMEOUT] API request timed out (Attempt {attempt+1}/{max_retries+1}).")
                if attempt < max_retries:
                    delay = 0.5 + random.uniform(0.1, 0.3)
                    time.sleep(delay)
                    continue
                return None

            except (openai.InternalServerError, openai.APIConnectionError) as e:
                with self._state_lock:
                    self.stats["transient_errors"] += 1
                    self._consecutive_transient_failures += 1
                    if self._consecutive_transient_failures >= 3:
                        self._transient_cooldown_until = time.time() + 30.0
                        self.stats["circuit_breaker_trips"] += 1

                if attempt < max_retries:
                    delay = (0.8 * (2 ** attempt)) + random.uniform(0.1, 0.5)
                    logger.warning(f"⚠️ [OPENAI_TRANSIENT] Temporary connection/5xx error ({type(e).__name__}). Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.warning(f"⚠️ [OPENAI_TRANSIENT] Server retry limit reached ({type(e).__name__}). Falling back cleanly.")
                    return None

            except openai.NotFoundError as e:
                with self._state_lock:
                    self.stats["client_errors"] += 1
                logger.error(f"🛑 [OPENAI_MODEL_ERROR] Requested model not found or unavailable: {e}")
                return None

            except Exception as e:
                with self._state_lock:
                    self.stats["client_errors"] += 1
                logger.warning(f"⚠️ [OPENAI_CALL_FAILED] Non-retryable error ({type(e).__name__}): {e}")
                return None

        return None

    def get_health_telemetry(self) -> Dict[str, Any]:
        """Provides sanitized telemetry regarding OpenAI integration health."""
        now = time.time()
        quota_cooldown = max(0, int(self._quota_cooldown_until - now))
        transient_cooldown = max(0, int(self._transient_cooldown_until - now))
        
        status = "HEALTHY"
        if not self.is_valid:
            status = "CONFIGURATION_ERROR"
        elif self._auth_broken:
            status = "AUTH_FAILED"
        elif quota_cooldown > 0:
            status = f"QUOTA_COOLDOWN_{quota_cooldown}s"
        elif transient_cooldown > 0:
            status = f"TRANSIENT_COOLDOWN_{transient_cooldown}s"

        return {
            "status": status,
            "is_available": self.is_available(),
            "auth_broken": self._auth_broken,
            "quota_cooldown_seconds": quota_cooldown,
            "transient_cooldown_seconds": transient_cooldown,
            "stats": dict(self.stats)
        }

    def is_auth_broken(self) -> bool:
        """Returns True if OpenAI API is disabled due to invalid credentials (HTTP 401)."""
        return self._auth_broken

    def get_degraded_reason(self) -> Optional[str]:
        """Returns a sanitized description of current degradation if unavailable."""
        if not self.is_valid:
            return "Configuration missing or placeholder"
        if self._auth_broken:
            return "Authentication failure (invalid or revoked API key)"
        now = time.time()
        if now < self._quota_cooldown_until:
            return f"Quota exhausted (cooldown remaining: {int(self._quota_cooldown_until - now)}s)"
        if now < self._transient_cooldown_until:
            return f"Transient connection errors (backoff remaining: {int(self._transient_cooldown_until - now)}s)"
        return None

    def get_user_facing_status_message(self) -> str:
        """Returns a user-friendly, safe message explaining degraded status without secrets."""
        if self._auth_broken:
            return "🌸 My AI thoughts are temporarily resting due to an authentication setup issue. Non-AI commands and server features remain fully active!"
        if time.time() < self._quota_cooldown_until:
            return "🌸 My AI mind is resting due to high activity quota limits. Non-AI commands remain fully active!"
        return "🌸 My AI thoughts are temporarily resting. Non-AI commands and server features remain fully active!"


# Singleton accessor
def get_reliability_guard() -> OpenAIReliabilityGuard:
    return OpenAIReliabilityGuard()
