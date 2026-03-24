Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location -Path (Join-Path $PSScriptRoot "desktop")

if (-not (Test-Path ".\node_modules")) {
    npm install
}

npm run dev

