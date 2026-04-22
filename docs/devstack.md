# DevStack Module — Specification

## Overview

DevStack manages and distributes developer environment configuration across the Vizzuality team (~30 developers). It handles Claude Code skills, commands, plugins, configs, and agents — ensuring every team member has a consistent, up-to-date environment without manual setup.

The org-level CLAUDE.md is deployed via Miradore (MDM) for initial bootstrap, then updated via MCP. Managed settings (hooks, permissions, env vars) are configured via the claude.ai org admin panel. DevStack focuses exclusively on the catalog of installable artifacts.

> **Looking for the operational guide?** See [`devstack-onboarding.md`](./devstack-onboarding.md) — admin deployment via Miradore, what lands on each dev's Mac, the session-start flow, and how per-project private CLAUDE.md sync works. This document is the design spec; the onboarding guide covers day-to-day usage.

## Architecture

Two layers, each with a clear owner:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 1: Miradore (MDM) — bootstrap only                               │
│  Target: /Library/Application Support/ClaudeCode/CLAUDE.md              │
│  Purpose: initial deployment of org CLAUDE.md on new machines           │
│  After bootstrap: CLAUDE.md updated via MCP + devstack-sync             │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────┐     ┌──────────────────────────────────┐
│  Layer 2: DevStack              │     │     Developer machine (local)    │
│  VizzHub (server-side)          │     │                                  │
│                                 │     │  /Library/App.../ClaudeCode/     │
│  DevStack catalog ←── VizzHub UI│     │    └── CLAUDE.md (org, managed)  │
│       (DB table)                │     │                                  │
│           │                     │     │  ~/.claude/                      │
│           ▼                     │     │    ├── skills/                   │
│  MCP tools (read-only)          │     │    ├── commands/                 │
│   • devstack_get_catalog        │     │    └── agents/                   │
│   • devstack_get_tech_radar     │     │                                  │
│   • devstack_get_installable    │     │  The dev invokes the devstack-   │
│   • devstack_discover           │     │  sync skill on demand to detect  │
│                                 │     │  drift and install updates.      │
└─────────────────────────────────┘     └──────────────────────────────────┘
```

**Separation of concerns:**

| Layer | What it manages | How | Enforcement |
|-------|----------------|-----|-------------|
| **Miradore** | Org CLAUDE.md (bootstrap only) | MDM script → filesystem | Hard — initial deployment |
| **DevStack** | Skills, commands, agents, npm packages, Tech Radar | MCP catalog + on-demand `devstack-sync` skill | Soft — dev triggers sync |

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
curl -sL "https://raw.githubusercontent.com/Vizzuality/claude-code-standards/main/Settings/managed/CLAUDE.md" \
  -o "$DIR/CLAUDE.md"
```

**After bootstrap:** The org CLAUDE.md contains instructions for Claude to call `devstack_get_catalog`, compare SHAs, and update files — including the CLAUDE.md itself. Miradore does not need to run again.

## Layer 2: DevStack — Artifact Catalog

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

Full catalog dump, for sync and install flows.

**Parameters:** none

**Returns:** JSON array of entries with `name`, `description`, `type`, `install_method`, `url`, `package`, `package_version`, `latest_package_version`, `required`, `origin`, `tech`, `github_sha`, `featured`.

#### `devstack_discover` (implemented)

Lightweight catalog view optimized for LLM consumption — answers "what skills/agents/commands are available?". Returns only `name`, `type`, `description` to minimize context.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `type` | enum | no | One of `skill`, `command`, `plugin`, `config`, `agent`. Omit for all types. |
| `tech` | string[] | no | Tech tags (any-match). E.g. `["python"]`. |
| `featured_only` | bool | no | If true, only entries flagged `featured`. Default false. |

**Returns:** JSON array ordered by `featured desc, required desc, name asc`. Fields: `name`, `type`, `description`.

#### `devstack_get_tech_radar(file)` (implemented)

Fetches a Tech Radar markdown file via the backend's GitHub token — removes the per-user `gh auth` dependency.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | enum | yes | One of `development`, `devops`, `tools-and-libraries`, `data-science-gis` (no `.md`). |

**Returns:** Raw markdown content. Error JSON if fetch fails.

#### `devstack_get_installable(name)` (implemented)

Returns a ready-to-write installable for a catalog entry. Backend fetches the source from GitHub, injects `devstack_sha` into the YAML frontmatter, and returns `{target_path, content}`. Claude writes verbatim — no client-side frontmatter composition.

