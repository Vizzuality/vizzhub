"""Integration tests for configuration loading from database."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig


class TestConfigLoadingIntegration:
    """Test that configuration is loaded correctly from database."""

    @pytest.mark.asyncio
    async def test_config_weights_loaded_from_db(
        self, db_session: AsyncSession, scoring_config: ScoringConfig
    ) -> None:
        """Verify scoring config weights are loaded from database."""
        # These should match the CSV seed values
        assert scoring_config.get_weight("global", "time") == pytest.approx(0.12)
        assert scoring_config.get_weight("global", "quality") == pytest.approx(0.205)
        assert scoring_config.get_weight("global", "flow") == pytest.approx(0.15)

    @pytest.mark.asyncio
    async def test_config_targets_loaded_from_db(
        self, db_session: AsyncSession, scoring_config: ScoringConfig
    ) -> None:
        """Verify scoring config targets are loaded from database."""
        assert scoring_config.get_target("spi") == pytest.approx(0.8)
        assert scoring_config.get_target("cpi") == pytest.approx(0.8)
        assert scoring_config.get_target("lead_time_days") == pytest.approx(10.0)
        assert scoring_config.get_target("mttr_hours") == pytest.approx(24.0)

    @pytest.mark.asyncio
    async def test_config_constants_loaded_from_db(
        self, db_session: AsyncSession, scoring_config: ScoringConfig
    ) -> None:
        """Verify scoring config constants are loaded from database."""
        assert scoring_config.get_constant("sev1_cap") == pytest.approx(60.0)
        assert scoring_config.get_constant("grace_days") == pytest.approx(3.0)

    @pytest.mark.asyncio
    async def test_config_weight_groups_sum_to_one(
        self, scoring_config: ScoringConfig
    ) -> None:
        """Verify all weight groups sum to 1.0."""
        validation = scoring_config.validate_weights()

        for group_name, is_valid in validation.items():
            assert is_valid, f"{group_name} weights do not sum to 1.0"
