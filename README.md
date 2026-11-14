# 研发脉冲 · Dev Pulse

面向研发的个人工作台：汇总 Gitea / Gitee 提交与手工工作记录，产出周报、月报、季报、年报；  
对提交做代码质量检查并推送 Issue；对内部服务定期探活，异常时经企业微信告警。

支持 Docker Compose 一键部署，内置定时同步，报告与审查接本地部署的 OpenAI 兼容大模型。

## 功能

| 模块    | 说明                                           |
| ----- | -------------------------------------------- |
| 代码审查  | 对已同步的提交做质量检查，发现的问题可推送到仓库 Issue               |
| 界面风格  | 科幻 HUD：深空底、半透明发光面板、状态灯脉冲；磁贴工作台导航，页面通栏        |
| 服务监控  | 定期探活内部服务，异常时推送企业微信群机器人告警                     |
| 仓库接入  | Gitea（含自建实例）与 Gitee 仓库登记、访问令牌加密存储、按关键字过滤     |
| 提交同步  | 手动触发与定时同步，分页拉取提交与文件变更明细，自动去重                 |
| 工作记录  | 手工登记工作内容、项目、类别与工时                            |
| 报告生成  | 周报 / 月报 / 季报 / 年报 / 自定义区间，Markdown 输出，可复制与下载 |
| 大模型撰写 | 接本地部署的 OpenAI 兼容接口，按事实材料生成结构化报告；未配置时回退到本地模板  |
| 访问控制  | 可选访问密码，会话基于 HMAC 签名 Cookie                   |
| 概览    | 提交趋势、仓库分布、工时统计、最近提交与报告                       |

## 技术栈

- 后端：Python 3.12 + FastAPI + SQLAlchemy 2.0 + APScheduler
- 数据库：MySQL 8（SQLAlchemy 亦可切回 SQLite）
- 前端：Vue 3 + TypeScript + Vite + Element Plus + ECharts
- 部署：Docker 多阶段构建，前端产物由后端进程直接托管

## 目录结构

```
.
├── scripts/
│   ├── package.ps1              打包脚本（Windows，PowerShell 7+）
│   ├── package.sh               打包脚本（Linux / macOS）
│   ├── podman_prepare.sh        Podman 部署前置：共享网络与 MySQL 接入
│   ├── podman_lan_route.sh      补内网路由（Linux/macOS）
│   └── podman_lan_route.ps1     补内网路由（Windows）
├── docs/
│   └── deploy.md                部署文档
├── backend/
│   ├── app/
│   │   ├── main.py              应用入口与静态资源托管
│   │   ├── config.py            环境变量配置
│   │   ├── database.py          引擎与会话
│   │   ├── models.py            数据模型
│   │   ├── schemas.py           请求响应模型
│   │   ├── security.py          令牌加密与会话签名
│   │   ├── timeutil.py          业务时区处理
│   │   ├── migrations.py        增量字段补齐
│   │   ├── routers/             API 路由
│   │   └── services/
│   │       ├── gitplatform.py   Gitea / Gitee 客户端
│   │       ├── llm.py           大模型客户端
│   │       ├── report.py        周期计算与报告生成
│   │       ├── review.py        代码审查与 Issue 推送
│   │       ├── monitor.py       服务探活与企微告警
│   │       ├── sync.py          仓库同步
│   │       ├── scheduler.py     定时任务
│   │       ├── task_queue.py    后台任务队列
│   │       └── config_store.py  运行时配置存取
│   ├── tests/                   pytest 用例
│   └── mock_llm.py              模拟大模型服务，用于联调
├── frontend/                    Vue 3 前端（科幻 HUD 风格）
│   └── src/
│       ├── api/                 接口封装与类型
│       ├── components/          图表等通用组件
│       ├── layouts/             顶栏框架
│       ├── router/              路由
│       ├── stores/              状态
│       ├── styles/              HUD 设计系统
│       ├── utils/               格式化工具
│       └── views/               页面
├── Dockerfile                   多阶段构建
├── docker-compose.yml           连接已有 MySQL 部署
├── docker-compose.mysql.yml     自带 MySQL 的独立部署
├── docker-compose.podman.yml    Podman 部署覆盖
└── .env                         运行时配置（不入库）
```

