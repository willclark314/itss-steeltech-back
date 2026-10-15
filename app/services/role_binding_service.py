from __future__ import annotations

from steeltech_db.extensions import db
from steeltech_db.models import Personnel, Role, RolePersonnel, RoleWorkshop


def normalize_workshop(value: str | None) -> str:
    return (value or "").strip()


def get_personnel_role_ids(personnel_id: str) -> set[str]:
    if not personnel_id:
        return set()

    person = Personnel.query.get(personnel_id)
    if person is None or person.status != "active":
        return set()

    direct_rows = (
        db.session.query(RolePersonnel.role_id)
        .join(Role, Role.id == RolePersonnel.role_id)
        .filter(
            RolePersonnel.personnel_id == personnel_id,
            Role.status == "active",
        )
        .all()
    )
    direct_ids = {row.role_id for row in direct_rows}

    workshop = normalize_workshop(person.workshop)
    workshop_rows = (
        db.session.query(RoleWorkshop.role_id)
        .join(Role, Role.id == RoleWorkshop.role_id)
        .filter(
            RoleWorkshop.workshop == workshop,
            Role.status == "active",
        )
        .all()
    )
    workshop_ids = {row.role_id for row in workshop_rows}

    return direct_ids | workshop_ids


def personnel_has_role_code(personnel_id: str, role_code: str) -> bool:
    code = (role_code or "").strip()
    if not code or not personnel_id:
        return False

    role_ids = get_personnel_role_ids(personnel_id)
    if not role_ids:
        return False

    return (
        db.session.query(Role.id)
        .filter(Role.id.in_(role_ids), Role.code == code, Role.status == "active")
        .first()
        is not None
    )
