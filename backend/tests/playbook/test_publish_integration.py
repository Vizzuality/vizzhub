"""Integration tests for the full publish pipeline end-to-end."""

from __future__ import annotations

import json

import pytest

from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.modules.playbook.services.publish_service import PublishService


class TestPublishIntegration:
    @pytest.mark.asyncio
    async def test_full_publish_flow(self, db_session):
        """End-to-end: create tree -> generate -> verify HTML structure."""
        culture = PlaybookNodeDB(
            title="Culture", slug="culture", type="group", position=0, is_public=True,
        )
        db_session.add(culture)
        await db_session.flush()

        values = PlaybookNodeDB(
            title="Our Values",
            slug="our-values",
            type="page",
            parent_id=culture.id,
            position=0,
            is_public=True,
        )
        growth = PlaybookNodeDB(
            title="Growth Framework",
            slug="growth-framework",
            type="page",
            parent_id=culture.id,
            position=1,
            is_public=True,
        )
        db_session.add_all([values, growth])
        await db_session.flush()

        db_session.add(
            PlaybookPageVersionDB(
                node_id=values.id,
                content="## Core Values\n\nWe believe in **impact**.",
                version=1,
            ),
        )
        db_session.add(
            PlaybookPageVersionDB(
                node_id=growth.id,
                content="## Growth\n\nContinuous learning.",
                version=1,
            ),
        )
        await db_session.flush()

        svc = PublishService()
        files = await svc._generate_site(db_session)

        assert "index.html" in files
        assert "culture/our-values.html" in files
        assert "culture/growth-framework.html" in files
        assert "culture/index.html" in files
        assert "assets/style.css" in files
        assert "assets/navigation.js" in files

        values_html = files["culture/our-values.html"].decode()
        assert "<strong>impact</strong>" in values_html
        assert "Our Values" in values_html

        assert "Culture" in values_html
        assert "Growth Framework" in values_html

        assert "growth-framework.html" in values_html

        manifest = json.loads(files["manifest.json"])
        assert manifest["page_count"] == 2
        assert "culture/our-values.html" in manifest["files"]

    @pytest.mark.asyncio
    async def test_private_pages_excluded(self, db_session):
        """Private pages should not appear in generated site."""
        public = PlaybookNodeDB(
            title="Public", slug="public", type="page", position=0, is_public=True,
        )
        private = PlaybookNodeDB(
            title="Private", slug="private", type="page", position=1, is_public=False,
        )
        db_session.add_all([public, private])
        await db_session.flush()
        db_session.add(
            PlaybookPageVersionDB(node_id=public.id, content="visible", version=1),
        )
        db_session.add(
            PlaybookPageVersionDB(node_id=private.id, content="hidden", version=1),
        )
        await db_session.flush()

        svc = PublishService()
        files = await svc._generate_site(db_session)

        assert "public.html" in files
        assert "private.html" not in files

    @pytest.mark.asyncio
    async def test_non_public_group_included_if_has_public_children(self, db_session):
        """Non-public group with public descendants should appear in nav."""
        group = PlaybookNodeDB(
            title="Internal", slug="internal", type="group", position=0, is_public=False,
        )
        db_session.add(group)
        await db_session.flush()
        page = PlaybookNodeDB(
            title="Visible",
            slug="visible",
            type="page",
            parent_id=group.id,
            position=0,
            is_public=True,
        )
        db_session.add(page)
        await db_session.flush()
        db_session.add(
            PlaybookPageVersionDB(node_id=page.id, content="content", version=1),
        )
        await db_session.flush()

        svc = PublishService()
        files = await svc._generate_site(db_session)

        assert "internal/visible.html" in files
        page_html = files["internal/visible.html"].decode()
        assert "Internal" in page_html
