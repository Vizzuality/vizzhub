# Historical Metrics Capture - Design Document

**Date:** 2026-01-30
**Status:** ✅ Implemented

## Implementation Notes (Post-Implementation)

The design was implemented with some refinements:

1. **Unified `metrics` table** - Instead of extending `metric_snapshots`, we consolidated into a single `metrics` table with `snapshot_type` column.

2. **Default to CUMULATIVE** - All API endpoints default to `snapshot_type=cumulative` for consistency. Project detail and history pages show cumulative data by default.

3. **Capture endpoint creates BOTH types** - `POST /projects/{id}/capture-period` automatically creates both punctual and cumulative snapshots in a single call.

4. **Model defaults** - Both `MetricsDB` and `MetricsCreate` default to `SnapshotType.CUMULATIVE`.

---

## Overview

Sistema para capturar métricas históricas de Jira/GitHub y popular la base de datos con snapshots mensuales. Permite visualizar trends y detectar outliers.

## Requisitos

- Capturar métricas desde fecha inicio proyecto hasta fecha fin especificada
- Dos modos de captura: **cumulative** (desde inicio) y **punctual** (solo ese mes)
- Métricas manuales: heredar de mes más cercano si no existen
- Evitar rate limiting en Jira/GitHub
- Acción batch para capturar último año
- Reporte detallado de capturas y errores
- Interfaz: API endpoint + CLI + botón UI

## Decisiones de Diseño

| Decisión | Opción elegida | Razón |
|----------|----------------|-------|
| Modelo de datos | Extender `metric_snapshots` con `snapshot_type` | Reutiliza infraestructura existente |
| Rate limiting | Delay fijo (1s) + backoff exponencial | Previene errores + recupera si fallan |
| Métricas manuales | Más cercana en tiempo (antes o después) | Simple, cubre caso de uso real |
| Reporte | JSON response + logs durante ejecución | Visibilidad + integración UI |
| Errores en batch | Retry 3x, luego marcar error y continuar | Capturar máximo posible |
| Snapshots existentes | Saltar por defecto, `--force` para sobrescribir | Evita trabajo innecesario |
| Config histórica | Guardar weights/targets en snapshot | Auditabilidad (ya implementado) |
| Operación larga | Síncrono inicialmente | Simple, migrar a async si necesario |

## Modelo de Datos

### Cambio en `metric_snapshots`

```python
class SnapshotType(str, Enum):
    CUMULATIVE = "cumulative"  # Desde inicio proyecto hasta mes
    PUNCTUAL = "punctual"      # Solo ese mes

# Actualizar índice único para permitir 2 snapshots por mes
__table_args__ = (
    Index(
        "uq_snapshot_project_month_type",
        "project_id",
        "period_year",
        "period_month",
        "snapshot_type",
        unique=True,
    ),
)
```

### Migración

- Añadir valor `"punctual"` como opción válida para `snapshot_type`
- Actualizar índice único para incluir `snapshot_type`
- Snapshots existentes mantienen `snapshot_type = "monthly"` (equivalente a cumulative)

## Mapeo de Métricas

| Métrica | Cumulative | Punctual |
|---------|------------|----------|
| bugs_total | Todos desde inicio proyecto | Solo creados ese mes |
| bugs_resolved | Todos resueltos hasta fecha | Solo resueltos ese mes |
| tasks_completed | Todos hasta fecha | Solo completados ese mes |
| total_merged_prs | Todos hasta fecha | Solo mergeados ese mes |
| deployment_frequency | N/A (ya es rate) | Deploys ese mes |
| lead_time_days | Promedio histórico | Promedio del mes |

## Arquitectura

### Servicio Principal

```python
# services/historical_capture_service.py

@dataclass
class CaptureResult:
    month: str
    snapshot_type: SnapshotType
    status: Literal["created", "skipped", "error"]
    error_message: str | None = None

@dataclass
class CaptureReport:
    project_id: str
    requested_range: tuple[date, date]
    captured: list[CaptureResult]
    errors: list[CaptureResult]
    summary: dict  # total, created, skipped, errors

class HistoricalCaptureService:
    DELAY_BETWEEN_CALLS = 1.0  # segundos
    MAX_RETRIES = 3

    async def capture_month(
        self,
        project_id: str,
        month: date,
        snapshot_type: SnapshotType,
        force: bool = False,
    ) -> CaptureResult

    async def capture_range(
        self,
        project_id: str,
        from_date: date,
        to_date: date,
        force: bool = False,
    ) -> CaptureReport
```

### Flujo de `capture_month`

1. Verificar si existe snapshot → skip si existe y no `force`
2. Calcular fechas según tipo (cumulative vs punctual)
3. Llamar Jira collector con fechas
4. Llamar GitHub collector con fechas
5. Obtener métricas manuales (más cercanas)
6. Guardar config actual (weights/targets)
7. Crear snapshot

