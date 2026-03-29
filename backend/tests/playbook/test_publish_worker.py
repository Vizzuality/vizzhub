import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.worker.publish_playbook import publish_playbook_task


class TestPublishPlaybookTask:
    @pytest.mark.asyncio
    async def test_calls_publish_service(self):
        mock_db = AsyncMock()
        ctx = {"db": mock_db}

        with patch("app.worker.publish_playbook.PublishService") as MockSvc:
            instance = MockSvc.return_value
            instance.publish = AsyncMock()
            result = await publish_playbook_task(ctx, publish_log_id="test-id")
            instance.publish.assert_called_once_with(mock_db, "test-id")
            assert result == {"publish_log_id": "test-id"}
