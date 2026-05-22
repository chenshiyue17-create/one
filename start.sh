#!/bin/bash

# 获取脚本所在绝对路径
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$BASE_DIR"

echo "========================================"
echo "   XHS_ALL_IN_ONE 一键启动脚本"
echo "========================================"

# 1. 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 python3，请确保已安装 Python 3.10+"
    exit 1
fi

# 2. 检查 Node.js 环境
if ! command -v npm &> /dev/null; then
    echo "[错误] 未找到 npm，请确保已安装 Node.js 20+"
    exit 1
fi

# 3. 检查并安装 Python 依赖
echo "[1/3] 检查 Python 依赖..."
pip3 install -r requirements.txt -q
pip3 install playwright fastapi uvicorn httpx -q
python3 -m playwright install chromium

# 4. 检查并安装前端依赖
if [ ! -d "frontend/node_modules" ]; then
    echo "[2/3] 正在安装前端依赖..."
    cd frontend && npm install && cd ..
fi

# 5. 启动项目
echo "[3/3] 正在启动后端和前端服务..."
echo "启动后请访问:"
echo "- 前端界面: http://localhost:5173"
echo "- API 文档: http://localhost:8000/docs"
echo "========================================"

python3 main.py --with-frontend
