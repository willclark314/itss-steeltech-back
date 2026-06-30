"""休假管理 — 业务逻辑层

覆盖：
- 休假策略 CRUD
- 休假记录 CRUD
- 日历聚合（计算计划 + 实际记录合并）
- 状态自动结算
"""

from __future__ import annotations

from datetime import date, datetime

from steeltech_db.extensions import db
from steeltech_db.models import Personnel, PersonnelLeaveEntry, PersonnelLeavePolicy, Role, RolePersonnel


# ── 默认策略参数 ──
DEFAULT_WORK_DAYS = 150
DEFAULT_LEAVE_DAYS = 19
POLICY_STAGGER_BASE_DATE = date(2020, 1, 1)  # 策略错开基准日


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> date:
    return date.today()


def _is_admin_personnel(personnel_id: str) -> bool:
    admin_role = (
        db.session.query(RolePersonnel)
        .join(Role, Role.id == RolePersonnel.role_id)
        .filter(RolePersonnel.personnel_id == personnel_id, Role.code == "admin")
        .first()
    )
    return admin_role is not None


def _can_access_personnel(
    target_personnel_id: str,
    *,
    viewer_personnel_id: str | None,
    viewer_is_admin: bool,
) -> bool:
    if viewer_is_admin:
        return True
    return bool(viewer_personnel_id and target_personnel_id == viewer_personnel_id)


def _empty_calendar(year: int, today: date) -> dict:
    return {
        "year": year,
        "today": today.isoformat(),
        "personnel": [],
        "policies": [],
        "actualEntries": [],
        "computedEntries": [],
        "lastLeaveAnchors": {},
        "earliestLeaveAnchors": {},
    }


def _ensure_policy_in_db(personnel_id: str) -> dict:
    """员工尚无入库策略时，写入默认策略并返回（持久化到 personnel_leave_policies）。"""
    existing = PersonnelLeavePolicy.query.filter_by(personnel_id=personnel_id).first()
    if existing:
        return existing.to_dict()

    base = POLICY_STAGGER_BASE_DATE.isoformat()
    now = _now()
    row = PersonnelLeavePolicy(
        id=f"POL_{personnel_id}",
        personnel_id=personnel_id,
        work_days=DEFAULT_WORK_DAYS,
        leave_days=DEFAULT_LEAVE_DAYS,
        cycle_start_date=base,
        effective_from=base,
        created_at=now,
        updated_at=now,
    )
    db.session.add(row)
    db.session.commit()
    return row.to_dict()


def _resolve_calendar_scope(
    *,
    viewer_personnel_id: str | None,
    viewer_is_admin: bool,
) -> tuple[str | None, bool]:
    """返回 (scope_personnel_id, is_scoped)。非管理员无 personnel_id 时 fail-closed。"""
    if viewer_is_admin:
        return None, False
    if not viewer_personnel_id:
        return None, True
    return viewer_personnel_id, True


# ════════════════════════════════════════════
#  策略
# ════════════════════════════════════════════


def list_policies(
    *,
    viewer_personnel_id: str | None = None,
    viewer_is_admin: bool = True,
) -> list[dict]:
    query = PersonnelLeavePolicy.query.order_by(PersonnelLeavePolicy.personnel_id)
    if not viewer_is_admin and viewer_personnel_id:
        query = query.filter_by(personnel_id=viewer_personnel_id)
    rows = query.all()
    return [r.to_dict() for r in rows]


def get_policy(policy_id: str) -> dict | None:
    row = PersonnelLeavePolicy.query.get(policy_id)
    return row.to_dict() if row else None


def get_policy_by_personnel(personnel_id: str) -> dict | None:
    row = PersonnelLeavePolicy.query.filter_by(personnel_id=personnel_id).first()
    return row.to_dict() if row else None


