"""休假记录 — 每一次实际休假（计划轮休 / 延长 / 提前）"""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class PersonnelLeaveEntry(db.Model):
    __tablename__ = "personnel_leave_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    personnel_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    # 休假类型
    #   regular   — 计划轮休（按策略周期正常休）
    #   extended  — 延长休假（在原休假结束后追加天数）
    #   early     — 提前休假（未满足工作天数，提前申请休假）
    #   request   — 请假（手工提交的休假申请）
    type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="regular"
    )
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    planned_days: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_days: Mapped[Optional[int]] = mapped_column(Integer)
    # 状态
    #   planned   — 计划中（未开始）
    #   active    — 休假中
    #   completed — 已结束
    #   cancelled — 已取消
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="planned"
    )
    # extended / early 类型时，关联被延长或被打断的原休假记录
    parent_entry_id: Mapped[Optional[str]] = mapped_column(String(64))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "personnelId": self.personnel_id,
            "type": self.type,
            "startDate": self.start_date,
            "endDate": self.end_date,
            "plannedDays": self.planned_days,
            "actualDays": self.actual_days,
            "status": self.status,
            "parentEntryId": self.parent_entry_id or "",
            "reason": self.reason or "",
            "remark": self.remark or "",
            "createdAt": self.created_at or "",
            "updatedAt": self.updated_at or "",
        }

    # ── 类型 / 状态常量 ──

    TYPE_REGULAR = "regular"
    TYPE_EXTENDED = "extended"
    TYPE_EARLY = "early"
    TYPE_REQUEST = "request"

    STATUS_PLANNED = "planned"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    VALID_TYPES = {TYPE_REGULAR, TYPE_EXTENDED, TYPE_EARLY, TYPE_REQUEST}
    VALID_STATUSES = {STATUS_PLANNED, STATUS_ACTIVE, STATUS_COMPLETED, STATUS_CANCELLED}
