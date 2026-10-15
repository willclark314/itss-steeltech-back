"""临时任务模型"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class TempTask(db.Model):
    __tablename__ = "temp_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    start_time: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[Optional[str]] = mapped_column(String(32))
    is_related_project: Mapped[int] = mapped_column(default=0)
    related_project_no: Mapped[Optional[str]] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))

    def to_dict(self, *, personnel_ids: list[str] | None = None, created_by_name: str | None = None) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description or "",
            "startTime": self.start_time,
            "completedAt": self.completed_at or "",
            "isRelatedProject": bool(self.is_related_project),
            "relatedProjectNo": self.related_project_no or "",
            "createdBy": self.created_by,
            "createdByName": created_by_name or "",
            "personnelIds": personnel_ids or [],
            "createdAt": self.created_at or "",
            "updatedAt": self.updated_at or "",
        }


class TempTaskPersonnel(db.Model):
    __tablename__ = "temp_task_personnel"

    temp_task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    personnel_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
