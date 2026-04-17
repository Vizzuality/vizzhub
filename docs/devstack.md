# DevStack Module — Specification

## Overview

DevStack manages and distributes developer environment configuration across the Vizzuality team (~30 developers). It handles Claude Code skills, commands, plugins, configs, and agents — ensuring every team member has a consistent, up-to-date environment without manual setup.

The org-level CLAUDE.md is deployed via Miradore (MDM). Managed settings (hooks, permissions, env vars) are configured via the claude.ai org admin panel. DevStack focuses exclusively on the catalog of installable artifacts.

## Architecture

Three layers, each with a clear owner:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 1: Miradore (MDM)                                                │
│  Target: /Library/Application Support/ClaudeCode/CLAUDE.md              │
│  Manages: org instructions, Tech Radar, coding standards                │
│  Source of truth: GitHub repo (Vizzuality/devstack)                     │
│  Enforcement: hard — user cannot exclude                                │
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
│                                 │     │  ~/.claude/                      │
│  DevStack catalog ←── VizzHub UI│     │    ├── skills/                    │
│       (DB table)                │     │    ├── commands/                  │
│           │                     │     │    └── agents/                   │
│           ▼                     │     │                                  │
│  MCP tool (read-only)           │     │  Local skill: devstack-sync      │
│   • devstack_get_catalog        │     │    1. Calls MCP → get catalog    │
│                                 │     │    2. Fetches content from GitHub │
│  Phase 2:                       │     │    3. Writes files locally        │
│   • devstack_list               │     │    4. Reports summary            │
│   • devstack_recommend          │     │                                  │
└─────────────────────────────────┘     └──────────────────────────────────┘
```

**Separation of concerns:**

| Layer | What it manages | How | Enforcement |
|-------|----------------|-----|-------------|
| **Miradore** | Org CLAUDE.md (instructions, Tech Radar) | MDM script → filesystem | Hard — system-level, cannot exclude |
| **claude.ai admin** | settings.json (hooks, permissions, env vars) | Server-managed, auto-propagates | Hard — cannot override |
| **DevStack** | Skills, commands, agents, configs, plugins | MCP catalog + local skill | Soft — depends on user/Claude running sync |

**Key principle:** The MCP tool is a read-only data provider. It returns the catalog of available artifacts. The local skill (running inside Claude Code) handles all filesystem operations: downloading from GitHub, writing files, running npm commands. No per-user state is stored in VizzHub — sync tracking is purely local.

## Layer 1: Miradore — Org CLAUDE.md

Deployed to `/Library/Application Support/ClaudeCode/CLAUDE.md` via Miradore "Add application" script. Source of truth lives in a GitHub repo (`Vizzuality/devstack`).

### Content

The managed CLAUDE.md contains org-wide instructions that apply to every Claude Code session. Cannot be excluded by user settings.

**Includes:**
- Tech Radar instructions (MUST-level, with `gh api` commands to fetch on-demand)
- Instruction to run `devstack-sync` for local environment setup
- Org-wide coding standards, conventions, or policies

### Tech Radar

Lives in GitHub at `Vizzuality/vizzuality-engineering-handbook/decisions/tech-radar/`. Not downloaded, not synced. Referenced in the managed CLAUDE.md as `gh api` commands that Claude executes on-demand:

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

### Deployment

**Miradore script:**

```bash
#!/bin/bash
DIR="/Library/Application Support/ClaudeCode"
mkdir -p "$DIR"
curl -sL "https://raw.githubusercontent.com/Vizzuality/devstack/main/org-claude.md" \
  -o "$DIR/CLAUDE.md"
