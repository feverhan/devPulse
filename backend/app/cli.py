"""命令行工具。

用法：
    python -m app.cli status                          查看当前数据库与初始化状态
    python -m app.cli init                            建表并写入默认配置
    python -m app.cli init --database-url ...          切换到指定数据库后再初始化
    python -m app.cli export --output backup.json     导出全部数据
    python -m app.cli import --input backup.json      从导出文件恢复数据
    python -m app.cli migrate --to-url ...            把数据迁移到另一个库（留空则本地 SQLite）
"""

from __future__ import annotations

import argparse
import sys

from .config import settings


def _report() -> None:
    from .database import SessionLocal, describe_database, init_schema
    from .services.config_store import ensure_defaults, get_llm_config, is_initialized

    init_schema()
    db = SessionLocal()
    try:
        ensure_defaults(db)
        info = describe_database()
        llm = get_llm_config(db)
        print(f"应用名称   {settings.app_name}")
        print(f"数据库     {info['driver']} · {info['target']}（来源 {info['source']}）")
        print(f"数据目录   {settings.data_path}")
        print(f"已初始化   {'是' if is_initialized(db) else '否'}")
        print(f"大模型     {llm.model if llm.ready else '未配置'}")
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli", description="研发脉冲命令行工具")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="查看状态")

    init_parser = sub.add_parser("init", help="初始化数据库与默认配置")
    init_parser.add_argument("--database-url", default="", help="指定数据库地址，留空用当前配置")

    export_parser = sub.add_parser("export", help="导出全部数据")
    export_parser.add_argument("--output", default="worklog-export.json")
    export_parser.add_argument("--from-url", default="", help="源库地址，留空用当前配置")

    import_parser = sub.add_parser("import", help="从导出文件恢复数据")
    import_parser.add_argument("--input", required=True)
    import_parser.add_argument("--to-url", default="", help="目标库地址，留空用当前配置")

    migrate_parser = sub.add_parser("migrate", help="把数据迁移到另一个库")
    migrate_parser.add_argument("--from-url", default="", help="源库地址，留空用当前配置")
    migrate_parser.add_argument("--to-url", default="", help="目标库地址，留空则本地 SQLite")

    args = parser.parse_args(argv)

    if args.command == "status":
        _report()
        return 0

    if args.command == "init":
        if args.database_url:
            from .database import switch_database, test_connection

            ok, reason = test_connection(args.database_url)
            if not ok:
                print(f"无法连接数据库：{reason}", file=sys.stderr)
                return 1
            switch_database(args.database_url)
            print(f"数据库已切换到 {args.database_url}")
        _report()
        return 0

    if args.command == "export":
        from .services.migrate import export_data, write_export_file

        payload = export_data(args.from_url)
        path = write_export_file(args.output, payload)
        total = sum(len(v) for v in payload.values() if isinstance(v, list))
        print(f"已导出 {total} 条记录到 {path}")
        return 0

    if args.command == "import":
        from .services.migrate import import_data, read_export_file

        payload = read_export_file(args.input)
        counts = import_data(payload, args.to_url)
        print("导入完成：" + ", ".join(f"{k}={v}" for k, v in counts.items()))
        return 0

    if args.command == "migrate":
        from .services.migrate import copy_database, target_sqlite_url

        source = args.from_url or settings.sqlalchemy_url
        target = args.to_url or target_sqlite_url()
        counts = copy_database(source, target)
        print(f"迁移完成 {source} -> {target}")
        print(", ".join(f"{k}={v}" for k, v in counts.items()))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())