def save_policy(
    data: dict,
    *,
    editor_personnel_id: str | None = None,
    editor_is_admin: bool = True,
) -> tuple[dict | None, str | None, int]:
    """创建或更新一条策略（每人仅允许一条）"""
    policy_id = (data.get("id") or "").strip()
    personnel_id = (data.get("personnelId") or "").strip()
    work_days = data.get("workDays", DEFAULT_WORK_DAYS)
    leave_days = data.get("leaveDays", DEFAULT_LEAVE_DAYS)
    cycle_start = (data.get("cycleStartDate") or "").strip()
    effective_from = (data.get("effectiveFrom") or "").strip() or None
    remark = (data.get("remark") or "").strip() or None

    if not personnel_id:
        return None, "人员ID 不能为空", 400
    if not _can_access_personnel(
        personnel_id,
        viewer_personnel_id=editor_personnel_id,
        viewer_is_admin=editor_is_admin,
    ):
        return None, "无权限修改他人员工的休假策略", 403
    if not cycle_start:
        return None, "cycleStartDate 不能为空", 400
    try:
        work_days = int(work_days)
        leave_days = int(leave_days)
    except (TypeError, ValueError):
        return None, "workDays/leaveDays 必须为正整数", 400
    if work_days <= 0 or leave_days <= 0:
        return None, "workDays/leaveDays 必须为正整数", 400

    now = _now()

    existing: PersonnelLeavePolicy | None = None
    if policy_id:
        existing = PersonnelLeavePolicy.query.get(policy_id)
    if existing is None:
        existing = PersonnelLeavePolicy.query.filter_by(personnel_id=personnel_id).first()

    if existing is not None:
        existing.work_days = work_days
        existing.leave_days = leave_days
        existing.cycle_start_date = cycle_start
        existing.effective_from = effective_from or existing.effective_from
        existing.remark = remark
        existing.updated_at = now
    else:
        existing = PersonnelLeavePolicy(
            id=f"POL_{personnel_id}",
            personnel_id=personnel_id,
            work_days=work_days,
            leave_days=leave_days,
            cycle_start_date=cycle_start,
            effective_from=effective_from or cycle_start,
            remark=remark,
            created_at=now,
            updated_at=now,
        )
        db.session.add(existing)

    db.session.commit()
    return existing.to_dict(), None, 200


def delete_policy(policy_id: str) -> tuple[dict | None, str | None, int]:
    row = PersonnelLeavePolicy.query.get(policy_id)
    if row is None:
        return None, "策略不存在", 404
    db.session.delete(row)
    db.session.commit()
    return {"id": policy_id}, None, 200


# ════════════════════════════════════════════
#  休假记录
# ════════════════════════════════════════════


def list_entries(
    *,
    year: int | None = None,
    personnel_id: str | None = None,
    entry_type: str | None = None,
    status: str | None = None,
    viewer_personnel_id: str | None = None,
    viewer_is_admin: bool = True,
) -> list[dict]:
    q = PersonnelLeaveEntry.query
    if not viewer_is_admin and viewer_personnel_id:
        q = q.filter_by(personnel_id=viewer_personnel_id)
    elif personnel_id:
        q = q.filter_by(personnel_id=personnel_id)
    if entry_type:
        q = q.filter_by(type=entry_type)
    if status:
        q = q.filter_by(status=status)
    if year is not None:
        q = q.filter(
            PersonnelLeaveEntry.start_date <= f"{year}-12-31",
            PersonnelLeaveEntry.end_date >= f"{year}-01-01",
        )

    rows = q.order_by(PersonnelLeaveEntry.start_date.desc()).all()
    return [r.to_dict() for r in rows]


def get_entry(entry_id: str) -> dict | None:
    row = PersonnelLeaveEntry.query.get(entry_id)
    return row.to_dict() if row else None


def _auto_settle_status(
    start_date: str, end_date: str, desired_status: str | None = None
) -> str:
    """根据日期自动判定状态（创建 / 更新时调用）"""
    if desired_status == PersonnelLeaveEntry.STATUS_CANCELLED:
        return desired_status
    today = _today()
    sd = date.fromisoformat(start_date)
    ed = date.fromisoformat(end_date)
    if ed < today:
        return PersonnelLeaveEntry.STATUS_COMPLETED
    if sd > today:
        return PersonnelLeaveEntry.STATUS_PLANNED
    return PersonnelLeaveEntry.STATUS_ACTIVE


