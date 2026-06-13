# ITSS Steeltech 后端

Flask 后端服务，连接本机 MySQL，为 [itss-steeltech-front](../itss-steeltech-front) 前端提供 API。

## 技术栈

| 依赖 | 版本 | 说明 |
|------|------|------|
| Flask | 3.1.0 | Web 框架 |
| Flask-SQLAlchemy | 3.1.1 | ORM |
| Flask-JWT-Extended | 4.7.1 | JWT 认证 |
| Flask-CORS | 5.0.1 | 跨域支持 |
| Flask-Migrate | 4.1.0 | 数据库迁移 |
| PyMySQL | 1.1.1 | MySQL 驱动 |
| cryptography | ≥42.0.0 | MySQL 8 认证支持 |
| python-dotenv | 1.1.0 | 环境变量加载 |

## 快速开始

### 1. 创建虚拟环境并安装依赖

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

若出现 `check_hostname requires server_hostname`，通常是本机代理（如 Clash `127.0.0.1:7897`）与 pip 冲突。可改用：

```powershell
.\install.ps1
```

或手动设置后再安装：

```powershell
$env:NO_PROXY='*'
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填写本机 MySQL 密码：

```powershell
copy .env.example .env
```

### 3. 初始化数据库

```powershell
python setup_db.py
python init_db.py
```

默认管理员账号：`admin` / `123456`

### 4. 启动后端

```powershell
python run.py
```

服务地址：http://localhost:5000

## 使用 Docker 运行

需要已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（或 Docker Engine + Compose 插件）。

### 方式一：SQLite（推荐，开箱即用）

默认使用容器内 SQLite，数据持久化在 Docker 卷 `backend-instance` 中。首次启动会自动建表并写入种子数据。

```powershell
cd itss-steeltech-back
docker compose up --build
```

后台运行：

```powershell
docker compose up --build -d
```

验证：

```powershell
curl http://localhost:5000/api/health
```

默认登录账号：`admin` / `123456`（可通过环境变量 `DEFAULT_LOGIN_PASSWORD` 修改）。

停止并删除容器（保留数据卷）：

```powershell
docker compose down
```

### 方式二：MySQL

同时启动 MySQL 8 与后端，适合需要独立数据库服务的场景：

```powershell
$env:DATABASE_BACKEND="mysql"
docker compose --profile mysql up --build
```

MySQL 连接信息（可通过环境变量覆盖）：

| 项 | 默认值 |
|----|--------|
| 主机（容器内） | `mysql` |
| 主机（本机访问） | `127.0.0.1` |
| 端口 | `3306` |
| 用户 | `root` |
| 密码 | `steeltech` |
| 数据库 | `itss_steeltech` |

示例：自定义密钥与数据库密码后启动：

```powershell
$env:SECRET_KEY="your-secret-key"
$env:MYSQL_PASSWORD="your-mysql-password"
$env:DATABASE_BACKEND="mysql"
docker compose --profile mysql up --build -d
```

### 常用 Docker 命令

| 命令 | 说明 |
|------|------|
| `docker compose logs -f backend` | 查看后端日志 |
| `docker compose restart backend` | 重启后端 |
| `docker compose down -v` | 停止并删除容器与数据卷（清空数据库） |
| `docker compose build --no-cache` | 无缓存重新构建镜像 |

### Docker 相关文件

| 文件 | 说明 |
|------|------|
| `Dockerfile` | 后端镜像构建定义 |
| `docker-compose.yml` | 编排后端与可选 MySQL 服务 |
| `docker-entrypoint.sh` | 容器启动脚本（MySQL 模式下先建库，再用 gunicorn 启动） |
| `.dockerignore` | 构建上下文排除项 |

## 与前端联调

前端开发服务器（Vite，端口 5173）通过代理将 `/api` 请求转发至本后端。

1. 启动后端：`python run.py`
2. 启动前端：在 `itss-steeltech-front` 目录执行 `npm run dev`
3. 访问 http://localhost:5173/login 进行登录

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SECRET_KEY` | — | Flask 密钥 |
| `JWT_SECRET_KEY` | 同 SECRET_KEY | JWT 签名密钥 |
| `MYSQL_HOST` | `127.0.0.1` | MySQL 主机 |
| `MYSQL_PORT` | `3306` | MySQL 端口 |
| `MYSQL_USER` | `root` | MySQL 用户名 |
| `MYSQL_PASSWORD` | — | MySQL 密码 |
| `MYSQL_DATABASE` | `itss_steeltech` | 数据库名 |
| `CORS_ORIGINS` | `http://localhost:5173,...` | 允许跨域的前端地址 |

配置文件：`.env`、`.env.example`

## API

### 健康检查

```
GET /api/health
```

响应：

```json
{ "status": "ok" }
```

### 登录

```
POST /api/auth/login
Content-Type: application/json
```

请求体：

```json
{
  "username": "admin",
  "password": "123456"
}
```

响应体：

```json
{
  "token": "eyJ..."
}
```

## 项目结构

