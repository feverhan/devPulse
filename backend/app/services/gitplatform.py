from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import httpx

from ..timeutil import parse_dt

GITEA_DEFAULT_BASE = "https://gitea.com"
GITEE_DEFAULT_BASE = "https://gitee.com"

GITEA_PAGE_SIZE = 50
GITEE_PAGE_SIZE = 100
MAX_FILE_COMMITS = 30
MAX_REVIEW_FILES = 8
MAX_REVIEW_FILE_BYTES = 6000
MAX_DIFF_CHARS = 24000


class PlatformError(RuntimeError):
    """平台接口调用失败，消息直接面向使用者。"""


@dataclass
class FetchedCommit:
    sha: str
    message: str = ""
    author_name: str = ""
    author_email: str = ""
    author_login: str = ""
    url: str = ""
    committed_at: datetime | None = None
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    files: list[dict] = field(default_factory=list)


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _parse_commit(raw: dict) -> FetchedCommit:
    commit = raw.get("commit") or {}
    inner_author = commit.get("author") or {}
    outer_author = raw.get("author") or {}
    stats = raw.get("stats") or {}
    files = raw.get("files") or []
    committed_at = parse_dt(inner_author.get("date")) or parse_dt(raw.get("created"))
    return FetchedCommit(
        sha=(raw.get("sha") or raw.get("id") or "").strip(),
        message=(commit.get("message") or raw.get("message") or "").strip(),
        author_name=(inner_author.get("name") or outer_author.get("name") or outer_author.get("full_name") or "").strip(),
        author_email=(inner_author.get("email") or "").strip(),
        author_login=(outer_author.get("login") or outer_author.get("username") or "").strip(),
        url=(raw.get("html_url") or raw.get("url") or "").strip(),
        committed_at=committed_at,
        additions=_as_int(stats.get("additions")),
        deletions=_as_int(stats.get("deletions")),
        changed_files=_as_int(stats.get("total")) or len(files),
        files=list(files)[:50],
    )


