from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# 新增列的显式定义：列名 -> DDL 片段
COLUMN_MIGRATIONS: dict[str, dict[str, str]] = {
    "repos": {
        "project": "VARCHAR(120) NOT NULL DEFAULT ''",
    },
    "code_reviews": {
        "task_id": "INT NULL",
    },
    "reports": {
        "stage": "VARCHAR(120) NOT NULL DEFAULT ''",
        "progress": "INT NOT NULL DEFAULT 0",
        "error": "TEXT NULL",
    },
}

# 需要在补列后执行的回填语句
BACKFILL: dict[str, list[str]] = {
    "repos": ["UPDATE repos SET project = name WHERE project = ''"],
}


def ensure_schema(engine: Engine) -> list[str]:
    """为已建好的库补齐新增字段。create_all 只会建新表，不会改已有表。"""
    applied: list[str] = []
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    for table_name, columns in COLUMN_MIGRATIONS.items():
        if table_name not in tables:
            continue
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, ddl in columns.items():
            if column_name in actual:
                continue
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
            applied.append(f"{table_name}.{column_name}")

    for table_name, statements in BACKFILL.items():
        if not any(item.startswith(f"{table_name}.") for item in applied):
            continue
        for statement in statements:
            with engine.begin() as conn:
                conn.execute(text(statement))

    # 外键约束单独补，MySQL 不支持 ADD COLUMN 同时带外键
    if "code_reviews.task_id" in applied and "review_tasks" in tables:
        with engine.begin() as conn:
            exists = conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS "
                    "WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'code_reviews' "
                    "AND CONSTRAINT_NAME = 'fk_code_reviews_task'"
                )
            ).scalar()
            if not exists:
                conn.execute(
                    text(
                        "ALTER TABLE code_reviews ADD CONSTRAINT fk_code_reviews_task "
                        "FOREIGN KEY (task_id) REFERENCES review_tasks(id) ON DELETE CASCADE"
                    )
                )
                applied.append("code_reviews.fk_task")

    return applied