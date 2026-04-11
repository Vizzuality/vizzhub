"""Users data access — team directory, functional areas, rates."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.rate import RateDB
from app.core.models.role import RoleDB, UserRoleDB
from app.core.models.user import UserDB


async def get_team(
    session: AsyncSession,
    *,
    active_only: bool = True,
    functional_area: str | None = None,
) -> list[dict]:
    """List users with their functional area, rate, dedication, and roles."""
    stmt = (
        select(
            UserDB.id,
            UserDB.email,
            UserDB.first_name,
            UserDB.last_name,
            UserDB.name,
            UserDB.active,
            UserDB.dedication,
            UserDB.requires_project_reporting,
            UserDB.slack_display_name,
            FunctionalAreaDB.name.label("functional_area"),
            RateDB.code.label("rate_code"),
        )
        .outerjoin(FunctionalAreaDB, UserDB.functional_area_id == FunctionalAreaDB.id)
        .outerjoin(RateDB, UserDB.rate_id == RateDB.id)
        .order_by(UserDB.first_name, UserDB.last_name, UserDB.email)
    )

    if active_only:
        stmt = stmt.where(UserDB.active.is_(True))
    if functional_area:
        stmt = stmt.where(FunctionalAreaDB.name == functional_area)

    result = await session.execute(stmt)
    rows = result.all()

    user_ids = [row.id for row in rows]
    roles_map = await _load_roles(session, user_ids)

    return [
        {
            "id": str(row.id),
            "email": row.email,
            "name": _display_name(row.first_name, row.last_name, row.name, row.email),
            "active": row.active,
            "functional_area": row.functional_area,
            "rate_code": row.rate_code,
            "dedication": float(row.dedication) if row.dedication is not None else None,
            "requires_project_reporting": row.requires_project_reporting,
            "slack_display_name": row.slack_display_name,
            "roles": roles_map.get(row.id, []),
        }
        for row in rows
    ]


async def get_detail(session: AsyncSession, user_id: str) -> dict | None:
    """Full detail for a single user."""
    stmt = (
        select(
            UserDB,
            FunctionalAreaDB.name.label("functional_area"),
            RateDB.code.label("rate_code"),
            RateDB.value.label("rate_value"),
        )
        .outerjoin(FunctionalAreaDB, UserDB.functional_area_id == FunctionalAreaDB.id)
        .outerjoin(RateDB, UserDB.rate_id == RateDB.id)
        .where(UserDB.id == user_id)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        return None

    user: UserDB = row[0]
    roles_map = await _load_roles(session, [user.id])

    return {
        "id": str(user.id),
        "email": user.email,
        "name": _display_name(user.first_name, user.last_name, user.name, user.email),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "active": user.active,
        "functional_area": row.functional_area,
        "rate_code": row.rate_code,
        "rate_value": float(row.rate_value) if row.rate_value is not None else None,
        "dedication": float(user.dedication) if user.dedication is not None else None,
        "requires_project_reporting": user.requires_project_reporting,
        "slack_display_name": user.slack_display_name,
        "last_login_at": user.last_login_at,
        "roles": roles_map.get(user.id, []),
    }


async def get_functional_areas(session: AsyncSession) -> list[dict]:
    """List all functional areas."""
    result = await session.execute(
        select(FunctionalAreaDB.id, FunctionalAreaDB.name)
        .order_by(FunctionalAreaDB.name)
    )
    return [
        {"id": str(row.id), "name": row.name}
        for row in result.all()
    ]


async def get_rates(session: AsyncSession) -> list[dict]:
    """List all rate bands."""
    result = await session.execute(
        select(RateDB.id, RateDB.code, RateDB.value)
        .order_by(RateDB.code)
    )
    return [
        {"id": str(row.id), "code": row.code, "value": float(row.value)}
        for row in result.all()
    ]


async def _load_roles(
    session: AsyncSession, user_ids: list,
) -> dict[str, list[str]]:
    """Batch-load role names for a list of user IDs."""
    if not user_ids:
        return {}
    stmt = (
        select(UserRoleDB.user_id, RoleDB.name)
        .join(RoleDB, UserRoleDB.role_id == RoleDB.id)
        .where(UserRoleDB.user_id.in_(user_ids))
        .order_by(RoleDB.name)
    )
    result = await session.execute(stmt)
    roles_map: dict[str, list[str]] = {}
    for row in result.all():
        roles_map.setdefault(row.user_id, []).append(row.name)
    return roles_map


def _display_name(
    first_name: str | None,
    last_name: str | None,
    name: str | None,
    email: str,
) -> str:
    """Build display name: first+last > name > email prefix."""
    parts = [p for p in (first_name, last_name) if p]
    if parts:
        return " ".join(parts)
    if name:
        return name
    return email.split("@")[0]
