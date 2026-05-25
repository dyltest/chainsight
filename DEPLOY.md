# ChainSight — 腾讯云部署指南

## 项目架构

```
用户浏览器
    │
    ▼
┌─────────────────────────────┐
│  腾讯云轻量应用服务器 (Lighthouse)  │
│                             │
│  ┌───────────────────────┐  │
│  │  Docker: chainsight    │  │
│  │  ┌─────────────────┐  │  │
│  │  │  FastAPI :8000   │  │  │
│  │  │                 │  │  │
│  │  │  /api/tokens ───┼──┼──┼──► CoinGecko API
│  │  │  /api/global ───┼──┼──┼──► (后端代理, 30s缓存)
│  │  │  /api/ohlc/*  ──┼──┼──┼──►
│  │  │                 │  │  │
│  │  │  / → index.html │  │  │
│  │  └─────────────────┘  │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
```

- **前端**：纯 HTML + ECharts，由 FastAPI 直接托管
- **后端**：FastAPI 代理 CoinGecko API，内置 30 秒 TTL 缓存，避免触发 CoinGecko 免费层限流
- **部署**：Docker 容器化，一键启动

## 项目文件结构

```
chainsight-deploy/
├── backend/
│   ├── main.py              # FastAPI 后端（API代理 + 缓存 + 静态文件服务）
│   ├── requirements.txt     # Python 依赖
│   └── Dockerfile            # 后端 Docker 镜像
├── static/
│   └── index.html            # 前端页面（5 个模块 Dashboard）
├── docker-compose.yml        # 一键编排
└── DEPLOY.md                 # 本文件
```

---

## 一、准备工作

### 1.1 购买腾讯云轻量应用服务器

1. 登录 [腾讯云控制台](https://console.cloud.tencent.com/lighthouse)
2. 点击「新建」→ 选择配置：
   - **地域**：建议选「硅谷」或「香港」（CoinGecko API 在海外，延迟更低）
   - **镜像**：选「Docker 基础镜像」或「Ubuntu 22.04」
   - **套餐**：2核2G 即可满足 Demo 需求（约 ¥50/月）
3. 购买完成后，记录 **公网 IP**

### 1.2 防火墙配置

在轻量应用服务器控制台 →「防火墙」→ 添加规则：

| 端口 | 协议 | 说明 |
|------|------|------|
| 8000 | TCP | ChainSight 服务端口 |
| 22   | TCP | SSH 远程管理 |

### 1.3 连接服务器

```bash
ssh root@<你的公网IP>
```

---

## 二、部署步骤

### 2.1 上传项目文件

在**本地电脑**上，将 `chainsight-deploy/` 整个目录上传到服务器：

```bash
# 方式一：scp 上传
scp -r chainsight-deploy/ root@<公网IP>:/root/chainsight-deploy/

# 方式二：在服务器上 git clone（如果推到了 Git 仓库）
```

### 2.2 安装 Docker（如镜像未预装）

```bash
# Ubuntu
curl -fsSL https://get.docker.com | bash

# 安装 docker-compose
apt install -y docker-compose

# 启动 Docker
systemctl enable docker && systemctl start docker
```

### 2.3 构建并启动

```bash
cd /root/chainsight-deploy/

# 构建镜像 + 启动容器（后台运行）
docker-compose up -d --build

# 查看日志确认启动成功
docker-compose logs -f

# 看到以下输出表示成功：
# Uvicorn running on http://0.0.0.0:8000
```

### 2.4 验证服务

```bash
# 健康检查
curl http://localhost:8000/api/health
# → {"status":"ok","ts":1716658800.123}

# 测试 API
curl http://localhost:8000/api/tokens?per_page=3
# → 返回 BTC/ETH/BNB 实时数据

# 浏览器访问
# http://<你的公网IP>:8000
```

---

## 三、可选：绑定域名 + HTTPS

### 3.1 DNS 解析

在你的域名管理后台添加 A 记录：
- 主机记录：`chainsight`（或 `@`）
- 记录值：`<服务器公网IP>`

### 3.2 使用 Nginx 反向代理（推荐）

在服务器上安装 Nginx：

```bash
apt install -y nginx
```

创建配置文件 `/etc/nginx/sites-available/chainsight`：

```nginx
server {
    listen 80;
    server_name chainsight.yourdomain.com;  # 替换为你的域名

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

启用配置：

```bash
ln -s /etc/nginx/sites-available/chainsight /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 3.3 配置 HTTPS（免费证书）

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d chainsight.yourdomain.com
```

---

## 四、日常运维

### 常用命令

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f --tail=100

# 重启服务
docker-compose restart

# 更新前端（修改 index.html 后无需重新构建）
# 直接替换 static/index.html，然后重启容器
docker-compose restart

# 更新后端代码后重新构建
docker-compose up -d --build

# 停止服务
docker-compose down
```

### API 缓存说明

- 后端内置 30 秒 TTL 内存缓存
- CoinGecko 免费层限制：30 次/分钟
- 当前配置 10 个代币 + global + OHLC = 每次刷新 3 次 API 调用
- 30 秒缓存 = 每分钟最多 6 次上游请求，远低于限制

---

## 五、项目本地开发

如果需要在本地测试：

```bash
cd chainsight-deploy/

# 安装 Python 依赖
pip install -r backend/requirements.txt

# 启动 FastAPI
cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 浏览器打开 http://localhost:8000
```

---

## 六、成本预估

| 项目 | 月费 |
|------|------|
| 腾讯云轻量服务器 2核2G | ~¥50 |
| CoinGecko API | 免费 |
| 域名（可选） | ~¥5 |
| **合计** | **~¥55/月** |

---

## 七、常见问题

**Q: 页面打开后数据显示 "CACHED"？**
A: 说明后端无法连接 CoinGecko。检查服务器是否能访问外网：`curl https://api.coingecko.com/api/v3/ping`

**Q: 如何修改缓存时间？**
A: 编辑 `backend/main.py` 中的 `CACHE_TTL = 30`，改为需要的秒数，重新构建即可。

**Q: 能否支持更多代币？**
A: 前端 URL 参数 `per_page=10` 可改为 50，但注意 CoinGecko 免费层限制。
