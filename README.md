---
title: Kazumi Companion
emoji: 🌸
colorFrom: pink
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# 🌸 Kazumi AI Companion & Discord Bot

[![Discord](https://img.shields.io/badge/Discord-Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

**Kazumi (和美)** is an emotionally intelligent, warm, and highly capable anime girl Discord companion bot. Built entirely in Python, Kazumi combines advanced conversational AI, realistic emotional expressions, persistent relationship memory, full server moderation, interactive music playback, and community engagement features into a single, standalone Discord bot.

> **Zero Website Dependencies**: Kazumi operates 100% autonomously as a Discord bot. No external web server, frontend dashboard, or Node.js runtime is required.

---

## ✨ Core Capabilities

### 1. 🌸 Empathetic AI Companion Core
- **Conversational Intelligence**: Empathetic, supportive, and context-aware responses powered by OpenAI API backend integrations.
- **Dynamic Mood & Emotion Engine (`kazumi_emotions.py`)**: Spontaneously expresses realistic emotional states and physical micro-expressions (blushing when flustered `😳`, playful teasing `😏`, deep affection `🥰`, dramatic cute pouting `😤`, starry-eyed excitement `✨`, cozy sleepy yawns `🥱`, gentle comfort `🌸`).
- **Archetype Switching**: Seamlessly toggle between personality modes with `/persona`: *Deredere* (Loving), *Teasing*, *Kuudere*, *Tsundere*, and *Unhinged / Savage Roast* mode.
- **Persistent Bond & Affection Progression**: Tracks friendship intimacy, affection level (0–100%), Cozy Points, and daily milestones (`/status`, `/quests`).
- **Daily Diaries & Horoscopes**: Kazumi writes daily personal reflections (`/diary`) and provides custom celestial readings with lucky gifts (`/horoscope`).
- **Precision OCR & Document Vision (`text_recognition.py`)**: Reads, transcribes, and discusses text extracted from user images, screenshots, handwritten notes, memes, documents, and code files via Discord chat or slash commands (`/recognize_text`, `/ocr`).

### 2. 🛡️ Server Moderation & AutoMod Suite
- **Complete Moderation Commands**: `/warn`, `/warnings`, `/clearwarnings`, `/timeout`, `/kick`, `/ban`, `/unban`, `/clear`, `/slowmode`, `/lock`, `/unlock`.
- **Real-Time AutoMod Protection**: Automatically mitigates message floods, duplicate spam, mass mentions, unauthorized invite links, arbitrary links, and prohibited word lists.
- **Comprehensive Audit Logging (`/logging`)**: Formatted embed logging for member joins, leaves, message edits, message deletions, bans, unbans, and role updates.

### 3. 🎵 High-Fidelity Music System
- **Voice Channel Playback**: Stream audio directly from YouTube, Soundcloud, and direct media URLs via `yt-dlp` and `FFmpeg`.
- **Interactive Playback Controls**: Dedicated Discord button UI for play/pause, skip, stop, loop, queue navigation, and volume control (`/play`, `/pause`, `/resume`, `/skip`, `/queue`, `/nowplaying`, `/volume`, `/loop`, `/stop`).

### 4. 🤝 Community Engagement & Utility
- **Customizable Welcome & Goodbye**: Card templates and greeting channels (`/welcome`, `/goodbye`).
- **Role Management**: Automated join roles (`/autorole`) and interactive button role assignment panels (`/reactionrole`).
- **Support Ticket System**: Private member-staff ticket channels with one-click closing and automated text transcripts (`/ticket`).
- **Giveaway Engine**: Interactive button-entry giveaways with background timer workers (`/giveaway`).
- **Community Tools**: `/poll`, `/announce`, `/remind`, `/time`, custom command management (`/customcommand`, `!<tag>`), and interactive mini-games (Connect 4, Tic-Tac-Toe, Trivia).

### 5. 🧠 Persistent Memory & Privacy
- **Atomic Local Persistence (`isa_memory/`)**: User profiles, affection levels, moderation cases, and server settings are stored in atomic, thread-safe JSON files with `.bak` rollback safety and buffer syncing (`os.fsync`).
- **Privacy First**: Complete user data autonomy with `/reset` to immediately wipe conversational session memory.

---

## 🛠️ Technology Stack

- **Runtime**: Python 3.11+
- **Bot Framework**: `discord.py` (v2.3+)
- **AI Backend**: `openai` (v1.0+)
- **Voice & Media**: `yt-dlp`, `PyNaCl`, `FFmpeg`
- **Vision & Imaging**: `Pillow`, `pytesseract`
- **Cloud Telemetry**: Native `aiohttp.web` micro-service providing `/health` checks on `$PORT`

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11 or higher
- FFmpeg installed and available on system `PATH` (for voice/music playback)
- A Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/pratyushranjansahu30909-maker/kazumi.git
cd kazumi

# Create and activate a virtual environment
python -m venv venv
# Linux / macOS:
source venv/bin/activate
# Windows:
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` (or create `.env`) and configure your tokens:
```env
# Required Discord credentials
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# Required for AI chat capabilities
OPENAI_API_KEY=your_openai_api_key_here

# Optional configuration
PREFIX=!k 
DISCORD_CHANNEL_ID=
PORT=10000
```

> [!IMPORTANT]
> In the [Discord Developer Portal](https://discord.com/developers/applications), under **Bot** -> **Privileged Gateway Intents**, enable:
> 1. ✅ **Server Members Intent** (For welcome cards and role automation)
> 2. ✅ **Message Content Intent** (For chat conversations and mentions)

---

## 💻 Running Kazumi

### Option A: Direct Python Execution
```bash
python -u discord_bot.py
```

### Option B: Windows 24/7 Supervisors
Kazumi includes pre-configured Windows scripts for hands-off 24/7 operation:
- `install_kazumi_autostart.bat`: Registers Kazumi in Windows Startup so she launches automatically upon PC boot.
- `launch_kazumi_silent.vbs`: Starts Kazumi silently in the background with zero popup command windows.
- `run_kazumi_bot.bat`: Launches Kazumi in an interactive console window with automatic crash restart.
- `status_kazumi.bat`: Checks if Kazumi is running, showing PID, memory, and uptime.
- `stop_kazumi.bat`: Cleanly terminates all running Kazumi bot processes and supervisors.

### Option C: Docker Deployment
Build and run Kazumi in a clean Python 3.11 container:
```bash
# Build the Docker image
docker build -t kazumi .

# Run the container
docker run -d --name kazumi-bot --env-file .env -p 10000:10000 kazumi
```

### Option D: Render Cloud Deployment
Kazumi is fully prepared for one-click deployment to **Render** as a Docker Web Service:
1. Connect your GitHub repository to Render.
2. Select **Web Service** with **Docker** runtime (or use `render.yaml`).
3. Set the Health Check path to `/health`.
4. Add your secret environment variables (`DISCORD_BOT_TOKEN`, `OPENAI_API_KEY`).
5. Render will automatically build the `Dockerfile`, pass the `/health` check on port `10000`, and keep Kazumi running 24/7.

---

## 🎮 Slash Command Catalog

| Category | Command | Description |
| :--- | :--- | :--- |
| **AI Companion** | `/chat <message>` | Send a cozy message to Kazumi |
| | `/roast [target]` | Deliver an unapologetically savage roast or comeback 💀🔥 |
| | `/unhinged [True/False]` | Toggle savage unhinged mode 💀🔥 |
| | `/persona <archetype>` | Switch personality (Deredere, Teasing, Kuudere, Tsundere, Unhinged) |
| | `/status` | View affection level, Cozy Points, and current archetype |
| | `/diary` | Read Kazumi's personal daily journal reflections |
| | `/quests` | View daily companion bonding quests |
| | `/horoscope <sign>` | Receive daily celestial astrological reading and lucky gifts |
| | `/reset` | Clear your conversational history for a fresh start |
| **Vision & OCR** | `/recognize_text [image]` | Extract and discuss text from an attached image or screenshot |
| **Music & Voice** | `/play <query_or_url>` | Play audio in your active voice channel |
| | `/pause` / `/resume` | Pause or resume current playback |
| | `/skip` | Skip the current track |
| | `/queue` | Display currently queued tracks |
| | `/nowplaying` | Show detailed track embed with interactive button controls |
| | `/volume <1-100>` | Adjust playback volume |
| | `/stop` | Clear queue and disconnect from voice |
| **Moderation** | `/warn <user> <reason>` | Issue a formal warning to a member |
| | `/warnings <user>` | View warning history for a member |
| | `/timeout <user> <duration>` | Mute a member for a specified duration |
| | `/kick <user> [reason]` | Kick a member from the server |
| | `/ban <user> [reason]` | Ban a member from the server |
| | `/automod <rule> <enabled>` | Configure real-time server protection rules |
| | `/logging <channel>` | Configure server audit event logging channel |
| **Community** | `/ticket` | Open an interactive private support ticket |
| | `/giveaway <prize> <time>` | Launch a community giveaway with countdown and winner selection |
| | `/poll <question> <options>` | Create an interactive community reaction poll |
| | `/remind <time> <message>` | Schedule a personal or channel reminder |
| | `/welcome` / `/goodbye` | Setup custom arrival/departure messages |
| | `/autorole <role>` | Configure automatic role assignment for new members |
| | `/help` | Interactive catalog of all commands and server features |

---

## 📄 License

This project is licensed under the MIT License.
