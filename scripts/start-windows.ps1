param(
    [switch]$SkipInstall,
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

foreach ($Command in @("uv", "node", "npm", "codex")) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "缺少 $Command，请先安装并确保它位于 PATH 中。"
    }
}

if (-not $SkipInstall) {
    uv sync --extra dev
    Push-Location frontend
    npm ci
    npm run build
    Pop-Location
}

$env:IMAGE_GEN_SERVICE_ROOT = $ProjectRoot
$env:IMAGE_GEN_DATA_DIR = Join-Path $ProjectRoot "data"
$env:IMAGE_GEN_DEFAULT_WORKDIR = $ProjectRoot
$env:IMAGE_GEN_FRONTEND_DIST_DIR = Join-Path $ProjectRoot "frontend\dist"
if (-not $env:IMAGE_GEN_CODEX_HOME) {
    $env:IMAGE_GEN_CODEX_HOME = Join-Path $HOME ".codex"
}
if (-not $env:IMAGE_GEN_CODEX_USER_HOME) {
    $env:IMAGE_GEN_CODEX_USER_HOME = $HOME
}

if ($Dev) {
    $Backend = Start-Process uv -ArgumentList @("run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8088", "--reload") -PassThru
    try {
        Push-Location frontend
        npm run dev -- --host 127.0.0.1
    }
    finally {
        Pop-Location
        Stop-Process -Id $Backend.Id -Force -ErrorAction SilentlyContinue
    }
}
else {
    uv run image-gen-service
}