## 快速开始（本地开发）

### 1. 后端

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp .env.example .env             # 按需修改
```

`.env` 中确认数据库连接：

```dotenv
DATABASE_URL=mysql+pymysql://root:ztt123456@localhost:3306/daylife?charset=utf8mb4
```

首次启动会自动建表，无需额外初始化。

启动：

```bash
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

开发地址 <http://127.0.0.1:5173>，接口已代理到 `127.0.0.1:8000`。

### 3. 生产构建（本地）

```bash
cd frontend && npm run build
cp -r dist ../static
python -m uvicorn app.main:app --app-dir backend --port 8000
```

## 周报格式

报告正文按**项目**分组，每个项目下用编号列出事项：

```markdown
一、集团访客系统

1.企业微信界面调整，默认发起时间各端统一

二、南通海事短临预警系统

1.短临预警系统MCP服务开发
2.风电场模块打卡业务调整

三、交通局充电平台运维项目

1.排查金立服务器无法连接问题
2.特来电相关企业数据对接
```

项目的归属规则：

| 数据来源 | 归属项目                 |
| ---- | -------------------- |
| 代码提交 | 所属仓库的「项目」字段，留空时取仓库名称 |
| 工作记录 | 记录自身的「项目」字段，必填       |

接入仓库时直接粘贴仓库地址即可（https / git@ 两种格式都可以），平台、拥有者、仓库名与服务地址自动填好，平台由服务址探测后确认。

工作记录的项目从已同步提交所属的项目中抽取（`GET /api/projects`），可直接选择，  
同时保留自定义输入，以覆盖尚未建仓的项目。

报告生成是后台任务：接口立即返回，页面通过 SSE 推送阶段与正文，生成期间能看到当前阶段、已用时长、汇总范围与逐段生成的正文，不会被一个转圈卡住。

统计口径（提交数、工时、代码变更、项目分布）不写进正文，在报告详情中作为独立模块展示。

## 只汇总自己的提交

「设置 → 同步 → 我的作者标识」可填入姓名、登录名或邮箱，多个用逗号分隔。填写后：

- 同步时跳过他人提交，并在仓库状态里说明跳过数量
- 再次同步会清理此前已入库的他人提交
- 修改标识后下次同步会重新扫一遍历史，避免新选的人的旧提交补不回来

下拉候选来自同步时见到的作者（含尚未汇总的他人），右侧标注为「已汇总」或「未汇总」。
候选不能只看已入库的提交，否则先按标识过滤、后才有候选，他人的名字会永远不出现。

提交信息以 `Merge ` / `Revert ` 开头的合并与回滚提交默认不计入统计。

## 代码审查

对已同步的提交做质量检查，把发现的问题记录下来，并可推送到仓库的 Issue。

流程：

1. 在「代码审查」页选择仓库，点「创建审查任务」。任务在后台执行，页面显示「排队中 / 审核中」，进度实时刷新。
2. 每个提交按变更内容交给大模型分析：Gitea 取提交 `.diff`，Gitee 取提交详情里的 `patch`；取不到时退回变更文件原文。
3. 只保留客观缺陷（逻辑错误、异常未处理、资源泄漏、并发、安全、性能、边界遗漏），风格类建议会被排除。
4. 审查出的问题按严重程度记录在「审查结果」里，可单条或批量推送为仓库 Issue，也可以忽略。

推送 Issue 需要令牌有写权限：Gitea 令牌勾选 `repo`，Gitee 令牌勾选 `projects` 写权限。

审查耗时取决于提交大小与模型速度，单个提交通常在 1 到 3 分钟；任务可随时取消，服务重启时未完成的任务会被标记为失败。

## 界面导航

采用磁贴工作台：首页即工作台，由 7 块磁贴构成（仓库 / 提交记录 / 项目 / 工作记录 / 报告 / 代码审查 / 服务监控），  
每块带实时指标与状态灯，点击进入对应模块。顶栏显示当前位置（工作台 / 当前页），可随时回到工作台。

