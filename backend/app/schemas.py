from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["gitea", "gitee"]
PeriodType = Literal["weekly", "monthly", "quarterly", "yearly", "custom"]


class RepoBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    project: str = ""
    platform: Platform = "gitea"
    owner: str = ""
    repo: str = ""
    base_url: str = ""
    # 仓库地址，粘贴后由服务端解析出平台、拥有者、仓库名与服务地址
    repo_url: str = ""
    token: str = ""
    enabled: bool = True
    include_keywords: str = ""
    exclude_keywords: str = ""


class RepoParseIn(BaseModel):
    url: str = ""
    token: str = ""


class RepoCreate(RepoBase):
    pass


class RepoUpdate(BaseModel):
    name: str | None = None
    project: str | None = None
    platform: Platform | None = None
    owner: str | None = None
    repo: str | None = None
    base_url: str | None = None
    # 传空串表示不修改令牌；需要清空时使用 clear_token
    token: str | None = None
    clear_token: bool = False
    enabled: bool | None = None
    include_keywords: str | None = None
    exclude_keywords: str | None = None


class RepoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    project: str
    platform: str
    owner: str
    repo: str
    base_url: str
    token_set: bool = False
    enabled: bool
    include_keywords: str
    exclude_keywords: str
    last_sync_at: datetime | None = None
    last_sync_status: str
    last_sync_message: str
    created_at: datetime


class CommitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repo_id: int
    repo_name: str = ""
    sha: str
    short_sha: str
    message: str
    author_name: str
    author_email: str
    author_login: str
    url: str
    additions: int
    deletions: int
    changed_files: int
    committed_at: datetime


class WorkEntryBase(BaseModel):
    work_date: date
    title: str = Field(min_length=1, max_length=200)
    content: str = ""
    category: str = "研发"
    project: str = Field(min_length=1, max_length=120)
    tags: str = ""
    hours: float | None = None


class WorkEntryCreate(WorkEntryBase):
    pass


class WorkEntryUpdate(BaseModel):
    work_date: date | None = None
    title: str | None = None
    content: str | None = None
    category: str | None = None
    project: str | None = Field(default=None, min_length=1, max_length=120)
    tags: str | None = None
    hours: float | None = None


class WorkEntryOut(WorkEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ReportGenerate(BaseModel):
    period_type: PeriodType = "weekly"
    start_date: date | None = None
    end_date: date | None = None
    reference_date: date | None = None
    title: str = ""
    focus: str = ""
    include_commits: bool = True
    include_works: bool = True
    use_llm: bool = True


class ReportUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    status: str | None = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    period_type: str
    start_date: date
    end_date: date
    summary: str
    content: str
    stats: dict[str, Any] | None = None
    model: str
    status: str
    stage: str = ""
    progress: int = 0
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class LLMConfigIn(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.3


class LLMConfigOut(BaseModel):
    base_url: str
    api_key_set: bool = False
    model: str
    temperature: float


class AppSettingsOut(BaseModel):
    llm: LLMConfigOut
    sync_interval_minutes: int
    fetch_commit_files: bool
    max_pages_per_sync: int
    my_authors: list[str] = []
    wechat_webhook: str = ""
    app_password_set: bool = False


class AppSettingsIn(BaseModel):
    llm: LLMConfigIn | None = None
    sync_interval_minutes: int | None = None
    fetch_commit_files: bool | None = None
    max_pages_per_sync: int | None = None
    my_authors: list[str] | None = None
    wechat_webhook: str | None = None
    app_password: str | None = None