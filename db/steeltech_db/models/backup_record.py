from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class BackupRecord(db.Model):
    __tablename__ = "backup_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "file_size": self.file_size,
            "status": self.status,
            "error_message": self.error_message,
            "trigger_type": self.trigger_type,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
