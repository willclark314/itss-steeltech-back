# steeltech-db

ITSS Steeltech 系统的**数据库层 Python 包**，位于后端仓库的 `db/` 目录。将 SQLAlchemy 模型、连接配置、权限目录、系统默认值与种子数据集中管理，供后端以可编辑依赖方式引用。

## 目录结构

```
db/                         # 位于 itss-steeltech-back/db/
├── pyproject.toml          # 包定义与依赖（Flask-SQLAlchemy、Flask-Migrate、PyMySQL 等）
├── datas/
│   ├── schema.sql          # SQLite 开发库 DDL（表结构、索引、约束）
│   └── steeltech.db        # 默认 SQLite 数据库文件（运行时生成，通常不入库）
├── scripts/
│   ├── setup_db.py         # 创建 MySQL 数据库（若不存在）
│   ├── init_db.py          # 初始化脚本（依赖后端 create_app，供后端仓库调用）
│   └── export_to_excel.py  # 全表导出为 Excel（发给同事清理数据）
└── steeltech_db/           # 主包
    ├── __init__.py         # 统一导出模型、配置、种子函数
    ├── config.py           # 数据库连接配置（SQLite / MySQL）
    ├── extensions.py       # db、migrate 单例
    ├── defaults.py         # 本地工作路径等系统默认值
    ├── permission_catalog.py  # 页面权限目录（与前端路由对齐）
    ├── seed.py             # 建表、迁移补丁、种子数据
    └── models/             # SQLAlchemy ORM 模型
        ├── personnel.py
        ├── role.py
        ├── project.py
        ├── contact.py
        ├── monthly_rest.py
        ├── system_setting.py
        ├── account_password.py
```

## 设计思路

本包把「数据结构」与「应用业务」分离：

| 职责 | 所在位置 | 说明 |
|------|----------|------|
| 表结构与 ORM | `models/`、`datas/schema.sql` | 单一数据源定义实体与关系 |
| 连接与后端切换 | `config.py` | 通过环境变量在 SQLite / MySQL 间切换 |
| 权限元数据 | `permission_catalog.py` | 按前端页面定义权限 code，写入 `permissions` 表 |
| 系统默认配置 | `defaults.py` | 本地工作路径（IP、路径模板）的默认值与校验 |
| 初始化与种子 | `seed.py` | 建表、增量补丁、开发账号、示例数据 |
| Flask 扩展实例 | `extensions.py` | `db`、`migrate` 由后端 `init_app` 绑定 |

后端 `requirements.txt` 通过 `-e ./db` 本地安装；启动时调用 `ensure_schema` / `seed_if_empty` 完成数据库就绪。

## 数据库后端

通过环境变量 `DATABASE_BACKEND` 选择（默认 `sqlite`）：

### SQLite（本地开发）

- 默认路径：`datas/steeltech.db`（可用 `SQLITE_DATABASE_PATH` 覆盖）
- 首次启动时，`bootstrap_sqlite_file` 若文件不存在，会执行 `datas/schema.sql` 建表
- 认证使用 `account_passwords` + `personnel` 工号/账号体系

### MySQL（生产）

- 连接参数：`MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DATABASE`
- 使用 `scripts/setup_db.py` 预先创建库
- 表结构由 SQLAlchemy `db.create_all()` + Flask-Migrate 维护
- 认证使用 `account_passwords` + `personnel` 工号/账号体系（与 SQLite 开发一致）

## 数据模型概览

```
personnel ──┬── role_personnel ── roles ── role_permissions ── permissions
            ├── project_personnel ── projects ── project_natures
            └── monthly_rest

contact_forms ──┬── contact_form_projects ── projects
                ├── contact_form_pdfs
                └── contact_form_project_cancellations

system_settings          # 键值配置（如 local_work_path）
account_passwords        # 登录密码
```

### 核心业务表

