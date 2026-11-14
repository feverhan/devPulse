# 部署文档

面向运维/实施，覆盖从拿到部署物到系统可用的完整流程。

## 1. 部署物

执行 `scripts/package.ps1`（或 `scripts/package.sh`）后，`dist/` 下产出两类文件：

| 文件                                 | 用途              | 典型大小     |
| ---------------------------------- | --------------- | -------- |
| `worklog-reporter-src-<版本>.tar.gz` | 源码包，可在目标机器上自行构建 | 约 100 KB |
| `worklog-reporter-<版本>.tar`        | 镜像包，离线导入直接运行    | 约 210 MB |

镜像包为 `docker-archive` 格式，`podman load` 与 `docker load` 均可导入。

## 2. 一键安装（推荐）

### 在线安装

把脚本拷到目标机器运行即可，无需手工写配置：

```bash
# Linux / macOS
bash scripts/install.sh

# Windows
pwsh -File .\scripts\install.ps1
```

脚本自动完成：检查容器引擎 → 准备镜像（本地有就用，没有就拉）→ 准备数据目录 →  
启动容器 → 等待健康检查 → 打开浏览器。可用 `--port` / `--data-dir` / `--database-url`  
（PowerShell 用 `-Port` / `-DataDir` / `-DatabaseUrl`）调整。

### 离线安装包

目标机器不通外网时，在有网环境生成：

```bash
pwsh -File .\scripts\bundle.ps1 -Version 1.0.0
```

产物 `dist/devpulse-1.0.0.zip`（约 70 MB），解压后运行 `安装.bat`（Windows）或  
`bash install.sh`（Linux / macOS）。包内含镜像、编排文件、安装脚本与本文档。

## 3. 免容器运行（单文件）

目标机器没有 podman / docker 时，打包成独立可执行程序：

```bash
# Windows
pwsh -File .\scripts\standalone\build.ps1

# Linux / macOS
bash scripts/standalone/build.sh
```

产物 `dist/devpulse.exe` 或 `dist/devpulse/devpulse`，内含 Python 运行时、后端与前端资源，  
拷到目标机器直接运行：

```bash
./devpulse --port 8000 --data-dir /opt/devpulse/data
```

数据目录默认落在系统用户目录：Windows 为 `%LOCALAPPDATA%\devpulse`，
Linux/macOS 为 `~/.local/share/devpulse`；加 `--portable` 则放在程序同级的 `data`，
适合整目录拷贝迁移。端口被占用时自动顺延到下一个可用端口，
打包脚本同时产出 `dist/devpulse-standalone.zip`（可执行程序 + 配置样例 + 使用说明），拷到任意机器解压即用。
启动后会自动打开浏览器（加 `--no-browser` 可关掉），
实际监听端口写在数据目录的 `runtime.json` 里；重复双击会直接提示已有实例的地址。

数据默认使用系统用户目录下的 SQLite 库；程序同级放 `.env` 同样生效。

## 4. 零配置启动（推荐先用这个验证）

不需要 `.env`、不需要 MySQL，一条命令即可跑起来：

```bash
podman run -d --name worklog-reporter -p 8000:8000 \
  -v worklog-data:/app/data worklog-reporter:1.0.0
```

启动过程全自动：建库（容器内 SQLite，位于 `/app/data/worklog.db`）→ 建表并补齐字段 →  
写入默认配置 → 生成加密主密钥 `secret.key` → 拉起定时同步与后台任务队列。

浏览器打开 <http://localhost:8000> 会进入**初始化向导**：

1. **数据库**：默认本地 SQLite；需要 MySQL 时在此填连接串，系统先试连，通了才切换，失败不动原库
2. **大模型**：填接口地址、令牌、模型名；先测试连通，通过才写入
3. **访问密码**：设置后立即下发会话，向导流程不中断
4. **代码仓库**：初始化后到工作台添加

点「跳过并进入工作台」可先跳过，之后随时补。

指定 MySQL 启动：

