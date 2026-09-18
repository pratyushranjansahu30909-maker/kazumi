#!/bin/bash

# Ensure logs directory exists
mkdir -p /app/logs

# Start Kazumi Discord Bot supervisor in background if DISCORD_BOT_TOKEN is configured
if [ -n "$DISCORD_BOT_TOKEN" ]; then
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
else
    echo "⚠️ DISCORD_BOT_TOKEN not found in environment, skipping Discord bot."
fi

# Start Kazumi Web Portfolio in foreground
echo "🌐 Starting Kazumi Web Interface on port ${PORT:-7860}..."
cd /app/portfolio
exec npm start
