# WriteGame 快速部署脚本 (Windows PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "========================================="
Write-Host "  WriteGame 一键部署"
Write-Host "========================================="

# 检查 Python
try { python --version | Out-Null } catch {
    Write-Host "[错误] 未找到 python，请先安装 Python 3.11+" -ForegroundColor Red
    exit 1
}

# 检查 Node.js
try { node --version | Out-Null } catch {
    Write-Host "[错误] 未找到 node，请先安装 Node.js 18+" -ForegroundColor Red
    exit 1
}

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectDir

Write-Host ""
Write-Host "[1/5] 创建 Python 虚拟环境..."
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".\.venv\Scripts\Activate.ps1"

Write-Host "[2/5] 安装后端依赖..."
pip install -r backend\requirements.txt -q

Write-Host "[3/5] 安装前端依赖..."
Set-Location frontend
npm install --silent
Write-Host "[4/5] 构建前端..."
npm run build
Set-Location $ProjectDir

Write-Host "[5/5] 初始化环境配置..."
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  -> 已创建 .env 文件，请编辑填写 API Key"
} else {
    Write-Host "  -> .env 已存在，跳过"
}

Write-Host ""
Write-Host "========================================="
Write-Host "  部署完成！"
Write-Host "  运行 .\scripts\start.ps1 启动服务"
Write-Host "========================================="
