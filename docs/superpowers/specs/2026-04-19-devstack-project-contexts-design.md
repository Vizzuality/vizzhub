# DevStack Project Contexts — Design

**Status:** Approved
**Date:** 2026-04-19
**Module:** DevStack
**Related:** `docs/devstack.md`, `project_devstack-module.md` (memory)

## Problem

Some client projects (NDA, GovTech, compliance-bound) cannot host their `CLAUDE.md` in the project's public GitHub repo. Today there is no sanctioned way to distribute per-project Claude instructions privately. Individual devs either:

- Commit CLAUDE.md to the public repo (compliance breach), or
- Keep it ad-hoc in their local filesystem (no team consistency), or
- Skip per-project Claude context entirely (degraded AI assistance).

## Goal

Register per-project private `CLAUDE.md` files in VizzHub (DevStack), stored in a private monorepo, and distribute them to developer workstations via the existing MCP + skill sync mechanism — without any new client-side convention (no forced `git clone`, no local path conventions, no filesystem setup).

## Non-goals (v1)

- Editing via DevStack UI (edits happen on the private repo directly, via any git workflow the editor prefers).
- Write MCP tool for private-context changes (out of scope; editors push to the private repo themselves).
- Project-scoped read permissions (trust-based; gate is the GitHub private repo access itself).
- Distributing per-project skills/commands/agents (CLAUDE.md only in v1; extensible later).
- Handling context deletion on the dev workstation (dev cleans up `./CLAUDE.md` manually if needed).

## Architecture

Reuses the exact pattern of the existing `devstack_get_installable` flow (server-side content fetch via GitHub API, client writes to filesystem with SHA marker for drift detection). No local git clone required for consumers.

### Components

```
┌─────────────────────────┐
│ Vizzuality/project-     │  Private monorepo, one folder per slug:
│ contexts  (GitHub)      │    acme-corp/CLAUDE.md
└───────────┬─────────────┘    gov-project-x/CLAUDE.md
            │  GitHub API
            │  (backend token)
            ▼
┌─────────────────────────┐
│ VizzHub backend         │  devstack_project_contexts table
│  - REST API (admin CRUD)│  registers slug ↔ private folder mapping
│  - MCP server           │  MCP tools fetch content server-side
└───────────┬─────────────┘
            │  MCP (HTTP/SSE)
            ▼
┌─────────────────────────┐
│ Developer workstation   │  devstack-sync skill:
│  Claude Code session    │   1. reads .claude/.devstack-context (slug)
│                         │   2. calls devstack_get_project_context
│                         │   3. writes ./CLAUDE.md + SHA marker
│                         │   4. ensures CLAUDE.md in .gitignore
└─────────────────────────┘
```

### Data model

New table `devstack_project_contexts`. **The existing `devstack_entries` and `projects` tables are NOT modified** — keeping the catalog (shareable artifacts) and project contexts (per-project private briefs) as separate domains avoids a discriminator-with-many-nullables antipattern.

```python
class DevstackProjectContextDB(Base):
    __tablename__ = "devstack_project_contexts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # [a-z0-9-]+, used as folder name in the private repo and client-side identifier

    project_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    # Nullable because a context could exist without a VizzHub Project row,
    # though in v1 the UI always picks from the Projects dropdown.

    private_repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    # e.g. "git@github.com:Vizzuality/project-contexts.git"
    # Stored per-row so we *could* support multiple private repos later,
    # but v1 always uses the single org monorepo.

    folder_path: Mapped[str] = mapped_column(String(128), nullable=False)
    # Path within the private repo; typically == slug.

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at, updated_at: timestamps
```

**Single source of slug uniqueness**: `slug` is globally unique. We do NOT allow two contexts for the same project.

### Private repo layout

`Vizzuality/project-contexts` (new private repo in the Vizzuality org):

```
project-contexts/
├── README.md                    # internal ops notes
├── acme-corp/
│   └── CLAUDE.md
├── gov-project-x/
│   └── CLAUDE.md
└── ...
```

One folder per registered context. Folder name = `folder_path` (typically == `slug`). Only `CLAUDE.md` is read by DevStack in v1 — other files in the folder are ignored (leaves room for future per-project skills).

