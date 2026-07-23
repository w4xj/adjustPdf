$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$targets = @(
    (Join-Path $root 'build'),
    (Join-Path $root 'dist'),
    (Join-Path $root '.pytest_cache')
)

foreach ($target in $targets) {
    $fullTarget = [IO.Path]::GetFullPath($target)
    $fullRoot = [IO.Path]::GetFullPath($root).TrimEnd('\') + '\'

    if (-not $fullTarget.StartsWith($fullRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝清理工作空间之外的路径：$fullTarget"
    }

    if (Test-Path -LiteralPath $fullTarget) {
        Remove-Item -LiteralPath $fullTarget -Recurse -Force
        Write-Host "已删除：$fullTarget"
    }
}
