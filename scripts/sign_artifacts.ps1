param(
    [Parameter(Mandatory = $true)]
    [string]$ReleaseDir,
    [Parameter(Mandatory = $true)]
    [string]$BackendExe
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$certPath = $env:CRIC_SIGN_CERT_PFX
$certPassword = $env:CRIC_SIGN_CERT_PASSWORD
$timestampUrl = if ($env:CRIC_SIGN_TIMESTAMP_URL) { $env:CRIC_SIGN_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }

if ([string]::IsNullOrWhiteSpace($certPath) -or [string]::IsNullOrWhiteSpace($certPassword)) {
    Write-Warning "Code signing skipped. Set CRIC_SIGN_CERT_PFX and CRIC_SIGN_CERT_PASSWORD to enable signed builds."
    return
}

if (-not (Test-Path $certPath)) {
    throw "Configured certificate file not found: $certPath"
}

$resolvedReleaseDir = (Resolve-Path $ReleaseDir).Path
$targets = @()
$targets += @(Get-ChildItem -Path $resolvedReleaseDir -Recurse -Filter "*.exe" | Select-Object -ExpandProperty FullName)
if (Test-Path $BackendExe) {
    $targets += (Resolve-Path $BackendExe).Path
}
$targets = @($targets | Select-Object -Unique)

if ($targets.Length -eq 0) {
    Write-Warning "No signable executables found."
    return
}

$signtool = Get-Command "signtool.exe" -ErrorAction SilentlyContinue
if (-not $signtool) {
    $candidatePaths = @(
        "$env:ProgramFiles(x86)\Windows Kits\10\bin\x64\signtool.exe",
        "$env:ProgramFiles\Windows Kits\10\bin\x64\signtool.exe"
    )
    foreach ($candidate in $candidatePaths) {
        if (Test-Path $candidate) {
            $signtool = @{ Source = $candidate }
            break
        }
    }
}

if (-not $signtool) {
    throw "signtool.exe not found. Install Windows SDK Signing Tools or add signtool.exe to PATH."
}

foreach ($file in $targets) {
    Write-Host "Signing: $file"
    & $signtool.Source sign /fd SHA256 /f "$certPath" /p "$certPassword" /tr "$timestampUrl" /td SHA256 "$file"
    if ($LASTEXITCODE -ne 0) {
        throw "Signing failed for $file (exit code $LASTEXITCODE)."
    }
}

Write-Host "Code signing completed for $($targets.Length) executable(s)."