顶部右侧常驻系统状态灯与设置入口，页面主体通栏，表格能完整铺开。

## 服务监控

登记需要保活的服务，系统按各自周期探活，状态变化时推送企业微信群机器人。

- 「新建监控」填服务地址后点「自动探测」：系统会并发试探 20 多个常见健康检查路径  
  （`/health`、`/healthz`、`/actuator/health`、`/api/status` 等），同时让大模型读取首页内容  
  推测该技术栈可能使用的路径，一并纳入候选
- 可设置期望状态码与响应关键词，响应需包含关键词才算正常
- 巡检完全自动：调度器每分钟扫描到期目标，按各自周期执行，检查动作进后台队列，单个慢目标不拖累其他目标
- 界面不提供手动触发，检查结果与「下次检查」时间每 10 秒自动刷新
- 首次检查不告警；此后状态发生跃迁才推送（正常→异常 报障，异常→正常 报恢复），避免告警轰炸
- 企微 webhook 在「设置 → 告警」填写

> 容器访问内网服务受 Podman 网段影响，跨网段时先补路由，见部署文档第 7 节。

## 免容器运行（单文件）

目标机器既没有 podman 也没有 docker 时，可以打包成一个独立可执行程序：

```bash
# Windows
pwsh -File .\scripts\standalone\build.ps1

# Linux / macOS
bash scripts/standalone/build.sh
```

产物 `dist/devpulse.exe`（Windows，约 28 MB）或 `dist/devpulse/devpulse`（Linux/macOS）。
打包脚本同时产出 `dist/devpulse-standalone.zip`（可执行程序 + 配置样例 + 使用说明），拷到任意机器解压即用。
里面打包了 Python 运行时、后端、依赖与前端静态资源，**目标机器什么都不用装**，
拷过去双击（Linux 上 `./devpulse`）即可：

```bash
devpulse --port 8000 --data-dir /opt/devpulse/data
```

| 参数 | 说明 |
| --- | --- |
| `-p, --port` | 监听端口，默认 8000；被占用时自动顺延到下一个可用端口 |
| `--strict-port` | 端口被占用时直接退出，不自动顺延 |
| `-d, --data-dir` | 数据目录，默认系统用户数据目录 |
| `--portable` | 数据放在程序同级的 `data`，便于整目录拷贝 |
| `--host` | 监听地址，默认 `0.0.0.0` |
| `--no-browser` | 启动后不自动打开浏览器 |
| `--database-url` | 指定数据库，留空则用本地 SQLite |

双击启动后会自动打开浏览器（服务就绪后打开实际监听地址）。

数据目录默认落在系统用户目录，Windows 为 `%LOCALAPPDATA%\devpulse`，
Linux/macOS 为 `~/.local/share/devpulse`；换机器或重装不影响数据，
也不会因为重新打包而丢失。实际监听端口写在数据目录的 `runtime.json` 里。

端口被占用时的处理：

- 占用者就是本应用（重复双击）→ 直接提示已有实例的地址并退出
- 被别的程序占用 → 自动顺延到 8001、8002……，启动横幅里会打印实际地址
- 端口连着顺延 50 个都不可用 → 明确报错退出

程序同级放一个 `.env` 同样生效，可配置数据库、大模型与访问密码；
只有程序同级有 `.env` 才会被读取，不会误读启动目录里的其它配置文件。
默认使用 SQLite；若要连 MySQL，初始化向导里可以直接切换或迁移。

也换机器迁移有两种方式：

- 整个数据目录一起拷过去（加 `--portable` 时数据就在程序同级）
- 在「设置 → 数据」导出 JSON，到新机器导入；导出文件带上主密钥，导入后仓库令牌与大模型密钥不需要重新配置

可以不用打包，直接用 Python 跑：

```bash
pip install -r backend/requirements.txt
cd frontend && npm run build && cd ..
python -m app            # 从 backend 目录运行
```

## 一键安装

### 在线安装

目标机器上有 podman 或 docker 时，复制一个脚本即可：

```bash
# Linux / macOS
bash scripts/install.sh

# Windows
pwsh -File .\scripts\install.ps1
```

