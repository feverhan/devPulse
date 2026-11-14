<#
.SYNOPSIS
    构建免容器的单文件可执行程序（Windows）。

.DESCRIPTION
    先构建前端静态资源，再用 PyInstaller 把后端与依赖打包成 dist/devpulse/devpulse.exe。
    目标机器无需 Python、无需容器，双击即用。

.EXAMPLE
    pwsh -File .\scripts\standalone\build.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [string]$Python = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location $root

function Step([string]$text) { Write-Host "`n>> $text" -ForegroundColor Cyan }
function Ok([string]$text) { Write-Host "   $text" -ForegroundColor Green }

try {
    Step '检查构建工具'
    if (-not $Python) {
        $venvPy = Join-Path $root '.venv\Scripts\python.exe'
        $Python = if (Test-Path $venvPy) { $venvPy } else { 'python' }
    }
    & $Python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host '   安装 PyInstaller …'
        & $Python -m pip install --quiet pyinstaller
    }
    Ok "Python $Python"

    if (-not $SkipFrontend) {
        Step '构建前端'
        Push-Location (Join-Path $root 'frontend')
        try {
            npm run build
            if ($LASTEXITCODE -ne 0) { throw '前端构建失败' }
        } finally {
            Pop-Location
        }
        Ok '前端构建完成'
    } else {
        Step '跳过前端构建'
    }

    Step '打包可执行程序'
    & $Python -m PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot 'devpulse.spec')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 打包失败' }

    $exe = Join-Path $root 'dist\devpulse.exe'
    if (-not (Test-Path $exe)) {
        $exe = Join-Path $root 'dist\devpulse\devpulse.exe'
    }
    if (-not (Test-Path $exe)) { throw '未找到打包产物' }
    $size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "`n构建完成：$exe（$size MB）" -ForegroundColor Green
    Write-Host '   拷到目标机器双击运行即可；数据目录默认在系统用户目录（%LOCALAPPDATA%\devpulse），加 --portable 则放 exe 同级。' -ForegroundColor Green
}
catch {
    Write-Host "`n构建失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}