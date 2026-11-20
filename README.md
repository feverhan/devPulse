# 研发脉冲 · Dev Pulse

面向研发的个人工作台：汇总 Gitea / Gitee 提交与手工工作记录，产出周报、月报、季报、年报；
对提交做代码质量检查并推送 Issue；对内部服务定期探活，异常时经企业微信告警。

内置定时同步，报告与审查接本地部署的 OpenAI 兼容大模型，默认 SQLite，开箱即用。

## 安装方式一览

| 方式 | 适合场景 | 机器依赖 |
| --- | --- | --- |
| [免安装单文件](#快速开始免安装单文件)（推荐） | 个人电脑、临时机器 | 无，解压双击即用 |
| [离线安装包](#一键安装脚本与离线安装包) | 服务器、无外网环境 | podman 或 docker |
| [容器在线安装](#一键安装脚本与离线安装包) | 有容器引擎的环境 | podman 或 docker |
| [源码开发](#本地开发) | 二次开发 | Python 3.12 + Node.js |

## 快速开始（免安装单文件）

产物是 `dist/devpulse-standalone.zip`（打包方法见[打包](#打包)），已内置 Python 运行时、
后端、依赖与前端静态资源，目标机器**什么都不用装**：

1. 解压 `devpulse-standalone.zip` 到任意目录
2. 双击 `devpulse.exe`（Linux/macOS 运行 `./devpulse`）
3. 启动完成自动打开浏览器；首次访问进入初始化向导

首次启动自动完成：建库（本地 SQLite）→ 建表与补齐字段 → 写入默认配置 → 生成加密主密钥 → 拉起调度器。

控制台会打印实际访问地址与数据目录：

```text
  研发脉冲 · Dev Pulse
  访问地址   http://127.0.0.1:8000
  数据目录   C:\Users\<你>\AppData\Local\devpulse
  停止服务   Ctrl + C
```

### 端口与多实例

- 默认端口 8000；被其他程序占用时自动顺延 8001、8002……（最多顺延 50 个），实际地址以控制台横幅为准
- 8000 上跑的已经是本应用（重复双击）→ 直接打开已有实例的地址后退出，不会起两个
- 想固定端口：`devpulse --port 9000`；占用就报错退出再加 `--strict-port`
- 实际监听端口记录在数据目录的 `runtime.json`

### 数据目录

默认放在系统用户数据目录（Windows 为 `%LOCALAPPDATA%\devpulse`，Linux/macOS 为
`~/.local/share/devpulse`），换机器或重装不影响数据，也不会因为重新打包而丢失。
`worklog.db`（SQLite）、`secret.key`（主密钥）、`database.url`（手动切换过数据库时存在）、
`runtime.json` 都在这里。

想整个目录随程序走：`devpulse --portable`，数据就放在 exe 同级的 `data`，方便拷贝迁移。

### 常用参数

```bash
devpulse --port 8000 --data-dir /opt/devpulse/data
```

| 参数 | 说明 |
| --- | --- |
| `-p, --port` | 监听端口，默认 8000；被占用时自动顺延 |
| `--strict-port` | 端口被占用时直接退出，不自动顺延 |
| `-d, --data-dir` | 数据目录，默认系统用户数据目录 |
| `--portable` | 数据放在程序同级的 `data` |
| `--host` | 监听地址，默认 `0.0.0.0` |
| `--database-url` | 指定数据库，留空则用本地 SQLite |
| `--no-browser` | 启动后不自动打开浏览器 |

程序同级的 `.env` 也会被读取（只认程序同级的，不误读启动目录里的其它配置文件），
可配置数据库、大模型与访问密码，见[配置项](#配置项)。

## 首次配置（初始化向导）

浏览器打开后进入初始化向导，四步完成：

| 步骤 | 内容 |
| --- | --- |
| 数据库 | 默认本地 SQLite，开箱即用；可当场切成 MySQL（先试连再切换，失败不动原库） |
| 大模型 | 填接口地址、令牌、模型名，先测试连通再落库，失败不写半成品配置 |
| 访问密码 | 设置后立即下发会话，后续步骤不会被打断 |
| 代码仓库 | 初始化后在工作台添加 |

也可以跳过向导直接进工作台，之后随时在「设置」里补。

### 连接 MySQL

两种方式任选：

```bash
# 方式一：启动前用环境变量 / 参数指定
devpulse --database-url 'mysql+pymysql://user:pwd@host:3306/daylife?charset=utf8mb4'

# 方式二：初始化向导或「设置 → 数据」里切换，运行时生效，无需重启
```

### 数据迁移与导入导出

不想重新配置时，把现有库的数据整体搬过来即可，不必手工重填：

- 「设置 → 数据」：导出 JSON 备份、导入 JSON、把数据迁移到 SQLite
- 初始化向导的「数据库」步骤也有「把数据迁移到 SQLite」入口：先试连两端，通了才复制，失败不动原库
- 迁移复制全部业务表：仓库、提交、工作记录、项目、报告、审查记录与问题、服务监控与巡检、运行配置
- 迁移完成后地址写入数据目录的 `database.url`，优先级高于环境变量，重启后依然生效；
  删除该文件或在向导里点「改回环境变量配置」即恢复

换机器迁移两种方式：

- 整个数据目录一起拷过去（`--portable` 时数据就在程序同级）
- 在「设置 → 数据」导出 JSON，到新机器导入；导出文件带上主密钥，导入后仓库令牌与大模型密钥不需要重新配置

命令行同样可用（单文件环境直接在本机跑 `app.cli`，容器环境见下节）：

```bash
python -m app.cli export --output backup.json   # 导出全部数据
python -m app.cli import --input backup.json    # 从导出文件恢复
python -m app.cli migrate --to-url ''           # 库间迁移，留空则目标为本地 SQLite
python -m app.cli status                        # 查看当前数据库与初始化状态
```

> 仓库令牌与大模型密钥按 `APP_SECRET` 派生的密钥加密存储。换库或换机器时保持 `APP_SECRET`
> 一致；未显式设置时会自动生成并保存到数据目录的 `secret.key`，导出 JSON 已随身携带主密钥。

## 日常使用

### 工作台

首页即磁贴工作台：仓库 / 提交记录 / 项目 / 工作记录 / 报告 / 代码审查 / 服务监控七块磁贴，
带实时指标与状态灯，点击进入对应模块。顶栏右侧常驻系统状态灯与设置入口。

### 仓库接入

在「仓库」页新建，**直接粘贴仓库地址**即可（`https://` 与 `git@` 两种格式都支持，
带端口、子路径也能解析），平台、拥有者、仓库名与服务地址自动填好，平台由服务地址探测后确认。

访问令牌：

- Gitea：「设置 → 应用 → 生成令牌」，勾选 `read:repository`
- Gitee：「设置 → 私人令牌」，勾选 `projects` 读权限
- 自建 Gitea 填实例根地址，例如 `https://git.corp.cn`

可设置「包含关键字」「排除关键字」，按提交说明过滤纳入统计的提交。

### 提交同步

手动「同步」/「同步全部」之外，调度器按设置间隔自动同步；分页拉取提交与文件变更明细，自动去重。

**只汇总自己的提交**：「设置 → 同步 → 我的作者标识」填姓名、登录名或邮箱（逗号分隔）。填写后
同步时跳过他人提交，再次同步会清理此前已入库的他人提交；修改标识后下次同步重新扫历史补齐。
下拉候选来自同步时见到的全部作者（含未汇总的他人），右侧标注「已汇总 / 未汇总」。

`Merge` / `Revert` 开头的提交默认不计入统计。

### 工作记录

手工登记工作内容、类别与工时，**项目必填**：可从已同步提交所属的项目中直接选择，
也可以自行输入（覆盖没有仓库的项目）。

### 报告生成

支持周报 / 月报 / 季报 / 年报 / 自定义区间。生成是后台任务：接口立即返回，页面通过 SSE
实时推送阶段、进度与正文，能看着内容逐段长出来；年报等长任务不再被一个转圈卡住，
超时（默认 30 分钟无进展）会明确标记失败。

正文按**项目**分组、编号列事项，输出即周报格式：

```markdown
一、集团访客系统

1.企业微信界面调整，默认发起时间各端统一

二、南通海事短临预警系统

1.短临预警系统MCP服务开发
2.风电场模块打卡业务调整
```

归属规则：代码提交按所属仓库的「项目」字段（留空取仓库名），工作记录按记录自身的项目。
统计口径（提交数、工时、代码变更、项目分布）不写进正文，在报告详情中作为独立模块展示。

大模型在「设置 → 大模型」配置（OpenAI 兼容 `/chat/completions`，vLLM / Ollama / LM Studio /
Xinference 等均可，地址未带 `/v1` 会自动补全）；未配置或调用失败时自动回退本地模板。

### 代码审查

「代码审查」页选仓库创建审查任务，后台执行，页面显示「排队中 / 审核中」并实时刷新进度。
每个提交按变更内容交给大模型分析（Gitea 取 `.diff`，Gitee 取提交 `patch`，取不到退回变更文件原文），
只保留客观缺陷（逻辑错误、异常未处理、资源泄漏、并发、安全、性能、边界遗漏），风格建议排除。

问题按严重程度记录在「审查结果」，可单条或批量推送为仓库 Issue（Gitea 令牌需 `repo` 写权限，
Gitee 需 `projects` 写权限），也可忽略。单个提交通常 1-3 分钟；任务可取消，服务重启时
未完成任务标记为失败。

### 服务监控

登记需要保活的服务，系统按各自周期自动探活，状态变化时推送企业微信群机器人：

- 「新建监控」填服务地址后点「自动探测」：并发试探 20 多个常见健康检查路径
  （`/health`、`/healthz`、`/actuator/health`、`/api/status` 等），
  同时让大模型读取首页内容推测该技术栈可能使用的路径
- 可设置期望状态码与响应关键词，响应包含关键词才算正常
- 调度器每分钟扫描到期目标，检查动作进后台队列，单个慢目标不拖累其他目标；
  结果与「下次检查」每 10 秒自动刷新
- 首次检查不告警，此后状态跃迁才推送（正常→异常报障，异常→正常报恢复），避免告警轰炸
- 企微 webhook 在「设置 → 告警」填写

## 配置项

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_NAME` | 研发脉冲 | 应用名称 |
| `APP_TIMEZONE` | Asia/Shanghai | 业务时区，决定日期归属与统计口径 |
| `DATA_DIR` | ./data | 数据目录，存放加密主密钥等文件 |
| `DATABASE_URL` | — | 数据库连接串；留空则用 `DATA_DIR` 下的 SQLite |
| `APP_SECRET` | — | 主密钥，用于加密仓库令牌与签发会话；留空则自动生成到 `DATA_DIR/secret.key` |
| `APP_PASSWORD` | — | 访问密码，留空不启用登录；也可在「设置」页设置 |
| `CORS_ORIGINS` | * | 允许的跨域来源 |
| `LLM_BASE_URL` | — | 大模型接口地址，OpenAI 兼容格式 |
| `LLM_API_KEY` | — | 大模型访问令牌 |
| `LLM_MODEL` | — | 模型名称 |
| `LLM_TIMEOUT` | 300 | 大模型单次调用超时（秒） |
| `LLM_TEMPERATURE` | 0.3 | 采样温度 |
| `SYNC_INTERVAL_MINUTES` | 30 | 定时同步间隔（分钟） |
| `MAX_PAGES_PER_SYNC` | 20 | 单次同步每个仓库最大拉取页数 |
| `FETCH_COMMIT_FILES` | true | 是否拉取文件变更明细 |

大模型与同步参数也可在「设置」页面在线修改，页面配置优先于环境变量。

## 容器部署

### 即开即用（容器版）

```bash
docker run -d -p 8000:8000 -v devpulse-data:/app/data worklog-reporter:1.0.0
```

启动后自动完成建库、建表、默认配置与主密钥生成，浏览器打开进入初始化向导。
数据落在命名卷 `devpulse-data`（SQLite 的 WAL 在 Windows 绑定挂载目录上会偶发创建失败，
**不要**用 `-v ./data:/app/data` 这种宿主机目录挂载）。

启动时指定 MySQL：

```bash
docker run -d -p 8000:8000 \
  -e DATABASE_URL='mysql+pymysql://user:pwd@host:3306/daylife?charset=utf8mb4' \
  -v devpulse-data:/app/data worklog-reporter:1.0.0
```

容器内执行命令行工具：

```bash
docker exec -it worklog-reporter python -m app.cli export --output /app/backup.json
docker cp worklog-reporter:/app/backup.json ./
docker exec -it worklog-reporter python -m app.cli import --input /app/backup.json
```

### Docker Compose

连接已有 MySQL：

```bash
cp .env.example .env   # 填 APP_SECRET、数据库地址、大模型参数
docker compose up -d --build
```

Compose 会把容器内 `DATABASE_URL` 指向 `host.docker.internal` 以访问宿主机 MySQL；
其它地址用环境变量 `DOCKER_DATABASE_URL` 覆盖。

自带 MySQL 的独立部署：

```bash
docker compose -f docker-compose.mysql.yml up -d --build
```

### Podman 部署

Podman 的 WSL 虚拟机里，宿主机已发布端口的回环转发不稳定，让应用容器与 MySQL 容器
加入同一个共享网络直接互访：

```bash
# 1. 创建共享网络，把已有 MySQL 容器接入（别名 mysql）
bash scripts/podman_prepare.sh

# 2. 启动
podman-compose -f docker-compose.yml -f docker-compose.podman.yml up -d --build
```

`NETWORK`、`MYSQL_CONTAINER`、`MYSQL_ALIAS` 环境变量可覆盖脚本默认值。
MySQL 由本项目 compose 自行管理时直接用 `docker-compose.mysql.yml`，无需共享网络。

**访问内网 Gitea / Gitee**：Podman 默认网桥 `10.88.0.0/16` 与内网网段重叠时，容器访问内网
会被网桥截走（`No route to host`），在虚拟机里补一条精确路由；开机自启脚本会自动补，手动执行：

```powershell
.\scripts\podman_lan_route.ps1 -Cidr 10.88.192.0/24
```

**开机自启（Windows + Podman）**：`scripts/podman_autostart.ps1` 会启动 podman 机器、
等待 API、拉起 mysql8 / redis / worklog-reporter，转发失效时自动 `wsl --shutdown` 重试，
并自动补上面这条内网路由（`-LanRoutes` 可调整网段）；
注册计划任务（AtLogon + AtBoot）即可实现登录/开机自启。

### 基础镜像源与公司仓库

Docker Hub 部分网络不可达时切换基础镜像仓库：

```bash
podman build --build-arg REGISTRY=docker.m.daocloud.io/library \
  --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple \
  -t worklog-reporter:1.0.0 .
```

推送到公司镜像仓库：

```bash
podman tag worklog-reporter:1.0.0 ascr.asun.cloud/visitor/worklog-reporter:1.0.0
podman push ascr.asun.cloud/visitor/worklog-reporter:1.0.0
```

### 常用运维命令

```bash
docker compose ps
docker compose logs -f app
docker compose restart app
docker compose down
```

## 一键安装脚本与离线安装包

目标机器上有 podman / docker 时，拷一个脚本即可：

```bash
# Linux / macOS
bash scripts/install.sh

# Windows
pwsh -File .\scripts\install.ps1
```

脚本依次完成：检查容器引擎 → 准备镜像（本地有就直接用，没有就拉）→ 准备数据目录 →
启动容器 → 等待健康检查 → 打开浏览器。可用 `--port` / `--data-dir` / `--database-url`
（PowerShell 为 `-Port` / `-DataDir` / `-DatabaseUrl`）调整，安装脚本会自动挑可用端口
（默认 8000 被占用时改用 8001）。

离线安装包（目标机器不通外网时，先在有网环境生成）：

```bash
pwsh -File .\scripts\bundle.ps1 -Version 1.0.0
```

产物 `dist/devpulse-1.0.0.zip`（约 70 MB，含镜像、编排文件、安装脚本与部署文档），
解压后运行：

- Windows：双击 `安装.bat`
- Linux / macOS：`bash install.sh`

## 打包

```bash
# Windows（PowerShell 7+）
pwsh -File .\scripts\package.ps1

# Linux / macOS
bash scripts/package.sh
```

依次执行类型检查、前端构建、后端测试、镜像构建，最后在 `dist/` 产出源码包与镜像包。
常用参数：

```bash
pwsh -File .\scripts\package.ps1 -Version 1.2.0 -Push   # 指定版本并推送镜像
bash scripts/package.sh --skip-tests --skip-image       # 只出源码包
```

免安装单文件与发布压缩包：

```bash
pwsh -File .\scripts\standalone\build.ps1    # dist/devpulse.exe + devpulse-standalone.zip
bash scripts/standalone/build.sh             # dist/devpulse/devpulse + zip
```

更多部署细节见 [docs/deploy.md](docs/deploy.md)。

## 本地开发

### 后端

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp .env.example .env             # 按需修改，留空 DATABASE_URL 即用 SQLite
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

首次启动自动建表，无需额外初始化。模拟大模型联调用 `backend/mock_llm.py`。

### 前端

```bash
cd frontend
npm install
npm run dev                      # http://127.0.0.1:5173，接口代理到 127.0.0.1:8000
```

### 生产构建（本地直接跑）

```bash
cd frontend && npm run build && cd ..
cp -r frontend/dist static
python -m uvicorn app.main:app --app-dir backend --port 8000
# 或者
python -m app                    # 从 backend 目录运行
```

### 测试

```bash
cd backend && python -m pytest
```

## 目录结构

```text
.
├── scripts/
│   ├── package.ps1 / package.sh      源码包与镜像打包
│   ├── standalone/build.ps1 / .sh    免安装单文件打包
│   ├── bundle.ps1                    离线安装包（镜像 + 安装脚本）
│   ├── install.ps1 / install.sh      容器一键安装
│   ├── podman_prepare.sh             Podman 部署前置：共享网络与 MySQL 接入
│   ├── podman_autostart.ps1          Windows 开机自启与容器拉起
│   └── podman_lan_route.*            补内网路由（跨网段 Gitea 访问）
├── docs/deploy.md                    部署文档
├── backend/
│   ├── app/
│   │   ├── main.py                   应用入口与静态资源托管
│   │   ├── standalone.py             单文件可执行入口（端口顺延、自动开浏览器）
│   │   ├── cli.py                    导出 / 导入 / 迁移 / 初始化命令行
│   │   ├── config.py                 环境变量配置
│   │   ├── database.py               引擎与会话（SQLite 韧性处理）
│   │   ├── models.py / schemas.py    数据模型与请求响应模型
│   │   ├── security.py               令牌加密与会话签名
│   │   ├── migrations.py             增量字段补齐
│   │   ├── routers/                  API 路由
│   │   └── services/
│   │       ├── gitplatform.py        Gitea / Gitee 客户端
│   │       ├── sync.py               仓库同步
│   │       ├── report.py             周期计算与报告生成（后台任务 + SSE）
│   │       ├── review.py             代码审查与 Issue 推送
│   │       ├── monitor.py            服务探活与企微告警
│   │       ├── llm.py                大模型客户端
│   │       ├── scheduler.py          定时任务
│   │       ├── task_queue.py         后台任务队列
│   │       └── config_store.py       运行时配置存取
│   ├── tests/                        pytest 用例
│   └── mock_llm.py                   模拟大模型服务
├── frontend/                         Vue 3 前端（科幻 HUD 风格，磁贴工作台）
│   └── src/{api,components,layouts,router,stores,styles,utils,views}
├── Dockerfile                        多阶段构建
├── docker-compose.yml                连接已有 MySQL 部署
├── docker-compose.mysql.yml          自带 MySQL 的独立部署
├── docker-compose.podman.yml         Podman 部署覆盖
└── .env                              运行时配置（不入库）
```

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| POST | `/api/auth/login` | 登录 |
| GET | `/api/setup/status` | 数据库与初始化状态 |
| POST | `/api/setup/database` | 切换数据库地址 |
| POST | `/api/setup/migrate` | 把数据整体迁移到另一个库 |
| GET/POST | `/api/setup/export` | 导出全部数据 |
| POST | `/api/setup/import` | 从导出数据恢复 |
| POST | `/api/setup/llm` | 配置大模型并测试连通 |
| POST | `/api/setup/password` | 设置访问密码 |
| POST | `/api/setup/complete` | 标记初始化完成 |
| GET/POST | `/api/repos` | 仓库列表 / 新建 |
| POST | `/api/repos/parse` | 解析仓库地址，自动填平台 / 拥有者 / 仓库名 / 服务地址 |
| PUT/DELETE | `/api/repos/{id}` | 修改 / 删除仓库 |
| POST | `/api/repos/{id}/sync` | 同步单个仓库 |
| POST | `/api/repos/sync` | 同步全部仓库 |
| GET | `/api/commits` | 提交记录分页查询 |
| GET | `/api/commits/authors` | 同步时见过的作者候选（含未汇总） |
| GET/POST | `/api/projects` | 项目清单 / 手工登记项目 |
| DELETE | `/api/projects/{id}` | 删除项目及其工作记录 |
| GET/POST | `/api/works` | 工作记录查询 / 新建 |
| PUT/DELETE | `/api/works/{id}` | 修改 / 删除工作记录 |
| GET/POST | `/api/reports` | 报告列表 / 生成报告（后台任务） |
| GET | `/api/reports/{id}/stream` | 报告生成进度与正文 SSE |
| PUT/DELETE | `/api/reports/{id}` | 修改 / 删除报告 |
| POST | `/api/reviews/tasks` | 创建代码审查任务（后台执行） |
| GET | `/api/reviews/tasks` | 审查任务列表 |
| POST | `/api/reviews/{id}/issues` | 把审查问题推送为仓库 Issue |
| GET/POST | `/api/monitors` | 监控目标列表 / 新建 |
| POST | `/api/monitors/probe` | 探测可用的健康检查路径 |
| GET/POST | `/api/monitors/{id}/check` | 检查记录 / 立即执行一次检查 |
| GET/PUT | `/api/settings` | 读取 / 保存配置 |
| POST | `/api/settings/llm/test` | 大模型连通性测试 |
| GET | `/api/dashboard/overview` | 概览数据 |

## 常见问题

**8000 端口被占用？**
单文件版自动顺延到下一个可用端口，横幅里打印实际地址；想固定端口加 `--port`，
不想顺延再加 `--strict-port`。

**容器部署后列表接口偶发 500？**
Windows 上把 SQLite 放在宿主机绑定挂载目录（`-v ./data:/app/data`）时，WAL 共享内存文件
可能创建失败。改用命名卷：`-v devpulse-data:/app/data`。

**同步到的提交里有别人的？**
在「设置 → 同步 → 我的作者标识」里填自己的姓名 / 登录名 / 邮箱，再次同步会清理
已入库的他人提交。

**换个机器令牌解不开了？**
令牌按 `APP_SECRET` 加密。保留原实例的数据目录（`secret.key` 随目录走），
或用「设置 → 数据」导出的 JSON 导入（自带主密钥）。

**Podman 容器访问不了内网 Gitea？**
默认网桥与内网网段重叠时补路由：`scripts/podman_lan_route.ps1 -Cidr <内网网段>`。
开机自启脚本会自动补；虚拟机重启后若还没跑自启脚本，手动执行一次即可。
