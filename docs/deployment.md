# 🌸 Kazumi Deployment & Operations Guide

This guide covers deployment options, environment variables, health checks, automatic restart configurations, and operational troubleshooting for Kazumi.

---

## 1. Hosting Environments

Kazumi can run either as a local service or as a 24/7 autonomous remote cloud instance.

### 1.1 Local Host (Windows / Linux / macOS)
- **Execution Command**:
  ```powershell
  python -u discord_bot.py
  ```
- **Concurrency Protection**:
  - Windows: Named Mutex (`Global\KazumiDiscordBotRunningMutex`).
  - Cross-platform: TCP Loopback Mutex on port `49281`.
  - Prevents dual-gateway duplicate message loops when launched multiple times.

### 1.2 Remote Cloud VPS (Linux / Ubuntu 22.04+)
For 24/7 continuous operation independent of any personal computer:
1. Clone repository to `/opt/kazumi`:
   ```bash
   git clone https://github.com/pratyushranjansahu30909-maker/kazumi.git /opt/kazumi
   cd /opt/kazumi
   ```
2. Setup virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install PyNaCl yt-dlp
   sudo apt-get install -y ffmpeg
   ```
3. Configure `systemd` unit file (`/etc/systemd/system/kazumi.service`):
   ```ini
   [Unit]
   Description=Kazumi AI Discord Bot Daemon
   After=network.target

   [Service]
   Type=simple
   User=kazumi
   WorkingDirectory=/opt/kazumi
   ExecStart=/opt/kazumi/venv/bin/python -u /opt/kazumi/discord_bot.py
   Restart=always
   RestartSec=5
   EnvironmentFile=/opt/kazumi/.env

   [Install]
   WantedBy=multi-user.target
   ```
4. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable kazumi
   sudo systemctl start kazumi
   ```

### 1.3 Container Deployment (Docker / Hugging Face Spaces)
- The project includes a root `Dockerfile` and `supervisord` configuration running both the Express.js telemetry dashboard on port `7860` and the Python Discord bot daemon.
- Persistent volume storage mounts `/data/isa_memory` automatically when running inside Hugging Face Spaces.

---

## 2. Environment Variables Checklist

| Variable | Required | Description |
| :--- | :--- | :--- |
| `DISCORD_BOT_TOKEN` | **Yes** | Bot token from the Discord Developer Portal. |
| `DISCORD_CHANNEL_ID` | Optional | Dedicated primary chat channel ID (if left blank, bot listens across permitted guild channels). |
| `PREFIX` | Optional | Prefix command trigger (defaults to `!k `). |
| `OPENAI_API_KEY` | Recommended | Primary API key for LLM cognitive chat completions. |
| `ANTHROPIC_API_KEY`| Optional | Fallback LLM provider key. |
| `PORT` | Optional | Dashboard HTTP port (defaults to `7860`). |

---

## 3. Reliability & 24/7 Uptime Guarantees

1. **Automatic Discord Gateway Reconnection**:
   The bot loop wraps `bot.run(...)` inside an auto-reconnect retry loop with exponential backoff up to 60 seconds.
2. **Process Respawn**:
   Unhandled exceptions trigger clean process respawn via `os.execv`.
3. **Graceful Shutdown**:
   Listens for `SIGINT` / `SIGTERM` and releases the single-instance socket and Named Mutex before exiting.
4. **Data Durability**:
   All state updates are flushed and synced (`os.fsync`) with `.bak` rollback safety to eliminate write corruption risks during power outages or sudden process kills.
