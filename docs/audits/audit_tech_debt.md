# Tech Debt Audit — Checkpoint

Broad sweep across all modules + shared layers. One module per iteration. Findings go to `audit_findings.md` (grouped by severity).

## How to run

```
/loop Itera revisando docs/audits/audit_tech_debt.md. Cada vuelta:
1. Lee este checkpoint.
2. Escoge la PRIMERA fila con status=pending.
3. Lanza un Agent (Explore, very thorough) que revise SOLO esa ruta.
   Devuelve un resumen estructurado con:
   - DRY violations (código duplicado entre archivos)
   - Anti-patterns (transactions inside endpoints, error handlers que se tragan errores, etc.)
   - Código muerto (funciones/imports no usados)
   - Tests ausentes o triviales
   - Observability faltante (endpoints sin structlog, eventos sin contexto)
   - Permisos sin gating en FE (write-op UI sin usePermission)
   - Dependencias circulares o cross-module imports saltándose public.py
   - Archivos > 400 líneas que deberían dividirse
4. Anexa hallazgos a docs/audits/audit_findings.md agrupados por severidad
   (blocker / major / minor / nit) con file:line.
5. Marca la fila como status=done en este checkpoint, anota completed_at.
6. Si quedan pending, sigue. Si todas done, para con un resumen final.
```

## Checkpoint

| # | Path | Type | Status | Completed At | Notes |
|---|------|------|--------|--------------|-------|
| 1 | backend/app/core/api | shared | done | 2026-05-14 | auth, projects, admin_users, jobs, oauth, currencies, rates |
| 2 | backend/app/core/services | shared | done | 2026-05-14 | oauth_service, job_service, integration_token_service, exchange_rate_service, capacity_insights |
| 3 | backend/app/core/models | shared | done | 2026-05-14 | Project, User, Job, OAuthToken, IntegrationSetting, ExchangeRate |
| 4 | backend/app/core/permissions | shared | done | 2026-05-14 | RBAC core, role unions, require_permission |
| 5 | backend/app/modules/scorecard | module | done | 2026-05-14 | metrics, scores, config, collectors, snapshots, global dashboard |
| 6 | backend/app/modules/tracker | module | done | 2026-05-14 | reports, budgets, invoices, progress, moods, costs, EVM |
| 7 | backend/app/modules/notifications | module | done | 2026-05-14 | Slack, alerts, templates, scheduled jobs |
| 8 | backend/app/modules/capacity | module | done | 2026-05-14 | insights, allocation, planner |
| 9 | backend/app/modules/events | module | done | 2026-05-14 | events, attendees, stats, import |
| 10 | backend/app/modules/iso | module | done | 2026-05-14 | snapshots, reviews, exports |
| 11 | backend/app/modules/iso_docs | module | done | 2026-05-14 | wiki, registries, SOA |
| 12 | backend/app/modules/playbook | module | done | 2026-05-14 | tree nav, articles, versioning |
| 13 | backend/app/modules/devstack | module | done | 2026-05-14 | catalog, tech radar |
| 14 | backend/app/worker | infra | done | 2026-05-14 | ARQ jobs, cron schedules |
| 15 | backend/mcp_server | infra | done | 2026-05-14 | MCP tools, OAuth (actual path: /mcp_server/) |
| 16 | frontend/src/core | shared | done | 2026-05-14 | layout, contexts, hooks, services, types |
| 17 | frontend/src/modules/scorecard | module | done | 2026-05-14 | dashboard, ProjectDetail, settings |
| 18 | frontend/src/modules/tracker | module | done | 2026-05-14 | burn, time, budgets, invoices, moods |
| 19 | frontend/src/modules/notifications | module | done | 2026-05-14 | (directory does not exist; admin UI in core/ — see iteration #16) |
| 20 | frontend/src/modules/capacity | module | done | 2026-05-14 | insights, FA detail, user detail |
| 21 | frontend/src/modules/events | module | done | 2026-05-14 | EventCard, stats, attendees |
| 22 | frontend/src/modules/iso | module | done | 2026-05-14 | snapshots, reviews, ISOConfig |
| 23 | frontend/src/modules/iso-docs | module | done | 2026-05-14 | wiki, registries |
| 24 | frontend/src/modules/playbook | module | done | 2026-05-14 | tree, article view |
| 25 | frontend/src/modules/devstack | module | done | 2026-05-14 | catalog browser |
| 26 | frontend/src/shared | shared | done | 2026-05-14 | ui/, hooks, constants |

## Stop condition

All rows status=done.
