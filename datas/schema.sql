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

-- 页面权限（按页面分类，含查看/新增/编辑/删除等操作）
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
  CHECK (action IN ('view', 'create', 'update', 'delete'))
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

-- 项目
CREATE TABLE IF NOT EXISTS projects (
  project_no  TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  customer    TEXT,
  status              TEXT NOT NULL DEFAULT 'active',
  received_date       TEXT,
  planned_start_date  TEXT,
  planned_end_date    TEXT,
  actual_start_date   TEXT,
  actual_end_date     TEXT,
  local_work_path     TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  updated_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status);

-- 项目性质（设计 / 细化，可多选）
CREATE TABLE IF NOT EXISTS project_natures (
  project_no  TEXT NOT NULL,
  nature      TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (project_no, nature),
  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
  CHECK (nature IN ('design', 'detail'))
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

-- 联系单与项目关联（多对多，带来源语义）
CREATE TABLE IF NOT EXISTS contact_form_projects (
  contact_form_id         TEXT NOT NULL,
  project_no              TEXT NOT NULL,
  source_type             TEXT NOT NULL DEFAULT 'own',
  source_contact_form_id  TEXT,
  created_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  PRIMARY KEY (contact_form_id, project_no),
  FOREIGN KEY (contact_form_id) REFERENCES contact_forms (id) ON DELETE CASCADE,
  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
  CHECK (source_type IN ('own', 'inherited', 'added', 'cancelled'))
);

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
  attachment_type TEXT NOT NULL DEFAULT 'supplement',
  sort_order      INTEGER NOT NULL DEFAULT 0,
  remark          TEXT,
  created_at      TEXT NOT NULL,
  FOREIGN KEY (contact_form_id) REFERENCES contact_forms (id) ON DELETE CASCADE,
  CHECK (attachment_type IN ('primary', 'supplement'))
);

CREATE INDEX IF NOT EXISTS idx_contact_form_pdfs_contact_id ON contact_form_pdfs (contact_form_id);

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
