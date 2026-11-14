<#
.SYNOPSIS
    研发脉冲 · 一键安装启动

.DESCRIPTION
    检查容器引擎 → 准备镜像 → 启动容器 → 等待健康 → 打开浏览器。
    首次访问会进入初始化向导，可在那里配置数据库、大模型与访问密码。

.EXAMPLE
    .\scripts\install.ps1

.EXAMPLE
    .\scripts\install.ps1 -Port 9000 -DataDir D:\data\devpulse
#>
[CmdletBinding()]
param(
    [string]$Image = 'ascr.asun.cloud/visitor/worklog-reporter:1.0.0',
    [string]$ImageFile = '',
    [int]$Port = 8000,
    [string]$DataDir = '',
    [string]$DatabaseUrl = '',
    [switch]$NoBrowser,
    [switch]$SkipPull,
    [string]$ContainerName = 'devpulse',
    [string]$VolumeName = 'devpulse-data'
)

$ErrorActionPreference = 'Stop'

function Step([string]$text) { Write-Host "`n>> $text" -ForegroundColor Cyan }
function Ok([string]$text) { Write-Host "   $text" -ForegroundColor Green }
function Warn([string]$text) { Write-Host "   $text" -ForegroundColor Yellow }
function Die([string]$text) { Write-Host "`n安装失败：$text" -ForegroundColor Red; exit 1 }

function Test-PortBusy([int]$Port) {
    # 已有进程在监听这个端口
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $client.Connect('127.0.0.1', $Port)
        $client.Close()
        return $true
    }
    catch { return $false }
}

function Find-FreePort([int]$Preferred) {
    # 端口被占用时向后找一个可用的
    for ($p = $Preferred; $p -le $Preferred + 20; $p++) {
        if (Test-PortBusy $p) { continue }
        $listener = $null
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $p)
            $listener.Start()
            return $p
        }
        catch { }
        finally {
            if ($listener) { $listener.Stop() }
        }
    }
    return $Preferred
}

# ---------- 1. 容器引擎 ----------
Step '检查容器引擎'
$engine = $null
foreach ($candidate in @('podman', 'docker')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) { $engine = $candidate; break }
}
if (-not $engine) { Die '未找到 podman 或 docker，请先安装其中之一' }
Ok "使用 $engine"

if ($engine -eq 'podman') {
    $machine = podman machine list --format '{{.Name}} {{.Running}}' 2>$null | Select-Object -First 1
    if (-not $machine) { Die 'Podman 尚未初始化，请先执行：podman machine init && podman machine start' }
    if ($machine -notmatch 'true') {
        Warn 'Podman 虚拟机未运行，正在启动…'
        podman machine start | Out-Null
    }
    Ok 'Podman 虚拟机就绪'
}

# ---------- 2. 镜像 ----------
Step '准备镜像'
$haveImage = (& $engine images --format '{{.Repository}}:{{.Tag}}' 2>$null) -contains $Image
if ($haveImage) {
    Ok "本地已有 $Image"
} elseif ($ImageFile -and (Test-Path $ImageFile)) {
    Ok "导入本地镜像包 $ImageFile"
    & $engine load -i $ImageFile | Out-Null
    if ($LASTEXITCODE -ne 0) { Die '镜像导入失败' }
    Ok '导入完成'
} elseif ($SkipPull) {
    Die '本地没有该镜像，且已指定跳过拉取'
} else {
    Ok "拉取 $Image"
    & $engine pull $Image
    if ($LASTEXITCODE -ne 0) { Die '镜像拉取失败，请检查网络或改用离线安装包' }
    Ok '拉取完成'
}

# ---------- 3. 数据目录 ----------
Step '准备数据目录'
# 指定了目录就直接挂载；没指定则用命名卷，避免 SQLite 在 Windows 挂载盘上异常
$useVolume = -not $DataDir
if ($useVolume) {
    & $engine volume exists $VolumeName 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        & $engine volume create $VolumeName | Out-Null
    }
    $resolvedData = "命名卷 $VolumeName"
    Ok "数据存在 $VolumeName 命名卷"
} else {
    $resolvedData = [System.IO.Path]::GetFullPath($DataDir)
    if (-not (Test-Path $resolvedData)) { New-Item -ItemType Directory -Force -Path $resolvedData | Out-Null }
    Ok "数据目录 $resolvedData"
}

# ---------- 4. 启动 ----------
Step '启动容器'
$realPort = Find-FreePort $Port
if ($realPort -ne $Port) {
    Warn "端口 $Port 已被占用，改用 $realPort"
    $Port = $realPort
}
& $engine rm -f $ContainerName 2>$null | Out-Null
$runArgs = @(
    'run', '-d',
    '--name', $ContainerName,
    '--restart', 'unless-stopped',
    '-p', "${Port}:8000",
    '-v', $(if ($useVolume) { "${VolumeName}:/app/data" } else { "${resolvedData}:/app/data" }),
    '-e', 'DATA_DIR=/app/data'
)
# 时区默认 Asia/Shanghai（与应用内默认值一致）；如需其他时区请手动加
# -e APP_TIMEZONE=Europe/London 这样的 IANA 时区名
if ($DatabaseUrl) { $runArgs += @('-e', "DATABASE_URL=$DatabaseUrl") }
$runArgs += $Image
& $engine @runArgs | Out-Null
if ($LASTEXITCODE -ne 0) { Die '容器启动失败' }
Ok "容器 $ContainerName 已启动，端口 $Port"

# ---------- 5. 健康检查 ----------
Step '等待服务就绪'
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 2
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" -UseBasicParsing -TimeoutSec 4
        if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    Warn '健康检查未通过，最近日志：'
    & $engine logs --tail 30 $ContainerName
    Die "服务未就绪，请查看日志排查"
}
Ok '服务已就绪'

$url = "http://127.0.0.1:$Port"
Write-Host "`n安装完成" -ForegroundColor Green
Write-Host "   访问地址   $url"
Write-Host "   数据目录   $resolvedData"
Write-Host "   停止服务   $engine stop $ContainerName"
Write-Host "   启动服务   $engine start $ContainerName"
Write-Host "   查看日志   $engine logs -f $ContainerName"
Write-Host "`n首次打开会进入初始化向导，可配置数据库、大模型与访问密码。`n"

if (-not $NoBrowser) {
    try { Start-Process $url | Out-Null } catch { }
}