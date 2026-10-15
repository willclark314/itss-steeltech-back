"""休假周期策略 — 每人一条，定义工作/休假交替规则"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class PersonnelLeavePolicy(db.Model):
    __tablename__ = "personnel_leave_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    personnel_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    work_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=150
    )
    leave_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=19
    )
    cycle_start_date: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
    effective_from: Mapped[Optional[str]] = mapped_column(String(10))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "personnelId": self.personnel_id,
            "workDays": self.work_days,
            "leaveDays": self.leave_days,
            "cycleStartDate": self.cycle_start_date,
            "effectiveFrom": self.effective_from or "",
            "remark": self.remark or "",
            "createdAt": self.created_at or "",
            "updatedAt": self.updated_at or "",
        }
