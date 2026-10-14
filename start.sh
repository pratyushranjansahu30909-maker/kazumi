#!/bin/bash

# Determine project directory dynamically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure logs and persistent memory directories exist
export ISA_MEMORY_DIR="${ISA_MEMORY_DIR:-$SCRIPT_DIR/isa_memory}"
export KAZUMI_SUPERVISED=1
export PYTHONUNBUFFERED=1
export PORT="${PORT:-7860}"
mkdir -p "$SCRIPT_DIR/logs" "$ISA_MEMORY_DIR"

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

echo "🌸 Starting Kazumi Standalone Discord AI Companion using $PYTHON_CMD..."

# Trap signals for graceful shutdown
cleanup() {
    echo "🌸 Received termination signal. Gracefully shutting down Kazumi Discord Bot..."
    pkill -TERM -f "discord_bot.py" 2>/dev/null || true
    exit 0
}
trap cleanup SIGTERM SIGINT

# Run discord_bot.py with supervisor loop in foreground
while true; do
    echo "[$(date)] 🌸 Launching Kazumi Discord Bot..."
    $PYTHON_CMD -u discord_bot.py
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 42 ]; then
        echo "[$(date)] ⚠️ Kazumi Discord Bot exited with code 42 (Configuration Error / Missing Token). Pausing 60s..."
        sleep 60
    elif [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date)] 🌸 Kazumi Discord Bot stopped cleanly with code 0. Exiting supervisor."
        exit 0
    else
        echo "[$(date)] ⚠️ Kazumi Discord Bot process exited with code $EXIT_CODE. Restarting in 5 seconds..."
        sleep 5
    fi
done