脚本会依次完成：检查容器引擎 → 准备镜像（本地有就直接用，没有就拉）→ 准备数据目录 →
启动容器 → 等待健康检查通过 → 打开浏览器。首次访问进入初始化向导。

常用参数：

```bash
bash scripts/install.sh --port 9000 --data-dir /opt/devpulse/data
pwsh -File .\scripts\install.ps1 -Port 9000 -DataDir D:\data\devpulse
```

### 离线安装包

目标机器不通外网时，生成一个自带镜像的安装包：

```bash
pwsh -File .\scripts\bundle.ps1 -Version 1.0.0
```

产物 `dist/devpulse-1.0.0.zip`（约 70 MB），解压后运行：

- Windows：双击 `安装.bat`
- Linux / macOS：`bash install.sh`

包内含镜像、编排文件、安装脚本与部署文档，目标机器无需任何配置即可启动。
安装脚本会自动挑一个可用端口（默认 8000 被占用时改用 8001），并在安装完成后打印实际地址。

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
pwsh -File .\scripts\package.ps1 -Version 1.2.0 -Push   # 指定版本并推送镜像仓库
bash scripts/package.sh --skip-tests --skip-image          # 只出源码包
```

部署步骤见 [docs/deploy.md](docs/deploy.md)。

## 即开即用

不需要任何配置即可启动：

```bash
podman run -d -p 8000:8000 -v worklog-data:/app/data worklog-reporter:1.0.0
```

启动后自动完成：建库（默认容器内 SQLite）→ 建表与补齐字段 → 写入默认配置 → 生成加密主密钥 → 拉起调度器。

浏览器打开后进入**初始化向导**，按四步完成配置：

| 步骤   | 内容                                          |
| ---- | ------------------------------------------- |
| 数据库  | 默认本地 SQLite，开箱即用；可当场切成 MySQL（先试连再切换，失败不动原库） |
| 大模型  | 填接口地址、令牌、模型名，**先测试连通再落库**，失败不写半成品配置         |
| 访问密码 | 设置后立即下发会话，后续步骤不会被打断                         |
| 代码仓库 | 初始化后在工作台添加                                  |

也可以跳过向导直接进工作台，之后随时在「设置」里补。

### 启动时指定数据库

```bash
podman run -d -p 8000:8000 \
  -e DATABASE_URL='mysql+pymysql://user:pwd@host:3306/daylife?charset=utf8mb4' \
  -v worklog-data:/app/data worklog-reporter:1.0.0
```

环境变量留空即使用 SQLite。也可在向导里切换，切换是运行时生效，无需重启。

### 数据迁移与导入导出

不想重新配置时，把**现有库的数据整体搬过来**即可，不必手工重填：

- 在「设置 → 数据」里直接导出 JSON 备份、导入 JSON、把数据迁移到 SQLite
- 初始化向导的「数据库」步骤也有「把数据迁移到 SQLite」入口：先试连两端，通了才复制，失败不动原库
- 迁移复制全部业务表：仓库、提交、工作记录、项目、报告、审查记录与问题、服务监控与巡检、运行配置
- 迁移完成后地址写入 `data/database.url`，优先级高于环境变量，重启后依然生效
- 想改回环境变量配置，删除该文件或在向导里点「改回环境变量配置」

页面上的三个动作对应：导出 = 下载一份 JSON 快照；导入 = 用 JSON 覆盖当前库（有二次确认）；
迁移 = 库与库之间直接复制。命令行同样支持：

```bash
# 导出为 JSON（可备份、可换机器导入）
docker exec worklog-reporter python -m app.cli export --output backup.json
docker cp worklog-reporter:/app/backup.json ./

# 从导出文件恢复
docker cp backup.json worklog-reporter:/app/backup.json
docker exec worklog-reporter python -m app.cli import --input /app/backup.json

