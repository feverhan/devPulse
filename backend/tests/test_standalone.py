from __future__ import annotations

import json
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import standalone  # noqa: E402


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_default_data_dir_not_under_executable():
    data_dir = standalone._default_data_dir()
    assert "devpulse" in data_dir
    assert Path(data_dir).is_absolute()


def test_data_dir_priority(monkeypatch, tmp_path):
    monkeypatch.setenv("DEV_PULSE_DATA_DIR", str(tmp_path / "env"))
    assert standalone._data_dir({"data_dir": str(tmp_path / "cli")}) == str(tmp_path / "cli")
    assert standalone._data_dir({}) == str(tmp_path / "env")


def test_port_is_free_detects_occupied_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = int(sock.getsockname()[1])
        assert standalone._port_is_free("127.0.0.1", port) is False
    finally:
        sock.close()
    assert standalone._port_is_free("127.0.0.1", port) is True


def test_resolve_port_keeps_free_port():
    port = _free_port()
    assert standalone._resolve_port("127.0.0.1", port) == (port, None)


def test_resolve_port_moves_to_next_free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = int(sock.getsockname()[1])
        resolved, conflict = standalone._resolve_port("127.0.0.1", port)
        assert conflict == port
        assert resolved > port
        assert standalone._port_is_free("127.0.0.1", resolved) is True
    finally:
        sock.close()


def test_resolve_port_strict_raises_when_occupied():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = int(sock.getsockname()[1])
        with pytest.raises(SystemExit):
            standalone._resolve_port("127.0.0.1", port, strict=True)
    finally:
        sock.close()


def test_running_instance_detects_devpulse():
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            payload = json.dumps({"status": "ok", "app": "研发脉冲"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        assert standalone._running_instance(port) is True
        assert standalone._has_listener("127.0.0.1", port) is True
    finally:
        server.shutdown()
        server.server_close()


def test_write_runtime_file(tmp_path):
    standalone._write_runtime_file(str(tmp_path), "0.0.0.0", 8123)
    payload = json.loads((tmp_path / "runtime.json").read_text(encoding="utf-8"))
    assert payload["port"] == 8123
    assert payload["url"] == "http://127.0.0.1:8123"


def test_open_browser_when_ready(monkeypatch):
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            payload = json.dumps({"status": "ok"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    opened: list[str] = []
    monkeypatch.setattr(standalone.webbrowser, "open", lambda url: opened.append(url))
    try:
        standalone._open_browser_when_ready(port, timeout=5)
    finally:
        server.shutdown()
        server.server_close()
    assert opened == [f"http://127.0.0.1:{port}"]


def test_open_browser_gives_up_when_service_never_ready(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(standalone.webbrowser, "open", lambda url: opened.append(url))
    standalone._open_browser_when_ready(_free_port(), timeout=1.0)
    assert opened == []
