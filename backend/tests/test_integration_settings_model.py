"""Tests for IntegrationSettingDB model."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.integration_setting import IntegrationSettingDB


class TestIntegrationSettingModel:
    """Tests for IntegrationSettingDB model."""

    def test_model_exists(self) -> None:
        """Test IntegrationSettingDB model has correct table name."""
        assert IntegrationSettingDB.__tablename__ == "integration_settings"

    @pytest.mark.asyncio
    async def test_create_setting(self, db_session: AsyncSession) -> None:
        """Test creating a setting and verifying all fields."""
        setting = IntegrationSettingDB(
            provider="slack",
            key="leadership_channel_id",
            value="C123456789",
        )
        db_session.add(setting)
        await db_session.commit()
        await db_session.refresh(setting)

        assert setting.id is not None
        assert setting.provider == "slack"
        assert setting.key == "leadership_channel_id"
        assert setting.value == "C123456789"
        assert setting.created_at is not None
        assert setting.updated_at is not None

    @pytest.mark.asyncio
    async def test_unique_constraint_provider_key(self, db_session: AsyncSession) -> None:
        """Test unique constraint on (provider, key) raises IntegrityError."""
        setting1 = IntegrationSettingDB(
            provider="slack",
            key="leadership_channel_id",
            value="C111111111",
        )
        setting2 = IntegrationSettingDB(
            provider="slack",
            key="leadership_channel_id",
            value="C222222222",
        )

        db_session.add(setting1)
        await db_session.commit()

        db_session.add(setting2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
