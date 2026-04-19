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
    slug: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    # [a-z0-9-]+, used as folder name in the private repo and client-side identifier.
    # UNIQUE NOT NULL. Immutable after creation (see API contract).

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    # NOT NULL in v1 — the UI always requires picking from the Projects dropdown.
    # RESTRICT on delete: deleting a project with an active context must fail loudly,
    # forcing the admin to delete the context first.

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at, updated_at: timestamps
```

**Kept out of the model in v1** (were in the earlier draft):

- `private_repo_url` → backend config constant `DEVSTACK_PROJECT_CONTEXTS_REPO` (e.g. `git@github.com:Vizzuality/project-contexts.git`). One private repo org-wide.
- `folder_path` → always derived from `slug` (folder == slug). If multi-repo or decoupled folders ever become a real requirement, columns can be added then without breaking existing rows.

**Single source of slug uniqueness**: `slug` is globally unique. We do NOT allow two contexts for the same project (enforced at the API layer — no DB-level unique on `project_id` so the data model still permits future relaxation).

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

One folder per registered context. Folder name == `slug`. Only `CLAUDE.md` is read by DevStack in v1 — other files in the folder are ignored (leaves room for future per-project skills).

Backend accesses this repo via the existing GitHub service token (same one used by the catalog's `devstack_get_installable`) and the repo URL in the `DEVSTACK_PROJECT_CONTEXTS_REPO` config setting. The token must have read access to `Vizzuality/project-contexts`.

### Backend API

New REST router under `/api/devstack/project-contexts` (mounted via `app/modules/devstack/router.py`):

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| `GET`  | `""` | `DEVSTACK_VIEW` | List all contexts (slug, project_id, description, project_name via join) |
| `POST` | `""` | `DEVSTACK_MANAGE` | Create — body: `project_id`, `slug`, `description`. Rejects if `project_id` already has a context or `slug` collides. |
| `GET`  | `/{id}` | `DEVSTACK_VIEW` | Detail |
| `PUT`  | `/{id}` | `DEVSTACK_MANAGE` | Update — only `description` is editable. Any attempt to change `slug` or `project_id` returns HTTP 400. |
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

#### Marker files

The skill uses **two** gitignored marker files under `.claude/` in the project root. Their mere presence disambiguates the three possible states — no content-parsing heuristics, no silent typos:

- **`.claude/.devstack-context`** — present if the project is linked to a DevStack context. Simple key/value format:

  ```
  slug: acme-corp
  sha: abc123def456...
  ```

  `slug` is written once on linking. `sha` is updated on every successful sync (see drift check below).

- **`.claude/.devstack-skip`** — present if the dev has explicitly declared this project has no private context. Content is irrelevant (may be empty or carry a timestamp for debugging). Its presence alone suppresses future prompts.

Both files are added to `.gitignore` by the skill on creation.

Rationale: two orthogonal files eliminate semantic ambiguity between "not configured yet", "explicitly skipped", and "linked" — the three states are presence-checked, not inferred from file contents. Removes a class of silent bugs from typos in a single status file.

#### Session-start logic

1. **Dispatch on markers**:
   - If `.claude/.devstack-context` exists → parse `slug` + `sha`, continue to step 2.
   - Else if `.claude/.devstack-skip` exists → no-op, silent exit.
   - Else (neither file exists) → ask the dev **once**: *"This project has no DevStack context linked. Is there a private context? Reply with the slug (e.g. `acme-corp`) or `N` to skip."* Then:
     - If slug → create `.claude/.devstack-context` with `slug: <slug>` (no `sha` yet), ensure it's in `.gitignore`, continue to step 2.
     - If `N` → create `.claude/.devstack-skip`, ensure it's in `.gitignore`, silent exit.

2. **Fetch content**: call `devstack_get_project_context(slug)`.
   - On success: receives `{content, devstack_sha}`.
   - On `NOT_FOUND`: warn the dev *"The context '<slug>' is no longer registered in VizzHub. Your local `./CLAUDE.md` may be stale. Ask me to unlink this project if it no longer applies."* — do **not** delete `./CLAUDE.md`. Exit.
   - On `FETCH_FAILED` / other: surface error, exit.

3. **Drift check**: compare `devstack_sha` against the `sha:` line in `.claude/.devstack-context`. If equal → exit silently. If different (or absent) → go to step 4.

4. **Atomic write**: write `content` to a tempfile in the same directory as `./CLAUDE.md` (e.g. `.CLAUDE.md.<pid>.tmp`), then `rename` over `./CLAUDE.md`. POSIX rename within the same filesystem is atomic, preventing truncated reads if a second Claude session (terminal + IDE, etc.) races the sync. The `CLAUDE.md` file itself carries **only content** — no SHA marker inside — so a dev's local edit can never silently corrupt the drift-detection state.

5. **Update marker**: rewrite `.claude/.devstack-context` with the new `sha: <devstack_sha>`.

6. **Gitignore check**: ensure `CLAUDE.md`, `.claude/.devstack-context`, and `.claude/.devstack-skip` are all present in the project's `.gitignore`. Append any missing entries and alert the dev: *"Added `CLAUDE.md` to `.gitignore` — this file contains private instructions and must not be committed to the public repo."*

#### Linking / unlinking after initial setup

No formal slash command is introduced. The skill documents that the dev can ask Claude in natural language:

- **Link / re-link** (e.g. *"vincula este proyecto al contexto acme-corp"* / *"link this project to the acme-corp context"*): Claude deletes `.claude/.devstack-skip` if present, writes `slug: acme-corp` to `.claude/.devstack-context`, and triggers a sync.
- **Unlink** (e.g. *"desvincula este proyecto de DevStack"* / *"unlink this project"*): Claude deletes `.claude/.devstack-context` and `./CLAUDE.md`, creates `.claude/.devstack-skip`. Explicit, reversible.

Both flows are plain file operations — no new MCP tools, no new commands.

#### Composition with the personal CLAUDE.md

The `./CLAUDE.md` synced by DevStack composes with any personal CLAUDE.md the dev may have (`~/.claude/CLAUDE.md`) via Claude Code's native resolution — both apply simultaneously with no interference from this feature. The DevStack sync only touches the project-root `CLAUDE.md`.

#### Editing

The skill tells the dev: *"To edit: clone `Vizzuality/project-contexts` anywhere you like, edit `<slug>/CLAUDE.md`, commit, push. Your team will see the change on their next session via drift detection. Conflicts are resolved via normal git workflow."* No convention on clone location — not our problem.

**MUST-opcional semantics**: the whole section is a no-op for projects without `.claude/.devstack-context`. Zero friction for non-private projects.

### Frontend

New page `/devstack/contexts` under the existing `DevStack` sidebar entry. Sidebar gets two sub-entries: "Catalog" (existing `/devstack`) and "Project Contexts" (new).

**List page**: table with columns `Project`, `Slug`, `Description`, `Actions` (Edit/Delete for `DEVSTACK_MANAGE`). Gated client-side with `usePermission(Action.DEVSTACK_MANAGE)` per the permission-gating rule in `CLAUDE.md` §8.

**Create/Edit form**:

- **Project dropdown**: searchable Combobox listing existing VizzHub projects (uses existing `useProjects` hook). On selection, auto-generates slug from project name via `slugify(name)` (lowercase, hyphens, strip diacritics, `[a-z0-9-]+` only). Admin can override the auto-slug at creation; regex-validated client-side, collision-checked against the API before submit.
- **Description**: free text.

The edit form disables the `slug` field and the `project_id` dropdown entirely, with a tooltip: *"Slug and project are immutable after creation. To rename, delete this context and recreate it."* Only `description` is editable post-creation.

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
        ├─ Neither .claude/.devstack-context nor .devstack-skip exist
        ├─ Skill asks once: "Private context slug, or N to skip?"
        ├─ Dev: "acme-corp"
        ├─ Skill writes .claude/.devstack-context (slug line only, no sha yet)
        ├─ Skill ensures .gitignore has CLAUDE.md, .claude/.devstack-context,
        │   and .claude/.devstack-skip
        ├─ Skill calls devstack_get_project_context("acme-corp")
        │   └─ Backend fetches Vizzuality/project-contexts/acme-corp/CLAUDE.md
        │       via GitHub API → returns {content, devstack_sha}
        ├─ Skill atomically writes ./CLAUDE.md (tempfile + rename)
        └─ Skill updates .claude/.devstack-context with sha: <devstack_sha>

Subsequent sessions:
  └─ .claude/.devstack-context exists → skill reads slug + local sha
     └─ MCP returns current devstack_sha
        └─ equal → no-op, silent
        └─ different → atomic rewrite + update marker

Dev edits CLAUDE.md through whatever workflow they prefer:
  Option 1: GitHub web UI on the private repo
  Option 2: Clone private repo somewhere (~/whatever), edit, commit, push
  → either way, next session any team member sees the update via SHA mismatch

Dev unlinks (natural language: "unlink this project from DevStack"):
  ├─ Claude deletes .claude/.devstack-context and ./CLAUDE.md
  └─ Claude creates .claude/.devstack-skip → future sessions silent
```