def save_entry(
    data: dict,
    *,
    editor_personnel_id: str | None = None,
    editor_is_admin: bool = True,
) -> tuple[dict | None, str | None, int]:
    """创建或更新一条休假记录"""
    entry_id = (data.get("id") or "").strip()
    personnel_id = (data.get("personnelId") or "").strip()
    entry_type = (data.get("type") or "regular").strip()
    start_date = (data.get("startDate") or "").strip()
    end_date = (data.get("endDate") or "").strip()
    planned_days = data.get("plannedDays", 0)
    actual_days = data.get("actualDays")
    desired_status = (data.get("status") or "").strip() or None
    parent_entry_id = (data.get("parentEntryId") or "").strip() or None
    reason = (data.get("reason") or "").strip() or None
    remark = (data.get("remark") or "").strip() or None

    # 校验
    if not personnel_id:
        return None, "人员ID 不能为空", 400

    if entry_id and not entry_id.startswith("COMP_"):
        existing_for_auth = PersonnelLeaveEntry.query.get(entry_id)
        if existing_for_auth is None:
            return None, "休假记录不存在", 404
        if not _can_access_personnel(
            existing_for_auth.personnel_id,
            viewer_personnel_id=editor_personnel_id,
            viewer_is_admin=editor_is_admin,
        ):
            return None, "无权限修改他人员工的休假记录", 403

    if not _can_access_personnel(
        personnel_id,
        viewer_personnel_id=editor_personnel_id,
        viewer_is_admin=editor_is_admin,
    ):
        return None, "无权限修改他人员工的休假记录", 403

    if entry_type not in PersonnelLeaveEntry.VALID_TYPES and entry_type != "request":
        return None, f"无效的休假类型: {entry_type}", 400
    if not start_date or not end_date:
        return None, "起止日期不能为空", 400
    if planned_days <= 0:
        return None, "计划天数必须 > 0", 400

    # 校验日期格式
    try:
        sd = date.fromisoformat(start_date)
        ed = date.fromisoformat(end_date)
    except ValueError:
        return None, "日期格式无效，应为 YYYY-MM-DD", 400
    if ed < sd:
        return None, "结束日期不能早于开始日期", 400

    # 日期与实际天数一致性校验
    expected_days = (ed - sd).days + 1
    if planned_days != expected_days:
        return None, f"计划天数({planned_days})与日期范围({start_date}~{end_date}, 共{expected_days}天)不一致", 400

    # 自动结算状态
    status = _auto_settle_status(start_date, end_date, desired_status)

    now = _now()

    if entry_id:
        existing = PersonnelLeaveEntry.query.get(entry_id)
        if existing is None:
            return None, "休假记录不存在", 404
        existing.personnel_id = personnel_id
        existing.type = entry_type
        existing.start_date = start_date
        existing.end_date = end_date
        existing.planned_days = planned_days
        existing.actual_days = actual_days
        existing.status = status
        existing.parent_entry_id = parent_entry_id
        existing.reason = reason
        existing.remark = remark
        existing.updated_at = now
    else:
        import uuid
        entry_id = f"LEAVE_{uuid.uuid4().hex[:12].upper()}"
        existing = PersonnelLeaveEntry(
            id=entry_id,
            personnel_id=personnel_id,
            type=entry_type,
            start_date=start_date,
            end_date=end_date,
            planned_days=planned_days,
            actual_days=actual_days,
            status=status,
            parent_entry_id=parent_entry_id,
            reason=reason,
            remark=remark,
            created_at=now,
            updated_at=now,
        )
        db.session.add(existing)

    db.session.commit()
    return existing.to_dict(), None, 200


