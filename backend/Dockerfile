FROM python:3.11-slim

LABEL maintainer="xin-yuan-invest"
LABEL description="新源的Invest工具 - Python后端服务"

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖（部分Python包编译需要）
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装（利用Docker缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建日志和数据目录
RUN mkdir -p /app/logs /app/pdf /app/data

# 暴露端口
EXPOSE 8002

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/')" || exit 1

# 启动命令（生产环境不使用 --reload）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
