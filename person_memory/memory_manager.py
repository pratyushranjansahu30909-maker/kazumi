"""
🌸 Kazumi Person Memory — Memory Manager
Thread-safe, atomic JSON persistence for person profiles and channel modes.
Stores data reliably under isa_memory/ to prevent corruption on Windows.
"""

import os
import json
import time
import shutil
import threading
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from person_memory.person_profile import PersonProfile

logger = logging.getLogger("KazumiPersonMemory")


class PersonMemoryManager:
    """
    Manages persistent storage of PersonProfiles and ChannelConfigs.
    Uses atomic writes with .tmp and .bak backups.
    """

    def __init__(self, persist_dir: str = "isa_memory"):
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)

        self.profiles_path = os.path.join(self.persist_dir, "person_profiles.json")
        self.channels_path = os.path.join(self.persist_dir, "channel_configs.json")

        self._lock = threading.RLock()
        self._profiles_cache: Dict[str, PersonProfile] = {}
        self._channels_cache: Dict[str, str] = {}  # channel_id -> mode

        self.load_all()

    def _atomic_write_json(self, file_path: str, data: Any) -> bool:
        """Atomically writes JSON with .bak fallback and fsync."""
        try:
            if os.path.exists(file_path):
                shutil.copy2(file_path, file_path + ".bak")

            tmp_path = file_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, file_path)
            return True
        except Exception as e:
            logger.error(f"Failed atomic write to {file_path}: {e}")
            tmp_path = file_path + ".tmp"
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            return False

    def _safe_read_json(self, file_path: str, default: Any) -> Any:
        """Safely reads JSON with fallback to .bak on corruption."""
        for path in [file_path, file_path + ".bak"]:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read {path}: {e}")
        return default

    def load_all(self) -> None:
        """Loads profiles and channel configs from disk into memory."""
        with self._lock:
            # 1. Load Profiles
            raw_profiles = self._safe_read_json(self.profiles_path, {})
            self._profiles_cache = {}
            if isinstance(raw_profiles, dict):
                for uid, pdata in raw_profiles.items():
                    try:
                        self._profiles_cache[str(uid)] = PersonProfile.from_dict(pdata)
                    except Exception as e:
                        logger.warning(f"Error loading profile for {uid}: {e}")

            # 2. Load Channel Configs
            raw_channels = self._safe_read_json(self.channels_path, {})
            self._channels_cache = {}
            if isinstance(raw_channels, dict):
                for cid, cdata in raw_channels.items():
                    if isinstance(cdata, dict) and "mode" in cdata:
                        self._channels_cache[str(cid)] = str(cdata["mode"]).upper()
                    elif isinstance(cdata, str):
                        self._channels_cache[str(cid)] = cdata.upper()

            logger.info(f"Loaded {len(self._profiles_cache)} person profile(s) and {len(self._channels_cache)} channel config(s).")
            # Auto-migrate legacy affection data from profile.json
            self.migrate_legacy_data()

    def migrate_legacy_data(self, profile_json_path: Optional[str] = None) -> int:
        """
        Safely migrates existing session_game_states from profile.json into person_profiles.json.
        Preserves all higher existing scores without destroying anything.
        """
        if profile_json_path is None:
            profile_json_path = os.path.join(self.persist_dir, "profile.json")

        if not os.path.exists(profile_json_path):
            return 0

        migrated_count = 0
        try:
            legacy_data = self._safe_read_json(profile_json_path, {})
            session_game_states = legacy_data.get("session_game_states", {})
            if isinstance(session_game_states, dict):
                for session_id, s_data in session_game_states.items():
                    if not isinstance(s_data, dict):
                        continue
                    # Match discord_user_<uid>
                    uid = None
                    if session_id.startswith("discord_user_"):
                        raw_id = session_id.replace("discord_user_", "").strip()
                        if raw_id.isdigit():
                            uid = raw_id

                    if not uid:
                        continue

                    profile = self.get_profile(uid, display_name=s_data.get("user_name"))
                    changed = False

                    leg_aff = s_data.get("affection_level")
                    if leg_aff is not None and isinstance(leg_aff, (int, float)):
                        leg_aff = int(leg_aff)
                        if leg_aff > profile.affection_level:
                            profile.affection_level = leg_aff
                            profile.lifetime_affection = max(profile.lifetime_affection, leg_aff)
                            changed = True

                    leg_cp = s_data.get("cozy_points")
                    if leg_cp is not None and isinstance(leg_cp, (int, float)):
                        leg_cp = int(leg_cp)
                        if leg_cp > profile.cozy_points:
                            profile.cozy_points = leg_cp
                            changed = True

                    leg_turns = s_data.get("turn_count")
                    if leg_turns is not None and isinstance(leg_turns, (int, float)):
                        profile.turn_count = max(profile.turn_count, int(leg_turns))
                        changed = True

                    if s_data.get("archetype") and not profile.archetype:
                        profile.archetype = s_data["archetype"]
                        changed = True

                    if changed:
                        migrated_count += 1

                if migrated_count > 0:
                    self.save_all()
                    logger.info(f"Successfully migrated {migrated_count} legacy user session(s) into person profiles.")
        except Exception as e:
            logger.warning(f"Error during legacy profile migration: {e}")

        return migrated_count

    def save_all(self) -> None:
        """Flushes in-memory profiles and channel configs to disk."""
        with self._lock:
            # Save profiles
            profiles_dict = {
                uid: profile.to_dict()
                for uid, profile in self._profiles_cache.items()
            }
            self._atomic_write_json(self.profiles_path, profiles_dict)

            # Save channels
            channels_dict = {
                cid: {"mode": mode}
                for cid, mode in self._channels_cache.items()
            }
            self._atomic_write_json(self.channels_path, channels_dict)

    def save_profiles(self) -> None:
        """Alias for save_all to ensure compatibility with profile persistence."""
        self.save_all()

    def get_profile(self, user_id: str, display_name: Optional[str] = None) -> PersonProfile:
        """Retrieves or creates a PersonProfile for user_id (stable platform ID)."""
        uid = str(user_id).strip()
        with self._lock:
            if uid in self._profiles_cache:
                profile = self._profiles_cache[uid]
                # Update display name if provided and changed
                if display_name and display_name.strip() and profile.display_name != display_name.strip():
                    profile.display_name = display_name.strip()
                return profile

            # Create fresh profile
            name = (display_name or "Unknown").strip()
            new_profile = PersonProfile(user_id=uid, display_name=name)
            self._profiles_cache[uid] = new_profile
            return new_profile

    def save_profile(self, profile: PersonProfile) -> None:
        """Updates cache and persists profile."""
        with self._lock:
            self._profiles_cache[str(profile.user_id)] = profile

        # Flush to disk
        self.save_all()

    def get_affection(self, user_id: str) -> int:
        """Returns the stable, persistent affection level for a Discord user."""
        profile = self.get_profile(user_id)
        return profile.affection_level

    def set_affection(self, user_id: str, value: int) -> int:
        """Sets the affection level directly with bounding and lifetime tracking."""
        profile = self.get_profile(user_id)
        clamped = max(0, min(100, int(value)))
        with self._lock:
            profile.affection_level = clamped
            if clamped > profile.lifetime_affection:
                profile.lifetime_affection = clamped
        self.save_profile(profile)
        return clamped

    def add_affection(self, user_id: str, base_gain: int = 1, allow_farming: bool = False, delta: Optional[float] = None) -> int:
        """
        Increments user affection with diminishing returns and anti-farming / spam protection.
        Different Discord members progress completely independently.
        """
        if delta is not None:
            base_gain = int(delta)
        import random
        profile = self.get_profile(user_id)
        curr_aff = profile.affection_level

        # Diminishing returns scaling formula
        if curr_aff < 50:
            factor = 0.25
        elif curr_aff < 75:
            factor = 0.12
        elif curr_aff < 90:
            factor = 0.04
        else:
            factor = 0.008

        now = time.time()
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Rate-limiting / anti-spam guard
        if not allow_farming:
            if now - profile.last_affection_gain_time < 3.0:
                return 0

            # Reset daily counter if new calendar day
            if profile.daily_affection_date != today_str:
                profile.daily_affection_date = today_str
                profile.daily_affection_earned = 0

            # Daily cap: max +25 affection per calendar day to prevent rapid farming
            if profile.daily_affection_earned >= 25:
                return 0

        raw_gain = base_gain * factor
        gain = int(raw_gain)
        fractional = raw_gain - gain
        if random.random() < fractional:
            gain += 1

        if not allow_farming and gain > 0:
            gain = min(gain, max(0, 25 - profile.daily_affection_earned))

        if gain > 0:
            with self._lock:
                new_aff = min(100, curr_aff + gain)
                profile.affection_level = new_aff
                profile.lifetime_affection = max(profile.lifetime_affection, new_aff)
                profile.last_affection_gain_time = now
                profile.daily_affection_earned += gain
            self.save_profile(profile)

        return gain

    def get_cozy_points(self, user_id: str) -> int:
        """Returns the cozy points for a Discord user."""
        profile = self.get_profile(user_id)
        return profile.cozy_points

    def add_cozy_points(self, user_id: str, points: int) -> int:
        """Awards cozy points to a Discord user and persists."""
        profile = self.get_profile(user_id)
        gain = max(0, int(points))
        with self._lock:
            profile.cozy_points += gain
        self.save_profile(profile)
        return profile.cozy_points

    def reset_person(self, user_id: str) -> bool:
        """
        Deletes and resets a person's behavioral profile.
        Mandatory privacy/safety feature (Section 19).
        """
        uid = str(user_id).strip()
        with self._lock:
            if uid in self._profiles_cache:
                del self._profiles_cache[uid]
                # Save immediately
                profiles_dict = {
                    u: p.to_dict()
                    for u, p in self._profiles_cache.items()
                }
                self._atomic_write_json(self.profiles_path, profiles_dict)
                logger.info(f"Behavior profile for user {uid} was successfully reset.")
                return True
        return False

    def get_channel_mode(self, channel_id: str, default: str = "OBSERVATION_ONLY") -> str:
        """Returns the configured mode for a channel: ACTIVE_CHAT, OBSERVATION_ONLY, or DISABLED."""
        cid = str(channel_id).strip()
        with self._lock:
            return self._channels_cache.get(cid, default).upper()

    def set_channel_mode(self, channel_id: str, mode: str) -> None:
        """Sets the mode for a channel and persists to disk."""
        cid = str(channel_id).strip()
        valid_mode = mode.upper().strip()
        if valid_mode not in ("ACTIVE_CHAT", "OBSERVATION_ONLY", "DISABLED"):
            valid_mode = "OBSERVATION_ONLY"

        with self._lock:
            self._channels_cache[cid] = valid_mode
            channels_dict = {
                c: {"mode": m}
                for c, m in self._channels_cache.items()
            }
            self._atomic_write_json(self.channels_path, channels_dict)
            logger.info(f"Set channel {cid} mode to {valid_mode}.")