| 表 | 模型 | 说明 |
|----|------|------|
| `personnel` | `Personnel` | 人员档案（工号、班组、证件、联系方式等） |
| `roles` / `permissions` | `Role` / `Permission` | RBAC：角色与页面级操作权限 |
| `role_permissions` | `RolePermission` | 角色 ↔ 权限 |
| `role_personnel` | `RolePersonnel` | 角色 ↔ 人员 |
| `projects` | `Project` | 项目主表（含 `local_work_path`） |
| `project_natures` | `ProjectNature` | 项目性质：`design` / `detail` |
| `project_personnel` | `ProjectPersonnel` | 项目参与人员 |
| `contact_forms` | `ContactForm` | 联系单（支持主单/补充/修订/跟进/取消等关系树） |
| `contact_form_projects` | `ContactFormProject` | 联系单与项目多对多，含来源语义 |
| `contact_form_pdfs` | `ContactFormPdf` | 联系单 PDF 附件 |
| `contact_form_project_cancellations` | — | 取消联系单对项目关联的审计记录 |
| `monthly_rest` | `MonthlyRest` | 人员月休计划（`rest_days` 为 JSON 日期数组） |
| `system_settings` | `SystemSetting` | 全局配置键值存储 |
| `account_passwords` | `AccountPassword` | 账号/工号登录密码 |

模型 `to_dict()` 输出字段名采用 **camelCase**，与前端 API 约定一致。

## 权限体系

`permission_catalog.py` 中的 `PAGE_DEFINITIONS` 定义前端各页面及允许的操作（`view` / `create` / `update` / `delete`），`build_permission_catalog()` 生成权限列表，code 格式为 `{page_key}:{action}`（如 `contact:create`）。

启动时 `sync_permission_catalog()` 会：

1. 将目录中新增的权限写入 `permissions` 表（已有 code 不覆盖）
2. 确保 `admin` 角色拥有系统设置相关权限
3. 确保 `detailer`（细化工程师）角色存在，并仅分配业务只读权限

内置角色：

| code | 名称 | 权限范围 |
|------|------|----------|
| `admin` | 系统管理员 | 全部页面权限 |
| `detailer` | 细化工程师 | 首页、关于、联系单/项目/工作安排仅查看 |

## 种子与启动流程

后端 `create_app()` 在应用上下文中依次执行：

```
bootstrap_sqlite_file()     # SQLite：不存在则执行 schema.sql
        ↓
ensure_schema()
  ├── db.create_all()       # 补齐 ORM 定义的表
  ├── migrate_contact_form_relations()  # SQLite 增量 ALTER（联系单关系字段）
  ├── sync_permission_catalog()
  ├── ensure_system_settings()          # 写入 local_work_path 默认配置
  └── seed_default_monthly_rest()       # 为在职人员补全当月周日休息
        ↓
seed_if_empty()             # 人员表为空时写入示例人员、角色、项目、账号
ensure_dev_users()          # 确保 DEV 测试账号存在（后端 init_db 可选调用）
```

### 开发测试账号（`DEV_USER_PROFILES`）

| 账号 | 工号 | 角色 |
|------|------|------|
| `admin` | `42609901` | 系统管理员 |
| `user` | `42609903` | 细化工程师 |

默认密码由后端 `DEFAULT_LOGIN_PASSWORD` 控制（默认 `123456`）。

## 系统配置：本地工作路径

`defaults.py` 定义 `local_work_path` 配置的默认值与规范化逻辑：

- 文件服务器 IP 列表（`ips`）
- 设计/细化路径模板（`pathPatterns.design` / `pathPatterns.detail`）

配置持久化在 `system_settings` 表，`key = local_work_path`，`value` 为 JSON。后端 `system_config_service` 与本包共享 `normalize_*` 函数。

## 安装与使用

### 作为依赖安装（推荐）

在后端仓库中已配置：

```bash
pip install -e ./db
```

### 环境变量

