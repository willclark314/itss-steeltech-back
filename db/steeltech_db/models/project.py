from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Project(db.Model):
    __tablename__ = "projects"

    project_no: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    customer: Mapped[Optional[str]] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")  # not_started/active/done/paused/cancelled
    design_completed: Mapped[bool] = mapped_column(nullable=False, default=False)
    detail_completed: Mapped[bool] = mapped_column(nullable=False, default=False)
    tile_layout_completed: Mapped[bool] = mapped_column(nullable=False, default=False)
    floor_deck_layout_completed: Mapped[bool] = mapped_column(nullable=False, default=False)
    drawing_issue_enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    drawing_issue_year_month: Mapped[Optional[str]] = mapped_column(String(7))
    is_jiagongdan: Mapped[bool] = mapped_column(nullable=False, default=False)
    received_date: Mapped[Optional[str]] = mapped_column(String(32))
    derived_received_date: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True,
        doc="优先使用 received_date，为空时取关联联系单的最早 received_date，用于排序"
    )
    planned_start_date: Mapped[Optional[str]] = mapped_column(String(32))
    planned_end_date: Mapped[Optional[str]] = mapped_column(String(32))
    actual_start_date: Mapped[Optional[str]] = mapped_column(String(32))
    actual_end_date: Mapped[Optional[str]] = mapped_column(String(32))
    design_work_path: Mapped[Optional[str]] = mapped_column(Text)
    detail_work_path: Mapped[Optional[str]] = mapped_column(Text)
    local_work_path: Mapped[Optional[str]] = mapped_column(Text)
    structure_type: Mapped[Optional[str]] = mapped_column(String(32))
    estimated_weight_tons: Mapped[Optional[float]] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=_now_text)
    updated_at: Mapped[str] = mapped_column(
        String(32), nullable=False, default=_now_text, onupdate=_now_text
    )


class ProjectNature(db.Model):
    __tablename__ = "project_natures"

    project_no: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_no", ondelete="CASCADE"), primary_key=True
    )
    nature: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[Optional[str]] = mapped_column(String(32))


class ProjectPersonnel(db.Model):
    __tablename__ = "project_personnel"

    project_no: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_no", ondelete="CASCADE"), primary_key=True
    )
    personnel_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("personnel.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[Optional[str]] = mapped_column(String(32))


class ProjectDetailWorkflow(db.Model):
    """细化主流程：建模 → 调图 → 钢板排板。plate_layout_* 指细化后钢板排板，非排楼承板/排瓦。"""

    __tablename__ = "project_detail_workflows"

    project_no: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_no", ondelete="CASCADE"), primary_key=True
    )
    modeling_status: Mapped[str] = mapped_column(String(16), nullable=False, default="not_started")
    drawing_status: Mapped[str] = mapped_column(String(16), nullable=False, default="not_started")
    plate_layout_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    plate_layout_status: Mapped[str] = mapped_column(String(16), nullable=False, default="not_started")
    modeling_started_at: Mapped[Optional[str]] = mapped_column(String(32))
    modeling_completed_at: Mapped[Optional[str]] = mapped_column(String(32))
    drawing_started_at: Mapped[Optional[str]] = mapped_column(String(32))
    drawing_completed_at: Mapped[Optional[str]] = mapped_column(String(32))
    plate_layout_started_at: Mapped[Optional[str]] = mapped_column(String(32))
    plate_layout_completed_at: Mapped[Optional[str]] = mapped_column(String(32))
    model_weight_tons: Mapped[Optional[float]] = mapped_column(nullable=True)
    model_weight_updated_at: Mapped[Optional[str]] = mapped_column(String(32))
    model_weight_updated_by: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("personnel.id")
    )
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=_now_text)
    updated_at: Mapped[str] = mapped_column(
        String(32), nullable=False, default=_now_text, onupdate=_now_text
    )


class ProjectDesignWorkflow(db.Model):
    """设计项目流程：设计开始 / 设计结束（仅日期） / 设计面积。"""

    __tablename__ = "project_design_workflows"

    project_no: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_no", ondelete="CASCADE"), primary_key=True
    )
    design_started_at: Mapped[Optional[str]] = mapped_column(String(10))
    design_completed_at: Mapped[Optional[str]] = mapped_column(String(10))
    design_area_sqm: Mapped[Optional[float]] = mapped_column(nullable=True)
    design_area_updated_at: Mapped[Optional[str]] = mapped_column(String(32))
    design_area_updated_by: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("personnel.id")
    )
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=_now_text)
    updated_at: Mapped[str] = mapped_column(
        String(32), nullable=False, default=_now_text, onupdate=_now_text
    )


class ContactFormProject(db.Model):
    __tablename__ = "contact_form_projects"
    __table_args__ = (
        UniqueConstraint("contact_form_id", "project_no", name="uq_cfp_contact_project"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contact_form_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("contact_forms.id", ondelete="CASCADE"), nullable=False
    )
    project_no: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_no", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="own")
    source_contact_form_id: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[Optional[str]] = mapped_column(String(32))


class ChangeOrderProject(db.Model):
    __tablename__ = "change_order_projects"
    __table_args__ = (UniqueConstraint("change_order_id", "project_no", name="uq_cop_order_project"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("change_orders.id", ondelete="CASCADE"), nullable=False
    )
    project_no: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_no", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
