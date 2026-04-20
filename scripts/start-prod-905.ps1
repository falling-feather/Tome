# Inkless 生产启动脚本（Windows / 阿里云 / 905 端口）
$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectDir

if (-not (Test-Path ".venv")) {
    Write-Host "[错误] 未找到虚拟环境，请先运行 .\scripts\deploy.ps1" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".env")) {
    Write-Host "[错误] 未找到 .env，请先复制 .env.example 并填写生产配置" -ForegroundColor Red
    exit 1
}

& ".\.venv\Scripts\Activate.ps1"

Write-Host "========================================="
Write-Host "  Inkless 生产服务启动中..."
Write-Host "  监听地址: 0.0.0.0:905"
Write-Host "  外网访问: http://你的域名:905"
Write-Host "  按 Ctrl+C 停止服务"
Write-Host "========================================="

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 905
