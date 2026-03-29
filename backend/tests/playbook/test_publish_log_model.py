import pytest

from app.modules.playbook.models.publish_log import PlaybookPublishLogDB


class TestPlaybookPublishLogModel:
    @pytest.mark.asyncio
    async def test_create_publish_log(self, db_session):
        log = PlaybookPublishLogDB(
            status="running",
            published_by_id=None,
        )
        db_session.add(log)
        await db_session.flush()
        assert log.id is not None
        assert log.status == "running"
        assert log.started_at is not None
        assert log.completed_at is None
        assert log.page_count is None
        assert log.error_message is None