### Collectors con Filtrado por Fechas

```python
# Modificación a collectors existentes

async def collect_metrics(
    self,
    project_key: str,
    from_date: date | None = None,
    to_date: date | None = None,
) -> JiraMetrics:
    # Si no hay fechas → comportamiento actual (todo)
    # Si hay fechas → filtrar por rango
```

**JQL ejemplos:**
```
# Punctual (solo marzo)
project = X AND resolved >= "2024-03-01" AND resolved < "2024-04-01"

# Cumulative (hasta fin marzo)
project = X AND resolved < "2024-04-01"
```

**Rate limiting:**
```python
async def _api_call_with_retry(self, call: Callable) -> Any:
    for attempt in range(MAX_RETRIES):
        await asyncio.sleep(DELAY_BETWEEN_CALLS)
        try:
            return await call()
        except RateLimitError:
            await asyncio.sleep(2 ** attempt)  # backoff exponencial
    raise CaptureError("Max retries exceeded")
```

### Métricas Manuales

```python
async def get_closest_manual_metrics(
    self,
    project_id: str,
    target_month: date,
) -> ManualMetrics | None:
    """Busca métricas manuales más cercanas al mes objetivo."""

    MANUAL_FIELDS = [
        "strategic_impact",
        "client_survey",
        "sev1_incidents",
        "evm_data",
        "milestones",
        "governance_tools",
    ]
```

**Query:**
```sql
SELECT *,
       ABS(EXTRACT(EPOCH FROM (period_end - :target_date))) as distance
FROM metrics
WHERE project_id = :project_id
  AND (strategic_impact IS NOT NULL OR ...)
ORDER BY distance ASC
LIMIT 1
```

### Gestión de Fechas

| Tipo | from_date | to_date |
|------|-----------|---------|
| Cumulative | `project.start_date` | Último día del mes |
| Punctual | Primer día del mes | Último día del mes |

```python
# Ejemplo: Marzo 2024, proyecto empezó 2024-01-15

# Cumulative
from_date = date(2024, 1, 15)  # project.start_date
to_date = date(2024, 3, 31)    # último día marzo

# Punctual
from_date = date(2024, 3, 1)   # primer día marzo
to_date = date(2024, 3, 31)    # último día marzo
```

## API

### Endpoint

```python
@router.post("/projects/{project_id}/capture-history")
async def capture_history(
    project_id: UUID,
    request: CaptureHistoryRequest,
    db: DBSession,
) -> CaptureReport:

class CaptureHistoryRequest(BaseModel):
    from_year: int
    from_month: int
    to_year: int
    to_month: int
    force: bool = False
```

### Respuesta

```json
{
  "project_id": "uuid",
  "requested_range": ["2024-01", "2024-12"],
  "summary": {
    "total_months": 12,
    "snapshots_created": 22,
    "snapshots_skipped": 2,
    "errors": 0
  },
  "details": [
    {"month": "2024-01", "type": "cumulative", "status": "created"},
    {"month": "2024-01", "type": "punctual", "status": "created"},
    {"month": "2024-02", "type": "cumulative", "status": "skipped"}
  ],
  "errors": []
}
```

## CLI

```bash
python scripts/capture_history.py \
  --project-id "uuid" \
  --from 2024-01 \
  --to 2024-12 \
  --force  # opcional
```

## UI

### Componente HistoricalCaptureButton

Ubicación: `ProjectHistory.tsx`

**Modal con:**
- Toggle: "Mes concreto" / "Rango de meses"
- Si single: Selector mes/año único
- Si range: Selectores desde/hasta
- Checkbox "Sobrescribir existentes"
- Botón "Capturar"
- Progreso durante ejecución
- Resumen al finalizar

### Hook

```tsx
const { mutate, isPending } = useMutation({
  mutationFn: (params) =>
    api.post(`/projects/${projectId}/capture-history`, params),
  onSuccess: () => {
    queryClient.invalidateQueries(queryKeys.snapshots.byProject(projectId));
  }
});
```

## Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Rate limiting Jira/GitHub | Captura incompleta | Delay 1s + backoff + retry 3x |
| Timeout en batch largo | Request falla | Timeout largo, migrar a async si necesario |
| Datos históricos incompletos | Métricas incorrectas | Log warning, continuar con resto |
| Proyecto sin start_date | Error en cumulative | Validar antes, error claro |

## Implementación

### Orden sugerido

1. Migración BD (índice único con snapshot_type)
2. Modificar collectors para aceptar fechas
3. Servicio HistoricalCaptureService
4. API endpoint
5. CLI script
6. UI (modal + botón)

### Estimación

- Backend (migración + servicio + API + CLI): ~2-3 días
- Frontend (modal + hook): ~1 día
- Testing: ~1 día
