# 运维与统计脚本

位于后端仓库根目录 `scripts/`，用于**只读**的数据库概览、项目文件夹与本地附件存储统计。  
与 `db/scripts/`（建库、迁移、导入导出）分工不同：本目录侧重日常巡检与数据健康检查。

## 前置条件

1. 已进入后端目录：`itss-steeltech-back`
2. 已创建并激活虚拟环境（与启动后端相同）
3. 已配置 `.env`（至少包含数据库连接，如 `DATABASE_URL`）

```powershell
cd itss-steeltech-back
.\venv\Scripts\activate
```

脚本会自动加载 `.env` 并创建 Flask 应用上下文，与 API 服务使用同一套数据库配置，**不会修改任何数据**。

## 快速开始

```powershell
# 数据库概览
python scripts/db_stats.py

# 项目工作路径统计
python scripts/project_folder_stats.py

# 本地附件存储体积
python scripts/storage_stats.py
```

将输出保存到文件（便于分享或对比）：

```powershell
python scripts/db_stats.py > scripts/reports/db_stats.txt
python scripts/project_folder_stats.py --missing-only > scripts/reports/missing_paths.txt
```

`scripts/reports/` 已在 `.gitignore` 中，生成的报告不会误提交。

---

## db_stats.py — 数据库概览

查看核心表行数、项目/人员/联系单分布、工作路径填写率。

```powershell
python scripts/db_stats.py
python scripts/db_stats.py --tables
```

| 参数 | 说明 |
|------|------|
| `--tables` | 额外列出全部业务表行数（默认只显示核心摘要） |

**输出内容：**

- 连接信息（`DATABASE_BACKEND`、连接串、SQLite 路径）
- 核心表行数（人员、角色、项目、联系单、PDF）
- 项目按 `status` 分布（active / done / cancelled 等）
- 人员按 `status`、`team` 分布
- 联系单（未软删）按 `status` 分布
- 项目路径填写情况（设计 / 细化 / 本地路径各多少条）

---

## project_folder_stats.py — 项目文件夹

统计数据库中登记的项目工作路径，可选检测 UNC 路径在本机是否可访问。

```powershell
# 默认：路径填写概览 + 已登记路径样例
python scripts/project_folder_stats.py

# 仅列出「三条路径均未填」的项目
python scripts/project_folder_stats.py --missing-only

# 检测 UNC 文件夹是否真实存在（需能访问文件服务器 10.10.x.x）
python scripts/project_folder_stats.py --check-exists

# 组合使用：列出缺失路径项目，最多显示 50 条
python scripts/project_folder_stats.py --missing-only --limit 50
```

| 参数 | 说明 |
|------|------|
| `--check-exists` | 将相对路径拼成 UNC 后检测目录是否存在 |
| `--missing-only` | 只输出未填写任何工作路径的项目列表 |
| `--limit N` | 明细表最多显示 N 行（默认 30） |

**路径类型说明：**

| 类型 | 对应字段 | 含义 |
|------|----------|------|
| `design` | `design_work_path` | 设计工作路径 |
| `detail` | `detail_work_path` | 细化工作路径 |
| `local` | `local_work_path` | 本地/归档路径 |

**注意：** `--check-exists` 依赖系统设置中的文件服务器 IP（`local_work_path` 配置）。若本机无法访问内网共享，检测结果会显示「不可访问」，属正常现象。

---

## storage_stats.py — 本地附件存储

扫描 `datas/files` 下各业务附件目录的文件数与占用体积。

```powershell
python scripts/storage_stats.py
```

统计范围（路径可在 `.env` 中通过 `*_STORAGE_ROOT` 覆盖）：

| 目录 | 环境变量 |
|------|----------|
| 联系单 PDF | `CONTACT_PDF_STORAGE_ROOT` |
| 联系单附件 | `CONTACT_ATTACHMENT_STORAGE_ROOT` |
| 周会图片 | `WEEKLY_MEETING_IMAGE_ROOT` |
| 周会扫描件 | `WEEKLY_MEETING_SCAN_ROOT` |
| 所长访谈图片 | `DIRECTOR_INTERVIEW_IMAGE_ROOT` |
| 变更单 PDF | `CHANGE_ORDER_PDF_STORAGE_ROOT` |
| 月度培训文件 | `MONTHLY_TRAINING_FILE_ROOT` |

---

## 常见场景

| 场景 | 推荐命令 |
|------|----------|
| 每日巡检数据库规模 | `python scripts/db_stats.py` |
| 找出还没填工作路径的项目 | `python scripts/project_folder_stats.py --missing-only` |
| 核对路径是否能在本机打开 | `python scripts/project_folder_stats.py --check-exists` |
| 查看附件磁盘占用 | `python scripts/storage_stats.py` |
| 导出完整表行数给同事 | `python scripts/db_stats.py --tables > scripts/reports/tables.txt` |

## 与 `db/scripts` 的区别

| 目录 | 用途 | 示例 |
|------|------|------|
| `db/scripts/` | 数据库生命周期：建库、种子、迁移、Excel 全表导出 | `init_db.py`、`export_to_excel.py` |
| `scripts/`（本目录） | 运行期巡检：统计、对账、健康检查，**不修改数据** | `db_stats.py`、`project_folder_stats.py` |

## 计划扩展（待实现）

### 数据库统计

- [ ] 联系单族（`root_id`）规模分布：主单 / 补充 / 修订数量
- [ ] 项目性质（`project_natures`）× 状态交叉表
- [ ] 月休 / 请假 / 结算等待办积压（按月份、班组）
- [ ] 软删与孤儿记录检测（联系单 PDF 路径失效、项目人员悬空等）
- [ ] 导出 Markdown / CSV 报告到 `scripts/reports/`

### 项目文件夹统计

- [ ] 按归档年份统计有路径项目数
- [ ] 对比数据库路径与文件服务器实际目录（借助 `path_search_service` 反查）
- [ ] 加工单（`is_jiagongdan`）路径单独汇总
- [ ] 大文件夹 Top N（按文件数或体积，需 `--check-exists`）

### 本地存储

- [ ] 数据库中 PDF 记录 vs 磁盘文件一致性（缺失 / 多余文件）
- [ ] 备份目录 `datas/backups` 体积与保留策略提示

## 开发约定

- 公共引导：`_bootstrap.py`（路径、`.env`、`app_context`）
- 输出格式：`_format.py`（终端表格）
- 新脚本保持**只读**；如需写库或批量修复，放在 `db/scripts/` 并单独评审
- 访问 UNC 路径时使用 `app.utils.paths` 中的 `build_full_path` / `normalize_access_path`
