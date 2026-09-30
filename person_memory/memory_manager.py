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

        self._lock = threading.Lock()
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
