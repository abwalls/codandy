$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $ProjectRoot "backend"

$BackendPython = Join-Path $BackendRoot ".venv-managed\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $BackendPython)) {
    $BackendPython = Join-Path $BackendRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $BackendPython)) {
    throw "The backend environment is missing. Run .\scripts\setup-windows.ps1 first."
}

$BackendCommand = "Set-Location '$BackendRoot'; & '$BackendPython' -m uvicorn app.main:app --reload --port 8000"
$FrontendCommand = "Set-Location '$ProjectRoot'; corepack pnpm dev"

Write-Host "Starting Code Atlas backend at http://localhost:8000" -ForegroundColor Cyan
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-NoExit", "-Command", $BackendCommand

Write-Host "Starting Code Atlas frontend at http://localhost:5173" -ForegroundColor Cyan
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-NoExit", "-Command", $FrontendCommand

Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
