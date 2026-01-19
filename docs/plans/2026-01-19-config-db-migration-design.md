# Configuration Database Migration - Design Document

**Date:** 2026-01-19
**Status:** Approved for implementation

## Overview

Migrate configuration parameters (targets, weights, constants) from YAML file to PostgreSQL database with full CRUD UI in Settings page.

**Current state:** `scoring_config.yaml` with hardcoded values, no UI editing
**Target state:** DB-backed configuration with edit UI, validation, and seed data

## Goals

1. Store all configuration parameters in database with metadata (unit, notes)
2. Enable UI editing with real-time weight validation
3. Maintain single source of truth (deprecate YAML completely)
4. Seed initial data from CSV on first deployment

## Data Model

### Database Schema

**Table: `config_parameters`**

```sql
CREATE TABLE config_parameters (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    name VARCHAR(100) NOT NULL UNIQUE,
    value DECIMAL(10, 4) NOT NULL,
    unit VARCHAR(50),
    notes TEXT,

    CONSTRAINT unique_param_name UNIQUE (name)
);

CREATE INDEX idx_config_category ON config_parameters(category);
```

**Fields:**
- `category`: Category from CSV ("Targets", "Quality Weights", "Global Weights", etc.)
- `name`: Technical parameter name (DefDensity_t, W_def, etc.) - **unique identifier**
- `value`: Numeric value (Decimal for precision)
- `unit`: Optional unit string ("defects/100 tasks", "weight", "hours", etc.)
- `notes`: Description/documentation from Excel

**SQLAlchemy Model:**

```python
# backend/app/models/config.py

class ConfigParameter(Base):
    __tablename__ = "config_parameters"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    unit: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
```

### Categories

Based on CSV structure:

- **Targets** (15 parameters): DefDensity_t, Escaped_t, MTTR_t, SPI_t, CPI_t, LT_t, FE_t, WIP_max, CFR_max, ROI_t, IaC_t, HighVuln_t, CritRisk_t, GovExc_t, PR_noReview_t
- **Quality Weights** (8 parameters): W_def, W_esc, W_mttr, W_q_storyrev, W_qual_gov, W_q_pr, W_q_design, W_q_science
- **Time Weights** (2 parameters): W_time_spi, W_time_milestones
- **Cost Weights** (2 parameters): W_cost_cpi, W_cost_var
- **Value Weights** (2 parameters): W_value_roi, W_value_okr
- **Satisfaction Weights** (10 parameters): W_sat_client, W_sat_pm, W_cs_understanding, W_cs_proactivity, W_cs_communication, W_cs_time, W_cs_response, W_cs_quality, W_cs_expect, W_cs_recommend
- **Efficiency Weights** (3 parameters): W_flow_lt, W_flow_fe, W_flow_cr
- **Engineering Weights** (4 parameters): W_eng_test, W_eng_pr, W_eng_iac, W_eng_arch
- **Risk Weights** (3 parameters): W_risk_pr, W_risk_vuln, W_risk_risks
- **Global Weights** (8 parameters): W_time, W_cost, W_quality, W_value, W_risk, W_flow, W_engineering, W_satisfaction
- **Gates & Constants** (3 parameters): Sev1_cap, GraceDays, Bonus_max
- **Test Maturity Weights** (5 parameters): W_test_e2e, W_test_unit, W_test_access, W_test_security, W_test_frontend

**Total: 65 parameters**

## Data Seeding

### CSV Source

**Location:** `backend/seeds/config_parameters.csv`

**Structure:**
```csv
category,name,value,unit,notes
Targets,DefDensity_t,3.00,defects/100 tasks,Target max defect density...
Quality Weights,W_def,0.05,weight,Defect density in P_quality
...
```

Clean tabular format with headers, no validators or empty rows.

### Seed Script

**Location:** `backend/scripts/seed_config_parameters.py`

**Logic:**
1. Check if `config_parameters` table is empty
2. If empty → parse CSV and insert all rows
3. If populated → skip (idempotent for deployments)

```python
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

        # Read and parse CSV
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
```

**Integration:** Run automatically on server startup (add to `run_server.py` or Alembic migration)

## Backend Services

### ConfigService

**Location:** `backend/app/services/config_service.py`

Business logic for configuration management:

