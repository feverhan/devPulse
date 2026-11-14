#!/usr/bin/env bash
# 构建免容器的单文件可执行程序（Linux / macOS）。
#
# 先构建前端静态资源，再用 PyInstaller 把后端与依赖打包成 dist/devpulse/devpulse。
# 目标机器无需 Python、无需容器，执行即用。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

SKIP_FRONTEND=0
PYTHON="python3"
for arg in "$@"; do
  case "$arg" in
    --skip-frontend) SKIP_FRONTEND=1 ;;
    --python) shift; PYTHON="$1" ;;
  esac
done

step() { printf '\n>> %s\n' "$1"; }
ok() { printf '   %s\n' "$1"; }

step "检查构建工具"
if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
  ok "安装 PyInstaller"
  "$PYTHON" -m pip install --quiet pyinstaller
fi
ok "Python $($PYTHON --version 2>&1)"

if [ "$SKIP_FRONTEND" -eq 0 ]; then
  step "构建前端"
  cd "$ROOT/frontend"
  npm run build
  cd "$ROOT"
  ok "前端构建完成"
fi

step "打包可执行程序"
"$PYTHON" -m PyInstaller --noconfirm --clean "$ROOT/scripts/standalone/devpulse.spec"

OUT="$ROOT/dist/devpulse/devpulse"
[ -x "$OUT" ] || OUT="$ROOT/dist/devpulse"
if [ ! -e "$OUT" ]; then
  echo "未找到打包产物" >&2
  exit 1
fi

SIZE=$(du -sh "$OUT" | cut -f1)
printf '\n构建完成：%s（%s）\n' "$OUT" "$SIZE"
printf '   拷到目标机器执行即用；数据目录默认在 ~/.local/share/devpulse，加 --portable 则放程序同级。\n'