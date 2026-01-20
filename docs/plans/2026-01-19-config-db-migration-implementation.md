# Configuration Database Migration - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate configuration from YAML to PostgreSQL with full CRUD UI

**Architecture:** Single `config_parameters` table with CSV seed, ConfigService for business logic, async calculators, Settings UI with tabs and edit mode

**Tech Stack:** SQLAlchemy async, Alembic, FastAPI, React Query, shadcn/ui tabs

---

## Task 1: Database Model and Migration

**Files:**
- Create: `backend/app/models/config.py` (new ConfigParameter model)
- Create: `backend/alembic/versions/XXXX_add_config_parameters.py`
- Test: `backend/tests/test_config_model.py`

**Step 1: Write failing test for ConfigParameter model**

```python
# backend/tests/test_config_model.py
import pytest
from decimal import Decimal
from app.models.config import ConfigParameter
from app.database import AsyncSessionLocal

@pytest.mark.asyncio
async def test_config_parameter_creation():
    """Test creating a config parameter."""
    async with AsyncSessionLocal() as db:
        param = ConfigParameter(
            category="Targets",
            name="DefDensity_t",
            value=Decimal("3.00"),
            unit="defects/100 tasks",
            notes="Target max defect density"
        )
        db.add(param)
        await db.commit()
        await db.refresh(param)

        assert param.id is not None
        assert param.category == "Targets"
        assert param.name == "DefDensity_t"
        assert param.value == Decimal("3.00")
        assert param.unit == "defects/100 tasks"

@pytest.mark.asyncio
async def test_config_parameter_unique_name():
    """Test that parameter name is unique."""
    async with AsyncSessionLocal() as db:
        param1 = ConfigParameter(
            category="Targets",
            name="test_param",
            value=Decimal("1.0")
        )
        param2 = ConfigParameter(
            category="Targets",
            name="test_param",
            value=Decimal("2.0")
        )

        db.add(param1)
        await db.commit()

        db.add(param2)
        with pytest.raises(Exception):  # IntegrityError
            await db.commit()
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_config_model.py -v`
Expected: FAIL with "cannot import name 'ConfigParameter'"

**Step 3: Create ConfigParameter model**

```python
# backend/app/models/config.py
from decimal import Decimal
from sqlalchemy import String, Text, Index
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class ConfigParameter(Base):
    """Configuration parameter with metadata."""
    __tablename__ = "config_parameters"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[Decimal] = mapped_column(NUMERIC(10, 4))
    unit: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index('idx_config_category', 'category'),
    )
```

**Step 4: Export model from __init__.py**

```python
# backend/app/models/__init__.py
# Add to existing exports:
from app.models.config import ConfigParameter

__all__ = [..., "ConfigParameter"]
```

**Step 5: Create Alembic migration**

Run: `cd backend && alembic revision --autogenerate -m "Add config_parameters table"`

Review generated migration, ensure it includes:
- Table creation
- Unique constraint on name
- Index on category

**Step 6: Run migration**

Run: `cd backend && alembic upgrade head`
Expected: Migration succeeds, table created

**Step 7: Run tests**

Run: `pytest backend/tests/test_config_model.py -v`
Expected: PASS (2 tests)

**Step 8: Commit**

```bash
git add backend/app/models/config.py backend/app/models/__init__.py backend/alembic/versions/* backend/tests/test_config_model.py
git commit -m "feat(db): add ConfigParameter model and migration

- Add ConfigParameter SQLAlchemy model with category, name, value, unit, notes
- Unique constraint on name field
- Index on category for efficient grouping queries
- Alembic migration to create config_parameters table
- Tests for model creation and unique constraint

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Seed Script

**Files:**
- Create: `backend/scripts/seed_config_parameters.py`
- Test: `backend/tests/test_seed_config.py`
- Data: `backend/seeds/config_parameters.csv` (already exists)

**Step 1: Write failing test for seed script**

```python
# backend/tests/test_seed_config.py
import pytest
from sqlalchemy import select, func
from app.models.config import ConfigParameter
from app.database import AsyncSessionLocal
from scripts.seed_config_parameters import seed_config_parameters

@pytest.mark.asyncio
async def test_seed_config_parameters_populates_table():
    """Test that seed script populates config_parameters table."""
    # Clear table first
    async with AsyncSessionLocal() as db:
        await db.execute("TRUNCATE TABLE config_parameters RESTART IDENTITY CASCADE")
        await db.commit()

    # Run seed
    await seed_config_parameters()

    # Verify data
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count()).select_from(ConfigParameter)
        )
        count = result.scalar()
        assert count == 65  # Total parameters from CSV

        # Verify specific parameter
        result = await db.execute(
            select(ConfigParameter).where(ConfigParameter.name == "DefDensity_t")
        )
        param = result.scalar_one()
        assert param.category == "Targets"
        assert param.value == 3.00
        assert param.unit == "defects/100 tasks"

@pytest.mark.asyncio
async def test_seed_config_parameters_is_idempotent():
    """Test that running seed twice doesn't duplicate data."""
    # Run seed twice
    await seed_config_parameters()
    await seed_config_parameters()

    # Verify only 65 records
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count()).select_from(ConfigParameter)
        )
        count = result.scalar()
        assert count == 65
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_seed_config.py -v`
Expected: FAIL with "cannot import 'seed_config_parameters'"

**Step 3: Create seed script**

```python
# backend/scripts/seed_config_parameters.py
import csv
import asyncio
from pathlib import Path
from decimal import Decimal
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.config import ConfigParameter


