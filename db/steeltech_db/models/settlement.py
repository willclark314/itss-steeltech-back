"""钢结构技术科结算模型"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class SettlementPricingBasis(db.Model):
    """结算定价依据（设计定价 / 细化定价）"""

    __tablename__ = "settlement_pricing_basis"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    pricing_code: Mapped[str] = mapped_column(String(32), nullable=False)
    item_name: Mapped[str] = mapped_column(String(512), nullable=False)
    calc_process: Mapped[Optional[str]] = mapped_column(Text)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "pricingCode": self.pricing_code,
            "itemName": self.item_name,
            "calcProcess": self.calc_process or "",
            "unitPrice": self.unit_price,
            "unit": self.unit,
            "remark": self.remark or "",
            "seq": self.seq,
        }


class SettlementRecord(db.Model):
    """结算记录（设计结算 / 细化结算）"""

    __tablename__ = "settlement_records"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    project_no: Mapped[Optional[str]] = mapped_column(String(64))
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    coefficient: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    pricing_code: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    settlement_year: Mapped[Optional[int]] = mapped_column(Integer)
    settlement_month: Mapped[Optional[int]] = mapped_column(Integer)
    issue_year: Mapped[Optional[int]] = mapped_column(Integer)
    issue_month: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "year": self.year,
            "month": self.month,
            "seq": self.seq,
            "category": self.category,
            "name": self.name,
            "projectNo": self.project_no or "",
            "quantity": self.quantity,
            "unit": self.unit,
            "unitPrice": self.unit_price,
            "totalPrice": self.total_price,
            "coefficient": self.coefficient,
            "pricingCode": self.pricing_code,
            "settlementYear": self.settlement_year,
            "settlementMonth": self.settlement_month,
            "issueYear": self.issue_year,
            "issueMonth": self.issue_month,
        }


class SettlementPendingItem(db.Model):
    """已完成但未结算的项目（无结算年月，仅有发图年月）"""

    __tablename__ = "settlement_pending_items"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    project_no: Mapped[Optional[str]] = mapped_column(String(64))
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    coefficient: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    pricing_code: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    issue_year: Mapped[Optional[int]] = mapped_column(Integer)
    issue_month: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "seq": self.seq,
            "name": self.name,
            "projectNo": self.project_no or "",
            "quantity": self.quantity,
            "unit": self.unit,
            "unitPrice": self.unit_price,
            "totalPrice": self.total_price,
            "coefficient": self.coefficient,
            "pricingCode": self.pricing_code,
            "issueYear": self.issue_year,
            "issueMonth": self.issue_month,
        }
