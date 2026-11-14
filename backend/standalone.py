"""单文件可执行程序的入口。

由 PyInstaller 打包成 devpulse.exe / devpulse，
目标机器无需 Python、无需容器，双击即用。
"""

from __future__ import annotations

import multiprocessing
import os
import sys


def _parse_args(argv: list[str]) -> dict:
    """解析命令行参数：--port / --host / --data-dir / --database-url"""
    options: dict[str, str] = {}
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in ("--port", "-p") and index + 1 < len(argv):
            options["port"] = argv[index + 1]
            index += 2
        elif token in ("--host",) and index + 1 < len(argv):
            options["host"] = argv[index + 1]
            index += 2
        elif token in ("--data-dir", "-d") and index + 1 < len(argv):
            options["data_dir"] = argv[index + 1]
            index += 2
        elif token in ("--database-url",) and index + 1 < len(argv):
            options["database_url"] = argv[index + 1]
            index += 2
        elif token in ("--help", "-h"):
            print("用法：devpulse [选项]")
            print("  -p, --port <端口>          监听端口，默认 8000")
            print("  -d, --data-dir <目录>      数据目录，默认 exe 同级的 data")
            print("      --host <地址>          监听地址，默认 0.0.0.0")
            print("      --database-url <连接串> 指定数据库，留空使用本地 SQLite")
            raise SystemExit(0)
        else:
            index += 1
    return options


def _data_dir() -> str:
    """数据目录：优先环境变量，其次 exe 同级，其次用户目录。"""
    env = os.getenv("DEV_PULSE_DATA_DIR")
    if env:
        return env
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        return os.path.join(base, "data")
    home = os.path.expanduser("~")
    return os.path.join(home, ".devpulse")


def main() -> int:
    import uvicorn

    options = _parse_args(sys.argv[1:])

    data_dir = options.get("data_dir") or os.getenv("DATA_DIR") or _data_dir()
    os.environ["DATA_DIR"] = data_dir
    os.makedirs(data_dir, exist_ok=True)
    if options.get("database_url"):
        os.environ["DATABASE_URL"] = options["database_url"]

    # 必须在设置好 DATA_DIR 之后再导入，配置在导入时读取
    from app.main import app

    host = options.get("host") or os.getenv("DEV_PULSE_HOST", "0.0.0.0")
    port = int(options.get("port") or os.getenv("DEV_PULSE_PORT") or 8000)

    print("=" * 52)
    print("  研发脉冲 · Dev Pulse")
    print(f"  访问地址   http://127.0.0.1:{port}")
    print(f"  数据目录   {data_dir}")
    print("  停止服务   Ctrl + C")
    print("=" * 52)

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())