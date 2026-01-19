from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import ConfigParameter, ConfigParameterUpdate


class ConfigService:
    """Business logic for configuration management."""

    @staticmethod
    async def get_parameter_value(db: AsyncSession, name: str) -> Decimal:
        """Get a single parameter value by name."""
        result = await db.execute(
            select(ConfigParameter.value).where(ConfigParameter.name == name)
        )
        value = result.scalar_one_or_none()
        if value is None:
            raise ValueError(f"Parameter {name} not found")
        return value

    @staticmethod
    async def get_parameters_by_category(
        db: AsyncSession, category: str
    ) -> dict[str, Decimal]:
        """Get all parameters in a category as dict {name: value}."""
        result = await db.execute(
            select(ConfigParameter).where(ConfigParameter.category == category)
        )
        params = result.scalars().all()
        return {p.name: p.value for p in params}

    @staticmethod
    async def get_all_parameters(
        db: AsyncSession,
    ) -> dict[str, list[ConfigParameter]]:
        """Get all parameters grouped by category."""
        result = await db.execute(
            select(ConfigParameter).order_by(
                ConfigParameter.category, ConfigParameter.name
            )
        )
        parameters = result.scalars().all()

        # Group by category
        grouped = {}
        for param in parameters:
            if param.category not in grouped:
                grouped[param.category] = []
            grouped[param.category].append(param)

        return grouped

    @staticmethod
    async def validate_weight_groups(db: AsyncSession) -> list[str]:
        """Validate that all weight groups sum to 1.0."""
        errors = []

        # Get all weight categories
        result = await db.execute(
            select(ConfigParameter).where(ConfigParameter.category.like("%Weights"))
        )
        parameters = result.scalars().all()

        # Group by category and sum
        grouped = {}
        for param in parameters:
            if param.category not in grouped:
                grouped[param.category] = Decimal("0")
            grouped[param.category] += param.value

        # Check each group sums to 1.0
        for category, total in grouped.items():
            if abs(total - Decimal("1.0")) > Decimal("0.001"):
                errors.append(f"{category} sum is {total}, expected 1.0")

        return errors

    @staticmethod
    async def update_parameters(
        db: AsyncSession, updates: list[ConfigParameterUpdate]
    ) -> None:
        """Update parameters and validate weight groups."""
        # Update values
        for update in updates:
            result = await db.execute(
                select(ConfigParameter).where(ConfigParameter.name == update.name)
            )
            param = result.scalar_one()
            param.value = update.value

        # Validate before commit
        errors = await ConfigService.validate_weight_groups(db)
        if errors:
            await db.rollback()
            raise ValueError(f"Weight validation failed: {errors}")

        await db.commit()
