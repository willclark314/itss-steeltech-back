# 数据库定时备份 — 设计方案

> 适用于 ITSS Steeltech 管理系统（Flask + SQLite/MySQL + Vue 3）

---

## 1. 整体架构

```
┌──────────────┐     REST API     ┌──────────────┐    APScheduler    ┌──────────────┐
│  Vue 前端    │ ◄──────────────► │  Flask 后端  │ ◄───────────────► │  SQLite 文件 │
│  (管理界面)  │                  │  (备份服务)  │   定时触发拷贝    │  / MySQL DB  │
└──────────────┘                  └──────┬───────┘                   └──────────────┘
                                         │
                                         ▼ 写入
                                   ┌──────────┐
                                   │ 备份目录 │
                                   │ datas/   │
                                   │ backups/ │
                                   └──────────┘
```

**核心思路：** 在 Flask 后端集成 APScheduler 轻量级调度器，按配置的周期自动执行数据库拷贝/导出；前端提供配置管理与备份历史查看界面。无需引入 Celery/Redis 等重量级消息队列。

---

## 2. 数据库设计

### 2.1 新增表 `backup_records`

存放于 `itss-steeltech-db/steeltech_db/models/`，通过 SQLAlchemy ORM 管理。

| 字段            | 类型         | 约束                        | 说明                                      |
| --------------- | ------------ | --------------------------- | ----------------------------------------- |
| `id`            | INTEGER      | PK, AUTOINCREMENT           | 自增主键                                  |
| `filename`      | VARCHAR(256) | NOT NULL                    | 备份文件名，如`backup_20260629_020000.db` |
| `file_size`     | INTEGER      | NOT NULL                    | 文件大小（字节）                          |
| `status`        | VARCHAR(16)  | NOT NULL, DEFAULT 'success' | `success` / `failed`                      |
| `error_message` | TEXT         | NULLABLE                    | 失败时的错误堆栈或原因                    |
| `trigger_type`  | VARCHAR(16)  | NOT NULL                    | `scheduled` / `manual`                    |
| `created_at`    | DATETIME     | NOT NULL, DEFAULT NOW       | 备份执行时间                              |

**SQLAlchemy 模型示例：**

```python
# steeltech_db/models/backup_record.py
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from steeltech_db.extensions import db

class BackupRecord(db.Model):
    __tablename__ = "backup_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
```

### 2.2 备份配置

复用现有 `system_settings` 键值表，新增 key `backup_config`，值存储 JSON 字符串。

**JSON schema：**

```json
{
  "enabled": true,
  "schedule": "daily",
  "time": "02:00",
  "retention_count": 30,
  "backup_dir": "datas/backups"
}
```

| 字段              | 类型    | 默认值            | 说明                                           |
| ----------------- | ------- | ----------------- | ---------------------------------------------- |
| `enabled`         | boolean | `true`            | 是否启用定时备份                               |
| `schedule`        | string  | `"daily"`         | 执行周期：`daily` / `weekly` / `monthly`       |
| `time`            | string  | `"02:00"`         | 执行时刻 HH:MM（24小时制，建议凌晨低负载时段） |
| `retention_count` | integer | `30`              | 保留最近 N 份备份，超出自动删除                |
| `backup_dir`      | string  | `"datas/backups"` | 备份文件存放目录（相对于项目根目录）           |

**默认值定义位置：** `steeltech_db/defaults.py`，新增 `BackupConfig` 数据类。

---

## 3. 后端设计

### 3.1 新增依赖

在 `itss-steeltech-back/requirements.txt` 中添加：

```
APScheduler==3.10.4
```

选型理由：

- 纯 Python，轻量无外部依赖
- 支持 BackgroundScheduler 在独立线程中运行，不阻塞 Flask 主进程
- 支持 cron 表达式，灵活配置调度规则
- 与 Flask 集成简单，无需额外中间件

### 3.2 新增文件清单

| 文件                             | 职责                               |
| -------------------------------- | ---------------------------------- |
| `app/services/backup_service.py` | 核心备份逻辑 + 调度器生命周期管理  |
| `app/routes/backup.py`           | REST API 端点（注册为`backup_bp`） |

需修改的文件：

