#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE_DIR"

LOG_DIR="$BASE_DIR/logs"
PID_DIR="$LOG_DIR/pids"
BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend-main.log"
FRONTEND_LOG="$LOG_DIR/frontend-main.log"
mkdir -p "$LOG_DIR" "$PID_DIR"

if [[ -f "$BASE_DIR/.env" ]]; then
  set -a
  source "$BASE_DIR/.env"
  set +a
fi

stop_pid_file() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 1
    fi
    rm -f "$pid_file"
  fi
}

stop_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti:"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

PYTHON_BIN="$BASE_DIR/.venv/bin/python"
PIP_BIN="$BASE_DIR/.venv/bin/pip"
if [[ ! -x "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 -m venv "$BASE_DIR/.venv"
  else
    echo "Python 3 not found" >&2
    exit 1
  fi
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found" >&2
  exit 1
fi

"$PIP_BIN" install --upgrade pip -q
"$PIP_BIN" install -r requirements.txt -q
if [[ ! -d "$BASE_DIR/frontend/node_modules" ]]; then
  (cd "$BASE_DIR/frontend" && npm install)
fi

stop_pid_file "$BACKEND_PID_FILE"
stop_pid_file "$FRONTEND_PID_FILE"
stop_port 8000
stop_port 5173

nohup /usr/bin/setsid "$PYTHON_BIN" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --lifespan on >"$BACKEND_LOG" 2>&1 < /dev/null &
echo $! > "$BACKEND_PID_FILE"
nohup /usr/bin/setsid npm --prefix "$BASE_DIR/frontend" run dev -- --host 127.0.0.1 --port 5173 >"$FRONTEND_LOG" 2>&1 < /dev/null &
echo $! > "$FRONTEND_PID_FILE"
disown || true

for _ in {1..30}; do
  sleep 1
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1 && curl -fsS http://127.0.0.1:5173 >/dev/null 2>&1; then
    echo "ok"
    exit 0
  fi
done

echo "failed" >&2
exit 1
