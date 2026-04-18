#!/bin/bash
# WriteGame 快速启动脚本 (Linux/macOS)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
    echo "[错误] 未找到虚拟环境，请先运行 ./scripts/deploy.sh"
    exit 1
fi

source .venv/bin/activate

echo "========================================="
echo "  WriteGame 启动中..."
echo "  访问地址: http://localhost:8000"
echo "  管理员: falling-feather"
echo "  按 Ctrl+C 停止服务"
echo "========================================="

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