Backend accesses this repo via the existing GitHub service token (same one used by the catalog's `devstack_get_installable`). The token must have read access to `Vizzuality/project-contexts`.

### Backend API

New REST router under `/api/devstack/project-contexts` (mounted via `app/modules/devstack/router.py`):

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| `GET`  | `""` | `DEVSTACK_VIEW` | List all contexts (slug, project_id, description, project_name via join) |
| `POST` | `""` | `DEVSTACK_MANAGE` | Create — body: `project_id`, `slug`, `private_repo_url`, `folder_path`, `description` |
| `GET`  | `/{id}` | `DEVSTACK_VIEW` | Detail |
| `PUT`  | `/{id}` | `DEVSTACK_MANAGE` | Update (slug editable until first sync — not enforced in v1, just a convention) |
| `DELETE` | `/{id}` | `DEVSTACK_MANAGE` | Delete |

List endpoint joins `projects` to surface `project_name` for the UI dropdown.

### MCP tools

New read-only tools in `app/mcp/tools/devstack.py`:

```python
@mcp.tool()
async def devstack_list_project_contexts() -> list[dict]:
    """List registered project contexts (slug + description + project_name).
    Use for discovery when the dev doesn't know the slug."""

@mcp.tool()
async def devstack_get_project_context(slug: str) -> dict:
    """Fetch a project's private CLAUDE.md content.
    Returns {target_path: "CLAUDE.md", content: str, devstack_sha: str, slug: str}.
    The SHA is the GitHub blob SHA of the CLAUDE.md file — used for drift detection
    exactly like devstack_get_installable."""
```

Both tools require `DEVSTACK_VIEW` (included in the default `user` role — every authenticated dev can call them). The real confidentiality boundary is the private GitHub repo's access list, not the MCP layer.

Error codes mirror `devstack_get_installable`:

- `NOT_FOUND` — slug not registered
- `FETCH_FAILED` — GitHub API call failed (auth, network, etc.)
- `NO_CONTENT` — folder exists but has no `CLAUDE.md`

### Skill changes (`devstack-sync`)

Add an optional section "Per-project private context" to the skill (the skill itself is public and distributed via the catalog — it contains only instructions, zero private data).

Skill logic (per session start):

1. **Check for slug**: read `.claude/.devstack-context` in the project root. If missing, invite the user: *"This project doesn't have a DevStack context configured. Is there one? (y/N) If yes, what's the slug?"* — persist the answer to `.claude/.devstack-context` (a one-line file with just the slug) and add that file to `.gitignore` if not already present.

2. **Fetch content**: call `devstack_get_project_context(slug)` → receives `{content, devstack_sha}`.

3. **Drift check**: read `./CLAUDE.md`. If it contains a trailing marker `<!-- devstack_sha: <sha> -->` matching `devstack_sha`, skip. Otherwise re-write.

4. **Write**: overwrite `./CLAUDE.md` with `content` + trailing `\n<!-- devstack_sha: {devstack_sha} -->`.

5. **Gitignore check**: ensure `CLAUDE.md` is present in `.gitignore` at the project root. If not, append it and alert the user: *"Added CLAUDE.md to .gitignore — this file contains private instructions and must not be committed to the public repo."*

**MUST-opcional semantics**: the section applies only if `.claude/.devstack-context` exists OR the user confirms a slug. For projects without a context configured, the whole section is a no-op — no prompts, no friction.

**Editing**: the skill tells the dev: *"To edit: clone `Vizzuality/project-contexts` anywhere, edit `<folder>/CLAUDE.md`, commit, push. Your team will see the change on their next session. Conflicts are resolved via normal git workflow."* No convention on clone location — not our problem.

### Frontend

New page `/devstack/contexts` under the existing `DevStack` sidebar entry. Sidebar gets two sub-entries: "Catalog" (existing `/devstack`) and "Project Contexts" (new).

**List page**: table with columns `Project`, `Slug`, `Description`, `Actions` (Edit/Delete for `DEVSTACK_MANAGE`). Gated client-side with `usePermission(Action.DEVSTACK_MANAGE)` per the permission-gating rule in `CLAUDE.md` §8.

**Create/Edit form**:

- **Project dropdown**: searchable Combobox listing existing VizzHub projects (uses existing `useProjects` hook). On selection, auto-generates slug from project name via `slugify(name)` (lowercase, hyphens, strip diacritics, `[a-z0-9-]+` only). Admin can override the auto-slug.
- **Private repo URL**: text input, defaulted to `git@github.com:Vizzuality/project-contexts.git` (constant, editable only if needed — v1 always uses the monorepo).
- **Folder path**: text input, defaulted to the slug value. Editable if the folder in the private repo doesn't match slug for historical reasons.
- **Description**: free text.

Permissions:

- Page route: `<PermissionRoute require={Action.DEVSTACK_VIEW}>`
- "New Project Context" button, Edit/Delete actions: gated by `usePermission(Action.DEVSTACK_MANAGE)` both at render time and at dialog-open time (defense in depth).

### Permissions recap

No new permissions. Uses existing:

- `DEVSTACK_VIEW` (in `user` role, given to all authenticated devs) — list/get contexts, call MCP tools
- `DEVSTACK_MANAGE` (admin/manager) — CRUD on contexts

Confidentiality is enforced at the private GitHub repo level — the VizzHub DB only stores metadata (slugs and repo paths), not CLAUDE.md content. If a slug "leaks", the attacker still can't fetch content without GitHub access.

## Flow: developer starts work on a private project

```
Dev cd's into ~/work/acme-corp (public project repo, no CLAUDE.md yet)
  └─ claude
     └─ Session start → devstack-sync skill runs
        ├─ .claude/.devstack-context missing
        ├─ Skill asks: "DevStack context for this project?"
        ├─ Dev: "acme-corp"
        ├─ Skill writes .claude/.devstack-context = "acme-corp"
        ├─ Skill calls devstack_get_project_context("acme-corp")
        │   └─ Backend fetches Vizzuality/project-contexts/acme-corp/CLAUDE.md
        │       via GitHub API → returns {content, devstack_sha}
        ├─ Skill writes ./CLAUDE.md with content + SHA marker
        └─ Skill appends "CLAUDE.md" to .gitignore (was missing)

Dev edits CLAUDE.md through whatever workflow they prefer:
  Option 1: GitHub web UI on the private repo
  Option 2: Clone private repo somewhere (~/whatever), edit, commit, push
  → either way, next session any team member sees the update via SHA mismatch
```

## Open questions resolved during brainstorming

| Question | Resolution |
|----------|------------|
| Local clone required? | **No.** Backend fetches content via GitHub API. Only editors clone, wherever they want. |
| Slug detection | Ask once, persist in `.claude/.devstack-context`. |
| New section or extend Catalog? | **New section** in UI; new table in DB (no shared model). |
| Link to VizzHub project? | Yes, nullable FK `project_id`. UI dropdown picks from existing projects, auto-slugs from name. |
| Target path | Fixed: `CLAUDE.md` at project root. |
| Write/edit from DevStack UI? | **No.** Out of scope v1. Editors use the private repo directly. |
| Multiple private repos? | Schema supports it (`private_repo_url` per row), but v1 always uses the single monorepo. |
| Project-scoped permissions? | **No.** Trust-based; real gate is GitHub repo access. |

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Dev forgets to gitignore `CLAUDE.md` and commits it to the public repo | Skill enforces `.gitignore` entry on every sync. Also add to public-repo template/onboarding. |
| Slug collision between contexts | DB unique constraint on `slug`. UI validates on form submit. |
| Backend GitHub token loses access to `project-contexts` repo | MCP returns `FETCH_FAILED`. Skill surfaces a clear error to the dev. Ops monitors via structlog. |
| Two devs edit same `CLAUDE.md` concurrently | Normal git conflict in the private repo. Explicitly called out in skill instructions — not our problem. |
| Private content ends up in VizzHub logs | MCP tool response content is NOT logged (only SHA + slug). Review `structlog` setup for the new tool. |

## Roadmap

1. **v1** (this spec) — read-only, CLAUDE.md at project root, skill + MCP + UI.
2. **v2** (future) — per-project skills/commands distribution (extend folder layout, add a `devstack_list_project_artifacts` MCP tool).
3. **v3** (future, if needed) — write-path via MCP `approve_command` queue (same pattern as `iso_*`, `playbook_*`): `devstack_update_project_context(slug, content)` queues a commit to the private repo.
4. **v4** (future, if needed) — project-scoped permissions tied to VizzHub project membership.

## File locations

- Backend model: `app/modules/devstack/models/project_context.py`
- Backend service: `app/modules/devstack/services/project_context_service.py` (GitHub fetch + CRUD)
- Backend API: `app/modules/devstack/api/project_contexts.py`
- MCP tools: add to `app/mcp/tools/devstack.py`
- Frontend page: `frontend/src/modules/devstack/pages/ProjectContexts.tsx`
- Frontend form: `frontend/src/modules/devstack/components/ProjectContextForm.tsx`
- Frontend hook: `frontend/src/modules/devstack/hooks/useProjectContexts.ts`
- Frontend service: `frontend/src/modules/devstack/services/projectContexts.ts`
- Frontend types: `frontend/src/modules/devstack/types/projectContexts.ts`
- Migration: `backend/alembic/versions/xxxx_devstack_project_contexts.py` (revision ID ≤ 32 chars)
- Skill: `Vizzuality/claude-code-standards` → `skills/devstack-sync/SKILL.md` (new section)
- Docs: update `docs/devstack.md` with the new feature

## Success criteria

- Admin can register a project context through the UI in < 30 seconds (pick project → auto-slug → save).
- A dev starting a fresh checkout of a private project runs Claude once, answers the slug prompt, and the correct CLAUDE.md appears in their project root with zero additional setup.
- Two devs editing the same context a week apart see each other's changes via drift detection — no manual copy-paste.
- `CLAUDE.md` never appears in the public project's git history.