## Open questions resolved during brainstorming

| Question | Resolution |
|----------|------------|
| Local clone required? | **No.** Backend fetches content via GitHub API. Only editors clone, wherever they want. |
| Slug detection | **Two marker files**: `.claude/.devstack-context` (linked) and `.claude/.devstack-skip` (opted out). Dev is asked exactly once when neither exists. |
| SHA storage | **Outside CLAUDE.md**, stored alongside slug in `.claude/.devstack-context`. Keeps `CLAUDE.md` content-only and immune to accidental local edits corrupting drift state. |
| Mutability of slug | **Immutable after creation**. API rejects changes (HTTP 400); UI disables the field in edit mode. Rename == delete + recreate. |
| New section or extend Catalog? | **New section** in UI; new table in DB (no shared model). |
| Link to VizzHub project? | Yes, **NOT NULL** FK `project_id`. UI dropdown picks from existing projects, auto-slugs from name. |
| Target path | Fixed: `CLAUDE.md` at project root. |
| Write/edit from DevStack UI? | **No.** Out of scope v1. Editors use the private repo directly. |
| Multiple private repos? | **Removed from v1 model.** Single repo URL lives in backend config (`DEVSTACK_PROJECT_CONTEXTS_REPO`). Columns can be added later if a concrete need appears. |
| Project-scoped permissions? | **No.** Trust-based; real gate is GitHub repo access. |
| Behaviour when context is deleted in VizzHub | Skill warns the dev on next sync (MCP returns `NOT_FOUND`) but does **not** delete the local `./CLAUDE.md`. Dev chooses to unlink explicitly. |

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Dev forgets to gitignore `CLAUDE.md` and commits it to the public repo | Skill enforces `.gitignore` entry on every sync. Also add to public-repo template/onboarding. |
| Slug collision between contexts | DB unique constraint on `slug`. UI validates on form submit. |
| Backend GitHub token loses access to `project-contexts` repo | MCP returns `FETCH_FAILED`. Skill surfaces a clear error to the dev. Ops monitors via structlog. |
| Two devs edit same `CLAUDE.md` concurrently | Normal git conflict in the private repo. Explicitly called out in skill instructions — not our problem. |
| Private content ends up in VizzHub logs | MCP tool response content is NOT logged (only SHA + slug). Enforced by: (1) an integration test that drives a `devstack_get_project_context` call through the MCP layer and asserts the returned `content` substring does not appear in captured `structlog` output; (2) an explicit review of the Sentry/APM configuration to confirm response bodies from `/api/devstack/project-contexts/*` and the MCP endpoint are excluded from breadcrumbs and error payloads. |
| Concurrent Claude sessions (terminal + IDE) racing the CLAUDE.md write | Skill uses tempfile + `os.rename` for the write (atomic on POSIX within the same filesystem). Worst case: one session's content wins, neither leaves a truncated file. |

## Roadmap

1. **v1** (this spec) — read-only, CLAUDE.md at project root, skill + MCP + UI.
2. **v2** (future) — per-project skills/commands distribution (extend folder layout, add a `devstack_list_project_artifacts` MCP tool).
3. **v3** (future, if needed) — write-path via MCP `approve_command` queue (same pattern as `iso_*`, `playbook_*`): `devstack_update_project_context(slug, content)` queues a commit to the private repo.
4. **v4** (future, if needed) — project-scoped permissions tied to VizzHub project membership.

## File locations

- Backend config: add `DEVSTACK_PROJECT_CONTEXTS_REPO` to `app/config.py` (default `git@github.com:Vizzuality/project-contexts.git`)
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
- A dev starting a fresh checkout of a private project runs Claude once, answers the one-time prompt, and the correct `CLAUDE.md` appears in their project root with zero additional setup.
- Two devs editing the same context a week apart see each other's changes via drift detection — no manual copy-paste.
- After a dev opts out (`N` at the prompt) the skill never prompts again for that project on any subsequent session.
- `CLAUDE.md` never appears in the public project's git history.
- The integration test for the content-vs-logs risk passes in CI, proving private content cannot leak via `structlog`.
