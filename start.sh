#!/bin/bash

# Determine project directory dynamically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure logs and persistent memory directories exist
mkdir -p "$SCRIPT_DIR/logs" "$SCRIPT_DIR/isa_memory"

# Source .env if present
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "📄 Sourcing environment from $SCRIPT_DIR/.env..."
    set -a
    source "$SCRIPT_DIR/.env" 2>/dev/null || true
    set +a
fi

# Detect python executable (python3 or python)
PYTHON_CMD="python3"
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
fi

echo "🌸 Starting Kazumi Discord Bot supervisor in background using $PYTHON_CMD..."
(
  while true; do
    echo "[$(date)] 🌸 Launching Kazumi Discord Bot..." >> "$SCRIPT_DIR/logs/discord_bot.log"
    $PYTHON_CMD -u discord_bot.py >> "$SCRIPT_DIR/logs/discord_bot.log" 2>&1
    EXIT_CODE=$?
    echo "[$(date)] ⚠️ Kazumi Discord Bot process exited with code $EXIT_CODE. Restarting in 5 seconds..." >> "$SCRIPT_DIR/logs/discord_bot.log"
    sleep 5
  done
) &

# Start Kazumi Web Portfolio in foreground
PORT="${PORT:-10000}"
echo "🌐 Starting Kazumi Web Interface on port $PORT..."
cd "$SCRIPT_DIR/portfolio"
exec npm start

