from __future__ import annotations

from flask import current_app
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity

from steeltech_db.extensions import db
from steeltech_db.models import AccountPassword, Personnel, Role, RolePersonnel
from steeltech_db.seed import DEV_USER_PROFILES

DEV_USERNAMES = frozenset({"admin", "user"})


def get_account_password(account: str) -> str:
    row = AccountPassword.query.filter_by(account=account).first()
    if row:
        return row.password
    return current_app.config["DEFAULT_LOGIN_PASSWORD"]


def set_account_password(account: str, password: str) -> None:
    row = AccountPassword.query.filter_by(account=account).first()
    if row is None:
        row = AccountPassword(account=account, password=password)
        db.session.add(row)
    else:
        row.password = password
    db.session.commit()


def verify_account_password(account: str, password: str) -> bool:
    return password == get_account_password(account)


def find_personnel_by_employee_no(employee_no: str) -> Personnel | None:
    return Personnel.query.filter_by(employee_no=employee_no).first()


def find_personnel_by_id(personnel_id: str) -> Personnel | None:
    return Personnel.query.get(personnel_id)


def build_login_user(
    account: str,
    login_type: str,
    profile: dict,
    *,
    personnel_id: str | None = None,
    roles: list[str] | None = None,
) -> dict:
    return {
        "username": account,
        "name": profile.get("name", ""),
        "employeeNo": profile.get("employeeNo", ""),
        "personnelId": personnel_id or profile.get("id", ""),
        "loginType": login_type,
        "profile": profile,
        "roles": roles or [],
    }


def get_dev_user_profile(account: str) -> dict | None:
    if account not in DEV_USERNAMES:
        return None
    base = DEV_USER_PROFILES[account]
    return {
        "id": base["id"],
        "name": base["name"],
        "employeeNo": base["employeeNo"],
        "idCardNo": "",
        "passportNo": "",
        "passportExpiry": "",
        "position": base.get("position", ""),
        "nationality": "中国",
        "workshop": "钢结构技术科",
        "team": base["team"],
        "birthDate": "",
        "age": 0,
        "gender": "",
        "ethnicity": "",
        "nativePlace": "",
        "education": "",
        "homeAddress": "",
        "graduationSchool": "",
        "major": "",
        "indonesiaPhone": "",
        "domesticPhone": "",
        "dormitoryNo": "",
        "status": "active",
    }


def get_personnel_role_codes(personnel_id: str) -> list[str]:
    """获取人员拥有的角色编码列表"""
    rows = (
        db.session.query(Role.code)
        .join(RolePersonnel, Role.id == RolePersonnel.role_id)
        .filter(RolePersonnel.personnel_id == personnel_id, Role.status == "active")
        .all()
    )
    return [row.code for row in rows]


def login(username: str, password: str) -> tuple[dict | None, str | None, int]:
    account = username.strip()
    if not account or not password:
        return None, "请输入账号和密码", 400

    if account in DEV_USERNAMES:
        if not verify_account_password(account, password):
            return None, "工号或密码错误", 401
        profile = get_dev_user_profile(account)
        if profile is None:
            return None, "开发账号配置缺失", 500
        token = create_access_token(
            identity=account,
            additional_claims={"login_type": "dev", "personnel_id": profile["id"]},
        )
        dev_roles = ["admin"] if account == "admin" else ["detailer"]
        user = build_login_user(account, "dev", profile, roles=dev_roles)
        return {"token": token, "user": user}, None, 200

    person = find_personnel_by_employee_no(account)
    if person is None or not verify_account_password(account, password):
        return None, "工号或密码错误", 401
    if person.status != "active":
        return None, "该人员账号不可用", 403

    profile = person.to_dict()
    roles = get_personnel_role_codes(person.id)
    token = create_access_token(
        identity=account,
        additional_claims={"login_type": "personnel", "personnel_id": person.id},
    )
    user = build_login_user(account, "personnel", profile, personnel_id=person.id, roles=roles)
    return {"token": token, "user": user}, None, 200


def change_password(old_password: str, new_password: str) -> tuple[dict | None, str | None, int]:
    account = get_jwt_identity()
    claims = get_jwt()
    if not account:
        return None, "请先登录", 401

    old_password = old_password.strip()
    new_password = new_password.strip()
    if not old_password or not new_password:
        return None, "请输入当前密码和新密码", 400
    if len(new_password) < 6:
        return None, "新密码长度不能少于 6 位", 400
    if old_password == new_password:
        return None, "新密码不能与当前密码相同", 400
    if not verify_account_password(str(account), old_password):
        return None, "当前密码不正确", 400

    set_account_password(str(account), new_password)
    return {"message": "密码已更新"}, None, 200


def get_current_user() -> tuple[dict | None, str | None, int]:
    account = get_jwt_identity()
    claims = get_jwt()
    if not account:
        return None, "请先登录", 401

    login_type = claims.get("login_type", "personnel")
    if login_type == "dev":
        profile = get_dev_user_profile(str(account))
        if profile is None:
            return None, "开发账号配置缺失", 500
        dev_roles = ["admin"] if str(account) == "admin" else ["detailer"]
        return {"user": build_login_user(str(account), "dev", profile, roles=dev_roles)}, None, 200

    personnel_id = claims.get("personnel_id")
    person = find_personnel_by_id(str(personnel_id)) if personnel_id else None
    if person is None:
        person = find_personnel_by_employee_no(str(account))
    if person is None or person.status != "active":
        return None, "未找到人员信息", 404

    profile = person.to_dict()
    roles = get_personnel_role_codes(person.id)
    return {
        "user": build_login_user(str(account), "personnel", profile, personnel_id=person.id, roles=roles),
    }, None, 200
