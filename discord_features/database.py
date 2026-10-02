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
        self.roast_metadata_path = os.path.join(self.persist_dir, "roast_metadata.json")
        self.cases_path = os.path.join(self.persist_dir, "cases.json")
        self.mod_notes_path = os.path.join(self.persist_dir, "mod_notes.json")
        self.reports_path = os.path.join(self.persist_dir, "reports.json")
        self.appeals_path = os.path.join(self.persist_dir, "appeals.json")
        self.security_path = os.path.join(self.persist_dir, "security_settings.json")
        self.game_stats_path = os.path.join(self.persist_dir, "game_stats.json")
        self.announcements_path = os.path.join(self.persist_dir, "announcements.json")

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
        self.roast_metadata: Dict[str, Any] = {"opt_out": [], "users": {}, "guilds": {}}
        self.cases: Dict[str, Dict[str, Any]] = {}
        self.mod_notes: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        self.reports: Dict[str, Dict[str, Any]] = {}
        self.appeals: Dict[str, Dict[str, Any]] = {}
        self.security_settings: Dict[str, Dict[str, Any]] = {}
        self.game_stats: Dict[str, Any] = {"users": {}, "daily": {}}
        self.announcements: Dict[str, Any] = {"history": [], "scheduled": {}, "templates": {}}

        self.load_all()

    def _atomic_write(self, file_path: str, data: Any) -> bool:
        """Atomically saves data with .bak backup and fsync."""
        try:
            if os.path.exists(file_path):
                try:
                    shutil.copy2(file_path, file_path + ".bak")
                except Exception:
                    pass

            tmp_path = file_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Retry on Windows if file is momentarily held
            for attempt in range(4):
                try:
                    os.replace(tmp_path, file_path)
                    return True
                except (PermissionError, OSError):
                    if attempt < 3:
                        time.sleep(0.05 * (attempt + 1))
                    else:
                        raise
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
            self.roast_metadata = self._safe_read(self.roast_metadata_path, {"opt_out": [], "users": {}, "guilds": {}})
            self.cases = self._safe_read(self.cases_path, {})
            self.mod_notes = self._safe_read(self.mod_notes_path, {})
            self.reports = self._safe_read(self.reports_path, {})
            self.appeals = self._safe_read(self.appeals_path, {})
            self.security_settings = self._safe_read(self.security_path, {})
            self.game_stats = self._safe_read(self.game_stats_path, {"users": {}, "daily": {}})
            self.announcements = self._safe_read(self.announcements_path, {"history": [], "scheduled": {}, "templates": {}})

    # --- Guild Settings ---
    def get_guild_settings(self, guild_id: str) -> Dict[str, Any]:
        gid = str(guild_id)
        with self._lock:
            if gid not in self.guild_settings:
                self.guild_settings[gid] = {
                    "log_channel_id": None,
                    "welcome_channel_id": None,
                    "welcome_message": "Welcome to **{server}**, {user}! 🌸 We're so excited to have you here with us.",
                    "welcome_enabled": True,
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

    def get_mod_logs(self, guild_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            actions = [a for a in self.moderation.get("actions", []) if str(a.get("guild_id")) == str(guild_id)]
            actions.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            return actions[:limit]

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

    set_giveaway = save_giveaway

    def get_giveaway(self, message_id: str) -> Optional[Dict[str, Any]]:
        mid = str(message_id)
        with self._lock:
            return self.giveaways.get(mid)

    def get_active_giveaways(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [g for g in self.giveaways.values() if not g.get("ended", False)]

    def get_guild_giveaways(self, guild_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [g for g in self.giveaways.values() if str(g.get("guild_id")) == str(guild_id)]

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

    # --- Roast Engine Settings & Metadata (Sections 16, 25, 26) ---
    def get_guild_roast_settings(self, guild_id: Any) -> Dict[str, Any]:
        gid = str(guild_id)
        with self._lock:
            guilds = self.roast_metadata.setdefault("guilds", {})
            if gid not in guilds:
                guilds[gid] = {
                    "allow_roasting": True,
                    "default_intensity": 2,
                    "max_intensity": 5,
                    "allow_user_to_opt_out": True,
                    "unhinged_mode": False
                }
            return dict(guilds[gid])

    def update_guild_roast_settings(self, guild_id: Any, updates: Dict[str, Any]) -> None:
        gid = str(guild_id)
        with self._lock:
            guilds = self.roast_metadata.setdefault("guilds", {})
            if gid not in guilds:
                self.get_guild_roast_settings(gid)
            guilds[gid].update(updates)
            self._atomic_write(self.roast_metadata_path, self.roast_metadata)

    def is_user_roast_opted_out(self, user_id: Any) -> bool:
        uid = str(user_id)
        with self._lock:
            opt_out_list = self.roast_metadata.setdefault("opt_out", [])
            return uid in opt_out_list

    def set_user_roast_opt_out(self, user_id: Any, opt_out: bool) -> None:
        uid = str(user_id)
        with self._lock:
            opt_out_list = self.roast_metadata.setdefault("opt_out", [])
            if opt_out and uid not in opt_out_list:
                opt_out_list.append(uid)
            elif not opt_out and uid in opt_out_list:
                opt_out_list.remove(uid)
            # Update in user meta as well
            users = self.roast_metadata.setdefault("users", {})
            u_meta = users.setdefault(uid, {"roast_count": 0, "preferred_intensity": 2, "opt_out": False})
            u_meta["opt_out"] = bool(opt_out)
            self._atomic_write(self.roast_metadata_path, self.roast_metadata)

    def get_user_roast_meta(self, user_id: Any) -> Dict[str, Any]:
        uid = str(user_id)
        with self._lock:
            users = self.roast_metadata.setdefault("users", {})
            if uid not in users:
                is_opted_out = uid in self.roast_metadata.setdefault("opt_out", [])
                users[uid] = {
                    "roast_count": 0,
                    "preferred_intensity": 2,
                    "opt_out": is_opted_out,
                    "last_roast_time": 0.0
                }
            return dict(users[uid])

    def set_user_roast_level(self, user_id: Any, level: int) -> None:
        uid = str(user_id)
        level = max(1, min(5, int(level)))
        with self._lock:
            users = self.roast_metadata.setdefault("users", {})
            u_meta = users.setdefault(uid, {
                "roast_count": 0,
                "preferred_intensity": 2,
                "opt_out": False,
                "last_roast_time": 0.0
            })
            u_meta["preferred_intensity"] = level
            self._atomic_write(self.roast_metadata_path, self.roast_metadata)

    def record_user_roast_interaction(self, user_id: Any, intensity: int = 2) -> None:
        uid = str(user_id)
        with self._lock:
            users = self.roast_metadata.setdefault("users", {})
            u_meta = users.setdefault(uid, {
                "roast_count": 0,
                "preferred_intensity": 2,
                "opt_out": False,
                "last_roast_time": 0.0
            })
            u_meta["roast_count"] = u_meta.get("roast_count", 0) + 1
            u_meta["last_roast_time"] = time.time()
            self._atomic_write(self.roast_metadata_path, self.roast_metadata)

    # =========================================================================
    # --- Moderation Case Management ---
    # =========================================================================
    def create_case(self, guild_id: Any, user_id: Any, moderator_id: Any, action: str, reason: str, duration: Optional[str] = None, evidence: Optional[str] = None) -> int:
        gid = str(guild_id)
        with self._lock:
            g_cases = self.cases.setdefault(gid, {})
            # Generate next sequential case number, starting at 1001
            case_id = max([int(k) for k in g_cases.keys()] or [1000]) + 1
            case_entry = {
                "case_id": case_id,
                "guild_id": gid,
                "user_id": str(user_id),
                "moderator_id": str(moderator_id),
                "action": action.upper(),
                "reason": reason or "No reason provided",
                "duration": duration,
                "evidence": evidence,
                "timestamp": time.time(),
                "status": "active"
            }
            g_cases[str(case_id)] = case_entry
            self._atomic_write(self.cases_path, self.cases)
            return case_id

    def get_case(self, guild_id: Any, case_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        with self._lock:
            if case_id is None:
                # Single argument passed as case_id
                target_cid = str(guild_id)
                for g_cases in self.cases.values():
                    if target_cid in g_cases:
                        return g_cases[target_cid]
                return None
            gid = str(guild_id)
            cid = str(case_id)
            return self.cases.get(gid, {}).get(cid)

    def get_user_cases(self, guild_id: Any, user_id: Any) -> List[Dict[str, Any]]:
        gid = str(guild_id)
        uid = str(user_id)
        with self._lock:
            g_cases = self.cases.get(gid, {})
            return sorted(
                [c for c in g_cases.values() if str(c.get("user_id")) == uid],
                key=lambda x: x.get("timestamp", 0),
                reverse=True
            )

    def list_cases(self, guild_id: Any, limit: int = 25, action_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        gid = str(guild_id)
        with self._lock:
            g_cases = list(self.cases.get(gid, {}).values())
            if action_filter:
                act = action_filter.upper()
                g_cases = [c for c in g_cases if c.get("action") == act]
            g_cases.sort(key=lambda x: x.get("case_id", 0), reverse=True)
            return g_cases[:limit]

    # =========================================================================
    # --- Private Moderator Staff Notes ---
    # =========================================================================
    def add_mod_note(self, guild_id: Any, user_id: Any, moderator_id: Any, content: str) -> Dict[str, Any]:
        gid = str(guild_id)
        uid = str(user_id)
        with self._lock:
            g_notes = self.mod_notes.setdefault(gid, {})
            u_notes = g_notes.setdefault(uid, [])
            note_id = len(u_notes) + 1
            note_entry = {
                "note_id": note_id,
                "moderator_id": str(moderator_id),
                "content": content.strip(),
                "timestamp": time.time()
            }
            u_notes.append(note_entry)
            self._atomic_write(self.mod_notes_path, self.mod_notes)
            return note_entry

    def get_mod_notes(self, guild_id: Any, user_id: Any) -> List[Dict[str, Any]]:
        gid = str(guild_id)
        uid = str(user_id)
        with self._lock:
            return list(self.mod_notes.get(gid, {}).get(uid, []))

    def delete_mod_note(self, guild_id: Any, user_id: Any, note_id: int) -> bool:
        gid = str(guild_id)
        uid = str(user_id)
        with self._lock:
            notes = self.mod_notes.get(gid, {}).get(uid, [])
            for i, note in enumerate(notes):
                if note.get("note_id") == note_id:
                    notes.pop(i)
                    self._atomic_write(self.mod_notes_path, self.mod_notes)
                    return True
            return False

    # =========================================================================
    # --- Message Report Queue System ---
    # =========================================================================
    def create_report(self, guild_id: Any, reporter_id: Any, reported_id: Any, channel_id: Any, message_id: Optional[Any], reason: str, details: str = "") -> int:
        gid = str(guild_id)
        with self._lock:
            g_reports = self.reports.setdefault(gid, {})
            report_id = max([int(k) for k in g_reports.keys()] or [500]) + 1
            report_entry = {
                "report_id": report_id,
                "guild_id": gid,
                "reporter_id": str(reporter_id),
                "reported_id": str(reported_id),
                "channel_id": str(channel_id),
                "message_id": str(message_id) if message_id else None,
                "reason": reason,
                "details": details.strip(),
                "timestamp": time.time(),
                "status": "pending",
                "resolved_by": None,
                "resolution_note": None
            }
            g_reports[str(report_id)] = report_entry
            self._atomic_write(self.reports_path, self.reports)
            return report_id

    def get_report(self, guild_id: Any, report_id: int) -> Optional[Dict[str, Any]]:
        gid = str(guild_id)
        return self.reports.get(gid, {}).get(str(report_id))

    def get_pending_reports(self, guild_id: Any) -> List[Dict[str, Any]]:
        gid = str(guild_id)
        with self._lock:
            g_reports = self.reports.get(gid, {})
            pending = [r for r in g_reports.values() if r.get("status") == "pending"]
            pending.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            return pending

    def resolve_report(self, guild_id: Any, report_id: int, status: str, moderator_id: Any, notes: str = "") -> bool:
        gid = str(guild_id)
        rid = str(report_id)
        with self._lock:
            report = self.reports.get(gid, {}).get(rid)
            if not report:
                return False
            report["status"] = status  # "resolved" or "dismissed"
            report["resolved_by"] = str(moderator_id)
            report["resolution_note"] = notes.strip()
            report["resolved_at"] = time.time()
            self._atomic_write(self.reports_path, self.reports)
            return True

    # =========================================================================
    # --- Moderation Appeals System ---
    # =========================================================================
    def create_appeal(self, guild_id: Any, user_id: Any, case_id: int, reason: str) -> int:
        gid = str(guild_id)
        with self._lock:
            g_appeals = self.appeals.setdefault(gid, {})
            # Check if an active appeal already exists for this case/user
            for app in g_appeals.values():
                if str(app.get("user_id")) == str(user_id) and app.get("case_id") == case_id and app.get("status") == "pending":
                    return int(app["appeal_id"])
            appeal_id = max([int(k) for k in g_appeals.keys()] or [200]) + 1
            appeal_entry = {
                "appeal_id": appeal_id,
                "guild_id": gid,
                "user_id": str(user_id),
                "case_id": case_id,
                "reason": reason.strip(),
                "timestamp": time.time(),
                "status": "pending",
                "reviewed_by": None,
                "review_note": None
            }
            g_appeals[str(appeal_id)] = appeal_entry
            self._atomic_write(self.appeals_path, self.appeals)
            return appeal_id

    def get_appeal(self, guild_id: Any, appeal_id: int) -> Optional[Dict[str, Any]]:
        gid = str(guild_id)
        return self.appeals.get(gid, {}).get(str(appeal_id))

    def get_user_appeals(self, guild_id: Any, user_id: Any) -> List[Dict[str, Any]]:
        gid = str(guild_id)
        uid = str(user_id)
        with self._lock:
            return [a for a in self.appeals.get(gid, {}).values() if str(a.get("user_id")) == uid]

    def get_pending_appeals(self, guild_id: Any) -> List[Dict[str, Any]]:
        gid = str(guild_id)
        with self._lock:
            apps = [a for a in self.appeals.get(gid, {}).values() if a.get("status") == "pending"]
            apps.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            return apps

    def review_appeal(self, guild_id: Any, appeal_id: int, status: str, reviewer_id: Any, review_note: str = "") -> bool:
        gid = str(guild_id)
        aid = str(appeal_id)
        with self._lock:
            app = self.appeals.get(gid, {}).get(aid)
            if not app:
                return False
            app["status"] = status  # "approved" or "rejected"
            app["reviewed_by"] = str(reviewer_id)
            app["review_note"] = review_note.strip()
            app["reviewed_at"] = time.time()
            self._atomic_write(self.appeals_path, self.appeals)
            return True

    # =========================================================================
    # --- Advanced Security, Anti-Raid, Anti-Nuke, Quarantine ---
    # =========================================================================
    def get_security_settings(self, guild_id: Any) -> Dict[str, Any]:
        gid = str(guild_id)
        with self._lock:
            if gid not in self.security_settings:
                self.security_settings[gid] = {
                    "anti_raid": {
                        "enabled": False,
                        "join_threshold": 8,
                        "join_window_sec": 10,
                        "action": "lockdown",  # "lockdown", "quarantine", "alert"
                        "alert_channel_id": None
                    },
                    "anti_nuke": {
                        "enabled": False,
                        "max_channel_deletions": 4,
                        "max_role_deletions": 4,
                        "max_bans": 5,
                        "max_kicks": 5,
                        "window_sec": 12,
                        "action": "lockdown"
                    },
                    "quarantine": {
                        "enabled": False,
                        "role_id": None,
                        "channel_id": None
                    },
                    "staff_roles": {
                        "helper": None,
                        "moderator": None,
                        "senior_moderator": None,
                        "administrator": None
                    },
                    "quarantined_users": {},
                    "raid_mode_active": False
                }
            return dict(self.security_settings[gid])

    def update_security_settings(self, guild_id: Any, updates: Dict[str, Any]) -> None:
        gid = str(guild_id)
        with self._lock:
            if gid not in self.security_settings:
                self.get_security_settings(gid)
            self.security_settings[gid].update(updates)
            self._atomic_write(self.security_path, self.security_settings)

    def is_user_quarantined(self, guild_id: Any, user_id: Any) -> bool:
        gid = str(guild_id)
        uid = str(user_id)
        with self._lock:
            settings = self.get_security_settings(gid)
            return uid in settings.get("quarantined_users", {})

    def set_user_quarantined(self, guild_id: Any, user_id: Any, quarantined: bool, moderator_id: Optional[Any] = None, reason: str = "", original_roles: Optional[List[int]] = None) -> None:
        gid = str(guild_id)
        uid = str(user_id)
        with self._lock:
            settings = self.security_settings.setdefault(gid, self.get_security_settings(gid))
            q_users = settings.setdefault("quarantined_users", {})
            if quarantined:
                q_users[uid] = {
                    "user_id": uid,
                    "moderator_id": str(moderator_id) if moderator_id else "AutoMod",
                    "reason": reason or "Flagged as high-risk / raid account",
                    "original_roles": [int(r) for r in (original_roles or [])],
                    "timestamp": time.time()
                }
            else:
                q_users.pop(uid, None)
            self._atomic_write(self.security_path, self.security_settings)

    def get_quarantined_record(self, guild_id: Any, user_id: Any) -> Optional[Dict[str, Any]]:
        gid = str(guild_id)
        uid = str(user_id)
        with self._lock:
            settings = self.get_security_settings(gid)
            return settings.get("quarantined_users", {}).get(uid)

    def is_raid_mode_active(self, guild_id: Any) -> bool:
        gid = str(guild_id)
        with self._lock:
            return bool(self.get_security_settings(gid).get("raid_mode_active", False))

    def set_raid_mode(self, guild_id: Any, enabled: bool) -> None:
        gid = str(guild_id)
        with self._lock:
            settings = self.security_settings.setdefault(gid, self.get_security_settings(gid))
            settings["raid_mode_active"] = bool(enabled)
            self._atomic_write(self.security_path, self.security_settings)

    # =========================================================================
    # --- Game Profiles, Leaderboards, Achievements & Daily Challenges ---
    # =========================================================================
    def get_game_profile(self, user_id: Any) -> Dict[str, Any]:
        uid = str(user_id)
        with self._lock:
            users = self.game_stats.setdefault("users", {})
            if uid not in users:
                users[uid] = {
                    "user_id": uid,
                    "xp": 0,
                    "level": 1,
                    "wins": 0,
                    "losses": 0,
                    "draws": 0,
                    "games_played": 0,
                    "win_rate": 0.0,
                    "streak": 0,
                    "best_streak": 0,
                    "achievements": [],
                    "per_game": {},
                    "daily_streak": 0,
                    "last_daily_date": None
                }
            return dict(users[uid])

    def record_game_outcome(self, user_id: Any, game_type: str, outcome: str, score: int = 0, xp_earned: int = 15) -> Dict[str, Any]:
        uid = str(user_id)
        with self._lock:
            users = self.game_stats.setdefault("users", {})
            prof = users.setdefault(uid, {
                "user_id": uid,
                "xp": 0,
                "level": 1,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "games_played": 0,
                "win_rate": 0.0,
                "streak": 0,
                "best_streak": 0,
                "achievements": [],
                "per_game": {},
                "daily_streak": 0,
                "last_daily_date": None
            })

            prof["games_played"] = prof.get("games_played", 0) + 1
            if outcome.lower() == "win":
                prof["wins"] = prof.get("wins", 0) + 1
                prof["streak"] = prof.get("streak", 0) + 1
                if prof["streak"] > prof.get("best_streak", 0):
                    prof["best_streak"] = prof["streak"]
            elif outcome.lower() == "loss":
                prof["losses"] = prof.get("losses", 0) + 1
                prof["streak"] = 0
            else:
                prof["draws"] = prof.get("draws", 0) + 1

            total_decided = prof["wins"] + prof["losses"]
            prof["win_rate"] = round((prof["wins"] / total_decided) * 100, 1) if total_decided > 0 else 0.0

            # Award XP & compute level (100 XP per level)
            prof["xp"] = prof.get("xp", 0) + max(0, int(xp_earned))
            prof["level"] = max(1, (prof["xp"] // 100) + 1)

            # Per-game breakdown
            g_dict = prof.setdefault("per_game", {})
            g_stat = g_dict.setdefault(game_type.lower(), {"wins": 0, "losses": 0, "draws": 0, "played": 0, "high_score": 0})
            g_stat["played"] = g_stat.get("played", 0) + 1
            if outcome.lower() == "win":
                g_stat["wins"] = g_stat.get("wins", 0) + 1
            elif outcome.lower() == "loss":
                g_stat["losses"] = g_stat.get("losses", 0) + 1
            else:
                g_stat["draws"] = g_stat.get("draws", 0) + 1
            if score > g_stat.get("high_score", 0):
                g_stat["high_score"] = score

            self._atomic_write(self.game_stats_path, self.game_stats)
            return prof

    def unlock_achievement(self, user_id: Any, achievement_id: str, title: str, description: str) -> bool:
        uid = str(user_id)
        aid = achievement_id.lower().strip()
        with self._lock:
            prof = self.get_game_profile(uid)
            ach_list = prof.setdefault("achievements", [])
            for ach in ach_list:
                if isinstance(ach, dict) and ach.get("id") == aid:
                    return False
                elif isinstance(ach, str) and ach == aid:
                    return False

            ach_entry = {
                "id": aid,
                "title": title,
                "description": description,
                "unlocked_at": time.time()
            }
            ach_list.append(ach_entry)
            self.game_stats["users"][uid] = prof
            self._atomic_write(self.game_stats_path, self.game_stats)
            return True

    def get_game_leaderboard(self, game_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            users = list(self.game_stats.get("users", {}).values())
            if game_type:
                gt = game_type.lower()
                users = [u for u in users if gt in u.get("per_game", {})]
                users.sort(key=lambda x: x.get("per_game", {}).get(gt, {}).get("wins", 0), reverse=True)
            else:
                users.sort(key=lambda x: (x.get("wins", 0), x.get("xp", 0)), reverse=True)
            return users[:limit]

    def get_daily_challenge(self, date_str: str) -> Dict[str, Any]:
        """Provides a deterministic daily puzzle/challenge for the specified date (YYYY-MM-DD)."""
        with self._lock:
            daily_dict = self.game_stats.setdefault("daily", {})
            if date_str not in daily_dict:
                import hashlib
                hash_val = int(hashlib.md5(date_str.encode()).hexdigest(), 16)
                challenges = [
                    {
                        "type": "word_riddle",
                        "title": "The Cipher of the Blossom",
                        "prompt": "I speak without a mouth and hear without ears. I have no body, but I come alive with wind. What am I?",
                        "solution": "echo",
                        "category": "Riddle"
                    },
                    {
                        "type": "logic_puzzle",
                        "title": "The Three Switches",
                        "prompt": "There are three light switches outside a closed room. Only one controls the bulb inside. You can flip switches as you wish, but you can only enter the room once. What switch property reveals the bulb?",
                        "solution": "heat",
                        "category": "Logic"
                    },
                    {
                        "type": "emoji_puzzle",
                        "title": "Movie in Emojis",
                        "prompt": "🦁 👑 🌅 (Guess the famous animated movie!)",
                        "solution": "the lion king",
                        "category": "Pop Culture"
                    },
                    {
                        "type": "math_sequence",
                        "title": "The Golden Sequence",
                        "prompt": "What is the next number in the pattern: 2, 3, 5, 8, 13, 21, ?",
                        "solution": "34",
                        "category": "Pattern"
                    },
                    {
                        "type": "trivia_master",
                        "title": "Cosmic Curiosity",
                        "prompt": "Which planet in our solar system spins clockwise (retrograde rotation)?",
                        "solution": "venus",
                        "category": "Astronomy"
                    }
                ]
                chosen = challenges[hash_val % len(challenges)]
                daily_dict[date_str] = {
                    "date": date_str,
                    "challenge": chosen,
                    "completions": []
                }
                self._atomic_write(self.game_stats_path, self.game_stats)
            return daily_dict[date_str]

    def complete_daily_challenge(self, user_id: Any, date_str: str, score: int = 50) -> bool:
        uid = str(user_id)
        with self._lock:
            daily = self.get_daily_challenge(date_str)
            if uid in daily.get("completions", []):
                return False
            daily["completions"].append(uid)
            prof = self.get_game_profile(uid)
            last_date = prof.get("last_daily_date")
            from datetime import datetime, timedelta
            try:
                curr_dt = datetime.strptime(date_str, "%Y-%m-%d")
                if last_date:
                    last_dt = datetime.strptime(last_date, "%Y-%m-%d")
                    if (curr_dt - last_dt).days == 1:
                        prof["daily_streak"] = prof.get("daily_streak", 0) + 1
                    elif (curr_dt - last_dt).days > 1:
                        prof["daily_streak"] = 1
                else:
                    prof["daily_streak"] = 1
            except Exception:
                prof["daily_streak"] = 1

            prof["last_daily_date"] = date_str
            prof["xp"] = prof.get("xp", 0) + score
            prof["level"] = max(1, (prof["xp"] // 100) + 1)
            self.game_stats["users"][uid] = prof
            self._atomic_write(self.game_stats_path, self.game_stats)
            return True

    # =========================================================================
    # --- Announcements, Scheduling & Templates ---
    # =========================================================================
    def record_announcement(self, record: Dict[str, Any]) -> None:
        with self._lock:
            history = self.announcements.setdefault("history", [])
            history.append(record)
            if len(history) > 200:
                self.announcements["history"] = history[-200:]
            self._atomic_write(self.announcements_path, self.announcements)

    def get_announcement_history(self, guild_id: str, limit: int = 25) -> List[Dict[str, Any]]:
        gid = str(guild_id)
        with self._lock:
            history = self.announcements.get("history", [])
            filtered = [r for r in history if str(r.get("guild_id")) == gid]
            return filtered[-limit:]

    def save_scheduled_announcement(self, item_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            scheduled = self.announcements.setdefault("scheduled", {})
            scheduled[str(item_id)] = data
            self._atomic_write(self.announcements_path, self.announcements)

    def get_scheduled_announcements(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.announcements.get("scheduled", {}).values())

    def delete_scheduled_announcement(self, item_id: str) -> bool:
        iid = str(item_id)
        with self._lock:
            scheduled = self.announcements.setdefault("scheduled", {})
            if iid in scheduled:
                del scheduled[iid]
                self._atomic_write(self.announcements_path, self.announcements)
                return True
            return False

    def save_announcement_template(self, guild_id: str, name: str, data: Dict[str, Any]) -> None:
        gid = str(guild_id)
        tname = str(name).lower().strip()
        with self._lock:
            templates = self.announcements.setdefault("templates", {})
            guild_tpls = templates.setdefault(gid, {})
            guild_tpls[tname] = data
            self._atomic_write(self.announcements_path, self.announcements)

    def get_announcement_templates(self, guild_id: str) -> Dict[str, Any]:
        gid = str(guild_id)
        with self._lock:
            return dict(self.announcements.get("templates", {}).get(gid, {}))

    def get_announcement_template(self, guild_id: str, name: str) -> Optional[Dict[str, Any]]:
        gid = str(guild_id)
        tname = str(name).lower().strip()
        with self._lock:
            return self.announcements.get("templates", {}).get(gid, {}).get(tname)

    def delete_announcement_template(self, guild_id: str, name: str) -> bool:
        gid = str(guild_id)
        tname = str(name).lower().strip()
        with self._lock:
            templates = self.announcements.setdefault("templates", {})
            guild_tpls = templates.get(gid, {})
            if tname in guild_tpls:
                del guild_tpls[tname]
                self._atomic_write(self.announcements_path, self.announcements)
                return True
            return False


_global_feature_db = None

def get_feature_db(persist_dir: str = "isa_memory") -> FeatureDatabase:
    """Returns singleton FeatureDatabase instance."""
    global _global_feature_db
    if _global_feature_db is None:
        _global_feature_db = FeatureDatabase(persist_dir=persist_dir)
    return _global_feature_db

# Convenience alias
FeatureDB = FeatureDatabase

