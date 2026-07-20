param(
    [string]$ProjectRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)

if (-not (Test-Path (Join-Path $ProjectRoot "backend")) -or
    -not (Test-Path (Join-Path $ProjectRoot "frontend"))) {
    throw "ProjectRoot must be the ai-lab root containing backend and frontend folders."
}

$Files = Get-ChildItem $PackageRoot -Recurse -File |
    Where-Object { $_.Name -notin @("install.ps1", "HANDOFF.md") }

foreach ($File in $Files) {
    $Relative = [System.IO.Path]::GetRelativePath($PackageRoot, $File.FullName)
    $Destination = Join-Path $ProjectRoot $Relative
    $DestinationDirectory = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $DestinationDirectory | Out-Null
    Copy-Item -Force $File.FullName $Destination
    Write-Host "[copied] $Relative"
}

Write-Host ""
Write-Host "Runtime control and knowledge source files installed."
Write-Host "Run backend tests, frontend lint, TypeScript, and then restart both services."
