# SonarQube Issues Report

**Fecha:** 2026-02-01
**Proyecto:** Vizzuality_project-score-card
**Total Issues:** 7,847

## Resumen por Severidad

| Severidad | Cantidad |
|-----------|----------|
| BLOCKER | 3 |
| CRITICAL | 29 |
| MAJOR | 3,911 |
| MINOR | 3,896 |
| INFO | 8 |

## Resumen por Tipo

| Tipo | Cantidad |
|------|----------|
| Code Smell | 7,688 |
| Bug | 156 |
| Vulnerability | 3 |

---

## BLOCKER (3) - Secrets Expuestos

| # | Archivo | Línea | Descripción |
|---|---------|-------|-------------|
| 1 | `docker-compose.yml` | 32 | PostgreSQL password hardcodeado |
| 2 | `docker-compose.yml` | 80 | PostgreSQL password hardcodeado |
| 3 | `.github/workflows/ci.yml` | 51 | PostgreSQL password en CI |

**Acción:** Usar variables de entorno o GitHub Secrets.

---

## CRITICAL (29) - Complejidad Cognitiva

### Backend (Python)

| # | Archivo | Línea | Complejidad | Permitido |
|---|---------|-------|-------------|-----------|
| 1 | `collectors/github/utils.py` | 117 | 42 | 15 |
| 2 | `collectors/github/utils.py` | 26 | 34 | 15 |
| 3 | `collectors/jira/commitment_reliability.py` | 132 | 37 | 15 |
| 4 | `scripts/run_jira_basic.py` | 21 | 22 | 15 |
| 5 | `api/oauth.py` | - | Literal duplicado "Token refresh failed" x3 |
| 6 | `collectors/jira/client.py` | 27 | 20 | 15 |
| 7 | `services/metrics_service.py` | 248 | 19 | 15 |
| 8 | `collectors/jira/lead_time.py` | 146 | 19 | 15 |
| 9 | `collectors/github/vulnerabilities.py` | 84 | 18 | 15 |
| 10 | `scripts/migrate_percentage_targets.py` | 53 | 17 | 15 |
| 11 | `api/scores.py` | 103 | 17 | 15 |
| 12 | `collectors/jira/lead_time.py` | 71 | 16 | 15 |
| 13 | `collectors/jira/commitment_reliability.py` | 44 | 16 | 15 |
| 14 | `models/metrics.py` | 598 | 16 | 15 |
| 15 | `api/jobs.py` | 135 | Literal duplicado "Job not found" x3 |
| 16 | `alembic/versions/000_initial_schema.py` | 25 | Literal "gen_random_uuid()" x4 |
| 17 | `alembic/versions/000_initial_schema.py` | 57 | Literal "projects.id" x3 |
| 18 | `scripts/run_jira_basic.py` | 33 | Literal duplicado x3 |

### Frontend (TypeScript)

| # | Archivo | Línea | Complejidad | Permitido |
|---|---------|-------|-------------|-----------|
| 1 | `QualityMetricsGrid.tsx` | 107 | 24 | 15 |
| 2 | `EditableMetricCard.tsx` | 47 | 18 | 15 |
| 3 | `EVMSection.tsx` | 36 | 16 | 15 |
| 4 | `EVM/PerformanceCard.tsx` | 35 | 16 | 15 |
| 5 | `ClientSurveyCard.tsx` | 95 | Nesting > 4 levels |
| 6 | `TestMaturityCard.tsx` | 71 | Nesting > 4 levels |
| 7 | `ArchitectureCard.tsx` | 83 | Nesting > 4 levels |
| 8 | `ArchitectureCard.tsx` | 91 | Nesting > 4 levels |
| 9 | `test/setup.ts` | 5-7 | Empty methods (mock) |

---

## Prioridad de Resolución

1. **P0 - Inmediato:** Secrets expuestos (3 BLOCKER)
2. **P1 - Alta:** Complejidad cognitiva > 30 (2 funciones)
3. **P2 - Media:** Complejidad cognitiva 16-30 (resto)
4. **P3 - Baja:** Literales duplicados, empty methods

---

## Progreso

- [x] BLOCKER: Secrets en docker-compose.yml → Usa `env_file: .env.docker`
- [x] BLOCKER: Secrets en ci.yml → Usa `secrets.DB_PASSWORD_CI`
- [x] CRITICAL: github/utils.py (42, 34 complejidad) → Helpers extraídos
- [x] CRITICAL: jira/commitment_reliability.py (37 complejidad) → Helpers extraídos
- [x] CRITICAL: jira/lead_time.py (19, 16 complejidad) → Helpers extraídos
- [x] CRITICAL: jira/client.py (20 complejidad) → Métodos extraídos
- [x] CRITICAL: github/vulnerabilities.py (18 complejidad) → Helpers extraídos
- [x] CRITICAL: api/jobs.py → Constante JOB_NOT_FOUND
- [x] CRITICAL: api/oauth.py → Constante TOKEN_REFRESH_FAILED
- [x] CRITICAL: QualityMetricsGrid.tsx (24 complejidad) → `renderConditionalCard()`
- [x] CRITICAL: ClientSurveyCard.tsx → Helper `getRatingColor()`
- [x] CRITICAL: TestMaturityCard.tsx → Helper `getMaturityColor()`
- [x] CRITICAL: test/setup.ts → Comentarios en mocks vacíos

**Fecha:** 2026-02-01
**Archivos modificados:** 14
