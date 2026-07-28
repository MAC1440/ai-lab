[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command "git" -ErrorAction SilentlyContinue)) {
    throw "Git is required to create a source release."
}

Push-Location $Root
try {
    $Dirty = & git status --porcelain
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect the Git working tree."
    }
    if ($Dirty) {
        throw "Commit or stash local changes before creating a release."
    }

    $Commit = (& git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $Commit) {
        throw "Could not resolve the current Git commit."
    }
    $ShortCommit = $Commit.Substring(0, 7)

    $ResolvedOutput = if ([System.IO.Path]::IsPathRooted($OutputDirectory)) {
        $OutputDirectory
    } else {
        Join-Path $Root $OutputDirectory
    }
    New-Item -ItemType Directory -Force -Path $ResolvedOutput | Out-Null

    $Archive = Join-Path $ResolvedOutput "ai-lab-source-$ShortCommit.zip"
    & git archive --format=zip --output=$Archive HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "Git source archive creation failed with exit code $LASTEXITCODE."
    }

    $Checksum = (Get-FileHash -Algorithm SHA256 $Archive).Hash.ToLowerInvariant()
    $ChecksumPath = "$Archive.sha256"
    "$Checksum  $(Split-Path -Leaf $Archive)" |
        Set-Content -Encoding ascii $ChecksumPath

    Write-Host "Created source release:" -ForegroundColor Green
    Write-Host "  $Archive"
    Write-Host "  $ChecksumPath"
} finally {
    Pop-Location
}
