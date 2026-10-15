from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class DirectorInterview(db.Model):
    __tablename__ = "director_interviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    employee_name: Mapped[str] = mapped_column(String(64), nullable=False)
    employee_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    division: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    position: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    interview_date: Mapped[str] = mapped_column(String(32), nullable=False)
    interview_topic: Mapped[str] = mapped_column(String(256), nullable=False)
    interview_content: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    conclusion: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    interviewer: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    interviewee: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))


class DirectorInterviewImage(db.Model):
    __tablename__ = "director_interview_images"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    interview_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("director_interviews.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/png")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
