#!/usr/bin/env bash
# ==============================================================================
# Script to run Personal Job Agent in the background on your Linux machine
# ==============================================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Please create it first:"
    echo "python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

echo "Starting Personal Job Agent in background (logs: app.log)..."
nohup "$DIR/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &

PID=$!
echo "Personal Job Agent is running with PID: $PID"
echo "Open dashboard at: http://localhost:8000"
echo "To stop: kill $PID"
