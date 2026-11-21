# 研发脉冲 · Dev Pulse

面向研发的个人工作台：汇总 Gitea / Gitee 提交与手工工作记录，一键产出周报、月报、季报、年报；对提交做代码质量审查并推送 Issue；对内部服务定期探活，异常时经企业微信告警。

默认本地 SQLite，开箱即用；报告与审查接 OpenAI 兼容大模型（vLLM / Ollama / LM Studio 等均可），未配置时自动回退本地模板。

## 下载与启动

到 [Releases](https://github.com/feverhan/devPulse/releases) 下载 `devpulse-standalone-v1.0.0.zip`，解压后：

1. 双击 `devpulse.exe`，弹出图形启动器
2. 首次使用可修改端口和数据目录，点「启动」
3. 点「打开页面」，浏览器进入初始化向导

关闭启动器窗口或点「停止」即结束服务。没有图形界面的场景（服务器、脚本）用 `devpulse-cli.exe`：

```bash
devpulse-cli.exe --port 8000 --data-dir D:\devpulse\data --no-browser
```

| 参数 | 说明 |
| --- | --- |
| `-p, --port` | 监听端口，默认 8000；被占用自动顺延 8001、8002…（最多 50 个） |
| `--strict-port` | 端口被占用时直接退出，不自动顺延 |
| `-d, --data-dir` | 数据目录，默认系统用户数据目录（`%LOCALAPPDATA%\devpulse`） |
| `--portable` | 数据放在 exe 同级的 `data`，方便整个目录拷贝迁移 |
| `--host` | 监听地址，默认 `0.0.0.0` |
| `--database-url` | 指定 MySQL 等外部数据库，留空用本地 SQLite |
| `--no-browser` | 启动后不自动打开浏览器 |

数据目录里存放 `worklog.db`（SQLite）、`secret.key`（主密钥）、`database.url`（手动切换过数据库时存在）、`runtime.json`（实际端口）。

## 初始化向导

浏览器打开后进入三步初始化，可跳过随时在「设置」里补：

| 步骤 | 内容 |
| --- | --- |
| 数据库 | 默认本地 SQLite；可当场切换 MySQL（先试连再切换，失败不动原库） |
| 大模型 | 填接口地址、令牌、模型名，先测试连通再落库 |
| 访问密码 | 设置后立即下发会话，不会打断后续步骤 |

### 连接 MySQL

初始化向导或「设置 → 数据」里填连接串即可，运行时生效，无需重启：

```
mysql+pymysql://user:password@host:3306/daylife?charset=utf8mb4
```

启动前也可指定：

```bash
devpulse-cli.exe --database-url 'mysql+pymysql://user:password@host:3306/daylife?charset=utf8mb4'
```

### 数据迁移与备份

「设置 → 数据」支持导出 JSON 备份 / 导入 JSON / 把数据迁移到 SQLite。迁移复制全部业务表（仓库、提交、工作记录、项目、报告、审查记录、服务监控、运行配置），先试连两端，通了才复制，失败不动原库。

换机器两种方式：

- 整个数据目录一起拷（`--portable` 时数据就在程序同级）
- 导出 JSON → 新机器导入；导出文件自带主密钥，令牌不需要重新配置

## 日常使用

### 仓库接入

「仓库」页直接粘贴仓库地址（`https://` / `git@` 均可），平台、拥有者、仓库名与服务地址自动填好。

访问令牌：Gitea 在「设置 → 应用 → 生成令牌」勾选 `read:repository`；Gitee 在「设置 → 私人令牌」勾选 `projects` 读权限。自建 Gitea 填实例根地址如 `https://git.corp.cn`。

可设置「包含关键字」「排除关键字」按提交说明过滤。

### 提交同步

手动点「同步」之外，调度器按间隔自动同步；分页拉取提交与变更明细，自动去重。

**只汇总自己的提交**：「设置 → 同步 → 我的作者标识」填姓名 / 登录名 / 邮箱（逗号分隔），同步时跳过他人提交，再次同步会清理此前已入库的他人提交。`Merge` / `Revert` 开头的提交默认不计入统计。

### 工作记录

手工登记工作内容、类别与工时，项目必填：可从已同步提交所属的项目中选择，也可自行输入。

### 报告生成

支持周报 / 月报 / 季报 / 年报 / 自定义区间。生成是后台任务，页面通过 SSE 实时显示进度与正文。正文按项目分组、编号列事项：

```markdown
一、集团访客系统

1.企业微信界面调整，默认发起时间各端统一

二、南通海事短临预警系统

1.短临预警系统MCP服务开发
```

大模型在「设置 → 大模型」配置，地址未带 `/v1` 会自动补全；未配置或调用失败时自动回退本地模板。

### 代码审查

「代码审查」页选仓库创建任务，后台逐提交分析（Gitea 取 `.diff`，Gitee 取 `patch`），只保留客观缺陷（逻辑错误、异常未处理、资源泄漏、并发、安全、性能），风格建议排除。问题可单条或批量推送为仓库 Issue。单个提交通常 1-3 分钟。

### 服务监控

登记需要保活的服务，系统按各自周期自动探活，状态变化时推送企业微信：

- 「新建监控」填地址后点「自动探测」，并发试探 20 多个常见健康检查路径，大模型读取首页推测该技术栈可能用的路径
- 可设期望状态码与响应关键词
- 首次检查不告警，此后状态跃迁才推送（正常→异常报障，异常→正常报恢复）
- 企微 webhook 在「设置 → 告警」填写

## 容器部署

**Docker Compose（连接已有 MySQL）**：

```bash
cp .env.example .env   # 填 APP_DATABASE_URL
docker compose up -d --build
```

**Podman（默认 SQLite）**：

```bash
podman-compose -f docker-compose.yml -f docker-compose.podman.yml up -d --build
```

**自带 MySQL 的独立部署**：

```bash
docker compose -f docker-compose.mysql.yml up -d --build
```

单容器快速启动：

```bash
docker run -d -p 8000:8000 -v devpulse-data:/app/data worklog-reporter:1.0.0
```

> Windows 绑定挂载目录上 SQLite WAL 可能创建失败，容器部署用命名卷 `-v devpulse-data:/app/data`，不要用 `-v ./data:/app/data`。

## 配置项

程序同级 `.env` 文件生效，以下为主要变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | — | 数据库连接串；留空则用数据目录下的 SQLite |
| `DATA_DIR` | ./data | 数据目录 |
| `APP_SECRET` | — | 主密钥；留空自动生成到 `DATA_DIR/secret.key` |
| `APP_PASSWORD` | — | 访问密码；也可在界面「设置」里改 |
| `LLM_BASE_URL` | — | 大模型接口地址，OpenAI 兼容格式 |
| `LLM_API_KEY` | — | 大模型访问令牌 |
| `LLM_MODEL` | — | 模型名称 |
| `SYNC_INTERVAL_MINUTES` | 30 | 定时同步间隔（分钟） |
| `APP_TIMEZONE` | Asia/Shanghai | 业务时区，决定日期归属与统计口径 |

完整列表见 [docs/deploy.md](docs/deploy.md)。

## 常见问题

**8000 端口被占用？**
自动顺延到下一个可用端口，界面/横幅显示实际地址。想固定端口加 `--port`，不想顺延加 `--strict-port`。

**容器里 SQLite 偶发 500？**
Windows 绑定挂载目录时 WAL 共享内存文件可能创建失败，改用命名卷。

**同步到的提交里有别人的？**
「设置 → 同步 → 我的作者标识」填自己的姓名 / 登录名 / 邮箱，再次同步自动清理。

**换个机器令牌解不开了？**
令牌按主密钥加密。保留原实例数据目录（`secret.key` 随目录走），或用导出 JSON 导入（自带主密钥）。

**Podman 容器访问不了内网 Gitea？**
默认网桥与内网网段重叠时补路由：`scripts/podman_lan_route.ps1 -Cidr <内网网段>`。开机自启脚本自动补。

---

## 开发者

```bash
# 后端
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload --port 8000

# 前端
cd frontend && npm install && npm run dev

# 测试
cd backend && python -m pytest

# 打包免安装程序
pwsh -File .\scripts\standalone\build.ps1
```

部署细节、完整配置项与 API 列表见 [docs/deploy.md](docs/deploy.md)。
