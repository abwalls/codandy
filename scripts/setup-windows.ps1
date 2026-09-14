$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Require-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$InstallHint
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required. $InstallHint"
    }
}

Require-Command -Name "node" -InstallHint "Install the current Node.js LTS release, reopen PowerShell, and run this script again."
Require-Command -Name "corepack" -InstallHint "Install or update Node.js, reopen PowerShell, and run this script again."
Require-Command -Name "python" -InstallHint "Install Python 3.12 or newer, enable Add Python to PATH, reopen PowerShell, and run this script again."
Require-Command -Name "uv" -InstallHint "Run: winget install --id=astral-sh.uv -e"

$PythonVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$PythonSupported = python -c "import sys; print('yes' if sys.version_info >= (3, 12) else 'no')"
if ($PythonSupported -ne "yes") {
    throw "Python 3.12 or newer is required. Detected Python $PythonVersion."
}

Write-Host "Preparing pnpm..." -ForegroundColor Cyan
corepack enable
corepack pnpm install

Write-Host "Preparing the Python backend..." -ForegroundColor Cyan
Push-Location (Join-Path $ProjectRoot "backend")
try {
    uv sync --extra dev
    uv run pytest -q
    uv run ruff check .
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Codandy is ready." -ForegroundColor Green
Write-Host "Run .\scripts\start-windows.ps1 to start the frontend and backend."
