# DevStack — Deployment & Onboarding Guide

Operational guide for how Vizzuality's DevStack reaches each developer's Mac and what Claude Code does on their behalf once it lands. For design rationale and MCP tool specs see `docs/devstack.md`.

Audience: IT / admin (deployment), developers (what to expect after onboarding).

---

## 1. Distribution channels

DevStack is delivered in two complementary channels, each owning a different slice of the payload:

| Channel | What it distributes | Where it lands on the Mac | Why this channel |
|---|---|---|---|
| **Miradore (MDM)** | Shell scripts that need elevated perms + the managed `CLAUDE.md` | `/Library/Application Support/ClaudeCode/` and `/usr/local/bin/` | Only MDM can `chmod` and write to `/Library` / `/usr/local` |
| **claude.ai admin console (Enterprise)** | `managed-settings.json` registering the `SessionStart` hook | `/Library/Application Support/ClaudeCode/managed-settings.json` (written by Claude Code itself) | Only claude.ai managed settings have precedence over every dev's `~/.claude/settings.json` |

Neither channel is optional. Miradore places the executable hook on disk; claude.ai tells Claude Code when to run it. Without the JSON registration the hook file sits unused; without the Miradore payload the JSON points at a missing file and the hook fails non-blocking on every session start.

---

## 2. One-time admin deployment

### 2.1 Miradore Application (Script type)

Source file: `Vizzuality/claude-code-standards` → `Settings/managed/miradore-installer.sh`.

Steps:

1. Fetch the script with LF preserved:
   ```bash
   gh api repos/Vizzuality/claude-code-standards/contents/Settings/managed/miradore-installer.sh \
     --jq '.content' | base64 -d > ~/Desktop/miradore-installer.sh
   grep -c $'\r' ~/Desktop/miradore-installer.sh   # must print 0
   ```
2. Open in **VSCode** and confirm the line-ending indicator reads **LF** (not CRLF). This step is not optional — pasting from a browser or the Miradore textarea on Windows routinely inserts `\r` bytes that break the shebang (`Exec format error` at runtime).
3. In Miradore: create an Application of type **Script** (not macOS Package — this Miradore instance execs payloads directly and never invokes `/usr/sbin/installer`). Paste the file from VSCode into the script textarea.
4. Name: `Vizzuality Claude Code Bootstrap`. Assign to a single test device first, validate, then roll out to the full macOS group.

On execution the installer:

- Writes `/usr/local/bin/vizz-bootstrap-claude.sh` (`chmod 0755`).
- Runs the bootstrap once, which in turn writes:
  - `/Library/Application Support/ClaudeCode/CLAUDE.md` (`chmod 0644`) — the managed org CLAUDE.md.
  - `/Library/Application Support/ClaudeCode/hooks/vizz-session-start.sh` (`chmod 0755`) — the SessionStart hook.

Run **once** per machine at enrollment. Do NOT schedule periodic re-runs — the installer embeds a snapshot of `CLAUDE.md` and would revert any updates that DevStack Sync has applied since.

### 2.2 claude.ai managed settings

Source file: `Vizzuality/claude-code-standards` → `Settings/managed/managed-settings.json`.

In the claude.ai admin console → Enterprise → Managed Settings, paste the JSON. It registers `/Library/Application Support/ClaudeCode/hooks/vizz-session-start.sh` for all three SessionStart matchers (`startup`, `resume`, `clear`) so the hook fires on fresh sessions, resumed sessions, and `/clear` within an existing session.

The path in the JSON is wrapped in single quotes because `/bin/sh -c` tokenises on spaces (`Application Support`).

Managed settings propagate to every Enterprise org member automatically — no manual action on the developer side.

---

## 3. What lands on each dev's Mac

After Miradore + managed-settings propagate, the developer's Mac has:

