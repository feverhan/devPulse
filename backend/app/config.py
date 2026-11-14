from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Environment variables override file values."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "研发脉冲"
    app_timezone: str = "Asia/Shanghai"
    data_dir: str = "./data"

    database_url: str = ""

    app_secret: str = ""
    app_password: str = ""
    cors_origins: str = "*"

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_temperature: float = 0.3

    auto_init: bool = True
    sync_interval_minutes: int = 30
    sync_on_start: bool = False
    fetch_commit_files: bool = True
    max_pages_per_sync: int = 20
    request_timeout: float = 30.0

    @property
    def data_path(self) -> Path:
        path = Path(self.data_dir).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_source(self) -> str:
        """当前数据库地址的来源：file / env / default。

        file 表示在界面或命令行里显式选定过，优先级高于环境变量。
        """
        if self.database_file.exists() and self.database_file.read_text(encoding="utf-8").strip():
            return "file"
        if (self.database_url or "").strip():
            return "env"
        return "default"

    @property
    def database_file(self) -> Path:
        return self.data_path / "database.url"

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_file.exists():
            saved = self.database_file.read_text(encoding="utf-8").strip()
            if saved:
                return saved
        explicit = (self.database_url or "").strip()
        if explicit:
            return explicit
        return f"sqlite:///{(self.data_path / 'worklog.db').as_posix()}"

    @property
    def is_sqlite(self) -> bool:
        return self.sqlalchemy_url.startswith("sqlite")

    @property
    def cors_origin_list(self) -> list[str]:
        raw = (self.cors_origins or "*").strip()
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()