#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$BASE_DIR/.env" ]]; then
  set -a
  source "$BASE_DIR/.env"
  set +a
fi

# Unified Service URL
SERVER_URL="http://127.0.0.1:8000"
WORKBENCH_URL="$SERVER_URL/api/local-helper/workbench"
APP_URL="$SERVER_URL/platforms/xhs/fast-download"

CHROME_APP="/Applications/Google Chrome.app"
CHROME_PROFILE_DIR="$BASE_DIR/.chrome-helper-profile"
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/local_helper_launcher.log"
ENTRY_NAME="${LAUNCHER_DESKTOP_ENTRY_NAME:-XHS工作台.app}"

mkdir -p "$LOG_DIR"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" | tee -a "$LOG_FILE"
}

server_ready() {
  curl -fsS "$SERVER_URL/api/health" >/dev/null 2>&1
}

stop_existing() {
  local pids
  pids="$(lsof -ti:8000 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    log "Stopping existing unified server on 8000: $pids"
    kill $pids 2>/dev/null || true
    sleep 2
  fi
}

start_server() {
  log "Starting unified server in Terminal..."
  osascript <<EOF
tell application "Terminal"
  activate
  do script "cd $(printf '%q' "$BASE_DIR") && ./.venv/bin/python main.py --host 127.0.0.1 --port 8000"
end tell
EOF
}

open_url() {
  local target_url="$1"
  if [[ -d "$CHROME_APP" ]]; then
    mkdir -p "$CHROME_PROFILE_DIR"
    # Close existing workbench windows
    osascript <<'EOF' >/dev/null 2>&1 || true
tell application "Google Chrome"
  repeat with w in (every window)
    try
      set shouldClose to false
      repeat with t in (every tab of w)
        set tabUrl to URL of t
        if tabUrl starts with "http://127.0.0.1:8000/" or tabUrl starts with "http://127.0.0.1:5173/" then
          set shouldClose to true
          exit repeat
        end if
      end repeat
      if shouldClose then close w
    end try
  end repeat
end tell
EOF
    log "Opening target page: $target_url"
    open -na "$CHROME_APP" --args \
      --user-data-dir="$CHROME_PROFILE_DIR" \
      --new-window \
      "$target_url"
    return
  fi

  log "Chrome not found, falling back to default browser: $target_url"
  open "$target_url"
}

main() {
  log "Launcher started (Unified Port): $ENTRY_NAME"

  # If not ready, start it
  if ! server_ready; then
    stop_existing
    start_server
  fi

  for _ in {1..30}; do
    sleep 1
    if server_ready; then
      log "Unified server is healthy"
      open_url "$APP_URL"
      exit 0
    fi
  done

  log "Unified server did not become healthy in time"
  osascript -e 'display alert "XHS工作台启动失败" message "统一服务器未能在 30 秒内启动，请检查 logs/start-main.log" as critical'
  exit 1
}

main "$@"
