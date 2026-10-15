"""项目模型（细化模型 / 甲供模型）"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class ProjectModel(db.Model):
    """项目关联的细化/甲供模型记录；同一项目可有多条。"""

    __tablename__ = "project_models"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_no: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("projects.project_no", ondelete="CASCADE"),
        nullable=False,
    )
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)  # detail / jiagong
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_started"
    )  # not_started / in_progress / completed
    model_weight_tons: Mapped[Optional[float]] = mapped_column(nullable=True)
    model_path: Mapped[Optional[str]] = mapped_column(Text)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=_now_text)
    updated_at: Mapped[str] = mapped_column(
        String(32), nullable=False, default=_now_text, onupdate=_now_text
    )

    def to_dict(self, *, project_name: str = "", is_jiagongdan: bool = False) -> dict:
        return {
            "id": self.id,
            "projectNo": self.project_no,
            "projectName": project_name,
            "isJiagongdan": bool(is_jiagongdan),
            "modelType": self.model_type,
            "name": self.name,
            "status": self.status,
            "modelWeightTons": self.model_weight_tons,
            "modelPath": self.model_path or "",
            "remark": self.remark or "",
            "seq": self.seq,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