Supports only `github`-installed `skill` / `command` / `agent` entries. Target paths:
- `skill` → `~/.claude/skills/{name}/SKILL.md`
- `command` → `~/.claude/commands/{name}.md`
- `agent` → `~/.claude/agents/{name}.md`

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `name` | string | yes | Catalog entry name (unique). |

**Returns on success:** `{"target_path": "...", "content": "..."}`.

**Returns on error:** `{"error": "...", "code": "..."}` where `code` is one of:

| Code | Meaning |
|------|---------|
| `NOT_FOUND` | Entry missing or inactive. |
| `UNSUPPORTED_TYPE` | Type is not `skill`/`command`/`agent` (e.g. `plugin`, `config`). |
| `NO_GITHUB_URL` | Entry not installed via `github`. |
| `NO_SHA` | `github_sha` not populated yet — catalog refresh pending. |
| `FETCH_FAILED` | Could not fetch source from GitHub. |

#### `devstack_recommend` (future)

Takes a technology stack and returns matching catalog entries ordered by tag overlap. Currently covered in part by `devstack_discover(tech=...)` — the `recommend` variant would add weighting.

### Sync Mechanism

The sync is driven by instructions in the org CLAUDE.md — not a separate skill. Claude reads the instructions at session start and follows them.

#### How SHA comparison works

1. Claude calls `devstack_get_catalog` → gets entries with `github_sha`
2. For each locally installed file, Claude reads the frontmatter `devstack_sha` field
3. If `devstack_sha` matches `github_sha` → up to date, skip
4. If they differ or file doesn't exist → needs update
5. Claude reports: "These entries need updating: X, Y. Update?"
6. On install/update of `skill`/`command`/`agent`: Claude calls `devstack_get_installable(name)` and writes the returned `content` to the returned `target_path` verbatim — the sha is injected server-side.

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

#### Sync instructions (org CLAUDE.md template)

The instructions below are the canonical contract Claude Code follows at session start. They live in `Vizzuality/claude-code-standards/Settings/managed/CLAUDE.md` and are deployed via Miradore to `/Library/Application Support/ClaudeCode/CLAUDE.md`. Keep the three locations (this doc, the repo, and the Miradore installer heredoc) in sync on every change.

See `Vizzuality/claude-code-standards/Settings/managed/CLAUDE.md` for the live version. The key mechanics:

- **Tech Radar** — call `devstack_get_tech_radar(file)` (no per-user `gh auth` needed).
- **Catalog** — call `devstack_get_catalog` to detect drift (compare frontmatter `devstack_sha` vs catalog `github_sha`).
- **Install / update** — for `skill`/`command`/`agent`, call `devstack_get_installable(name)` and write the returned `content` to `target_path` verbatim. The sha is injected server-side.
- **Discovery** — `devstack_discover(type?, tech?, featured_only?)` for "what's available?" questions.
- **Lifecycle warnings (pending)** — the sync contract does NOT yet alert the user when an entry is `deprecated: true` or has `vulnerabilities.critical/high > 0`. This is planned as part of the "extract to skill" work (roadmap item 7–8 below) so we can iterate on the warning text without re-deploying Miradore.
- **Managed CLAUDE.md** — Miradore-owned; on drift report and ask to re-run Miradore, do not auto-update.

> **Planned refactor:** the canonical home for these instructions will move from the managed CLAUDE.md to a dedicated skill distributed via DevStack Sync. The managed CLAUDE.md will shrink to a minimal pointer. See roadmap item 7 for the reasoning and mechanics.

### Tech Radar

Lives in GitHub at `Vizzuality/vizzuality-engineering-handbook/decisions/tech-radar/`. Exposed to Claude Code via the MCP tool `devstack_get_tech_radar(file)` — the backend holds the GitHub token, so no per-user `gh auth` is needed. The org CLAUDE.md directs Claude to the MCP call and spells out the mandatory tier interpretation (Adopt/Trial/Assess/Hold).

### Org CLAUDE.md as catalog entry

The org CLAUDE.md itself is a catalog entry with `type: config`. This means:
- Its content lives in GitHub (`Vizzuality/claude-code-standards/Settings/managed/CLAUDE.md`)
- VizzHub tracks its `github_sha`
- The sync instructions in the CLAUDE.md include updating itself
- Target path: `/Library/Application Support/ClaudeCode/CLAUDE.md` (Miradore installs the directory + file at bootstrap; sync owns it afterwards)

### Drift detection — self-healing via Sync