```
/Library/Application Support/ClaudeCode/
├── CLAUDE.md                          # managed org instructions (Tech Radar + mandatory skills)
├── managed-settings.json              # registers the SessionStart hook (written by Claude Code)
└── hooks/
    └── vizz-session-start.sh          # shell hook, <100 ms, idempotent

/usr/local/bin/
└── vizz-bootstrap-claude.sh           # left on disk for manual diagnostic re-runs
```

Prerequisite on each dev's Mac:

- **`gh auth login`** — Tech Radar markdown and a small number of private skill sources are still fetched via `gh api`. Documented in the Vizzuality onboarding checklist. Future MCP tooling (`devstack_get_tech_radar` and `devstack_get_installable`) removes this dependency for Claude-side calls but a few manual workflows still rely on it.
- **MCP server `vizzhub-remote` connected** — configured in the user's Claude Code MCP settings with OAuth login against VizzHub. The `devstack-sync` skill starts with a precheck call and stops if the MCP is not reachable.

---

## 4. Onboarding flow — what happens when the dev opens Claude Code

```
┌──────────────────────────────────────────────────────────────────────┐
│  SessionStart event (startup / resume / clear)                       │
└──────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
     managed-settings.json runs /Library/.../hooks/vizz-session-start.sh
                                 │
                                 ▼
          ┌──────────────────────────────────────────────┐
          │  Hook inspects state and emits reminders:    │
          │   • Managed CLAUDE.md present?               │
          │   • ~/.claude/skills/devstack-sync/ present? │
          │   • ./.claude/.devstack-context / -skip?     │
          │   • ./.git present?                          │
          └──────────────────────────────────────────────┘
                                 │
                                 ▼
             stdout: JSON envelope with system-reminders
                                 │
                                 ▼
          ┌──────────────────────────────────────────────┐
          │  Claude Code injects reminders into the LLM  │
          │  context BEFORE the first user message.      │
          └──────────────────────────────────────────────┘
                                 │
                                 ▼
     Claude invokes the `devstack-sync` skill (bootstrapping it via
     `devstack_get_installable('devstack-sync')` if not on disk yet).
                                 │
                                 ▼
            Skill runs: precheck → debounce → catalog sync →
                       per-project private context
                                 │
                                 ▼
                      First user message answered.
```

The hook is intentionally narrow: it never calls MCP, never reads project files beyond the marker and `.git` check. All operational work is performed by the skill at the LLM's request, so the protocol can evolve without touching Miradore.

### 4.1 Skill bootstrap (first session only)

On a brand-new machine, `~/.claude/skills/devstack-sync/SKILL.md` does not exist yet. The managed CLAUDE.md contains an explicit bootstrap instruction; combined with the hook's reminder, Claude calls:

```
devstack_get_installable('devstack-sync')
```

The tool returns `{target_path, content}` with the SHA already injected server-side. Claude writes the file verbatim. Subsequent sessions find the skill already installed and invoke it directly.

### 4.2 Catalog debounce

The skill writes `~/.claude/.devstack-last-catalog-sync` (Unix timestamp) after each successful sync. The next session within 3600 s skips the catalog fetch + install passes entirely, which keeps cold start snappy when devs open several Claude Code instances in a row. Bypass phrases: *"sync the devstack catalog"*, *"refresh my skills"*, *"check for devstack updates"*.

---

## 5. Tools and processes available after onboarding

Once the skill runs at least once, these capabilities are available in every session:

### 5.1 Catalog sync (automatic, debounced)

At session start the skill compares local `devstack_sha` frontmatter against the catalog's `github_sha` and surfaces drift grouped by action. Nothing is overwritten without explicit confirmation.

Covered entry types:

- `skill` → `~/.claude/skills/{name}/SKILL.md`
- `command` → `~/.claude/commands/{name}.md`
- `agent` → `~/.claude/agents/{name}.md`
- `npm` plugin → global npm install at `package_version`

The managed `CLAUDE.md` itself (type `config`) is tracked but not auto-updated — it is owned by Miradore and requires root to rewrite. On drift the skill reports and asks the dev to re-run `sudo /usr/local/bin/vizz-bootstrap-claude.sh`.

