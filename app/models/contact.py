from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class ContactForm(db.Model):
    __tablename__ = "contact_forms"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    received_date: Mapped[str] = mapped_column(String(32), nullable=False)
    urgency: Mapped[str] = mapped_column(String(32), nullable=False, default="普通")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    content: Mapped[Optional[str]] = mapped_column(Text)
    expect_reply_date: Mapped[Optional[str]] = mapped_column(String(32))
    parent_id: Mapped[Optional[str]] = mapped_column(String(64))
    root_id: Mapped[str] = mapped_column(String(64), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False, default="primary")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancel_scope: Mapped[Optional[str]] = mapped_column(String(16))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))


class ContactFormPdf(db.Model):
    __tablename__ = "contact_form_pdfs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contact_form_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("contact_forms.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="application/pdf")
    attachment_type: Mapped[str] = mapped_column(String(16), nullable=False, default="supplement")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
