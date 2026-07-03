"""Portfolio Overview import: parse xlsx -> staging, match, apply decisions."""

import io
from dataclasses import dataclass
from uuid import UUID

import structlog
from openpyxl import load_workbook
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_overview import MatchAction, PortfolioOverviewStagingDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.services.name_matching import Scored, rank

logger = structlog.get_logger()

_SHEET = "Categorised"
_HEADER_ROW = 2
_SEPARATOR = "only old projects"

# 1-based column numbers -> field
_COLS = {
    "name": 3,
    "main_partner": 4,
    "on_website": 5,
    "client_type_raw": 6,
    "service_raw": 7,
    "impact_area_raw": 8,
    "topics_raw": 9,
    "objective": 10,
    "short_description": 11,
    "stage": 12,
    "notes": 13,
    "last_update": 14,
    "web_copy": 15,
    "impact_story": 17,
    "client_contact": 18,
}


@dataclass
class StagedRow:
    row_index: int
    name: str
    main_partner: str | None = None
    on_website: bool | None = None
    client_type_raw: str | None = None
    service_raw: str | None = None
    impact_area_raw: str | None = None
    topics_raw: str | None = None
    objective: str | None = None
    short_description: str | None = None
    stage: str | None = None
    notes: str | None = None
    last_update: str | None = None
    web_copy: str | None = None
    impact_story: str | None = None
    client_contact: str | None = None
    is_old_project: bool = False


def _text(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if s.endswith(".0"):  # openpyxl reads bare years/ints as floats
        s = s[:-2]
    return s or None


def _yesno(value: object) -> bool | None:
    s = _text(value)
    if s is None:
        return None
    return s.lower().startswith("y")


def parse_overview_xlsx(content: bytes) -> list[StagedRow]:
    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb[_SHEET] if _SHEET in wb.sheetnames else wb.active
    rows: list[StagedRow] = []
    old_mode = False
    for idx, cells in enumerate(
        ws.iter_rows(min_row=_HEADER_ROW + 1, values_only=True), start=_HEADER_ROW + 1
    ):

        def col(field: str, _row: tuple = cells) -> object:
            i = _COLS[field] - 1
            return _row[i] if i < len(_row) else None

        name = _text(col("name"))
        if name is None:
            continue
        if _SEPARATOR in name.lower():
            old_mode = True
            continue
        rows.append(
            StagedRow(
                row_index=idx,
                name=name,
                main_partner=_text(col("main_partner")),
                on_website=_yesno(col("on_website")),
                client_type_raw=_text(col("client_type_raw")),
                service_raw=_text(col("service_raw")),
                impact_area_raw=_text(col("impact_area_raw")),
                topics_raw=_text(col("topics_raw")),
                objective=_text(col("objective")),
                short_description=_text(col("short_description")),
                stage=_text(col("stage")),
                notes=_text(col("notes")),
                last_update=_text(col("last_update")),
                web_copy=_text(col("web_copy")),
                impact_story=_text(col("impact_story")),
                client_contact=_text(col("client_contact")),
                is_old_project=old_mode,
            )
        )
    wb.close()
    return rows


async def replace_staging(
    db: AsyncSession, batch_id: UUID, rows: list[StagedRow]
) -> tuple[int, int]:
    await db.execute(delete(PortfolioOverviewStagingDB))
    old = 0
    for r in rows:
        db.add(
            PortfolioOverviewStagingDB(
                import_batch=batch_id,
                row_index=r.row_index,
                name=r.name,
                main_partner=r.main_partner,
                on_website=r.on_website,
                client_type_raw=r.client_type_raw,
                service_raw=r.service_raw,
                impact_area_raw=r.impact_area_raw,
                topics_raw=r.topics_raw,
                objective=r.objective,
                short_description=r.short_description,
                stage=r.stage,
                notes=r.notes,
                last_update=r.last_update,
                web_copy=r.web_copy,
                impact_story=r.impact_story,
                client_contact=r.client_contact,
                is_old_project=r.is_old_project,
            )
        )
        old += 1 if r.is_old_project else 0
    await db.flush()
    logger.info("portfolio_overview_uploaded", batch_id=str(batch_id), rows=len(rows), old=old)
    return len(rows), old


STRONG = 0.85
CANDIDATE_THRESHOLD = 0.35


@dataclass
class CandidateData:
    kind: str
    id: UUID
    name: str
    score: float


@dataclass
class SuggestedData:
    action: MatchAction
    program_id: UUID | None
    project_id: UUID | None
    score: float


@dataclass
class StagingMatchData:
    staging_id: UUID
    name: str
    is_old_project: bool
    client_type_raw: str | None
    service_raw: str | None
    impact_area_raw: str | None
    suggested: SuggestedData
    candidates: list[CandidateData]


async def _match_targets(
    db: AsyncSession,
) -> tuple[list[tuple[str, tuple[str, UUID, str]]], list[tuple[str, tuple[str, UUID, str]]]]:
    programs = (await db.execute(select(ProgramDB.id, ProgramDB.name))).all()
    projects = (
        await db.execute(
            select(ProjectDB.id, ProjectDB.name).where(
                ProjectDB.is_billable.is_(True),
                ProjectDB.is_absence.is_(False),
                ProjectDB.program_id.is_(None),
            )
        )
    ).all()
    prog_cands = [(p.name, ("program", p.id, p.name)) for p in programs]
    proj_cands = [(p.name, ("project", p.id, p.name)) for p in projects]
    return prog_cands, proj_cands


def _suggest(is_old: bool, ranked: list[Scored]) -> SuggestedData:
    if is_old:
        return SuggestedData(MatchAction.SKIP, None, None, 0.0)
    best_prog = next((s for s in ranked if s.payload[0] == "program"), None)
    if best_prog is not None and best_prog.score >= STRONG:
        return SuggestedData(MatchAction.LINK, best_prog.payload[1], None, best_prog.score)
    best_proj = next((s for s in ranked if s.payload[0] == "project"), None)
    if best_proj is not None and best_proj.score >= STRONG:
        return SuggestedData(MatchAction.CREATE, None, best_proj.payload[1], best_proj.score)
    return SuggestedData(MatchAction.CREATE, None, None, 0.0)


async def build_matches(db: AsyncSession, batch_id: UUID) -> list[StagingMatchData]:
    prog_cands, proj_cands = await _match_targets(db)
    all_cands = prog_cands + proj_cands
    staging = (
        (
            await db.execute(
                select(PortfolioOverviewStagingDB)
                .where(PortfolioOverviewStagingDB.import_batch == batch_id)
                .order_by(PortfolioOverviewStagingDB.row_index)
            )
        )
        .scalars()
        .all()
    )
    result: list[StagingMatchData] = []
    for row in staging:
        ranked = rank(row.name, all_cands, limit=5, threshold=CANDIDATE_THRESHOLD)
        candidates = [
            CandidateData(kind=s.payload[0], id=s.payload[1], name=s.payload[2], score=s.score)
            for s in ranked
        ]
        result.append(
            StagingMatchData(
                staging_id=row.id,
                name=row.name,
                is_old_project=row.is_old_project,
                client_type_raw=row.client_type_raw,
                service_raw=row.service_raw,
                impact_area_raw=row.impact_area_raw,
                suggested=_suggest(row.is_old_project, ranked),
                candidates=candidates,
            )
        )
    return result
