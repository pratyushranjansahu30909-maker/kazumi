# 🌸 Kazumi Commands Reference

Kazumi features **59 registered slash commands** across core AI interaction, moderation, community automation, voice, and server utilities.

---

## 1. Core AI Companion Commands
| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/chat` | `<message>` | Direct conversational chat with Kazumi. |
| `/status` | None | Displays relationship affection percentage (56%), persona, and mood. |
| `/diary` | None | Reads reflective diary thoughts written by Kazumi. |
| `/reset` | None | Resets conversational session memory for the user. |
| `/archetype` | `<name>` | Adjusts personality archetype (Empathetic, Unhinged, Tsundere, etc.). |
| `/mode` | `<mode>` | Toggles conversational behavioral modes. |
| `/voice` | None | Inspects active voice profile settings. |

---

## 2. Server Moderation & Security
| Command | Arguments | Required Permission | Description |
| :--- | :--- | :--- | :--- |
| `/warn` | `<user> <reason>` | Manage Messages | Issues formal persistent warning to a member. |
| `/warnings` | `<user>` | Manage Messages | Displays warning count and violation history. |
| `/clearwarnings`| `<user>` | Manage Messages | Clears all accumulated warnings for a user. |
| `/timeout` | `<user> <duration> [reason]`| Moderate Members | Applies Discord native timeout (e.g. `10m`, `2h`, `1d`). |
| `/kick` | `<user> [reason]` | Kick Members | Kicks a member from the server. |
| `/ban` | `<user> [reason]` | Ban Members | Bans a member from the server. |
| `/unban` | `<user_id> [reason]` | Ban Members | Unbans a user ID. |
| `/clear` | `<amount>` | Manage Messages | Bulk purges messages (1-100). |
| `/slowmode` | `<seconds>` | Manage Channels | Sets channel slowmode (0-21600s). |
| `/lock` | None | Manage Channels | Locks current channel for `@everyone`. |
| `/unlock` | None | Manage Channels | Restores chat permissions in the channel. |
| `/automod` | `[enabled] [anti_spam]...` | Manage Server | Configures real-time chat protection. |

---

## 3. Server Logging & Audit Trail
| Command | Arguments | Required Permission | Description |
| :--- | :--- | :--- | :--- |
| `/logging set` | `<channel>` | Manage Server | Configures mod-log audit destination. |
| `/logging status` | None | Manage Server | Shows active logging channel and status. |
| `/logging disable`| None | Manage Server | Disables audit logging. |

---

## 4. Community & Onboarding
| Command | Arguments | Required Permission | Description |
| :--- | :--- | :--- | :--- |
| `/welcome set` | `<channel> [message]` | Manage Server | Configures welcome cards with template variables. |
| `/welcome status` | None | Manage Server | Views welcome system configuration. |
| `/welcome disable`| None | Manage Server | Disables welcome messages. |
| `/goodbye set` | `<channel> [message]` | Manage Server | Configures goodbye farewell cards. |
| `/goodbye status`| None | Manage Server | Views goodbye configuration. |
| `/goodbye disable`| None | Manage Server | Disables goodbye messages. |
| `/autorole set` | `<role>` | Manage Roles | Configures role assigned to new members on join. |
| `/autorole remove`| `<role>` | Manage Roles | Removes an autorole. |
| `/autorole status`| None | Manage Roles | Lists active autoroles. |
| `/autorole clear` | None | Manage Roles | Clears all autoroles. |
| `/reactionrole`| `<title> <desc> <role1>...`| Manage Roles | Creates interactive button role panel. |

---

## 5. Support Tickets
| Command | Arguments | Required Permission | Description |
| :--- | :--- | :--- | :--- |
| `/ticket` | `action:panel` | Manage Channels | Deploys public **Create Ticket 📩** panel. |
| `/ticket` | `action:setup [category] [role]` | Manage Channels | Configures ticket category and staff role. |
| `/ticket` | `action:add <user>` | Manage Channels | Adds a member to the current ticket. |
| `/ticket` | `action:remove <user>` | Manage Channels | Removes a member from the ticket. |
| `/ticket` | `action:close` | None | Closes the current ticket channel. |
| `/ticket` | `action:transcript` | None | Generates and uploads full text transcript. |

---

## 6. Giveaways
| Command | Arguments | Required Permission | Description |
| :--- | :--- | :--- | :--- |
| `/giveaway` | `action:create <duration> <prize> [winners]` | Manage Server | Launches interactive giveaway with button entries. |
| `/giveaway` | `action:end <message_id>` | Manage Server | Ends giveaway and selects random winners. |
| `/giveaway` | `action:reroll <message_id>` | Manage Server | Picks new random winners from existing entries. |
| `/giveaway` | `action:cancel <message_id>` | Manage Server | Cancels active giveaway. |

---

## 7. Custom Commands & Tags
| Command | Arguments | Required Permission | Description |
| :--- | :--- | :--- | :--- |
| `/customcommand` | `action:add <name> <response>` | Manage Server | Creates a custom text command. |
| `/customcommand` | `action:delete <name>` | Manage Server | Deletes custom command. |
| `/customcommand` | `action:list` | None | Lists all custom commands in the guild. |
| `/tag` | `<name>` | None | Invokes a custom command response. |

---

## 8. Server Info & Utility Tools
| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/serverinfo` | None | Detailed server statistics, channels, roles, and security level. |
| `/userinfo` | `[user]` | Member join date, account creation date, badges, roles, permissions. |
| `/avatar` | `[user]` | High-resolution avatar embed with direct image links. |
| `/roleinfo` | `<role>` | Role permissions, color, hoist status, and member count. |
| `/channelinfo`| `[channel]` | Channel topic, slowmode, category, and ID. |
| `/permissions`| `[user]` | Complete breakdown of guild permissions. |
| `/ping` | None | Bot websocket latency and response time. |
| `/uptime` | None | Continuous process runtime and boot timestamp. |
| `/botinfo` | None | Host environment, platform, library versions, and architecture. |
| `/poll` | `<question> <option1> <option2>...` | Multi-option community poll with reaction voting. |
| `/announce` | `<channel> <message> [title]` | Clean announcement card. |
| `/remind` | `<duration> <text>` | Scheduled reminder with persistent timer. |
| `/time` | `[timezone]` | Current server and international time. |

---

## 9. Voice & Music Commands
| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/play` | `<query>` | Plays audio or queues a song from YouTube/SoundCloud. |
| `/pause` | None | Pauses playback. |
| `/resume` | None | Resumes paused audio. |
| `/skip` | None | Skips current track. |
| `/queue` | None | Shows interactive upcoming track queue. |
| `/nowplaying` | None | Detailed track title, duration, and requester. |
| `/volume` | `<level>` | Sets volume (1–100%). |
| `/loop` | None | Toggles repeat mode. |
| `/stop` | None | Stops playback, clears queue, and leaves voice channel. |
