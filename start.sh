#!/bin/bash

# Ensure logs directory exists
mkdir -p /app/logs

# Source .env if present
if [ -f /app/.env ]; then
    echo "📄 Sourcing environment from /app/.env..."
    set -a
    source /app/.env 2>/dev/null || true
    set +a
fi

echo "🌸 Starting Kazumi Discord Bot supervisor in background..."
(
  while true; do
    echo "[$(date)] 🌸 Launching Kazumi Discord Bot..." >> /app/logs/discord_bot.log
    python -u discord_bot.py >> /app/logs/discord_bot.log 2>&1
    EXIT_CODE=$?
    echo "[$(date)] ⚠️ Kazumi Discord Bot process exited with code $EXIT_CODE. Restarting in 5 seconds..." >> /app/logs/discord_bot.log
    sleep 5
  done
) &

# Start Kazumi Web Portfolio in foreground
PORT="${PORT:-10000}"
echo "🌐 Starting Kazumi Web Interface on port $PORT..."
cd /app/portfolio
exec npm start
