# CLAUDE.md

## Commands

Backend: `cd backend && pytest` / `python run_server.py`
Frontend: `cd frontend && npm test` / `npm run dev`
Worker: `cd backend && arq app.worker.settings.WorkerSettings`

## Modular Architecture Rules (MUST FOLLOW)

The Hub is a multi-module platform (scorecard, iso, tracker). See `docs/vizztracker_integration.md`.

1. **New code in modules**: `app/modules/{scorecard,iso,tracker}/`. Existing scorecard code stays until migrated.
2. **Core entities** (`Project`, `User`) in `app/core/models/`.
3. **Cross-module imports through `public.py` ONLY** — never import another module's internals.
4. **Write isolation, read flexibility**: Each module writes only to its own tables. Cross-module reads via `public.py`. Analytical JOINs allowed in `app/core/services/`.
5. **Entity placement**: ALL modules → `core/`. One creates, others read → owner + `public.py`. Single module → private.
6. **Frontend modules self-contained**: own `components/`, `hooks/`, `pages/`. Shared → `src/shared/`.
7. **Router aggregation**: Module `router.py` aggregates sub-routers. `main.py` only mounts module routers. Prefixes in `include_router`, never in router files.
8. **Project-scoped permissions**: New endpoints use `ProjectViewer`/`ProjectContributor`/`ProjectManager` from `app/core/permissions.py`. Existing scorecard can keep `CurrentUser`.
9. **URL = source of truth**: All view state in URL params. Use `useUrlState` hook, not bare `useState`. Tabs use nested routes.

## Constraints

- **Targets vs Ideals**: Target = minimum acceptable (color coding). Ideal = perfect score (100 pts). SPI 0.85 → green (above target) but 85 points (not 100). Only SPI/CPI have explicit ideals.
- **Snapshot types**: Capture creates BOTH cumulative and punctual. Manual fields synced between types; collector fields are NOT.
- **Disabled governance tools** → score 0, not neutral.
- **No trailing slashes**: Routes use `""` not `"/"`. `redirect_slashes=False` in main.py.
- **DBSession manages transactions**: Do NOT use `async with db.begin()` inside endpoints — nested transaction error. Only use manual `db.begin()` outside request context.
- **Weights must sum to 1.0** per group in `config_parameters`.
- **React Query keys**: Always use `queryKeys` from `hooks/queryKeys.ts`. Never string literals.

## Reference Docs

- `docs/CLAUDE_REFERENCE.md` — Auth, Slack, jobs, Redis cache, AWS, API endpoints
- `docs/vizztracker_integration.md` — Multi-module architecture spec
- `docs/OAUTH_SETUP.md` — Jira OAuth setup
- `docs/API.md` — Full API documentation
