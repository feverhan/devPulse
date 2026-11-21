<#
.SYNOPSIS
    工时周报 · 打包脚本

.DESCRIPTION
    依次执行：代码检查 → 前端构建 → 后端测试 → 容器镜像构建 → 导出源码包与镜像包（可选推送仓库）。
    产物统一输出到 dist/ 目录。

.EXAMPLE
    .\scripts\package.ps1
    以当天日期为版本号打包。

.EXAMPLE
    .\scripts\package.ps1 -Version 1.2.0 -Push
    指定版本号，打包并推送到公司镜像仓库。
#>
[CmdletBinding()]
param(
    [string]$Version = '',
    [string]$Registry = 'ascr.asun.cloud/visitor',
    [string]$ImageName = 'worklog-reporter',
    [ValidateSet('podman', 'docker')]
    [string]$Engine = 'podman',
    [string]$OutputDir = 'dist',
    [switch]$SkipTests,
    [switch]$SkipSource,
    [switch]$SkipImage,
    [switch]$Push,
    [string]$BaseRegistry = 'docker.m.daocloud.io/library'
)

$ErrorActionPreference = 'Stop'

if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Host '本脚本需要 PowerShell 7+（本文件为 UTF-8 无 BOM，Windows PowerShell 5.1 无法正确解析中文）。' -ForegroundColor Red
    Write-Host '请改用：pwsh -File .\scripts\package.ps1' -ForegroundColor Yellow
    exit 1
}

$root = Split-Path -Parent $PSScriptRoot
Push-Location $root

function Write-Step([string]$text) {
    Write-Host ''
    Write-Host "==> $text" -ForegroundColor Cyan
}

function Write-Ok([string]$text) {
    Write-Host "    $text" -ForegroundColor DarkGreen
}

function Write-Warn([string]$text) {
    Write-Host "    $text" -ForegroundColor Yellow
}

try {
    # ---------- 1. 版本与目录 ----------
    Write-Step '准备打包环境'
    if (-not $Version) {
        $Version = if (Get-Command git -ErrorAction SilentlyContinue) {
            $tag = git describe --tags --always --dirty 2>$null
            if ($tag) { $tag } else { (Get-Date -Format 'yyyyMMdd') }
        } else {
            (Get-Date -Format 'yyyyMMdd')
        }
    }
    $Version = $Version -replace '[^0-9A-Za-z._-]', '-'
    $outPath = if ([System.IO.Path]::IsPathRooted($OutputDir)) { $OutputDir } else { Join-Path $root $OutputDir }
    if (-not (Test-Path $outPath)) { New-Item -ItemType Directory -Force -Path $outPath | Out-Null }
    $imageRef = "$Registry/$ImageName`:$Version"
    $localRef = "$ImageName`:$Version"
    Write-Ok "版本       $Version"
    Write-Ok "产物目录   $outPath"
    Write-Ok "镜像标签   $imageRef"

    if (-not (Get-Command $Engine -ErrorAction SilentlyContinue)) {
        throw "未找到容器引擎 $Engine，请先安装或用 -Engine 指定"
    }
    Write-Ok "容器引擎   $Engine"

    # ---------- 2. 前端构建 ----------
    Write-Step '构建前端'
    Push-Location (Join-Path $root 'frontend')
    try {
        if (-not (Test-Path 'node_modules')) {
            Write-Ok '安装依赖 npm ci'
            npm ci --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'npm ci 失败' }
        }
        Write-Ok '类型检查 vue-tsc'
        npx vue-tsc --noEmit
        if ($LASTEXITCODE -ne 0) { throw '类型检查未通过' }
        Write-Ok '构建产物 vite build'
        npm run build
        if ($LASTEXITCODE -ne 0) { throw '前端构建失败' }
    } finally {
        Pop-Location
    }

    # ---------- 3. 后端测试 ----------
    if (-not $SkipTests) {
        Write-Step '运行后端测试'
        $python = Join-Path $root '.venv\Scripts\python.exe'
        if (-not (Test-Path $python)) { $python = 'python' }
        & $python -m pytest backend/tests -q
        if ($LASTEXITCODE -ne 0) { throw '后端测试未通过' }
        Write-Ok '全部通过'
    } else {
        Write-Step '跳过后端测试'
    }

    # ---------- 4. 构建镜像 ----------
    if (-not $SkipImage) {
        Write-Step "构建镜像 $localRef"
        $buildArgs = @('build')
        if ($Engine -eq 'podman') { $buildArgs += @('--format', 'docker') }
        $buildArgs += @('--build-arg', "REGISTRY=$BaseRegistry", '-t', $localRef, '-t', $imageRef, '.')
        & $Engine @buildArgs
        if ($LASTEXITCODE -ne 0) { throw '镜像构建失败' }
        Write-Ok '镜像构建完成'
    } else {
        Write-Step '跳过镜像构建'
    }

    # ---------- 5. 导出源码包 ----------
    if (-not $SkipSource) {
        Write-Step '导出源码包'
        $srcArchive = Join-Path $outPath "$ImageName-src-$Version.tar.gz"
        if (Test-Path $srcArchive) { Remove-Item $srcArchive -Force }
        $excludes = @(
            '--exclude=.venv', '--exclude=node_modules', '--exclude=frontend/node_modules',
            '--exclude=frontend/dist', '--exclude=static', '--exclude=data', '--exclude=.env',
            '--exclude=.git', '--exclude=__pycache__', '--exclude=*.pyc',
            '--exclude=.pytest_cache', "--exclude=$([System.IO.Path]::GetFileName($outPath))",
            "--exclude=./$([System.IO.Path]::GetFileName($outPath))",
            '--exclude=.playwright-cli', '--exclude=*.log'
        )
        & tar -czf $srcArchive @excludes -C $root .
        if ($LASTEXITCODE -ne 0) { throw '源码包导出失败' }
        Write-Ok $srcArchive
    } else {
        Write-Step '跳过源码包导出'
    }

    # ---------- 6. 导出镜像包 ----------
    if (-not $SkipImage) {
        Write-Step '导出镜像包'
        $imgArchive = Join-Path $outPath "$ImageName-$Version.tar"
        if (Test-Path $imgArchive) { Remove-Item $imgArchive -Force }
        & $Engine save --format docker-archive -o $imgArchive $imageRef
        if ($LASTEXITCODE -ne 0) { & $Engine save -o $imgArchive $imageRef }
        if ($LASTEXITCODE -ne 0) { throw '镜像包导出失败' }
        Write-Ok $imgArchive
    }

    # ---------- 7. 推送 ----------
    if ($Push -and -not $SkipImage) {
        Write-Step "推送镜像 $imageRef"
        & $Engine push $imageRef
        if ($LASTEXITCODE -ne 0) { throw '镜像推送失败' }
        Write-Ok '推送完成'
    }

    # ---------- 8. 产物清单 ----------
    Write-Step '打包产物'
    Get-ChildItem $outPath -File | Sort-Object Name | ForEach-Object {
        $hash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.Substring(0, 16)
        Write-Host ("    {0,-46} {1,10:N1} MB  {2}" -f $_.Name, ($_.Length / 1MB), $hash)
    }
    Write-Host ''
    Write-Host '打包完成' -ForegroundColor Green
}
catch {
    Write-Host ''
    Write-Host "打包失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
