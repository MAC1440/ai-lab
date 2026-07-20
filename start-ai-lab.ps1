[CmdletBinding()]
param(
    [ValidateSet("development", "production")]
    [string]$Mode = "development",
    [switch]$NoBrowser,
    [switch]$Check
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "Backend environment is missing. Run .\setup-ai-lab.ps1 first."
}

$Arguments = @(
    (Join-Path $Root "launcher\ai_lab_launcher.py"),
    "--root", $Root,
    "--mode", $Mode
)
if ($NoBrowser) { $Arguments += "--no-browser" }
if ($Check) { $Arguments += "--check" }

& $Python @Arguments
exit $LASTEXITCODE
