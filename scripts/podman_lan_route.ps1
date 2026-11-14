<#
.SYNOPSIS
    为 podman 虚拟机补一条更具体的路由，解决内网网段与 podman 网桥网段冲突。

.DESCRIPTION
    podman 默认网桥使用 10.88.0.0/16。若内网地址也落在该网段，容器访问内网时
    会被 podman0 网桥截走，表现为 "No route to host"。
    这里在虚拟机里加一条更精确的路由，把指定网段指回宿主机默认网关。

.EXAMPLE
    .\scripts\podman_lan_route.ps1 -Cidr 10.88.192.0/24
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string[]]$Cidr,

    [string]$Gateway = ""
)

$ErrorActionPreference = "Stop"

function Get-VmGateway {
    $route = podman machine ssh -- ip route 2>$null
    foreach ($line in $route) {
        if ($line -match "^default via (\S+) dev") { return $Matches[1] }
    }
    throw "未能从 podman 虚拟机中解析默认网关"
}

if (-not $Gateway) {
    $Gateway = Get-VmGateway
}

Write-Host "虚拟机默认网关：$Gateway"

foreach ($net in $Cidr) {
    podman machine ssh -- sudo ip route replace $net via $Gateway dev eth0 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "添加路由失败：$net via $Gateway dev eth0"
    }
    Write-Host "已设置路由 $net via $Gateway dev eth0"
}

Write-Host "当前路由表："
podman machine ssh -- ip route