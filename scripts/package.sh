#!/usr/bin/env bash
# 工时周报 · 打包脚本（Linux / macOS）
#
# 用法：
#   bash scripts/package.sh
#   bash scripts/package.sh --version 1.2.0 --push
#   bash scripts/package.sh --engine docker --skip-tests
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION=""
REGISTRY="ascr.asun.cloud/visitor"
IMAGE_NAME="worklog-reporter"
ENGINE="podman"
OUTPUT_DIR="dist"
BASE_REGISTRY="docker.m.daocloud.io/library"
SKIP_TESTS=0
SKIP_SOURCE=0
SKIP_IMAGE=0
PUSH=0

while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION="$2"; shift 2 ;;
    --registry) REGISTRY="$2"; shift 2 ;;
    --image-name) IMAGE_NAME="$2"; shift 2 ;;
    --engine) ENGINE="$2"; shift 2 ;;
    --output) OUTPUT_DIR="$2"; shift 2 ;;
    --base-registry) BASE_REGISTRY="$2"; shift 2 ;;
    --skip-tests) SKIP_TESTS=1; shift ;;
    --skip-source) SKIP_SOURCE=1; shift ;;
    --skip-image) SKIP_IMAGE=1; shift ;;
    --push) PUSH=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "未知参数：$1" >&2; exit 1 ;;
  esac
done

step() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    %s\n' "$1"; }

step "准备打包环境"
if [ -z "$VERSION" ]; then
  if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
    VERSION="$(git describe --tags --always --dirty 2>/dev/null || true)"
  fi
  [ -z "$VERSION" ] && VERSION="$(date +%Y%m%d)"
fi
VERSION="$(printf '%s' "$VERSION" | tr -c '0-9A-Za-z._-' '-')"
mkdir -p "$OUTPUT_DIR"
IMAGE_REF="${REGISTRY}/${IMAGE_NAME}:${VERSION}"
LOCAL_REF="${IMAGE_NAME}:${VERSION}"
command -v "$ENGINE" >/dev/null 2>&1 || { echo "未找到容器引擎 $ENGINE" >&2; exit 1; }
ok "版本       $VERSION"
ok "产物目录   $(cd "$OUTPUT_DIR" && pwd)"
ok "镜像标签   $IMAGE_REF"
ok "容器引擎   $ENGINE"

step "构建前端"
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  ok "安装依赖 npm ci"
  npm ci --no-audit --no-fund
fi
ok "类型检查 vue-tsc"
npx vue-tsc --noEmit
ok "构建产物 vite build"
npm run build
cd "$ROOT"

if [ "$SKIP_TESTS" -eq 0 ]; then
  step "运行后端测试"
  if [ -x "$ROOT/.venv/bin/python" ]; then
    "$ROOT/.venv/bin/python" -m pytest backend/tests -q
  else
    python3 -m pytest backend/tests -q
  fi
  ok "全部通过"
fi

if [ "$SKIP_IMAGE" -eq 0 ]; then
  step "构建镜像 $LOCAL_REF"
  "$ENGINE" build --build-arg "REGISTRY=$BASE_REGISTRY" -t "$LOCAL_REF" -t "$IMAGE_REF" .
  ok "镜像构建完成"
fi

if [ "$SKIP_SOURCE" -eq 0 ]; then
  step "导出源码包"
  SRC_ARCHIVE="$OUTPUT_DIR/${IMAGE_NAME}-src-${VERSION}.tar.gz"
  rm -f "$SRC_ARCHIVE"
  tar -czf "$SRC_ARCHIVE" \
    --exclude=.venv --exclude=node_modules --exclude=frontend/node_modules \
    --exclude=frontend/dist --exclude=static --exclude=data --exclude=.env \
    --exclude=.git --exclude=__pycache__ --exclude='*.pyc' \
    --exclude=.pytest_cache --exclude="$(basename "$OUTPUT_DIR")" \
    --exclude=.playwright-cli --exclude='*.log' \
    -C "$ROOT" .
  ok "$SRC_ARCHIVE"
fi

if [ "$SKIP_IMAGE" -eq 0 ]; then
  step "导出镜像包"
  IMG_ARCHIVE="$OUTPUT_DIR/${IMAGE_NAME}-${VERSION}.tar"
  rm -f "$IMG_ARCHIVE"
  "$ENGINE" save --format docker-archive -o "$IMG_ARCHIVE" "$IMAGE_REF" \
    || "$ENGINE" save -o "$IMG_ARCHIVE" "$IMAGE_REF"
  ok "$IMG_ARCHIVE"
fi

if [ "$PUSH" -eq 1 ] && [ "$SKIP_IMAGE" -eq 0 ]; then
  step "推送镜像 $IMAGE_REF"
  "$ENGINE" push "$IMAGE_REF"
  ok "推送完成"
fi

step "打包产物"
( cd "$OUTPUT_DIR" && ls -lh --time-style=+ | tail -n +2 )

printf '\n打包完成\n'