from __future__ import annotations

import json
import socket
import time
import urllib.request

import pytest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_gui_service_starts_and_stops(tmp_path):
    """图形启动器的托管服务能完成一次启动、健康检查与停止。"""
    pytest.importorskip("tkinter")

    import standalone_gui

    port = _free_port()
    service = standalone_gui.Service()
    service.start(host="127.0.0.1", port=port, data_dir=str(tmp_path))

    ready = False
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health", timeout=1
            ) as response:
                if response.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.1)
    assert ready, (service.phase, service.error, service.detail)

    payload = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health").read())
    assert payload["status"] == "ok"

    service.stop()
    assert not service.busy
    assert (tmp_path / "runtime.json").is_file()
