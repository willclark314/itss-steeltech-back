"""月休计划锁定（按年月）模型"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class MonthlyRestLock(db.Model):
    __tablename__ = "monthly_rest_lock"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[int] = mapped_column(Integer, primary_key=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(64))
    locked_at: Mapped[Optional[str]] = mapped_column(String(32))

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "month": self.month,
            "lockedBy": self.locked_by,
            "lockedAt": self.locked_at,
            "locked": True,
        }

