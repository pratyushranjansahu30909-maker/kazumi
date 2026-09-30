# 🌸 Kazumi Troubleshooting Guide

Common issues, error codes, and operational fixes.

---

## 1. Bot Is Offline
- **Cause 1**: `DISCORD_BOT_TOKEN` is missing, expired, or invalid.
  - *Fix*: Check `.env` file and regenerate token from Discord Developer Portal.
- **Cause 2**: Process already running on another terminal.
  - *Fix*: Check Named Mutex / Port 49281 lock. Stop the other process before starting a new one.

---

## 2. Slash Commands Not Appearing in Discord
- **Cause**: Command tree sync latency.
  - *Fix*: Global commands take up to 5-10 minutes to populate across all Discord clients. Restarting your Discord desktop/mobile app forces a local command cache refresh.

---

## 3. Music Plays Nothing or Gives Voice Error
- **Cause 1**: `PyNaCl` library missing on host machine.
  - *Fix*: `pip install PyNaCl`.
- **Cause 2**: `ffmpeg` missing in system PATH.
  - *Fix*: On Windows: `winget install Gyan.FFmpeg`. On Linux: `sudo apt-get install -y ffmpeg`.

---

## 4. Hugging Face Spaces ECONNRESET
- **Cause**: Cloudflare blocks certain Hugging Face shared free-tier egress IP ranges from connecting to Discord Gateway on port 443.
  - *Fix*: Host on Render Cloud (`render.yaml`), Railway, or an independent Linux VPS where egress is unblocked.