No write-time enforcement in v1. DevStack Sync is responsible for detecting and fixing drift:

1. At session start, Claude calls `devstack_get_catalog` → has each entry's `github_sha`.
2. For each required entry, Claude reads the local frontmatter `devstack_sha`.
3. Missing or different → treated as drift → Claude offers to reinstall.

This makes the system **self-healing within a session boundary**: drift introduced by any mechanism (direct edit, `Bash cat`, forgotten sha on install) is detected and corrected the next time Claude Code opens. A write-time hook was piloted and rolled back (see Backlog below for the reasoning and the path forward).

### Distribution via Miradore

One-time bootstrap installs CLAUDE.md. After that, DevStack Sync (inside Claude Code) owns CLAUDE.md updates.

**Files in `Settings/managed/` (in `claude-code-standards`)**:

| File | Purpose |
|---|---|
| `CLAUDE.md` | Managed org CLAUDE.md content |
| `miradore-bootstrap-claudemd.sh` | Bootstrap: writes CLAUDE.md with correct perms |
| `miradore-installer.sh` | **This is what you paste into Miradore.** Writes the bootstrap to `/usr/local/bin/vizz-bootstrap-claude.sh` and runs it once |

**Miradore Application type**: **Script** (not `.pkg` — this Miradore instance runs files directly instead of invoking `/usr/sbin/installer`, so pkgs never install).

**CRLF gotcha (critical)**: Miradore's admin textarea is hosted on Windows and copy-paste from browsers routinely converts LF → CRLF. The macOS kernel then refuses to exec the script (`Exec format error`), even though the file has a valid shebang. **Always paste into VSCode (force LF indicator bottom-right)** and copy from there into Miradore — this normalises line endings before they reach the textarea.

**Managed settings.json** (claude.ai admin panel → Settings → Managed): **unchanged** for v1. Just keep what you already had. Hook activation comes back in a later phase with a warn-only variant.

**Prerequisite on each dev**: `gh auth login` must be done. Tech Radar and DevStack skill sources live in private repos. This dependency will be removed when `devstack_get_tech_radar` (backlog) serves Tech Radar via the backend token.

### VizzHub UI

**Catalog** (`/devstack`) — admin-only for catalog management:
- Table of all entries with columns: name, type, install_method, required, origin, active
- Filter by type
- Add/edit/delete entries (admin only)
- Dialog form for creating/editing entries
- Phase 2: "Refresh SHAs" button

### Onboarding flow

```
1. Miradore runs Application (Script, pasted via VSCode to preserve LF)
   → writes /usr/local/bin/vizz-bootstrap-claude.sh
   → runs it → writes CLAUDE.md to /Library/Application Support/ClaudeCode/
2. Developer has `gh auth login` done (Vizzuality onboarding checklist item).
3. Developer opens Claude Code → managed CLAUDE.md active.
4. Claude reads sync instructions → calls devstack_get_catalog (MCP).
5. For each required entry with drift, Claude installs via gh api + Write
   (injecting devstack_sha client-side per the sync contract).
6. Done — future drift detected automatically via SHA comparison on next
   session. No write-time enforcement in v1.
```

No bootstrap command needed on the developer side. Admin-side steps are documented in `Settings/managed/README.md` of the `claude-code-standards` repo.

## Phases

### Phase 0 — Infrastructure setup (no code)

- Add `Settings/managed/CLAUDE.md` + bootstrap/installer scripts to `Vizzuality/claude-code-standards`
- Create Miradore Application (Script type) pasting `miradore-installer.sh` via VSCode
- Deploy to all managed macOS devices
- (Optional) Keep managed `settings.json` in claude.ai admin panel — no hook wiring in v1

### Phase 1 — Catalog + MCP (implemented)

- `devstack_entries` table + migration
- CRUD API for catalog entries (admin-only)
- MCP tool: `devstack_get_catalog` (read-only, returns all active entries)
- VizzHub UI: Catalog page (admin)
- Backend tests (9) + MCP tests (2)

### Phase 1.5 — SHA tracking (shipped)

- `github_sha` column on `devstack_entries`
- Auto-fetch SHA from GitHub API on entry create/edit
- `github_sha` returned in MCP catalog response
- Initial sync instructions in the managed org CLAUDE.md

### Phase 2 — Discovery + Maintenance (shipped)

