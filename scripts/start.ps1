# WriteGame 快速启动脚本 (Windows PowerShell)
$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectDir

if (-not (Test-Path ".venv")) {
    Write-Host "[错误] 未找到虚拟环境，请先运行 .\scripts\deploy.ps1" -ForegroundColor Red
    exit 1
}

& ".\.venv\Scripts\Activate.ps1"

Write-Host "========================================="
Write-Host "  WriteGame 启动中..."
Write-Host "  访问地址: http://localhost:8000"
Write-Host "  管理员: falling-feather"
Write-Host "  按 Ctrl+C 停止服务"
Write-Host "========================================="

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
