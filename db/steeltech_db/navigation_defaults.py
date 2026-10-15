"""导航排序默认值 —— 与前端 appNavigation.ts 保持一致。"""

from __future__ import annotations

from dataclasses import dataclass, field

from steeltech_db.permission_catalog import PAGE_DEFINITIONS

NAVIGATION_ORDER_KEY = "navigation_order"

DEFAULT_NAVIGATION_SYSTEMS = ["portal", "business", "production", "personnel", "system"]

VALID_NAVIGATION_SYSTEMS = frozenset(DEFAULT_NAVIGATION_SYSTEMS)

DEFAULT_NAVIGATION_PAGES = [page["page_key"] for page in PAGE_DEFINITIONS]

# 页面配置中不可隐藏，避免无法再进入配置页
ALWAYS_VISIBLE_PAGES = frozenset({"page-config"})


@dataclass
class NavigationOrderConfig:
    systems: list[str] = field(default_factory=lambda: list(DEFAULT_NAVIGATION_SYSTEMS))
    pages: list[str] = field(default_factory=lambda: list(DEFAULT_NAVIGATION_PAGES))
    hidden_pages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "systems": list(self.systems),
            "pages": list(self.pages),
            "hiddenPages": list(self.hidden_pages),
        }


def get_default_navigation_order() -> NavigationOrderConfig:
    return NavigationOrderConfig()
