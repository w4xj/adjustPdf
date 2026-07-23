param(
    [string]$Source = (Join-Path $PSScriptRoot '..\assets\lty.jpg'),
    [string]$Output = (Join-Path $PSScriptRoot '..\resources\skins\lty.png')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$outputPath = [IO.Path]::GetFullPath($Output)
New-Item -ItemType Directory -Path (Split-Path -Parent $outputPath) -Force | Out-Null

$image = [Drawing.Image]::FromFile($sourcePath)
try {
    $image.Save($outputPath, [Drawing.Imaging.ImageFormat]::Png)
}
finally {
    $image.Dispose()
}

Write-Output "Skin asset created: $outputPath"
