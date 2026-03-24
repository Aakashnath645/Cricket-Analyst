Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$ErrorMessage
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$ErrorMessage (exit code $LASTEXITCODE)"
    }
}

Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Error "Virtual environment not found. Run: python -m venv .venv"
}

& .\scripts\generate_app_icon.ps1

.\.venv\Scripts\python -m scripts.build_backend_exe
if ($LASTEXITCODE -ne 0) {
    throw "Backend build failed."
}

Write-Host "Running Python tests..."
.\.venv\Scripts\python -m pytest tests -q
if ($LASTEXITCODE -ne 0) {
    throw "Python tests failed."
}

Set-Location -Path (Join-Path $PSScriptRoot "desktop")

Get-Process -Name "CricAnalyst", "CricAnalystApi", "electron" -ErrorAction SilentlyContinue | Stop-Process -Force
$releaseStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$releaseDir = "release\$releaseStamp"
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

if (-not (Test-Path ".\node_modules")) {
    Invoke-Native -Command { npm install } -ErrorMessage "npm install failed."
}

Invoke-Native -Command { npm audit --omit=dev } -ErrorMessage "npm audit failed."
Invoke-Native -Command { npm run build:renderer } -ErrorMessage "Renderer build failed."
Invoke-Native -Command { npx electron-builder --config.directories.output=$releaseDir } -ErrorMessage "Electron build failed."

Set-Location -Path $PSScriptRoot
& .\scripts\sign_artifacts.ps1 -ReleaseDir (Join-Path $PSScriptRoot (Join-Path "desktop" $releaseDir)) -BackendExe (Join-Path $PSScriptRoot "dist\CricAnalystApi.exe")
& .\scripts\security_integrity_checks.ps1 -ReleaseDir (Join-Path $PSScriptRoot (Join-Path "desktop" $releaseDir))
if ($LASTEXITCODE -ne 0) {
    throw "Security/integrity checks failed."
}

Write-Host "Installer output directory: desktop\$releaseDir"

