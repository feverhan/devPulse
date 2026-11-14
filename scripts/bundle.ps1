<#
.SYNOPSIS
    研发脉冲 · 生成离线安装包

.DESCRIPTION
    把镜像、编排文件、安装脚本与文档打成一个压缩包。
    目标机器解压后运行「安装.bat」（Windows）或「install.sh」（Linux/macOS）即可启动。

.EXAMPLE
    .\scripts\bundle.ps1 -Version 1.0.0

.EXAMPLE
    .\scripts\bundle.ps1 -SkipImage
    只打包脚本与文档，不含镜像（适合在线安装）。
#>
[CmdletBinding()]
param(
    [string]$Version = '',
    [string]$Image = 'ascr.asun.cloud/visitor/worklog-reporter:1.0.0',
    [ValidateSet('podman', 'docker')]
    [string]$Engine = 'podman',
    [string]$OutputDir = 'dist',
    [switch]$SkipImage
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root

function Step([string]$text) { Write-Host "`n>> $text" -ForegroundColor Cyan }
function Ok([string]$text) { Write-Host "   $text" -ForegroundColor Green }

try {
    Step '准备安装包'
    if (-not $Version) {
        $tag = & $Engine images --format '{{.Tag}}' $Image 2>$null | Select-Object -First 1
        $Version = if ($tag) { $tag } else { (Get-Date -Format 'yyyyMMdd') }
    }
    $outPath = if ([System.IO.Path]::IsPathRooted($OutputDir)) { $OutputDir } else { Join-Path $root $OutputDir }
    if (-not (Test-Path $outPath)) { New-Item -ItemType Directory -Force -Path $outPath | Out-Null }

    $bundleName = "devpulse-$Version"
    $bundleDir = Join-Path $outPath $bundleName
    if (Test-Path $bundleDir) { Remove-Item $bundleDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path (Join-Path $bundleDir 'scripts') | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $bundleDir 'docs') | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $bundleDir 'image') | Out-Null
    Ok "安装包目录 $bundleDir"

    Step '收集文件'
    Copy-Item 'docker-compose.yml' $bundleDir
    Copy-Item 'docker-compose.podman.yml' $bundleDir
    Copy-Item 'docker-compose.mysql.yml' $bundleDir
    Copy-Item '.env.example' $bundleDir
    Copy-Item 'README.md' $bundleDir
    if (Test-Path 'docs\deploy.md') { Copy-Item 'docs\deploy.md' (Join-Path $bundleDir 'docs') }
    Copy-Item 'scripts\install.ps1' (Join-Path $bundleDir 'scripts')
    Copy-Item 'scripts\install.sh' (Join-Path $bundleDir 'scripts')
    Ok '编排文件、安装脚本与文档已复制'

    $imageTar = ''
    if (-not $SkipImage) {
        Step '导出镜像'
        $imageTar = Join-Path $bundleDir "image\worklog-reporter-$Version.tar"
        & $Engine save --format docker-archive -o $imageTar $Image
        if ($LASTEXITCODE -ne 0) { & $Engine save -o $imageTar $Image }
        if ($LASTEXITCODE -ne 0) { throw "镜像导出失败（本地可能还没有 $Image）" }
        Ok "镜像已导出 $imageTar"
    }

    Step '生成启动入口'
    $bat = @"
@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 研发脉冲 · 安装启动
echo.
echo   正在安装并启动 研发脉冲 ...
echo.
powershell -ExecutionPolicy Bypass -File "scripts\install.ps1" -ImageFile "image\worklog-reporter-$Version.tar"
echo.
pause
"@
    Set-Content -Path (Join-Path $bundleDir '安装.bat') -Value $bat -Encoding UTF8

    $sh = @"
#!/usr/bin/env bash
cd "`$(dirname "`$0")"
bash scripts/install.sh --image-file "image/worklog-reporter-$Version.tar"
"@
    Set-Content -Path (Join-Path $bundleDir 'install.sh') -Value $sh -Encoding UTF8
    Ok '安装.bat / install.sh 已生成'

    Step '打包'
    $zipPath = Join-Path $outPath "$bundleName.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path $bundleDir -DestinationPath $zipPath -CompressionLevel Optimal
    Ok "安装包 $zipPath"

    $size = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
    Write-Host "`n离线安装包已生成：$zipPath（$size MB）" -ForegroundColor Green
    Write-Host '   目标机器解压后运行「安装.bat」（Windows）或「install.sh」（Linux/macOS）即可。' -ForegroundColor Green
}
catch {
    Write-Host "`n打包失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}