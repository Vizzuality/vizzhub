"""REST API for per-project private CLAUDE.md registrations."""

import re
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.config import get_settings
from app.core.api.deps import DBSession
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.devstack.api.deps import DevstackManager, DevstackViewer
from app.modules.devstack.models.project_context import DevstackProjectContextDB
from app.modules.devstack.services.project_context_github import (
    AlreadyExistsError,
    CommitError,
    FetchError,
    ProjectContextGitHubClient,
)
from app.modules.devstack.services.project_context_service import (
    DevstackProjectContextService,
    DuplicateSlugError,
    ProjectAlreadyLinkedError,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/project-contexts", tags=["devstack-contexts"])

SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")


class ProjectContextResponse(BaseModel):
    id: UUID
    slug: str
    project_id: UUID
    project_name: str | None
    description: str | None
    # Populated only by the POST (create) endpoint. github_seeded is True if
    # <slug>/CLAUDE.md exists in the repo after this request — either freshly
    # seeded here or pre-existing and explicitly associated. False with
    # github_error set if seeding failed (missing token, repo unreachable,
    # commit rejected). GET/PUT/LIST leave both as None.
    github_seeded: bool | None = None
    github_error: str | None = None


class ProjectContextCreate(BaseModel):
    slug: Annotated[str, Field(min_length=1, max_length=64)]
    project_id: UUID
    description: str | None = None
    # When True, skip the GitHub seed and assume `<slug>/CLAUDE.md` already
    # exists in the repo. Set by the UI after the user confirms association
    # with a pre-existing file (the pre-check surfaced it via 409).
    associate_existing: bool = False

    @field_validator("slug")
    @classmethod
    def _slug_shape(cls, v: str) -> str:
        if not SLUG_PATTERN.fullmatch(v):
            raise ValueError("slug must match ^[a-z0-9-]+$")
        return v


class ProjectContextUpdate(BaseModel):
    """Only description is mutable. slug and project_id present as placeholders so
    we can detect them and return 400 (not the Pydantic 422 from extra='forbid')."""
    description: str | None = None
    slug: str | None = None
    project_id: UUID | None = None


def _to_response(
    ctx: DevstackProjectContextDB,
    project_name: str | None,
    *,
    github_seeded: bool | None = None,
    github_error: str | None = None,
) -> ProjectContextResponse:
    return ProjectContextResponse(
        id=ctx.id,
        slug=ctx.slug,
        project_id=ctx.project_id,
        project_name=project_name,
        description=ctx.description,
        github_seeded=github_seeded,
        github_error=github_error,
    )


def _render_seed_template(slug: str, project_name: str, description: str | None) -> str:
    """Initial CLAUDE.md content created when registering a new Project Context.

    Deliberately minimal — the intent is to provide a starting scaffold that
    devs will iterate on through Claude Code, not a comprehensive template.
    """
    lines = [f"# {project_name}", ""]
    if description:
        lines.extend([description, ""])
    lines.extend(
        [
            "<!-- Private project context synced via VizzHub DevStack.",
            f"     Slug: {slug}",
            "     Edit through Claude Code and publish with \"publica los cambios\". -->",
            "",
        ]
    )
    return "\n".join(lines)


async def _check_github_file_exists(db, slug: str) -> bool | None:
    """Return whether `<slug>/CLAUDE.md` already lives in the private repo.

    Returns True/False if we could check, or None if we couldn't (token
    missing or GitHub unreachable). In the None case the caller should
    fall through to the normal seed flow — any underlying issue will be
    surfaced again via `github_error`.
    """
    token = await IntegrationTokenService.get_token(db, "github")
    if not token:
        return None
    settings = get_settings()
    client = ProjectContextGitHubClient(
        repo=settings.devstack_project_contexts_repo,
        token=token,
        committer_name=settings.devstack_project_contexts_committer_name,
        committer_email=settings.devstack_project_contexts_committer_email,
    )
    try:
        return await client.file_exists(slug)
    except FetchError:
        return None


async def _seed_github_claude_md(
    db,
    slug: str,
    project_name: str,
    description: str | None,
    user_id: UUID,
    user_email: str | None,
) -> tuple[bool, str | None]:
    """Attempt to create `<slug>/CLAUDE.md` in the private repo.

    Returns (seeded, error_message). Never raises — missing token, unreachable
    repo, or "file already exists" are reported as errors in the response so
    the caller can decide (and the DB mapping remains valid either way).
    """
    token = await IntegrationTokenService.get_token(db, "github")
    if not token:
        return False, "GitHub integration token not configured in VizzHub"

    settings = get_settings()
    user_row = await db.get(UserDB, user_id)
    author_name = user_row.name if user_row and user_row.name else (user_email or "VizzHub User")
    author_email = user_email or settings.devstack_project_contexts_committer_email

    client = ProjectContextGitHubClient(
        repo=settings.devstack_project_contexts_repo,
        token=token,
        committer_name=settings.devstack_project_contexts_committer_name,
        committer_email=settings.devstack_project_contexts_committer_email,
    )
    content = _render_seed_template(slug, project_name, description)
    try:
        await client.create_file(
            slug=slug,
            content=content,
            author_name=author_name,
            author_email=author_email,
            message=f"Seed {slug}/CLAUDE.md via VizzHub",
        )
        return True, None
    except AlreadyExistsError:
        # The file is already there — the mapping is still valid; this is
        # the common case when re-registering a context after a previous
        # delete, or when the admin pre-seeded the file by hand.
        return False, "File already exists in GitHub — mapping linked to it"
    except CommitError as exc:
        return False, f"GitHub rejected the seed commit: {exc}"
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        return False, f"Seed failed: {exc}"


@router.get("", responses={403: {"description": "Not authorized"}})
async def list_project_contexts(
    db: DBSession, user: DevstackViewer
) -> list[ProjectContextResponse]:
    result = await db.execute(
        select(DevstackProjectContextDB, ProjectDB.name)
        .join(ProjectDB, DevstackProjectContextDB.project_id == ProjectDB.id)
        .order_by(DevstackProjectContextDB.slug)
    )
    return [_to_response(ctx, name) for ctx, name in result.all()]


@router.post(
    "",
    status_code=201,
    responses={
        403: {"description": "Not authorized"},
        409: {
            "description": (
                "Slug already registered, project already linked, or "
                "`<slug>/CLAUDE.md` already exists in GitHub (code="
                "github_file_exists; resubmit with associate_existing=true)."
            )
        },
        422: {"description": "Invalid slug shape or project not found"},
    },
)
async def create_project_context(
    body: ProjectContextCreate, db: DBSession, user: DevstackManager
) -> ProjectContextResponse:
    project = await db.get(ProjectDB, body.project_id)
    if project is None:
        raise HTTPException(status_code=422, detail="Project not found")

    # Pre-check: if the file is already in GitHub and the caller hasn't
    # explicitly opted into linking to it, bounce with a structured 409 so
    # the UI can ask the user to confirm association. Never creates a row
    # in this branch — prevents the "DB row orphaned by seed fail" trap.
    if not body.associate_existing:
        exists = await _check_github_file_exists(db, body.slug)
        if exists is True:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "github_file_exists",
                    "slug": body.slug,
                    "message": (
                        f"{body.slug}/CLAUDE.md already exists in GitHub. "
                        "Resubmit with associate_existing=true to link "
                        "this mapping to the existing file without "
                        "modifying it."
                    ),
                },
            )

    svc = DevstackProjectContextService(db)
    try:
        ctx = await svc.create(
            slug=body.slug,
            project_id=body.project_id,
            description=body.description,
        )
    except DuplicateSlugError:
        raise HTTPException(status_code=409, detail=f"Slug '{body.slug}' already exists")
    except ProjectAlreadyLinkedError:
        raise HTTPException(
            status_code=409,
            detail=f"Project {body.project_id} already has a linked context",
        )

    if body.associate_existing:
        github_seeded = True
        github_error = None
        logger.info(
            "project_context_associated",
            slug=body.slug,
            project_id=str(project.id),
        )
    else:
        github_seeded, github_error = await _seed_github_claude_md(
            db,
            slug=body.slug,
            project_name=project.name,
            description=body.description,
            user_id=UUID(user.user_id),
            user_email=user.email,
        )
        if github_seeded:
            logger.info("project_context_seeded", slug=body.slug, project_id=str(project.id))
        else:
            logger.warning(
                "project_context_seed_failed",
                slug=body.slug,
                project_id=str(project.id),
                reason=github_error,
            )

    return _to_response(
        ctx,
        project.name,
        github_seeded=github_seeded,
        github_error=github_error,
    )