推荐设置单一连接串 `DATABASE_URL`（或 `SQLALCHEMY_DATABASE_URI`），未设置时使用下方 legacy 分散变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | （空） | 优先；如 `sqlite:///.../steeltech.db` 或 `mysql+pymysql://...` |
| `DATABASE_BACKEND` | `sqlite` | legacy：`sqlite` 或 `mysql` |
| `SQLITE_DATABASE_PATH` | `datas/steeltech.db` | legacy：SQLite 文件路径 |
| `MYSQL_HOST` | `127.0.0.1` | legacy：MySQL 主机 |
| `MYSQL_PORT` | `3306` | legacy：MySQL 端口 |
| `MYSQL_USER` | `root` | legacy：MySQL 用户 |
| `MYSQL_PASSWORD` | （空） | legacy：MySQL 密码 |
| `MYSQL_DATABASE` | `itss_steeltech` | legacy：MySQL 库名 |

### 初始化 MySQL 库

```bash
python scripts/setup_db.py
```

### 导出数据库为 Excel

用于把当前库全表导出成 `.xlsx`，发给同事做数据清理核对。依赖：`pandas`、`openpyxl`、以及本包已有的 SQLAlchemy / PyMySQL。

在 `itss-steeltech-back/db` 目录执行：

```bash
python scripts/export_to_excel.py
```

指定输出路径：

```bash
python scripts/export_to_excel.py --out D:/share/steeltech.xlsx
```

指定连接串（可选，一般不用）：

```bash
python scripts/export_to_excel.py --url "mysql+pymysql://user:pass@127.0.0.1:3306/itss_steeltech?charset=utf8mb4"
```

**连接串解析顺序：**

1. 命令行 `--url`
2. 环境变量 `DATABASE_URL` / `SQLALCHEMY_DATABASE_URI`
3. 后端仓库 `.env` 中的 `DATABASE_URL`
4. 默认本地 MySQL：`mysql+pymysql://root:123456@127.0.0.1:3306/itss_steeltech?charset=utf8mb4`

**输出说明：**

| 项 | 说明 |
|----|------|
| 默认目录 | `datas/exports/` |
| 默认文件名 | `itss_steeltech_export_YYYYMMDD_HHMMSS.xlsx` |
| Sheet 结构 | 首页 `_目录`（表名 / 行数 / 列数）+ 每张业务表一个 Sheet |
| 跳过表 | `backup_records`、`alembic_version`（备份与迁移元数据） |
| 脱敏 | `account_passwords.password` 导出为 `***` |

导出文件体积通常较小（全库约数百 KB～数 MB），可直接通过邮件或网盘分享。PDF / 图片等附件仍以路径字段记录在表中，不会把二进制文件打进 Excel。

### 在后端代码中引用

```python
from steeltech_db.extensions import db
from steeltech_db.models import Personnel, Project, Role
from steeltech_db.seed import ensure_schema, seed_if_empty
from steeltech_db.permission_catalog import build_permission_catalog
from steeltech_db.defaults import normalize_local_work_path_config
```

## 与前后端的关系

```
itss-steeltech-back/
├── app/                 # routes / services / 业务逻辑
└── db/                  # models / seed / defaults（pip -e ./db）
         │
         └──────── API (camelCase) ──────>  itss-steeltech-front
```

- **本包**：定义「存什么、怎么连、初始数据是什么」
- **后端**：定义「怎么读写、鉴权、文件存储、API」
- **前端**：消费 API；权限页面定义与 `PAGE_DEFINITIONS` 保持对齐

## 维护说明

- 新增表或字段：同步修改 `models/` 与 `datas/schema.sql`；SQLite 存量库可通过 `seed.py` 中的 `migrate_*` 函数做增量补丁
- 新增前端页面权限：在 `permission_catalog.py` 的 `PAGE_DEFINITIONS` 中追加，重启后 `sync_permission_catalog` 自动入库
