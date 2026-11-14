"""\u4ece\u4ed3\u5e93\u5730\u5740\u89e3\u6790\u5e73\u53f0\u3001\u62e5\u6709\u8005\u3001\u4ed3\u5e93\u540d\u4e0e\u670d\u52a1\u5730\u5740\u3002"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

# Gitee \u7684\u57df\u540d\u9700\u8981\u5355\u72ec\u5224\u65ad\uff0c\u5176\u4f59\u9ed8\u8ba4\u5f53\u4f5c Gitea \u81ea\u90e8\u670d\u52a1
GITEE_HOSTS = ("gitee.com",)

_SCP_RE = re.compile(r"^(?:(?P<user>[^@/]+)@)?(?P<host>[^:/]+):(?P<path>.+)$")


def guess_platform(host: str) -> str:
    """\u6839\u636e\u57df\u540d\u731c\u6d4b\u5e73\u53f0\uff0c\u6700\u7ec8\u4ee5\u63a2\u6d4b\u7ed3\u679c\u4e3a\u51c6\u3002"""
    name = (host or "").strip().lower()
    if any(name == item or name.endswith("." + item) for item in GITEE_HOSTS):
        return "gitee"
    return "gitea"


def _split_port(segments: list[str]) -> tuple[str, list[str]]:
    """\u5904\u7406 scp \u5f62\u5f0f\u4e2d\u7684\u7aef\u53e3\uff1agit@host:3000/owner/repo\u3002"""
    if segments and segments[0].isdigit():
        return segments[0], segments[1:]
    return "", segments


def parse_repo_url(url: str) -> dict:
    """\u628a\u4ed3\u5e93\u5730\u5740\u62c6\u6210\u5e73\u53f0\u3001\u62e5\u6709\u8005\u3001\u4ed3\u5e93\u540d\u4e0e\u670d\u52a1\u5730\u5740\u3002

    \u652f\u6301\u4ee5\u4e0b\u5f62\u5f0f\uff1a
      https://gitee.com/owner/repo        https://gitee.com/owner/repo.git
      git@gitee.com:owner/repo.git        http://10.88.192.10:3000/root/ntms
      https://example.com/gitea/owner/repo
    """
    raw = (url or "").strip()
    if not raw:
        return {"ok": False, "message": "\u8bf7\u586b\u5199\u4ed3\u5e93\u5730\u5740"}

    host = ""
    port = ""
    scheme = "https"
    path = ""

    if "://" in raw:
        parts = urlsplit(raw)
        scheme = parts.scheme or "https"
        host = parts.hostname or ""
        try:
            port = str(parts.port) if parts.port else ""
        except ValueError:
            port = ""
        path = parts.path
    else:
        matched = _SCP_RE.match(raw)
        if matched:
            host = matched.group("host")
            segments = [item for item in matched.group("path").split("/") if item]
            port, segments = _split_port(segments)
            path = "/".join(segments)
        else:
            segments = [item for item in raw.split("/") if item]
            if len(segments) >= 3 and "." in segments[0]:
                host = segments[0]
                path = "/".join(segments[1:])
            else:
                return {"ok": False, "message": "\u65e0\u6cd5\u8bc6\u522b\u5730\u5740\u683c\u5f0f"}

    segments = [item for item in path.split("/") if item]
    if segments and segments[-1].endswith(".git"):
        segments[-1] = segments[-1][: -len(".git")]
    if len(segments) < 2:
        return {"ok": False, "message": "\u5730\u5740\u91cc\u7f3a\u5c11\u62e5\u6709\u8005\u6216\u4ed3\u5e93\u540d"}

    owner = segments[-2]
    repo = segments[-1]
    prefix = segments[:-2]

    base_url = f"{scheme}://{host}"
    if port:
        base_url += f":{port}"
    if prefix:
        base_url += "/" + "/".join(prefix)

    return {
        "ok": True,
        "platform": guess_platform(host),
        "owner": owner,
        "repo": repo,
        "base_url": base_url,
        "host": host,
    }
