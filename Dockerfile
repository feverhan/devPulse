# 构建参数：基础镜像仓库，国内网络可改为 docker.m.daocloud.io/library
ARG REGISTRY=docker.io/library
# PyPI 索引，国内网络可换镜像源
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple

# ---------- 前端构建 ----------
FROM ${REGISTRY}/node:20-alpine AS web
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 后端运行 ----------
FROM ${REGISTRY}/python:3.12-slim
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai \
    PYTHONPATH=/app/backend

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --timeout 60 --retries 5 \
    -i ${PIP_INDEX_URL} \
    -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY --from=web /build/dist /app/static

ENV DATA_DIR=/app/data
VOLUME ["/app/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/backend"]