<#
.SYNOPSIS
    开机自启：拉起 podman 虚拟机与容器。

.DESCRIPTION
    被 Windows 计划任务（启动与登录时）调用：
    1. 启动 podman 虚拟机（已运行则跳过）
    2. 等待 podman API 就绪，失败时重启 WSL 重建 Windows 侧端口转发
    3. 拉起 MySQL、Redis 与研发脉冲容器

.EXAMPLE
    pwsh -File .\scripts\podman_autostart.ps1
#>
[CmdletBinding()]
param(
    [string]$Machine = 'podman-machine-default',
    [string[]]$Containers = @('mysql8', 'redis', 'worklog-reporter'),
    [int]$WaitSeconds = 45
)

$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'

function Step([string]$text) { Write-Host ">> $text" }

function Test-ApiReady([int]$seconds) {
    for ($i = 0; $i -lt [math]::Max(1, $seconds / 2); $i++) {
        & podman ps > $null 2>&1
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

Step "检查 podman 虚拟机 $Machine"
$running = (& podman machine list --format '{{.Name}} {{.Running}}' 2>$null) | Select-String -SimpleMatch $Machine
if (-not ($running -and "$running" -match 'true')) {
    & podman machine start $Machine | Out-Null
    Step "虚拟机已启动"
}

Step "等待 podman API 就绪"
if (-not (Test-ApiReady $WaitSeconds)) {
    # Windows 侧的端口转发可能已失效，重启 WSL 后重建
    Step "端口转发未就绪，重启 WSL 后重试"
    & wsl --shutdown | Out-Null
    Start-Sleep -Seconds 8
    & podman machine start $Machine | Out-Null
    if (-not (Test-ApiReady $WaitSeconds)) {
        Write-Host "   podman 虚拟机启动失败，请检查 podman 服务"
        exit 1
    }
}

Step "拉起容器"
foreach ($name in $Containers) {
    & podman start $name 2>$null | Out-Null
    Write-Host "   $name"
}

Step "当前容器"
& podman ps --format '   {{.Names}}  {{.Status}}  {{.Ports}}'
