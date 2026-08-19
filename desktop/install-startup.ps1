# Installs Barq to auto-start at Windows login (hidden until the wake word).
# Creates a shortcut in the current user's Startup folder running Electron with --hidden.

$ErrorActionPreference = "Stop"

$desktopDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "Barq Assistant.lnk"

# Find the electron binary in the desktop/node_modules and fall back to npm if needed
$electronExe = Join-Path $desktopDir "node_modules\electron\dist\electron.exe"
$launcher = if (Test-Path $electronExe) { $electronExe } else { "npm.cmd" }
$arguments = if (Test-Path $electronExe) { ". --hidden" } else { "start -- --hidden" }

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($shortcutPath)
$sc.TargetPath = $launcher
$sc.Arguments = $arguments
$sc.WorkingDirectory = $desktopDir
$sc.Description = "Barq AI Assistant (runs in background, wake-word activated)"
$sc.Save()

Write-Host "Installed Barq auto-start shortcut:"
Write-Host $shortcutPath