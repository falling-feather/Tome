# Inkless 一键部署并运行（阿里云 Windows10 / 905 端口）
$ErrorActionPreference = "Stop"

function Ensure-LineValue {
    param(
        [string]$FilePath,
        [string]$Key,
        [string]$Value
    )

    if (-not (Test-Path $FilePath)) { return }
    $content = Get-Content $FilePath -Raw
    if ($content -match "(?m)^$Key=") {
        $content = [regex]::Replace($content, "(?m)^$Key=.*$", "$Key=$Value")
    } else {
        if (-not $content.EndsWith("`r`n")) { $content += "`r`n" }
        $content += "$Key=$Value`r`n"
    }
    Set-Content -Path $FilePath -Value $content -Encoding UTF8
}

$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectDir

Write-Host "========================================="
Write-Host "  Inkless 阿里云一键部署 + 启动"
Write-Host "  目标端口: 905"
Write-Host "========================================="

try { python --version | Out-Null } catch {
    Write-Host "[错误] 未检测到 Python 3.11+，请先安装。" -ForegroundColor Red
    exit 1
}
try { node --version | Out-Null } catch {
    Write-Host "[错误] 未检测到 Node.js 20+，请先安装。" -ForegroundColor Red
    exit 1
}

Write-Host "[1/6] 创建或检查虚拟环境..."
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".\.venv\Scripts\Activate.ps1"

Write-Host "[2/6] 安装后端依赖..."
pip install -r backend\requirements.txt

Write-Host "[3/6] 安装前端依赖并构建..."
Push-Location frontend
npm ci --no-audit --no-fund
npm run build
Pop-Location

Write-Host "[4/6] 初始化生产配置..."
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}
Ensure-LineValue -FilePath ".env" -Key "HOST" -Value "0.0.0.0"
Ensure-LineValue -FilePath ".env" -Key "PORT" -Value "905"
Ensure-LineValue -FilePath ".env" -Key "DEBUG" -Value "false"

Write-Host "[5/6] 提醒检查 API Key 与 SECRET_KEY..." -ForegroundColor Yellow
Write-Host "  如首次部署，请打开 .env 填写 SECRET_KEY 与 LLM API Key。" -ForegroundColor Yellow
Write-Host "  配置文件位置: $ProjectDir\.env" -ForegroundColor Yellow

Write-Host "[6/6] 启动服务..."
Write-Host "========================================="
Write-Host "  本机地址: http://127.0.0.1:905"
Write-Host "  外网地址: http://你的域名:905"
Write-Host "  健康检查: /api/health"
Write-Host "========================================="

python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 905