```bash
podman run -d --name worklog-reporter -p 8000:8000 \
  -e DATABASE_URL='mysql+pymysql://user:pwd@host:3306/daylife?charset=utf8mb4' \
  -v worklog-data:/app/data worklog-reporter:1.0.0
```

命令行初始化：

```bash
docker exec -it worklog-reporter python -m app.cli status
docker exec -it worklog-reporter python -m app.cli init --database-url 'mysql+pymysql://...'
```

## 5. 环境要求

| 项目   | 最低                          | 说明                     |
| ---- | --------------------------- | ---------------------- |
| 容器引擎 | Podman 4.4+ 或 Docker 20.10+ | 二选一                    |
| 数据库  | MySQL 8.0+                  | 需已建库并授权；也可由 compose 内置 |
| 内存   | 2 GB                        | 应用本身约 300 MB           |
| 端口   | 8000                        | 可通过 `APP_PORT` 改       |

安装脚本会自动挑一个可用端口：默认 8000 被占用时自动改用 8001，以此类推，安装完成后会打印实际地址。
| 大模型  | OpenAI 兼容接口                 | 本地部署或内网推理服务，可稍后在页面配置   |

## 6. 部署前准备

### 6.1 复制配置文件（可选）

```bash
cp .env.example .env
```

`.env` 不在源码包中（避免泄露密钥），需要时由部署方自行创建；**不创建也能启动**，此时用容器内 SQLite。

### 6.2 准备数据库（使用 MySQL 时）

```sql
CREATE DATABASE daylife DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'worklog'@'%' IDENTIFIED BY '你的密码';
GRANT ALL PRIVILEGES ON daylife.* TO 'worklog'@'%';
FLUSH PRIVILEGES;
```

把连接串写进 `.env`：

```dotenv
DATABASE_URL=mysql+pymysql://worklog:你的密码@127.0.0.1:3306/daylife?charset=utf8mb4
```

### 6.3 关键配置

```dotenv
# 必改：主密钥，用于加密仓库令牌与签发登录会话，丢失后已存令牌无法解密
APP_SECRET=换成一串足够长的随机字符串

# 访问密码，留空表示不启用登录
APP_PASSWORD=

# 大模型（也可以部署完在「设置」页面填）
LLM_BASE_URL=http://127.0.0.1:8000/v1
LLM_API_KEY=
LLM_MODEL=qwen2.5:7b
```

> **APP_SECRET 务必备份。** 仓库访问令牌、模型令牌都以它派生的密钥加密存储，丢失 `APP_SECRET` 或 `data/secret.key` 后，数据库中的密文将无法解密，只能重新填写令牌。

随机生成一个：

```bash
openssl rand -hex 32
```

## 7. 部署

### 7.1 离线：导入镜像包

```bash
podman load -i worklog-reporter-1.0.0.tar
# docker load -i worklog-reporter-1.0.0.tar
```

### 7.2 Podman

```bash
# 已有外部 MySQL
podman-compose -f docker-compose.yml up -d

# 自带 MySQL
podman-compose -f docker-compose.mysql.yml up -d
```

### 7.3 Docker

```bash
docker compose -f docker-compose.yml up -d
```

### 7.4 从镜像仓库拉取

```bash
podman pull ascr.asun.cloud/visitor/worklog-reporter:1.0.0
podman tag ascr.asun.cloud/visitor/worklog-reporter:1.0.0 worklog-reporter:1.0.0
podman-compose -f docker-compose.yml up -d
```

### 7.5 从源码包构建

```bash
tar -xzf worklog-reporter-src-1.0.0.tar.gz
cd worklog-reporter-src-1.0.0
cp .env.example .env    # 按第 3 节填写
podman-compose -f docker-compose.yml up -d --build
```

## 8. 验证

```bash
curl http://127.0.0.1:8000/api/health
# {"status":"ok","app":"工时周报","version":"1.0.0"}
```

浏览器打开 `http://<服务器地址>:8000`。

容器健康状态：

```bash
podman ps                     # STATUS 显示 healthy
podman logs --tail 50 worklog-reporter
```

