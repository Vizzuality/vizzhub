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
curl -sL "https://raw.githubusercontent.com/Vizzuality/claude-code-standards/main/Settings/managed/CLAUDE.md" \
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

#### Sync instructions (org CLAUDE.md template)

The instructions below are the canonical contract Claude Code follows at session start. They live in `Vizzuality/claude-code-standards/Settings/managed/CLAUDE.md` and are deployed via Miradore to `/Library/Application Support/ClaudeCode/CLAUDE.md`. Update both places together.

````markdown
## DevStack Sync

At the start of every session, synchronize the local developer environment with the Vizzuality DevStack catalog. Do this silently unless something needs the user's attention.

### Steps

1. **Fetch the catalog** — call the MCP tool `devstack_get_catalog`. It returns all active entries with `name`, `type`, `install_method`, `url`, `package`, `package_version`, `required`, `github_sha`, `latest_package_version`.

2. **Filter to required entries** — only entries with `required: true` are auto-synced. Non-required entries are installed on explicit user request (via `devstack_list` / `devstack_recommend`).

3. **For each required entry, detect drift:**

   - **`install_method: github`** (skills, commands, agents, configs)
     - Resolve the local target path (see table below).
     - If the file does not exist → needs install.
     - If it exists, read the YAML frontmatter and compare `devstack_sha` with the catalog's `github_sha`.
       - Equal → up to date, skip.
       - Different or missing → needs update.

   - **`install_method: npm`** (CLI tools, linters)
     - Run `npm list -g --depth=0 --json <package>` and read the installed version.
     - Compare with the catalog's `package_version`.
       - Equal → up to date, skip.
       - Different or not installed → needs update.
     - Ignore `latest_package_version` for sync decisions; it is informational (shown in VizzHub UI when a newer version exists upstream).

   - **`install_method: claude_plugin`**
     - Skip. Claude Code's plugin manager owns the lifecycle of marketplace plugins. DevStack only lists them for discoverability.

4. **Report drift once, concisely** — if one or more entries need changes, list them grouped by action (install / update) with the entry name and reason (`new`, `sha <old>→<new>`, `version <old>→<new>`). Ask the user to confirm before making any changes. Never install or overwrite files without confirmation.

5. **On confirmation, apply changes:**

   - **github** — fetch the file content via `gh api repos/{owner}/{repo}/contents/{path}?ref={ref} --jq '.content' | base64 -d`. Write it to the target path. Inject or replace the `devstack_sha: <github_sha>` line in the YAML frontmatter (create the frontmatter block if missing). Preserve all other frontmatter fields.
   - **npm** — run `npm install -g <package>@<package_version>`.
   - **config** entries targeting `/Library/Application Support/ClaudeCode/CLAUDE.md` — write with elevated permissions; if the write fails, report the path and stop (do not silently skip).

6. **Verify** — after each install/update, re-read the target to confirm the write succeeded and the SHA/version landed as expected. Report a one-line summary per entry.

### Target paths

| Type             | Target                                                     |
|------------------|------------------------------------------------------------|
| `skill`          | `~/.claude/skills/{name}/SKILL.md`                         |
| `command`        | `~/.claude/commands/{name}.md`                             |
| `agent`          | `~/.claude/agents/{name}.md`                               |
| `config` (org)   | `/Library/Application Support/ClaudeCode/CLAUDE.md`        |
| `config` (other) | as specified by the entry (fall back to asking the user)   |
| `plugin` (npm)   | npm global                                                 |

### Frontmatter SHA contract

Every installed file of type `skill` / `command` / `agent` / `config` MUST carry a `devstack_sha` key in its YAML frontmatter. Example:

```yaml
---
name: finalize
description: End-of-session finalization workflow.
devstack_sha: 8790a9aac0d4528de87e61aab742a2f7556a2e23
---
```

- Claude Code ignores unknown frontmatter keys — safe to add.
- If the upstream file has no frontmatter, create one with just `name` and `devstack_sha`.
- Never remove `devstack_sha` on edit. It is the only source of truth for drift detection.

### Authentication

- GitHub: private repos require `gh auth status` to be OK. If it is not, stop and ask the user to run `gh auth login` — do not attempt anonymous fetches.
- npm: public registry, no auth needed for the catalog entries currently tracked.

### Failure modes

- **MCP unavailable** — skip sync for this session and report once. Do not block the user.
- **Single entry fails** — continue with the rest, report failures at the end.
- **Frontmatter parse error** — treat as "needs update" and rewrite cleanly.
````

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

### Roadmap — what's next after v1 rollout

Ordered by priority. All items move reliability/ergonomics from "Claude follows text instructions" to "backend provides data atomically" or "UX has no friction".

**Done**

1. ~~**`devstack_get_tech_radar(file)`**~~ — shipped. Removes per-user `gh auth login` prerequisite for Tech Radar consultation. Accepts `development` | `devops` | `tools-and-libraries` | `data-science-gis`.
2. ~~**`devstack_discover(type, tech, featured_only)`**~~ — shipped. Lightweight dev-facing view returning only `name`, `type`, `description`. Replaces the Phase 2 `devstack_list` idea.
3. ~~**`DEVSTACK_VIEW` added to `user` role**~~ — catalog and discovery tools now callable by any authenticated dev.

**Next**

4. **`devstack_get_installable(name)`** — MCP tool that fetches source for a catalog entry and returns `{ target_path, content }` where `content` already has `devstack_sha` injected into the YAML frontmatter. Claude then writes verbatim. Eliminates client-side composition, which is the main failure mode of the current sync contract. Unblocks hook v2.

**Then (quality-of-life on top of the above)**

5. **Hook v2 — warn-only, broad coverage** — reintroduce the PreToolUse hook as non-blocking (logs to a file, exits 0 always). Matcher expanded to `Write|Edit|MultiEdit`. Becomes a visible drift signal without obstructing developers. Works in tandem with `devstack_get_installable`: the install path is guaranteed correct by the server, the hook catches manual/edit deviations.

6. **Orphan detection in sync** — during the session-start sync pass, scan `~/.claude/{skills,commands,agents}/` for files whose name isn't in the catalog. Surface them as "untracked" so the dev can decide: add to catalog, mark local (`devstack_sha: local`), or remove.

**Later (Phase 3)**

7. **`devstack_recommend`** — weighted tech-match ranking (on top of the existing `devstack_discover(tech=...)`).
8. **npm install lifecycle** — npm-based entries with version comparison.
9. **Dry-run mode for sync** — show what would change without applying.

### Why the hook was dropped in v1

We piloted a strict PreToolUse hook during the 2026-04-18 distribution validation. Shipped, debugged, deployed end-to-end. Then rolled back before group rollout for these reasons:

- **Weak enforcement**: the hook only checked that `devstack_sha:` was present and non-empty. It did not verify the value matched the catalog. Claude could write `devstack_sha: WRONG` and pass.
- **High friction on non-catalog skills**: any dev experimenting with a skill from outside Vizzuality's catalog was blocked on the first write, forcing them to add `devstack_sha: local` manually.
- **Partial coverage**: only the `Write` tool was intercepted. `Edit`, `MultiEdit`, and `Bash` (`cat > file`) all bypassed the hook silently.
- **Redundant with Sync**: DevStack Sync already detects drift (missing or wrong sha → reinstall next session). The hook only shortened the drift window within a session, at the cost of all of the above.

The right place for this enforcement is the backend (via `devstack_get_installable`) and a warn-only client hook as a secondary signal. Both are captured in the roadmap above.

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