### 5.2 Tech Radar consultation

Before suggesting any library, framework, database, or CLI tool the managed `CLAUDE.md` requires Claude to call `devstack_get_tech_radar(file)` — where `file` is one of `development`, `devops`, `tools-and-libraries`, `data-science-gis`. Adopt is auto-approved; Trial must be flagged; Assess is exploration only; Hold is forbidden in new code. Unlisted technologies must be flagged to the dev before use.

### 5.3 Discovery on demand

Users can ask *"what skills / commands / agents are available for Python?"* — Claude answers via `devstack_discover(type?, tech?, featured_only?)`, a lightweight catalog view returning only `name`, `type`, `description`. Never surfaced proactively at session start.

### 5.4 Per-project private CLAUDE.md sync

See §6 — the main operational surface beyond session start.

---

## 6. Per-project private context

For projects under NDA or compliance constraints where the `CLAUDE.md` cannot be committed to the public repo, DevStack distributes it through the private monorepo `Vizzuality/project-contexts`. One folder per project, keyed by a unique `slug`.

### 6.1 Marker files (where project state lives)

Two mutually exclusive marker files live under `.claude/` at the project root. **They are not environment variables** — they are small text files that the skill reads at session start and edits as the dev links / unlinks / syncs.

| File | Meaning | Format |
|---|---|---|
| `.claude/.devstack-context` | Project is linked to a DevStack slug | `slug: <slug>`<br>`sha: <blob SHA at last sync>`<br>`local_hash: <sha256 of ./CLAUDE.md at last sync>` |
| `.claude/.devstack-skip` | Dev has explicitly declared no private context for this project | content irrelevant (empty file is fine) |

Never present both. The root-level `./CLAUDE.md` is the synced content itself.

The slug is discoverable in two ways:

- Ask Claude *"list the available DevStack contexts"* → it calls `devstack_list_project_contexts` and returns slug + description pairs.
- The VizzHub UI at `/devstack/contexts` lists all registered slugs (admins + devs with `DEVSTACK_VIEW`).

### 6.2 First link

At session start, if neither marker exists and the cwd is a git repo, the hook injects a reminder asking Claude to prompt:

> *This project has no DevStack context linked. Reply with the slug (e.g. `acme-corp`) or `N` to skip.*

Two paths diverge based on whether `./CLAUDE.md` already exists in the working directory:

- **No local `CLAUDE.md`** → remote content is written atomically and the marker is initialised with `sha` + `local_hash`.
- **Local `CLAUDE.md` exists** → the skill does NOT overwrite. It treats the situation as a merge against an empty base and enters the LLM-mediated merge (see §6.4) so no in-flight local work is lost.

### 6.3 Gitignore contract

The first time a project is linked, the skill ensures the project root `.gitignore` contains:

```
CLAUDE.md
.claude/.devstack-context
.claude/.devstack-skip
```

Creates the file if absent; appends only missing lines otherwise. Private content must never reach the public repo history.

### 6.4 Pull / merge at session start

After dispatch the skill fetches `devstack_get_project_context(slug)` and compares:

- `local_changed = sha256(./CLAUDE.md) != marker.local_hash`
- `remote_changed = remote_sha != marker.sha`

| local | remote | Action |
|:-:|:-:|---|
| no | no | silent no-op |
| no | yes | fast-forward pull (atomic write, update marker) |
| yes | no | silent, one soft reminder that local has unpublished changes |
| yes | yes | **LLM-mediated 3-way merge** — fetches `base_content` via `at_sha=marker.sha`, summarises local + remote diffs, proposes a merged version, waits for explicit approval, writes atomically and updates marker |

### 6.5 Publishing local edits

Triggered by natural language — *"publica los cambios del contexto"*, *"push my CLAUDE.md changes"*, *"sync this context"*, or equivalent. The skill calls `devstack_update_project_context(slug, local_content, expected_remote_sha)` which enqueues a command-queue entry (auto-approved by the VizzHub bot) and opens a PR-style commit on the private repo, attributed to the dev (author) and the VizzHub bot (committer).

