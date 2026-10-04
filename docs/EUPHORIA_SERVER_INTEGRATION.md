# 🌸 Euphoria Server Integration & Launch Guide

This master guide provides the complete setup, channel architecture, role hierarchy, permission matrix, and step-by-step onboarding configuration for launching **Kazumi** inside your Discord server, **Euphoria**.

---

## 1. Euphoria Channel Architecture

Organize your server categories and text/voice channels as follows. This layout balances community engagement, entertainment, and staff moderation while preventing conversational bot spam in general channels.

```text
📁 INFORMATION (Read-only for @everyone)
├── 📌 #welcome              - Newcomer greeting cards & arrivals (Kazumi /welcome)
├── 📜 #rules                - Community guidelines & server expectations
├── 📢 #announcements        - Official news, updates & events (Kazumi /announce)
├── 🧭 #server-guide         - Channel directory and feature guide
└── 🎭 #roles                - Interactive button-role assignment (Kazumi /reactionrole)

📁 COMMUNITY (Public discussion — Kazumi is in OBSERVATION_ONLY mode)
├── 💬 #general              - Main social lounge (Kazumi observes & reacts; no text spam)
├── 👋 #introductions        - New member bios and welcomes
├── 📸 #media                - Pictures, art, screenshots (Vision OCR via /ocr)
├── 🐸 #memes                - Humor and funny clips
├── ❓ #questions            - Community questions & discussions
└── 💡 #suggestions          - Member feedback & ideas

📁 KAZUMI & ENTERTAINMENT (Active companion & bot playground)
├── 🌸 #kazumi-chat          - Dedicated 24/7 AI companion chat (ACTIVE_CHAT mode)
├── 🤖 #bot-commands         - Text & utility slash commands (/status, /persona, /diary)
├── 🎮 #games                - 20 multiplayer & solo games (/game, /dailygame, /arcade)
├── 🎉 #giveaways            - Interactive community giveaways (/giveaway)
├── 🗓️ #events               - Scheduled activities & reminder alerts (/remind)
└── 🎵 #music-commands       - Voice stream controls & queue buttons (/play, /queue)

📁 VOICE CHANNELS
├── 🔊 General Voice
├── 🎮 Gaming Lounge
├── 🎧 Music Lounge          - High-bitrate music listening channel
└── 💤 AFK

📁 PRIVATE STAFF (Hidden from @everyone; Staff & Kazumi only)
├── 🔒 #staff-chat           - Internal moderator discussions
├── 🛡️ #mod-logs             - Formatted audit & AutoMod alerts (Kazumi /logging)
├── 🚨 #member-reports       - Member issue queues & ticket transcripts
├── 📢 #staff-announcements  - Internal staff notices
├── 📋 #kazumi-logs          - Bot health diagnostics & security alerts
└── 🧪 #bot-testing          - Test channel for new commands & configurations
```

---

## 2. Channel Behavior Matrix for Kazumi

Kazumi automatically respects channel boundaries to avoid disrupting conversations:

| Channel Category / Channel | Operational Mode | Kazumi Behavior |
| :--- | :---: | :--- |
| `#kazumi-chat`, Direct Messages | **`ACTIVE_CHAT`** | Responds naturally to ongoing chat, mentions, and commands. |
| `#general`, `#media`, `#memes` | **`OBSERVATION_ONLY`** | Silently observes to update social familiarity; may add context-aware emoji reactions (`😂`, `🎉`, `❤️`). **Never sends unprompted text**. |
| Observation Channel with Ping | **`REDIRECT`** | If pinged in `#general`, replies once politely: *"Hi! To keep this channel clean, let's chat in #kazumi-chat or DMs! ✨"* |
| `#welcome` | **`EVENTS_ONLY`** | Dispatches customized companion welcome embed cards on member join. |
| `#mod-logs` | **`AUDIT_ONLY`** | Posts formatted embed logs for warns, kicks, bans, timeouts, and AutoMod triggers. |
| Private Staff Channels | **`STAFF_ONLY`** | Standard members cannot view or read history. |