| 文件                                                | 变更                                                     |
| --------------------------------------------------- | -------------------------------------------------------- |
| `app/__init__.py`                                   | 注册`backup_bp` 蓝图，启动时初始化调度器                 |
| `itss-steeltech-db/steeltech_db/models/__init__.py` | 导出`BackupRecord` 模型                                  |
| `itss-steeltech-db/steeltech_db/defaults.py`        | 添加`BackupConfig` 默认值                                |
| `itss-steeltech-db/steeltech_db/seed.py`            | `ensure_system_settings()` 中加入 `backup_config` 初始化 |
| `itss-steeltech-db/datas/schema.sql`                | 添加`backup_records` 建表语句                            |

### 3.3 备份服务 `app/services/backup_service.py`

**类结构：**

```
BackupService:
  ├── backup_now(trigger_type: str) → BackupRecord
  ├── get_config() → BackupConfig
  ├── apply_config(config: BackupConfig) → None
  ├── init_scheduler(app: Flask) → None
  ├── shutdown_scheduler() → None
  ├── cleanup_old_backups() → None
  └── get_history(page, per_page) → PaginatedResult
```

**核心方法说明：**

#### `backup_now(trigger_type)`

```
1. 读取 backup_config 获取 backup_dir
2. 若目录不存在则 os.makedirs()
3. 生成时间戳文件名: backup_{YYYYMMDD}_{HHMMSS}.db
4. 根据 DATABASE_BACKEND 环境变量选择策略:
   - SQLite: shutil.copy2(app.config['SQLITE_DATABASE_PATH'], backup_path)
   - MySQL:  subprocess.run(['mysqldump', '-h', host, '-u', user, '-p', pwd, db], stdout=file)
5. 获取文件大小 os.path.getsize()
6. 写入 BackupRecord 到数据库
7. 调用 cleanup_old_backups()
8. 返回 BackupRecord
```

#### `init_scheduler(app)`

```
1. 从 system_settings 读取 backup_config
2. 若 enabled=False 则跳过
3. 创建 BackgroundScheduler 实例
4. 将 schedule + time 转换为 cron 表达式:
   - daily:   minute hour * * *
   - weekly:  minute hour * * 0   (每周日凌晨)
   - monthly: minute hour 1 * *    (每月1号凌晨)
5. 添加 job: scheduler.add_job(backup_now, 'cron', ..., args=['scheduled'])
6. scheduler.start()
```

#### `cleanup_old_backups()`

```
1. 查询 backup_records 按 created_at 降序
2. 保留前 retention_count 条记录
3. 删除超出记录的磁盘文件（os.remove）
4. 删除超出记录的数据库行
```

#### `apply_config(config)`

```
1. 将 config JSON 写入 system_settings (key='backup_config')
2. 调用 shutdown_scheduler() 停止当前调度器
3. 调用 init_scheduler() 按新配置重启
```

### 3.4 API 端点

注册为 `backup_bp`，URL 前缀 `/api/system/backup`。所有端点需要 JWT 认证 + 管理员权限。

| 方法     | 路径             | 说明                      | 请求体                   | 返回值                                        |
| -------- | ---------------- | ------------------------- | ------------------------ | --------------------------------------------- |
| `GET`    | `/config`        | 获取备份配置              | —                        | `BackupConfig` JSON                           |
| `PUT`    | `/config`        | 更新备份配置，重启调度器  | `BackupConfig` JSON      | `{ "message": "ok" }`                         |
| `POST`   | `/trigger`       | 手动触发一次备份          | —                        | `{ "message": "ok", "record": BackupRecord }` |
| `GET`    | `/history`       | 分页查询备份历史          | Query:`page`, `per_page` | `{ "items": [...], "total": N }`              |
| `GET`    | `/download/<id>` | 下载指定备份文件          | —                        | 文件流 (`application/octet-stream`)           |
| `DELETE` | `/<id>`          | 删除指定备份（文件+记录） | —                        | `{ "message": "ok" }`                         |

**路由伪代码（`app/routes/backup.py`）：**

