"""
🌸 Kazumi Discord Features — Unified Persistent Database Manager
Provides thread-safe, atomic JSON persistence for:
- Guild Settings (AutoMod, Logging, Welcome, AutoRole, Tickets)
- Moderation Records (Warnings, Mod actions)
- Tickets (Active & closed support tickets)
- Giveaways (Active giveaways, entries, timers)
- Custom Commands (Per-guild custom triggers)
- Reaction Roles (Button & menu role assignments)
- Reminders (Scheduled user alerts)
- Social Graph & Server Memory
"""

import os
import json
import time
import shutil
import threading
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("KazumiFeatureDatabase")


class FeatureDatabase:
    """
    Manages persistent state for all server management, community,
    and moderation features under isa_memory/.
    """

    def __init__(self, persist_dir: str = "isa_memory"):
        self.persist_dir = persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)
        self._lock = threading.RLock()


        # Storage paths
        self.guild_settings_path = os.path.join(self.persist_dir, "guild_settings.json")
        self.moderation_path = os.path.join(self.persist_dir, "moderation_records.json")
        self.tickets_path = os.path.join(self.persist_dir, "tickets.json")
        self.giveaways_path = os.path.join(self.persist_dir, "giveaways.json")
        self.custom_commands_path = os.path.join(self.persist_dir, "custom_commands.json")
        self.reaction_roles_path = os.path.join(self.persist_dir, "reaction_roles.json")
        self.reminders_path = os.path.join(self.persist_dir, "reminders.json")
        self.social_graph_path = os.path.join(self.persist_dir, "social_graph.json")
        self.server_memory_path = os.path.join(self.persist_dir, "server_memory.json")

        # In-memory caches
        self.guild_settings: Dict[str, Dict[str, Any]] = {}
        self.moderation: Dict[str, Any] = {"warnings": {}, "actions": []}
        self.tickets: Dict[str, Dict[str, Any]] = {}
        self.giveaways: Dict[str, Dict[str, Any]] = {}
        self.custom_commands: Dict[str, Dict[str, Any]] = {}
        self.reaction_roles: Dict[str, Dict[str, Any]] = {}
        self.reminders: List[Dict[str, Any]] = []
        self.social_graph: Dict[str, Dict[str, Any]] = {}
        self.server_memory: Dict[str, Dict[str, Any]] = {}

        self.load_all()

    def _atomic_write(self, file_path: str, data: Any) -> bool:
        """Atomically saves data with .bak backup and fsync."""
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

    def _safe_read(self, file_path: str, default: Any) -> Any:
        """Reads JSON safely, falling back to .bak if primary is corrupted."""
        for path in [file_path, file_path + ".bak"]:
            if os.path.exists(path) and os.path.getsize(path) > 0:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read {path}: {e}")
        return default

    def load_all(self) -> None:
        """Loads all databases into memory."""
        with self._lock:
            self.guild_settings = self._safe_read(self.guild_settings_path, {})
            self.moderation = self._safe_read(self.moderation_path, {"warnings": {}, "actions": []})
            self.tickets = self._safe_read(self.tickets_path, {})
            self.giveaways = self._safe_read(self.giveaways_path, {})
            self.custom_commands = self._safe_read(self.custom_commands_path, {})
            self.reaction_roles = self._safe_read(self.reaction_roles_path, {})
            self.reminders = self._safe_read(self.reminders_path, [])
            self.social_graph = self._safe_read(self.social_graph_path, {})
            self.server_memory = self._safe_read(self.server_memory_path, {})

    # --- Guild Settings ---
    def get_guild_settings(self, guild_id: str) -> Dict[str, Any]:
        gid = str(guild_id)
        with self._lock:
            if gid not in self.guild_settings:
                self.guild_settings[gid] = {
                    "log_channel_id": None,
                    "welcome_channel_id": None,
                    "welcome_message": "Welcome to the server, {user}! 🌸 We're so glad you're here.",
                    "welcome_enabled": False,
                    "goodbye_channel_id": None,
                    "goodbye_message": "{user} has left the server. Take care! 🌸",
                    "goodbye_enabled": False,
                    "autorole_ids": [],
                    "automod": {
                        "enabled": False,
                        "anti_spam": True,
                        "anti_invites": True,
                        "anti_links": False,
                        "anti_mentions": True,
                        "max_mentions": 5,
                        "bad_words": []
                    },
                    "ticket_category_id": None,
                    "ticket_support_role_id": None
                }
            return dict(self.guild_settings[gid])

    def update_guild_settings(self, guild_id: str, updates: Dict[str, Any]) -> None:
        gid = str(guild_id)
        with self._lock:
            if gid not in self.guild_settings:
                self.get_guild_settings(gid)
            self.guild_settings[gid].update(updates)
            self._atomic_write(self.guild_settings_path, self.guild_settings)

    # --- Moderation ---
    def add_warning(self, guild_id: str, user_id: str, moderator_id: str, reason: str) -> int:
        gid = str(guild_id)
        uid = str(user_id)
        key = f"{gid}:{uid}"
        with self._lock:
            warnings_dict = self.moderation.setdefault("warnings", {})
            user_warnings = warnings_dict.setdefault(key, [])
            warn_entry = {
                "id": len(user_warnings) + 1,
                "moderator_id": str(moderator_id),
                "reason": reason,
                "timestamp": time.time()
            }
            user_warnings.append(warn_entry)
            self._atomic_write(self.moderation_path, self.moderation)
            return len(user_warnings)

    def get_warnings(self, guild_id: str, user_id: str) -> List[Dict[str, Any]]:
        gid = str(guild_id)
        uid = str(user_id)
        key = f"{gid}:{uid}"
        with self._lock:
            return list(self.moderation.get("warnings", {}).get(key, []))

    def clear_warnings(self, guild_id: str, user_id: str) -> int:
        gid = str(guild_id)
        uid = str(user_id)
        key = f"{gid}:{uid}"
        with self._lock:
            warnings_dict = self.moderation.get("warnings", {})
            if key in warnings_dict:
                count = len(warnings_dict[key])
                del warnings_dict[key]
                self._atomic_write(self.moderation_path, self.moderation)
                return count
            return 0

    def record_mod_action(self, guild_id: str, action: str, target_id: str, mod_id: str, reason: str) -> None:
        with self._lock:
            actions = self.moderation.setdefault("actions", [])
            actions.append({
                "guild_id": str(guild_id),
                "action": action,
                "target_id": str(target_id),
                "moderator_id": str(mod_id),
                "reason": reason,
                "timestamp": time.time()
            })
            if len(actions) > 500:
                self.moderation["actions"] = actions[-500:]
            self._atomic_write(self.moderation_path, self.moderation)

    # --- Tickets ---
    def save_ticket(self, channel_id: str, ticket_data: Dict[str, Any]) -> None:
        cid = str(channel_id)
        with self._lock:
            self.tickets[cid] = ticket_data
            self._atomic_write(self.tickets_path, self.tickets)

    def get_ticket(self, channel_id: str) -> Optional[Dict[str, Any]]:
        cid = str(channel_id)
        with self._lock:
            return self.tickets.get(cid)

    def close_ticket(self, channel_id: str) -> None:
        cid = str(channel_id)
        with self._lock:
            if cid in self.tickets:
                self.tickets[cid]["status"] = "closed"
                self.tickets[cid]["closed_at"] = time.time()
                self._atomic_write(self.tickets_path, self.tickets)

    # --- Giveaways ---
    def save_giveaway(self, message_id: str, giveaway_data: Dict[str, Any]) -> None:
        mid = str(message_id)
        with self._lock:
            self.giveaways[mid] = giveaway_data
            self._atomic_write(self.giveaways_path, self.giveaways)

    def get_giveaway(self, message_id: str) -> Optional[Dict[str, Any]]:
        mid = str(message_id)
        with self._lock:
            return self.giveaways.get(mid)

    def get_active_giveaways(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [g for g in self.giveaways.values() if not g.get("ended", False)]

    # --- Custom Commands ---
    def add_custom_command(self, guild_id: str, name: str, response: str, creator_id: str) -> None:
        gid = str(guild_id)
        cmd_name = name.lower().strip()
        with self._lock:
            guild_cmds = self.custom_commands.setdefault(gid, {})
            guild_cmds[cmd_name] = {
                "response": response,
                "creator_id": str(creator_id),
                "created_at": time.time()
            }
            self._atomic_write(self.custom_commands_path, self.custom_commands)

    def get_custom_command(self, guild_id: str, name: str) -> Optional[Dict[str, Any]]:
        gid = str(guild_id)
        cmd_name = name.lower().strip()
        with self._lock:
            return self.custom_commands.get(gid, {}).get(cmd_name)

    def delete_custom_command(self, guild_id: str, name: str) -> bool:
        gid = str(guild_id)
        cmd_name = name.lower().strip()
        with self._lock:
            guild_cmds = self.custom_commands.get(gid, {})
            if cmd_name in guild_cmds:
                del guild_cmds[cmd_name]
                self._atomic_write(self.custom_commands_path, self.custom_commands)
                return True
            return False

    def list_custom_commands(self, guild_id: str) -> List[str]:
        gid = str(guild_id)
        with self._lock:
            return list(self.custom_commands.get(gid, {}).keys())

    # --- Reminders ---
    def add_reminder(self, user_id: str, channel_id: str, due_time: float, text: str) -> None:
        with self._lock:
            self.reminders.append({
                "user_id": str(user_id),
                "channel_id": str(channel_id),
                "due_time": float(due_time),
                "text": text,
                "created_at": time.time()
            })
            self._atomic_write(self.reminders_path, self.reminders)

    def get_due_reminders(self) -> List[Dict[str, Any]]:
        now = time.time()
        due = []
        remaining = []
        with self._lock:
            for rem in self.reminders:
                if rem["due_time"] <= now:
                    due.append(rem)
                else:
                    remaining.append(rem)
            if due:
                self.reminders = remaining
                self._atomic_write(self.reminders_path, self.reminders)
        return due

    # --- Reaction Roles ---
    def save_reaction_role(self, message_id: str, role_mappings: Dict[str, str]) -> None:
        mid = str(message_id)
        with self._lock:
            self.reaction_roles[mid] = role_mappings
            self._atomic_write(self.reaction_roles_path, self.reaction_roles)

    def get_reaction_role(self, message_id: str) -> Optional[Dict[str, str]]:
        mid = str(message_id)
        with self._lock:
            return self.reaction_roles.get(mid)

    # Alias for custom command
    def set_custom_command(self, guild_id: str, name: str, response: str, creator_id: str) -> None:
        self.add_custom_command(guild_id, name, response, creator_id)

    # --- Social Graph & Server Memory ---
    def get_social_graph(self, guild_id: Any) -> Dict[str, Any]:
        gid = str(guild_id)
        with self._lock:
            return self.social_graph.setdefault(gid, {"users": {}})

    def update_social_graph(self, guild_id: Any, data: Dict[str, Any]) -> None:
        gid = str(guild_id)
        with self._lock:
            self.social_graph[gid] = data
            self._atomic_write(self.social_graph_path, self.social_graph)

    def get_server_memory(self, guild_id: Any) -> Dict[str, Any]:
        gid = str(guild_id)
        with self._lock:
            return self.server_memory.setdefault(gid, {"channels": {}, "current_mood": "calm", "inside_jokes": []})

    def update_server_memory(self, guild_id: Any, updates: Dict[str, Any]) -> None:
        gid = str(guild_id)
        with self._lock:
            mem = self.get_server_memory(gid)
            mem.update(updates)
            self._atomic_write(self.server_memory_path, self.server_memory)


_global_feature_db = None

def get_feature_db(persist_dir: str = "isa_memory") -> FeatureDatabase:
    """Returns singleton FeatureDatabase instance."""
    global _global_feature_db
    if _global_feature_db is None:
        _global_feature_db = FeatureDatabase(persist_dir=persist_dir)
    return _global_feature_db

# Convenience alias
FeatureDB = FeatureDatabase