@router.get(
    "/{context_id}",
    responses={
        403: {"description": "Not authorized"},
        404: {"description": "Project context not found"},
    },
)
async def get_project_context(
    context_id: UUID, db: DBSession, user: DevstackViewer
) -> ProjectContextResponse:
    svc = DevstackProjectContextService(db)
    ctx = await svc.get(context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Project context not found")
    project = await db.get(ProjectDB, ctx.project_id)
    return _to_response(ctx, project.name if project else None)


@router.put(
    "/{context_id}",
    responses={
        400: {"description": "Attempt to change immutable field (slug or project_id)"},
        403: {"description": "Not authorized"},
        404: {"description": "Project context not found"},
    },
)
async def update_project_context(
    context_id: UUID,
    body: ProjectContextUpdate,
    db: DBSession,
    user: DevstackManager,
) -> ProjectContextResponse:
    if body.slug is not None or body.project_id is not None:
        raise HTTPException(status_code=400, detail="slug and project_id are immutable after creation")

    svc = DevstackProjectContextService(db)
    try:
        ctx = await svc.update(context_id, description=body.description)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project context not found")
    project = await db.get(ProjectDB, ctx.project_id)
    return _to_response(ctx, project.name if project else None)


@router.delete(
    "/{context_id}",
    status_code=204,
    responses={
        403: {"description": "Not authorized"},
        404: {"description": "Project context not found"},
    },
)
async def delete_project_context(
    context_id: UUID, db: DBSession, user: DevstackManager
) -> None:
    svc = DevstackProjectContextService(db)
    ctx = await svc.get(context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Project context not found")
    await svc.delete(context_id)