- MCP tools: `devstack_discover(type, tech, featured_only)` (replaced the earlier `devstack_list` idea), `devstack_get_tech_radar(file)`, `devstack_get_installable(name)`
- Daily cron `refresh_devstack_sources` to refresh GitHub SHAs + npm `latest_package_version`
- "Refresh SHAs" button in the admin UI
- `DEVSTACK_VIEW` permission granted to the `user` role → discovery + catalog tools callable by any authenticated dev
- Managed org CLAUDE.md updated to use `devstack_get_installable` for writes (Miradore re-deployed 2026-04-18)
- Orphan detection — **dropped** on 2026-04-19 (see Roadmap § "Dropped")

### Phase 3 — Lifecycle signals (shipped 2026-04-19)

- `install_count`, `last_installed_at`, `deprecated`, `deprecation_message`, `vulnerabilities` on `devstack_entries`.
- Daily cron (`refresh_devstack_sources`) pulls deprecation from the npm registry and advisories from the GitHub Advisory DB for every npm entry.
- MCP `devstack_get_installable` bumps `install_count` via fire-and-log direct write (see `docs/mcp.md` § "Direct-Write Exception: Telemetry").
- Frontend surfaces badges on EntryCard (critical/high/deprecated) and Security / Deprecation / Stats sections on EntryDetail. Sort by "Most installed" available.

### Phase 4 — Sync instructions as a skill (shipped)

The full sync/discovery/lifecycle protocol lives in the `devstack-sync` skill (`Vizzuality/claude-code-standards/Skills/devstack-sync.md`), distributed as a catalog entry. The managed CLAUDE.md stays minimal — Tech Radar rule + a pointer to DevStack MCP tools + escalation boilerplate.

The skill is invoked **on demand** (e.g. *"sync the devstack catalog"*, *"what skills are available for X?"*) — there is no SessionStart hook forcing it. See "Why the SessionStart hook was dropped" below.

### Roadmap — what's next after v1 rollout

Ordered by priority. All items move reliability/ergonomics from "Claude follows text instructions" to "backend provides data atomically" or "UX has no friction".

**Done**

1. ~~**`devstack_get_tech_radar(file)`**~~ — shipped. Removes per-user `gh auth login` prerequisite for Tech Radar consultation. Accepts `development` | `devops` | `tools-and-libraries` | `data-science-gis`.
2. ~~**`devstack_discover(type, tech, featured_only)`**~~ — shipped. Lightweight dev-facing view returning only `name`, `type`, `description`. Replaces the Phase 2 `devstack_list` idea.
3. ~~**`DEVSTACK_VIEW` added to `user` role**~~ — catalog and discovery tools now callable by any authenticated dev.
4. ~~**`devstack_get_installable(name)`**~~ — shipped. Backend injects `devstack_sha` into frontmatter and returns `{target_path, content}`. Removes the main failure mode of the sync contract.
5. ~~**Update org CLAUDE.md**~~ — shipped. Sync contract now uses `devstack_get_installable` and `devstack_get_tech_radar` throughout. Miradore re-deployed 2026-04-18.
6. ~~**npm lifecycle + install metrics**~~ — shipped 2026-04-19. See "Phase 3" above.

**Dropped**

- **SessionStart hook** (2026-04-22). Re-ran `devstack-sync` on every session start / resume / clear. Automatic project-context sync, auto-catalog-sync, and auto-skill-install all hit the "too intrusive" bar. Skill is now invoked on demand. See "Why the SessionStart hook was dropped" below.
- **Per-project private context sync** (2026-04-22). Dropped together with the hook — without a session-start pull trigger the remaining push-on-demand flow wasn't worth the surface area. Private project CLAUDE.md files now live wherever the team chooses (local, separate repo), outside DevStack.
- **Hook v2 (warn-only PreToolUse)** (2026-04-19). Self-healing via Sync already handles drift in practice.
- **Orphan detection in sync** (2026-04-19). Same reasoning.

**Later**

7. **Surface deprecated / vulnerable warnings to the user** — today the data flows to the UI but the skill does NOT instruct Claude to warn the user when a catalog entry is flagged `deprecated: true` or has `vulnerabilities.critical > 0 || high > 0`. Add to the skill: on any catalog drift report, surface lifecycle warnings once per session with advisory IDs / deprecation message.
8. **`devstack_recommend`** — weighted tech-match ranking. Needs popularity signal interpretation, not just the raw `install_count` we now expose. Worth revisiting once we have a few weeks of real install data.
9. **Dry-run mode for sync** — show what would change without applying. Low priority; sync is already self-healing and the user confirms before installs.
10. **npm install lifecycle for `claude_plugin` type** — today we track `latest_package_version` + deprecation + CVEs but don't offer to install/upgrade plugins from MCP. Plugins have their own lifecycle (managed by the user via `npx claude-plugins install`). Worth exploring if admins want an install button from the catalog.

