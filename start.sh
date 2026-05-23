#!/bin/bash
set -euo pipefail

BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$BASE_DIR"

echo "========================================"
echo "   XHS_ALL_IN_ONE 一键启动脚本"
echo "========================================"

PYTHON_BIN="$BASE_DIR/.venv/bin/python"
PIP_BIN="$BASE_DIR/.venv/bin/pip"
LOG_DIR="$BASE_DIR/logs"
mkdir -p "$LOG_DIR"

if [ ! -x "$PYTHON_BIN" ]; then
    if command -v python3.10 &> /dev/null; then
        BOOTSTRAP_PYTHON="$(command -v python3.10)"
    elif command -v python3.11 &> /dev/null; then
        BOOTSTRAP_PYTHON="$(command -v python3.11)"
    elif command -v python3 &> /dev/null; then
        BOOTSTRAP_PYTHON="$(command -v python3)"
    else
        echo "[错误] 未找到 Python，请安装 Python 3.10+"
        exit 1
    fi
    echo "[准备] 创建项目虚拟环境: $BOOTSTRAP_PYTHON"
    "$BOOTSTRAP_PYTHON" -m venv "$BASE_DIR/.venv"
fi

if ! command -v npm &> /dev/null; then
    echo "[错误] 未找到 npm，请确保已安装 Node.js 20+"
    exit 1
fi

echo "[1/4] 检查 Python 依赖..."
"$PIP_BIN" install --upgrade pip -q
"$PIP_BIN" install -r requirements.txt -q
"$PIP_BIN" install playwright fastapi uvicorn httpx -q
if [ ! -d "$HOME/Library/Caches/ms-playwright/chromium-1223" ]; then
    "$PYTHON_BIN" -m playwright install chromium
fi

echo "[2/4] 检查前端依赖..."
if [ ! -d "frontend/node_modules" ]; then
    cd frontend && npm install && cd "$BASE_DIR"
fi

stop_port() {
    local port="$1"
    local pids
    pids="$(lsof -ti:"$port" 2>/dev/null || true)"
    if [ -n "$pids" ]; then
        echo "清理端口 $port: $pids"
        kill $pids 2>/dev/null || true
        sleep 1
    fi
}

echo "[3/4] 清理旧端口..."
stop_port 8000
stop_port 5173

echo "========================================"
echo "[4/4] 正在以前台模式启动，保持此窗口打开"
echo "- 前端界面: http://127.0.0.1:5173"
echo "- API 文档: http://127.0.0.1:8000/docs"
echo "- 状态接口: http://127.0.0.1:8000/api/system/status"
echo "========================================"

exec "$PYTHON_BIN" main.py --with-frontend
