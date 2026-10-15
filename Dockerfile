FROM python:3.11-slim

WORKDIR /app

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5

# build context = itss-steeltech-back/（本目录 .dockerignore 生效）
COPY requirements.txt .
COPY db ./db

# 先装构建依赖，避免 -e ./db 在隔离环境里再拉 setuptools 时镜像超时
RUN pip install --upgrade pip setuptools wheel \
    -i ${PIP_INDEX_URL} --trusted-host ${PIP_TRUSTED_HOST} \
 && pip install --no-build-isolation -r requirements.txt gunicorn \
    -i ${PIP_INDEX_URL} --trusted-host ${PIP_TRUSTED_HOST}

COPY . .

RUN sed -i 's/\r$//' docker-entrypoint.sh \
    && chmod +x docker-entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["./docker-entrypoint.sh"]
