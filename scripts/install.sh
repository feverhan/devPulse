#!/usr/bin/env bash
# 研发脉冲 · 一键安装启动
#
# 用法：
#   bash scripts/install.sh
#   bash scripts/install.sh --port 9000 --data-dir /opt/devpulse/data
set -euo pipefail

IMAGE="ascr.asun.cloud/visitor/worklog-reporter:1.0.0"
IMAGE_FILE=""
PORT=8000
DATA_DIR=""
DATABASE_URL=""
NO_BROWSER=0
CONTAINER="devpulse"

while [ $# -gt 0 ]; do
  case "$1" in
    --image) IMAGE="$2"; shift 2 ;;
    --image-file) IMAGE_FILE="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    --database-url) DATABASE_URL="$2"; shift 2 ;;
    --no-browser) NO_BROWSER=1; shift ;;
    *) echo "未知参数：$1" >&2; exit 1 ;;
  esac
done

step() { printf '\n>> %s\n' "$1"; }
ok() { printf '   %s\n' "$1"; }
die() { printf '\n安装失败：%s\n' "$1" >&2; exit 1; }

step "检查容器引擎"
ENGINE=""
for candidate in podman docker; do
  if command -v "$candidate" >/dev/null 2>&1; then ENGINE="$candidate"; break; fi
done
[ -z "$ENGINE" ] && die "未找到 podman 或 docker"
ok "使用 $ENGINE"

if [ "$ENGINE" = "podman" ]; then
  if ! podman machine list --format '{{.Running}}' 2>/dev/null | grep -q true; then
    ok "启动 Podman 虚拟机"
    podman machine start >/dev/null
  fi
  ok "Podman 虚拟机就绪"
fi

step "准备镜像"
if "$ENGINE" images --format '{{.Repository}}:{{.Tag}}' | grep -qx "$IMAGE"; then
  ok "本地已有 $IMAGE"
elif [ -n "$IMAGE_FILE" ] && [ -f "$IMAGE_FILE" ]; then
  ok "导入本地镜像包 $IMAGE_FILE"
  "$ENGINE" load -i "$IMAGE_FILE" >/dev/null || die "镜像导入失败"
  ok "导入完成"
else
  ok "拉取 $IMAGE"
  "$ENGINE" pull "$IMAGE" || die "镜像拉取失败，请检查网络或改用离线安装包"
  ok "拉取完成"
fi

step "准备数据目录"
[ -z "$DATA_DIR" ] && DATA_DIR="$(pwd)/data"
mkdir -p "$DATA_DIR"
DATA_DIR="$(cd "$DATA_DIR" && pwd)"
ok "数据目录 $DATA_DIR"

step "启动容器"
"$ENGINE" rm -f "$CONTAINER" >/dev/null 2>&1 || true
ARGS=(run -d --name "$CONTAINER" --restart unless-stopped
  -p "${PORT}:8000" -v "${DATA_DIR}:/app/data"
  -e DATA_DIR=/app/data)
[ -n "$DATABASE_URL" ] && ARGS+=(-e "DATABASE_URL=$DATABASE_URL")
ARGS+=("$IMAGE")
"$ENGINE" "${ARGS[@]}" >/dev/null || die "容器启动失败"
ok "容器 $CONTAINER 已启动，端口 $PORT"

step "等待服务就绪"
READY=0
for _ in $(seq 1 40); do
  sleep 2
  if curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then READY=1; break; fi
done
if [ "$READY" -ne 1 ]; then
  "$ENGINE" logs --tail 30 "$CONTAINER"
  die "服务未就绪，请查看日志排查"
fi
ok "服务已就绪"

printf '\n安装完成\n'
printf '   访问地址   http://127.0.0.1:%s\n' "$PORT"
printf '   数据目录   %s\n' "$DATA_DIR"
printf '   停止服务   %s stop %s\n' "$ENGINE" "$CONTAINER"
printf '   启动服务   %s start %s\n' "$ENGINE" "$CONTAINER"
printf '   查看日志   %s logs -f %s\n' "$ENGINE" "$CONTAINER"
printf '\n首次打开会进入初始化向导，可配置数据库、大模型与访问密码。\n\n'

[ "$NO_BROWSER" -eq 1 ] || (command -v xdg-open >/dev/null 2>&1 && xdg-open "http://127.0.0.1:${PORT}" >/dev/null 2>&1 &) || true