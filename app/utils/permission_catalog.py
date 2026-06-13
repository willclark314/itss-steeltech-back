from __future__ import annotations

ACTION_LABELS = {
    "view": "查看",
    "create": "新增",
    "update": "编辑",
    "delete": "删除",
}

PAGE_DEFINITIONS = [
    {"page_key": "home", "page_name": "首页", "module": "门户", "path": "/home", "actions": ["view"]},
    {"page_key": "about", "page_name": "关于", "module": "门户", "path": "/portal/about", "actions": ["view"]},
    {
        "page_key": "contact",
        "page_name": "联系单",
        "module": "业务系统",
        "path": "/business/contact",
        "actions": ["view", "create", "update", "delete"],
    },
    {
        "page_key": "project",
        "page_name": "项目",
        "module": "业务系统",
        "path": "/business/project",
        "actions": ["view", "create", "update", "delete"],
    },
    {
        "page_key": "schedule",
        "page_name": "工作安排",
        "module": "业务系统",
        "path": "/business/schedule",
        "actions": ["view"],
    },
    {
        "page_key": "person",
        "page_name": "人员",
        "module": "人员系统",
        "path": "/personnel/person",
        "actions": ["view", "create", "update", "delete"],
    },
    {
        "page_key": "role",
        "page_name": "角色",
        "module": "人员系统",
        "path": "/personnel/role",
        "actions": ["view", "create", "update", "delete"],
    },
    {
        "page_key": "leave",
        "page_name": "休假",
        "module": "人员系统",
        "path": "/personnel/leave",
        "actions": ["view"],
    },
    {
        "page_key": "system-settings",
        "page_name": "全局配置",
        "module": "系统设置",
        "path": "/system/settings",
        "actions": ["view", "update"],
    },
]

MODULE_ORDER = list(dict.fromkeys(page["module"] for page in PAGE_DEFINITIONS))
PAGE_ORDER_MAP = {page["page_key"]: index for index, page in enumerate(PAGE_DEFINITIONS)}
MODULE_ORDER_MAP = {module: index for index, module in enumerate(MODULE_ORDER)}
ACTION_ORDER = ["view", "create", "update", "delete"]


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
