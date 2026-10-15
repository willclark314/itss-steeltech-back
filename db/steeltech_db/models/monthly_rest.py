"""月休计划模型"""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class MonthlyRest(db.Model):
    __tablename__ = "monthly_rest"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    personnel_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    rest_days: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))

    def to_dict(self) -> dict:
        try:
            days = json.loads(self.rest_days)
            if not isinstance(days, list):
                days = []
        except (json.JSONDecodeError, TypeError):
            days = []

        return {
            "id": self.id,
            "personnelId": self.personnel_id,
            "year": self.year,
            "month": self.month,
            "restDays": days,
        }