## 9. 配置项说明

全部集中在 `.env`，容器启动时注入。

| 变量                      | 默认            | 说明                                                                                                |
| ----------------------- | ------------- | ------------------------------------------------------------------------------------------------- |
| `APP_NAME`              | 工时周报          | 应用名称                                                                                              |
| `APP_TIMEZONE`          | Asia/Shanghai | 业务时区，决定日期归属与统计口径                                                                                  |
| `DATA_DIR`              | ./data        | 数据目录，存放自动生成的加密主密钥                                                                                 |
| `DATABASE_URL`          | —             | 数据库连接串；留空则用 `DATA_DIR` 下的 SQLite。MySQL 形如 `mysql+pymysql://user:pwd@host:3306/db?charset=utf8mb4` |
| `APP_SECRET`            | —             | 主密钥，用于加密令牌与签发会话；留空则自动生成并存到 `DATA_DIR/secret.key`                                                  |
| `APP_PASSWORD`          | —             | 访问密码；留空不启用登录。也可在「设置」页面设置                                                                          |
| `CORS_ORIGINS`          | *             | 允许的跨域来源，多个用逗号分隔                                                                                   |
| `LLM_BASE_URL`          | —             | 大模型接口地址，OpenAI 兼容格式；未带 `/v1` 会自动补全                                                                |
| `LLM_API_KEY`           | —             | 大模型令牌                                                                                             |
| `LLM_MODEL`             | —             | 模型名称                                                                                              |
| `LLM_TEMPERATURE`       | 0.3           | 采样温度                                                                                              |
| `SYNC_INTERVAL_MINUTES` | 30            | 定时同步间隔（分钟），最小 5                                                                                   |
| `MAX_PAGES_PER_SYNC`    | 20            | 单次同步每个仓库最大拉取页数                                                                                    |
| `FETCH_COMMIT_FILES`    | true          | 是否拉取文件变更明细                                                                                        |
| `REQUEST_TIMEOUT`       | 30            | 对外请求超时（秒）                                                                                         |
| `APP_PORT`              | 8000          | 宿主机映射端口，仅 compose 生效                                                                              |
| `APP_DATABASE_URL`      | —             | compose 场景下的数据库连接串；留空则容器内用 SQLite                                                                 |
| `DOCKER_DATABASE_URL`   | —             | compose 场景下覆盖容器内的 `DATABASE_URL`                                                                  |

页面「设置」中的配置优先级高于环境变量。

## 10. 访问内网 Git 服务

内网 Gitea/Gitee 常落在 `10.x` 网段，而 Podman 默认网桥使用 `10.88.0.0/16`。网段重叠时容器访问内网会被网桥截走，表现为 `No route to host`。

先确认冲突：

```bash
podman machine ssh -- ip route | grep 10.88
```

若内网地址落在该网段，补一条更精确的路由：

```bash
# Linux / macOS
bash scripts/podman_lan_route.sh 10.88.192.0/24

# Windows
.\scripts\podman_lan_route.ps1 -Cidr 10.88.192.0/24
```

该路由写在虚拟机内，重启 podman machine 后失效，需要重新执行。

## 11. 升级

```bash
# 1. 备份
podman exec worklog-reporter sh -c 'cat /app/data/secret.key' > secret.key.bak
mysqldump -u worklog -p daylife > daylife-$(date +%Y%m%d).sql

# 2. 换镜像
podman pull ascr.asun.cloud/visitor/worklog-reporter:1.1.0
podman-compose -f docker-compose.yml up -d

# 3. 校验
curl http://127.0.0.1:8000/api/health
```

数据库表结构由应用启动时自动补齐，新增字段无需手工执行 DDL。

## 12. 换库与数据迁移

不想重新配置时，直接把数据搬过去。页面入口在「设置 → 数据」：

- **导出 JSON 备份**：下载一份全量快照
- **导入 JSON**：用快照覆盖当前库（有二次确认）
- **迁移到 SQLite**：库与库之间直接复制（仅在当前是 MySQL 时出现）