async def _request(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
    """统一的请求入口，把网络异常转成可读的 PlatformError。"""
    try:
        response = await client.request(method, url, **kwargs)
    except httpx.TimeoutException as exc:
        raise PlatformError(f"连接 {url} 超时") from exc
    except httpx.ConnectError as exc:
        raise PlatformError(f"无法连接 {url}：{exc}") from exc
    except httpx.HTTPError as exc:
        raise PlatformError(f"请求 {url} 失败：{exc}") from exc
    return response


class PlatformClient:
    platform = ""
    default_base = ""

    def __init__(self, base_url: str, token: str, timeout: float = 30.0):
        self.base_url = (base_url or self.default_base).strip().rstrip("/")
        self.token = (token or "").strip()
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "worklog-reporter/1.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    async def whoami(self) -> str:
        raise NotImplementedError

    async def get_commit_diff(self, owner: str, repo: str, sha: str) -> str:
        raise NotImplementedError

    async def get_commit_files(self, owner: str, repo: str, sha: str) -> list[dict]:
        raise NotImplementedError

    async def get_file_contents(self, owner: str, repo: str, sha: str, files: list[dict]) -> str:
        """按提交时的版本读取文件内容，作为审查素材。"""
        blocks: list[str] = []
        for item in files[:MAX_REVIEW_FILES]:
            path = item.get("filename") or item.get("path") or ""
            if not path:
                continue
            content = await self._read_raw(owner, repo, sha, path)
            if content is None:
                continue
            if len(content) > MAX_REVIEW_FILE_BYTES:
                content = content[:MAX_REVIEW_FILE_BYTES] + "\n... (内容已截断)"
            blocks.append(f"----- {path} -----\n{content}")
        return "\n\n".join(blocks)

    async def _read_raw(self, owner: str, repo: str, sha: str, path: str) -> str | None:
        raise NotImplementedError

    async def create_issue(self, owner: str, repo: str, title: str, body: str) -> dict:
        raise NotImplementedError

    async def list_commits(
        self,
        owner: str,
        repo: str,
        since: datetime | None = None,
        until: datetime | None = None,
        max_pages: int = 20,
    ) -> list[FetchedCommit]:
        raise NotImplementedError


class GiteaClient(PlatformClient):
    platform = "gitea"
    default_base = GITEA_DEFAULT_BASE

    async def whoami(self) -> str:
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            resp = await _request(client, "GET", f"{self.base_url}/api/v1/user")
            if resp.status_code == 404:
                raise PlatformError(f"{self.base_url} 不是 Gitea 服务，请核对平台与服务地址")
            if resp.status_code in (401, 403):
                raise PlatformError("Gitea 鉴权失败：令牌无效或缺少读权限")
            if resp.status_code >= 400:
                raise PlatformError(f"Gitea 鉴权失败：HTTP {resp.status_code}")
            data = resp.json()
            return data.get("login") or data.get("full_name") or ""

    async def get_commit_diff(self, owner: str, repo: str, sha: str) -> str:
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/commits/{sha}.diff"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            resp = await _request(client, "GET", url)
            if resp.status_code < 400:
                return resp.text[:MAX_DIFF_CHARS]
        return ""

    async def get_commit_files(self, owner: str, repo: str, sha: str) -> list[dict]:
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/commits/{sha}"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            resp = await _request(client, "GET", url)
            if resp.status_code >= 400:
                return []
            data = resp.json()
        files = data.get("files") or []
        return [item for item in files if isinstance(item, dict)]

    async def _read_raw(self, owner: str, repo: str, sha: str, path: str) -> str | None:
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/raw/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            resp = await _request(client, "GET", url, params={"ref": sha})
            if resp.status_code >= 400:
                return None
            return resp.text

    async def create_issue(self, owner: str, repo: str, title: str, body: str) -> dict:
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/issues"
        payload = {"title": title, "body": body}
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            resp = await _request(client, "POST", url, json=payload)
            if resp.status_code >= 400:
                raise PlatformError(f"Gitea 创建 Issue 失败：HTTP {resp.status_code} {resp.text[:200]}")
            data = resp.json()
            return {
                "number": data.get("number"),
                "url": data.get("html_url") or "",
                "platform": "gitea",
            }

    async def list_commits(
        self,
        owner: str,
        repo: str,
        since: datetime | None = None,
        until: datetime | None = None,
        max_pages: int = 20,
    ) -> list[FetchedCommit]:
        collected: list[FetchedCommit] = []
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/commits"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            for page in range(1, max(1, max_pages) + 1):
                params: dict[str, object] = {"page": page, "limit": GITEA_PAGE_SIZE, "stat": "true", "files": "true"}
                if since:
                    params["since"] = since.isoformat()
                if until:
                    params["until"] = until.isoformat()
                resp = await _request(client, "GET", url, params=params)
                if resp.status_code == 404:
                    raise PlatformError(
                        f"{self.base_url} 上找不到该仓库：仓库名有误，或令牌无权访问"
                        f"（私有仓库无权限时 Gitea 同样返回 404）"
                    )
                if resp.status_code in (401, 403):
                    raise PlatformError("Gitea 鉴权失败：令牌无效或缺少读权限")
                if resp.status_code >= 400:
                    raise PlatformError(f"Gitea 拉取提交失败：HTTP {resp.status_code} {resp.text[:200]}")
                items = resp.json()
                if not isinstance(items, list) or not items:
                    break
                collected.extend(_parse_commit(item) for item in items if isinstance(item, dict))
                if len(items) < GITEA_PAGE_SIZE:
                    break
        return [c for c in collected if c.sha]


class GiteeClient(PlatformClient):
    platform = "gitee"
    default_base = GITEE_DEFAULT_BASE

    async def whoami(self) -> str:
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            resp = await _request(client, "GET", f"{self.base_url}/api/v5/user")
            if resp.status_code == 404:
                raise PlatformError(f"{self.base_url} 不是 Gitee 服务，请核对平台与服务地址")
            if resp.status_code in (401, 403):
                raise PlatformError("Gitee 鉴权失败：令牌无效或缺少读权限")
            if resp.status_code >= 400:
                raise PlatformError(f"Gitee 鉴权失败：HTTP {resp.status_code}")
            data = resp.json()
            return data.get("login") or data.get("name") or ""

    async def get_commit_diff(self, owner: str, repo: str, sha: str) -> str:
        url = f"{self.base_url}/api/v5/repos/{owner}/{repo}/commits/{sha}/diff"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            resp = await _request(client, "GET", url)
            if resp.status_code < 400:
                return resp.text[:MAX_DIFF_CHARS]
        return ""

    async def get_commit_files(self, owner: str, repo: str, sha: str) -> list[dict]:
        # Gitee 的提交详情里带 files 与每个文件的 patch
        url = f"{self.base_url}/api/v5/repos/{owner}/{repo}/commits/{sha}"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            resp = await _request(client, "GET", url)
            if resp.status_code >= 400:
                return []
            data = resp.json()
        files = data.get("files") or []
        return [item for item in files if isinstance(item, dict)]

    async def _read_raw(self, owner: str, repo: str, sha: str, path: str) -> str | None:
        url = f"{self.base_url}/api/v5/repos/{owner}/{repo}/raw/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            resp = await _request(client, "GET", url, params={"ref": sha})
            if resp.status_code >= 400:
                return None
            return resp.text

    async def create_issue(self, owner: str, repo: str, title: str, body: str) -> dict:
        url = f"{self.base_url}/api/v5/repos/{owner}/{repo}/issues"
        params = {"access_token": self.token} if self.token else {}
        payload = {"title": title, "body": body}
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            resp = await _request(client, "POST", url, params=params, json=payload)
            if resp.status_code >= 400:
                raise PlatformError(f"Gitee 创建 Issue 失败：HTTP {resp.status_code} {resp.text[:200]}")
            data = resp.json()
            return {
                "number": data.get("number"),
                "url": data.get("html_url") or "",
                "platform": "gitee",
            }

    async def list_commits(
        self,
        owner: str,
        repo: str,
        since: datetime | None = None,
        until: datetime | None = None,
        max_pages: int = 20,
    ) -> list[FetchedCommit]:
        collected: list[FetchedCommit] = []
        url = f"{self.base_url}/api/v5/repos/{owner}/{repo}/commits"
        async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as client:
            for page in range(1, max(1, max_pages) + 1):
                params: dict[str, object] = {"page": page, "per_page": GITEE_PAGE_SIZE}
                if since:
                    params["since"] = since.isoformat()
                if until:
                    params["until"] = until.isoformat()
                resp = await _request(client, "GET", url, params=params)
                if resp.status_code == 404:
                    raise PlatformError(
                        f"{self.base_url} 上没有该仓库或不是 Gitee 服务，请核对平台与服务地址"
                    )
                if resp.status_code in (401, 403):
                    raise PlatformError("Gitee 鉴权失败：令牌无效或缺少读权限")
                if resp.status_code >= 400:
                    raise PlatformError(f"Gitee 拉取提交失败：HTTP {resp.status_code} {resp.text[:200]}")
                items = resp.json()
                if not isinstance(items, list) or not items:
                    break
                collected.extend(_parse_commit(item) for item in items if isinstance(item, dict))
                if len(items) < GITEE_PAGE_SIZE:
                    break

            # 必须在 AsyncClient 关闭前补齐文件明细
            missing_files = [c for c in collected if not c.files][:MAX_FILE_COMMITS]
            for commit in missing_files:
                await self._attach_files(client, owner, repo, commit)
        return [c for c in collected if c.sha]

    async def _attach_files(self, client: httpx.AsyncClient, owner: str, repo: str, commit: FetchedCommit) -> None:
        url = f"{self.base_url}/api/v5/repos/{owner}/{repo}/commits/{commit.sha}"
        try:
            resp = await _request(client, "GET", url)
        except Exception:  # noqa: BLE001 - 文件明细缺失不影响主流程
            return
        if resp.status_code >= 400:
            return
        try:
            data = resp.json()
        except ValueError:
            return
        if not isinstance(data, dict):
            return
        files = [item for item in (data.get("files") or []) if isinstance(item, dict)]
        commit.files = files[:50]
        if not commit.changed_files:
            commit.changed_files = len(files)
        if not commit.additions:
            commit.additions = sum(_as_int(f.get("additions")) for f in files)
        if not commit.deletions:
            commit.deletions = sum(_as_int(f.get("deletions")) for f in files)


async def detect_platform(base_url: str, timeout: float = 10.0) -> str:
    """探测服务地址对应的平台，确认是 Gitea 返回 gitea，无法识别返回空串。"""
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return ""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await _request(client, "GET", f"{base}/api/v1/version")
            if resp.status_code < 400:
                return "gitea"
    except PlatformError:
        return ""
    return ""


def build_client(platform: str, base_url: str, token: str, timeout: float = 30.0) -> PlatformClient:
    kind = (platform or "").strip().lower()
    if kind == "gitea":
        return GiteaClient(base_url, token, timeout)
    if kind == "gitee":
        return GiteeClient(base_url, token, timeout)
    raise PlatformError(f"不支持的平台：{platform}")