# 库间迁移（--to-url 留空则目标为本地 SQLite）
docker exec worklog-reporter python -m app.cli migrate --to-url ''
```

> 仓库令牌与大模型密钥是按 `APP_SECRET` 派生的密钥加密存储的。换库或换机器时请保持
> `APP_SECRET` 一致，否则密文解不开、需要重新填写令牌。

### 命令行初始化

```bash
docker exec -it worklog-reporter python -m app.cli status   # 查看当前数据库与初始化状态
docker exec -it worklog-reporter python -m app.cli init     # 建表并写入默认配置
docker exec -it worklog-reporter python -m app.cli init --database-url 'mysql+pymysql://...'
```

## Docker Compose 部署

### 方式一：连接已有 MySQL

```bash
cp .env.example .env
# 编辑 .env，填入 APP_SECRET、数据库地址、大模型参数
docker compose up -d --build
```

Compose 会把容器内的 `DATABASE_URL` 指向 `host.docker.internal`，  
以便访问宿主机上的 MySQL；需要指定其他地址时设置环境变量 `DOCKER_DATABASE_URL`。

访问 <http://localhost:8000>

### 方式二：自带 MySQL 的独立部署

```bash
docker compose -f docker-compose.mysql.yml up -d --build
```

该方式会额外启动 MySQL 8.4 容器，数据保存在 `mysql-data` 卷中。

### 方式三：Podman 部署

Podman 的 WSL 虚拟机中，宿主机已发布端口的回环转发不稳定，  
因此让应用容器与 MySQL 容器加入同一个共享网络，直接走容器网络互访。

```bash
# 1. 创建共享网络，并把已有的 MySQL 容器接入（别名 mysql）
bash scripts/podman_prepare.sh

# 2. 启动
podman-compose -f docker-compose.yml -f docker-compose.podman.yml up -d --build
```

访问 <http://localhost:8000>

`scripts/podman_prepare.sh` 的参数可用环境变量覆盖：  
`NETWORK`、`MYSQL_CONTAINER`、`MYSQL_ALIAS`。

若 MySQL 由本项目的 compose 自行管理，直接用 `docker-compose.mysql.yml` 即可，  
无需共享网络：

```bash
podman-compose -f docker-compose.mysql.yml up -d --build
```

### 访问内网 Gitea / Gitee

Podman 默认网桥使用 `10.88.0.0/16`，与内网网段重叠时，容器访问内网会被网桥截走，表现为 `No route to host`。  
此时在虚拟机里补一条更精确的路由：

```bash
.\scripts\podman_lan_route.ps1 -Cidr 10.88.192.0/24
```

路由在虚拟机重启后失效，重新执行即可。

### 基础镜像源

Docker Hub 在部分网络下不可达，Dockerfile 通过 `REGISTRY` 构建参数切换基础镜像仓库：

```bash
podman build --build-arg REGISTRY=docker.m.daocloud.io/library -t worklog-reporter:1.0.0 .
```

`docker-compose.podman.yml` 已默认使用 `docker.m.daocloud.io/library`。

### 推送镜像到公司仓库

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

## 配置项

| 变量                      | 默认值           | 说明                                                                                                |
| ----------------------- | ------------- | ------------------------------------------------------------------------------------------------- |
| `APP_NAME`              | 研发脉冲          | 应用名称                                                                                              |
| `APP_TIMEZONE`          | Asia/Shanghai | 业务时区，决定日期归属与统计口径                                                                                  |
| `DATA_DIR`              | ./data        | 数据目录，存放加密主密钥等文件                                                                                   |
| `DATABASE_URL`          | —             | 数据库连接串；留空则用 `DATA_DIR` 下的 SQLite。MySQL 形如 `mysql+pymysql://user:pwd@host:3306/db?charset=utf8mb4` |
| `APP_SECRET`            | —             | 主密钥，用于加密仓库令牌与签发会话；留空则自动生成并保存到 `DATA_DIR/secret.key`                                               |
| `APP_PASSWORD`          | —             | 访问密码，留空表示不启用登录；也可在「设置」页面设置                                                                        |
| `CORS_ORIGINS`          | *             | 允许的跨域来源                                                                                           |
| `LLM_BASE_URL`          | —             | 大模型接口地址，OpenAI 兼容格式，如 `http://127.0.0.1:8000/v1`                                                  |
| `LLM_API_KEY`           | —             | 大模型访问令牌                                                                                           |
| `LLM_MODEL`             | —             | 模型名称                                                                                              |
| `LLM_TEMPERATURE`       | 0.3           | 采样温度                                                                                              |
| `SYNC_INTERVAL_MINUTES` | 30            | 定时同步间隔（分钟）                                                                                        |
| `MAX_PAGES_PER_SYNC`    | 20            | 单次同步每个仓库最大拉取页数                                                                                    |
| `FETCH_COMMIT_FILES`    | true          | 是否拉取文件变更明细                                                                                        |

