from __future__ import annotations

from datetime import date

from app.services.report import (
    build_summary,
    clean_subject,
    cn_number,
    compute_stats,
    default_title,
    fallback_markdown,
    group_by_project,
    project_items,
    resolve_period,
)


def test_weekly_period_covers_monday_to_sunday():
    start, end = resolve_period("weekly", reference_date=date(2026, 11, 13))
    assert start == date(2026, 11, 9)
    assert end == date(2026, 11, 15)


def test_monthly_period_covers_full_month():
    start, end = resolve_period("monthly", reference_date=date(2026, 11, 13))
    assert start == date(2026, 11, 1)
    assert end == date(2026, 11, 30)


def test_quarterly_period_covers_quarter():
    start, end = resolve_period("quarterly", reference_date=date(2026, 11, 13))
    assert start == date(2026, 10, 1)
    assert end == date(2026, 12, 31)


def test_yearly_period_covers_year():
    start, end = resolve_period("yearly", reference_date=date(2026, 11, 13))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 12, 31)


def test_custom_period_swaps_reversed_dates():
    start, end = resolve_period("custom", start_date=date(2026, 3, 10), end_date=date(2026, 3, 1))
    assert start == date(2026, 3, 1)
    assert end == date(2026, 3, 10)


def test_default_title_for_year():
    start, end = resolve_period("yearly", reference_date=date(2026, 11, 13))
    assert default_title("yearly", start, end) == "2026 年度报告"


def test_compute_stats_aggregates_by_repo_and_category():
    source = {
        "commits": [
            {"repo": "A", "project": "项目一", "item": "提交一", "additions": 10, "deletions": 2, "changed_files": 1, "date": "2026-11-01"},
            {"repo": "A", "project": "项目一", "item": "提交二", "additions": 5, "deletions": 1, "changed_files": 2, "date": "2026-11-02"},
            {"repo": "B", "project": "项目二", "item": "提交三", "additions": 3, "deletions": 0, "changed_files": 1, "date": "2026-11-02"},
        ],
        "works": [
            {"project": "项目一", "title": "记录一", "category": "研发", "hours": 4, "date": "2026-11-02"},
            {"project": "项目一", "title": "记录二", "category": "研发", "hours": 2, "date": "2026-11-02"},
            {"project": "项目二", "title": "记录三", "category": "测试", "hours": 1, "date": "2026-11-02"},
        ],
    }
    stats = compute_stats(source)
    assert stats["commit_count"] == 3
    assert stats["additions"] == 18
    assert stats["deletions"] == 3
    assert stats["changed_files"] == 4
    assert stats["repo_count"] == 2
    assert stats["work_count"] == 3
    assert stats["hours"] == 7
    assert stats["by_repo"][0]["name"] == "A"
    assert stats["by_repo"][0]["count"] == 2
    assert stats["by_category"][0] == {"name": "研发", "count": 2}
    assert stats["active_days"] == 2


def test_cn_number():
    assert cn_number(1) == "一"
    assert cn_number(3) == "三"
    assert cn_number(10) == "十"
    assert cn_number(11) == "十一"
    assert cn_number(20) == "二十"
    assert cn_number(21) == "二十一"


def test_clean_subject_strips_conventional_prefix():
    assert clean_subject("feat(report): 支持周报汇总") == "支持周报汇总"
    assert clean_subject("fix(sync): 修复分页问题\n\n详细说明") == "修复分页问题"
    assert clean_subject("普通提交说明") == "普通提交说明"


def test_group_by_project_merges_repos_and_works():
    source = {
        "commits": [
            {"repo": "A", "project": "项目一", "item": "提交事项一", "date": "2026-11-10"},
            {"repo": "B", "project": "项目一", "item": "提交事项二", "date": "2026-11-09"},
            {"repo": "C", "project": "项目二", "item": "提交事项三", "date": "2026-11-08"},
        ],
        "works": [
            {"project": "项目一", "title": "工作事项一", "date": "2026-11-11", "content": "", "category": "研发", "hours": 2},
        ],
    }
    groups = group_by_project(source)
    assert [g["name"] for g in groups] == ["项目一", "项目二"]
    assert len(groups[0]["works"]) == 1
    assert len(groups[0]["commits"]) == 2

    items = project_items(groups[0])
    assert items[0] == "工作事项一"
    assert "提交事项一" in items


