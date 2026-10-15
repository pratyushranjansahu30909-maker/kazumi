# -*- coding: utf-8 -*-
"""
🌸 Kazumi Discord Features — Persistent 24/7 Monitoring & Alerting System
========================================================================
Provides:
1. Runtime Health & Gateway Heartbeat Monitoring
2. Durable Event Ledger for Member Join / Departure Events
3. Event Delivery State Machine (RECEIVED -> PROCESSING -> SENT / FAILED)
4. Webhook Alerting with Cooldowns, Deduplication, and Storm Suppression
5. Comprehensive Liveness, Readiness, and Health State Assessment
"""

import os
import json
import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
import aiohttp
import discord

logger = logging.getLogger("KazumiMonitoring")

# Environment Variable Configurations with Safe Defaults
MONITORING_ENABLED_RAW = os.environ.get("KAZUMI_MONITORING_ENABLED", "1").strip().lower()
MONITORING_ENABLED = MONITORING_ENABLED_RAW not in ("0", "false", "no", "off")

ALERT_WEBHOOK_URL = os.environ.get("KAZUMI_ALERT_WEBHOOK_URL", "").strip()

try:
    ALERT_COOLDOWN_SECONDS = float(os.environ.get("KAZUMI_ALERT_COOLDOWN_SECONDS", "300"))
except ValueError:
    ALERT_COOLDOWN_SECONDS = 300.0

try:
    EVENT_RETRY_LIMIT = int(os.environ.get("KAZUMI_EVENT_RETRY_LIMIT", "3"))
except ValueError:
    EVENT_RETRY_LIMIT = 3

try:
    EVENT_RETRY_BASE_SECONDS = float(os.environ.get("KAZUMI_EVENT_RETRY_BASE_SECONDS", "2.0"))
except ValueError:
    EVENT_RETRY_BASE_SECONDS = 2.0

try:
    GATEWAY_TIMEOUT_SECONDS = float(os.environ.get("KAZUMI_GATEWAY_TIMEOUT_SECONDS", "60.0"))
except ValueError:
    GATEWAY_TIMEOUT_SECONDS = 60.0


# Storage Directory
ISA_MEMORY_DIR = os.environ.get("ISA_MEMORY_DIR") or os.environ.get("DATA_DIR") or "isa_memory"
EVENT_LEDGER_PATH = os.path.join(ISA_MEMORY_DIR, "event_ledger.json")
RUNTIME_STATE_PATH = os.path.join(ISA_MEMORY_DIR, "runtime_monitor.json")