```python
from flask import Blueprint, request, send_file
from flask_jwt_extended import jwt_required
from app.services.backup_service import BackupService

backup_bp = Blueprint("backup", __name__)
service = BackupService()

@backup_bp.route("/config", methods=["GET"])
@jwt_required()
def get_config():
    admin_required()
    return jsonify(service.get_config())

@backup_bp.route("/config", methods=["PUT"])
@jwt_required()
def update_config():
    admin_required()
    data = request.get_json()
    service.apply_config(data)
    return jsonify({"message": "备份配置已更新"})

@backup_bp.route("/trigger", methods=["POST"])
@jwt_required()
def trigger_backup():
    admin_required()
    record = service.backup_now(trigger_type="manual")
    return jsonify({"message": "备份完成", "record": record.to_dict()})

@backup_bp.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    admin_required()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    return jsonify(service.get_history(page, per_page))

@backup_bp.route("/download/<int:id>", methods=["GET"])
@jwt_required()
def download_backup(id):
    admin_required()
    record = BackupRecord.query.get_or_404(id)
    filepath = os.path.join(service.backup_dir, record.filename)
    return send_file(filepath, as_attachment=True, download_name=record.filename)

@backup_bp.route("/<int:id>", methods=["DELETE"])
@jwt_required()
def delete_backup(id):
    admin_required()
    service.delete_backup(id)
    return jsonify({"message": "已删除"})
```

### 3.5 调度器生命周期

在 `app/__init__.py` 的 `create_app()` 中集成：

```python
def create_app():
    # ... 现有初始化代码 ...

    # 注册备份蓝图
    from app.routes.backup import backup_bp
    app.register_blueprint(backup_bp, url_prefix="/api/system/backup")

    # 启动备份调度器（在应用上下文中）
    with app.app_context():
        from app.services.backup_service import BackupService
        BackupService().init_scheduler(app)

    return app
```

调度器作为 `BackgroundScheduler` 在独立守护线程中运行，随 Flask 进程启动和销毁。生产环境（Gunicorn 多 worker）中需注意：

- **推荐方案：** 仅在主 worker 中启动调度器（通过环境变量或 `--preload` 控制）
- **备选方案：** 使用 `scheduler.add_job(..., max_instances=1)` 防止重复执行

---

## 4. 前端设计

### 4.1 新增文件

| 文件                              | 职责                  |
| --------------------------------- | --------------------- |
| `src/views/system/BackupView.vue` | 备份管理页面组件      |
| `src/api/backup.ts`               | 备份相关 API 请求函数 |

### 4.2 页面布局

```
┌─────────────────────────────────────────────────────┐
│  数据库备份                                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─ 备份状态 ───────────────────────────────────┐ │
│  │                                              │ │
│  │  上次备份: 2026-06-29 02:00  ✓ 成功 (2.3 MB)  │ │
│  │  下次执行: 2026-06-30 02:00                   │ │
│  │                                              │ │
│  │  [ 立即备份 ]      启用定时备份  [====]        │ │
│  └──────────────────────────────────────────────┘ │
│                                                   │
│  ┌─ 定时设置 ───────────────────────────────────┐ │
│  │                                              │ │
│  │  执行周期:  [ 每天 ▼ ]                        │ │
│  │  执行时间:  [ 02:00 ]                         │ │
│  │  保留份数:  [ 30 ]                            │ │
│  │  备份目录:  [ datas/backups ]                 │ │
│  │                                              │ │
│  │  [ 保存设置 ]                                 │ │
│  └──────────────────────────────────────────────┘ │
│                                                   │
│  ┌─ 备份历史 ───────────────────────────────────┐ │
│  │                                              │ │
│  │  ┌──────────────────────────────────────────┐ │ │
│  │  │ 文件名           大小   类型     状态 时间 │ │ │
│  │  │ backup_0629_0200  2.3M  自动   ✓ 成功 ... │ │ │
│  │  │ backup_0628_0200  2.2M  自动   ✓ 成功 ... │ │ │
│  │  │ backup_0627_1510  2.2M  手动   ✓ 成功 ... │ │ │
│  │  └──────────────────────────────────────────┘ │ │
│  │                     < 1  2  3  4  5 >         │ │
│  └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### 4.3 `src/api/backup.ts`

```typescript
import { request } from './request'

export interface BackupConfig {
  enabled: boolean
  schedule: 'daily' | 'weekly' | 'monthly'
  time: string
  retention_count: number
  backup_dir: string
}

export interface BackupRecord {
  id: number
  filename: string
  file_size: number
  status: 'success' | 'failed'
  error_message?: string
  trigger_type: 'scheduled' | 'manual'
  created_at: string
}

export function getBackupConfig() {
  return request<BackupConfig>({ url: '/system/backup/config' })
}

export function updateBackupConfig(data: BackupConfig) {
  return request<void>({ url: '/system/backup/config', method: 'PUT', data })
}

export function triggerBackup() {
  return request<{ message: string; record: BackupRecord }>({
    url: '/system/backup/trigger',
    method: 'POST',
  })
}