def cancel_entry(
    entry_id: str,
    *,
    editor_personnel_id: str | None = None,
    editor_is_admin: bool = True,
) -> tuple[dict | None, str | None, int]:
    """取消一条休假记录（软取消，改状态为 cancelled）"""
    row = PersonnelLeaveEntry.query.get(entry_id)
    if row is None:
        return None, "休假记录不存在", 404
    if not _can_access_personnel(
        row.personnel_id,
        viewer_personnel_id=editor_personnel_id,
        viewer_is_admin=editor_is_admin,
    ):
        return None, "无权限修改他人员工的休假记录", 403
    if row.status == PersonnelLeaveEntry.STATUS_CANCELLED:
        return None, "该记录已取消", 400
    row.status = PersonnelLeaveEntry.STATUS_CANCELLED
    row.updated_at = _now()
    db.session.commit()
    return row.to_dict(), None, 200


def delete_entry(
    entry_id: str,
    *,
    editor_personnel_id: str | None = None,
    editor_is_admin: bool = True,
) -> tuple[dict | None, str | None, int]:
    """硬删除一条休假记录"""
    row = PersonnelLeaveEntry.query.get(entry_id)
    if row is None:
        return None, "休假记录不存在", 404
    if not _can_access_personnel(
        row.personnel_id,
        viewer_personnel_id=editor_personnel_id,
        viewer_is_admin=editor_is_admin,
    ):
        return None, "无权限修改他人员工的休假记录", 403
    db.session.delete(row)
    db.session.commit()
    return {"id": entry_id}, None, 200


# ════════════════════════════════════════════
#  日历聚合
# ════════════════════════════════════════════


def _compute_cycle_entries(
    policy: dict, year: int, today: date,
    anchor_override: str | None = None,
    future_only: bool = False,
) -> list[dict]:
    """根据策略计算某年内所有计划轮休段（计算值，不入库）

    anchor_override:
      结束日期最晚的已保存休假的 endDate。传入时，从该日期的下一工作日起算 workDays 后得到下一次休假。
    future_only:
      True 时仅返回尚未结束的条目，避免与实际记录重叠。
    """
    work_days = policy["workDays"]
    leave_days = policy["leaveDays"]
    cycle_days = work_days + leave_days
    personnel_id = policy["personnelId"]

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    if anchor_override:
        last_end = date.fromisoformat(anchor_override)
        # 休假结束次日为下一工作周期起点，再工作 workDays 天后开始休假
        cursor = date.fromordinal(last_end.toordinal() + 1)
    else:
        cycle_start = date.fromisoformat(policy["cycleStartDate"])
        # 无实际记录时从周期锚点正向推算，避免锚点之前出现虚假休假段
        cursor = cycle_start

    entries: list[dict] = []
    seq = 1

    search_end = date(year + 1, 12, 31)
    while cursor <= search_end:
        ls = date.fromordinal(cursor.toordinal() + work_days)
        le = date.fromordinal(ls.toordinal() + leave_days - 1)

        # future_only 模式：跳过已结束的条目
        if future_only and le < today:
            cursor = date.fromordinal(cursor.toordinal() + cycle_days)
            continue

        if le >= year_start and ls <= year_end:
            entries.append({
                "id": f"COMP_{personnel_id}_{seq}",
                "personnelId": personnel_id,
                "type": "regular",
                "startDate": ls.isoformat(),
                "endDate": le.isoformat(),
                "plannedDays": leave_days,
                "actualDays": None,
                "status": (
                    "completed" if le < today
                    else "active" if ls <= today <= le
                    else "planned"
                ),
                "parentEntryId": "",
                "reason": "",
                "remark": "",
                "computed": True,
            })
            seq += 1

        cursor = date.fromordinal(cursor.toordinal() + cycle_days)

    return entries


