# 🌸 Kazumi Setup Guide

Step-by-step instructions to get Kazumi running on Discord.

---

## 1. Prerequisites

- Python 3.10+ (tested with Python 3.10, 3.12, and 3.14).
- A Discord Bot Application on the [Discord Developer Portal](https://discord.com/developers/applications).
- API Key for LLM completions (OpenAI, Claude, or local Ollama).
- Optional: `ffmpeg` and `yt-dlp` for music playback.

---

## 2. Discord Developer Portal Setup

1. Create a **New Application** named `Kazumi`.
2. Navigate to **Bot**:
   - Enable **Privileged Gateway Intents**:
     - ✅ **Presence Intent**
     - ✅ **Server Members Intent**
     - ✅ **Message Content Intent**
   - Click **Reset Token** and copy the bot token.
3. Navigate to **OAuth2 ➡️ URL Generator**:
   - Select scopes: `bot`, `applications.commands`.
   - Select permissions:
     - `Administrator` (Recommended for full moderation, role management, and channel management).
   - Open generated invite URL in browser to invite Kazumi to your server.

---

## 3. Local Installation

```bash
git clone https://github.com/pratyushranjansahu30909-maker/kazumi.git
cd kazumi
pip install -r requirements.txt
pip install PyNaCl yt-dlp
```

Create a `.env` file in the root directory:
```env
DISCORD_BOT_TOKEN=your_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
PREFIX=!k 
```

Launch the bot:
```powershell
python -u discord_bot.py
```