async def seed_config_parameters() -> None:
    """Seed config parameters from CSV if table is empty."""
    async with AsyncSessionLocal() as db:
        # Check if already seeded
        result = await db.execute(
            select(func.count()).select_from(ConfigParameter)
        )
        count = result.scalar()

        if count > 0:
            print(f"✓ Config parameters already seeded ({count} rows)")
            return

        # Read CSV
        csv_path = Path(__file__).parent.parent / "seeds" / "config_parameters.csv"
        parameters = []

        with open(csv_path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                parameters.append(ConfigParameter(
                    category=row['category'],
                    name=row['name'],
                    value=Decimal(row['value']),
                    unit=row['unit'] if row['unit'] else None,
                    notes=row['notes'] if row['notes'] else None
                ))

        db.add_all(parameters)
        await db.commit()
        print(f"✓ Seeded {len(parameters)} config parameters")


if __name__ == "__main__":
    asyncio.run(seed_config_parameters())
```

**Step 4: Run tests**

Run: `pytest backend/tests/test_seed_config.py -v`
Expected: PASS (2 tests)

**Step 5: Run seed script manually to verify**

Run: `cd backend && python scripts/seed_config_parameters.py`
Expected: "✓ Seeded 65 config parameters"

**Step 6: Commit**

```bash
git add backend/scripts/seed_config_parameters.py backend/tests/test_seed_config.py
git commit -m "feat(db): add config parameters seed script

- Seed script reads from seeds/config_parameters.csv
- Idempotent: only seeds if table is empty
- Loads all 65 parameters with category, name, value, unit, notes
- Tests verify seeding and idempotency

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: ConfigService

**Files:**
- Create: `backend/app/services/config_service.py`
- Test: `backend/tests/test_config_service.py`

**Step 1: Write failing tests for ConfigService**

```python
# backend/tests/test_config_service.py
import pytest
from decimal import Decimal
from sqlalchemy import select
from app.models.config import ConfigParameter
from app.database import AsyncSessionLocal
from app.services.config_service import ConfigService

@pytest.mark.asyncio
async def test_get_parameter_value():
    """Test getting a single parameter value by name."""
    async with AsyncSessionLocal() as db:
        value = await ConfigService.get_parameter_value(db, "DefDensity_t")
        assert value == Decimal("3.00")

@pytest.mark.asyncio
async def test_get_parameter_value_not_found():
    """Test getting non-existent parameter raises error."""
    async with AsyncSessionLocal() as db:
        with pytest.raises(ValueError, match="Parameter.*not found"):
            await ConfigService.get_parameter_value(db, "NonExistent")

@pytest.mark.asyncio
async def test_get_parameters_by_category():
    """Test getting all parameters in a category."""
    async with AsyncSessionLocal() as db:
        params = await ConfigService.get_parameters_by_category(db, "Time Weights")

        assert "W_time_spi" in params
        assert "W_time_milestones" in params
        assert params["W_time_spi"] == Decimal("0.60")
        assert params["W_time_milestones"] == Decimal("0.40")

@pytest.mark.asyncio
async def test_validate_weight_groups_all_valid():
    """Test weight validation passes for valid weights."""
    async with AsyncSessionLocal() as db:
        errors = await ConfigService.validate_weight_groups(db)
        assert len(errors) == 0

@pytest.mark.asyncio
async def test_validate_weight_groups_detects_invalid():
    """Test weight validation detects invalid sum."""
    async with AsyncSessionLocal() as db:
        # Temporarily break Quality Weights (change W_def to 0)
        await db.execute(
            "UPDATE config_parameters SET value = 0 WHERE name = 'W_def'"
        )
        await db.commit()

        errors = await ConfigService.validate_weight_groups(db)
        assert len(errors) > 0
        assert any("Quality Weights" in err for err in errors)

        # Restore
        await db.execute(
            "UPDATE config_parameters SET value = 0.05 WHERE name = 'W_def'"
        )
        await db.commit()

@pytest.mark.asyncio
async def test_update_parameters():
    """Test updating multiple parameters."""
    from app.models.config import ConfigParameterUpdate

    async with AsyncSessionLocal() as db:
        updates = [
            ConfigParameterUpdate(name="DefDensity_t", value=Decimal("2.50"))
        ]

        await ConfigService.update_parameters(db, updates)

        # Verify update
        value = await ConfigService.get_parameter_value(db, "DefDensity_t")
        assert value == Decimal("2.50")

        # Restore original
        updates = [
            ConfigParameterUpdate(name="DefDensity_t", value=Decimal("3.00"))
        ]
        await ConfigService.update_parameters(db, updates)

@pytest.mark.asyncio
async def test_update_parameters_rejects_invalid_weights():
    """Test update rejects changes that break weight validation."""
    from app.models.config import ConfigParameterUpdate

    async with AsyncSessionLocal() as db:
        # Try to set W_time_spi to 1.0 (breaks Time Weights sum)
        updates = [
            ConfigParameterUpdate(name="W_time_spi", value=Decimal("1.00"))
        ]

        with pytest.raises(ValueError, match="Weight validation failed"):
            await ConfigService.update_parameters(db, updates)
```

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_config_service.py -v`
Expected: FAIL with "cannot import 'ConfigService'"

**Step 3: Create ConfigParameterUpdate Pydantic model**

```python
# backend/app/models/config.py (add to end of file)
from pydantic import BaseModel, ConfigDict

class ConfigParameterResponse(BaseModel):
    id: int
    category: str
    name: str
    value: Decimal
    unit: str | None
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class ConfigParameterUpdate(BaseModel):
    name: str
    value: Decimal
```

**Step 4: Create ConfigService**

```python
# backend/app/services/config_service.py
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
```

**Step 5: Run tests**

Run: `pytest backend/tests/test_config_service.py -v`
Expected: PASS (6 tests)

**Step 6: Commit**

```bash
git add backend/app/services/config_service.py backend/app/models/config.py backend/tests/test_config_service.py
git commit -m "feat(service): add ConfigService with validation

- ConfigService for business logic (get, update, validate)
- get_parameter_value: fetch single value by name
- get_parameters_by_category: fetch all params in category as dict
- validate_weight_groups: ensure all weight categories sum to 1.0
- update_parameters: atomic update with validation
- ConfigParameterUpdate and ConfigParameterResponse Pydantic models
- Comprehensive tests for all methods

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: API Endpoints

**Files:**
- Modify: `backend/app/api/config.py`
- Test: `backend/tests/test_api_config.py`

**Step 1: Write failing tests for new endpoints**

```python
# backend/tests/test_api_config.py
import pytest
from httpx import AsyncClient
from decimal import Decimal

@pytest.mark.asyncio
async def test_get_config_parameters(client: AsyncClient, auth_headers: dict):
    """Test GET /api/config/parameters returns all grouped parameters."""
    response = await client.get("/api/config/parameters", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert "Targets" in data
    assert "Global Weights" in data
    assert "Quality Weights" in data

    # Verify specific parameter
    targets = data["Targets"]
    defect_param = next(p for p in targets if p["name"] == "DefDensity_t")
    assert defect_param["value"] == "3.0000"
    assert defect_param["unit"] == "defects/100 tasks"
    assert defect_param["category"] == "Targets"

@pytest.mark.asyncio
async def test_update_config_parameters(client: AsyncClient, auth_headers: dict):
    """Test PUT /api/config/parameters updates values."""
    updates = [
        {"name": "DefDensity_t", "value": "2.5000"}
    ]

    response = await client.put(
        "/api/config/parameters",
        headers=auth_headers,
        json=updates
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    # Verify update persisted
    response = await client.get("/api/config/parameters", headers=auth_headers)
    targets = response.json()["Targets"]
    defect_param = next(p for p in targets if p["name"] == "DefDensity_t")
    assert defect_param["value"] == "2.5000"

    # Restore original
    await client.put(
        "/api/config/parameters",
        headers=auth_headers,
        json=[{"name": "DefDensity_t", "value": "3.0000"}]
    )

@pytest.mark.asyncio
async def test_update_config_parameters_rejects_invalid_weights(
    client: AsyncClient, auth_headers: dict
):
    """Test PUT rejects updates that break weight validation."""
    updates = [
        {"name": "W_time_spi", "value": "1.0000"}  # Breaks Time Weights sum
    ]

    response = await client.put(
        "/api/config/parameters",
        headers=auth_headers,
        json=updates
    )

    assert response.status_code == 400
    assert "Weight validation failed" in response.json()["detail"]

@pytest.mark.asyncio
async def test_validate_config(client: AsyncClient, auth_headers: dict):
    """Test GET /api/config/validate returns validation status."""
    response = await client.get("/api/config/validate", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert "valid" in data
    assert "errors" in data
    assert data["valid"] is True
    assert len(data["errors"]) == 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_api_config.py::test_get_config_parameters -v`
Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Update API endpoints**

```python
# backend/app/api/config.py
# Add these imports at top:
from app.services.config_service import ConfigService
from app.models.config import ConfigParameterResponse, ConfigParameterUpdate

# Add new endpoints after existing ones:

@router.get("/parameters")
@limiter.limit("100/minute")
async def get_config_parameters(
    request: Request, current_user: CurrentUser, db: DBSession
) -> dict[str, list[ConfigParameterResponse]]:
    """Get all config parameters grouped by category. Requires authentication."""
    parameters = await ConfigService.get_all_parameters(db)

    # Convert to response models
    response = {}
    for category, params in parameters.items():
        response[category] = [
            ConfigParameterResponse.model_validate(p) for p in params
        ]

    return response


@router.put("/parameters")
@limiter.limit("10/minute")
async def update_config_parameters(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    updates: list[ConfigParameterUpdate],
) -> dict[str, str]:
    """Update multiple config parameters. Validates weight groups. Requires authentication."""
    try:
        await ConfigService.update_parameters(db, updates)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@router.get("/validate")
@limiter.limit("100/minute")
async def validate_config(
    request: Request, current_user: CurrentUser, db: DBSession
) -> dict[str, bool | list[str]]:
    """Validate that all weight groups sum to 1. Requires authentication."""
    errors = await ConfigService.validate_weight_groups(db)
    return {"valid": len(errors) == 0, "errors": errors}
```

**Step 4: Run tests**

Run: `pytest backend/tests/test_api_config.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/app/api/config.py backend/tests/test_api_config.py
git commit -m "feat(api): add config parameters CRUD endpoints

- GET /api/config/parameters: return all params grouped by category
- PUT /api/config/parameters: update multiple params with validation
- GET /api/config/validate: check weight group validation status
- All endpoints require authentication
- Rate limiting: 100/min for GET, 10/min for PUT
- Tests verify CRUD operations and validation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Refactor Quality Calculator

**Files:**
- Modify: `backend/app/services/calculators/quality.py`
- Test: `backend/tests/test_calculators.py` (update existing tests)

**Step 1: Read existing calculator to understand structure**

Run: `cat backend/app/services/calculators/quality.py`

**Step 2: Write test comparing old vs new implementation**

```python
# backend/tests/test_calculator_refactor.py
import pytest
from decimal import Decimal
from app.services.calculators.quality import QualityCalculator
from app.database import AsyncSessionLocal

@pytest.mark.asyncio
async def test_quality_calculator_async():
    """Test refactored async quality calculator."""
    indicators = {
        "defect_density": Decimal("1.0"),
        "escaped_rate": Decimal("1.0"),
        "mttr": Decimal("1.0"),
        "story_review": Decimal("1.0"),
        "governance": Decimal("1.0"),
        "pr_review": Decimal("1.0"),
    }

    async with AsyncSessionLocal() as db:
        score = await QualityCalculator.calculate(db, indicators)

        # Should be perfect score (100) since all indicators are 1.0
        assert score == 100.0

@pytest.mark.asyncio
async def test_quality_calculator_uses_db_weights():
    """Test calculator uses weights from database."""
    indicators = {
        "defect_density": Decimal("1.0"),
        "escaped_rate": Decimal("0.0"),
        "mttr": Decimal("0.0"),
        "story_review": Decimal("0.0"),
        "governance": Decimal("0.0"),
        "pr_review": Decimal("0.0"),
    }

    async with AsyncSessionLocal() as db:
        score = await QualityCalculator.calculate(db, indicators)

        # Should be W_def * 100 = 0.05 * 100 = 5.0
        assert abs(score - 5.0) < 0.01
```

**Step 3: Run test to verify it fails**

Run: `pytest backend/tests/test_calculator_refactor.py -v`
Expected: FAIL (calculator still expects ScoringConfig)

**Step 4: Refactor QualityCalculator to async**

```python
# backend/app/services/calculators/quality.py
# Replace entire file content:

from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.config_service import ConfigService


class QualityCalculator:
    """Calculate P_quality score using DB config."""

    @staticmethod
    async def calculate(
        db: AsyncSession,
        indicators: dict[str, Decimal],
        has_sev1: bool = False,
    ) -> float:
        """
        Calculate quality score from indicators.

        Args:
            db: Database session
            indicators: Dict with keys: defect_density, escaped_rate, mttr,
                       story_review, governance, pr_review
            has_sev1: Whether project had Sev1 incident (caps score at 60)

        Returns:
            Quality score 0-100
        """
        # Load weights from database
        weights = await ConfigService.get_parameters_by_category(db, "Quality Weights")

        # Calculate weighted score
        score = (
            weights["W_def"] * indicators.get("defect_density", Decimal("0.5"))
            + weights["W_esc"] * indicators.get("escaped_rate", Decimal("0.5"))
            + weights["W_mttr"] * indicators.get("mttr", Decimal("0.5"))
            + weights["W_q_storyrev"] * indicators.get("story_review", Decimal("0.5"))
            + weights["W_qual_gov"] * indicators.get("governance", Decimal("0.5"))
            + weights["W_q_pr"] * indicators.get("pr_review", Decimal("0.5"))
        )

        score_100 = float(score * 100)

        # Apply Sev1 cap
        if has_sev1:
            sev1_cap = await ConfigService.get_parameter_value(db, "Sev1_cap")
            score_100 = min(score_100, float(sev1_cap))

        return score_100
```

**Step 5: Run new tests**

Run: `pytest backend/tests/test_calculator_refactor.py -v`
Expected: PASS (2 tests)

**Step 6: Update existing calculator tests**

Update `backend/tests/test_calculators.py` to pass `db` session to `QualityCalculator.calculate()` and make tests async.

**Step 7: Run all calculator tests**

Run: `pytest backend/tests/test_calculators.py::TestQualityCalculator -v`
Expected: PASS

**Step 8: Commit**

```bash
git add backend/app/services/calculators/quality.py backend/tests/test_calculator_refactor.py backend/tests/test_calculators.py
git commit -m "refactor(calc): migrate QualityCalculator to async DB config

- Change from sync YAML config to async database config
- Use ConfigService to load Quality Weights from DB
- Sev1_cap now loaded from DB constants
- All methods now async
- Tests updated to use async/await and DB session
- Maintains exact same calculation logic

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Refactor Remaining Calculators

**Files:**
- Modify: `backend/app/services/calculators/*.py` (7 more calculators)
- Test: `backend/tests/test_calculators.py`

**For each calculator (Time, Cost, Value, Satisfaction, Flow, Engineering, Risk):**

**Step 1: Update calculator to async with DB config**

Follow same pattern as QualityCalculator:
- Make `calculate()` static async method
- Accept `db: AsyncSession` as first parameter
- Load weights using `ConfigService.get_parameters_by_category(db, "<Category> Weights")`
- Load targets/constants using `ConfigService.get_parameter_value(db, "<param_name>")`

**Step 2: Update tests to async**

**Step 3: Run tests for that calculator**

Run: `pytest backend/tests/test_calculators.py::Test<Calculator>Calculator -v`
Expected: PASS

**Step 4: Commit each calculator separately**

```bash
git add backend/app/services/calculators/<calculator>.py backend/tests/test_calculators.py
git commit -m "refactor(calc): migrate <Calculator>Calculator to async DB config"
```

**Note:** Do this for:
- TimeCalculator (uses W_time_spi, W_time_milestones, GraceDays)
- CostCalculator (uses W_cost_cpi, W_cost_var)
- ValueCalculator (uses W_value_roi, W_value_okr, ROI_t)
- SatisfactionCalculator (uses W_sat_client, W_sat_pm, W_cs_*)
- FlowCalculator (uses W_flow_lt, W_flow_fe, W_flow_cr, LT_t, FE_t)
- EngineeringCalculator (uses W_eng_test, W_eng_pr, W_eng_arch, W_test_*)
- RiskCalculator (uses W_risk_pr, W_risk_vuln, HighVuln_t)

---

## Task 7: Refactor FinalScoreCalculator

**Files:**
- Modify: `backend/app/services/calculators/final_score.py`
- Test: `backend/tests/test_calculators.py::TestFinalScoreCalculator`

**Step 1: Update FinalScoreCalculator**

```python
# backend/app/services/calculators/final_score.py
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.config_service import ConfigService
from app.services.calculators.quality import QualityCalculator
from app.services.calculators.time import TimeCalculator
# ... import all other calculators


class FinalScoreCalculator:
    """Calculate final weighted score from all dimensions."""

    @staticmethod
    async def calculate(
        db: AsyncSession,
        dimension_scores: dict[str, float],
    ) -> float:
        """
        Calculate final weighted score.

        Args:
            db: Database session
            dimension_scores: Dict with keys: quality, time, cost, value,
                            satisfaction, flow, engineering, risk

        Returns:
            Final score 0-100
        """
        # Load global weights from database
        weights = await ConfigService.get_parameters_by_category(db, "Global Weights")

        # Calculate weighted score
        final_score = (
            weights["W_quality"] * Decimal(dimension_scores.get("quality", 0))
            + weights["W_time"] * Decimal(dimension_scores.get("time", 0))
            + weights["W_cost"] * Decimal(dimension_scores.get("cost", 0))
            + weights["W_value"] * Decimal(dimension_scores.get("value", 0))
            + weights["W_satisfaction"] * Decimal(dimension_scores.get("satisfaction", 0))
            + weights["W_flow"] * Decimal(dimension_scores.get("flow", 0))
            + weights["W_engineering"] * Decimal(dimension_scores.get("engineering", 0))
            + weights["W_risk"] * Decimal(dimension_scores.get("risk", 0))
        )

        return float(final_score)
```

**Step 2: Update tests to async**

**Step 3: Run tests**

Run: `pytest backend/tests/test_calculators.py::TestFinalScoreCalculator -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/services/calculators/final_score.py backend/tests/test_calculators.py
git commit -m "refactor(calc): migrate FinalScoreCalculator to async DB config

- Load Global Weights from database
- All dimension calculators now async
- Maintains exact same weighted sum logic

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Update Metrics API to Use Async Calculators

**Files:**
- Modify: `backend/app/api/metrics.py`
- Modify: `backend/app/api/deps.py` (remove ScoringConfigDep)
- Test: `backend/tests/test_api_metrics.py`

**Step 1: Remove ScoringConfig dependency**

```python
# backend/app/api/deps.py
# Delete this entire section:
# from app.config import get_scoring_config, ScoringConfig
# ScoringConfigDep = Annotated[ScoringConfig, Depends(get_scoring_config)]
```

**Step 2: Update scores endpoint**

```python
# backend/app/api/metrics.py
# Update get_scores endpoint:

@router.get("/{project_id}/scores", response_model=ProjectScores)
@limiter.limit("100/minute")
async def get_scores(
    request: Request,
    project_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> ProjectScores:
    """Get calculated scores for a project. Requires authentication."""
    # Get indicators
    indicators = await get_indicators_for_project(db, project_id)

    # Calculate dimension scores using async calculators
    quality_score = await QualityCalculator.calculate(
        db, indicators.quality, has_sev1=indicators.has_sev1
    )
    time_score = await TimeCalculator.calculate(db, indicators.time)
    cost_score = await CostCalculator.calculate(db, indicators.cost)
    value_score = await ValueCalculator.calculate(db, indicators.value)
    satisfaction_score = await SatisfactionCalculator.calculate(db, indicators.satisfaction)
    flow_score = await FlowCalculator.calculate(db, indicators.flow)
    engineering_score = await EngineeringCalculator.calculate(db, indicators.engineering)
    risk_score = await RiskCalculator.calculate(db, indicators.risk)

    dimension_scores = {
        "quality": quality_score,
        "time": time_score,
        "cost": cost_score,
        "value": value_score,
        "satisfaction": satisfaction_score,
        "flow": flow_score,
        "engineering": engineering_score,
        "risk": risk_score,
    }

    # Calculate final score
    final_score = await FinalScoreCalculator.calculate(db, dimension_scores)

    return ProjectScores(
        score=final_score,
        dimensions=DimensionScores(**{
            f"p_{k}": v for k, v in dimension_scores.items()
        })
    )
```

**Step 3: Run tests**

Run: `pytest backend/tests/test_api_metrics.py::test_get_scores -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/app/api/metrics.py backend/app/api/deps.py backend/tests/test_api_metrics.py
git commit -m "refactor(api): update metrics endpoints to use async calculators

- Remove ScoringConfigDep dependency
- Pass db session to all calculator calls
- All calculator invocations now async
- Tests verify scores still calculated correctly

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Delete Legacy YAML Config

**Files:**
- Delete: `backend/app/config.py::ScoringConfig` class
- Delete: `backend/scoring_config.yaml` (keep as reference in legacy/)
- Test: Run all backend tests

**Step 1: Move YAML to legacy/**

```bash
mkdir -p backend/legacy
mv backend/scoring_config.yaml backend/legacy/scoring_config.yaml
```

**Step 2: Delete ScoringConfig from config.py**

```python
# backend/app/config.py
# Delete entire ScoringConfig class and get_scoring_config function
# Keep only Settings class
```

**Step 3: Run all backend tests**

Run: `pytest backend/ -v`
Expected: ALL PASS (no references to ScoringConfig remain)

**Step 4: Commit**

```bash
git add backend/app/config.py backend/legacy/scoring_config.yaml backend/scoring_config.yaml
git commit -m "refactor(config): remove YAML-based ScoringConfig

- Delete ScoringConfig class (fully migrated to DB)
- Move scoring_config.yaml to legacy/ for reference
- All config now loaded from database via ConfigService
- All tests passing with DB-backed configuration

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 10: Frontend Hooks

**Files:**
- Create: `frontend/src/hooks/useConfig.ts`
- Test: `frontend/src/hooks/__tests__/useConfig.test.ts`

**Step 1: Write failing test for hooks**

```typescript
// frontend/src/hooks/__tests__/useConfig.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useConfigParameters, useUpdateConfigParameters } from '../useConfig';
import api from '../../services/api';

jest.mock('../../services/api');

describe('useConfig hooks', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  it('useConfigParameters fetches grouped parameters', async () => {
    const mockData = {
      'Targets': [
        { id: 1, category: 'Targets', name: 'DefDensity_t', value: '3.0000', unit: 'defects/100 tasks', notes: '' }
      ]
    };

    (api.get as jest.Mock).mockResolvedValue({ data: mockData });

    const { result } = renderHook(() => useConfigParameters(), {
      wrapper: ({ children }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
    expect(api.get).toHaveBeenCalledWith('/api/config/parameters');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- useConfig.test.ts`
Expected: FAIL (hook doesn't exist)

**Step 3: Create hooks**

```typescript
// frontend/src/hooks/useConfig.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import type { ConfigParameter, ConfigParameterUpdate } from '../types/config';

export function useConfigParameters() {
  return useQuery<Record<string, ConfigParameter[]>>({
    queryKey: ['config', 'parameters'],
    queryFn: async () => {
      const response = await api.get('/api/config/parameters');
      return response.data;
    },
  });
}

export function useConfigValidation() {
  return useQuery<{ valid: boolean; errors: string[] }>({
    queryKey: ['config', 'validation'],
    queryFn: async () => {
      const response = await api.get('/api/config/validate');
      return response.data;
    },
  });
}

export function useUpdateConfigParameters() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (updates: ConfigParameterUpdate[]) => {
      const response = await api.put('/api/config/parameters', updates);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
      queryClient.invalidateQueries({ queryKey: ['scores'] });
    },
  });
}
```

**Step 4: Create TypeScript types**

```typescript
// frontend/src/types/config.ts
export interface ConfigParameter {
  id: number;
  category: string;
  name: string;
  value: string;
  unit: string | null;
  notes: string | null;
}

export interface ConfigParameterUpdate {
  name: string;
  value: string;
}
```

**Step 5: Run tests**

Run: `cd frontend && npm test -- useConfig.test.ts`
Expected: PASS

**Step 6: Commit**

```bash
git add frontend/src/hooks/useConfig.ts frontend/src/types/config.ts frontend/src/hooks/__tests__/useConfig.test.ts
git commit -m "feat(frontend): add config parameters hooks

- useConfigParameters: fetch all params grouped by category
- useConfigValidation: check weight validation status
- useUpdateConfigParameters: update params with auto-invalidation
- TypeScript types for ConfigParameter and Update
- Tests for hooks

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 11: Settings UI - Tab Structure

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`
- Test: `frontend/src/pages/__tests__/Settings.test.tsx`

**Step 1: Install shadcn/ui tabs component**

Run: `cd frontend && npx shadcn-ui@latest add tabs`

**Step 2: Write failing test**

```typescript
// frontend/src/pages/__tests__/Settings.test.tsx
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Settings from '../Settings';

describe('Settings', () => {
  it('renders tabs for Configuration and Validation', () => {
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <Settings />
      </QueryClientProvider>
    );

    expect(screen.getByText('Configuration')).toBeInTheDocument();
    expect(screen.getByText('Validation')).toBeInTheDocument();
  });
});
```

**Step 3: Run test to verify it fails**

Run: `cd frontend && npm test -- Settings.test.tsx`
Expected: FAIL (tabs not rendered)

**Step 4: Update Settings component with tabs**

```tsx
// frontend/src/pages/Settings.tsx
import { useState } from 'react';
import { Pencil, Save, X } from 'lucide-react';
import { useConfigParameters, useConfigValidation } from '../hooks/useConfig';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent } from '@/components/ui/card';

export default function Settings(): JSX.Element {
  const [isEditing, setIsEditing] = useState(false);
  const { data: parameters, isLoading } = useConfigParameters();
  const { data: validation } = useConfigValidation();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        {!isEditing ? (
          <Button onClick={() => setIsEditing(true)}>
            <Pencil className="w-5 h-5 mr-2" />
            Edit Configuration
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button
              variant="ghost"
              onClick={() => setIsEditing(false)}
              className="border border-input"
            >
              <X className="w-5 h-5 mr-2" />
              Cancel
            </Button>
            <Button onClick={() => {}}>
              <Save className="w-5 h-5 mr-2" />
              Save Changes
            </Button>
          </div>
        )}
      </div>

      <Tabs defaultValue="config">
        <TabsList>
          <TabsTrigger value="config">Configuration</TabsTrigger>
          <TabsTrigger value="validation">Validation</TabsTrigger>
        </TabsList>

        <TabsContent value="config" className="space-y-6">
          <Card>
            <CardContent className="pt-6">
              <p className="text-muted-foreground">Configuration content coming soon...</p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="validation">
          <Card>
            <CardContent className="pt-6">
              <p className="text-muted-foreground">Validation content coming soon...</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

**Step 5: Run tests**

Run: `cd frontend && npm test -- Settings.test.tsx`
Expected: PASS

**Step 6: Commit**

```bash
git add frontend/src/pages/Settings.tsx frontend/src/pages/__tests__/Settings.test.tsx
git commit -m "feat(ui): add Settings tabs structure

- Tabs for Configuration and Validation
- Edit mode toggle (Edit/Cancel/Save buttons)
- Placeholder content for both tabs
- Tests verify tabs render

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 12: Settings UI - Parameter Display Components

**Files:**
- Create: `frontend/src/components/Settings/ParameterRow.tsx`
- Create: `frontend/src/components/Settings/ConfigSection.tsx`
- Create: `frontend/src/components/Settings/WeightsSection.tsx`
- Test: Component tests

**Step 1: Create ParameterRow component**

```tsx
// frontend/src/components/Settings/ParameterRow.tsx
import { Input } from '@/components/ui/input';
import type { ConfigParameter } from '../../types/config';

interface ParameterRowProps {
  parameter: ConfigParameter;
  isEditing: boolean;
  value: string;
  onValueChange: (name: string, value: string) => void;
}

export default function ParameterRow({
  parameter,
  isEditing,
  value,
  onValueChange,
}: ParameterRowProps): JSX.Element {
  return (
    <div className="flex items-center justify-between py-2 border-b last:border-0">
      <div className="flex-1">
        <div className="font-medium">{parameter.name}</div>
        {parameter.notes && (
          <div className="text-sm text-muted-foreground">{parameter.notes}</div>
        )}
      </div>
      <div className="flex items-center gap-2">
        {isEditing ? (
          <Input
            type="number"
            step="0.01"
            value={value}
            onChange={(e) => onValueChange(parameter.name, e.target.value)}
            className="w-24"
          />
        ) : (
          <span className="font-medium">{parameter.value}</span>
        )}
        {parameter.unit && (
          <span className="text-sm text-muted-foreground min-w-[120px]">
            {parameter.unit}
          </span>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Create ConfigSection component**

```tsx
// frontend/src/components/Settings/ConfigSection.tsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import ParameterRow from './ParameterRow';
import type { ConfigParameter } from '../../types/config';

interface ConfigSectionProps {
  title: string;
  parameters: ConfigParameter[];
  isEditing: boolean;
  editedValues: Map<string, string>;
  onValueChange: (name: string, value: string) => void;
}

export default function ConfigSection({
  title,
  parameters,
  isEditing,
  editedValues,
  onValueChange,
}: ConfigSectionProps): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {parameters.map((param) => (
            <ParameterRow
              key={param.id}
              parameter={param}
              isEditing={isEditing}
              value={editedValues.get(param.name) || param.value}
              onValueChange={onValueChange}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
```

**Step 3: Create WeightsSection with sum indicator**

```tsx
// frontend/src/components/Settings/WeightsSection.tsx
import { CheckCircle, XCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import ParameterRow from './ParameterRow';
import type { ConfigParameter } from '../../types/config';

interface WeightsSectionProps {
  title: string;
  parameters: ConfigParameter[];
  isEditing: boolean;
  editedValues: Map<string, string>;
  onValueChange: (name: string, value: string) => void;
}

export default function WeightsSection({
  title,
  parameters,
  isEditing,
  editedValues,
  onValueChange,
}: WeightsSectionProps): JSX.Element {
  // Calculate sum using edited or original values
  const sum = parameters.reduce((acc, p) => {
    const value = editedValues.get(p.name) || p.value;
    return acc + parseFloat(value);
  }, 0);

  const isValid = Math.abs(sum - 1.0) < 0.001;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{title}</CardTitle>
          {isEditing && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                Sum: {sum.toFixed(4)}
              </span>
              {isValid ? (
                <CheckCircle className="w-5 h-5 text-primary" />
              ) : (
                <XCircle className="w-5 h-5 text-destructive" />
              )}
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {parameters.map((param) => (
            <ParameterRow
              key={param.id}
              parameter={param}
              isEditing={isEditing}
              value={editedValues.get(param.name) || param.value}
              onValueChange={onValueChange}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
```

**Step 4: Commit**

```bash
git add frontend/src/components/Settings/
git commit -m "feat(ui): add Settings parameter display components

- ParameterRow: display single param with view/edit modes
- ConfigSection: group params by category
- WeightsSection: ConfigSection with sum validation indicator
- Real-time sum calculation and validation feedback

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 13: Settings UI - Complete Integration

**Files:**
- Modify: `frontend/src/pages/Settings.tsx` (integrate all sections)
- Create: `frontend/src/hooks/useConfigEditor.ts` (state management)

**Step 1: Create useConfigEditor hook**

```typescript
// frontend/src/hooks/useConfigEditor.ts
import { useState } from 'react';
import type { ConfigParameter } from '../types/config';

export function useConfigEditor(original: Record<string, ConfigParameter[]> | undefined) {
  const [editedValues, setEditedValues] = useState<Map<string, string>>(new Map());
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  const updateValue = (name: string, value: string) => {
    const newEdited = new Map(editedValues);
    newEdited.set(name, value);
    setEditedValues(newEdited);

    // Validate weights in real-time
    if (original) {
      const errors = validateWeights(original, newEdited);
      setValidationErrors(errors);
    }
  };

  const validateWeights = (
    original: Record<string, ConfigParameter[]>,
    changes: Map<string, string>
  ): string[] => {
    const errors: string[] = [];
    const weightCategories = Object.keys(original).filter(cat => cat.includes('Weights'));

    weightCategories.forEach((category) => {
      const params = original[category] || [];
      let sum = 0;

      params.forEach((param) => {
        const value = changes.has(param.name) ? changes.get(param.name)! : param.value;
        sum += parseFloat(value);
      });

      if (Math.abs(sum - 1.0) > 0.001) {
        errors.push(`${category} sum is ${sum.toFixed(4)}, expected 1.0`);
      }
    });

    return errors;
  };

  const getUpdates = () => {
    const updates = [];
    for (const [name, value] of editedValues.entries()) {
      updates.push({ name, value });
    }
    return updates;
  };

  const reset = () => {
    setEditedValues(new Map());
    setValidationErrors([]);
  };

  const hasChanges = editedValues.size > 0;
  const canSave = hasChanges && validationErrors.length === 0;

  return {
    editedValues,
    updateValue,
    validationErrors,
    hasChanges,
    canSave,
    getUpdates,
    reset,
  };
}
```

**Step 2: Complete Settings component**

```tsx
// frontend/src/pages/Settings.tsx
import { useState } from 'react';
import { Pencil, Save, X, CheckCircle, XCircle } from 'lucide-react';
import { useConfigParameters, useConfigValidation, useUpdateConfigParameters } from '../hooks/useConfig';
import { useConfigEditor } from '../hooks/useConfigEditor';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import ConfigSection from '../components/Settings/ConfigSection';
import WeightsSection from '../components/Settings/WeightsSection';

export default function Settings(): JSX.Element {
  const [isEditing, setIsEditing] = useState(false);
  const { data: parameters, isLoading } = useConfigParameters();
  const { data: validation } = useConfigValidation();
  const updateMutation = useUpdateConfigParameters();

  const {
    editedValues,
    updateValue,
    validationErrors,
    hasChanges,
    canSave,
    getUpdates,
    reset,
  } = useConfigEditor(parameters);

  const handleSave = async () => {
    const updates = getUpdates();
    await updateMutation.mutateAsync(updates);
    setIsEditing(false);
    reset();
  };

  const handleCancel = () => {
    setIsEditing(false);
    reset();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight">Settings</h1>
        {!isEditing ? (
          <Button onClick={() => setIsEditing(true)}>
            <Pencil className="w-5 h-5 mr-2" />
            Edit Configuration
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button variant="ghost" onClick={handleCancel} className="border border-input">
              <X className="w-5 h-5 mr-2" />
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={!canSave}>
              <Save className="w-5 h-5 mr-2" />
              Save Changes
            </Button>
          </div>
        )}
      </div>

      {isEditing && validationErrors.length > 0 && (
        <Card className="bg-destructive/10 border-destructive">
          <CardContent className="pt-6">
            <p className="font-medium text-destructive mb-2">Validation Errors:</p>
            <ul className="list-disc list-inside text-sm text-destructive">
              {validationErrors.map((error, i) => (
                <li key={i}>{error}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="config">
        <TabsList>
          <TabsTrigger value="config">Configuration</TabsTrigger>
          <TabsTrigger value="validation">Validation</TabsTrigger>
        </TabsList>

        <TabsContent value="config" className="space-y-6">
          {parameters && (
            <>
              <ConfigSection
                title="Targets"
                parameters={parameters['Targets'] || []}
                isEditing={isEditing}
                editedValues={editedValues}
                onValueChange={updateValue}
              />

              <ConfigSection
                title="Gates & Constants"
                parameters={parameters['Gates & Constants'] || []}
                isEditing={isEditing}
                editedValues={editedValues}
                onValueChange={updateValue}
              />

              <WeightsSection
                title="Global Weights"
                parameters={parameters['Global Weights'] || []}
                isEditing={isEditing}
                editedValues={editedValues}
                onValueChange={updateValue}
              />

              <WeightsSection
                title="Quality Weights"
                parameters={parameters['Quality Weights'] || []}
                isEditing={isEditing}
                editedValues={editedValues}
                onValueChange={updateValue}
              />

              <WeightsSection
                title="Time Weights"
                parameters={parameters['Time Weights'] || []}
                isEditing={isEditing}
                editedValues={editedValues}
                onValueChange={updateValue}
              />

              <WeightsSection
                title="Cost Weights"
                parameters={parameters['Cost Weights'] || []}
                isEditing={isEditing}
                editedValues={editedValues}
                onValueChange={updateValue}
              />

              <WeightsSection
                title="Value Weights"
                parameters={parameters['Value Weights'] || []}
                isEditing={isEditing}
                editedValues={editedValues}
                onValueChange={updateValue}
              />

              <WeightsSection
                title="Satisfaction Weights"
                parameters={parameters['Satisfaction Weights'] || []}
                isEditing={isEditing}
                editedValues={editedValues}
                onValueChange={updateValue}
              />

              <WeightsSection
                title="Efficiency Weights"
                parameters={parameters['Efficiency Weights'] || []}
                isEditing={isEditing}
                editedValues={editedValues}
                onValueChange={updateValue}
              />

              <WeightsSection
                title="Engineering Weights"
                parameters={parameters['Engineering Weights'] || []}
                isEditing={isEditing}
                editedValues={editedValues}
                onValueChange={updateValue}
              />

              <WeightsSection
                title="Risk Weights"
                parameters={parameters['Risk Weights'] || []}
                isEditing={isEditing}
                editedValues={editedValues}
                onValueChange={updateValue}
              />

              <WeightsSection
                title="Test Maturity Weights"
                parameters={parameters['Test Maturity Weights'] || []}
                isEditing={isEditing}
                editedValues={editedValues}
                onValueChange={updateValue}
              />
            </>
          )}
        </TabsContent>

        <TabsContent value="validation">
          <Card>
            <CardHeader>
              <CardTitle>Weight Validation</CardTitle>
            </CardHeader>
            <CardContent>
              {validation && (
                <div className="flex items-center gap-2 mb-4">
                  {validation.valid ? (
                    <>
                      <CheckCircle className="w-5 h-5 text-primary" />
                      <span className="text-primary">All weight groups are valid</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-5 h-5 text-destructive" />
                      <span className="text-destructive">Some weight groups are invalid</span>
                    </>
                  )}
                </div>
              )}
              {validation?.errors && validation.errors.length > 0 && (
                <ul className="list-disc list-inside text-sm text-destructive">
                  {validation.errors.map((error, i) => (
                    <li key={i}>{error}</li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

**Step 3: Run frontend tests**

Run: `cd frontend && npm test`
Expected: PASS

**Step 4: Run frontend dev server and manually test**

Run: `cd frontend && npm run dev`
Test: Navigate to Settings, toggle edit mode, change values, verify validation, save

**Step 5: Commit**

```bash
git add frontend/src/pages/Settings.tsx frontend/src/hooks/useConfigEditor.ts
git commit -m "feat(ui): complete Settings page with editing

- useConfigEditor hook for state management and validation
- Real-time weight validation with error display
- Edit mode with Cancel/Save buttons
- All 12 parameter sections displayed
- Validation tab shows current validation status
- Save calls API and invalidates queries

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 14: Integration Testing

**Files:**
- Create: `backend/tests/test_integration_config.py`
- Test: End-to-end flow

**Step 1: Write integration test**

```python
# backend/tests/test_integration_config.py
import pytest
from httpx import AsyncClient
from app.database import AsyncSessionLocal
from app.services.calculators.quality import QualityCalculator
from decimal import Decimal

@pytest.mark.asyncio
async def test_config_update_affects_calculator(client: AsyncClient, auth_headers: dict):
    """Test that updating config affects calculator results."""
    # Get current Quality score
    indicators = {
        "defect_density": Decimal("1.0"),
        "escaped_rate": Decimal("0.0"),
        "mttr": Decimal("0.0"),
        "story_review": Decimal("0.0"),
        "governance": Decimal("0.0"),
        "pr_review": Decimal("0.0"),
    }

    async with AsyncSessionLocal() as db:
        score_before = await QualityCalculator.calculate(db, indicators)

    # Score should be W_def * 100 = 0.05 * 100 = 5.0
    assert abs(score_before - 5.0) < 0.01

    # Update W_def to 0.10
    updates = [{"name": "W_def", "value": "0.1000"}]
    response = await client.put(
        "/api/config/parameters",
        headers=auth_headers,
        json=updates
    )
    assert response.status_code == 200

    # Get new score
    async with AsyncSessionLocal() as db:
        score_after = await QualityCalculator.calculate(db, indicators)

    # Score should now be 0.10 * 100 = 10.0
    assert abs(score_after - 10.0) < 0.01

    # Restore original
    await client.put(
        "/api/config/parameters",
        headers=auth_headers,
        json=[{"name": "W_def", "value": "0.0500"}]
    )

@pytest.mark.asyncio
async def test_full_config_workflow(client: AsyncClient, auth_headers: dict):
    """Test full workflow: seed → get → update → validate."""
    # Get all parameters
    response = await client.get("/api/config/parameters", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    # Verify seeded data
    assert "Targets" in data
    assert "Global Weights" in data
    assert len(data["Targets"]) == 15

    # Validate (should be valid)
    response = await client.get("/api/config/validate", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["valid"] is True

    # Update a target
    response = await client.put(
        "/api/config/parameters",
        headers=auth_headers,
        json=[{"name": "DefDensity_t", "value": "4.0000"}]
    )
    assert response.status_code == 200

    # Verify update
    response = await client.get("/api/config/parameters", headers=auth_headers)
    targets = response.json()["Targets"]
    defect = next(p for p in targets if p["name"] == "DefDensity_t")
    assert defect["value"] == "4.0000"

    # Restore
    await client.put(
        "/api/config/parameters",
        headers=auth_headers,
        json=[{"name": "DefDensity_t", "value": "3.0000"}]
    )
```

**Step 2: Run integration tests**

Run: `pytest backend/tests/test_integration_config.py -v`
Expected: PASS

**Step 3: Run ALL tests (backend + frontend)**

Backend: `pytest backend/ -v`
Frontend: `cd frontend && npm test`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add backend/tests/test_integration_config.py
git commit -m "test: add integration tests for config migration

- Test config update affects calculator results
- Test full workflow: seed → get → update → validate
- Verify end-to-end functionality

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 15: Documentation

**Files:**
- Create: `docs/CONFIG_MIGRATION.md`
- Update: `README.md` (if needed)

**Step 1: Create migration documentation**

```markdown
# docs/CONFIG_MIGRATION.md

# Configuration Database Migration

## Overview

Configuration parameters have been migrated from YAML (`scoring_config.yaml`) to PostgreSQL database.

## What Changed

### Before (YAML)
- Configuration in `backend/scoring_config.yaml`
- Hardcoded values, no UI editing
- Required code changes to update config

### After (Database)
- Configuration in `config_parameters` table
- Editable via Settings UI
- Changes take effect immediately (scores calculated on-the-fly)

## Database Structure

```sql
CREATE TABLE config_parameters (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100),
    name VARCHAR(100) UNIQUE,
    value DECIMAL(10, 4),
    unit VARCHAR(50),
    notes TEXT
);
```

**65 parameters total** across 12 categories:
- Targets (15)
- Quality Weights (8)
- Time Weights (2)
- Cost Weights (2)
- Value Weights (2)
- Satisfaction Weights (10)
- Efficiency Weights (3)
- Engineering Weights (4)
- Risk Weights (3)
- Global Weights (8)
- Gates & Constants (3)
- Test Maturity Weights (5)

## Initial Data

On first deployment, run seed script:

```bash
cd backend
python scripts/seed_config_parameters.py
```

This populates the table from `backend/seeds/config_parameters.csv`.

## Editing Configuration

### Via UI

1. Navigate to Settings page
2. Click "Edit Configuration"
3. Modify values (validation happens in real-time)
4. Click "Save Changes"

Weight groups must sum to 1.0 (tolerance: ±0.001).

### Via API

```bash
# Get all parameters
curl http://localhost:8000/api/config/parameters

# Update parameters
curl -X PUT http://localhost:8000/api/config/parameters \
  -H "Content-Type: application/json" \
  -d '[{"name": "DefDensity_t", "value": "2.5"}]'

# Validate weights
curl http://localhost:8000/api/config/validate
```

## Validation

All weight groups validate automatically:
- Global Weights must sum to 1.0
- Each dimension's weights must sum to 1.0
- Client survey weights must sum to 1.0
- Test maturity weights must sum to 1.0

API rejects updates that break validation.

## Migration Path

1. ✅ Database model created
2. ✅ Seed script populates initial data
3. ✅ ConfigService provides business logic
4. ✅ API endpoints for CRUD
5. ✅ All calculators refactored to async + DB
6. ✅ Frontend UI with tabs and editing
7. ✅ YAML config deprecated (moved to `backend/legacy/`)

## Backwards Compatibility

**None.** This is a breaking change. The old `ScoringConfig` class has been removed.

If you need to reference the old YAML structure, see `backend/legacy/scoring_config.yaml`.
```

**Step 2: Commit**

```bash
git add docs/CONFIG_MIGRATION.md
git commit -m "docs: add configuration migration guide

- Overview of YAML → DB migration
- Database structure and categories
- How to seed initial data
- How to edit via UI and API
- Validation rules
- Migration path documentation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Final Checklist

Before considering this complete:

- [ ] All backend tests pass (`pytest backend/ -v`)
- [ ] All frontend tests pass (`cd frontend && npm test`)
- [ ] Seed script runs successfully
- [ ] Settings UI loads and displays all 65 parameters
- [ ] Edit mode works with real-time validation
- [ ] Save persists changes to database
- [ ] Calculators use DB config (verify with integration test)
- [ ] No references to `ScoringConfig` remain in codebase
- [ ] Documentation complete

---

## Execution Notes

- **Working directory:** `/Volumes/Work/Dev/project-score-card/.worktrees/config-db-migration`
- **Current branch:** `feature/config-db-migration`
- **All commits should include Co-Authored-By tag**
- **Run migrations:** `cd backend && alembic upgrade head`
- **Seed data:** `cd backend && python scripts/seed_config_parameters.py`
- **Test backend:** `pytest backend/ -v`
- **Test frontend:** `cd frontend && npm test`
