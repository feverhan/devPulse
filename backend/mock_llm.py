"""模拟 OpenAI 兼容大模型服务，用于端到端联调验证。

启动：python backend/mock_llm.py 18080
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 18080

SAMPLE = """一、集团访客系统

1.企业微信界面调整，默认发起时间各端统一

二、南通海事短临预警系统

1.短临预警系统MCP服务开发
2.风电场模块打卡业务调整

三、交通局充电平台运维项目

1.排查金立服务器无法连接问题
2.特来电相关企业数据对接
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):  # 静默
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"models": [{"id": "mock-qwen"}]}).encode("utf-8"))

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        is_probe = "只回复两个字" in json.dumps(payload, ensure_ascii=False)
        content = "正常" if is_probe else SAMPLE
        body = {
            "id": "mock",
            "object": "chat.completion",
            "model": payload.get("model", "mock-qwen"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        }
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print(f"mock llm listening on http://127.0.0.1:{PORT}/v1")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()