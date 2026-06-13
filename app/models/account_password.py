from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class AccountPassword(db.Model):
    __tablename__ = "account_passwords"

    account: Mapped[str] = mapped_column(String(128), primary_key=True)
    password: Mapped[str] = mapped_column(String(256), nullable=False)
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))
