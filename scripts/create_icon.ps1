param(
    [string]$Source = (Join-Path $PSScriptRoot '..\assets\icon\tool box-512x512.png'),
    [string]$Output = (Join-Path $PSScriptRoot '..\resources\app.ico')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$outputPath = [IO.Path]::GetFullPath($Output)
$outputDirectory = Split-Path -Parent $outputPath
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

$sizes = @(16, 24, 32, 48, 64, 128, 256)
$pngFrames = @()
$sourceImage = [Drawing.Image]::FromFile($sourcePath)

try {
    foreach ($size in $sizes) {
        $bitmap = New-Object Drawing.Bitmap($size, $size)
        try {
            $bitmap.SetResolution(96, 96)
            $graphics = [Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.Clear([Drawing.Color]::Transparent)
                $graphics.CompositingMode = [Drawing.Drawing2D.CompositingMode]::SourceCopy
                $graphics.CompositingQuality = [Drawing.Drawing2D.CompositingQuality]::HighQuality
                $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::HighQuality
                $graphics.PixelOffsetMode = [Drawing.Drawing2D.PixelOffsetMode]::HighQuality
                $graphics.DrawImage($sourceImage, 0, 0, $size, $size)
            }
            finally {
                $graphics.Dispose()
            }

            $memory = New-Object IO.MemoryStream
            try {
                $bitmap.Save($memory, [Drawing.Imaging.ImageFormat]::Png)
                $pngFrames += ,([pscustomobject]@{
                    Size = $size
                    Data = $memory.ToArray()
                })
            }
            finally {
                $memory.Dispose()
            }
        }
        finally {
            $bitmap.Dispose()
        }
    }
}
finally {
    $sourceImage.Dispose()
}

$fileStream = New-Object IO.FileStream($outputPath, [IO.FileMode]::Create, [IO.FileAccess]::Write)
$writer = New-Object IO.BinaryWriter($fileStream)
try {
    $writer.Write([UInt16]0)
    $writer.Write([UInt16]1)
    $writer.Write([UInt16]$pngFrames.Count)

    $offset = 6 + (16 * $pngFrames.Count)
    foreach ($frame in $pngFrames) {
        $widthByte = if ($frame.Size -eq 256) { 0 } else { $frame.Size }
        $heightByte = $widthByte
        $writer.Write([byte]$widthByte)
        $writer.Write([byte]$heightByte)
        $writer.Write([byte]0)
        $writer.Write([byte]0)
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]32)
        $writer.Write([UInt32]$frame.Data.Length)
        $writer.Write([UInt32]$offset)
        $offset += $frame.Data.Length
    }

    foreach ($frame in $pngFrames) {
        $writer.Write($frame.Data)
    }
}
finally {
    $writer.Dispose()
    $fileStream.Dispose()
}

Write-Output "Icon created: $outputPath"
Write-Output "Sizes: $($sizes -join ', ')"
