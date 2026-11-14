#!/usr/bin/env bash
# Podman 部署前置准备：创建共享网络并把已有 MySQL 容器接入
set -euo pipefail

NETWORK="${NETWORK:-daylife_net}"
MYSQL_CONTAINER="${MYSQL_CONTAINER:-mysql8}"
MYSQL_ALIAS="${MYSQL_ALIAS:-mysql}"

if ! podman network exists "$NETWORK"; then
  podman network create "$NETWORK"
  echo "已创建网络 $NETWORK"
fi

if podman inspect "$MYSQL_CONTAINER" >/dev/null 2>&1; then
  if ! podman inspect "$MYSQL_CONTAINER" --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' | grep -qw "$NETWORK"; then
    podman network connect --alias "$MYSQL_ALIAS" "$NETWORK" "$MYSQL_CONTAINER"
    echo "已将 $MYSQL_CONTAINER 接入 $NETWORK，别名 $MYSQL_ALIAS"
  else
    echo "$MYSQL_CONTAINER 已在 $NETWORK 中"
  fi
else
  echo "未找到容器 $MYSQL_CONTAINER，请确认 MySQL 已启动" >&2
  exit 1
fi