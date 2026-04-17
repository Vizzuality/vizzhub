# DevStack Module — Specification

## Overview

DevStack manages and distributes developer environment configuration across the Vizzuality team (~30 developers). It handles Claude Code skills, commands, plugins, configs, and agents — ensuring every team member has a consistent, up-to-date environment without manual setup.

The org-level CLAUDE.md is deployed via Miradore (MDM) for initial bootstrap, then updated via MCP. Managed settings (hooks, permissions, env vars) are configured via the claude.ai org admin panel. DevStack focuses exclusively on the catalog of installable artifacts.

## Architecture

Three layers, each with a clear owner:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 1: Miradore (MDM) — bootstrap only                               │
│  Target: /Library/Application Support/ClaudeCode/CLAUDE.md              │
│  Purpose: initial deployment of org CLAUDE.md on new machines           │
│  After bootstrap: CLAUDE.md updated via MCP + devstack-sync             │
│  Status: VALIDATED                                                      │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 2: claude.ai org admin panel                                     │
│  Target: server-managed settings.json (propagates to all org members)   │
│  Manages: hooks, permissions, env vars                                  │
│  Enforcement: hard — user cannot override                               │
│  Status: VALIDATED                                                      │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────┐     ┌──────────────────────────────────┐
│  Layer 3: DevStack              │     │     Developer machine (local)    │
│  VizzHub (server-side)          │     │                                  │
│                                 │     │  /Library/App.../ClaudeCode/     │
│  DevStack catalog ←── VizzHub UI│     │    └── CLAUDE.md (org, managed)  │
│       (DB table)                │     │                                  │
│           │                     │     │  ~/.claude/                      │
│           ▼                     │     │    ├── skills/                    │
│  MCP tool (read-only)           │     │    ├── commands/                  │
│   • devstack_get_catalog        │     │    └── agents/                   │
│                                 │     │                                  │
│  Phase 2:                       │     │  Org CLAUDE.md instructs Claude: │
│   • devstack_list               │     │    "sync required entries, check │
│   • devstack_recommend          │     │     SHAs, report what's outdated"│
└─────────────────────────────────┘     └──────────────────────────────────┘
```

**Separation of concerns:**

| Layer | What it manages | How | Enforcement |
|-------|----------------|-----|-------------|
| **Miradore** | Org CLAUDE.md (bootstrap only) | MDM script → filesystem | Hard — initial deployment |
| **claude.ai admin** | settings.json (hooks, permissions, env vars) | Server-managed, auto-propagates | Hard — cannot override |
| **DevStack** | Skills, commands, agents, configs, plugins + org CLAUDE.md updates | MCP catalog + instructions in org CLAUDE.md | Soft — Claude follows instructions |

**Key principles:**
- The MCP tool is a read-only data provider. It returns the catalog with GitHub SHAs.
- No per-user state in VizzHub — sync tracking is purely local (SHA embedded in file frontmatter).
- The org CLAUDE.md is a catalog entry itself (`type: config`), kept up-to-date by the same sync mechanism.
- npm entries use `package_version` from the catalog for version comparison (no npm registry calls).

## Layer 1: Miradore — Bootstrap

Deploys the initial org CLAUDE.md to `/Library/Application Support/ClaudeCode/CLAUDE.md` on new machines. After bootstrap, the CLAUDE.md instructs Claude to keep itself updated via MCP.

**Miradore script (one-time):**

```bash
#!/bin/bash
DIR="/Library/Application Support/ClaudeCode"
mkdir -p "$DIR"
curl -sL "https://raw.githubusercontent.com/Vizzuality/devstack/main/org-claude.md" \
  -o "$DIR/CLAUDE.md"
