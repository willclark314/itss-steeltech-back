from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Tag(db.Model):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=_now_text)


class ProjectTag(db.Model):
    __tablename__ = "project_tags"

    project_no: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_no", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=_now_text)


class ContactFormTag(db.Model):
    __tablename__ = "contact_form_tags"

    contact_form_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("contact_forms.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=_now_text)
