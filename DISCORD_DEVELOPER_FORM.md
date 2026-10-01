# 🌸 Kazumi AI Companion — Discord Developer Portal Form

This document provides **pre-filled, copy-paste ready answers** for every section and field in the **Discord Developer Portal** ([discord.com/developers/applications](https://discord.com/developers/applications)).

---

## 1. General Information

| Field | Value to Enter |
| :--- | :--- |
| **App Name** | `Kazumi` |
| **App Icon** | Upload `portfolio/public/favicon.ico` or any Kazumi avatar portrait. |
| **Tags** | `ai`, `companion`, `roleplay`, `social`, `entertainment` |

### **Description / About Me** *(Copy & Paste)*:
```markdown
🌸 **Kazumi (和美) — Your Cozy AI Server Companion**

Kazumi is an emotionally intelligent anime companion bot crafted to bring warm, uplifting, and empathetic conversations to your Discord community.

✨ **Key Features:**
• **Conversational Chat**: Talk naturally by mentioning `@Kazumi`, replying to her messages, or using `/chat`.
• **Persistent Bond & Affection**: Remembers your unique friendship, earning Cozy Points and affection hearts over time.
• **Daily Diaries & Horoscopes**: Read her daily reflections with `/diary` or get personalized celestial readings with `/horoscope`.
• **Personality Archetypes**: Switch between *Deredere* (Loving), *Teasing*, *Kuudere*, and *Tsundere* with `/persona`.
• **Cozy Quests & Goals**: Level up your companion bond through daily milestones (`/quests`).
• **Privacy First**: Complete control over your data with `/reset` to clear history anytime.
```

---

## 2. Bot Settings (`Bot` Tab)

| Setting | Recommendation |
| :--- | :--- |
| **Username** | `Kazumi` |
| **Public Bot** | **ON** (Allows others to invite Kazumi, or keep OFF for private server only) |
| **Requires OAuth2 Code Grant** | **OFF** |

### **Privileged Gateway Intents**
> [!IMPORTANT]
> You **MUST** enable these toggles under the **Privileged Gateway Intents** section:

1. **PRESENCE INTENT**: *Optional* (Leave OFF unless displaying custom user activities)
2. **SERVER MEMBERS INTENT**: **ON** *(Allows personalized greetings and user display name recognition)*
3. **MESSAGE CONTENT INTENT**: **ON** ⚠️ *(Mandatory: Needed for Kazumi to read chat messages when mentioned or replied to)*

---

## 3. Privileged Gateway Intents & App Verification Form
*(If prompted by Discord for verification or intent justification)*

### Question 1: What is the primary purpose of your application?
> "Kazumi is an empathetic, AI-powered companion bot that fosters a warm, engaging, and friendly atmosphere in Discord communities. She provides conversational support, daily reflective diary entries, celestial horoscopes, cozy mini-games, and personalized affection progression."

### Question 2: Why does your bot need the Message Content Intent?
> "Kazumi strictly uses the Message Content Intent to read messages where users interact with her—specifically when users mention `@Kazumi`, reply to her previous messages in a thread, or speak in designated companion text channels. The message text is passed to her cognitive engine to generate real-time conversational responses."

### Question 3: What specific commands or features rely on message content?
> "1. **Direct Mentions:** Responding naturally when a user mentions `@Kazumi <message>` in text channels.
> 2. **Contextual Thread Conversations:** Continuing multi-turn discussions when users click 'Reply' on Kazumi's messages.
> 3. **Interactive Mini-Games & Roleplay:** Playing ambient text-based games and casual server banter without requiring command prefixes."

### Question 4: How is user data stored, processed, and protected?
> "All user messages are processed in real-time in memory. Chat histories are indexed solely by unique Discord User IDs for conversational continuity and relationship progression. Data is never shared with third parties or used for external advertising. Users can immediately wipe all stored memory and chat logs at any time using the `/reset` slash command."

### Question 5: Step-by-Step Testing Instructions for Discord Reviewers:
> "1. Invite Kazumi to your test server using the generated bot OAuth2 link.
> 2. Send `@Kazumi Hello! How are you doing today?` in any text channel.
>    • **Expected:** Kazumi shows a typing indicator and responds with a warm, conversational reply.
> 3. Click 'Reply' on Kazumi's message and type a follow-up question.
>    • **Expected:** Kazumi detects the reply reference and continues the conversation.
> 4. Test Slash Commands:
>    • `/chat message:Tell me a cozy bedtime story` → Returns story.
>    • `/status` → Displays user's affection level, cozy points, and current archetype.
>    • `/horoscope sign:Gemini` → Returns cosmic reading and lucky gifts.
>    • `/diary` → Displays her latest journal entry.
>    • `/persona archetype:Teasing` → Shifts personality tone to playful/teasing.
>    • `/reset` → Clears session conversation history."

---

## 4. OAuth2 & Bot Invite URL Generator (`OAuth2` Tab)

### Selected Scopes:
- [x] `bot`
- [x] `applications.commands`

### Selected Bot Permissions:
- [x] **Send Messages** (`2048`)
- [x] **Send Messages in Threads** (`274877906944`)
- [x] **Embed Links** (`16384`)
- [x] **Attach Files** (`32768`)
- [x] **Read Message History** (`65536`)
- [x] **Add Reactions** (`64`)
- [x] **View Channels** (`1024`)

### Generated Permissions Integer:
`277025507392`

### Template Invite URL:
```text
https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=277025507392&scope=bot%20applications.commands
```
*(Replace `YOUR_CLIENT_ID` with your Discord Application Client ID from General Information).*

---

## 5. Connecting Kazumi to Discord

Once you copy your **Bot Token** from the `Bot` tab:

### Method A: Edit `.env` file
Add your token to `.env`:
```env
DISCORD_BOT_TOKEN=your_actual_bot_token_here
DISCORD_CHANNEL_ID=optional_channel_id_here
DISCORD_PREFIX=!k 
```

### Method B: Run directly via CLI
```bash
python discord_bot.py --token "your_actual_bot_token_here"
```
