# Configuration Database Migration

## Overview

Project Scorecard configuration has been migrated from `scoring_config.yaml` to a PostgreSQL database. This enables:

- **Live Updates**: Changes apply immediately without server restart
- **Audit Trail**: Track configuration changes over time
- **Web UI**: Edit configuration through the Settings page
- **Validation**: Real-time weight validation ensures data integrity
- **Multi-Environment**: Different values per deployment without code changes

## What Changed

### Before (YAML-based)

**File:** `backend/scoring_config.yaml`

```yaml
targets:
  DefDensity_t: 3.0
  Escaped_t: 0.01

global_weights:
  W_quality: 0.15
  W_time: 0.15
```

- Static file requiring server restart for changes
- No validation until runtime
- Manual editing prone to errors
- No change history

### After (Database-backed)

**Table:** `config_parameters`

```sql
CREATE TABLE config_parameters (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100),
    name VARCHAR(100) UNIQUE,
    value NUMERIC(10, 4),
    unit VARCHAR(50),
    notes TEXT
);
```

- Live updates via Settings UI or API
- Automatic weight validation (sum = 1.0)
- Change tracking via database transactions
- User-friendly interface with notes and units

## Using the Settings UI

### Viewing Configuration

1. Navigate to **Settings** in the main menu
2. **Configuration Tab**: View all 65 configuration parameters organized by category:
   - Targets (DefDensity_t, Escaped_t, etc.)
   - Gates & Constants (GraceDays, Sev1_cap, etc.)
   - Global Weights (8 dimension weights)
   - Dimension Weights (Quality, Time, Cost, Value, Satisfaction, Flow, Engineering, Risk)
   - Test Maturity Weights

3. **Validation Tab**: View current weight validation status

### Editing Configuration

1. Click **Edit Configuration** button
2. Modify parameter values using number inputs
3. **Real-time Validation**:
   - Weight sections show sum and validation icon (✓ or ✗)
   - Green checkmark = valid (sum = 1.0 ± 0.001)
   - Red X = invalid (requires correction)
4. Click **Save Changes** (disabled if validation fails)
5. Click **Cancel** to discard changes

### Validation Rules

- **Weight Groups**: All weight categories must sum to 1.0 (±0.001 tolerance)
  - Global Weights (8 dimensions)
  - Quality Weights (6 sub-indicators)
  - Time Weights (2 sub-indicators)
  - Cost Weights (2 sub-indicators)
  - Value Weights (2 sub-indicators)
  - Satisfaction Weights (2 sub-indicators)
  - Flow Weights (3 sub-indicators)
  - Engineering Weights (3 sub-indicators)
  - Risk Weights (2 sub-indicators)
  - Test Maturity Weights (4 sub-indicators)

- **Targets & Constants**: No sum validation, but must be numeric

## Developer Guide

### Accessing Configuration in Code

**Backend (Python):**

```python
from app.services.config_service import ConfigService
from sqlalchemy.ext.asyncio import AsyncSession

# Get single parameter value
async def example(db: AsyncSession):
    defdensity_target = await ConfigService.get_parameter_value(db, "DefDensity_t")
    # Returns: Decimal("3.0000")

# Get parameters by category (as dict)
async def example2(db: AsyncSession):
    quality_weights = await ConfigService.get_parameters_by_category(db, "Quality Weights")
    # Returns: {"W_quality_dd": Decimal("0.2500"), "W_quality_er": Decimal("0.1500"), ...}

# Get all parameters grouped by category
async def example3(db: AsyncSession):
    all_params = await ConfigService.get_all_parameters(db)
    # Returns: {"Targets": [ConfigParameter(...), ...], "Global Weights": [...], ...}

# Validate weight groups
async def example4(db: AsyncSession):
    errors = await ConfigService.validate_weight_groups(db)
    # Returns: [] if valid, ["Quality Weights sum is 0.98, expected 1.0"] if invalid

# Update parameters
async def example5(db: AsyncSession):
    updates = [
        ConfigParameterUpdate(name="W_quality_dd", value=Decimal("0.30")),
        ConfigParameterUpdate(name="W_quality_er", value=Decimal("0.10")),
    ]
    await ConfigService.update_parameters(db, updates)
    # Validates weights before committing, raises ValueError if invalid
```

**Frontend (TypeScript):**

```typescript
import { useConfigParameters, useUpdateConfigParameters, useConfigValidation } from '@/hooks/useConfig';

function MyComponent() {
  // Fetch all parameters grouped by category
  const { data: parameters, isLoading } = useConfigParameters();
  // parameters: Record<string, ConfigParameter[]>

  // Check validation status
  const { data: validation } = useConfigValidation();
  // validation: { valid: boolean, errors: string[] }

  // Update parameters
  const updateMutation = useUpdateConfigParameters();

  const handleSave = async () => {
    const updates = [
      { name: 'W_quality_dd', value: '0.30' },
      { name: 'W_quality_er', value: '0.10' },
    ];
    await updateMutation.mutateAsync(updates);
    // Automatically invalidates config and scores queries
  };
}
```