```

**After bootstrap:** The org CLAUDE.md contains instructions for Claude to call `devstack_get_catalog`, compare SHAs, and update files — including the CLAUDE.md itself. Miradore does not need to run again.

## Layer 2: claude.ai Admin — Managed Settings

Hooks, permissions, and env vars are configured in the **claude.ai org admin panel** under "Managed settings (settings.json)". Settings propagate automatically to all org members.

**Current config:**

```json
{
  "attribution": {
    "commit": "",
    "pr": ""
  }
}
```

## Layer 3: DevStack — Artifact Catalog

### Data Model

Single table. No per-user state.

#### `devstack_entries` table

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `id` | UUID | PK | |
| `name` | varchar(100) | yes | Identifier, used as directory/file name when installing. Unique. |
| `description` | text | yes | Human-readable, shown in UI and returned by MCP |
| `type` | varchar(20) | yes | `skill`, `command`, `plugin`, `config`, `agent` |
| `install_method` | varchar(20) | yes | `github`, `npm` (extensible) |
| `url` | text | conditional | GitHub URL. Required when `install_method = github` |
| `package` | varchar(200) | conditional | npm package name. Required when `install_method = npm` |
| `package_version` | varchar(50) | no | Pinned version for npm packages. Used for version comparison during sync |
| `required` | boolean | yes | `true` = auto-installed on sync, `false` = installed on demand |
| `origin` | varchar(20) | yes | `internal` (Vizzuality-created) or `external` (third-party) |
| `tech` | jsonb | no | Array of technology tags (e.g. `["python", "fastapi"]`) |
| `active` | boolean | yes | Soft-delete / draft flag. Inactive entries not returned by MCP |
| `github_sha` | varchar(40) | no | SHA of the file in GitHub. Auto-fetched on create/edit for github entries. Used by sync to detect changes. |
| `created_by_id` | UUID FK | no | |
| `updated_by_id` | UUID FK | no | |
| `created_at` | timestamptz | auto | |
| `updated_at` | timestamptz | auto | |

#### GitHub SHA management

When a catalog entry with `install_method = github` is created or updated:
1. The backend calls the GitHub API to fetch the current SHA of the file at the given URL
2. Stores it in `github_sha`
3. The MCP catalog returns this SHA so the sync can compare

**SHA refresh:**
- **On create/edit** — automatic, at API endpoint level
- **Cron job** (Phase 2) — periodic worker that refreshes all github SHAs
- **Manual button** (Phase 2) — "Refresh SHAs" in the UI for immediate update after a push

For npm entries, `package_version` serves the same role — the admin updates it in the catalog when a new version should be distributed.

### MCP Tools

Read-only. Registered via `register_devstack_tools(server)`.

#### `devstack_get_catalog` (Phase 1 — implemented)

Returns all active entries from the catalog, including `github_sha` for change detection.

**Parameters:** none

**Returns:** JSON array of entries with `name`, `description`, `type`, `install_method`, `url`, `package`, `package_version`, `required`, `origin`, `tech`, `github_sha`.

#### `devstack_list` (Phase 2)

Lists all catalog entries grouped by type. Informational — for discovery.

**Parameters:** none

**Returns:** JSON grouped by type, each entry with `name`, `description`, `origin`, `required`, `tech`.

#### `devstack_recommend` (Phase 2)

Takes a technology stack and returns matching catalog entries.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `tech` | string[] | yes | Technology tags (e.g. `["python", "fastapi"]`) |

**Returns:** JSON array of matching entries ordered by tag overlap.

### Sync Mechanism

The sync is driven by instructions in the org CLAUDE.md — not a separate skill. Claude reads the instructions at session start and follows them.

#### How SHA comparison works

1. Claude calls `devstack_get_catalog` → gets entries with `github_sha`
2. For each locally installed file, Claude reads the frontmatter `devstack_sha` field
3. If `devstack_sha` matches `github_sha` → up to date, skip
4. If they differ or file doesn't exist → needs update
5. Claude reports: "These entries need updating: X, Y. Update?"
6. On install/update, Claude writes the file with `devstack_sha: <sha>` in the frontmatter

**Frontmatter SHA tracking (local, per file):**

```yaml
---
name: finalize
description: ...
devstack_sha: abc123def456
---
```

Claude Code ignores unknown frontmatter fields. The SHA travels with the file, no external state needed.

#### Sync behavior by entry type

| Type | Target path | SHA tracking |
|------|-------------|-------------|
| `skill` | `~/.claude/skills/{name}/SKILL.md` | frontmatter `devstack_sha` |
| `command` | `~/.claude/commands/{name}.md` | frontmatter `devstack_sha` |
| `agent` | `~/.claude/agents/{name}.md` | frontmatter `devstack_sha` |
| `config` | entry-specific (e.g. managed CLAUDE.md path) | frontmatter `devstack_sha` |
| `plugin` (npm) | npm global | compare `package_version` vs `npm list -g` |

#### Required vs on-demand

- `required: true` — auto-synced at session start (per org CLAUDE.md instruction)
- `required: false` — shown when developer asks "what's available?" via `devstack_list`. Installed on request.

### Tech Radar

Lives in GitHub at `Vizzuality/vizzuality-engineering-handbook/decisions/tech-radar/`. Referenced in the org CLAUDE.md as `gh api` commands:

```markdown
## Tech Radar

**You MUST consult the Tech Radar before suggesting any library, framework,
database, or tool.** Run:

