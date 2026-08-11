# ==============================
# Stage 1: Build React frontend
# ==============================

FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY . .

RUN npm run build


# ==============================
# Stage 2: Nginx
# ==============================

FROM nginx:alpine

# 移除 Nginx 預設網站
RUN rm -rf /usr/share/nginx/html/*

# 複製 React build
COPY --from=builder /app/dist /usr/share/nginx/html

# 複製 PrintCheck Nginx 設定
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
