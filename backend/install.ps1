param([string]$ProjectRoot = (Get-Location).Path)

$ErrorActionPreference = "Stop"
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)

if (-not (Test-Path (Join-Path $ProjectRoot "backend")) -or
    -not (Test-Path (Join-Path $ProjectRoot "frontend"))) {
    throw "ProjectRoot must be your ai-lab directory."
}

Get-ChildItem $PackageRoot -Recurse -File |
    Where-Object { $_.Name -notin @("install.ps1", "HANDOFF.md") } |
    ForEach-Object {
        $Relative = [System.IO.Path]::GetRelativePath($PackageRoot, $_.FullName)
        $Destination = Join-Path $ProjectRoot $Relative
        New-Item -ItemType Directory -Force -Path (Split-Path $Destination) | Out-Null
        Copy-Item -Force $_.FullName $Destination
        Write-Host "[copied] $Relative"
    }

Write-Host "RAG override and UI refactor installed. Restart FastAPI and Next.js."
