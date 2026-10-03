<#
.SYNOPSIS
    Installs Barq AI Assistant as a Windows Service for zero-memory background operation.

.DESCRIPTION
    Creates a Windows Service that runs the Barq Python backend in headless mode.
    The service starts at boot, runs silently (<50MB RAM), and spawns the UI
    only when the wake word is detected.

.NOTES
    Requires Administrator privileges.
    Run from the project root: D:\Barq Assistant\barq-ai-assistant
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$ServiceName = "BarqAssistant",

    [Parameter(Mandatory=$false)]
    [string]$DisplayName = "Barq AI Assistant",

    [Parameter(Mandatory=$false)]
    [string]$Description = "Personal AI assistant - zero-memory background service with wake-word activation",

    [Parameter(Mandatory=$false)]
    [string]$ProjectPath = "D:\Barq Assistant\barq-ai-assistant"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message"
}

function Check-Admin {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-PythonPath {
    param([string]$ProjectPath)
    $venvPython = Join-Path $ProjectPath "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    throw "Python not found at $venvPython. Run setup first."
}

function Get-ServiceScript {
    param([string]$ProjectPath)
    $script = Join-Path $ProjectPath "barq_service.py"
    if (Test-Path $script) {
        return $script
    }
    throw "Service script not found at $script"
}

# --- Main ---

Write-Log "=== Barq Windows Service Installer ==="

if (-not (Check-Admin)) {
    Write-Log "ERROR: This script requires Administrator privileges." "ERROR"
    Write-Log "Right-click PowerShell and select 'Run as Administrator'." "ERROR"
    exit 1
}

$pythonExe = Get-PythonPath $ProjectPath
$serviceScript = Get-ServiceScript $ProjectPath

Write-Log "Python: $pythonExe"
Write-Log "Script: $serviceScript"

# Check if service already exists
$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Log "Service '$ServiceName' already exists. Removing..." "WARN"
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
}

# Create the service using NSSM (Non-Sucking Service Manager) approach
# We'll use the built-in sc.exe with a wrapper
$nssmPath = Join-Path $ProjectPath "tools\nssm.exe"
if (-not (Test-Path $nssmPath)) {
    Write-Log "Downloading NSSM..." "INFO"
    $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
    $zipPath = Join-Path $env:TEMP "nssm.zip"
    Invoke-WebRequest -Uri $nssmUrl -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath (Join-Path $ProjectPath "tools") -Force
    $nssmPath = Join-Path $ProjectPath "tools\nssm-2.24\win64\nssm.exe"
    if (-not (Test-Path $nssmPath)) {
        throw "NSSM not found after download"
    }
}

Write-Log "Installing service with NSSM..."
& $nssmPath install $ServiceName $pythonExe $serviceScript
if ($LASTEXITCODE -ne 0) {
    throw "NSSM install failed with exit code $LASTEXITCODE"
}

& $nssmPath set $ServiceName DisplayName $DisplayName
& $nssmPath set $ServiceName Description $Description
& $nssmPath set $ServiceName Start SERVICE_AUTO_START
& $nssmPath set $ServiceName AppDirectory $ProjectPath
& $nssmPath set $ServiceName AppStdout (Join-Path $ProjectPath "barq_data\service.log")
& $nssmPath set $ServiceName AppStderr (Join-Path $ProjectPath "barq_data\service_error.log")
& $nssmPath set $ServiceName AppRotateFiles 1
& $nssmPath set $ServiceName AppRotateBytes 10485760

# Set recovery actions: restart on failure
& $nssmPath set $ServiceName AppExit Default Restart
& $nssmPath set $ServiceName AppThrottle 5000

Write-Log "Service installed successfully!"

# Start the service
Write-Log "Starting service..."
Start-Service -Name $ServiceName -ErrorAction Stop
Start-Sleep -Seconds 3

$status = (Get-Service -Name $ServiceName).Status
Write-Log "Service status: $status"

if ($status -eq 'Running') {
    Write-Log "SUCCESS: Barq service is running!"
    Write-Log ""
    Write-Log "Next steps:"
    Write-Log "  - Say 'Barq' or 'Hey Barq' to wake the assistant"
    Write-Log "  - UI will appear automatically on wake"
    Write-Log "  - Say 'go to sleep' to dismiss UI"
    Write-Log ""
    Write-Log "To manage the service:"
    Write-Log "  Start:   Start-Service -Name $ServiceName"
    Write-Log "  Stop:    Stop-Service -Name $ServiceName"
    Write-Log "  Status:  Get-Service -Name $ServiceName"
    Write-Log "  Logs:    Get-Content 'D:\Barq Assistant\barq-ai-assistant\barq_data\service.log' -Wait"
} else {
    Write-Log "WARNING: Service installed but not running. Check logs:" "WARN"
    Write-Log "  $ProjectPath\barq_data\service_error.log" "WARN"
}

Write-Log "=== Installation Complete ==="