```

**Update flow:** Edit `org-claude.md` in GitHub via PR → merge → trigger Miradore deployment (manual push or scheduled).

## Layer 2: claude.ai Admin — Managed Settings

Hooks, permissions, and env vars are configured in the **claude.ai org admin panel** under "Managed settings (settings.json)". Settings propagate automatically to all org members — no MDM or local deployment needed.

**Current config:**

```json
{
  "attribution": {
    "commit": "",
    "pr": ""
  }
}
```

Future additions (hooks for DevStack sync, org-wide permissions, etc.) go here.

## Layer 3: DevStack — Artifact Catalog

### Data Model

Single table. No per-user state — sync tracking is local to each developer's machine.

#### `devstack_entries` table

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `id` | UUID | PK | |
| `name` | varchar(100) | yes | Identifier, used as directory/file name when installing. Unique. |
| `description` | text | yes | Human-readable, shown in UI and returned by MCP |
| `type` | varchar(20) | yes | `skill`, `command`, `plugin`, `config`, `agent` |
| `install_method` | varchar(20) | yes | `github`, `npm` (extensible — adding `pip` later is just a new case) |
| `url` | text | conditional | GitHub URL (raw file or directory). Required when `install_method = github` |
| `package` | varchar(200) | conditional | npm package name. Required when `install_method = npm` |
| `package_version` | varchar(50) | no | Pinned version for npm packages (e.g. `1.2.3`). If null, installs latest |
| `required` | boolean | yes | `true` = installed for everyone on sync, `false` = installed on demand |
| `origin` | varchar(20) | yes | `internal` (Vizzuality-created) or `external` (third-party) |
| `tech` | jsonb | no | Array of technology tags (e.g. `["python", "fastapi"]`) |
| `active` | boolean | yes | Soft-delete / draft flag. Inactive entries are not returned by MCP |
| `created_by_id` | UUID FK | no | |
| `updated_by_id` | UUID FK | no | |
| `created_at` | timestamptz | auto | |
| `updated_at` | timestamptz | auto | |

### MCP Tools

Read-only. Registered via `register_devstack_tools(server)` in `mcp_server/tools/devstack.py`, data access in `mcp_server/data/devstack.py`.

#### `devstack_get_catalog` (Phase 1 — implemented)

Returns all active entries from the catalog. Everything the local skill needs to perform a sync.

**Parameters:** none

**Returns:** JSON array of entries with `name`, `description`, `type`, `install_method`, `url`, `package`, `package_version`, `required`, `origin`, `tech`.

**Used by:** the local `devstack-sync` skill at sync time.

#### `devstack_list` (Phase 2)

Lists all catalog entries grouped by type. Informational — for discovery, not sync.

**Parameters:** none

**Returns:** JSON grouped by type, each entry with `name`, `description`, `origin`, `required`, `tech`.

#### `devstack_recommend` (Phase 2)

Takes a technology stack and returns matching catalog entries.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `tech` | string[] | yes | Technology tags (e.g. `["python", "fastapi"]`) |

**Returns:** JSON array of matching entries ordered by tag overlap, with `name`, `description`, `type`, `tech`, `required`.

Claude Code can call this automatically when it detects a project's stack (from `package.json`, `pyproject.toml`, etc.) and suggest relevant skills.

### Local Artifacts

These live in the GitHub repo (`Vizzuality/devstack`) and are the only artifacts that need manual bootstrap.

#### Skill: `devstack-sync`

Installed at `~/.claude/skills/devstack-sync.md`. This is the orchestrator.

**Behavior:**

1. Call `devstack_get_catalog` via MCP → receive the list of entries
2. For each `required: true` entry:
   - `install_method: github` → fetch content from `url` using `gh api` or `curl`, write to target directory
   - `install_method: npm` → run `npm install -g <package>@<version>` (ask user confirmation first)
3. Report summary: installed (new), updated, skipped, failed

For `required: false` entries, the developer asks Claude to install specific ones on demand — no automatic sync.

**Target directories by type:**

| Type | Target |
|------|--------|
| `skill` | `~/.claude/skills/` |
| `command` | `~/.claude/commands/` |
| `agent` | `~/.claude/agents/` |
| `config` | varies (entry-specific, encoded in catalog) |
| `plugin` | npm global |

**Error handling:**
- If VizzHub MCP is unreachable, log and stop — don't touch existing local files
- If a single GitHub download fails, skip it and continue with the rest
- Never block a Claude Code session from starting
- npm install failures are reported but don't stop the sync

**Invocation:**
- Manual: user runs `/devstack-sync` or asks Claude to sync their environment
- The managed CLAUDE.md instructs Claude to run the sync, but it's a soft instruction (Claude may skip it if the user goes straight to a task — this is acceptable)

#### Command: `devstack-init`

One-time bootstrap. Downloaded manually from the DevStack GitHub repo and placed in `~/.claude/commands/`.

**Steps:**

1. Authenticate with VizzHub via existing MCP OAuth flow (user is prompted to log in)
2. Install the `devstack-sync` skill from GitHub to `~/.claude/skills/`
3. Run the sync skill to complete initial setup

**Prerequisites:** Miradore has already deployed the managed CLAUDE.md (happens automatically for all managed devices). Managed settings.json is already active via claude.ai.

**Onboarding flow for a new developer:**

```
1. Miradore deploys managed CLAUDE.md (automatic, no user action)
2. claude.ai pushes managed settings.json (automatic, no user action)
3. Developer downloads devstack-init.md → ~/.claude/commands/
4. Opens Claude Code → org CLAUDE.md is already active
5. Runs /devstack-init → installs sync skill + runs first sync
6. Done — everything else is automatic from here
```

### VizzHub UI

New section in the VizzHub sidebar: **DevStack** (admin-only for catalog management).

**Catalog** (`/devstack`)
- Table of all entries with columns: name, type, install_method, required, origin, active
- Filter by type
- Add/edit/delete entries (admin only)
- Dialog form for creating/editing entries

### Cleanup & Lifecycle

#### Orphan detection

When `devstack-sync` runs, it compares:
- Files currently in `~/.claude/skills/`, `~/.claude/commands/`, `~/.claude/agents/`
- Entries in the catalog

Files that exist locally but are **not** in the catalog are flagged as orphans. The skill reports them but does **not** auto-delete — the user decides.

#### Deactivation

Setting `active: false` on a catalog entry removes it from all future syncs. Next time any user syncs, the entry will appear as an orphan. No remote-delete of user files.

## Phases

### Phase 0 — Infrastructure setup (no code)

- Create GitHub repo `Vizzuality/devstack` with `org-claude.md` (Tech Radar instructions, env_sync instruction, org standards)
- Create Miradore "application" script that fetches from GitHub and writes to `/Library/Application Support/ClaudeCode/CLAUDE.md`
- Deploy to all managed macOS devices
- Configure managed settings.json in claude.ai admin panel (hooks, permissions as needed)
- Write `devstack-init.md` command in the GitHub repo

### Phase 1 — Catalog + MCP (implemented)

- `devstack_entries` table + migration
- CRUD API for catalog entries (admin-only)
- MCP tool: `devstack_get_catalog` (read-only, returns all active entries)
- VizzHub UI: Catalog page (admin)
- Backend tests (9) + MCP tests (2)

### Phase 2 — Discovery

- MCP tools: `devstack_list`, `devstack_recommend`
- `devstack_recommend` cross-references Tech Radar (if a recommended entry's tech tags include something in Hold, flag it)
- Orphan detection in `devstack-sync`

### Phase 3 — npm + Lifecycle

- npm install support in `devstack-sync` (with user confirmation)
- `package_version` pinning
- Dry-run mode for `devstack-sync` (show what would change without doing it)

## Validation Log

| Test | Result | Date |
|------|--------|------|
| Managed CLAUDE.md via Miradore → `/Library/Application Support/ClaudeCode/CLAUDE.md` | Passed | 2026-04-17 |
| Managed settings.json (hooks) via claude.ai admin panel | Passed | 2026-04-17 |
| Phase 1 implementation (catalog + API + MCP + UI) | Passed (11 tests) | 2026-04-17 |

## Open Questions

1. ~~**Managed settings.json coexistence**~~ — **Resolved.** Hooks/permissions go through claude.ai managed settings (server-managed), CLAUDE.md goes through Miradore (endpoint-managed). No conflict — each manages a different file type.

2. **GitHub auth for private repos** — If the DevStack repo or any skill repo is private, `gh api` needs authentication. Most Vizzuality devs should have `gh` configured, but the bootstrap command should verify this.

3. **Conflict with project CLAUDE.md** — The managed CLAUDE.md sets org-wide rules. Project CLAUDE.md files may have conflicting instructions. Claude Code's built-in precedence applies (managed > project > user). Document this clearly in the org CLAUDE.md itself.

4. **Linux support** — Managed CLAUDE.md path on Linux is `/etc/claude-code/CLAUDE.md`. If any team members use Linux, Miradore scripts need a variant or the script needs OS detection.