---

## 3. Least-Privilege Role Hierarchy

To ensure safety, Kazumi adheres strictly to Discord role hierarchy. **Never grant Kazumi the `Administrator` permission**. Position Kazumi's integration role directly above standard members and below moderators:

```text
[Position 100]  👑 Owner              (Complete server ownership)
[Position 90]   ⚡ Administrator      (Full administrative management)
[Position 75]   🛡️ Moderator          (Manage messages, timeout, kick, ban)
[Position 65]   🔨 Trial Moderator    (Manage messages, warn, timeout)
[Position 55]   🎉 Event Host         (Manage events, giveaways, stage speakers)
[Position 40]   🌸 Kazumi (Bot Role)  (Assigned strictly needed permissions)
[Position 20]   ⭐ Member             (Verified regular community member)
[Position 10]   🌱 Newcomer           (Newly joined member awaiting rules review)
[Position 0]    @everyone             (Base default permissions)
```

### Required Bot Permissions:
* **Manage Roles** *(Needed strictly to assign roles lower than Kazumi's role, e.g. AutoRole `@Member`)*
* **Manage Channels** *(Needed to create and delete private `#ticket-XXXX` support channels)*
* **Kick Members** & **Ban Members** *(For moderation commands)*
* **Moderate Members (Timeout)** *(For automated and manual mute/timeout)*
* **Send Messages & Embed Links** *(Core responses and cards)*
* **Attach Files & Read Message History** *(For Vision OCR and conversation continuity)*
* **Add Reactions & Use External Emojis** *(For contextual emotional reactions)*
* **Connect & Speak** *(For Voice/Music system)*

---

## 4. Step-by-Step Server Setup Checklist

Once Kazumi is invited to Euphoria, run these commands in `#bot-testing` to configure your server in 2 minutes:

### Step 1: Set Audit & Moderation Logging
```text
/logging action:Set Log Channel channel:#mod-logs
```
*Effect: Kazumi will now send all join/leave, message edit/delete, warning, timeout, kick, and ban logs to `#mod-logs`.*

### Step 2: Configure Welcome Greetings
```text
/welcome channel:#welcome
```
*(Optional: Customize the message template with `/welcome message:🌸 Welcome to Euphoria, {user}! Please check out #rules and say hi in #introductions! ✨`)*

### Step 3: Configure AutoRole for New Members
```text
/autorole action:Add / Set AutoRole role:@Member
```
*Effect: New arrivals automatically receive the `@Member` role.*

### Step 4: Configure AutoMod Protection
```text
/automod rule:anti_spam enabled:True
/automod rule:anti_invites enabled:True
/automod rule:anti_mentions enabled:True
```
*Effect: Server is actively guarded against rapid message floods, unauthorized Discord invite links, and mass pings.*

### Step 5: Launch Support Ticket Panel (Optional)
In `#bot-commands` or `#server-guide`:
```text
/ticket
```
*Effect: Posts an interactive button panel allowing members to open private staff support tickets.*

---

## 5. Security & Isolation Guarantees

1. **Staff Channel Privacy**:
   - In category `PRIVATE STAFF`, ensure `@everyone` has `View Channel = ❌ DENIED`.
   - Only `@Moderator`, `@Administrator`, and `🌸 Kazumi` have `View Channel = ✅ ALLOWED`.
2. **Hierarchy Protection**:
   - Kazumi cannot be used by a rogue moderator to ban or timeout the Server Owner or higher-ranked Administrators.
   - Kazumi cannot moderate any member whose top role is higher than or equal to her own role.
3. **Cross-User Data Isolation**:
   - Each member's conversation history, affection level, Cozy Points, and game statistics are strictly indexed by stable Discord User IDs (`author.id`).
   - One member cannot reset, inspect, or tamper with another member's companion relationship.
4. **Anti-Recursion Safety**:
   - Kazumi ignores messages from herself and all other bots (`message.author.bot = True`).
   - Bot responses will never trigger recursive conversation loops.
