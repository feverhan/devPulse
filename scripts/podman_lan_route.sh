#!/usr/bin/env bash
# 为 podman 虚拟机补一条更具体的路由，解决内网网段与 podman 网桥网段冲突。
# 用法：bash scripts/podman_lan_route.sh 10.88.192.0/24 [更多网段...]
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "用法：$0 <CIDR> [CIDR...]" >&2
  exit 1
fi

GATEWAY="${GATEWAY:-}"
if [ -z "$GATEWAY" ]; then
  GATEWAY=$(podman machine ssh -- ip route | awk '/^default via/ {print $3; exit}')
fi

echo "虚拟机默认网关：$GATEWAY"

for cidr in "$@"; do
  podman machine ssh -- sudo ip route replace "$cidr" via "$GATEWAY" dev eth0
  echo "已设置路由 $cidr via $GATEWAY dev eth0"
done

echo "当前路由表："
podman machine ssh -- ip route