def _atomic_json_write(filepath: str, data: Any) -> bool:
    """Safely and atomically writes JSON data with temp file and Windows retry."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        tmp_path = f"{filepath}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())

        for attempt in range(4):
            try:
                os.replace(tmp_path, filepath)
                return True
            except (PermissionError, OSError):
                if attempt < 3:
                    time.sleep(0.05 * (attempt + 1))
                else:
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except Exception:
                            pass
                    os.rename(tmp_path, filepath)
                    return True
    except Exception as e:
        logger.warning(f"Failed atomic write to {filepath}: {e}")
        return False


def _safe_mask_url(url: str) -> str:
    """Masks secret tokens inside webhook URLs for logging."""
    if not url:
        return "None"
    try:
        parts = url.split("/")
        if len(parts) >= 2:
            parts[-1] = "***" + parts[-1][-4:] if len(parts[-1]) > 4 else "***"
            return "/".join(parts)
    except Exception:
        pass
    return "***[MASKED_URL]***"


# ==============================================================================
# 1. ALERT MANAGER (Deduplication, Cooldowns, Safe Webhook Dispatch)
# ==============================================================================
class AlertManager:
    """
    Handles administrator alerts over Discord webhook with deduplication,
    bounded timeouts, rate-limit awareness, and storm prevention.
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        cooldown_seconds: float = ALERT_COOLDOWN_SECONDS,
        enabled: bool = MONITORING_ENABLED
    ):
        self.webhook_url = webhook_url or ALERT_WEBHOOK_URL
        self.cooldown_seconds = cooldown_seconds
        self.enabled = enabled
        self._last_alert_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    def is_configured(self) -> bool:
        return bool(self.enabled and self.webhook_url and self.webhook_url.startswith("http"))

    async def send_alert(
        self,
        incident_type: str,
        severity: str,
        message: str,
        guild_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        correlation_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> bool:
        """
        Dispatches an alert webhook if configured and not throttled by cooldown.
        Severity: INFO, WARNING, ERROR, CRITICAL
        """
        if not self.is_configured():
            logger.debug(f"[ALERT_SKIPPED] Monitoring alert not sent (webhook not configured or disabled): {incident_type}")
            return False

        now = time.time()
        dedup_key = f"{incident_type}:{guild_id or 0}:{channel_id or 0}"

        async with self._lock:
            last_time = self._last_alert_times.get(dedup_key, 0.0)
            if not force and (now - last_time < self.cooldown_seconds):
                logger.debug(f"[ALERT_THROTTLED] Throttling alert for {dedup_key} (cooldown: {self.cooldown_seconds}s)")
                return False
            self._last_alert_times[dedup_key] = now

        # Build Discord webhook embed payload
        color_map = {
            "INFO": 0x3b82f6,      # Blue
            "WARNING": 0xf59e0b,   # Amber
            "ERROR": 0xef4444,     # Red
            "CRITICAL": 0x991b1b,  # Dark Red
            "RECOVERY": 0x10b981   # Green
        }
        color = color_map.get(severity.upper(), 0xef4444)

        fields = [
            {"name": "🚨 Incident", "value": f"`{incident_type}`", "inline": True},
            {"name": "⚠️ Severity", "value": f"`{severity}`", "inline": True},
            {"name": "🕒 Time (UTC)", "value": f"<t:{int(now)}:F>", "inline": True},
        ]
        if guild_id:
            fields.append({"name": "🌐 Guild ID", "value": f"`{guild_id}`", "inline": True})
        if channel_id:
            fields.append({"name": "💬 Channel ID", "value": f"`{channel_id}`", "inline": True})
        if correlation_id:
            fields.append({"name": "🔗 Correlation ID", "value": f"`{correlation_id}`", "inline": True})

        if extra:
            for k, v in list(extra.items())[:5]:
                fields.append({"name": f"🔹 {k}", "value": f"`{str(v)[:100]}`", "inline": True})

        payload = {
            "username": "Kazumi Sentry 🌸",
            "embeds": [
                {
                    "title": f"🌸 Kazumi Sentry Alert • {incident_type}",
                    "description": message[:1900],
                    "color": color,
                    "fields": fields,
                    "footer": {"text": "Kazumi Production Monitor • Bot-Hosting.net"},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ]
        }

        try:
            timeout = aiohttp.ClientTimeout(total=5.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.webhook_url, json=payload) as resp:
                    if resp.status in (200, 204):
                        logger.info(f"[ALERT_DISPATCHED] Alert '{incident_type}' sent to webhook successfully.")
                        return True
                    else:
                        logger.warning(f"[ALERT_DISPATCH_FAILED] Webhook returned status {resp.status}")
                        return False
        except Exception as e:
            logger.warning(f"[ALERT_DISPATCH_ERROR] Failed to post alert to webhook: {e}")
            return False


# ==============================================================================
# 2. PERSISTENT EVENT LEDGER (Durable Join / Leave Tracking & State Machine)
# ==============================================================================
class EventState:
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_PERMANENT = "FAILED_PERMANENT"


class EventLedger:
    """
    Maintains a durable, bounded persistent ledger of member join/leave events.
    Guarantees state machine: RECEIVED -> PROCESSING -> SENT / FAILED.
    Recovers abandoned PROCESSING records across container restarts.
    """

    MAX_ENTRIES = 500  # Bound ledger size to prevent memory & disk bloat

    def __init__(self, ledger_path: str = EVENT_LEDGER_PATH):
        self.ledger_path = ledger_path
        self._lock = asyncio.Lock()
        self._events: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self):
        """Loads events from disk into memory cache."""
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._events = data.get("events", {})
            except Exception as e:
                logger.warning(f"Failed to load event ledger from {self.ledger_path}: {e}")
                self._events = {}

    def save(self) -> bool:
        """Atomically saves memory cache to disk."""
        data = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(self._events),
            "events": self._events
        }
        return _atomic_json_write(self.ledger_path, data)

    def generate_event_id(self, event_type: str, guild_id: int, member_id: int, timestamp: Optional[float] = None) -> str:
        ts = int(timestamp or time.time())
        return f"{event_type}_{guild_id}_{member_id}_{ts}"

    async def record_received(
        self,
        event_type: str,
        guild_id: int,
        member_id: int,
        member_name: str,
        channel_id: Optional[int] = None
    ) -> str:
        """Records initial RECEIVED state in durable ledger."""
        now = time.time()
        event_id = self.generate_event_id(event_type, guild_id, member_id, now)

        async with self._lock:
            # Bound cache size: prune oldest terminal records (SENT, FAILED_PERMANENT) only
            # Never prune PROCESSING, RECEIVED, or FAILED_RETRYABLE records awaiting recovery
            if len(self._events) >= self.MAX_ENTRIES:
                prunable_keys = [
                    k for k, v in self._events.items()
                    if v.get("state") in (EventState.SENT, EventState.FAILED_PERMANENT)
                ]
                if prunable_keys:
                    prunable_keys.sort(key=lambda k: self._events[k].get("created_at_epoch", 0.0))
                    excess = len(self._events) - self.MAX_ENTRIES + 1
                    for k in prunable_keys[:excess]:
                        del self._events[k]

            self._events[event_id] = {
                "event_id": event_id,
                "event_type": event_type,
                "guild_id": guild_id,
                "member_id": member_id,
                "member_name": member_name,
                "channel_id": channel_id,
                "state": EventState.RECEIVED,
                "retry_count": 0,
                "last_error": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_at_epoch": now,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None
            }
            self.save()
        return event_id

    async def record_processing(self, event_id: str, channel_id: Optional[int] = None) -> bool:
        """Transitions state to PROCESSING."""
        async with self._lock:
            if event_id not in self._events:
                return False
            rec = self._events[event_id]
            rec["state"] = EventState.PROCESSING
            if channel_id:
                rec["channel_id"] = channel_id
            rec["handler_start_time"] = datetime.now(timezone.utc).isoformat()
            rec["updated_at"] = datetime.now(timezone.utc).isoformat()
            return self.save()

    async def record_sent(self, event_id: str, message_id: Optional[int] = None) -> bool:
        """Transitions state to SENT on verified delivery."""
        async with self._lock:
            if event_id not in self._events:
                return False
            rec = self._events[event_id]
            rec["state"] = EventState.SENT
            rec["message_id"] = message_id
            rec["completed_at"] = datetime.now(timezone.utc).isoformat()
            rec["updated_at"] = datetime.now(timezone.utc).isoformat()
            return self.save()

    async def record_failure(
        self,
        event_id: str,
        error_category: str,
        error_message: str,
        is_permanent: bool = False
    ) -> bool:
        """Transitions state to FAILED_PERMANENT or FAILED_RETRYABLE."""
        async with self._lock:
            if event_id not in self._events:
                return False
            rec = self._events[event_id]
            rec["retry_count"] = rec.get("retry_count", 0) + 1
            rec["last_error"] = f"{error_category}: {error_message}"
            rec["state"] = EventState.FAILED_PERMANENT if is_permanent else EventState.FAILED_RETRYABLE
            rec["updated_at"] = datetime.now(timezone.utc).isoformat()
            if is_permanent:
                rec["completed_at"] = datetime.now(timezone.utc).isoformat()
            return self.save()

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        return self._events.get(event_id)

    def get_abandoned_processing_events(self, max_age_seconds: float = 300.0) -> List[Dict[str, Any]]:
        """Identifies events left in PROCESSING state after an abrupt shutdown or crash."""
        now = time.time()
        abandoned = []
        for rec in self._events.values():
            if rec.get("state") == EventState.PROCESSING:
                created = rec.get("created_at_epoch", 0.0)
                if now - created > max_age_seconds:
                    abandoned.append(rec)
        return abandoned

    async def recover_abandoned_events(self) -> int:
        """Marks old abandoned PROCESSING events as FAILED_RETRYABLE to allow investigation/retry."""
        abandoned = self.get_abandoned_processing_events()
        if not abandoned:
            return 0
        async with self._lock:
            count = 0
            for rec in abandoned:
                rec["state"] = EventState.FAILED_RETRYABLE
                rec["last_error"] = "PROCESS_RESTART_ABANDONED: Recovered from unfinished state after restart"
                rec["updated_at"] = datetime.now(timezone.utc).isoformat()
                count += 1
            self.save()
            return count

    def get_stats(self) -> Dict[str, int]:
        counts = {
            "total": len(self._events),
            "received": 0,
            "processing": 0,
            "sent": 0,
            "failed_retryable": 0,
            "failed_permanent": 0
        }
        for rec in self._events.values():
            st = rec.get("state", "").lower()
            if st in counts:
                counts[st] += 1
        return counts


