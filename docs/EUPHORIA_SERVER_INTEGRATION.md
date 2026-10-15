# 🌸 Euphoria Server Integration & Complete Verification Guide

This guide documents the live server architecture, authentic channel types, role hierarchy, permission matrix, and centralized channel policy system for **Euphoria** (Guild ID: `1546919406603337809`) with **Kazumi**.

---

## 1. Live Euphoria Channel Architecture & IDs

Euphoria is fully configured as a verified **Discord Community** using genuine Discord channel types:

```text
🌸 INFORMATION (Category ID: 1557697973465518151) — Read-Only for @everyone
├── 📢 #announcements      - ID: 1557699277512249398 [Type: Announcement / News Channel]
├── 📜 #rules              - ID: 1556629631832952903 [Type: Text Channel] (Official guidelines published)
├── 📌 #welcome            - ID: 1557699099246071900 [Type: Text Channel] (Personalized 2-line rhyming welcome poems)
├── 📖 #server-guide       - ID: 1557699104291954759 [Type: Text Channel] (Verified server navigation & command handbook)
└── 🎭 #roles              - ID: 1557699112294547507 [Type: Text Channel] (Role hierarchy & notification selection)

COMMUNITY (Category ID: 1546919407580876972)
├── 💬 #general💬          - ID: 1546919407580876974 [Type: Text Channel] (Mode: OBSERVATION_ONLY; redirect on ping)
├── 👋 #introduction👋     - ID: 1556610885185970227 [Type: Text Channel] (Mode: INTRODUCTIONS_ONLY)
├── 📸 #media📸            - ID: 1556611228288417902 [Type: Text Channel] (Mode: MEDIA_OBSERVATION)
├── 🐸 #meme🐸             - ID: 1556611697152630885 [Type: Text Channel] (Mode: HUMOR_OBSERVATION)
├── ❓ #questions          - ID: 1557699282239361076 [Type: Forum Channel] (Mode: FORUM_QA)
└── 💡 #suggestions        - ID: 1557699285255192637 [Type: Forum Channel] (Mode: FORUM_SUGGESTIONS)

🌸 KAZUMI & ENTERTAINMENT (Category ID: 1557697978578378812)
├── 🌸 #kazumi-chat        - ID: 1555189316140015756 [Type: Text Channel] (Mode: ACTIVE_CHAT)
├── 🤖 #bot-commands       - ID: 1556626012022775849 [Type: Text Channel] (Mode: COMMANDS_ONLY)
├── 🎮 #games              - ID: 1557699124302712912 [Type: Text Channel] (Mode: GAMEPLAY_ONLY)
├── 🎉 #giveaways          - ID: 1557699127897493554 [Type: Text Channel] (Mode: GIVEAWAYS_ONLY)
├── 🗓️ #events             - ID: 1557699130850279475 [Type: Text Channel] (Mode: EVENTS_ONLY)
└── 🎵 #music-commands     - ID: 1557699133165412444 [Type: Text Channel] (Mode: MUSIC_CONTROL_ONLY)

VOICE (Category ID: 1546919407580876973)
├── 🎙️ Community Stage    - ID: 1557699287704535121 [Type: Stage Channel] (Mode: STAGE_EVENT_ONLY)
├── 🔊 General             - ID: 1546919407580876975 [Type: Voice Channel]
├── 🎮 Gaming Lounge       - ID: 1557699136885760050 [Type: Voice Channel]
├── 🎧 Music Lounge        - ID: 1557699139003752539 [Type: Voice Channel]
└── 💤 AFK                 - ID: 1557699144079114362 [Type: Voice Channel]

PRIVATE STAFF (Category ID: 1557699089356038146) — View Denied for @everyone
├── 🔒 #staff-chat         - ID: 1557699153084031037 [Type: Text Channel]
├── 🛡️ #mod-logs           - ID: 1557699156196462704 [Type: Text Channel] (Audit & moderation logging)
├── 🚨 #member-reports     - ID: 1557703893222293575 [Type: Forum Channel] (Staff incident tickets)
├── 📢 #staff-announcements- ID: 1557699160616996916 [Type: Text Channel]
├── 📋 #kazumi-logs        - ID: 1557699163133710396 [Type: Text Channel] (Bot diagnostic telemetry)
└── 🧪 #bot-testing        - ID: 1557699289801691136 [Type: Text Channel] (Safe test sandbox)
```