大模型与同步参数也可在「设置」页面在线修改，页面配置优先于环境变量。

## 接入 Gitea / Gitee

1. 在「仓库」页新建仓库，选择平台并填写拥有者与仓库名。
2. 填入访问令牌：
   - Gitea：`设置 → 应用 → 生成令牌`，勾选 `read:repository`
   - Gitee：`设置 → 私人令牌`，勾选 `projects` 读权限
3. 自建 Gitea 在「服务地址」填实例根地址，例如 `https://git.corp.cn`
4. 点「同步」或「同步全部」

可设置「包含关键字」「排除关键字」，按提交说明过滤需要纳入统计的提交。

## 接入本地大模型

服务需提供 OpenAI 兼容的 `/chat/completions` 接口（vLLM、Ollama、LM Studio、Xinference、llama.cpp server 均支持）。

在「设置 → 大模型」填写接口地址、令牌与模型名称，点「测试连接」验证。地址未带 `/v1` 时会自动补全。

未配置或调用失败时，报告自动回退到本地模板输出，统计数据不受影响。

## API

| 方法         | 路径                         | 说明                |
| ---------- | -------------------------- | ----------------- |
| GET        | `/api/health`              | 健康检查              |
| POST       | `/api/auth/login`          | 登录                |
| GET        | `/api/setup/status`        | 数据库与初始化状态          |
| POST       | `/api/setup/database`      | 切换数据库地址           |
| POST       | `/api/setup/migrate`       | 把数据整体迁移到另一个库      |
| POST       | `/api/setup/export`        | 导出全部数据            |
| POST       | `/api/setup/import`        | 从导出数据恢复           |
| POST       | `/api/setup/llm`           | 配置大模型并测试连通       |
| POST       | `/api/setup/password`      | 设置访问密码            |
| POST       | `/api/setup/complete`      | 标记初始化完成          |
| GET/POST   | `/api/repos`               | 仓库列表 / 新建         |
| PUT/DELETE | `/api/repos/{id}`          | 修改 / 删除仓库         |
| POST       | `/api/repos/{id}/sync`     | 同步单个仓库            |
| POST       | `/api/repos/sync`          | 同步全部仓库            |
| GET        | `/api/commits`             | 提交记录分页查询          |
| GET/POST   | `/api/monitors`            | 监控目标列表 / 新建       |
| POST       | `/api/monitors/probe`      | 探测可用的健康检查路径       |
| POST       | `/api/monitors/{id}/check` | 立即执行一次检查          |
| GET/POST   | `/api/projects`            | 项目清单 / 手工登记项目     |
| DELETE     | `/api/projects/{id}`       | 删除项目及其工作记录        |
| GET/POST   | `/api/works`               | 工作记录查询 / 新建       |
| PUT/DELETE | `/api/works/{id}`          | 修改 / 删除工作记录       |
| GET/POST   | `/api/reports`             | 报告列表 / 生成报告       |
| PUT/DELETE | `/api/reports/{id}`        | 修改 / 删除报告         |
| POST       | `/api/reviews/tasks`       | 创建代码审查任务（后台执行）    |
| GET        | `/api/reviews/tasks`       | 审查任务列表            |
| POST       | `/api/reviews/{id}/issues` | 把审查问题推送为仓库 Issue |
| GET/PUT    | `/api/settings`            | 读取 / 保存配置          |
| POST       | `/api/settings/llm/test`   | 大模型连通性测试          |
| GET        | `/api/dashboard/overview`  | 概览数据               |