### API Endpoints

**GET /api/config/parameters**
- Returns: `Record<string, ConfigParameter[]>` grouped by category
- Auth: Required (JWT token)
- Rate limit: 100/minute

**PUT /api/config/parameters**
- Body: `ConfigParameterUpdate[]` (array of {name, value})
- Returns: `{status: "success"}` or 400 error with validation details
- Validates weight groups before committing
- Auth: Required (JWT token)
- Rate limit: 10/minute

**GET /api/config/validate**
- Returns: `{valid: boolean, errors: string[]}`
- Auth: Required (JWT token)
- Rate limit: 100/minute

## Migration Notes

### Initial Deployment

1. **Database Migration**: Run Alembic migration to create `config_parameters` table
   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Seed Data**: Populate table with initial values from CSV
   ```bash
   cd backend
   python -c "import asyncio; from scripts.seed_config_parameters import seed_config_parameters; asyncio.run(seed_config_parameters())"
   ```

3. **Verify**: Check that 65 parameters were inserted
   ```sql
   SELECT category, COUNT(*) FROM config_parameters GROUP BY category;
   ```

### Legacy YAML File

The original `scoring_config.yaml` has been moved to `backend/legacy/scoring_config.yaml` for reference. It is no longer used by the application.

### Backward Compatibility

**⚠️ Breaking Change**: The old `ScoringConfig` class has been removed. Any code referencing it must be updated to use `ConfigService`.

**Before:**
```python
from app.config import get_scoring_config

config = get_scoring_config()
target = config.targets.DefDensity_t  # Synchronous
```

**After:**
```python
from app.services.config_service import ConfigService

target = await ConfigService.get_parameter_value(db, "DefDensity_t")  # Async
```

### Calculator Refactoring Status

**NOTE**: As of this migration, calculators still use the legacy YAML-based `ScoringConfig` class. Calculator refactoring to use the database-backed config is planned but not yet implemented.

This means:
- ✅ Settings UI works and stores values in database
- ✅ API endpoints read/write to database
- ❌ Calculators do NOT yet use database values
- ❌ Changes in Settings UI do NOT yet affect score calculations

**Next Steps**: Migrate all 8 calculators + FinalScoreCalculator to async and use `ConfigService` instead of `ScoringConfig`.

## Testing

### Backend Tests

```bash
cd backend

# All config tests
pytest tests/test_config_*.py tests/test_api_config.py -v

# Specific test categories
pytest tests/test_config_model.py -v      # Database model tests
pytest tests/test_config_service.py -v    # Business logic tests
pytest tests/test_api_config.py -v        # API endpoint tests
```

**Coverage**: 13 tests covering:
- Model creation and constraints
- Service methods (get, update, validate)
- API endpoints with auth
- Weight validation logic

### Frontend Tests

```bash
cd frontend

# All tests
npm test

# Config-specific tests
npm test -- useConfig.test
npm test -- Settings.test
```

**Coverage**: 5 tests for config hooks + 3 tests for Settings UI

### Manual Testing

1. Start backend: `cd backend && python run_server.py`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to http://localhost:5173/settings
4. Test edit mode, validation, save/cancel

## Troubleshooting

### "Weight validation failed" error

**Problem**: Sum of weights in a category ≠ 1.0

**Solution**: Check all weights in that category. They must sum to exactly 1.0 (within 0.001 tolerance).

Example:
```
Quality Weights sum is 0.98, expected 1.0
```

This means you need to add 0.02 across the Quality Weights parameters.

### Changes not reflected in UI

**Problem**: Settings page shows old values after save

**Solution**: The save operation automatically invalidates React Query cache. If values don't update:
1. Check browser console for API errors
2. Hard refresh (Cmd+Shift+R / Ctrl+Shift+R)
3. Verify backend database was actually updated

### Migration didn't run

**Problem**: Table `config_parameters` doesn't exist

**Solution**: Run Alembic migration:
```bash
cd backend
alembic upgrade head
```

### Seed data didn't load

**Problem**: Table exists but has 0 rows

**Solution**: Run seed script:
```bash
cd backend
python scripts/seed_config_parameters.py
```

**Note**: Seed script is idempotent - it only inserts data if table is empty.

## Future Enhancements

- [ ] Change history tracking (audit log)
- [ ] Rollback to previous values
- [ ] Export/import configuration as JSON
- [ ] Configuration templates for different project types
- [ ] Per-project configuration overrides
- [ ] Calculator refactoring to use database config

## Related Documentation

- [Design Document](plans/2026-01-19-config-db-migration-design.md) - Architecture decisions
- [Implementation Plan](plans/2026-01-19-config-db-migration-implementation.md) - Step-by-step implementation
- [Security Quick Start](SECURITY_QUICK_START.md) - Authentication requirements
