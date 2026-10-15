from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class MonthlyTraining(db.Model):
    __tablename__ = "monthly_trainings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    training_year: Mapped[str] = mapped_column(String(4), nullable=False)
    training_month: Mapped[str] = mapped_column(String(2), nullable=False)
    item_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    category_tag: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    trainer: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    archive_no: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    training_date: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    # 正文 PDF（培训记录正式文件，每条最多 1 个）
    content_file_name: Mapped[Optional[str]] = mapped_column(String(256))
    content_file_path: Mapped[Optional[str]] = mapped_column(Text)
    content_file_size: Mapped[Optional[int]] = mapped_column(Integer)
    content_mime_type: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))


class MonthlyTrainingMaterial(db.Model):
    __tablename__ = "monthly_training_materials"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    training_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("monthly_trainings.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="application/pdf")
    material_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class MonthlyTrainingPhoto(db.Model):
    __tablename__ = "monthly_training_photos"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    training_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("monthly_trainings.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/png")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