# ==============================================================================
# 3. RUNTIME MONITOR (Gateway Heartbeat & Liveness Coordinator)
# ==============================================================================
class BotMonitor:
    """
    Coordinates bot runtime health, Gateway heartbeat evaluation,
    liveness/readiness reporting, and automatic failure alerts.
    """

    _instance: Optional["BotMonitor"] = None

    def __init__(self, bot: Optional[discord.Client] = None):
        self.bot = bot
        self.start_time = time.time()
        self.pid = os.getpid()
        self.is_connected = False
        self.last_connect_time: Optional[float] = None
        self.last_disconnect_time: Optional[float] = None
        self.last_heartbeat_time: float = time.time()
        self.last_successful_api_time: float = time.time()
        self.reconnect_failures_count: int = 0
        self.monitoring_task: Optional[asyncio.Task] = None
        self.alert_manager = AlertManager()
        self.event_ledger = EventLedger()
        self._lock = asyncio.Lock()

        # Track restart count across deployments in persistent runtime state
        self.restart_count = self._load_and_increment_restart_count()

    @classmethod
    def get_instance(cls, bot: Optional[discord.Client] = None) -> "BotMonitor":
        if cls._instance is None:
            cls._instance = cls(bot)
        elif bot is not None and cls._instance.bot is None:
            cls._instance.bot = bot
        return cls._instance

    def _load_and_increment_restart_count(self) -> int:
        """Loads and increments the persistent boot counter in runtime_monitor.json."""
        current_count = 0
        try:
            if os.path.exists(RUNTIME_STATE_PATH):
                with open(RUNTIME_STATE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    current_count = int(data.get("restart_count", 0))
        except Exception:
            pass

        new_count = current_count + 1
        payload = {
            "restart_count": new_count,
            "last_boot_time": datetime.now(timezone.utc).isoformat(),
            "pid": self.pid
        }
        _atomic_json_write(RUNTIME_STATE_PATH, payload)
        return new_count

    # --------------------------------------------------------------------------
    # Lifecycle Event Hooks
    # --------------------------------------------------------------------------
    def record_connect(self):
        self.is_connected = True
        self.last_connect_time = time.time()
        self.last_heartbeat_time = time.time()
        self.reconnect_failures_count = 0
        logger.info(f"[MONITOR] Gateway connection established (PID: {self.pid}, Boot #{self.restart_count})")

    def record_ready(self):
        self.is_connected = True
        self.last_connect_time = time.time()
        self.last_heartbeat_time = time.time()
        self.last_successful_api_time = time.time()
        self.reconnect_failures_count = 0
        logger.info("[MONITOR] Gateway connection ready and initialized.")

    def record_resumed(self):
        self.is_connected = True
        self.last_heartbeat_time = time.time()
        self.last_successful_api_time = time.time()
        self.reconnect_failures_count = 0
        logger.info("[MONITOR] Gateway session resumed.")

    def record_disconnect(self):
        self.is_connected = False
        self.last_disconnect_time = time.time()
        self.reconnect_failures_count += 1
        logger.warning(f"[MONITOR] Gateway disconnected (Attempt #{self.reconnect_failures_count}).")

    def record_api_interaction(self):
        self.last_successful_api_time = time.time()

    # --------------------------------------------------------------------------
    # Health Assessment & Telemetry
    # --------------------------------------------------------------------------
    def get_health_status(self) -> Dict[str, Any]:
        """Evaluates overall health and returns comprehensive telemetry."""
        now = time.time()
        uptime = round(now - self.start_time, 1)

        # Determine Gateway Latency
        latency_ms = 0.0
        if self.bot and getattr(self.bot, "latency", None):
            latency_ms = round(self.bot.latency * 1000.0, 1)

        # Determine Disconnection Duration
        disconnect_duration = 0.0
        if not self.is_connected and self.last_disconnect_time:
            disconnect_duration = round(now - self.last_disconnect_time, 1)

        # Liveness: True if Python process and event loop are actively executing
        liveness = True

        # Readiness: True if Gateway connected, ready, and latency within reasonable bound (<5000ms)
        is_ready = bool(self.bot and self.bot.is_ready() and self.is_connected)
        readiness = is_ready and (latency_ms < 5000.0)

        # State Classification
        if readiness:
            if latency_ms > 1500.0:
                state = "degraded"
            else:
                state = "healthy"
        elif not self.is_connected:
            state = "disconnected"
        else:
            state = "starting"

        return {
            "liveness": liveness,
            "readiness": readiness,
            "state": state,
            "is_connected": self.is_connected,
            "uptime_seconds": uptime,
            "latency_ms": latency_ms,
            "pid": self.pid,
            "restart_count": self.restart_count,
            "disconnect_duration_seconds": disconnect_duration,
            "reconnect_failures": self.reconnect_failures_count,
            "last_heartbeat_ago_seconds": round(now - self.last_heartbeat_time, 1),
            "last_api_interaction_ago_seconds": round(now - self.last_successful_api_time, 1),
            "ledger_stats": self.event_ledger.get_stats(),
            "monitoring_enabled": self.alert_manager.enabled,
            "webhook_configured": self.alert_manager.is_configured(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    # --------------------------------------------------------------------------
    # Background Health Monitor Loop
    # --------------------------------------------------------------------------
    async def start_background_monitor(self):
        """Starts the persistent background health check loop."""
        if self.monitoring_task is not None and not self.monitoring_task.done():
            return
        self.monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info("[MONITOR] Background 24/7 health monitor loop started.")

    async def _monitor_loop(self):
        """Periodically evaluates connection health and dispatches alerts on threshold breaches."""
        was_disconnected = False

        # On startup, attempt to recover any abandoned processing records
        try:
            recovered_count = await self.event_ledger.recover_abandoned_events()
            if recovered_count > 0:
                logger.info(f"[MONITOR] Recovered {recovered_count} abandoned event record(s) from previous run.")
        except Exception as e:
            logger.warning(f"[MONITOR] Failed to recover abandoned events: {e}")

        while True:
            try:
                await asyncio.sleep(20.0)
                now = time.time()

                if self.bot and self.bot.is_ready():
                    self.last_heartbeat_time = now
                    self.is_connected = True

                    # Check if recovering from a past disconnection incident
                    if was_disconnected:
                        was_disconnected = False
                        await self.alert_manager.send_alert(
                            incident_type="GATEWAY_RECOVERED",
                            severity="RECOVERY",
                            message="🌸 Kazumi Discord Gateway connection has fully recovered and is healthy.",
                            extra={"latency_ms": round(self.bot.latency * 1000, 1) if self.bot.latency else 0.0}
                        )
                else:
                    # Gateway is not ready / disconnected
                    if self.last_disconnect_time:
                        elapsed = now - self.last_disconnect_time
                        if elapsed > GATEWAY_TIMEOUT_SECONDS:
                            was_disconnected = True
                            await self.alert_manager.send_alert(
                                incident_type="GATEWAY_DISCONNECTED",
                                severity="CRITICAL",
                                message=(
                                    f"⚠️ Kazumi Discord Gateway has been disconnected for {int(elapsed)} seconds. "
                                    f"Reconnect attempts: {self.reconnect_failures_count}."
                                ),
                                extra={"reconnect_attempts": self.reconnect_failures_count}
                            )

                    if self.reconnect_failures_count >= 5:
                        await self.alert_manager.send_alert(
                            incident_type="REPEATED_RECONNECT_FAILURE",
                            severity="CRITICAL",
                            message=f"🚨 Gateway reconnect failed {self.reconnect_failures_count} consecutive times.",
                            extra={"reconnect_attempts": self.reconnect_failures_count}
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MONITOR] Error in background monitor loop: {e}", exc_info=True)


# ==============================================================================
# 4. DISPATCH HELPER WITH RETRY & PERMISSION AUDIT
# ==============================================================================
def check_channel_permissions(channel: Any, me: Any) -> Tuple[bool, Optional[str]]:
    """
    Audits bot permissions in target channel.
    Returns (True, None) if valid, or (False, reason) if lacking essential permissions.
    """
    if not channel:
        return False, "CHANNEL_NOT_FOUND"

    if hasattr(channel, "permissions_for") and me:
        perms = channel.permissions_for(me)
        if not getattr(perms, "send_messages", False):
            return False, "MISSING_PERMISSION_SEND_MESSAGES"
        if not getattr(perms, "embed_links", False):
            return False, "MISSING_PERMISSION_EMBED_LINKS"

    return True, None


async def execute_with_retry(
    action_coro_fn,
    event_id: str,
    ledger: EventLedger,
    alert_mgr: AlertManager,
    guild_id: int,
    channel_id: Optional[int],
    max_retries: int = EVENT_RETRY_LIMIT,
    base_backoff: float = EVENT_RETRY_BASE_SECONDS
) -> Tuple[bool, Optional[Any]]:
    """
    Executes a Discord send action with bounded exponential backoff for transient errors
    and immediate failure classification for permanent permission/channel errors.
    """
    last_err = None

    for attempt in range(max_retries):
        try:
            await ledger.record_processing(event_id, channel_id)
            result = await action_coro_fn()
            msg_id = getattr(result, "id", None)
            await ledger.record_sent(event_id, msg_id)
            return True, result

        except discord.Forbidden as e:
            # Permanent permission error: do not retry
            last_err = e
            await ledger.record_failure(event_id, "PERMISSIONS_FORBIDDEN", str(e), is_permanent=True)
            await alert_mgr.send_alert(
                incident_type="CHANNEL_PERMISSION_ERROR",
                severity="ERROR",
                message=f"Bot lacks required permissions in destination channel {channel_id}: {e}",
                guild_id=guild_id,
                channel_id=channel_id,
                correlation_id=event_id
            )
            return False, e

        except discord.NotFound as e:
            # Permanent channel missing error: do not retry
            last_err = e
            await ledger.record_failure(event_id, "CHANNEL_NOT_FOUND", str(e), is_permanent=True)
            await alert_mgr.send_alert(
                incident_type="CHANNEL_NOT_FOUND_ERROR",
                severity="ERROR",
                message=f"Destination channel {channel_id} was not found: {e}",
                guild_id=guild_id,
                channel_id=channel_id,
                correlation_id=event_id
            )
            return False, e

        except (discord.RateLimited, discord.HTTPException, asyncio.TimeoutError, ConnectionError, OSError) as e:
            last_err = e
            is_last_attempt = (attempt == max_retries - 1)
            await ledger.record_failure(
                event_id,
                "TRANSIENT_API_ERROR",
                str(e),
                is_permanent=is_last_attempt
            )

            if not is_last_attempt:
                backoff = base_backoff * (2 ** attempt)
                # Respect Discord rate limit retry_after if provided
                retry_after = getattr(e, "retry_after", None)
                if retry_after is not None:
                    try:
                        backoff = max(float(retry_after), backoff)
                    except (ValueError, TypeError):
                        pass
                logger.warning(
                    f"[RETRY] Transient failure on {event_id} (Attempt {attempt+1}/{max_retries}): {e}. "
                    f"Backing off for {backoff:.1f}s..."
                )
                await asyncio.sleep(backoff)
            else:
                logger.error(f"[EXHAUSTED] Retries exhausted for {event_id} after {max_retries} attempts: {e}")
                await alert_mgr.send_alert(
                    incident_type="EVENT_DELIVERY_FAILURE",
                    severity="ERROR",
                    message=f"Message delivery failed after {max_retries} retries: {e}",
                    guild_id=guild_id,
                    channel_id=channel_id,
                    correlation_id=event_id
                )
                return False, e

        except Exception as e:
            # Unexpected general error
            last_err = e
            await ledger.record_failure(event_id, "UNEXPECTED_ERROR", str(e), is_permanent=True)
            await alert_mgr.send_alert(
                incident_type="EVENT_DELIVERY_FAILURE",
                severity="ERROR",
                message=f"Unexpected error during message delivery: {e}",
                guild_id=guild_id,
                channel_id=channel_id,
                correlation_id=event_id
            )
            return False, e

    return False, last_err
