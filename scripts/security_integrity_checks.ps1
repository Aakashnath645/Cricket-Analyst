param(
    [string]$ReleaseDir = "$PSScriptRoot\..\desktop\release"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$releasePath = (Resolve-Path $ReleaseDir).Path
$installer = Get-ChildItem -Path $releasePath -Filter "CricAnalyst-Setup-*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $installer) {
    throw "No installer found in $releasePath. Run build_electron_exe.ps1 first."
}

Write-Host "Using installer: $($installer.FullName)"

$hashFiles = @($installer.FullName)
$backendExe = Join-Path $root "dist\CricAnalystApi.exe"
if (Test-Path $backendExe) {
    $hashFiles += $backendExe
}

$hashOutput = Join-Path $releasePath "SHA256SUMS.txt"
$hashLines = @()
foreach ($file in $hashFiles) {
    $hash = Get-FileHash -Path $file -Algorithm SHA256
    $line = "{0}  {1}" -f $hash.Hash, (Split-Path -Leaf $file)
    $hashLines += $line
}
Set-Content -Path $hashOutput -Value $hashLines -Encoding ascii
Write-Host "Wrote SHA256 checksums to: $hashOutput"

$signature = Get-AuthenticodeSignature -FilePath $installer.FullName
$requireSignature = $env:CRIC_REQUIRE_SIGNATURE -eq "1"
if ($signature.Status -ne "Valid") {
    Write-Warning "Installer is not code signed (status: $($signature.Status)). Integrity checksums were generated, but production distribution should use a trusted code-signing certificate."
    if ($requireSignature) {
        throw "CRIC_REQUIRE_SIGNATURE=1 but installer signature is not valid."
    }
} else {
    Write-Host "Installer code-signature is valid."
}

function Invoke-DefenderFileScan {
    param([Parameter(Mandatory = $true)][string]$FilePath)

    $defenderPath = "$env:ProgramFiles\Windows Defender\MpCmdRun.exe"
    if (-not (Test-Path $defenderPath)) {
        Write-Warning "Microsoft Defender command-line scanner not found at $defenderPath. Skipping malware scan."
        return
    }

    Write-Host "Running Defender scan for: $FilePath"
    & $defenderPath -Scan -ScanType 3 -File $FilePath | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Defender scan returned non-zero exit code $LASTEXITCODE for $FilePath"
    }
}

Invoke-DefenderFileScan -FilePath $installer.FullName
if (Test-Path $backendExe) {
    Invoke-DefenderFileScan -FilePath $backendExe
}

$unpacked = Join-Path $releasePath "win-unpacked"
if (Test-Path $unpacked) {
    $asarPath = Join-Path $unpacked "resources\app.asar"
    if (-not (Test-Path $asarPath)) {
        Write-Warning "app.asar not found in win-unpacked resources."
    } else {
        Write-Host "Found packaged app archive: $asarPath"
    }

    $pyFiles = @(Get-ChildItem -Path (Join-Path $unpacked "resources") -Recurse -Filter "*.py" -ErrorAction SilentlyContinue)
    if ($pyFiles.Length -gt 0) {
        Write-Warning "Found Python source files in packaged resources; review for accidental source leakage."
        $pyFiles | Select-Object -First 10 | ForEach-Object { Write-Host " - $($_.FullName)" }
    } else {
        Write-Host "No Python source files found in packaged resources."
    }
}

Write-Host "Running Python dependency integrity check (pip check)..."
& "$root\.venv\Scripts\python.exe" -m pip check

Write-Host "Running npm production audit..."
Push-Location (Join-Path $root "desktop")
try {
    npm audit --omit=dev
}
finally {
    Pop-Location
}

Write-Host "Security/integrity checks completed."
