[CmdletBinding()]
param(
    [ValidateSet("development", "production")]
    [string]$Mode = "development"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $Root "start-ai-lab.ps1"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "AI Lab.lnk"
$PowerShell = (Get-Command powershell.exe).Source

if (-not (Test-Path $Launcher)) {
    throw "start-ai-lab.ps1 is missing from $Root"
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PowerShell
$Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Launcher`" -Mode $Mode"
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = "Start the local AI Lab coding assistant"
$Shortcut.Save()

Write-Host "Created desktop shortcut: $ShortcutPath" -ForegroundColor Green
