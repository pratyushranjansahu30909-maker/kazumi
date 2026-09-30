# 🌸 Kazumi Feature Catalog

This document details all active features, commands, cognitive capabilities, and behavioral systems in Kazumi.

---

## 1. Core AI Companion Features

### 1.1 Personality & Emotional System
- **Core Identity**: Kazumi is an affectionate, warm, slightly teasing, emotionally intelligent anime companion.
- **Creator Lore**: Kazumi immediately recognizes **Aamir the Chad** and **Sir Shan D. First** as her creators and loving father figures.
- **Affection System**: Tracks relationship affection percentage (0% to 100%) and unlocks closer persona dynamics (e.g. Deredere, Protective).
- **Emotion Engine**: Real-time facial expression states and emotional valence (`kazumi_emotions.py`).
- **Text & Document OCR**: Optical character recognition for user-uploaded images and documents (`text_recognition.py`).

### 1.2 Original Core Slash Commands (16 Commands)
1. `/chat <message>`: Directly converse with Kazumi.
2. `/status`: Check affection level, mood, and persona.
3. `/diary`: View Kazumi's personal reflective entries.
4. `/reset`: Safely reset conversation session memory.
5. `/archetype`: Adjust persona mode (Empathetic, Unhinged, Tsundere, etc.).
6. `/mode`: Toggle behavioral modes.
7. `/voice`: Inspect voice profile settings.
8. Plus 9 utility and diagnostic subcommands.

---

## 2. Advanced Discord Bot Feature Suite (43 Commands)

### 2.1 Server Administration & Moderation
- `/warn <user> <reason>`: Issues formal persistent warning to a member.
- `/warnings <user>`: Displays warning count and violation history.
- `/clearwarnings <user>`: Clears all accumulated warnings.
- `/timeout <user> <duration> [reason]`: Applies native Discord timeout (`5m`, `1h`, `1d`).
- `/kick <user> [reason]`: Kicks member with server-side role hierarchy verification.
- `/ban <user> [reason]`: Bans member with server-side role hierarchy verification.
- `/unban <user_id> [reason]`: Unbans user ID.
- `/clear <amount>`: Bulk purges recent messages up to 100 at a time.
- `/slowmode <seconds>`: Adjusts channel slowmode interval.
- `/lock` & `/unlock`: Locks and unlocks public chat permissions in a channel.
- `/automod [enabled] [anti_spam] [anti_invites] [anti_links] [anti_mentions]`: Configures real-time chat defense.

### 2.2 Server Audit Logging
- `/logging set <channel>`: Sets audit logging target channel.
- `/logging status`: Displays current audit logging configuration.
- `/logging disable`: Disables audit logging.
- **Events Logged**: Joins, leaves, message deletions, message edits, bans, unbans, nickname changes, role additions/removals, and channel creation/deletion.

### 2.3 Community Onboarding & Roles
- `/welcome set <channel> [message]`: Custom welcome cards with `{user}`, `{username}`, `{server}`, `{count}`.
- `/welcome status` & `/welcome disable`.
- `/goodbye set <channel> [message]`, `/goodbye status`, `/goodbye disable`.
- `/autorole set <role>`: Automatically assigns role to new members upon joining.
- `/autorole remove <role>`, `/autorole status`, `/autorole clear`.
- `/reactionrole <title> <description> <role1> [role2]...`: Interactive button-role panels.

### 2.4 Support Tickets
- `/ticket panel`: Posts public panel with interactive **Create Ticket 📩** button.
- Creates private ticket text channels with staff-role permission overwrites.
- Interactive in-channel buttons: **Close 🔒**, **Claim 🙋**, **Transcript 📜**, **Reopen 🔓**, **Delete 🗑️**.

### 2.5 Giveaways
- `/giveaway create <duration> <prize> [winners]`: Interactive **🎉 Enter Giveaway** button.
- `/giveaway end <message_id>`: Ends giveaway and selects random winners.
- `/giveaway reroll <message_id>`: Rerolls new winners from valid entries.
- `/giveaway cancel <message_id>`: Cancels active giveaway.

### 2.6 Custom Commands & Tags
- `/customcommand add <name> <response>`: Adds per-guild custom command.
- `/customcommand delete <name>` & `/customcommand list`.
- Direct invocation via `/tag <name>` or `!<name>` in chat.

### 2.7 Server Information & Utilities
- `/serverinfo`: Server stats, channels, owner, security level.
- `/userinfo`: Member join date, account age, roles, permissions.
- `/avatar`: User avatar card.
- `/roleinfo`, `/channelinfo`, `/permissions`: Detailed permission breakdowns.
- `/ping`, `/uptime`, `/botinfo`, `/poll`, `/announce`, `/remind`, `/time`.

### 2.8 Voice & Music System
- `/play <query>`: Streams audio from YouTube / SoundCloud using `yt-dlp` and `FFmpeg`.
- `/pause`, `/resume`, `/skip`, `/queue`, `/nowplaying`, `/volume`, `/loop`, `/stop`.
- Interactive Discord UI buttons: ⏯️ Pause/Resume, ⏭️ Skip, 📜 Queue, ⏹️ Stop.

---

## 3. Social Intelligence & Observation Systems

- **Observation Modes**:
  - `ACTIVE_CHAT`: Full conversational replies, learning, and reactions.
  - `OBSERVATION_ONLY`: Silently learns and observes, never sends text replies, reacts contextually.
  - `DISABLED`: Completely ignored.
- **Smart Silence Engine**: Evaluates direct pings, recent bot replies, and channel context before speaking to prevent AI chatter spam.
- **Mood System**: 8 states (`happy`, `calm`, `excited`, `curious`, `sleepy`, `playful`, `concerned`, `neutral`) subtly influencing Kazumi's conversational tone.
- **Social Memory Graph**: Maps user topics, habits, and familiarity levels (`New` ➡️ `Recognised` ➡️ `Familiar` ➡️ `Regular` ➡️ `Very Familiar`).
- **Server Memory**: Discovers channel roles, projects, and community context without requiring repetitive explanations.
- **Conversation Continuity**: Resumes previous conversation topics across breaks.
- **Kazumi Moments**: Spontaneous, non-spammy community check-ins during quiet periods or milestones (24-hour rate-limited).