Three outcomes:

- `up_to_date` → local content matches remote; marker refreshed, nothing else.
- `committed` → new commit lands on `main`; marker updated with the new blob SHA.
- `conflict` → remote advanced mid-flight; skill re-runs the merge flow against the new head, then retries.

### 6.6 Unlinking a project

Triggered by *"unlink this project from DevStack"* / *"desvincula este proyecto de DevStack"*.

The skill never deletes `./CLAUDE.md`. It renames it to `./CLAUDE.md.devstack-unlinked.bak` (overwriting any previous backup), deletes `.claude/.devstack-context`, and creates `.claude/.devstack-skip`. The dev retains the content locally if needed; future sessions are silent on the private-context axis for this project.

---

## 7. Troubleshooting

### 7.1 SessionStart hook error: `/bin/sh: /Library/Application: No such file or directory`

Cause: path-with-spaces tokenisation in `/bin/sh -c`.

Fix: the managed `managed-settings.json` wraps the hook path in single quotes. If the error persists, confirm the JSON ingested by claude.ai matches the version in `Settings/managed/managed-settings.json` and that the developer received the latest managed-settings push.

### 7.2 Dev sees the hook error but Miradore hasn't reached their Mac yet

Non-blocking error. The hook fails, no `additionalContext` is injected, and Claude Code proceeds normally. The dev loses DevStack automation for that session but nothing else. Accept temporarily during Miradore rollout; the error clears once the bootstrap runs.

### 7.3 Skill install fails with `NOT_FOUND`

The catalog is missing the `devstack-sync` entry. Check the VizzHub admin UI at `/devstack` → search for the `devstack-sync` skill entry → confirm `active=true` and the GitHub URL points at `Vizzuality/claude-code-standards/Skills/devstack-sync.md`.

### 7.4 Managed `CLAUDE.md` missing

The bootstrap script was never run or was interrupted. Have the dev run `sudo /usr/local/bin/vizz-bootstrap-claude.sh` manually. If the bootstrap file itself is missing, re-run the Miradore Application.

### 7.5 `gh auth` expired

Tech Radar consultation and any remaining private-repo `gh api` fallback paths will fail silently. Have the dev run `gh auth login` — already on the onboarding checklist.

### 7.6 MCP `vizzhub-remote` disconnected

The skill's §0 precheck catches this and instructs the dev to run `/mcp` in Claude Code and reconnect. No further DevStack work happens until the connection is restored.

### 7.7 Catalog sync runs on every session (debounce not effective)

Check `ls -la ~/.claude/.devstack-last-catalog-sync`. The file should exist and contain a Unix timestamp. If missing, the last sync failed — the skill intentionally does not update the timestamp on failure, to avoid masking a persistent error. Investigate the failure first.

---

## 8. Maintenance

### 8.1 Updating the managed `CLAUDE.md`

After the initial deploy, the managed `CLAUDE.md` is owned by DevStack Sync inside Claude Code. Commit changes to `Vizzuality/claude-code-standards` → `Settings/managed/CLAUDE.md`; every dev picks them up on the next session via the sync block — **no Miradore re-deploy**.

### 8.2 Updating the hook

Changes to `vizz-session-start.sh` require a Miradore re-deploy (the bootstrap carries a snapshot of the hook). Keep hook edits rare; the operational logic belongs in the skill.

### 8.3 Updating the skill

Commit changes to `Vizzuality/claude-code-standards` → `Skills/devstack-sync.md`. The catalog entry's `github_sha` refreshes automatically via the daily cron; devs pick up the new version on their next catalog sync pass (within the hour or on the next bypass).

### 8.4 Rolling back a bad managed `CLAUDE.md`

Revert the file in `Vizzuality/claude-code-standards`. Devs pick up the revert on their next DevStack Sync pass. No emergency push needed.
