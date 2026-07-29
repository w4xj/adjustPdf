param(
    [ValidateSet('OneFile', 'OneDir')]
    [string]$Mode = 'OneFile',

    [switch]$SkipInstall,
    [switch]$SkipTests,
    [switch]$SkipSmokeTest
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$existingVenvPython = Join-Path $root '.venv\Scripts\python.exe'
$buildVenv = Join-Path $root '.venv-build'
$buildVenvPython = Join-Path $buildVenv 'Scripts\python.exe'

Push-Location $root
try {
    $env:PYTHONUTF8 = '1'
    $env:PYTHONPATH = Join-Path $root 'src'

    if (Test-Path -LiteralPath $existingVenvPython) {
        $python = $existingVenvPython
        Write-Host "使用现有虚拟环境：$python" -ForegroundColor Cyan
    }
    else {
        if (-not (Test-Path -LiteralPath $buildVenvPython)) {
            Write-Host '正在创建构建虚拟环境……' -ForegroundColor Cyan
            py -3.11 -m venv $buildVenv
            if ($LASTEXITCODE -ne 0) {
                throw '创建构建虚拟环境失败。请确认已经安装 Python 3.11 或更高版本。'
            }
        }
        $python = $buildVenvPython
    }

    if (-not $SkipInstall) {
        Write-Host '正在安装或更新构建依赖……' -ForegroundColor Cyan
        & $python -m pip install -r (Join-Path $root 'requirements-dev.txt')
        if ($LASTEXITCODE -ne 0) {
            throw '依赖安装失败。'
        }
    }

    if (-not $SkipTests) {
        Write-Host '正在运行自动化测试……' -ForegroundColor Cyan
        & $python -m pytest
        if ($LASTEXITCODE -ne 0) {
            throw '测试未通过，已停止构建。'
        }
    }

    $iconPath = Join-Path $root 'resources\app.ico'
    if (-not (Test-Path -LiteralPath $iconPath)) {
        Write-Host '正在从 PNG 生成 Windows ICO 图标……' -ForegroundColor Cyan
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\create_icon.ps1')
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $iconPath)) {
            throw '生成应用图标失败。'
        }
    }

    $skinPath = Join-Path $root 'resources\skins\lty.png'
    if (-not (Test-Path -LiteralPath $skinPath)) {
        Write-Host '正在生成 LTY 背景皮肤资源……' -ForegroundColor Cyan
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\create_skin_assets.ps1')
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $skinPath)) {
            throw '生成 LTY 背景皮肤失败。'
        }
    }

    $arguments = @(
        '--noconfirm',
        '--clean',
        '--windowed',
        '--name', 'PDF-如一',
        '--paths', (Join-Path $root 'src'),
        '--icon', $iconPath,
        '--add-data', "$iconPath;resources",
        '--add-data', "$skinPath;resources/skins",
        '--version-file', (Join-Path $root 'resources\version_info.txt')
    )

    if ($Mode -eq 'OneFile') {
        $arguments += '--onefile'
    }
    else {
        $arguments += '--onedir'
    }

    $arguments += (Join-Path $root 'main.py')

    Write-Host "正在构建 $Mode 版本……" -ForegroundColor Cyan
    & $python -m PyInstaller @arguments
    if ($LASTEXITCODE -ne 0) {
        throw 'PyInstaller 构建失败。'
    }

    # 构建完成后重命名产物，追加版本号
    $versionFile = Join-Path $root 'src\adjust_pdf\__init__.py'
    $versionLine = Select-String -Path $versionFile -Pattern '__version__\s*=\s*"(.*)"'
    $version = if ($versionLine) { $versionLine.Matches.Groups[1].Value } else { '0.0.0' }

    if ($Mode -eq 'OneFile') {
        $artifact = Join-Path $root "dist\PDF-如一.exe"
    }
    else {
        $artifact = Join-Path $root "dist\PDF-如一\PDF-如一.exe"
    }

    $finalArtifact = Join-Path $root "dist\PDF-如一_v${version}.exe"
    if (Test-Path -LiteralPath $artifact) {
        Move-Item -LiteralPath $artifact -Destination $finalArtifact -Force
        $artifact = $finalArtifact
    }

    if (-not (Test-Path -LiteralPath $artifact)) {
        throw "找不到构建产物：$artifact"
    }

    if (-not $SkipSmokeTest) {
        Write-Host '正在运行 EXE 冒烟测试……' -ForegroundColor Cyan
        & $python (Join-Path $root 'scripts\smoke_test_exe.py') $artifact
        if ($LASTEXITCODE -ne 0) {
            throw 'EXE 冒烟测试失败。'
        }

        $realFixture = Join-Path $root 'testFile\20260722.pdf'
        if (Test-Path -LiteralPath $realFixture) {
            Write-Host '正在运行真实 PDF 回归测试……' -ForegroundColor Cyan
            & $python (Join-Path $root 'scripts\verify_real_fixture.py') $artifact $realFixture
            if ($LASTEXITCODE -ne 0) {
                throw '真实 PDF 回归测试失败。'
            }

            Write-Host '正在运行按页码 EXE 回归测试……' -ForegroundColor Cyan
            & $python (Join-Path $root 'scripts\verify_page_selection_exe.py') $artifact $realFixture
            if ($LASTEXITCODE -ne 0) {
                throw '按页码 EXE 回归测试失败。'
            }

            Write-Host '正在运行签名安全策略 EXE 回归测试……' -ForegroundColor Cyan
            & $python (Join-Path $root 'scripts\verify_signature_guard_exe.py') $artifact $realFixture
            if ($LASTEXITCODE -ne 0) {
                throw '签名安全策略 EXE 回归测试失败。'
            }
        }
        else {
            Write-Host "未找到真实 PDF 样本，跳过：$realFixture" -ForegroundColor Yellow
        }
    }

    $file = Get-Item -LiteralPath $artifact
    $sizeMb = [Math]::Round($file.Length / 1MB, 2)
    Write-Host ''
    Write-Host '构建成功！' -ForegroundColor Green
    Write-Host "文件：$artifact"
    Write-Host "大小：$sizeMb MB"
}
finally {
    Pop-Location
}