`gh api repos/Vizzuality/vizzuality-engineering-handbook/contents/decisions/tech-radar/<file>.md --jq '.content' | base64 -d`

Files: `development.md`, `devops.md`, `tools-and-libraries.md`, `data-science-gis.md`.

- **Adopt** — use by default, no justification needed
- **Trial** — allowed in selected projects, flag it explicitly
- **Assess** — do not use in production, exploration only
- **Hold** — do not use in new projects under any circumstance

If a technology is not listed in the Tech Radar, flag it before proceeding.
```

### Org CLAUDE.md as catalog entry

The org CLAUDE.md itself is a catalog entry with `type: config`. This means:
- Its content lives in GitHub (`Vizzuality/devstack/org-claude.md`)
- VizzHub tracks its `github_sha`
- The sync instructions in the CLAUDE.md include updating itself
- Target path: `/Library/Application Support/ClaudeCode/CLAUDE.md` (needs write permission — tested, works if Miradore set up the directory)

### VizzHub UI

**Catalog** (`/devstack`) — admin-only for catalog management:
- Table of all entries with columns: name, type, install_method, required, origin, active
- Filter by type
- Add/edit/delete entries (admin only)
- Dialog form for creating/editing entries
- Phase 2: "Refresh SHAs" button

### Onboarding flow

```
1. Miradore deploys initial CLAUDE.md (automatic, on device setup)
2. claude.ai pushes managed settings.json (automatic, on org join)
3. Developer opens Claude Code → org CLAUDE.md active
4. Claude reads sync instructions → calls devstack_get_catalog
5. Installs required entries, reports status
6. Done — future updates detected automatically via SHA comparison
```

No bootstrap command needed. No manual steps beyond Miradore's initial deploy.

## Phases

### Phase 0 — Infrastructure setup (no code)

- Create GitHub repo `Vizzuality/devstack` with `org-claude.md`
- Create Miradore "application" script for initial deployment
- Deploy to all managed macOS devices
- Configure managed settings.json in claude.ai admin panel

### Phase 1 — Catalog + MCP (implemented)

- `devstack_entries` table + migration
- CRUD API for catalog entries (admin-only)
- MCP tool: `devstack_get_catalog` (read-only, returns all active entries)
- VizzHub UI: Catalog page (admin)
- Backend tests (9) + MCP tests (2)

### Phase 1.5 — SHA tracking (next)

- Add `github_sha` column to `devstack_entries`
- Auto-fetch SHA from GitHub API on entry create/edit
- Return `github_sha` in MCP catalog response
- Write sync instructions in org CLAUDE.md

### Phase 2 — Discovery + Maintenance

- MCP tools: `devstack_list`, `devstack_recommend`
- Cron job to refresh GitHub SHAs periodically
- "Refresh SHAs" button in UI
- `devstack_recommend` cross-references Tech Radar
- Orphan detection (local files not in catalog)

### Phase 3 — npm + Lifecycle

- npm install support in sync instructions (with user confirmation)
- Dry-run mode (show what would change without doing it)

## Validation Log

| Test | Result | Date |
|------|--------|------|
| Managed CLAUDE.md via Miradore → `/Library/Application Support/ClaudeCode/CLAUDE.md` | Passed | 2026-04-17 |
| Managed settings.json (hooks) via claude.ai admin panel | Passed | 2026-04-17 |
| Phase 1 implementation (catalog + API + MCP + UI) | Passed (11 tests) | 2026-04-17 |
| MCP `devstack_get_catalog` from production | Passed | 2026-04-17 |
| Fetch + install skill from private GitHub repo via `gh api` | Passed | 2026-04-17 |

## Open Questions

1. ~~**Managed settings.json coexistence**~~ — **Resolved.** Hooks/permissions go through claude.ai managed settings, CLAUDE.md goes through Miradore (bootstrap) then MCP (updates).

2. **GitHub auth for private repos** — `gh api` works with private repos if developer has `gh` authenticated. The org CLAUDE.md should verify `gh auth status` before attempting sync.

3. **Conflict with project CLAUDE.md** — The managed CLAUDE.md sets org-wide rules. Claude Code's built-in precedence applies (managed > project > user).

4. **Linux support** — Managed CLAUDE.md path on Linux is `/etc/claude-code/CLAUDE.md`. Sync instructions need OS detection.

5. **CLAUDE.md write permissions** — Claude Code needs write access to `/Library/Application Support/ClaudeCode/`. Works if Miradore created the directory with appropriate permissions. Needs testing on the laptop.
