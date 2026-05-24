"""Alias service: CRUD over ``accrual_aliases``.

Aliases persist the mapping Excel-code ↔ tracker-project with weights:
- 1:1 — single row, weight=1.0
- 1:N — multiple rows sharing ``excel_code`` (one Excel row → N tracker
  projects, e.g. OEM Main + WP7 split), weights summing to 1.0
- N:1 — multiple rows sharing ``project_id`` (N Excel rows → 1 tracker
  project, e.g. FHWPC phases), each weight=1.0

Manual aliases override the importer's auto-matching (code-based resolution).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.accrual.models.accrual_alias import AccrualAliasDB

logger = structlog.get_logger()


class AliasError(Exception):
    """Base exception for alias-service domain errors."""


class AliasNotFound(AliasError):
    """Alias ID not present."""


class AliasConflict(AliasError):
    """Unique constraint violation: (excel_code, project_id) already mapped."""


class ProjectNotFound(AliasError):
    """Referenced project does not exist."""


async def _assert_project_exists(db: AsyncSession, project_id: UUID) -> None:
    found = (await db.execute(select(ProjectDB.id).where(ProjectDB.id == project_id))).first()
    if not found:
        raise ProjectNotFound(f"Project {project_id} not found")


async def list_aliases(
    db: AsyncSession,
    *,
    excel_code: str | None = None,
    project_id: UUID | None = None,
) -> list[tuple[AccrualAliasDB, ProjectDB]]:
    """Return ``(alias, project)`` tuples. Always joined — the project is the
    key piece of context the UI needs."""
    stmt = (
        select(AccrualAliasDB, ProjectDB)
        .join(ProjectDB, ProjectDB.id == AccrualAliasDB.project_id)
        .order_by(AccrualAliasDB.excel_code, AccrualAliasDB.created_at)
    )
    if excel_code:
        stmt = stmt.where(AccrualAliasDB.excel_code == excel_code)
    if project_id is not None:
        stmt = stmt.where(AccrualAliasDB.project_id == project_id)
    return [(r[0], r[1]) for r in (await db.execute(stmt)).all()]


async def get_alias(db: AsyncSession, alias_id: UUID) -> AccrualAliasDB:
    alias = (
        await db.execute(select(AccrualAliasDB).where(AccrualAliasDB.id == alias_id))
    ).scalar_one_or_none()
    if alias is None:
        raise AliasNotFound(f"Alias {alias_id} not found")
    return alias


async def create_alias(
    db: AsyncSession,
    *,
    excel_code: str,
    project_id: UUID,
    weight: Decimal = Decimal("1.0"),
    notes: str | None = None,
    created_by: UUID | None = None,
) -> AccrualAliasDB:
    """Create one alias row. Raises ``AliasConflict`` on duplicate (code, project_id)."""
    await _assert_project_exists(db, project_id)
    alias = AccrualAliasDB(
        excel_code=excel_code,
        project_id=project_id,
        weight=weight,
        notes=notes,
        created_by=created_by,
    )
    db.add(alias)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise AliasConflict(f"Alias ({excel_code}, {project_id}) already exists") from exc
    logger.info(
        "accrual_alias_created",
        alias_id=str(alias.id),
        excel_code=excel_code,
        project_id=str(project_id),
        weight=str(weight),
        created_by=str(created_by) if created_by else None,
    )
    return alias


async def update_alias(
    db: AsyncSession,
    *,
    alias_id: UUID,
    weight: Decimal | None = None,
    notes: str | None = None,
) -> AccrualAliasDB:
    """Patch weight / notes. ``None`` means "don't change"."""
    alias = await get_alias(db, alias_id)
    if weight is not None:
        alias.weight = weight
    if notes is not None:
        alias.notes = notes
    await db.flush()
    logger.info(
        "accrual_alias_updated",
        alias_id=str(alias_id),
        weight=str(alias.weight),
    )
    return alias


async def delete_alias(db: AsyncSession, *, alias_id: UUID) -> None:
    alias = await get_alias(db, alias_id)
    await db.delete(alias)
    await db.flush()
    logger.info(
        "accrual_alias_deleted",
        alias_id=str(alias_id),
        excel_code=alias.excel_code,
    )


async def bulk_create_aliases(
    db: AsyncSession,
    *,
    excel_code: str,
    mappings: list[tuple[UUID, Decimal, str | None]],
    created_by: UUID | None = None,
    replace_existing: bool = False,
) -> list[AccrualAliasDB]:
    """Create N alias rows for one Excel code in a single SAVEPOINT.

    ``mappings`` is a list of ``(project_id, weight, notes)``. When
    ``replace_existing`` is True, any existing aliases for this excel_code are
    deleted first (so the UI's "Map this row to these projects" flow is
    idempotent).
    """
    project_ids = [project_id for project_id, _w, _n in mappings]
    found_ids = set(
        (await db.execute(select(ProjectDB.id).where(ProjectDB.id.in_(project_ids))))
        .scalars()
        .all()
    )
    missing = [pid for pid in project_ids if pid not in found_ids]
    if missing:
        raise ProjectNotFound(f"Project {missing[0]} not found")

    savepoint = await db.begin_nested()
    try:
        if replace_existing:
            existing = (
                (
                    await db.execute(
                        select(AccrualAliasDB).where(AccrualAliasDB.excel_code == excel_code)
                    )
                )
                .scalars()
                .all()
            )
            for old in existing:
                await db.delete(old)
            await db.flush()

        created: list[AccrualAliasDB] = []
        for project_id, weight, notes in mappings:
            alias = AccrualAliasDB(
                excel_code=excel_code,
                project_id=project_id,
                weight=weight,
                notes=notes,
                created_by=created_by,
            )
            db.add(alias)
            created.append(alias)
        await db.flush()
        await savepoint.commit()
    except IntegrityError as exc:
        await savepoint.rollback()
        raise AliasConflict(f"Conflicting alias for excel_code={excel_code}") from exc
    except Exception:
        await savepoint.rollback()
        raise
    logger.info(
        "accrual_aliases_bulk_created",
        excel_code=excel_code,
        count=len(created),
        replaced=replace_existing,
    )
    return created