```python
class ConfigService:
    """Business logic for configuration management."""

    @staticmethod
    async def get_all_parameters(
        db: AsyncSession
    ) -> dict[str, list[ConfigParameter]]:
        """Get all parameters grouped by category."""
        result = await db.execute(
            select(ConfigParameter).order_by(
                ConfigParameter.category,
                ConfigParameter.name
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
    async def get_parameter_value(
        db: AsyncSession,
        name: str
    ) -> Decimal:
        """Get a single parameter value by name."""
        result = await db.execute(
            select(ConfigParameter.value)
            .where(ConfigParameter.name == name)
        )
        value = result.scalar_one_or_none()
        if value is None:
            raise ValueError(f"Parameter {name} not found")
        return value

    @staticmethod
    async def get_parameters_by_category(
        db: AsyncSession,
        category: str
    ) -> dict[str, Decimal]:
        """Get all parameters in a category as dict {name: value}."""
        result = await db.execute(
            select(ConfigParameter)
            .where(ConfigParameter.category == category)
        )
        params = result.scalars().all()
        return {p.name: p.value for p in params}

    @staticmethod
    async def update_parameters(
        db: AsyncSession,
        updates: list[ConfigParameterUpdate]
    ) -> None:
        """Update parameters and validate weight groups."""
        # Update values
        for update in updates:
            result = await db.execute(
                select(ConfigParameter)
                .where(ConfigParameter.name == update.name)
            )
            param = result.scalar_one()
            param.value = update.value

        # Validate before commit
        errors = await ConfigService.validate_weight_groups(db)
        if errors:
            raise ValueError(f"Weight validation failed: {errors}")

        await db.commit()

    @staticmethod
    async def validate_weight_groups(db: AsyncSession) -> list[str]:
        """Validate that all weight groups sum to 1.0."""
        errors = []

        # Get all weight categories
        result = await db.execute(
            select(ConfigParameter)
            .where(ConfigParameter.category.like('%Weights'))
        )
        parameters = result.scalars().all()

        # Group by category and sum
        grouped = {}
        for param in parameters:
            if param.category not in grouped:
                grouped[param.category] = Decimal('0')
            grouped[param.category] += param.value

        # Check each group sums to 1.0
        for category, total in grouped.items():
            if abs(total - Decimal('1.0')) > Decimal('0.001'):
                errors.append(f"{category} sum is {total}, expected 1.0")

        return errors
```

### API Endpoints

**Location:** `backend/app/api/config.py`

```python
# GET /api/config/parameters
@router.get("/parameters")
@limiter.limit("100/minute")
async def get_config_parameters(
    request: Request,
    current_user: CurrentUser,
    db: DBSession
) -> dict[str, list[ConfigParameterResponse]]:
    """Get all config parameters grouped by category."""
    parameters = await ConfigService.get_all_parameters(db)

    # Convert to response models
    response = {}
    for category, params in parameters.items():
        response[category] = [
            ConfigParameterResponse.model_validate(p) for p in params
        ]

    return response


# PUT /api/config/parameters
@router.put("/parameters")
@limiter.limit("10/minute")
async def update_config_parameters(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    updates: list[ConfigParameterUpdate]
) -> dict[str, str]:
    """Update multiple config parameters. Validates weight groups."""
    try:
        await ConfigService.update_parameters(db, updates)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


# GET /api/config/validate
@router.get("/validate")
@limiter.limit("100/minute")
async def validate_config(
    request: Request,
    current_user: CurrentUser,
    db: DBSession
) -> dict[str, bool | dict]:
    """Validate that all weight groups sum to 1."""
    errors = await ConfigService.validate_weight_groups(db)
    return {
        "valid": len(errors) == 0,
        "errors": errors
    }
```

**Pydantic Models:**

```python
# backend/app/models/config.py

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

## Refactoring Existing Code

### Deprecate YAML-based ScoringConfig

**Files to remove:**
- `backend/scoring_config.yaml` → Keep as reference/documentation only
- `app/config.py::ScoringConfig` class → Delete
- `app/config.py::get_scoring_config()` → Delete

**Keep:** `app/config.py::Settings` for environment variables

### Migrate Calculators to Async

All calculators currently use sync `ScoringConfig`. Need to migrate to async DB queries.

**Before:**
```python
class QualityCalculator:
    def __init__(self, config: ScoringConfig):
        self.weights = {
            "defect_density": config.get_weight("quality", "defect_density"),
            "escaped_rate": config.get_weight("quality", "escaped_rate"),
        }

    def calculate(self, indicators: dict) -> float:
        score = (
            self.weights["defect_density"] * indicators.defect_density +
            self.weights["escaped_rate"] * indicators.escaped_rate
        )
        return score * 100
