"""steeltech_db — ITSS Steeltech 数据库层（模型、配置、种子数据、迁移脚本）。"""

from steeltech_db.config import BaseConfig
from steeltech_db.defaults import (
    DEFAULT_LOCAL_WORK_PATH,
    DEFAULT_PATH_PATTERNS,
    DEFAULT_SERVER_IP,
    SETTINGS_KEY,
    LocalWorkPathConfig,
    normalize_ip_list,
    normalize_local_work_path_config,
    normalize_path_patterns,
)
from steeltech_db.extensions import db, migrate
from steeltech_db.models import (
    AccountPassword,
    ContactForm,
    ContactFormPdf,
    ContactFormProject,
    MonthlyRest,
    Permission,
    Personnel,
    Project,
    ProjectNature,
    ProjectPersonnel,
    Role,
    RolePermission,
    RolePersonnel,
    SystemSetting,
)
from steeltech_db.permission_catalog import (
    PAGE_DEFINITIONS,
    build_permission_catalog,
    sort_permissions,
)
from steeltech_db.seed import (
    DETAILER_PERMISSION_CODES,
    DEV_USER_PROFILES,
    bootstrap_sqlite_file,
    ensure_dev_users,
    ensure_schema,
    ensure_system_settings,
    migrate_contact_form_relations,
    seed_default_monthly_rest,
    seed_if_empty,
    sync_permission_catalog,
)

__all__ = [
    # config
    "BaseConfig",
    # defaults
    "DEFAULT_LOCAL_WORK_PATH",
    "DEFAULT_PATH_PATTERNS",
    "DEFAULT_SERVER_IP",
    "SETTINGS_KEY",
    "LocalWorkPathConfig",
    "normalize_ip_list",
    "normalize_local_work_path_config",
    "normalize_path_patterns",
    # extensions
    "db",
    "migrate",
    # models
    "AccountPassword",
    "ContactForm",
    "ContactFormPdf",
    "ContactFormProject",
    "MonthlyRest",
    "Permission",
    "Personnel",
    "Project",
    "ProjectNature",
    "ProjectPersonnel",
    "Role",
    "RolePermission",
    "RolePersonnel",
    "SystemSetting",
    # permission catalog
    "PAGE_DEFINITIONS",
    "build_permission_catalog",
    "sort_permissions",
    # seed
    "DETAILER_PERMISSION_CODES",
    "DEV_USER_PROFILES",
    "bootstrap_sqlite_file",
    "ensure_dev_users",
    "ensure_schema",
    "ensure_system_settings",
    "migrate_contact_form_relations",
    "seed_default_monthly_rest",
    "seed_if_empty",
    "sync_permission_catalog",
]
