"""Portfolio command handler — dispatches 4 write actions to backend services."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.program import ProgramDB
from app.core.models.taxonomy import TaxonomyDB, TaxonomyTermDB
from app.core.services.program_catalog import replace_program_terms, upsert_program_profile
from app.modules.portfolio.schemas.programs import ProgramProfileUpdate, ProgramTermsUpdate

logger = structlog.get_logger()

PROFILE_TEXT_FIELDS = (
    "objective",
    "short_description",
    "web_copy",
    "website_url",
    "impact_story",
    "main_partner",
    "stage",
)


async def _resolve_program(session: AsyncSession, target: str | None) -> ProgramDB:
    if not target:
        raise ValueError("target (program_id) is required")
    try:
        program_id = UUID(target)
    except ValueError as exc:
        raise ValueError(f"Invalid program_id: {target}") from exc
    program = (
        await session.execute(select(ProgramDB).where(ProgramDB.id == program_id))
    ).scalar_one_or_none()
    if program is None:
        raise ValueError(f"Program '{target}' not found")
    return program


async def _create_program(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("payload.name is required")
    existing = (
        await session.execute(select(ProgramDB).where(func.lower(ProgramDB.name) == name.lower()))
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError(f"A program named '{existing.name}' already exists")

    program = ProgramDB(name=name)
    session.add(program)
    await session.flush()
    await session.refresh(program)

    logger.info("mcp_portfolio_program_created", program_id=str(program.id), name=name)
    return {"program_id": str(program.id), "name": name}


async def _rename_program(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    program = await _resolve_program(session, target)
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("payload.name is required")

    old_name = program.name
    program.name = name
    await session.flush()

    logger.info(
        "mcp_portfolio_program_renamed",
        program_id=str(program.id),
        old_name=old_name,
        new_name=name,
    )
    return {"program_id": str(program.id), "name": name}


async def _update_profile(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    program = await _resolve_program(session, target)

    # Empty string means "clear the field" (MCP callers cannot send explicit
    # null for a subset of fields); absent keys are left untouched.
    fields = {
        key: (None if isinstance(value, str) and not value.strip() else value)
        for key, value in payload.items()
        if key in {*PROFILE_TEXT_FIELDS, "on_website"}
    }
    if not fields:
        raise ValueError("No profile fields provided")

    profile = await upsert_program_profile(
        session, program.id, ProgramProfileUpdate(**fields)
    )
    logger.info(
        "mcp_portfolio_profile_updated",
        program_id=str(program.id),
        fields=sorted(fields),
    )
    return {"program_id": str(program.id), "profile": profile.model_dump(mode="json")}


async def _resolve_terms(
    session: AsyncSession, taxonomy: TaxonomyDB, term_names: list[str]
) -> dict[str, TaxonomyTermDB]:
    wanted = {name.strip().lower(): name for name in term_names if name.strip()}
    rows = (
        (
            await session.execute(
                select(TaxonomyTermDB).where(
                    TaxonomyTermDB.taxonomy_id == taxonomy.id,
                    func.lower(TaxonomyTermDB.name).in_(wanted),
                    TaxonomyTermDB.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    found = {term.name.lower(): term for term in rows}
    unmatched = [original for key, original in wanted.items() if key not in found]
    if unmatched:
        raise ValueError(
            f"Terms not found in taxonomy '{taxonomy.name}': {', '.join(sorted(unmatched))}"
        )
    return found


async def _set_tags(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    program = await _resolve_program(session, target)
    taxonomy_ref = (payload.get("taxonomy") or "").strip()
    if not taxonomy_ref:
        raise ValueError("payload.taxonomy is required")
    taxonomy = (
        await session.execute(
            select(TaxonomyDB).where(
                or_(
                    func.lower(TaxonomyDB.slug) == taxonomy_ref.lower(),
                    func.lower(TaxonomyDB.name) == taxonomy_ref.lower(),
                )
            )
        )
    ).scalar_one_or_none()
    if taxonomy is None:
        raise ValueError(f"Taxonomy '{taxonomy_ref}' not found")

    term_names: list[str] = payload.get("term_names") or []
    found = await _resolve_terms(session, taxonomy, term_names)
    ordered_ids = [
        found[name.strip().lower()].id for name in term_names if name.strip().lower() in found
    ]

    primary_name = (payload.get("primary") or "").strip()
    primary_id = None
    if primary_name:
        primary_term = found.get(primary_name.lower())
        if primary_term is None:
            raise ValueError(f"Primary term '{primary_name}' must be among term_names")
        primary_id = primary_term.id

    chips = await replace_program_terms(
        session,
        program.id,
        ProgramTermsUpdate(
            taxonomy_id=taxonomy.id, term_ids=ordered_ids, primary_term_id=primary_id
        ),
        assigned_by=user_id,
    )
    logger.info(
        "mcp_portfolio_tags_set",
        program_id=str(program.id),
        taxonomy=taxonomy.slug,
        terms=[c.name for c in chips],
    )
    return {
        "program_id": str(program.id),
        "taxonomy": taxonomy.slug,
        "terms": [c.model_dump(mode="json") for c in chips],
    }


# ---------------------------------------------------------------------------
# Action dispatch
# ---------------------------------------------------------------------------

_ACTIONS: dict[str, object] = {
    "create_program": _create_program,
    "rename_program": _rename_program,
    "update_profile": _update_profile,
    "set_tags": _set_tags,
}


async def execute(
    action: str,
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    """Dispatch a portfolio write action to the appropriate handler."""
    handler = _ACTIONS.get(action)
    if handler is None:
        raise ValueError(f"Unknown portfolio action: '{action}'")
    return await handler(target, payload, user_id, session)
