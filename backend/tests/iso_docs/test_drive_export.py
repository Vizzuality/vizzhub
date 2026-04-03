"""Tests for ISO Docs Google Drive export.

Tests the export service logic (MD→HTML, tree walk, mapping CRUD)
and API endpoints (status, trigger export, concurrent rejection).
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.api.deps import get_db
from app.core.models.job import Job, JobStatus, JobType
from app.main import app
from app.modules.iso_docs.models.drive_mapping import IsoDocDriveMappingDB
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.iso_docs.services.drive_export_service import DriveExportService

EDITOR_USER_ID = UUID("00000000-0000-0000-0000-000000000010")

EDITOR_TOKEN = TokenData(
    user_id=str(EDITOR_USER_ID),
    email="editor@test.com",
    roles=["user", "iso_docs_editor"],
    permissions=["iso_docs:edit"],
)

REGULAR_TOKEN = TokenData(
    user_id=str(EDITOR_USER_ID),
    email="user@test.com",
    roles=["user"],
    permissions=["scorecard:view"],
)


def _override_user(token: TokenData):
    async def _get_user() -> TokenData:
        return token
    return _get_user


@pytest_asyncio.fixture
async def _setup_db(db_session: AsyncSession):
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_tree(db_session: AsyncSession) -> dict:
    """Create a small tree: group with 2 pages."""
    group = IsoDocNodeDB(
        title="Policies",
        slug="policies",
        type="group",
        position=0,
    )
    db_session.add(group)
    await db_session.flush()

    page1 = IsoDocNodeDB(
        title="Security Policy",
        slug="security-policy",
        type="page",
        parent_id=group.id,
        position=0,
    )
    page2 = IsoDocNodeDB(
        title="Privacy Policy",
        slug="privacy-policy",
        type="page",
        parent_id=group.id,
        position=1,
    )
    db_session.add_all([page1, page2])
    await db_session.flush()

    v1 = IsoDocVersionDB(
        node_id=page1.id, content="# Security\n\nBe secure.", version=1
    )
    v2 = IsoDocVersionDB(
        node_id=page2.id, content="# Privacy\n\nBe private.", version=1
    )
    db_session.add_all([v1, v2])

    meta1 = IsoDocMetadataDB(
        node_id=page1.id,
        code="POL-001",
        status="approved",
        category="policy",
        standard=["ISO 27001"],
        clauses=["A.5.1"],
    )
    db_session.add(meta1)
    await db_session.flush()

    return {
        "group": group,
        "page1": page1,
        "page2": page2,
    }


class TestDriveExportService:
    """Unit tests for DriveExportService."""

    def test_to_html_with_metadata(self, sample_tree):
        """Markdown + metadata renders to HTML with header table."""
        svc = DriveExportService()
        meta = MagicMock()
        meta.code = "POL-001"
        meta.standard = ["ISO 27001"]
        meta.clauses = ["A.5.1"]
        meta.status = "approved"
        meta.doc_version = "2.0"

        meta.changelog = [{"version": "1.0", "date": "2024-01-01", "author": "Admin", "description": "Init"}]

        html = svc._to_html("Test Doc", "# Hello\n\nWorld", meta, "Policies")

        assert "Test Doc</h1>" in html
        assert "POL-001" in html
        assert "ISO 27001" in html
        assert "Policies" in html
        assert "Approved" in html
        assert "<h1>Hello</h1>" in html
        assert "<p>World</p>" in html
        assert "v1.0" in html
        assert "2024-01-01" in html
        assert "Admin" in html

    def test_to_html_without_metadata(self):
        """Markdown without metadata renders cleanly."""
        svc = DriveExportService()
        html = svc._to_html("Simple", "Just text", None)

        assert "Simple</h1>" in html
        assert "<p>Just text</p>" in html

    def test_to_html_escapes_special_chars(self):
        """HTML special characters in title are escaped."""
        svc = DriveExportService()
        html = svc._to_html("A <b>bold</b> & Title", "", None)
        assert "A &lt;b&gt;bold&lt;/b&gt; &amp; Title" in html

    @pytest.mark.asyncio
    async def test_load_data(self, db_session, sample_tree):
        """Loads nodes, latest versions, and metadata from DB."""
        svc = DriveExportService()
        nodes, versions_map, metadata_map = await svc._load_data(db_session)

        assert len(nodes) == 3
        assert sample_tree["page1"].id in versions_map
        assert sample_tree["page2"].id in versions_map
        assert sample_tree["page1"].id in metadata_map

    @pytest.mark.asyncio
    async def test_save_and_load_mappings(self, db_session, sample_tree):
        """Mappings are saved and retrievable."""
        svc = DriveExportService()
        cache: dict = {}
        await svc._save_mapping(
            db_session,
            sample_tree["page1"].id,
            "drive_file_abc",
            "document",
            cache,
        )

        mappings = await svc._load_mappings(db_session)
        assert sample_tree["page1"].id in mappings
        assert mappings[sample_tree["page1"].id] == "drive_file_abc"

    @pytest.mark.asyncio
    async def test_save_mapping_updates_existing(self, db_session, sample_tree):
        """Saving a mapping for the same node updates in place."""
        svc = DriveExportService()
        cache: dict = {}
        await svc._save_mapping(
            db_session, sample_tree["page1"].id, "old_id", "document", cache
        )
        await svc._save_mapping(
            db_session, sample_tree["page1"].id, "new_id", "document", cache
        )

        mappings = await svc._load_mappings(db_session)
        assert mappings[sample_tree["page1"].id] == "new_id"

    @pytest.mark.asyncio
    async def test_root_nodes_from_loaded_data(self, db_session, sample_tree):
        """Root-level nodes are correctly identified from loaded data."""
        svc = DriveExportService()
        nodes, _, _ = await svc._load_data(db_session)
        roots = sorted(
            [n for n in nodes if n.parent_id is None],
            key=lambda n: n.position,
        )
        assert len(roots) == 1
        assert roots[0].title == "Policies"


class TestDriveExportAPI:
    """Integration tests for Drive export API endpoints."""

    @pytest.mark.asyncio
    async def test_status_not_connected(self, _setup_db):
        """Status returns connected=false when no Drive token exists."""
        app.dependency_overrides[get_current_user] = _override_user(EDITOR_TOKEN)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.get("/api/iso-docs/drive/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False

    @pytest.mark.asyncio
    async def test_status_requires_editor(self, _setup_db):
        """Status endpoint rejects non-editors."""
        app.dependency_overrides[get_current_user] = _override_user(REGULAR_TOKEN)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.get("/api/iso-docs/drive/status")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_export_not_connected(self, _setup_db):
        """Export rejects when Drive is not connected."""
        app.dependency_overrides[get_current_user] = _override_user(EDITOR_TOKEN)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post("/api/iso-docs/drive/export")
        assert resp.status_code == 400
        assert "not connected" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_export_rejects_concurrent(self, _setup_db, db_session):
        """Export rejects if another export is already running."""
        job = Job(
            type=JobType.EXPORT_GDRIVE,
            status=JobStatus.RUNNING,
            name="Existing export",
            params={},
        )
        db_session.add(job)
        await db_session.flush()

        app.dependency_overrides[get_current_user] = _override_user(EDITOR_TOKEN)

        with patch(
            "app.modules.iso_docs.api.drive_export.GoogleDriveOAuth.get_valid_token",
            new_callable=AsyncMock,
            return_value="fake-token",
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                resp = await c.post("/api/iso-docs/drive/export")

        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_stale_job_gets_cleaned(self, _setup_db, db_session):
        """A pending job older than 10 minutes is marked FAILED and unblocks new exports."""
        stale_job = Job(
            type=JobType.EXPORT_GDRIVE,
            status=JobStatus.PENDING,
            name="Stale export",
            params={},
        )
        db_session.add(stale_job)
        await db_session.flush()

        stale_job.created_at = datetime.now(timezone.utc) - timedelta(minutes=15)
        await db_session.flush()

        app.dependency_overrides[get_current_user] = _override_user(EDITOR_TOKEN)

        with patch(
            "app.modules.iso_docs.api.drive_export.GoogleDriveOAuth.get_valid_token",
            new_callable=AsyncMock,
            return_value="fake-token",
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                resp = await c.post("/api/iso-docs/drive/export")

        # The export may fail for other reasons (no root folder), but the
        # stale job should have been cleaned up — not a 409.
        assert resp.status_code != 409

        await db_session.refresh(stale_job)
        assert stale_job.status == JobStatus.FAILED
        assert stale_job.result == {"error": "Timed out after 10 minutes"}
