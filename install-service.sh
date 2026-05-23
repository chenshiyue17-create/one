#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/Users/cc/XHS_ALL_IN_ONE"
PLIST_PATH="$HOME/Library/LaunchAgents/com.xhs.localhelper.plist"
PYTHON_BIN="$BASE_DIR/.venv/bin/python"

echo "正在创建系统服务配置..."

cat <<EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.xhs.localhelper</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>backend.app.local_helper:app</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>8765</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>$BASE_DIR</string>
    <key>StandardOutPath</key>
    <string>$BASE_DIR/logs/local_helper_service.log</string>
    <key>StandardErrorPath</key>
    <string>$BASE_DIR/logs/local_helper_service.err</string>
</dict>
</plist>
EOF

echo "正在启动服务..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "========================================"
echo "服务已集成到系统后台！"
echo "- 以后开机自动运行，无需手动启动。"
echo "- 无论使用本地 App 还是远程服务器 (47.87.68.74)，均可直接同步 Cookie。"
echo "- 日志查看: $BASE_DIR/logs/local_helper_service.log"
echo "========================================"