```

**After:**
```python
class QualityCalculator:
    @staticmethod
    async def calculate(db: AsyncSession, indicators: dict) -> float:
        # Load weights from DB
        weights = await ConfigService.get_parameters_by_category(
            db, "Quality Weights"
        )

        score = (
            weights["W_def"] * indicators.defect_density +
            weights["W_esc"] * indicators.escaped_rate +
            weights["W_mttr"] * indicators.mttr +
            weights["W_q_storyrev"] * indicators.story_review +
            weights["W_qual_gov"] * indicators.governance +
            weights["W_q_pr"] * indicators.pr_review
        )
        return score * 100
```

**Files to refactor:**
- `app/services/calculators/quality.py`
- `app/services/calculators/time.py`
- `app/services/calculators/cost.py`
- `app/services/calculators/value.py`
- `app/services/calculators/satisfaction.py`
- `app/services/calculators/flow.py`
- `app/services/calculators/engineering.py`
- `app/services/calculators/risk.py`
- `app/services/calculators/final_score.py`

**Update endpoints:**
- `app/api/metrics.py` - Remove `ScoringConfigDep`, pass `db` to calculators

### Mapping Parameter Names

**YAML → DB name mapping:**

Targets:
- `defect_density` → `DefDensity_t`
- `escaped_rate` → `Escaped_t`
- `mttr_hours` → `MTTR_t`
- `spi` → `SPI_t`
- `cpi` → `CPI_t`
- `lead_time_days` → `LT_t`
- `flow_efficiency` → `FE_t`
- `high_vuln_count` → `HighVuln_t`
- `gov_exceptions` → `GovExc_t`
- `pr_no_review_ratio` → `PR_noReview_t`

Constants:
- `sev1_cap` → `Sev1_cap`
- `grace_days` → `GraceDays`

Weights (example):
- `weights.quality.defect_density` → `W_def`
- `weights.quality.escaped_rate` → `W_esc`
- `weights.global.time` → `W_time`

## Frontend UI

### Settings Page with Tabs

**Location:** `frontend/src/pages/Settings.tsx`

**Structure:**
- Tab "Configuration" → All parameters with hierarchical display
- Tab "Validation" → Weight validation summary

**Edit Mode:**
- Toggle button: "Edit Configuration" / "Cancel" + "Save Changes"
- When editing: all values become inputs
- Real-time validation shows errors
- Save button disabled if validation fails

**Component Hierarchy:**

```
Settings
├── Tabs
│   ├── Configuration Tab
│   │   ├── ConfigSection (Targets)
│   │   ├── ConfigSection (Gates & Constants)
│   │   ├── WeightsSection (Global Weights)
│   │   ├── WeightsSection (Quality Weights)
│   │   ├── WeightsSection (Time Weights)
│   │   ├── ... (rest of weight groups)
│   └── Validation Tab
│       └── ValidationView
```

**ConfigSection Component:**

Displays parameters with unit and notes:

```tsx
function ConfigSection({ title, parameters, isEditing }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {parameters.map(param => (
            <ParameterRow
              key={param.id}
              parameter={param}
              isEditing={isEditing}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
```

**WeightsSection Component:**

Same as ConfigSection but with sum indicator:

```tsx
function WeightsSection({ title, parameters, isEditing }: Props) {
  const sum = parameters.reduce((acc, p) => acc + parseFloat(p.value), 0);
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
        {/* Parameters list */}
      </CardContent>
    </Card>
  );
}
```

**ParameterRow Component:**

Single parameter with view/edit modes:

```tsx
function ParameterRow({ parameter, isEditing }: Props) {
  const [value, setValue] = useState(parameter.value);

  return (
    <div className="flex items-center justify-between py-2 border-b last:border-0">
      <div className="flex-1">
        <div className="font-medium">{parameter.name}</div>
        {parameter.notes && (
          <div className="text-sm text-muted-foreground">
            {parameter.notes}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        {isEditing ? (
          <Input
            type="number"
            step="0.01"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="w-24"
          />
        ) : (
          <span className="font-medium">{parameter.value}</span>
        )}
        {parameter.unit && (
          <span className="text-sm text-muted-foreground min-w-[100px]">
            {parameter.unit}
          </span>
        )}
      </div>
    </div>
  );
}
```

### Real-Time Validation

**Custom Hook:** `useConfigEditor`

Manages state, validation, and save logic:

```tsx
function useConfigEditor() {
  const queryClient = useQueryClient();
  const { data: original } = useConfigParameters();
  const [edited, setEdited] = useState<Map<string, Decimal>>(new Map());
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  const updateValue = (name: string, value: Decimal) => {
    const newEdited = new Map(edited);
    newEdited.set(name, value);
    setEdited(newEdited);

    // Validate weights in real-time
    const errors = validateWeights(original, newEdited);
    setValidationErrors(errors);
  };

  const validateWeights = (
    original: ConfigParameters,
    changes: Map<string, Decimal>
  ): string[] => {
    const errors: string[] = [];
    const weightCategories = [
      'Global Weights',
      'Quality Weights',
      'Time Weights',
      'Cost Weights',
      'Value Weights',
      'Satisfaction Weights',
      'Efficiency Weights',
      'Engineering Weights',
      'Risk Weights',
      'Test Maturity Weights',
    ];

    weightCategories.forEach(category => {
      const params = original[category] || [];
      let sum = 0;

      params.forEach(param => {
        const value = changes.has(param.name)
          ? changes.get(param.name)
          : param.value;
        sum += parseFloat(value);
      });

      if (Math.abs(sum - 1.0) > 0.001) {
        errors.push(`${category} sum is ${sum.toFixed(4)}, expected 1.0`);
      }
    });

    return errors;
  };

  const hasChanges = edited.size > 0;
  const canSave = hasChanges && validationErrors.length === 0;

  return {
    original,
    updateValue,
    validationErrors,
    hasChanges,
    canSave,
    getEditedValue: (name: string) => edited.get(name),
  };
}
```

**Error Display:**

```tsx
{isEditing && validationErrors.length > 0 && (
  <Card className="bg-destructive/10 border-destructive">
    <CardContent className="pt-6">
      <p className="font-medium text-destructive mb-2">
        Validation Errors:
      </p>
      <ul className="list-disc list-inside text-sm text-destructive">
        {validationErrors.map((error, i) => (
          <li key={i}>{error}</li>
        ))}
      </ul>
    </CardContent>
  </Card>
)}
```

### React Query Hooks

**Location:** `frontend/src/hooks/useConfig.ts`

```typescript
export function useConfigParameters() {
  return useQuery({
    queryKey: ['config', 'parameters'],
    queryFn: async () => {
      const response = await api.get('/api/config/parameters');
      return response.data;
    }
  });
}

export function useConfigValidation() {
  return useQuery({
    queryKey: ['config', 'validation'],
    queryFn: async () => {
      const response = await api.get('/api/config/validate');
      return response.data;
    }
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
    }
  });
}
```

## Migration Strategy

**Complete migration - no dual mode:**

1. Create new DB table and models
2. Create seed script with CSV data
3. Add new API endpoints
4. Refactor all calculators to async + DB
5. Update all API endpoints using calculators
6. Build new Settings UI
7. Remove YAML ScoringConfig completely
8. Keep `scoring_config.yaml` as reference documentation

**No fallback to YAML:** DB is the single source of truth from day 1.

## Testing Strategy

### Backend Tests

**Unit tests:**
- `ConfigService.get_parameter_value()`
- `ConfigService.validate_weight_groups()` with various scenarios
- `ConfigService.update_parameters()` with validation

**Integration tests:**
- Seed script idempotency (run twice, check count)
- API endpoints (GET, PUT, validation)
- Calculator refactor (compare old vs new results)

**Example test:**

```python
async def test_weight_validation_fails():
    """Test that weight validation catches invalid sums."""
    # Set Quality Weights to sum to 0.95 instead of 1.0
    await db.execute(
        update(ConfigParameter)
        .where(ConfigParameter.name == "W_def")
        .values(value=Decimal("0.00"))
    )

    errors = await ConfigService.validate_weight_groups(db)
    assert len(errors) == 1
    assert "Quality Weights" in errors[0]
```

### Frontend Tests

**Component tests:**
- ParameterRow (view/edit modes)
- WeightsSection (sum calculation, validation indicator)
- Settings page (edit mode toggle)

**Hook tests:**
- `useConfigEditor` validation logic
- Real-time error detection

## Deployment Checklist

1. ✅ Create migration script (Alembic)
2. ✅ Run seed script on first deployment
3. ✅ Verify all 65 parameters loaded
4. ✅ Run validation endpoint - all groups should pass
5. ✅ Test calculator outputs match previous YAML-based results
6. ✅ Remove YAML references from deployment configs
7. ✅ Update documentation

## Open Questions

None - design approved.

## References

- CSV source: `backend/seeds/config_parameters.csv`
- Original Excel: User-provided legacy params sheet
- Current YAML: `backend/scoring_config.yaml` (reference only after migration)
