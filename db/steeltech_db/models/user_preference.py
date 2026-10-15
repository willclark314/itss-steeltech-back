from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from steeltech_db.extensions import db


class UserPreference(db.Model):
    __tablename__ = "user_preferences"

    account: Mapped[str] = mapped_column(String(64), primary_key=True)
    preference_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    preference_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))
