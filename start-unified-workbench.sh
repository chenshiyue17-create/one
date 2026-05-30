#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE_DIR"

if [[ -f "$BASE_DIR/.env" ]]; then
  set -a
  source "$BASE_DIR/.env"
  set +a
fi

DESKTOP_DIR="$HOME/Desktop"
ARCHIVE_DIR="$DESKTOP_DIR/_XHS旧入口归档"
ENTRY_NAME="${LAUNCHER_DESKTOP_ENTRY_NAME:-XHS工作台.app}"
VISIBLE_APP="$DESKTOP_DIR/$ENTRY_NAME"
VISIBLE_COMMAND="$DESKTOP_DIR/启动_XHS工作台.command"
CANONICAL_COMMAND="$BASE_DIR/打开小红书工作台.command"
LEGACY_ITEMS=(
  "$DESKTOP_DIR/XHS全能工作站.app"
  "$DESKTOP_DIR/启动_XHS_ALL_IN_ONE.command"
  "$DESKTOP_DIR/启动_XHS全能工作站.command"
  "$DESKTOP_DIR/启动_XHS工作台.command"
)

mkdir -p "$ARCHIVE_DIR"

archive_if_needed() {
  local path="$1"
  if [[ -e "$path" ]]; then
    mv "$path" "$ARCHIVE_DIR/$(basename "$path")"
  fi
}

sync_desktop_entries() {
  rm -f "$VISIBLE_COMMAND"

  local launcher_path
  launcher_path="$(printf '%q' "$BASE_DIR/launch-server-workbench.sh")"
  rm -rf "$VISIBLE_APP"
  osacompile -o "$VISIBLE_APP" -e "do shell script \"$launcher_path\"" >/dev/null
}

for item in "${LEGACY_ITEMS[@]}"; do
  archive_if_needed "$item"
done

sync_desktop_entries
exec "$CANONICAL_COMMAND"
