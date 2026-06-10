# ===== 阶段1: 构建 =====
FROM node:18-alpine AS builder

LABEL maintainer="xin-yuan-invest"
LABEL description="新源的Invest工具 - 前端构建"

WORKDIR /app

# 复制依赖文件（利用Docker缓存层）
COPY package.json package-lock.json ./

# 安装依赖
RUN npm ci

# 复制源码并构建
COPY . .
RUN npm run build

# ===== 阶段2: 运行 =====
FROM nginx:alpine

# 复制构建产物到nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制nginx配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
