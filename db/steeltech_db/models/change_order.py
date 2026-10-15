from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class ChangeOrder(db.Model):
    __tablename__ = "change_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    received_date: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    deleted_at: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))


class ChangeOrderPdf(db.Model):
    __tablename__ = "change_order_pdfs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    change_order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("change_orders.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(256), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_md5: Mapped[Optional[str]] = mapped_column(String(32))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="application/pdf")
    attachment_type: Mapped[str] = mapped_column(String(16), nullable=False, default="primary")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_current: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    original_file_name: Mapped[Optional[str]] = mapped_column(String(256))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    deleted_at: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
