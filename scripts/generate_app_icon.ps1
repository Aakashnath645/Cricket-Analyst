Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

$root = Split-Path -Parent $PSScriptRoot
$assetsDir = Join-Path $root "assets"
$desktopBuildDir = Join-Path $root "desktop\build"

New-Item -ItemType Directory -Path $assetsDir -Force | Out-Null
New-Item -ItemType Directory -Path $desktopBuildDir -Force | Out-Null

function New-CricAnalystIcon {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PngPath,
        [Parameter(Mandatory = $true)]
        [string]$IcoPath
    )

    $size = 256
    $bmp = New-Object System.Drawing.Bitmap($size, $size)
    $g = [System.Drawing.Graphics]::FromImage($bmp)

    try {
        $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

        $backgroundRect = New-Object System.Drawing.Rectangle(0, 0, $size, $size)
        $backgroundBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
            $backgroundRect,
            [System.Drawing.Color]::FromArgb(255, 9, 33, 69),
            [System.Drawing.Color]::FromArgb(255, 12, 103, 93),
            45.0
        )

        $g.FillRectangle($backgroundBrush, $backgroundRect)
        $backgroundBrush.Dispose()

        $ballRect = New-Object System.Drawing.Rectangle(34, 34, 188, 188)
        $ballBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
            $ballRect,
            [System.Drawing.Color]::FromArgb(255, 206, 25, 38),
            [System.Drawing.Color]::FromArgb(255, 140, 10, 20),
            120.0
        )
        $g.FillEllipse($ballBrush, $ballRect)
        $ballBrush.Dispose()

        $shadowPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(90, 0, 0, 0), 10)
        $g.DrawEllipse($shadowPen, $ballRect)
        $shadowPen.Dispose()

        $seamPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(245, 250, 250, 250), 10)
        $g.DrawArc($seamPen, 62, 46, 132, 170, 210, 120)
        $g.DrawArc($seamPen, 62, 46, 132, 170, 30, 120)

        for ($i = 0; $i -lt 5; $i++) {
            $offset = 70 + ($i * 24)
            $g.DrawLine($seamPen, 102, $offset, 156, $offset - 8)
        }
        $seamPen.Dispose()

        $glowBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(80, 255, 255, 255))
        $g.FillEllipse($glowBrush, 74, 62, 46, 32)
        $glowBrush.Dispose()

        $bmp.Save($PngPath, [System.Drawing.Imaging.ImageFormat]::Png)

        $icon = [System.Drawing.Icon]::FromHandle($bmp.GetHicon())
        $iconStream = [System.IO.File]::Open($IcoPath, [System.IO.FileMode]::Create)
        try {
            $icon.Save($iconStream)
        }
        finally {
            $iconStream.Close()
            $icon.Dispose()
        }
    }
    finally {
        $g.Dispose()
        $bmp.Dispose()
    }
}

$assetsPng = Join-Path $assetsDir "icon.png"
$assetsIco = Join-Path $assetsDir "icon.ico"
$desktopPng = Join-Path $desktopBuildDir "icon.png"
$desktopIco = Join-Path $desktopBuildDir "icon.ico"

New-CricAnalystIcon -PngPath $assetsPng -IcoPath $assetsIco
Copy-Item -Path $assetsPng -Destination $desktopPng -Force
Copy-Item -Path $assetsIco -Destination $desktopIco -Force

Write-Host "Generated app icons:"
Write-Host " - $assetsPng"
Write-Host " - $assetsIco"
Write-Host " - $desktopPng"
Write-Host " - $desktopIco"