def test_fallback_markdown_uses_project_numbering():
    groups = [
        {
            "name": "集团访客系统",
            "works": [{"project": "集团访客系统", "title": "企业微信界面调整", "date": "2026-11-10", "content": "", "category": "", "hours": None}],
            "commits": [],
        },
        {
            "name": "南通海事短临预警系统",
            "works": [
                {"project": "南通海事短临预警系统", "title": "短临预警系统MCP服务开发", "date": "2026-11-11", "content": "", "category": "", "hours": None},
                {"project": "南通海事短临预警系统", "title": "风电场模块打卡业务调整", "date": "2026-11-11", "content": "", "category": "", "hours": None},
            ],
            "commits": [],
        },
    ]
    content = fallback_markdown(groups)
    assert content.startswith("一、集团访客系统")
    assert "1.企业微信界面调整" in content
    assert "二、南通海事短临预警系统" in content
    assert "1.短临预警系统MCP服务开发" in content
    assert "2.风电场模块打卡业务调整" in content
    assert "##" not in content
    assert "数据概览" not in content


def test_build_summary_lists_projects():
    groups = [
        {"name": "项目甲", "works": [], "commits": [{"item": "做了一件事"}]},
        {"name": "项目乙", "works": [], "commits": [{"item": "做了另一件事"}]},
    ]
    assert build_summary(groups) == "涉及 2 个项目：项目甲、项目乙"


def _wait_report(client, report_id: int, timeout: float = 20.0) -> dict:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/reports/{report_id}").json()
        if body["status"] in ("published", "failed"):
            return body
        time.sleep(0.1)
    raise AssertionError("\u62a5\u544a\u751f\u6210\u8d85\u65f6")


def test_generate_returns_immediately_with_generating_status(client):
    """\u751f\u6210\u662f\u540e\u53f0\u4efb\u52a1\uff0c\u63a5\u53e3\u7acb\u523b\u8fd4\u56de\uff0c\u4e0d\u963b\u585e\u5728\u6a21\u578b\u8c03\u7528\u4e0a\u3002"""
    resp = client.post(
        "/api/reports/generate",
        json={"period_type": "weekly", "reference_date": "2026-11-13", "use_llm": False},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "generating"
    assert data["stage"]
    assert data["progress"] < 100


def test_background_task_fills_report_content(client):
    resp = client.post(
        "/api/reports/generate",
        json={"period_type": "weekly", "reference_date": "2026-11-13", "use_llm": False},
    )
    report_id = resp.json()["id"]
    body = _wait_report(client, report_id)
    assert body["status"] == "published"
    assert body["progress"] == 100
    assert body["stage"] == "\u5b8c\u6210"
    assert body["model"] == "\u672c\u5730\u6a21\u677f"


def test_stream_endpoint_sends_final_state(client):
    import json

    resp = client.post(
        "/api/reports/generate",
        json={"period_type": "weekly", "reference_date": "2026-11-13", "use_llm": False},
    )
    report_id = resp.json()["id"]
    _wait_report(client, report_id)

    events: list[dict] = []
    with client.stream("GET", f"/api/reports/{report_id}/stream") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:") :]))

    assert events
    last = events[-1]
    assert last["status"] == "published"
    assert last["progress"] == 100


def _make_generating_report(db, title: str = "卡住的报告") -> int:
    from app.models import Report

    report = Report(
        title=title,
        period_type="weekly",
        start_date=date(2026, 11, 9),
        end_date=date(2026, 11, 15),
        status="generating",
        stage="排队中",
        progress=5,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report.id


def test_reset_stale_reports_marks_generating_as_failed():
    """服务重启后不能让报告一直挂在「生成中」。"""
    from app.database import SessionLocal
    from app.models import Report
    from app.services.report import reset_stale_reports

    db = SessionLocal()
    try:
        report_id = _make_generating_report(db)
        assert reset_stale_reports() >= 1
        db.expire_all()
        row = db.get(Report, report_id)
        assert row.status == "failed"
        assert row.stage == "生成中断"
    finally:
        db.query(Report).filter(Report.id == report_id).delete()
        db.commit()
        db.close()


def test_sweep_stale_reports_only_kills_old_tasks():
    from datetime import timedelta

    from app.database import SessionLocal
    from app.models import Report
    from app.services.report import sweep_stale_reports
    from app.timeutil import now_local

    db = SessionLocal()
    try:
        fresh_id = _make_generating_report(db, "刚开始的报告")
        old_id = _make_generating_report(db, "卡住很久的报告")
        old = db.get(Report, old_id)
        old.updated_at = now_local() - timedelta(minutes=45)
        db.commit()

        sweep_stale_reports(minutes=30)

        db.expire_all()
        assert db.get(Report, old_id).status == "failed"
        assert db.get(Report, old_id).stage == "生成超时"
        assert db.get(Report, fresh_id).status == "generating"
    finally:
        db.query(Report).filter(Report.id.in_([fresh_id, old_id])).delete()
        db.commit()
        db.close()
