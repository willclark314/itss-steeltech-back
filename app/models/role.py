from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Permission(db.Model):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    module: Mapped[str] = mapped_column(String(64), nullable=False)
    path: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    page_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    page_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(16), nullable=False, default="view")
    created_at: Mapped[Optional[str]] = mapped_column(String(32))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "module": self.module,
            "path": (self.path or "").strip(),
            "pageKey": (self.page_key or "").strip(),
            "pageName": (self.page_name or "").strip(),
            "action": (self.action or "view").strip() or "view",
        }


class Role(db.Model):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))


class RolePermission(db.Model):
    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[Optional[str]] = mapped_column(String(32))


class RolePersonnel(db.Model):
    __tablename__ = "role_personnel"

    role_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    personnel_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("personnel.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
