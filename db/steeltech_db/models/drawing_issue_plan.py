"""钢构细化发图计划模型"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class DrawingIssuePlan(db.Model):
    __tablename__ = "drawing_issue_plans"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    project_name: Mapped[str] = mapped_column(String(512), nullable=False)
    project_no: Mapped[str] = mapped_column(String(64), nullable=False)
    component_weight_kg: Mapped[Optional[float]] = mapped_column(Float)
    # 细化图纸发出时间
    detail_planned_issue_date: Mapped[Optional[str]] = mapped_column(String(16))
    detail_actual_issue_date: Mapped[Optional[str]] = mapped_column(String(16))
    # 排楼承板图纸发出时间（细化页也可维护）
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
            "detailPlannedIssueDate": self.detail_planned_issue_date,
            "detailActualIssueDate": self.detail_actual_issue_date,
            "floorDeckPlannedIssueDate": self.floor_deck_planned_issue_date,
            "floorDeckActualIssueDate": self.floor_deck_actual_issue_date,
            "materialPrepListIssueDate": self.material_prep_list_issue_date,
            "remark": self.remark or "",
        }
