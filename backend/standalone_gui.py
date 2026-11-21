"""研发脉冲 Windows 图形启动器。

默认 exe 打开此窗口，可在窗口内启动/停止本地服务；
命令行高级用法继续使用 devpulse-cli.exe。
"""

from __future__ import annotations

import multiprocessing
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Any

import uvicorn

import standalone

APP_TITLE = standalone.APP_NAME


class Service:
    """托管的 uvicorn 服务。"""

    def __init__(self) -> None:
        self.thread: threading.Thread | None = None
        self.server: uvicorn.Server | None = None
        self.app: Any = None
        self.port: int | None = None
        self.data_dir: str = ""
        self.phase = "stopped"
        self.detail = ""
        self.error = ""
        self._stop_requested = False

    @property
    def busy(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def start(
        self,
        *,
        host: str,
        port: int,
        data_dir: str,
        database_url: str = "",
        strict_port: bool = False,
    ) -> None:
        if self.busy:
            return
        self._stop_requested = False
        self.thread = threading.Thread(
            target=self._run,
            args=(host, port, data_dir, database_url, strict_port),
            daemon=True,
        )
        self.thread.start()

    def stop(self, timeout: float = 6.0) -> None:
        self._stop_requested = True
        if self.server is not None:
            self.server.should_exit = True
        if self.thread is not None:
            self.thread.join(timeout)

    def _prepare_environment(self, data_dir: str, database_url: str) -> None:
        os.environ["DATA_DIR"] = data_dir
        os.makedirs(data_dir, exist_ok=True)
        if database_url:
            os.environ["DATABASE_URL"] = database_url
        standalone._use_local_env_file()

    def _run(
        self,
        host: str,
        requested_port: int,
        data_dir: str,
        database_url: str,
        strict_port: bool,
    ) -> None:
        self.phase = "starting"
        self.error = ""
        self.detail = ""
        self.server = None
        self.port = None
        self.data_dir = data_dir

        try:
            port, conflict = standalone._resolve_port(host, requested_port, strict=strict_port)
        except standalone._AlreadyRunning as exc:
            self.port = exc.port
            self.phase = "already"
            self.detail = f"http://127.0.0.1:{exc.port}"
            return
        except SystemExit as exc:
            self.phase = "error"
            self.error = str(exc)
            return
        except Exception as exc:  # noqa: BLE001
            self.phase = "error"
            self.error = str(exc)
            return

        self.port = port
        if conflict:
            self.detail = f"端口 {conflict} 已占用，实际使用 {port}"

        try:
            self._prepare_environment(data_dir, database_url)
            standalone._write_runtime_file(data_dir, host, port)
            if self.app is None:
                from app.main import app

                self.app = app
            server = uvicorn.Server(
                uvicorn.Config(
                    self.app,
                    host=host,
                    port=port,
                    log_level="warning",
                    log_config=None,
                    access_log=False,
                )
            )
            self.server = server
            if self._stop_requested:
                self.phase = "stopped"
                return
            server.run()
            self.phase = "stopped"
        except Exception as exc:  # noqa: BLE001
            self.phase = "error"
            self.error = str(exc)
        finally:
            self.server = None


class Launcher:
    """最小可用的启动/停止窗口。"""

    def __init__(self, options: dict[str, str]) -> None:
        self.options = options
        self.service = Service()
        default_data_dir = standalone._data_dir(options)
        default_host = options.get("host") or os.getenv("DEV_PULSE_HOST", "0.0.0.0")
        default_port = options.get("port") or os.getenv("DEV_PULSE_PORT") or str(standalone.DEFAULT_PORT)

        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("560x240")
        self.root.minsize(500, 210)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.status_var = tk.StringVar(value="已停止")
        self.url_var = tk.StringVar(value="—")
        self.detail_var = tk.StringVar(value="")
        self.port_var = tk.StringVar(value=default_port)
        self.data_dir_var = tk.StringVar(value=default_data_dir)

        frame = ttk.Frame(self.root, padding=(18, 16, 18, 14))
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="运行状态").grid(row=0, column=0, sticky="w", pady=(0, 3))
        ttk.Label(frame, textvariable=self.status_var, font=("", 11, "bold")).grid(
            row=0, column=1, sticky="w", pady=(0, 3)
        )
        ttk.Label(frame, text="访问地址").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Label(frame, textvariable=self.url_var).grid(row=1, column=1, sticky="w", pady=3)
        ttk.Label(frame, text="端口").grid(row=3, column=0, sticky="w", pady=(12, 3))
        self.port_entry = ttk.Entry(frame, textvariable=self.port_var, width=14)
        self.port_entry.grid(row=3, column=1, sticky="w", pady=(12, 3))
        ttk.Label(frame, text="数据目录").grid(row=4, column=0, sticky="w", pady=3)
        self.data_entry = ttk.Entry(frame, textvariable=self.data_dir_var)
        self.data_entry.grid(row=4, column=1, columnspan=3, sticky="ew", pady=3)

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(18, 0))
        self.start_button = ttk.Button(buttons, text="启动", command=self.start)
        self.stop_button = ttk.Button(buttons, text="停止", command=self.stop, state="disabled")
        self.open_button = ttk.Button(buttons, text="打开页面", command=self.open_page, state="disabled")
        self.quit_button = ttk.Button(buttons, text="退出", command=self.close)
        self.start_button.pack(side="left", padx=(0, 8))
        self.stop_button.pack(side="left", padx=(0, 8))
        self.open_button.pack(side="left", padx=(0, 8))
        self.quit_button.pack(side="right")

        ttk.Label(frame, textvariable=self.detail_var, foreground="#666666", wraplength=460).grid(
            row=6, column=0, columnspan=4, sticky="w", pady=(12, 0)
        )
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        self.root.after(250, self.refresh)

    def start(self) -> None:
        if self.service.busy:
            return
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            self.detail_var.set("端口必须是数字")
            return
        data_dir = self.data_dir_var.get().strip() or standalone._data_dir(self.options)
        self.service.start(
            host=self.options.get("host") or os.getenv("DEV_PULSE_HOST", "0.0.0.0"),
            port=port,
            data_dir=data_dir,
            database_url=self.options.get("database_url", ""),
            strict_port=bool(self.options.get("strict_port")),
        )
        self.refresh()

    def stop(self) -> None:
        if not self.service.busy:
            return
        self.service.phase = "stopping"
        self.refresh()
        threading.Thread(target=self.service.stop, daemon=True).start()

    def open_page(self) -> None:
        if self.service.port:
            import webbrowser

            webbrowser.open(f"http://127.0.0.1:{self.service.port}")

    def close(self) -> None:
        self.service.stop()
        self.root.destroy()

    def refresh(self) -> None:
        service = self.service
        phase = service.phase
        if service.busy and service.server is not None and not service.server.should_exit and phase != "stopping":
            phase = "running"
        url = f"http://127.0.0.1:{service.port}" if service.port and phase in ("running", "already") else ""
        if phase == "running":
            self.status_var.set("已启动")
        elif service.phase == "starting":
            self.status_var.set("正在启动")
        elif service.phase == "stopping":
            self.status_var.set("正在停止")
        elif service.phase == "already":
            self.status_var.set("已运行")
        elif service.phase == "error":
            self.status_var.set("启动失败")
        else:
            self.status_var.set("已停止")

        self.url_var.set(url or "—")
        if service.phase == "error":
            self.detail_var.set(service.error)
        elif service.detail:
            self.detail_var.set(service.detail)
        elif service.phase == "running":
            self.detail_var.set("")
        elif service.phase == "already":
            self.detail_var.set("同一端口已有本应用实例")

        busy = service.busy
        can_start = not busy and service.phase != "already"
        self.start_button.configure(state="normal" if can_start else "disabled")
        self.stop_button.configure(state="normal" if busy else "disabled")
        open_enabled = service.port is not None and phase in ("running", "already")
        self.open_button.configure(state="normal" if open_enabled else "disabled")
        self.port_entry.configure(state="normal" if not busy else "disabled")
        self.data_entry.configure(state="normal" if not busy else "disabled")

        self.root.after(250, self.refresh)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    multiprocessing.freeze_support()
    options = standalone._parse_args(sys.argv[1:])
    Launcher(options).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



