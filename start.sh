#!/usr/bin/env bash
# Start webapp_v2: pure-Python backend (no Wolfram) + React frontend.
# Usage: bash start.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Backend ──────────────────────────────────────────────────────────────────
echo "Starting backend on http://localhost:8001 ..."
cd "$SCRIPT_DIR/backend"

# Install Python dependencies if needed
if ! python3 -c "import fastapi, networkx" 2>/dev/null; then
  echo "Installing Python dependencies..."
  pip3 install -r requirements.txt
fi

uvicorn main:app --host 0.0.0.0 --port 8001 --reload &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "Starting frontend on http://localhost:5174 ..."
cd "$SCRIPT_DIR/frontend"

# Install npm dependencies if needed
if [ ! -d node_modules ]; then
  echo "Installing npm dependencies..."
  npm install
fi

npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "Open http://localhost:5174 in your browser."
echo "Press Ctrl+C to stop both servers."

# Wait and forward Ctrl+C to both processes
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
