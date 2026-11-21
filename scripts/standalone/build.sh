#!/usr/bin/env bash
# 构建免容器的可执行程序（Linux / macOS）。
#
# 先构建前端静态资源，再用 PyInstaller 打包图形 exe 与命令行可执行程序。
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

GUI_OUT="$ROOT/dist/devpulse"
CLI_OUT="$ROOT/dist/devpulse-cli"
[ -e "$GUI_OUT" ] || { echo "未找到图形启动器：$GUI_OUT" >&2; exit 1; }
[ -e "$CLI_OUT" ] || { echo "未找到命令行程序：$CLI_OUT" >&2; exit 1; }

SIZE=$(du -csh "$GUI_OUT" "$CLI_OUT" | tail -1 | cut -f1)
printf '\n构建完成：%s / %s（合计 %s）\n' "$GUI_OUT" "$CLI_OUT" "$SIZE"
printf '   devpulse 是图形启动/停止界面；devpulse-cli 保留命令行模式。\n'

step '生成免容器发布包'
STAGE=$ROOT/dist/devpulse-standalone
rm -rf $STAGE
mkdir -p $STAGE
cp "$GUI_OUT" "$STAGE/devpulse"
cp "$CLI_OUT" "$STAGE/devpulse-cli"
cp "$ROOT/.env.example" "$STAGE/.env.example"
cat > $STAGE/使用说明.txt <<'GUIDE'
研发脉冲 · Dev Pulse（免容器版）

1. 解压后执行 ./devpulse 打开启动/停止界面
2. 在界面里点「启动」；服务运行后可点「打开页面」，停止用「停止」或直接关闭窗口
3. 需要命令行/服务器模式时执行 ./devpulse-cli，例如：
   ./devpulse-cli --port 8080 --no-browser
   端口被占用时自动顺延到下一个可用端口，界面/横幅里是实际地址
   需要固定端口、冲突就报错：./devpulse-cli --strict-port
   不自动打开浏览器：./devpulse-cli --no-browser
4. 数据目录：~/.local/share/devpulse（可用 XDG_DATA_HOME 调整）
   换机器或整目录搬走：加 --portable ，数据放在程序同级
5. 配置：程序同级放 .env（从 .env.example 改），只认程序同级这一份
6. 迁移到新机器：数据目录一起拷过去；或者在「设置 → 数据」导出 JSON，到新机器导入
GUIDE
tar -czf "$ROOT/dist/devpulse-standalone.tar.gz" -C "$STAGE" .
rm -rf "$STAGE"
ok "免容器发布包 $ROOT/dist/devpulse-standalone.tar.gz"
