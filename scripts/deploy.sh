#!/bin/bash
# WriteGame 快速部署脚本 (Linux/macOS)
set -e

echo "========================================="
echo "  WriteGame 一键部署"
echo "========================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 python3，请先安装 Python 3.11+"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "[错误] 未找到 node，请先安装 Node.js 18+"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo ""
echo "[1/5] 创建 Python 虚拟环境..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "[2/5] 安装后端依赖..."
pip install -r backend/requirements.txt -q

echo "[3/5] 安装前端依赖..."
cd frontend
npm install --silent
echo "[4/5] 构建前端..."
npm run build
cd "$PROJECT_DIR"

echo "[5/5] 初始化环境配置..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  -> 已创建 .env 文件，请编辑填写 API Key"
else
    echo "  -> .env 已存在，跳过"
fi

echo ""
echo "========================================="
echo "  部署完成！"
echo "  运行 ./scripts/start.sh 启动服务"
echo "========================================="