### Why the PreToolUse hook was dropped

We piloted a strict PreToolUse hook during the 2026-04-18 distribution validation. Shipped, debugged, deployed end-to-end. Then rolled back before group rollout for these reasons:

- **Weak enforcement**: the hook only checked that `devstack_sha:` was present and non-empty. It did not verify the value matched the catalog. Claude could write `devstack_sha: WRONG` and pass.
- **High friction on non-catalog skills**: any dev experimenting with a skill from outside Vizzuality's catalog was blocked on the first write, forcing them to add `devstack_sha: local` manually.
- **Partial coverage**: only the `Write` tool was intercepted. `Edit`, `MultiEdit`, and `Bash` (`cat > file`) all bypassed the hook silently.
- **Redundant with Sync**: DevStack Sync already detects drift (missing or wrong sha → reinstall next session). The hook only shortened the drift window within a session, at the cost of all of the above.

### Why the SessionStart hook was dropped (2026-04-22)

The `SessionStart` hook that auto-invoked `devstack-sync` on every session start / resume / clear was dropped together with the per-project private-context sync. Reasons:

- **Intrusive**: every `/clear` inside an existing session re-ran the full sync contract (MCP precheck + catalog drift + per-project context). For devs who open and clear sessions often, this turned into a visible tax on each turn.
- **Auto-sync ran without consent**: the skill detected "local `CLAUDE.md` exists but no marker" and started prompting about linking to a DevStack slug. Devs with their own per-project CLAUDE.md conventions got prompted in projects that had nothing to do with DevStack.
- **The managed CLAUDE.md can carry the "what's DevStack" information without a hook** — devs see the MCP tools and invoke the skill when they need it.

After the rollback, the skill is on-demand. Catalog updates land when the dev asks (*"sync the devstack catalog"*, *"install finalize"*, etc.); Tech Radar is still mandatory at the LLM level via the managed CLAUDE.md rule.

## Validation Log

| Test | Result | Date |
|------|--------|------|
| Managed CLAUDE.md via Miradore → `/Library/Application Support/ClaudeCode/CLAUDE.md` | Passed | 2026-04-17 |
| Managed settings.json (hooks) via claude.ai admin panel | Passed | 2026-04-17 |
| Phase 1 implementation (catalog + API + MCP + UI) | Passed (11 tests) | 2026-04-17 |
| MCP `devstack_get_catalog` from production | Passed | 2026-04-17 |
| Fetch + install skill from private GitHub repo via `gh api` | Passed | 2026-04-17 |
| Miradore Application (Script type) pasted via VSCode → deploys CLAUDE.md + hook + bootstrap | Passed | 2026-04-18 |
| PreToolUse hook smoke test (allow with sha, block without) | Passed | 2026-04-18 |

## Open Questions

1. ~~**Managed settings.json coexistence**~~ — **Resolved.** Hooks/permissions go through claude.ai managed settings, CLAUDE.md goes through Miradore (bootstrap) then MCP (updates).

2. **GitHub auth for private repos** — `gh api` works with private repos if developer has `gh` authenticated. The org CLAUDE.md should verify `gh auth status` before attempting sync.

3. **Conflict with project CLAUDE.md** — The managed CLAUDE.md sets org-wide rules. Claude Code's built-in precedence applies (managed > project > user).

4. **Linux support** — Managed CLAUDE.md path on Linux is `/etc/claude-code/CLAUDE.md`. Sync instructions need OS detection.

5. ~~**CLAUDE.md write permissions**~~ — **Resolved 2026-04-18.** Miradore creates the directory as root via the installer script; Claude Code (running as user) can read but not write. DevStack Sync updates the file via `sudo` when needed, or via a future MCP tool that wraps the write.

6. **Miradore pkg limitation** — The Vizzuality Miradore instance cannot install macOS `.pkg` files (it execs the payload directly rather than invoking `/usr/sbin/installer`). Use Script type only. Revisit if IT upgrades the Miradore plan or configures a dedicated pkg-install Configuration.

7. **CRLF in Miradore textarea** — Documented gotcha: always paste via VSCode, verify LF indicator. Confirmed 2026-04-18 with three failed Exec format errors before the workaround landed.
