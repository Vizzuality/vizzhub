"""Tests for PublishService.publish orchestration method."""

from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock

from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.modules.playbook.models.publish_log import PlaybookPublishLogDB
from app.modules.playbook.services.publish_service import PublishService


class TestPublishOrchestration:
    @pytest.mark.asyncio
    async def test_publish_updates_log_on_success(self, db_session):
        svc = PublishService()
        page = PlaybookNodeDB(
            title="Hello", slug="hello", type="page", position=0, is_public=True,
        )
        db_session.add(page)
        await db_session.flush()
        db_session.add(PlaybookPageVersionDB(node_id=page.id, content="Hi", version=1))
        log = PlaybookPublishLogDB(status="running")
        db_session.add(log)
        await db_session.flush()

        with patch.object(svc, "_upload_site", new_callable=AsyncMock):
            with patch.object(svc, "_cleanup_orphans", new_callable=AsyncMock, return_value=0):
                await svc.publish(db_session, str(log.id))

        await db_session.refresh(log)
        assert log.status == "completed"
        assert log.page_count == 1
        assert log.completed_at is not None

    @pytest.mark.asyncio
    async def test_publish_updates_log_on_failure(self, db_session):
        svc = PublishService()
        log = PlaybookPublishLogDB(status="running")
        db_session.add(log)
        await db_session.flush()

        await svc.publish(db_session, str(log.id))

        await db_session.refresh(log)
        assert log.status == "failed"
        assert "No public pages" in log.error_message
