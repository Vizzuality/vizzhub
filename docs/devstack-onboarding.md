# DevStack — Deployment & Onboarding Guide

Operational guide for how Vizzuality's DevStack reaches each developer's Mac and what Claude Code does on their behalf once it lands. For design rationale and MCP tool specs see `docs/devstack.md`.

Audience: IT / admin (deployment), developers (what to expect after onboarding).

---

## 1. Distribution

DevStack uses a single one-time distribution channel (Miradore) plus on-demand pulls through the `vizzhub-remote` MCP server.

| Channel | What it distributes | Where it lands on the Mac |
|---|---|---|
| **Miradore (MDM)** | `vizz-bootstrap-claude.sh` + managed `CLAUDE.md` | `/usr/local/bin/` and `/Library/Application Support/ClaudeCode/` |
| **DevStack MCP + `devstack-sync` skill** | Skills, commands, agents, npm packages | `~/.claude/skills/` / `~/.claude/commands/` / `~/.claude/agents/` / npm global |

Miradore is a one-time deployment. Day-to-day updates to skills/commands/agents are pulled by the dev through the `devstack-sync` skill when they ask for them — there is no automatic session-start hook.

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

Run **once** per machine at enrollment. Do NOT schedule periodic re-runs — the installer embeds a snapshot of `CLAUDE.md` and would revert any updates that DevStack Sync has applied since.

---

## 3. What lands on each dev's Mac

After Miradore propagates, the developer's Mac has:

```
/Library/Application Support/ClaudeCode/
└── CLAUDE.md                          # managed org instructions (Tech Radar + DevStack pointer)

/usr/local/bin/
└── vizz-bootstrap-claude.sh           # left on disk for manual diagnostic re-runs
```

Prerequisites on each dev's Mac:

- **`gh auth login`** — Tech Radar markdown and private skill sources are fetched via `gh api` in a few manual paths. Documented in the Vizzuality onboarding checklist.
- **MCP server `vizzhub-remote` connected** — configured in the user's Claude Code MCP settings with OAuth login against VizzHub. Required for any `devstack_*` tool call.

---

## 4. What Claude Code does day-to-day

The managed `CLAUDE.md` sets two baseline rules:

1. **Tech Radar consultation** — before suggesting any library, framework, or tool, Claude MUST call `devstack_get_tech_radar(file)`.
2. **DevStack tools are available** — the managed file lists the MCP tools and tells Claude to delegate to the `devstack-sync` skill whenever the dev asks about installing or syncing DevStack artifacts.

There is **no automatic session-start sync**. Catalog drift is pulled only when the dev asks — natural-language triggers like *"sync the devstack catalog"*, *"check for devstack updates"*, *"install finalize"*, *"what skills are available for react?"*.

### 4.1 First `devstack-sync` invocation

The skill lives in the catalog. If the dev asks for a sync on a clean machine where `~/.claude/skills/devstack-sync/SKILL.md` does not exist yet, Claude bootstraps it:

```
devstack_get_installable('devstack-sync')
```

The tool returns `{target_path, content}` with the SHA already injected server-side. Claude writes the file verbatim, then invokes it.

---

## 5. Tools and processes available after onboarding

### 5.1 Catalog sync (on demand)

The `devstack-sync` skill compares local `devstack_sha` frontmatter against the catalog's `github_sha` and surfaces drift grouped by action. Nothing is overwritten without explicit confirmation.

Covered entry types:

- `skill` → `~/.claude/skills/{name}/SKILL.md`
- `command` → `~/.claude/commands/{name}.md`
- `agent` → `~/.claude/agents/{name}.md`
- `npm` plugin → global npm install at `package_version`

The managed `CLAUDE.md` itself (type `config`) is tracked but not auto-updated — it is owned by Miradore and requires root to rewrite. On drift the skill reports and asks the dev to re-run `sudo /usr/local/bin/vizz-bootstrap-claude.sh`.

### 5.2 Tech Radar consultation

Mandatory before suggesting libraries/frameworks/tools — call `devstack_get_tech_radar(file)` with `file` ∈ {`development`, `devops`, `tools-and-libraries`, `data-science-gis`}. Adopt is auto-approved; Trial must be flagged; Assess is exploration only; Hold is forbidden in new code. Unlisted technologies must be flagged to the dev before use.

### 5.3 Discovery on demand

Users can ask *"what skills / commands / agents are available for Python?"* — Claude answers via `devstack_discover(type?, tech?, featured_only?)`, a lightweight catalog view returning only `name`, `type`, `description`.

---

## 6. Troubleshooting

### 6.1 Managed `CLAUDE.md` missing

The bootstrap script was never run or was interrupted. Have the dev run `sudo /usr/local/bin/vizz-bootstrap-claude.sh` manually. If the bootstrap file itself is missing, re-run the Miradore Application.

### 6.2 Skill install fails with `NOT_FOUND`

The catalog is missing the `devstack-sync` entry. Check the VizzHub admin UI at `/devstack` → search for the `devstack-sync` skill entry → confirm `active=true` and the GitHub URL points at `Vizzuality/claude-code-standards/Skills/devstack-sync.md`.

### 6.3 `gh auth` expired

Tech Radar consultation and any `gh api` fallback paths will fail silently. Have the dev run `gh auth login` — already on the onboarding checklist.

### 6.4 MCP `vizzhub-remote` disconnected

The skill's §0 precheck catches this and instructs the dev to run `/mcp` in Claude Code and reconnect. No DevStack MCP tool works until the connection is restored.

---

## 7. Maintenance

### 7.1 Updating the managed `CLAUDE.md`

Two paths:

- **Content change** — edit `Vizzuality/claude-code-standards/Settings/managed/CLAUDE.md` and also update the heredoc inside `Settings/managed/miradore-installer.sh` so new Miradore runs deploy the same version. Re-run the Miradore Application on existing machines to pick up the change.
- **Preference**: keep changes to this file rare — the whole point of the skill-based distribution is that protocol evolution happens via `devstack-sync`, not via `CLAUDE.md`.

### 7.2 Updating the `devstack-sync` skill

Commit changes to `Vizzuality/claude-code-standards` → `Skills/devstack-sync.md`. The catalog entry's `github_sha` refreshes automatically via the daily cron; devs pick up the new version the next time they run the skill.

### 7.3 Rolling back a bad skill or catalog entry

Revert the file in `Vizzuality/claude-code-standards`. Devs pick up the revert on their next `devstack-sync` run. No emergency push needed.
