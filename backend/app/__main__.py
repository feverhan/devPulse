"""裸机运行入口：python -m app

不依赖容器，直接在本机起服务。
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    import uvicorn

    host = os.getenv("DEV_PULSE_HOST", "0.0.0.0")
    port = int(os.getenv("DEV_PULSE_PORT", "8000"))
    print(f"研发脉冲 · 启动中 http://127.0.0.1:{port}")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level=os.getenv("DEV_PULSE_LOG_LEVEL", "info"),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())