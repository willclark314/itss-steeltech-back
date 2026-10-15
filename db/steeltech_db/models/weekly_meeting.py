from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class WeeklyMeeting(db.Model):
    __tablename__ = "weekly_meetings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    meeting_date: Mapped[str] = mapped_column(String(32), nullable=False)
    meeting_theme: Mapped[str] = mapped_column(String(256), nullable=False)
    location: Mapped[str] = mapped_column(String(256), nullable=False)
    host: Mapped[str] = mapped_column(String(64), nullable=False)
    recorder: Mapped[str] = mapped_column(String(64), nullable=False)
    attendees: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_items: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))


class WeeklyMeetingImage(db.Model):
    __tablename__ = "weekly_meeting_images"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("weekly_meetings.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="image/png")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class WeeklyMeetingScan(db.Model):
    __tablename__ = "weekly_meeting_scans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("weekly_meetings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mime_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="application/pdf"
    )
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