---

## 2. Role Hierarchy & Security Configuration

Order configured in Discord (top to bottom):

```text
👑 Owner
🛡️ Administrator
⚔️ Moderator
🔰 Trial Moderator
🎪 Event Host
🌸 Kazumi (Bot Role — Non-Administrator)
🌟 Member
🌱 Newcomer
@everyone
```

### Least Privilege Enforcement
- Kazumi does **NOT** possess `Administrator` permissions.
- Granted specific operational permissions: `View Channels`, `Send Messages`, `Read Message History`, `Embed Links`, `Attach Files`, `Add Reactions`, `Use External Emojis`, `Connect`, `Speak`, `Manage Channels`, `Manage Roles`.
- Moderation operations enforce role boundary checks preventing any action against users higher than or equal to Kazumi's role.

---

## 3. Strict Channel Policy & Feature Isolation Matrix

Features are gated **before** execution or AI API consumption in `discord_features/channel_policy.py`:

| Channel | Policy Mode | Allowed Feature Groups | Blocked Features |
| :--- | :--- | :--- | :--- |
| `#welcome` | `EVENTS_ONLY` | Welcome events, greetings | AI chat, games, roast, moderation |
| `#rules` | `READ_ONLY` | Rules, informational views | Normal chat, commands, games |
| `#announcements` | `ANNOUNCEMENTS_ONLY`| Official announcements | AI chat, games, informal chatting |
| `#server-guide` | `GUIDE_ONLY` | Guide navigation | Normal chat, mini-games, roast |
| `#roles` | `ROLE_SELECTION_ONLY`| Role assignment buttons | Privilege escalation, chat |
| `#general` | `OBSERVATION_ONLY` | Familiarity observation, reactions, single redirect on ping | Unsolicited AI replies, game spam, roasts |
| `#introductions` | `INTRODUCTIONS_ONLY`| Welcome reactions, member hellos | Automatic AI spam, games |
| `#media` | `MEDIA_OBSERVATION` | Explicit vision/OCR request | Automatic heavy OCR/vision API runs |
| `#memes` | `HUMOR_OBSERVATION` | Contextual reactions, explicit roast | Paragraph spam, mini-games |
| `#questions` | `FORUM_QA` | Q&A forum threads | Casual AI spam, game engine |
| `#suggestions` | `FORUM_SUGGESTIONS` | Suggestions, feedback | Unrelated automation |
| `#kazumi-chat` | `ACTIVE_CHAT` | Full companion, memory, conversation | Staff logs, audit records |
| `#bot-commands` | `COMMANDS_ONLY` | Slash commands & utilities | Free-form chat conversations |
| `#games` | `GAMEPLAY_ONLY` | Mini-games, arcade, leaderboards | Unrelated chat |
| `#giveaways` | `GIVEAWAYS_ONLY` | Giveaways, rolls, lucky draws | AI chat, game engine |
| `#events` | `EVENTS_ONLY` | Event notifications, reminders | AI chat |
| `#music-commands`| `MUSIC_CONTROL_ONLY`| Music controls (when active) | General AI chat |
| `Community Stage`| `STAGE_EVENT_ONLY` | Stage events, speaker management | General AI chat |
| `PRIVATE STAFF` | `STAFF_ONLY` | Logs, moderation, reports, diagnostics | Public access |

---

## 4. Personalized Welcome Poem System

- **Two-Line Couplet**: Every new arrival receives an exclusive, rhyming two-line poem naturally incorporating their display name.
- **Safety Sanitization**: `sanitize_display_name()` strips Discord mass mentions (`@everyone`, `@here`), markdown tags, URLs, control characters, and truncation beyond 32 chars.
- **Resilient Fallback**: 10 hand-crafted poetic couplets ensure instant delivery if the AI API is rate-limited or unavailable.
- **Join Deduplication**: In-memory and cache locks deduplicate joins across a 180-second window, preventing re-welcome loops on reconnects or nickname updates.