```
itss-steeltech-back/
├── app/                        # 应用主包
│   ├── __init__.py             # 应用工厂，注册扩展、蓝图与 CORS
│   ├── config.py               # 配置类（MySQL / JWT / CORS）
│   ├── extensions.py           # db、jwt、migrate、cors 扩展实例
│   ├── models/                 # 数据模型
│   │   ├── __init__.py
│   │   └── user.py             # 用户模型（密码哈希）
│   └── routes/                 # 路由蓝图
│       ├── __init__.py
│       └── auth.py             # 认证接口 POST /api/auth/login
├── run.py                      # 启动入口（0.0.0.0:5000）
├── setup_db.py                 # 创建 MySQL 数据库
├── init_db.py                  # 建表并写入默认管理员
├── install.ps1                 # 绕过系统代理安装依赖（Windows）
├── requirements.txt            # Python 依赖清单
├── Dockerfile                  # Docker 镜像构建
├── docker-compose.yml          # Docker Compose 编排
├── docker-entrypoint.sh        # 容器启动入口
├── .dockerignore               # Docker 构建排除项
├── .env.example                # 环境变量模板
├── .env                        # 本地环境变量（不提交 Git）
├── .gitignore
└── README.md
```

### 模块说明

| 路径 | 职责 |
|------|------|
| `app/__init__.py` | `create_app()` 工厂函数，加载 `.env`、初始化扩展、注册 `/api/auth` 蓝图与 `/api/health` |
| `app/config.py` | 从环境变量读取 MySQL 连接串、JWT 密钥、CORS 白名单 |
| `app/extensions.py` | 集中声明 SQLAlchemy、JWT、Migrate、CORS 单例，避免循环导入 |
| `app/models/user.py` | `users` 表：id、username、password_hash、created_at |
| `app/routes/auth.py` | 校验用户名密码，签发 JWT Token |
| `setup_db.py` | 连接 MySQL 服务器，创建 `itss_steeltech` 库（若不存在） |
| `init_db.py` | `db.create_all()` 建表，创建默认账号 admin/123456 |
| `install.ps1` | 设置 `NO_PROXY=*` 后执行 pip install，解决 Clash 代理导致的 SSL 错误 |

---

## 创建历史

### v0.1.0 — 2026-06-07

**初始版本**，在空目录中搭建 Flask + MySQL 后端，对接前端登录接口。

#### 创建步骤

1. 初始化 Flask 应用工厂结构（`app/` 包 + `run.py` 入口）
2. 配置 Flask-SQLAlchemy 连接本机 MySQL（PyMySQL 驱动）
3. 实现 `User` 模型与密码哈希存储（Werkzeug）
4. 实现 `POST /api/auth/login`，使用 Flask-JWT-Extended 签发 Token
5. 配置 Flask-CORS，允许前端 `localhost:5173` 跨域访问
6. 编写 `setup_db.py`、`init_db.py` 数据库初始化脚本
7. 添加 `.env.example`、`.gitignore`、`requirements.txt`
8. 在前端 `vite.config.js` 中配置 `/api` → `http://localhost:5000` 代理

#### 初始功能

- 用户登录（JWT Token）
- 健康检查接口
- 默认管理员账号初始化

#### 新增文件

| 路径 | 说明 |
|------|------|
| `app/__init__.py` | 应用工厂 |
| `app/config.py` | 配置 |
| `app/extensions.py` | 扩展实例 |
| `app/models/user.py` | 用户模型 |
| `app/routes/auth.py` | 登录路由 |
| `run.py` | 启动入口 |
| `setup_db.py` | 创建数据库 |
| `init_db.py` | 初始化表与用户 |
| `requirements.txt` | 依赖清单 |
| `.env.example` | 环境变量模板 |

---

## 安装记录

### 2026-06-07 — 首次安装

#### 环境

| 项 | 值 |
|----|-----|
| 操作系统 | Windows 10 |
| Python | 3.9 |
| MySQL | 本机 127.0.0.1:3306 |
| 前端联调地址 | http://localhost:5173 |

#### 安装步骤

```powershell
# 1. 创建虚拟环境
cd c:\Users\willc\Documents\github\itss-steeltech-back
python -m venv venv

# 2. 安装依赖（遇代理问题时加 NO_PROXY）
$env:NO_PROXY='*'
.\venv\Scripts\pip install -r requirements.txt

# 3. 配置环境变量
copy .env.example .env
# 编辑 .env 中的 MYSQL_PASSWORD

# 4. 初始化数据库
.\venv\Scripts\python setup_db.py
.\venv\Scripts\python init_db.py

# 5. 启动服务
.\venv\Scripts\python run.py
```

#### 已安装依赖

```
Flask==3.1.0
Flask-SQLAlchemy==3.1.1
Flask-JWT-Extended==4.7.1
Flask-CORS==5.0.1
Flask-Migrate==4.1.0
PyMySQL==1.1.1
cryptography>=42.0.0
python-dotenv==1.1.0
Werkzeug==3.1.3
```

#### 遇到的问题与处理

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `check_hostname requires server_hostname` | 本机 Clash 代理（`127.0.0.1:7897`）被 Python 自动读取，与 pip HTTPS 请求冲突 | 安装前设置 `$env:NO_PROXY='*'`，或使用 `install.ps1` |
| `'cryptography' package is required` | MySQL 8 默认使用 `caching_sha2_password` 认证 | 在 `requirements.txt` 中添加 `cryptography` 依赖 |
| `Access denied for user 'root'@'localhost'` | `.env` 中 `MYSQL_PASSWORD` 与本机 MySQL 密码不一致 | 修改 `.env` 后重新执行 `setup_db.py` 和 `init_db.py` |

#### 辅助脚本

新增 `install.ps1`，封装 `NO_PROXY` 设置，后续安装可直接运行：

```powershell
.\install.ps1
```
