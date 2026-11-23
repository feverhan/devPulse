# 05 API 接口清单

全部接口挂在 `/api` 下；除 `auth` 与 `/api/health` 外都需要会话（未设置访问密码时放行）。出入参见 `backend/app/schemas.py`，交互细节可直接看各 router 文件。

## auth（`/api/auth`，免登录）
- `POST /login` 登录（设置过密码时）
- `POST /logout` 退出
- `GET /me` 当前会话状态（是否需要密码、是否已登录）

## setup（`/api/setup`，初始化与数据）
- `GET /status` 初始化状态（三步是否完成）
- `POST /database` 试连并切换数据库
- `POST /llm` 保存并试连大模型配置
- `POST /password` 设置/修改访问密码
- `POST /migrate` 数据迁移（先试连后复制）
- `POST /export` 导出 JSON 备份；`GET /export` 下载备份文件
- `POST /import` 导入 JSON 备份（自带主密钥）
- `POST /reset-database-source`、`POST /complete`、`POST /reset` 向导流转

## repos（`/api/repos`）
- `GET /`、`POST /`、`PUT /{repo_id}`、`DELETE /{repo_id}` 仓库 CRUD
- `POST /parse` 解析仓库地址
- `POST /probe` 探测平台连通性（建仓前填地址时用）
- `POST /{repo_id}/test` 校验令牌
- `POST /sync` 全部仓库同步；`POST /{repo_id}/sync` 单仓库同步

## commits（`/api/commits`）
- `GET /` 提交列表（筛选、分页）
- `GET /authors` 作者候选（用于作者标识选择）

## projects（`/api/projects`）
- `GET /`、`POST /`、`DELETE /{project_id}`

## works（`/api/works`）
- `GET /`、`POST /`、`PUT /{work_id}`、`DELETE /{work_id}`

## reports（`/api/reports`）
- `GET /` 列表；`GET /{report_id}` 详情；`PUT /{report_id}` 改标题/正文；`DELETE /{report_id}`
- `POST /generate` 创建生成任务（202，后台执行）
- `GET /{report_id}/stream` SSE：阶段、进度、正文实时回显

## reviews（`/api/reviews`）
- `POST /tasks` 创建审查任务；`GET /tasks` 任务列表；`GET /tasks/{task_id}` 任务进度
- `POST /tasks/{task_id}/cancel` 取消任务
- `GET /` 审查结果列表；`GET /{review_id}` 单提交详情
- `POST /{review_id}/issues` 推送该提交的问题为 Issue
- `POST /findings/{finding_id}/ignore` 忽略单条问题
- `DELETE /{review_id}` 删除审查记录

## monitors（`/api/monitors`）
- `GET /`、`POST /`、`PUT /{monitor_id}`、`DELETE /{monitor_id}`
- `GET /overview` 汇总状态
- `POST /probe` 地址自动探测健康路径
- `POST /{monitor_id}/check` 立即检查一次；`POST /{monitor_id}/run` 启停巡检
- `GET /{monitor_id}/checks` 检查流水

## dashboard（`/api/dashboard`）
- `GET /overview` 概览统计

## settings（`/api/settings`）
- `GET /` 读配置；`PUT /` 写配置；`POST /llm/test` 大模型连通性测试