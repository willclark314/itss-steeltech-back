from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Project(db.Model):
    __tablename__ = "projects"

    project_no: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    customer: Mapped[Optional[str]] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    received_date: Mapped[Optional[str]] = mapped_column(String(32))
    planned_start_date: Mapped[Optional[str]] = mapped_column(String(32))
    planned_end_date: Mapped[Optional[str]] = mapped_column(String(32))
    actual_start_date: Mapped[Optional[str]] = mapped_column(String(32))
    actual_end_date: Mapped[Optional[str]] = mapped_column(String(32))
    local_work_path: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))


class ProjectNature(db.Model):
    __tablename__ = "project_natures"

    project_no: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_no", ondelete="CASCADE"), primary_key=True
    )
    nature: Mapped[str] = mapped_column(String(16), primary_key=True)
    created_at: Mapped[Optional[str]] = mapped_column(String(32))


class ProjectPersonnel(db.Model):
    __tablename__ = "project_personnel"

    project_no: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_no", ondelete="CASCADE"), primary_key=True
    )
    personnel_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("personnel.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[Optional[str]] = mapped_column(String(32))


class ContactFormProject(db.Model):
    __tablename__ = "contact_form_projects"

    contact_form_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("contact_forms.id", ondelete="CASCADE"), primary_key=True
    )
    project_no: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_no", ondelete="CASCADE"), primary_key=True
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="own")
    source_contact_form_id: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
