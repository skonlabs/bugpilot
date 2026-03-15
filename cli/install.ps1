# BugPilot CLI installer for Windows (PowerShell)
# Usage: iex (New-Object Net.WebClient).DownloadString('https://get.bugpilot.com/install.ps1')
#        or: .\install.ps1 [-Version v1.0.0] [-InstallDir C:\Users\you\bin]

param(
    [string]$Version = "",
    [string]$InstallDir = "$env:LOCALAPPDATA\bugpilot\bin"
)

$ErrorActionPreference = "Stop"
$Repo = "skonlabs/bugpilot"
$BinaryName = "bugpilot.exe"

function Write-Info   { Write-Host "[bugpilot] $args" -ForegroundColor Green }
function Write-Warn   { Write-Host "[bugpilot] $args" -ForegroundColor Yellow }
function Write-Err    { Write-Host "[bugpilot] ERROR: $args" -ForegroundColor Red; exit 1 }

# Fetch latest version if not specified
if (-not $Version) {
    Write-Info "Fetching latest version..."
    try {
        $Release = Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest"
        $Version = $Release.tag_name
    } catch {
        Write-Err "Could not fetch latest version: $_"
    }
}

if (-not $Version) {
    Write-Err "Could not determine latest version"
}

Write-Info "Installing bugpilot $Version for windows/amd64..."

# Download URL
$AssetName = "bugpilot-windows-amd64.exe"
$DownloadUrl = "https://github.com/$Repo/releases/download/$Version/$AssetName"

# Create install directory
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$TmpFile = Join-Path $env:TEMP "bugpilot-download.exe"
$InstallPath = Join-Path $InstallDir $BinaryName

Write-Info "Downloading $DownloadUrl..."
try {
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $TmpFile -UseBasicParsing
} catch {
    Write-Err "Download failed: $_"
}

# Verify
try {
    $out = & $TmpFile version 2>&1
} catch {
    Write-Warn "Version check failed — binary may not work correctly"
}

Move-Item -Path $TmpFile -Destination $InstallPath -Force
Write-Info "Installed to $InstallPath"

# Add to PATH if not already present
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable(
        "Path",
        "$UserPath;$InstallDir",
        "User"
    )
    Write-Info "Added $InstallDir to user PATH (restart your terminal)"
}

Write-Info "✓ bugpilot $Version installed successfully"
Write-Host ""
Write-Host "  Get started:"
Write-Host "    bugpilot init"
Write-Host "    bugpilot investigate TICKET-123"
