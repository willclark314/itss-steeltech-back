"""钢构设计发图计划模型"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class DesignDrawingIssuePlan(db.Model):
    __tablename__ = "design_drawing_issue_plans"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    project_name: Mapped[str] = mapped_column(String(512), nullable=False)
    project_no: Mapped[str] = mapped_column(String(64), nullable=False)
    component_weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    # 设计图纸发出时间
    design_planned_issue_date: Mapped[Optional[str]] = mapped_column(String(16))
    design_actual_issue_date: Mapped[Optional[str]] = mapped_column(String(16))
    # 排瓦图纸发出时间
    tile_layout_planned_issue_date: Mapped[Optional[str]] = mapped_column(String(16))
    tile_layout_actual_issue_date: Mapped[Optional[str]] = mapped_column(String(16))
    # 排楼承板图纸发出时间
    floor_deck_planned_issue_date: Mapped[Optional[str]] = mapped_column(String(16))
    floor_deck_actual_issue_date: Mapped[Optional[str]] = mapped_column(String(16))
    material_prep_list_issue_date: Mapped[Optional[str]] = mapped_column(String(16))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "year": self.year,
            "month": self.month,
            "seq": self.seq,
            "projectName": self.project_name,
            "projectNo": self.project_no,
            "componentWeightKg": self.component_weight_kg,
            "designPlannedIssueDate": self.design_planned_issue_date,
            "designActualIssueDate": self.design_actual_issue_date,
            "tileLayoutPlannedIssueDate": self.tile_layout_planned_issue_date,
            "tileLayoutActualIssueDate": self.tile_layout_actual_issue_date,
            "floorDeckPlannedIssueDate": self.floor_deck_planned_issue_date,
            "floorDeckActualIssueDate": self.floor_deck_actual_issue_date,
            "materialPrepListIssueDate": self.material_prep_list_issue_date,
            "remark": self.remark or "",
        }
