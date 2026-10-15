-- ITSS Steeltech 本地开发 SQLite 结构
-- 数据库文件：datas/steeltech.db

PRAGMA foreign_keys = ON;

-- 人员
CREATE TABLE IF NOT EXISTS personnel (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  employee_no     TEXT NOT NULL,
  id_card_no      TEXT,
  passport_no     TEXT,
  passport_expiry TEXT,
  position        TEXT,
  nationality     TEXT NOT NULL DEFAULT '中国',
  workshop        TEXT,
  team            TEXT NOT NULL,
  birth_date      TEXT,
  age             INTEGER,
  gender          TEXT,
  ethnicity       TEXT,
  native_place    TEXT,
  education       TEXT,
  home_address    TEXT,
  graduation_school TEXT,
  major           TEXT,
  indonesia_phone TEXT,
  domestic_phone  TEXT,
  dormitory_no    TEXT,
  status          TEXT NOT NULL DEFAULT 'active',
  created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_personnel_team ON personnel (team);
CREATE INDEX IF NOT EXISTS idx_personnel_employee_no ON personnel (employee_no);

-- 系统全局配置（键值存储）
CREATE TABLE IF NOT EXISTS system_settings (
  key         TEXT PRIMARY KEY,
  value       TEXT NOT NULL,
  updated_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 登录密码（未设置时使用系统默认密码）
CREATE TABLE IF NOT EXISTS account_passwords (
  account     TEXT PRIMARY KEY,
  password    TEXT NOT NULL,
  updated_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 用户个性化偏好（按账号存储，如细化组人员排列顺序）
CREATE TABLE IF NOT EXISTS user_preferences (
  account          TEXT NOT NULL,
  preference_key   TEXT NOT NULL,
  preference_value TEXT NOT NULL,
  updated_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (account, preference_key)
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_account
  ON user_preferences (account);

-- 页面权限（按页面分类，含查看/编辑操作）
CREATE TABLE IF NOT EXISTS permissions (
  id          TEXT PRIMARY KEY,
  code        TEXT NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  module      TEXT NOT NULL,
  path        TEXT NOT NULL,
  page_key    TEXT NOT NULL,
  page_name   TEXT NOT NULL,
  action      TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  CHECK (action IN ('view', 'edit'))
);

CREATE INDEX IF NOT EXISTS idx_permissions_module ON permissions (module);

-- 角色
CREATE TABLE IF NOT EXISTS roles (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  code        TEXT NOT NULL UNIQUE,
  description TEXT,
  status      TEXT NOT NULL DEFAULT 'active',
  created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_roles_status ON roles (status);

-- 角色权限（多对多）
CREATE TABLE IF NOT EXISTS role_permissions (
  role_id       TEXT NOT NULL,
  permission_id TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (role_id, permission_id),
  FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE,
  FOREIGN KEY (permission_id) REFERENCES permissions (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_role_id ON role_permissions (role_id);

-- 角色人员（多对多）
CREATE TABLE IF NOT EXISTS role_personnel (
  role_id       TEXT NOT NULL,
  personnel_id  TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (role_id, personnel_id),
  FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE,
  FOREIGN KEY (personnel_id) REFERENCES personnel (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_role_personnel_role_id ON role_personnel (role_id);
CREATE INDEX IF NOT EXISTS idx_role_personnel_personnel_id ON role_personnel (personnel_id);

-- 角色科室（多对多）
CREATE TABLE IF NOT EXISTS role_workshops (
  role_id    TEXT NOT NULL,
  workshop   TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (role_id, workshop),
  FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_role_workshops_workshop ON role_workshops (workshop);

-- 项目
CREATE TABLE IF NOT EXISTS projects (
  project_no  TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  customer    TEXT,
  status              TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'done', 'paused', 'cancelled')),
  design_completed    INTEGER NOT NULL DEFAULT 0 CHECK (design_completed IN (0, 1)),
  detail_completed    INTEGER NOT NULL DEFAULT 0 CHECK (detail_completed IN (0, 1)),
  tile_layout_completed INTEGER NOT NULL DEFAULT 0 CHECK (tile_layout_completed IN (0, 1)),
  floor_deck_layout_completed INTEGER NOT NULL DEFAULT 0 CHECK (floor_deck_layout_completed IN (0, 1)),
  drawing_issue_enabled INTEGER NOT NULL DEFAULT 0 CHECK (drawing_issue_enabled IN (0, 1)),
  drawing_issue_year_month TEXT,
  is_jiagongdan       INTEGER NOT NULL DEFAULT 0 CHECK (is_jiagongdan IN (0, 1)),
  received_date       TEXT,
  derived_received_date TEXT,
  planned_start_date  TEXT,
  planned_end_date    TEXT,
  actual_start_date   TEXT,
  actual_end_date     TEXT,
  design_work_path    TEXT,
  detail_work_path    TEXT,
  local_work_path     TEXT,
  structure_type      TEXT,
  estimated_weight_tons REAL
    CHECK (estimated_weight_tons IS NULL OR estimated_weight_tons >= 0),
  created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status);
CREATE INDEX IF NOT EXISTS idx_projects_derived_received_date ON projects (derived_received_date);

-- 项目性质（设计 / 细化 / 细化问题 / 排楼板 / 排瓦，可多选）
-- 注：钢板排板属于细化主流程子阶段（见 project_detail_workflows.plate_layout_enabled），非独立项目性质
-- plate_layout 为历史遗留值，迁移后不再写入
-- 排瓦 = 墙面板排版（瓦片排版）；排楼板 = 楼承板排版（楼层板排版）
CREATE TABLE IF NOT EXISTS project_natures (
  project_no  TEXT NOT NULL,
  nature      TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (project_no, nature),
  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
  CHECK (nature IN ('design', 'detail', 'detail_issue', 'plate_layout', 'floor_deck_layout', 'tile_layout'))
);

CREATE INDEX IF NOT EXISTS idx_project_natures_project_no ON project_natures (project_no);

-- 项目分配人员（可多选）
CREATE TABLE IF NOT EXISTS project_personnel (
  project_no    TEXT NOT NULL,
  personnel_id  TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (project_no, personnel_id),
  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
  FOREIGN KEY (personnel_id) REFERENCES personnel (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_project_personnel_project_no ON project_personnel (project_no);
CREATE INDEX IF NOT EXISTS idx_project_personnel_personnel_id ON project_personnel (personnel_id);

-- 细化项目流程（建模 / 调图 / 钢板排板；仅含「细化」性质的项目有记录）
CREATE TABLE IF NOT EXISTS project_detail_workflows (
  project_no                TEXT PRIMARY KEY,
  modeling_status           TEXT NOT NULL DEFAULT 'not_started'
    CHECK (modeling_status IN ('not_started', 'in_progress', 'completed')),
  drawing_status            TEXT NOT NULL DEFAULT 'not_started'
    CHECK (drawing_status IN ('not_started', 'in_progress', 'completed')),
  plate_layout_enabled      INTEGER NOT NULL DEFAULT 1
    CHECK (plate_layout_enabled IN (0, 1)),
  plate_layout_status       TEXT NOT NULL DEFAULT 'not_started'
    CHECK (plate_layout_status IN ('not_started', 'in_progress', 'completed', 'not_applicable')),
  modeling_started_at       TEXT,
  modeling_completed_at     TEXT,
  drawing_started_at        TEXT,
  drawing_completed_at      TEXT,
  plate_layout_started_at   TEXT,
  plate_layout_completed_at TEXT,
  model_weight_tons         REAL
    CHECK (model_weight_tons IS NULL OR model_weight_tons >= 0),
  model_weight_updated_at   TEXT,
  model_weight_updated_by   TEXT,
  created_at                TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at                TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
  FOREIGN KEY (model_weight_updated_by) REFERENCES personnel (id)
);

CREATE INDEX IF NOT EXISTS idx_pdw_modeling_status ON project_detail_workflows (modeling_status);
CREATE INDEX IF NOT EXISTS idx_pdw_drawing_status ON project_detail_workflows (drawing_status);
CREATE INDEX IF NOT EXISTS idx_pdw_plate_layout_status ON project_detail_workflows (plate_layout_status);

-- 设计项目流程（设计开始 / 设计结束仅存日期 YYYY-MM-DD；设计面积；仅含设计性质的项目有记录）
CREATE TABLE IF NOT EXISTS project_design_workflows (
  project_no                TEXT PRIMARY KEY,
  design_started_at         TEXT,
  design_completed_at       TEXT,
  design_area_sqm           REAL
    CHECK (design_area_sqm IS NULL OR design_area_sqm >= 0),
  design_area_updated_at    TEXT,
  design_area_updated_by    TEXT,
  created_at                TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at                TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
  FOREIGN KEY (design_area_updated_by) REFERENCES personnel (id)
);

-- 联系单（一条记录 = 一张独立联系单；PDF 见 contact_form_pdfs）
CREATE TABLE IF NOT EXISTS contact_forms (
  id                TEXT PRIMARY KEY,
  title             TEXT NOT NULL,
  received_date     TEXT NOT NULL,
  urgency           TEXT NOT NULL DEFAULT '普通',
  status            TEXT NOT NULL DEFAULT 'pending',
  content           TEXT,
  expect_reply_date TEXT,
  parent_id         TEXT,
  root_id           TEXT NOT NULL,
  relation_type     TEXT NOT NULL DEFAULT 'primary',
  sort_order        INTEGER NOT NULL DEFAULT 0,
  cancel_scope      TEXT,
  derived_family_max_date TEXT,
  deleted_at        TEXT,
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (parent_id) REFERENCES contact_forms (id) ON DELETE SET NULL,
  CHECK (relation_type IN ('primary', 'supplement', 'revision', 'follow_up', 'cancel')),
  CHECK (cancel_scope IS NULL OR cancel_scope IN ('full', 'partial'))
);

CREATE INDEX IF NOT EXISTS idx_contact_forms_status ON contact_forms (status);
CREATE INDEX IF NOT EXISTS idx_contact_forms_received_date ON contact_forms (received_date);
CREATE INDEX IF NOT EXISTS idx_contact_forms_root_sort ON contact_forms (root_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_contact_forms_parent ON contact_forms (parent_id);

-- 联系单与项目关联（多对多，带来源语义；id 为行唯一标识，更新关联时会删除重建）
CREATE TABLE IF NOT EXISTS contact_form_projects (
  id                      INTEGER PRIMARY KEY AUTOINCREMENT,
  contact_form_id         TEXT NOT NULL,
  project_no              TEXT NOT NULL,
  source_type             TEXT NOT NULL DEFAULT 'own',
  source_contact_form_id  TEXT,
  created_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  UNIQUE (contact_form_id, project_no),
  FOREIGN KEY (contact_form_id) REFERENCES contact_forms (id) ON DELETE CASCADE,
  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
  CHECK (source_type IN ('own', 'inherited', 'added', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_cfp_contact_form_id ON contact_form_projects (contact_form_id);
CREATE INDEX IF NOT EXISTS idx_cfp_project_no ON contact_form_projects (project_no);

-- 联系单 PDF（primary=本体，supplement=追加附件）
CREATE TABLE IF NOT EXISTS contact_form_pdfs (
  id              TEXT PRIMARY KEY,
  contact_form_id TEXT NOT NULL,
  file_name       TEXT NOT NULL,
  file_path       TEXT NOT NULL,
  file_md5        TEXT,
  file_size       INTEGER,
  mime_type       TEXT NOT NULL DEFAULT 'application/pdf',
  attachment_type     TEXT NOT NULL DEFAULT 'supplement',
  sort_order          INTEGER NOT NULL DEFAULT 0,
  is_current          INTEGER NOT NULL DEFAULT 1,
  original_file_name  TEXT,
  remark              TEXT,
  deleted_at          TEXT,
  created_at          TEXT NOT NULL,
  FOREIGN KEY (contact_form_id) REFERENCES contact_forms (id) ON DELETE CASCADE,
  CHECK (attachment_type IN ('primary', 'supplement'))
);

CREATE INDEX IF NOT EXISTS idx_contact_form_pdfs_contact_id ON contact_form_pdfs (contact_form_id);
CREATE INDEX IF NOT EXISTS idx_contact_form_pdfs_md5 ON contact_form_pdfs (file_md5);
CREATE INDEX IF NOT EXISTS idx_contact_forms_deleted_at ON contact_forms (deleted_at);
CREATE INDEX IF NOT EXISTS idx_contact_form_pdfs_deleted_at ON contact_form_pdfs (deleted_at);

-- 取消联系单对项目关联的审计
CREATE TABLE IF NOT EXISTS contact_form_project_cancellations (
  id                TEXT PRIMARY KEY,
  cancel_contact_id TEXT NOT NULL,
  target_contact_id TEXT NOT NULL,
  project_no        TEXT NOT NULL,
  cancelled_at      TEXT NOT NULL,
  FOREIGN KEY (cancel_contact_id) REFERENCES contact_forms (id) ON DELETE CASCADE,
  FOREIGN KEY (target_contact_id) REFERENCES contact_forms (id) ON DELETE CASCADE,
  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cfpc_cancel ON contact_form_project_cancellations (cancel_contact_id);
CREATE INDEX IF NOT EXISTS idx_cfpc_target ON contact_form_project_cancellations (target_contact_id);

-- 标签（项目与联系单共用）
CREATE TABLE IF NOT EXISTS tags (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS project_tags (
  project_no  TEXT NOT NULL,
  tag_id      TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (project_no, tag_id),
  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_project_tags_project_no ON project_tags (project_no);
CREATE INDEX IF NOT EXISTS idx_project_tags_tag_id ON project_tags (tag_id);

CREATE TABLE IF NOT EXISTS contact_form_tags (
  contact_form_id TEXT NOT NULL,
  tag_id          TEXT NOT NULL,
  created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (contact_form_id, tag_id),
  FOREIGN KEY (contact_form_id) REFERENCES contact_forms (id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_contact_form_tags_contact ON contact_form_tags (contact_form_id);
CREATE INDEX IF NOT EXISTS idx_contact_form_tags_tag ON contact_form_tags (tag_id);

-- 月休计划
CREATE TABLE IF NOT EXISTS monthly_rest (
  id            TEXT PRIMARY KEY,
  personnel_id  TEXT NOT NULL,
  year          INTEGER NOT NULL,
  month         INTEGER NOT NULL,
  rest_days     TEXT NOT NULL DEFAULT '[]',
  created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (personnel_id) REFERENCES personnel (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_monthly_rest_personnel ON monthly_rest (personnel_id);
CREATE INDEX IF NOT EXISTS idx_monthly_rest_year_month ON monthly_rest (year, month);

-- 月休计划锁定（按年月，管理员定稿后员工不可再修改）
CREATE TABLE IF NOT EXISTS monthly_rest_lock (
  year        INTEGER NOT NULL,
  month       INTEGER NOT NULL,
  locked_by   TEXT,
  locked_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (year, month)
);

CREATE INDEX IF NOT EXISTS idx_monthly_rest_lock_year_month ON monthly_rest_lock (year, month);

-- 临时任务（我的日程侧边栏）
CREATE TABLE IF NOT EXISTS temp_tasks (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  description   TEXT,
  start_time    TEXT NOT NULL,
  completed_at  TEXT,
  is_related_project INTEGER NOT NULL DEFAULT 0,
  related_project_no TEXT,
  created_by    TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (created_by) REFERENCES personnel (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_temp_tasks_created_by ON temp_tasks (created_by);
CREATE INDEX IF NOT EXISTS idx_temp_tasks_start_time ON temp_tasks (start_time);

-- 临时任务关联人员（可多选）
CREATE TABLE IF NOT EXISTS temp_task_personnel (
  temp_task_id  TEXT NOT NULL,
  personnel_id  TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (temp_task_id, personnel_id),
  FOREIGN KEY (temp_task_id) REFERENCES temp_tasks (id) ON DELETE CASCADE,
  FOREIGN KEY (personnel_id) REFERENCES personnel (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_temp_task_personnel_personnel ON temp_task_personnel (personnel_id);

-- 钢构细化发图计划
CREATE TABLE IF NOT EXISTS drawing_issue_plans (
  id                  TEXT PRIMARY KEY,
  year                INTEGER NOT NULL,
  month               INTEGER NOT NULL,
  seq                 INTEGER NOT NULL,
  project_name        TEXT NOT NULL,
  project_no          TEXT NOT NULL,
  component_weight_kg REAL,
  detail_planned_issue_date TEXT,
  detail_actual_issue_date TEXT,
  floor_deck_planned_issue_date TEXT,
  floor_deck_actual_issue_date TEXT,
  material_prep_list_issue_date TEXT,
  remark              TEXT,
  created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_drawing_issue_plans_year_month ON drawing_issue_plans (year, month);
CREATE UNIQUE INDEX IF NOT EXISTS idx_drawing_issue_plans_year_month_seq ON drawing_issue_plans (year, month, seq);

-- 钢构设计发图计划
CREATE TABLE IF NOT EXISTS design_drawing_issue_plans (
  id                  TEXT PRIMARY KEY,
  year                INTEGER NOT NULL,
  month               INTEGER NOT NULL,
  seq                 INTEGER NOT NULL,
  project_name        TEXT NOT NULL,
  project_no          TEXT NOT NULL,
  component_weight_kg REAL,
  design_planned_issue_date TEXT,
  design_actual_issue_date TEXT,
  tile_layout_planned_issue_date TEXT,
  tile_layout_actual_issue_date TEXT,
  floor_deck_planned_issue_date TEXT,
  floor_deck_actual_issue_date TEXT,
  material_prep_list_issue_date TEXT,
  remark              TEXT,
  created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_design_drawing_issue_plans_year_month ON design_drawing_issue_plans (year, month);
CREATE UNIQUE INDEX IF NOT EXISTS idx_design_drawing_issue_plans_year_month_seq ON design_drawing_issue_plans (year, month, seq);

-- 项目模型（细化模型 / 甲供模型；同一项目可有多条）
CREATE TABLE IF NOT EXISTS project_models (
  id                TEXT PRIMARY KEY,
  project_no        TEXT NOT NULL,
  model_type        TEXT NOT NULL,
  name              TEXT NOT NULL,
  status            TEXT NOT NULL DEFAULT 'not_started'
    CHECK (status IN ('not_started', 'in_progress', 'completed')),
  model_weight_tons REAL
    CHECK (model_weight_tons IS NULL OR model_weight_tons >= 0),
  model_path        TEXT,
  remark            TEXT,
  seq               INTEGER NOT NULL DEFAULT 0,
  created_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
  CHECK (model_type IN ('detail', 'jiagong'))
);

CREATE INDEX IF NOT EXISTS idx_project_models_project_no ON project_models (project_no);
CREATE INDEX IF NOT EXISTS idx_project_models_model_type ON project_models (model_type);
CREATE INDEX IF NOT EXISTS idx_project_models_status ON project_models (status);
CREATE INDEX IF NOT EXISTS idx_project_models_project_no_seq ON project_models (project_no, seq);

-- 钢结构技术科结算定价依据
CREATE TABLE IF NOT EXISTS settlement_pricing_basis (
  id            TEXT PRIMARY KEY,
  category      TEXT NOT NULL,
  pricing_code  TEXT NOT NULL,
  item_name     TEXT NOT NULL,
  calc_process  TEXT,
  unit_price    REAL NOT NULL,
  unit          TEXT NOT NULL,
  remark        TEXT,
  seq           INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_settlement_pricing_category ON settlement_pricing_basis (category);
CREATE UNIQUE INDEX IF NOT EXISTS idx_settlement_pricing_code ON settlement_pricing_basis (category, pricing_code);

-- 钢结构技术科结算记录
CREATE TABLE IF NOT EXISTS settlement_records (
  id               TEXT PRIMARY KEY,
  year             INTEGER NOT NULL,
  month            INTEGER NOT NULL,
  seq              INTEGER NOT NULL,
  category         TEXT NOT NULL,
  name             TEXT NOT NULL,
  project_no       TEXT,
  quantity         REAL NOT NULL DEFAULT 0,
  unit             TEXT NOT NULL DEFAULT '',
  unit_price       REAL NOT NULL DEFAULT 0,
  total_price      REAL NOT NULL DEFAULT 0,
  coefficient      REAL NOT NULL DEFAULT 1,
  pricing_code     TEXT NOT NULL DEFAULT '',
  settlement_year  INTEGER,
  settlement_month INTEGER,
  issue_year       INTEGER,
  issue_month      INTEGER,
  created_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_settlement_records_year_month ON settlement_records (year, month);
CREATE INDEX IF NOT EXISTS idx_settlement_records_category ON settlement_records (category);
CREATE UNIQUE INDEX IF NOT EXISTS idx_settlement_records_year_month_category_seq ON settlement_records (year, month, category, seq);

-- 已完成但未结算的项目
CREATE TABLE IF NOT EXISTS settlement_pending_items (
  id            TEXT PRIMARY KEY,
  category      TEXT NOT NULL,
  seq           INTEGER NOT NULL,
  name          TEXT NOT NULL,
  project_no    TEXT,
  quantity      REAL NOT NULL DEFAULT 0,
  unit          TEXT NOT NULL DEFAULT '',
  unit_price    REAL NOT NULL DEFAULT 0,
  total_price   REAL NOT NULL DEFAULT 0,
  coefficient   REAL NOT NULL DEFAULT 1,
  pricing_code  TEXT NOT NULL DEFAULT '',
  issue_year    INTEGER,
  issue_month   INTEGER,
  created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_settlement_pending_category ON settlement_pending_items (category);
CREATE UNIQUE INDEX IF NOT EXISTS idx_settlement_pending_category_seq ON settlement_pending_items (category, seq);

-- 变更单（id 为内部唯一标识，order_no 为对外变更单号，新建时可留空自动生成）
CREATE TABLE IF NOT EXISTS change_orders (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  order_no      TEXT,
  title         TEXT NOT NULL,
  received_date TEXT NOT NULL DEFAULT '',
  content       TEXT,
  deleted_at    TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_change_orders_order_no ON change_orders (order_no);
CREATE INDEX IF NOT EXISTS idx_change_orders_deleted_at ON change_orders (deleted_at);

-- 变更单与项目关联（多对多；id 为行唯一标识，勿用变更单号作主键——更新时会删除重建）
CREATE TABLE IF NOT EXISTS change_order_projects (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  change_order_id INTEGER NOT NULL,
  project_no      TEXT NOT NULL,
  created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  UNIQUE (change_order_id, project_no),
  FOREIGN KEY (change_order_id) REFERENCES change_orders (id) ON DELETE CASCADE,
  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cop_change_order_id ON change_order_projects (change_order_id);
CREATE INDEX IF NOT EXISTS idx_cop_project_no ON change_order_projects (project_no);

-- 变更单文件（仅 primary=正文；历史 supplement 由迁移并入 primary）
CREATE TABLE IF NOT EXISTS change_order_pdfs (
  id              TEXT PRIMARY KEY,
  change_order_id INTEGER NOT NULL,
  file_name       TEXT NOT NULL,
  file_path       TEXT NOT NULL,
  file_md5        TEXT,
  file_size       INTEGER,
  mime_type       TEXT NOT NULL DEFAULT 'application/pdf',
  attachment_type     TEXT NOT NULL DEFAULT 'primary',
  sort_order          INTEGER NOT NULL DEFAULT 0,
  is_current          INTEGER NOT NULL DEFAULT 1,
  original_file_name  TEXT,
  remark              TEXT,
  deleted_at          TEXT,
  created_at          TEXT NOT NULL,
  FOREIGN KEY (change_order_id) REFERENCES change_orders (id) ON DELETE CASCADE,
  CHECK (attachment_type IN ('primary', 'supplement'))
);

CREATE INDEX IF NOT EXISTS idx_change_order_pdfs_order_id ON change_order_pdfs (change_order_id);
CREATE INDEX IF NOT EXISTS idx_change_order_pdfs_md5 ON change_order_pdfs (file_md5);
CREATE INDEX IF NOT EXISTS idx_change_order_pdfs_deleted_at ON change_order_pdfs (deleted_at);

-- 数据库备份记录
CREATE TABLE IF NOT EXISTS backup_records (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  filename      VARCHAR(256) NOT NULL,
  file_size     INTEGER NOT NULL DEFAULT 0,
  status        VARCHAR(16) NOT NULL DEFAULT 'success',
  error_message TEXT,
  trigger_type  VARCHAR(16) NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_backup_records_created_at ON backup_records (created_at);
