"""单文件可执行程序的入口。

由 PyInstaller 打包成 devpulse.exe / devpulse，
目标机器无需 Python、无需容器，双击即用。
"""

from __future__ import annotations

import json
import multiprocessing
import os
import socket
import sys
import time
import urllib.request

APP_NAME = "研发脉冲"
DEFAULT_PORT = 8000
# 端口被占用时向后顺延的最大次数
PORT_SCAN_RANGE = 50


def _default_data_dir() -> str:
    """默认数据目录：系统用户数据目录。

    不跟着可执行文件走，避免把数据写进构建产物目录（下次构建可能被清掉）。
    """
    if sys.platform == "win32":
        base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "devpulse")
    base = os.getenv("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "devpulse")


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
        elif token == "--portable":
            options["portable"] = "1"
            index += 1
        elif token == "--strict-port":
            options["strict_port"] = "1"
            index += 1
        elif token in ("--help", "-h"):
            print("用法：devpulse [选项]")
            print("  -p, --port <端口>          监听端口，默认 8000；被占用时自动顺延")
            print("      --strict-port          端口被占用时直接退出，不自动顺延")
            print("  -d, --data-dir <目录>      数据目录，默认系统用户数据目录")
            print("      --portable             数据放在程序同级，便于整目录拷贝")
            print("      --host <地址>          监听地址，默认 0.0.0.0")
            print("      --database-url <连接串> 指定数据库，留空使用本地 SQLite")
            raise SystemExit(0)
        else:
            index += 1
    return options


def _data_dir(options: dict) -> str:
    """数据目录优先级：命令行 > 环境变量 > 便携模式 > 系统用户目录。"""
    if options.get("data_dir"):
        return options["data_dir"]
    env = os.getenv("DEV_PULSE_DATA_DIR") or os.getenv("DATA_DIR")
    if env:
        return env
    if options.get("portable") and getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "data")
    return _default_data_dir()


def _bind_host(host: str) -> str:
    return "0.0.0.0" if host in ("", "0.0.0.0", "::", "*") else host


def _has_listener(host: str, port: int, timeout: float = 0.4) -> bool:
    """该端口是否已有进程在监听。

    Windows 上通配地址与具体地址可以共存，只看绑定结果会误判，
    这里先主动连一次，确认是否有既有服务占着地址。
    """
    targets = ["127.0.0.1"] if host in ("", "0.0.0.0", "::", "*") else [host]
    for target in targets:
        try:
            with socket.create_connection((target, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def _port_is_free(host: str, port: int) -> bool:
    """端口是否可用：无人监听，且能绑定。"""
    if _has_listener(host, port):
        return False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((_bind_host(host), port))
    except OSError:
        return False
    return True


def _running_instance(port: int, timeout: float = 1.5) -> bool:
    """该端口上是否已经跑着一份本应用。"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as resp:
            if resp.status != 200:
                return False
            payload = json.loads(resp.read().decode("utf-8", "ignore"))
    except Exception:
        return False
    return isinstance(payload, dict) and payload.get("app") == APP_NAME


class _AlreadyRunning(Exception):
    """端口上已经有本应用的实例。"""

    def __init__(self, port: int) -> None:
        super().__init__(port)
        self.port = port


def _resolve_port(host: str, requested: int, strict: bool = False) -> tuple[int, int | None]:
    """确定实际监听端口。

    返回 (监听端口, 被占用的原端口)；原端口为 None 表示未发生冲突。
    端口已被本应用占用时抛出 _AlreadyRunning，由调用方提示后退出。
    """
    if _port_is_free(host, requested):
        return requested, None
    if strict:
        raise SystemExit(f"端口 {requested} 已被占用")
    if _running_instance(requested):
        raise _AlreadyRunning(requested)
    for offset in range(1, PORT_SCAN_RANGE + 1):
        candidate = requested + offset
        if _port_is_free(host, candidate):
            return candidate, requested
    raise SystemExit(f"端口 {requested}-{requested + PORT_SCAN_RANGE} 均已被占用")


def _write_runtime_file(data_dir: str, host: str, port: int) -> None:
    """把本次运行的端口等信息写到数据目录，方便外部脚本定位实例。"""
    try:
        path = os.path.join(data_dir, "runtime.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "pid": os.getpid(),
                    "host": host,
                    "port": port,
                    "url": f"http://127.0.0.1:{port}",
                    "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
    except OSError:
        pass


def _use_local_env_file() -> None:
    """只读程序同级的 .env，不受启动目录影响。"""
    if not getattr(sys, "frozen", False):
        return
    os.environ["DEV_PULSE_ENV_FILE"] = os.path.join(os.path.dirname(sys.executable), ".env")


def _use_utf8_console() -> None:
    """控制台按 UTF-8 输出，日志重定向到文件时也不会乱码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    import uvicorn

    _use_utf8_console()
    options = _parse_args(sys.argv[1:])

    data_dir = _data_dir(options)
    os.environ["DATA_DIR"] = data_dir
    os.makedirs(data_dir, exist_ok=True)
    if options.get("database_url"):
        os.environ["DATABASE_URL"] = options["database_url"]
    _use_local_env_file()

    # 必须在设置好 DATA_DIR 之后再导入，配置在导入时读取
    from app.main import app

    host = options.get("host") or os.getenv("DEV_PULSE_HOST", "0.0.0.0")
    requested_port = int(options.get("port") or os.getenv("DEV_PULSE_PORT") or DEFAULT_PORT)

    try:
        port, conflict = _resolve_port(host, requested_port, strict=bool(options.get("strict_port")))
    except _AlreadyRunning as exc:
        print("=" * 52, flush=True)
        print(f"  端口 {exc.port} 上已有运行中的 {APP_NAME}：http://127.0.0.1:{exc.port}", flush=True)
        print("  需要另起一个实例请加 --port 指定其他端口", flush=True)
        print("=" * 52, flush=True)
        return 0

    if conflict:
        print(f"端口 {conflict} 已被占用，自动改用 {port}", flush=True)

    _write_runtime_file(data_dir, host, port)

    print("=" * 52, flush=True)
    print(f"  {APP_NAME} · Dev Pulse", flush=True)
    print(f"  访问地址   http://127.0.0.1:{port}", flush=True)
    print(f"  数据目录   {data_dir}", flush=True)
    print("  停止服务   Ctrl + C", flush=True)
    print("=" * 52, flush=True)

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
