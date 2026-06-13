from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class Personnel(db.Model):
    __tablename__ = "personnel"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    employee_no: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    id_card_no: Mapped[Optional[str]] = mapped_column(String(64))
    passport_no: Mapped[Optional[str]] = mapped_column(String(64))
    passport_expiry: Mapped[Optional[str]] = mapped_column(String(32))
    position: Mapped[Optional[str]] = mapped_column(String(128))
    nationality: Mapped[str] = mapped_column(String(32), nullable=False, default="中国")
    workshop: Mapped[Optional[str]] = mapped_column(String(128))
    team: Mapped[str] = mapped_column(String(64), nullable=False)
    birth_date: Mapped[Optional[str]] = mapped_column(String(32))
    age: Mapped[Optional[int]] = mapped_column(Integer)
    gender: Mapped[Optional[str]] = mapped_column(String(16))
    ethnicity: Mapped[Optional[str]] = mapped_column(String(32))
    native_place: Mapped[Optional[str]] = mapped_column(String(128))
    education: Mapped[Optional[str]] = mapped_column(String(64))
    home_address: Mapped[Optional[str]] = mapped_column(Text)
    graduation_school: Mapped[Optional[str]] = mapped_column(String(128))
    major: Mapped[Optional[str]] = mapped_column(String(128))
    indonesia_phone: Mapped[Optional[str]] = mapped_column(String(32))
    domestic_phone: Mapped[Optional[str]] = mapped_column(String(32))
    dormitory_no: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
    updated_at: Mapped[Optional[str]] = mapped_column(String(32))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "employeeNo": self.employee_no or "",
            "idCardNo": self.id_card_no or "",
            "passportNo": self.passport_no or "",
            "passportExpiry": self.passport_expiry or "",
            "position": self.position or "",
            "nationality": self.nationality or "",
            "workshop": self.workshop or "",
            "team": self.team or "",
            "birthDate": self.birth_date or "",
            "age": self.age or 0,
            "gender": self.gender or "",
            "ethnicity": self.ethnicity or "",
            "nativePlace": self.native_place or "",
            "education": self.education or "",
            "homeAddress": self.home_address or "",
            "graduationSchool": self.graduation_school or "",
            "major": self.major or "",
            "indonesiaPhone": self.indonesia_phone or "",
            "domesticPhone": self.domestic_phone or "",
            "dormitoryNo": self.dormitory_no or "",
            "status": self.status or "",
        }
