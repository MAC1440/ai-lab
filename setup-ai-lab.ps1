[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$Launcher = Join-Path $Root "launcher\ai_lab_launcher.py"

function Require-Command([string]$Name, [string]$Message) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw $Message
    }
}

function Invoke-Checked(
    [string]$Description,
    [string]$Command,
    [string[]]$Arguments
) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

Require-Command "python" "Python 3.11 or 3.12 is required."
Require-Command "npm" "Node.js 20 or newer is required."

$Version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0) {
    throw "Python version detection failed with exit code $LASTEXITCODE."
}
if ($Version -notin @("3.11", "3.12", "3.13")) {
    Write-Warning "Python $Version may be incompatible. Python 3.11 or 3.12 is recommended."
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating backend virtual environment…" -ForegroundColor Cyan
    Invoke-Checked `
        "Backend virtual environment creation" `
        "python" `
        @("-m", "venv", (Join-Path $Backend ".venv"))
}

Write-Host "Installing backend dependencies…" -ForegroundColor Cyan
Invoke-Checked `
    "pip upgrade" `
    $VenvPython `
    @("-m", "pip", "install", "--upgrade", "pip")
Invoke-Checked `
    "Backend dependency installation" `
    $VenvPython `
    @("-m", "pip", "install", "-r", (Join-Path $Backend "requirements.txt"))

$EnvFile = Join-Path $Backend ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Backend ".env.example") $EnvFile
    Write-Host "Created backend\.env from the safe defaults." -ForegroundColor Green
}

Write-Host "Installing frontend dependencies…" -ForegroundColor Cyan
Push-Location $Frontend
try {
    if (Test-Path "package-lock.json") {
        Invoke-Checked "Frontend dependency installation" "npm" @("ci")
    } else {
        Invoke-Checked "Frontend dependency installation" "npm" @("install")
    }

    if ($Build) {
        Invoke-Checked "Frontend production build" "npm" @("run", "build")
    }
} finally {
    Pop-Location
}

if ($Build) {
    Invoke-Checked `
        "Production build fingerprint" `
        $VenvPython `
        @($Launcher, "--root", $Root, "--write-build-marker")
}

if (-not $SkipModels -and (Get-Command "ollama" -ErrorAction SilentlyContinue)) {
    Write-Host "Ensuring the current local models exist…" -ForegroundColor Cyan
    Invoke-Checked "Granite model installation" "ollama" @("pull", "granite4.1:3b")
    Invoke-Checked "Embedding model installation" "ollama" @("pull", "nomic-embed-text")
} elseif (-not $SkipModels) {
    Write-Warning "Ollama was not found. Install it, then pull granite4.1:3b and nomic-embed-text."
}

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host "Start AI Lab with: .\start-ai-lab.ps1"
if ($Build) {
    Write-Host "Production mode is available with: .\start-ai-lab.ps1 -Mode production"
}