def get_calendar(
    year: int | None = None,
    *,
    viewer_personnel_id: str | None = None,
    viewer_is_admin: bool = True,
    include_computed: bool = True,
) -> dict:
    """
    获取休假日历聚合数据。
    返回:
      {
        year, today,
        personnel: [{id, name, team, ...}],
        policies: [...],
        actualEntries: [...],
        computedEntries: [...]
      }
    """
    if year is None:
        year = _today().year
    today = _today()

    scope_personnel_id, is_scoped = _resolve_calendar_scope(
        viewer_personnel_id=viewer_personnel_id,
        viewer_is_admin=viewer_is_admin,
    )
    if is_scoped and not scope_personnel_id:
        return _empty_calendar(year, today)

    # 在职人员（非管理员仅查本人）
    personnel_query = Personnel.query.filter_by(status="active")
    if scope_personnel_id:
        personnel_query = personnel_query.filter_by(id=scope_personnel_id)
    personnel_rows = personnel_query.order_by(Personnel.team, Personnel.name).all()
    personnel_list = [p.to_dict() for p in personnel_rows]

    # 策略
    policy_query = PersonnelLeavePolicy.query
    if scope_personnel_id:
        policy_query = policy_query.filter_by(personnel_id=scope_personnel_id)
    policies = [p.to_dict() for p in policy_query.all()]
    if scope_personnel_id and not any(
        p["personnelId"] == scope_personnel_id for p in policies
    ):
        policies.append(_ensure_policy_in_db(scope_personnel_id))

    # 实际休假记录
    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"
    entry_query = PersonnelLeaveEntry.query.filter(
        PersonnelLeaveEntry.end_date >= year_start,
        PersonnelLeaveEntry.start_date <= year_end,
    )
    if scope_personnel_id:
        entry_query = entry_query.filter_by(personnel_id=scope_personnel_id)
    actual_entries = [
        e.to_dict() for e in entry_query.order_by(PersonnelLeaveEntry.start_date).all()
    ]

    # 结束日期最晚的已保存休假（不受当前查看年份限制），用于推算下一次休假
    from sqlalchemy import desc as sa_desc

    latest_query = PersonnelLeaveEntry.query.filter(
        PersonnelLeaveEntry.status != PersonnelLeaveEntry.STATUS_CANCELLED,
    )
    if scope_personnel_id:
        latest_query = latest_query.filter_by(personnel_id=scope_personnel_id)
    # 按 end_date 取最晚，与入库先后无关
    all_latest_desc = latest_query.order_by(
        PersonnelLeaveEntry.personnel_id,
        sa_desc(PersonnelLeaveEntry.end_date),
        sa_desc(PersonnelLeaveEntry.start_date),
    ).all()

    last_entry_map: dict[str, str] = {}
    last_leave_anchors: dict[str, dict] = {}
    for e in all_latest_desc:
        if e.personnel_id not in last_entry_map:
            last_entry_map[e.personnel_id] = e.end_date
            last_leave_anchors[e.personnel_id] = {
                "startDate": e.start_date,
                "endDate": e.end_date,
            }

    # 最早入库休假（任意类型，用于向前网格推算）
    earliest_leave_anchors: dict[str, dict] = {}
    earliest_any_query = PersonnelLeaveEntry.query.filter(
        PersonnelLeaveEntry.status != PersonnelLeaveEntry.STATUS_CANCELLED,
    )
    if scope_personnel_id:
        earliest_any_query = earliest_any_query.filter_by(personnel_id=scope_personnel_id)
    for e in earliest_any_query.order_by(
        PersonnelLeaveEntry.personnel_id,
        PersonnelLeaveEntry.start_date,
    ).all():
        if e.personnel_id not in earliest_leave_anchors:
            earliest_leave_anchors[e.personnel_id] = {
                "startDate": e.start_date,
                "endDate": e.end_date,
            }

    # 计算计划轮休段；无实际记录时展示假设初始休假，有记录后仅推算未来段
    computed_entries: list[dict] = []
    if include_computed:
        for policy in policies:
            pid = policy["personnelId"]
            last_end = last_entry_map.get(pid)
            if last_end:
                computed_entries.extend(
                    _compute_cycle_entries(
                        policy, year, today,
                        anchor_override=last_end,
                        future_only=False,
                    )
                )
            else:
                computed_entries.extend(_compute_cycle_entries(policy, year, today))

    return {
        "year": year,
        "today": today.isoformat(),
        "personnel": personnel_list,
        "policies": policies,
        "actualEntries": actual_entries,
        "computedEntries": computed_entries,
        "lastLeaveAnchors": last_leave_anchors,
        "earliestLeaveAnchors": earliest_leave_anchors,
    }
