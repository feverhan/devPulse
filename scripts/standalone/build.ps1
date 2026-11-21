<#
.SYNOPSIS
    构建免容器的可执行程序（Windows）。

.DESCRIPTION
    先构建前端静态资源，再用 PyInstaller 打包图形启动器与命令行程序。
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

    $guiExe = Join-Path $root 'dist\devpulse.exe'
    if (-not (Test-Path $guiExe)) {
        $guiExe = Join-Path $root 'dist\devpulse\devpulse.exe'
    }
    $cliExe = Join-Path $root 'dist\devpulse-cli.exe'
    if (-not (Test-Path $cliExe)) {
        $cliExe = Join-Path $root 'dist\devpulse\devpulse-cli.exe'
    }
    if (-not (Test-Path $guiExe) -or -not (Test-Path $cliExe)) { throw '未找到打包产物' }
    $size = [math]::Round(((Get-Item $guiExe).Length + (Get-Item $cliExe).Length) / 1MB, 1)
    Write-Host "`n构建完成：$guiExe / $cliExe（合计约 $size MB）" -ForegroundColor Green
    Write-Host '   devpulse.exe 是图形启动/停止界面；devpulse-cli.exe 保留命令行模式。' -ForegroundColor Green


    Step '生成免容器发布包'
    $stage = Join-Path $root 'dist\devpulse-standalone'
    if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $stage | Out-Null
    Copy-Item $guiExe (Join-Path $stage (Split-Path -Leaf $guiExe))
    Copy-Item $cliExe (Join-Path $stage (Split-Path -Leaf $cliExe))
    Copy-Item (Join-Path $root '.env.example') $stage
    $guide = @'
研发脉冲 · Dev Pulse（免容器版）

1. 解压后双击 devpulse.exe 打开启动/停止界面
2. 在界面里点「启动」；服务运行后可点「打开页面」，停止用「停止」或直接关闭窗口
3. 需要命令行/服务器模式时执行 devpulse-cli.exe，例如：
   devpulse-cli.exe --port 8080 --no-browser
   端口被占用时自动顺延到下一个可用端口，界面/横幅里是实际地址
   需要固定端口、冲突就报错：devpulse-cli.exe --strict-port
   不自动打开浏览器：devpulse-cli.exe --no-browser
4. 数据目录：Windows %LOCALAPPDATA%\devpulse ，Linux/macOS ~/.local/share/devpulse
   换机器或整目录搬走：加 --portable ，数据放在程序同级
5. 配置：程序同级放 .env（从 .env.example 改），只认程序同级这一份
6. 迁移到新机器：数据目录一起拷过去；或者在「设置 → 数据」导出 JSON，到新机器导入
'@
    [System.IO.File]::WriteAllText((Join-Path $stage '使用说明.txt'), $guide, (New-Object System.Text.UTF8Encoding($false)))
    $zip = Join-Path $root 'dist\devpulse-standalone.zip'
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -Force
    Remove-Item $stage -Recurse -Force
    Ok "免容器发布包 $zip"
}
catch {
    Write-Host "`n构建失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