export function getBackupHistory(params: { page: number; per_page: number }) {
  return request<{ items: BackupRecord[]; total: number }>({
    url: '/system/backup/history',
    params,
  })
}

export function deleteBackup(id: number) {
  return request<void>({ url: `/system/backup/${id}`, method: 'DELETE' })
}
```

### 4.4 路由与菜单

在 `src/router/index.ts` 的 `mainChildren` 中添加：

```ts
{
  path: 'system/backup',
  name: 'SystemBackup',
  component: () => import('@/views/system/BackupView.vue'),
  meta: { title: '数据库备份', adminOnly: true },
}
```

在 `src/layouts/MainLayout.vue` 的 `menuItemsBySystem.system` 中添加：

```ts
{ path: '/system/backup', title: '数据库备份', icon: 'FolderOpened' },
```

---

## 5. 安全与容错

| 关注点           | 措施                                                                                                 |
| ---------------- | ---------------------------------------------------------------------------------------------------- |
| **权限控制**     | 所有 API 端点标记`adminOnly`，前端页面与菜单仅管理员可见                                             |
| **备份文件保护** | 备份目录不通过 Web 静态路由暴露；下载通过受 JWT 认证的`/download/<id>` 端点                          |
| **并发安全**     | `backup_now` 方法内部加 `threading.Lock`，防止手动触发与定时任务同时执行                             |
| **磁盘空间**     | `retention_count` 自动清理；备份前检查 `shutil.disk_usage()` 确保剩余空间 > 100MB                    |
| **失败容错**     | 备份失败不抛出异常导致调度器崩溃；`try/except` 捕获后写入 `error_message` 到 `BackupRecord`          |
| **时区**         | 使用服务器本地时区（`APScheduler` 默认行为），在配置文档中注明                                       |
| **多 Worker**    | Gunicorn 生产环境下通过`--preload` + 环境变量 `BACKUP_SCHEDULER_ENABLED=true` 控制仅主进程启动调度器 |

### Gunicorn 多 Worker 适配方案

```python
# app/services/backup_service.py
import os

def init_scheduler(app):
    # 仅在明确启用时启动调度器（生产环境通过环境变量控制）
    if os.environ.get('BACKUP_SCHEDULER_ENABLED', 'true') != 'true':
        return
    # 防止 Gunicorn preload 后 fork 导致重复调度
    if os.environ.get('GUNICORN_WORKER_ID', '0') != '0':
        return
    # ... 启动调度器 ...
```

---

## 6. 实施步骤

| 序号 | 内容                                             | 涉及仓库             | 预估工作量 |
| ---- | ------------------------------------------------ | -------------------- | ---------- |
| 1    | 添加`BackupRecord` 模型到 `steeltech_db/models/` | itss-steeltech-db    | 小         |
| 2    | 添加`BackupConfig` 默认值到 `defaults.py`        | itss-steeltech-db    | 小         |
| 3    | 更新`schema.sql` 添加 `backup_records` 建表语句  | itss-steeltech-db    | 小         |
| 4    | 在`seed.py` 中添加 `backup_config` 初始化逻辑    | itss-steeltech-db    | 小         |
| 5    | 实现`app/services/backup_service.py`             | itss-steeltech-back  | 中         |
| 6    | 实现`app/routes/backup.py` API 端点              | itss-steeltech-back  | 中         |
| 7    | 在`app/__init__.py` 注册蓝图并初始化调度器       | itss-steeltech-back  | 小         |
| 8    | 添加`APScheduler` 到 `requirements.txt`          | itss-steeltech-back  | 小         |
| 9    | 创建前端`BackupView.vue` 页面                    | itss-steeltech-front | 中         |
| 10   | 创建前端`src/api/backup.ts`                      | itss-steeltech-front | 小         |
| 11   | 添加路由与菜单项                                 | itss-steeltech-front | 小         |
| 12   | 联调测试（SQLite + MySQL）                       | 全部                 | 中         |

---

## 7. 扩展方向（可选）

- **远程备份：** 支持备份到网络路径（UNC 路径 `\\10.10.1.175\backup`），与现有的 `localWorkPath` 配置体系保持一致
- **邮件/企业微信通知：** 备份失败时通过 Webhook 发送告警
- **备份验证：** 备份完成后自动还原到临时库验证完整性
- **增量备份：** 对 MySQL 使用 `mysqldump --single-transaction` 减少锁表时间
