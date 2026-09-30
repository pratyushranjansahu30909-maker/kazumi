# 🌸 Kazumi Database & Storage Specification

Kazumi uses thread-safe, atomic file persistence under `isa_memory/`.

---

## 1. Schema & File Manifest

| File | Purpose | Primary Keys |
| :--- | :--- | :--- |
| `guild_settings.json` | AutoMod rules, log channel, welcome/goodbye settings. | `guild_id` |
| `moderation_records.json` | Warning history and moderation actions. | `guild_id:user_id` |
| `tickets.json` | Open and closed ticket metadata. | `channel_id` |
| `giveaways.json` | Active and historical giveaways, timers, entries. | `message_id` |
| `custom_commands.json` | Per-guild custom command tags and responses. | `guild_id -> command_name` |
| `reaction_roles.json` | Message ID to role mappings. | `message_id` |
| `reminders.json` | Scheduled user reminder timestamps. | `user_id, due_time` |
| `social_graph.json` | Member familiarity levels, topics, style tags. | `guild_id -> user_id` |
| `server_memory.json` | Channel purposes, server mood, community context. | `guild_id` |
| `conversations.json` | Chat history buffer and affection states. | `session_id` |

---

## 2. Atomic Write Protocol

To prevent corrupted JSON files during sudden crashes or power failures:
1. Target data is serialized to a temporary file (`.tmp`).
2. Buffer is flushed and forced to disk via `os.fsync(fileno)`.
3. Atomic swap replaces the target file via `os.replace`.
4. Automated `.bak` backup preserved for instant rollback if read failure occurs.
