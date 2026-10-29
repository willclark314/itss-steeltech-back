from __future__ import annotations

ACTION_LABELS = {
    "view": "查看",
    "view-all": "查看全员",
    # 历史兼容：migrate_permission_action_constraint 仍可能写入 edit 行
    "edit": "编辑",
}

PAGE_DEFINITIONS = [
    {"page_key": "home", "page_name": "首页", "module": "门户", "path": "/home", "actions": ["view"]},
    {"page_key": "my", "page_name": "我的", "module": "门户", "path": "/portal/my", "actions": ["view"]},
    {"page_key": "about", "page_name": "关于", "module": "门户", "path": "/portal/about", "actions": ["view"]},
    {"page_key": "guide", "page_name": "说明", "module": "门户", "path": "/portal/guide", "actions": ["view"]},
    {
        "page_key": "contact-browse",
        "page_name": "联系单",
        "module": "钢构技术系统",
        "path": "/business/contact-browse",
        "actions": ["view"],
    },
    {
        "page_key": "contact",
        "page_name": "联系单管理",
        "module": "钢构技术系统",
        "path": "/business/contact",
        "actions": ["view"],
    },
    {
        "page_key": "change-order",
        "page_name": "变更单管理",
        "module": "钢构技术系统",
        "path": "/business/change-order",
        "actions": ["view"],
    },
    {
        "page_key": "project-browse",
        "page_name": "项目",
        "module": "钢构技术系统",
        "path": "/business/project-browse",
        "actions": ["view"],
    },
    {
        "page_key": "project",
        "page_name": "项目管理",
        "module": "钢构技术系统",
        "path": "/business/project",
        "actions": ["view"],
    },
    {
        "page_key": "schedule",
        "page_name": "工作安排",
        "module": "钢构技术系统",
        "path": "/business/schedule",
        "actions": ["view"],
    },
    {
        "page_key": "design-team-schedule",
        "page_name": "设计组排班",
        "module": "钢构技术系统",
        "path": "/business/design-team-schedule",
        "actions": ["view"],
    },
    {
        "page_key": "detail-team-schedule",
        "page_name": "细化组排班",
        "module": "钢构技术系统",
        "path": "/business/detail-team-schedule",
        "actions": ["view"],
    },
    {
        "page_key": "design-drawing-issue-plan",
        "page_name": "设计发图计划",
        "module": "钢构技术系统",
        "path": "/business/design-drawing-issue-plan",
        "actions": ["view"],
    },
    {
        "page_key": "drawing-issue-plan",
        "page_name": "细化发图计划",
        "module": "钢构技术系统",
        "path": "/business/drawing-issue-plan",
        "actions": ["view"],
    },
    {
        "page_key": "weekly-meeting",
        "page_name": "周例会",
        "module": "钢构技术系统",
        "path": "/business/weekly-meeting",
        "actions": ["view"],
    },
    {
        "page_key": "director-interview",
        "page_name": "主任座谈会",
        "module": "钢构技术系统",
        "path": "/business/director-interview",
        "actions": ["view"],
    },
    {
        "page_key": "monthly-training",
        "page_name": "月度培训",
        "module": "钢构技术系统",
        "path": "/business/monthly-training",
        "actions": ["view"],
    },
    {
        "page_key": "settlement-record",
        "page_name": "项目结算",
        "module": "钢构技术系统",
        "path": "/business/settlement-record",
        "actions": ["view"],
    },
    {
        "page_key": "project-model",
        "page_name": "项目模型管理",
        "module": "钢构技术系统",
        "path": "/business/project-model",
        "actions": ["view"],
    },
    {
        "page_key": "production-sample",
        "page_name": "示例页面",
        "module": "生产计划系统",
        "path": "/production/sample",
        "actions": ["view"],
    },
    {
        "page_key": "change-order-browse",
        "page_name": "变更单",
        "module": "生产计划系统",
        "path": "/production/change-order-browse",
        "actions": ["view"],
    },
    {
        "page_key": "production-contact",
        "page_name": "联系单登记",
        "module": "生产计划系统",
        "path": "/production/contact",
        "actions": ["view"],
    },
    {
        "page_key": "production-project-browse",
        "page_name": "项目概况",
        "module": "生产计划系统",
        "path": "/production/project-browse",
        "actions": ["view"],
    },
    {
        "page_key": "person",
        "page_name": "人员",
        "module": "人员系统",
        "path": "/personnel/person",
        "actions": ["view"],
    },
    {
        "page_key": "role",
        "page_name": "角色",
        "module": "人员系统",
        "path": "/personnel/role",
        "actions": ["view"],
    },
    {
        "page_key": "leave",
        "page_name": "年休",
        "module": "人员系统",
        "path": "/personnel/leave",
        "actions": ["view", "view-all"],
    },
    {
        "page_key": "monthly-rest",
        "page_name": "月休",
        "module": "人员系统",
        "path": "/personnel/monthly-rest",
        "actions": ["view"],
    },
    {
        "page_key": "system-settings",
        "page_name": "全局配置",
        "module": "系统设置",
        "path": "/system/settings",
        "actions": ["view"],
    },
    {
        "page_key": "page-config",
        "page_name": "页面配置",
        "module": "系统设置",
        "path": "/system/page-config",
        "actions": ["view"],
    },
]

MODULE_ORDER = list(dict.fromkeys(page["module"] for page in PAGE_DEFINITIONS))
PAGE_ORDER_MAP = {page["page_key"]: index for index, page in enumerate(PAGE_DEFINITIONS)}
MODULE_ORDER_MAP = {module: index for index, module in enumerate(MODULE_ORDER)}
ACTION_ORDER = ["view", "view-all"]
LEGACY_WRITE_ACTIONS = frozenset({"create", "update", "delete", "edit"})
ALLOWED_PERMISSION_ACTIONS = frozenset({"view", "view-all", "edit"})


def build_permission_catalog() -> list[dict]:
    catalog: list[dict] = []
    index = 1
    for page in PAGE_DEFINITIONS:
        for action in page["actions"]:
            catalog.append(
                {
                    "id": f"PERM{index:03d}",
                    "code": f"{page['page_key']}:{action}",
                    "name": ACTION_LABELS[action],
                    "module": page["module"],
                    "path": page["path"],
                    "page_key": page["page_key"],
                    "page_name": page["page_name"],
                    "action": action,
                }
            )
            index += 1
    return catalog


def sort_permissions(permissions: list[dict]) -> list[dict]:
    def sort_key(item: dict) -> tuple[int, int, int]:
        module_index = MODULE_ORDER_MAP.get(item.get("module", ""), 10_000)
        page_index = PAGE_ORDER_MAP.get(item.get("pageKey", ""), 10_000)
        action = item.get("action", "view")
        action_index = ACTION_ORDER.index(action) if action in ACTION_ORDER else 99
        return module_index, page_index, action_index

    return sorted(permissions, key=sort_key)
