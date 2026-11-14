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

step '生成免容器发布包'
STAGE=$ROOT/dist/devpulse-standalone
rm -rf $STAGE
mkdir -p $STAGE
cp $OUT $STAGE/devpulse
cp $ROOT/.env.example $STAGE/.env.example
cat > $STAGE/使用说明.txt <<'GUIDE'
研发脉冲 · Dev Pulse（免容器单文件版）

1. 解压后执行 ./devpulse
2. 启动后自动打开浏览器（默认 http://127.0.0.1:8000 ），首次进入按向导配置数据库与大模型
3. 换端口：./devpulse --port 8080
   端口被占用时自动顺延到下一个可用端口，启动横幅里是实际地址
   需要固定端口、冲突就报错：./devpulse --strict-port
   不自动打开浏览器：./devpulse --no-browser
4. 数据目录：~/.local/share/devpulse（可用 XDG_DATA_HOME 调整）
   换机器或整目录搬走：加 --portable ，数据放在程序同级
5. 配置：程序同级放 .env（从 .env.example 改），只认程序同级这一份
7. 迁移到新机器：数据目录一起拷过去，并保持 .env 里的 APP_SECRET 不变
6. 停止服务：Ctrl + C
GUIDE
tar -czf $ROOT/dist/devpulse-standalone.tar.gz -C $STAGE .
rm -rf $STAGE
ok '免容器发布包 $ROOT/dist/devpulse-standalone.tar.gz'