命令行同样支持：

```bash
# MySQL -> 本地 SQLite
docker exec worklog-reporter python -m app.cli migrate --to-url ''

# 导出 JSON 备份
docker exec worklog-reporter python -m app.cli export --output backup.json
docker cp worklog-reporter:/app/backup.json ./

# 从备份恢复
docker cp backup.json worklog-reporter:/app/backup.json
docker exec worklog-reporter python -m app.cli import --input /app/backup.json
```

迁移会复制全部业务表。迁移完成后地址写入 `data/database.url`，该文件优先级高于环境变量，  
重启后依然生效；想改回环境变量配置，删除该文件或在向导里点「改回环境变量配置」。

令牌与大模型密钥按 `APP_SECRET` 派生密钥加密，换库或换机器时请保持 `APP_SECRET` 一致。

## 13. 备份与恢复

需要备份三样东西：

| 内容   | 位置                                        | 说明                 |
| ---- | ----------------------------------------- | ------------------ |
| 业务数据 | MySQL 库 `daylife`                         | 仓库、提交、工作记录、报告、审查记录 |
| 主密钥  | `.env` 的 `APP_SECRET` 或 `data/secret.key` | 丢了令牌就解不开           |
| 配置文件 | `.env`                                    | 大模型地址、访问密码等        |

恢复：

```bash
mysql -u worklog -p daylife < daylife-20260113.sql
# 还原 .env 与 data/secret.key
podman-compose -f docker-compose.yml up -d
```

## 14. 常见问题

| 现象                          | 原因与处理                                                              |
| --------------------------- | ------------------------------------------------------------------ |
| 容器反复重启，日志报 `Unknown column` | 数据库结构过旧。确认镜像为最新版本，启动时会自动补列；必要时执行 `podman logs` 查看补齐结果              |
| 页面提示仓库令牌为空                  | `APP_SECRET` 与加密时不一致。从备份还原 `APP_SECRET` 或 `data/secret.key`        |
| 同步报 `No route to host`      | 内网网段与 podman 网桥冲突，见第 7 节                                           |
| 同步报 404 / 找不到仓库             | 平台选错或令牌无该私有仓库权限。Gitea 对无权限的私有仓库也返回 404                             |
| 报告生成失败，提示未配置大模型             | 在「设置 → 大模型」填写接口地址与模型名，或检查 `.env` 的 `LLM_*`                         |
| 代码审查一直排队                    | 后台任务队列按序执行，单个提交审查需 1～3 分钟；服务重启时未完成的任务会被标记为失败                       |
| 服务监控报「No route to host」     | 监控目标在内网且跨网段，见第 10 节补路由                                             |
| 迁移后令牌读不出来                   | 迁移时 `APP_SECRET` 变了，密文无法解密，需重新填写令牌                                 |
| 企业微信收不到告警                   | 先在「设置 → 告警」确认 webhook 地址；首次检查不告警，只有状态跃迁才推送                         |
| 页面中文显示为方块或字体缺失              | 界面字体依赖 Google Fonts 的 JetBrains Mono（拉丁字符），中文回落到系统字体；完全离线环境建议自托管字体 |
| 端口被占用                       | 改 `.env` 的 `APP_PORT`，或在 compose 中映射其他宿主机端口                        |

## 15. 服务监控配置

在「设置 → 告警」填入企业微信群机器人的 webhook 地址（群机器人 → 复制 webhook 地址）：

```
https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxx
```

然后在「服务监控」页新建监控目标，填写服务地址后点「自动探测」挑选健康检查路径。

## 16. 常用命令

```bash
podman ps                                    # 容器状态
podman logs -f worklog-reporter              # 实时日志
podman exec worklog-reporter python -c "print('ok')"
podman-compose -f docker-compose.yml logs -f app
podman-compose -f docker-compose.yml down
podman-compose -f docker-compose.yml up -d --build
```

进入容器：

```bash
podman exec -it worklog-reporter sh
```
