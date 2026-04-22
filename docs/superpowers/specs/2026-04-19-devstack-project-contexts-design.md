# DevStack Project Contexts — Design — ABANDONED

**Status:** ABANDONED (2026-04-22). The feature was shipped, then removed. Too intrusive — auto-prompting to link projects at every session start, hook-driven sync, and the heavy LLM-mediated merge flow created more friction than value. Backend tables, MCP tools, frontend page, and SessionStart hook all deleted. Kept as historical record.
**Date:** 2026-04-19
**Module:** DevStack
**Related:** `docs/devstack.md`, `project_devstack-module.md` (memory)

## Problem

Some client projects (NDA, GovTech, compliance-bound) cannot host their `CLAUDE.md` in the project's public GitHub repo. Today there is no sanctioned way to distribute per-project Claude instructions privately. Individual devs either:

- Commit CLAUDE.md to the public repo (compliance breach), or
- Keep it ad-hoc in their local filesystem (no team consistency), or
- Skip per-project Claude context entirely (degraded AI assistance).

## Goal

Register per-project private `CLAUDE.md` files in VizzHub (DevStack), stored in a private monorepo, and enable bidirectional sync with developer workstations through the MCP + skill — pull on every session start, push on explicit dev intent, with 3-way merge to preserve local edits. No forced `git clone`, no local path conventions, no filesystem setup beyond the two marker files under `.claude/`. Every published change is committed to the private repo with the dev as `author` and an auto-approved command-queue row for compliance audit.

## Non-goals (v1)

- Editing via DevStack UI (edits happen through Claude Code: local edit + natural-language push, or directly on the private repo via any git workflow).
- Cross-approval / peer review of proposed updates (all updates are auto-approved in v1 — the explicit push action IS the approval. A `requires_cross_approval` per-context flag is a clean v2 extension).
- Project-scoped read permissions (trust-based; gate is the GitHub private repo access itself).
- Distributing per-project skills/commands/agents (CLAUDE.md only in v1; extensible later).

## Architecture

Bidirectional sync between the developer's working directory and the private monorepo, mediated by VizzHub:

- **Backend role**: dumb blob store with optimistic locking. Two GitHub-facing responsibilities — fetching blobs (head or historical) and pushing commits via the Git Data API (blob → tree → commit → update ref), routed through the existing command queue for auditability. No merge logic, no diff logic, no conflict resolution server-side.
- **Merge is LLM-mediated**: when remote and local have both diverged, the skill fetches the base blob via `devstack_get_project_context(slug, at_sha=base_sha)`, shows the dev both changes in natural language, proposes a merged version, and writes only after the dev approves. `CLAUDE.md` is human-authored prose (decisions, rules, context) — semantic merging by an LLM-in-the-loop is a better fit than line-based `diff3` markers that would produce noise on non-code content. The dev's review-before-push is the safety net that would otherwise be provided by deterministic merge.
- **Push uses optimistic locking**: the skill sends `(content, expected_remote_sha)`. Backend commits only if remote is still at that SHA. If the remote has advanced, backend refuses with `conflict` and returns the current remote SHA — skill triggers the same LLM-mediated merge flow against the new remote, then retries.
- **Temporal pattern**: **pull-automatic, push-explicit**. Session start always pulls remote changes (LLM-mediated merge if local has also diverged). Push only happens on explicit dev intent (*"publica los cambios"*, *"push my CLAUDE.md changes"*, …). The explicit push is the approval — the command queue auto-approves on v1, providing the audit trail without interactive friction.

### Components

```
┌─────────────────────────┐
│ Vizzuality/project-     │  Private monorepo, one folder per slug:
│ contexts  (GitHub)      │    acme-corp/CLAUDE.md
└───▲─────────────┬───────┘
    │ push        │ fetch
    │ (Git Data   │ (head or
    │  API: blob  │  historical
    │  →tree      │  blob by sha)
    │  →commit    │
    │  →ref)      │
┌───┴─────────────▼───────┐
│ VizzHub backend         │  devstack_project_contexts table
│  - REST API (admin CRUD)│  - Dumb blob fetch / commit push
│  - MCP server           │  - Optimistic lock via expected_remote_sha
│                         │  - Auto-approved command-queue entries
│                         │    for audit trail (compliance evidence)
└───▲─────────────┬───────┘
    │ push        │ get (head +
    │ (explicit,  │   at_sha=base
    │  optimistic │   when merging)
    │  lock)      │
┌───┴─────────────▼───────┐
│ Developer workstation   │  devstack-sync skill (prose procedure):
│  Claude Code session    │   • Session start → pull
│                         │   • If both diverged → LLM-mediated merge
│                         │     (fetch base blob, diff, propose, write)
│                         │   • NL "publica/push" → commit via lock
│                         │   • Markers under .claude/ (all gitignored)
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

Three tools in `app/mcp/tools/devstack.py` (list, get, update). All require `DEVSTACK_VIEW` (included in the default `user` role — every authenticated dev can call them, including the update tool). The real confidentiality boundary is the private GitHub repo's access list, not the MCP layer.

```python
@mcp.tool()
async def devstack_list_project_contexts() -> list[dict]:
    """List registered project contexts (slug + description + project_name).
    Use for discovery when the dev doesn't know the slug."""

@mcp.tool()
async def devstack_get_project_context(
    slug: str,
    at_sha: str | None = None,
) -> dict:
    """Fetch a project's private CLAUDE.md content.

    If at_sha is None → return the current HEAD content of <slug>/CLAUDE.md
    with its blob SHA.
    If at_sha is set → return the content of the blob with that exact SHA
    (used by the skill to fetch the 'base' version during an LLM-mediated
    merge). GitHub blobs are immutable, so historical SHAs always resolve
    to the same bytes.

    Returns {target_path: "CLAUDE.md", content: str, devstack_sha: str, slug: str}.
    - devstack_sha == the blob SHA actually returned (HEAD or at_sha).
    """

@mcp.tool()
async def devstack_update_project_context(
    slug: str,
    content: str,
    expected_remote_sha: str,
) -> dict:
    """Publish an update to a project's private CLAUDE.md. Invoked only
    when the dev explicitly asks to publish.

    Optimistic locking — the backend does NO merging:
      1. Fetch the current remote blob SHA of <slug>/CLAUDE.md.
      2. If current_remote_sha != expected_remote_sha → return conflict
         (the skill must re-fetch, run the LLM-mediated merge flow
         against the new remote, and retry).
      3. If content matches the remote content byte-for-byte → return
         up_to_date (no commit needed).
      4. Otherwise → create a GitHub commit via Git Data API
         (blob → tree → commit → update ref) attributed to the calling
         user (author = dev from JWT, committer = VizzHub bot). Commit
         message: "Update <slug>/CLAUDE.md via VizzHub (<dev-email>)".
      5. Record an entry in the command queue, marked auto-approved in
         the same transaction (audit trail without interactive gate).

    Returns one of:
      {status: "up_to_date", remote_sha: str}
      {status: "committed", new_sha: str, command_id: UUID}
      {status: "conflict", remote_sha: str}  # new head; skill must merge
    """
```

Error codes:

- `NOT_FOUND` — slug not registered in VizzHub, or `at_sha` blob does not exist
- `NO_CONTENT` — folder exists in the private repo but has no `CLAUDE.md` at HEAD (only on `devstack_get_project_context` with `at_sha=None`)
- `FETCH_FAILED` — GitHub API call failed (auth, network, quota)
- `COMMIT_FAILED` — GitHub rejected the push (e.g. ref advanced between our SHA check and our update-ref; skill retries the full merge flow)

**Auto-approve details**: the command-queue entry for `devstack_update_project_context` is created and marked approved within the same DB transaction as the GitHub push — the audit record is always consistent with the actual repo state. No row ever exists in "pending" state for v1. A future `requires_cross_approval` flag on `devstack_project_contexts` would split that transaction: create the row pending, wait for a second-party approval, then push.

**No merge logic on the backend**: the backend does not read the base content, does not compute diffs, and does not resolve conflicts. All merge intelligence lives in the skill (executed by the LLM). This is a deliberate choice — see "Merge strategy" in the Open questions table.

### Skill changes (`devstack-sync`)

Add an optional section "Per-project private context" to the skill (the skill itself is public and distributed via the catalog — it contains only instructions, zero private data).

#### Marker files

The skill uses **two** gitignored marker files under `.claude/` in the project root. Their mere presence disambiguates the three possible states — no content-parsing heuristics, no silent typos:

- **`.claude/.devstack-context`** — present if the project is linked to a DevStack context. Simple key/value format:

  ```
  slug: acme-corp
  sha: abc123def456...
  local_hash: 7f9c2a...
  ```

  - `slug`: written once on linking, never changes.
  - `sha`: GitHub blob SHA of `./CLAUDE.md` from the remote at the time of last successful sync (pull or push). Used to detect that the remote has advanced since the dev last synced.
  - `local_hash`: SHA-256 of `./CLAUDE.md` content at the time of last successful sync (pull or push). Used to detect that the dev has edited locally since the last sync — if current hash of `./CLAUDE.md` differs from `local_hash`, there are unpushed local changes.

- **`.claude/.devstack-skip`** — present if the dev has explicitly declared this project has no private context. Content is irrelevant (may be empty or carry a timestamp for debugging). Its presence alone suppresses future prompts.

Both files are added to `.gitignore` by the skill on creation.

Rationale: two orthogonal files eliminate semantic ambiguity between "not configured yet", "explicitly skipped", and "linked" — the three states are presence-checked, not inferred from file contents. Removes a class of silent bugs from typos in a single status file.

#### Session start: pull-automatic

The skill **only pulls at session start**. It never pushes automatically — push is always driven by explicit dev intent (see next subsection).

1. **Dispatch on markers**:
   - If `.claude/.devstack-context` exists → parse `slug`, `sha`, `local_hash`, continue to step 2.
   - Else if `.claude/.devstack-skip` exists → no-op, silent exit.
   - Else (neither file exists) → ask the dev **once**: *"This project has no DevStack context linked. Is there a private context? Reply with the slug (e.g. `acme-corp`) or `N` to skip."* Then:
     - If slug → create `.claude/.devstack-context` with `slug: <slug>` (no `sha` / `local_hash` yet), ensure it's in `.gitignore`, continue to step 2.
     - If `N` → create `.claude/.devstack-skip`, ensure it's in `.gitignore`, silent exit.

2. **Fetch remote head**: call `devstack_get_project_context(slug)` (no `at_sha`).
   - On success: receives `{content: remote_content, devstack_sha: remote_sha}`.
   - On `NOT_FOUND`: warn *"The context '<slug>' is no longer registered in VizzHub. Your local `./CLAUDE.md` may be stale. Ask me to unlink this project if it no longer applies."* — do **not** delete `./CLAUDE.md`. Exit.
   - On `FETCH_FAILED` / other: surface error, exit.

3. **First-sync fast path** (marker has no `sha`/`local_hash` yet): write `remote_content` atomically to `./CLAUDE.md`, update marker with `sha: remote_sha` and `local_hash: sha256(remote_content)`. Continue to step 6.

4. **Compute current local state**:
   - Read `./CLAUDE.md` if it exists → `local_content` (empty string if missing).
   - Compute `current_local_hash = sha256(local_content)`.
   - `local_changed = current_local_hash != marker.local_hash`.
   - `remote_changed = remote_sha != marker.sha`.

5. **Decide action**:

   | `local_changed` | `remote_changed` | Action |
   |:---:|:---:|---|
   | ❌ | ❌ | Silent no-op. |
   | ❌ | ✅ | **Fast-forward pull**: atomic write `remote_content` to `./CLAUDE.md`; update marker `sha = remote_sha`, `local_hash = sha256(remote_content)`. No LLM reasoning needed — deterministic overwrite because the dev had no local edits. |
   | ✅ | ❌ | Silent no-op here. Emit a **single soft reminder** near the end of session start: *"You have unpublished changes to this project's CLAUDE.md. Ask me to publish when you're ready."* |
   | ✅ | ✅ | **LLM-mediated merge** — run the procedure in step 6 below. |

6. **LLM-mediated merge** (only when both sides diverged):
   1. Fetch the common ancestor: `devstack_get_project_context(slug, at_sha=marker.sha)` → `base_content`. (GitHub blobs are immutable, so this always resolves.)
   2. Read local content from `./CLAUDE.md` → `local_content`.
   3. Compare the three strings (`base_content`, `remote_content`, `local_content`) and summarise for the dev in natural language: what changed remotely since `base`, what you changed locally since `base`, and where (if anywhere) those changes overlap. Use concise prose + quoted snippets; this is the LLM's job, not a mechanical tool's.
   4. Propose a merged version. In the common case (non-overlapping edits) just announce how you're combining them: *"I'm keeping both — your addition to the Testing section and the team's new rule about imports."* For overlapping edits, present the tension explicitly and ask the dev how to resolve: *"Both of you edited the SPI target. Team now says 0.90, you had it at 0.85. Which stays?"*.
   5. **Wait for the dev's approval** before writing. The dev can say *"aprobado"*, tweak the proposal (*"use 0.90 but add a note about Q4"*), or ask you to pull the three raw versions into the chat to reason about it more. Do not overwrite `./CLAUDE.md` without their go-ahead.
   6. Once approved, write the agreed content atomically to `./CLAUDE.md`, update the marker: `sha = remote_sha`, `local_hash = sha256(merged_content)`. The local edits are now layered on top of the new remote base.

7. **Atomic write**: any write to `./CLAUDE.md` uses tempfile + `os.rename` in the same directory. POSIX rename is atomic, preventing truncated reads if two Claude sessions (terminal + IDE, etc.) race.

8. **Gitignore check**: ensure `CLAUDE.md`, `.claude/.devstack-context`, and `.claude/.devstack-skip` are all present in the project's `.gitignore`. Append any missing entries and alert the dev the first time an entry is added.

#### Push: explicit, natural language

Triggered when the dev asks Claude to publish — e.g. *"publica los cambios del contexto"*, *"sync my CLAUDE.md changes to DevStack"*, *"push this context"*. There is no slash command.

1. Read `./CLAUDE.md` → `local_content`. Read `marker.sha` → `expected_remote_sha`.
2. Call `devstack_update_project_context(slug, local_content, expected_remote_sha)`.
3. Handle response:
   - `status: "up_to_date"` → nothing to publish. Update marker `local_hash = sha256(local_content)` (in case the file was edited to equal the remote). Tell dev: *"Your local content already matches the published version — nothing to publish."*
   - `status: "committed"` → success. Update marker `sha = new_sha`, `local_hash = sha256(local_content)`. Tell dev: *"Published. Commit `<new_sha[:7]>` added to the private repo, attributed to you. Command queue entry: `<command_id>`."*
   - `status: "conflict"` → the remote advanced while the dev was working. Re-enter the **LLM-mediated merge** flow (step 6 of session-start), but now between:
     - `base_content` = content at `expected_remote_sha` (the dev's old base),
     - `remote_content` = content at the new `remote_sha` returned by the conflict response (fetch via `devstack_get_project_context(slug)` — no `at_sha`),
     - `local_content` = dev's current `./CLAUDE.md`.

     After the dev approves the merged version, retry `devstack_update_project_context(slug, merged_content, expected_remote_sha=<new remote_sha>)`. If another concurrent push has happened in the meantime, the loop repeats. In practice two iterations is the upper bound under any realistic concurrency.

**Attribution**: the backend reads the calling user's email + display name from the MCP session JWT and passes them as the GitHub commit `author`. The `committer` is always the VizzHub service account. This preserves `git blame` correctness in the private repo (and leaves a compliance-usable author trail) while keeping the push mechanics under the service account's single token.

#### Linking / unlinking after initial setup

No formal slash command is introduced. The dev asks in natural language:

- **Link / re-link** (*"vincula este proyecto al contexto acme-corp"* / *"link this project to the acme-corp context"*): Claude deletes `.claude/.devstack-skip` if present, writes `slug: acme-corp` to `.claude/.devstack-context` (no `sha` / `local_hash` yet), runs the session-start pull flow.
- **Unlink** (*"desvincula este proyecto de DevStack"* / *"unlink this project"*): Claude deletes `.claude/.devstack-context` and `./CLAUDE.md`, creates `.claude/.devstack-skip`. Explicit and reversible.

Both are plain file operations — no new MCP tools or commands.

#### Composition with the personal CLAUDE.md

The `./CLAUDE.md` synced by DevStack composes with any personal CLAUDE.md the dev may have (`~/.claude/CLAUDE.md`) via Claude Code's native resolution — both apply simultaneously with no interference from this feature. The DevStack sync only touches the project-root `CLAUDE.md`.

#### Alternative edit paths

The primary workflow is local edit + natural-language push. Devs who prefer editing outside Claude (e.g. bulk edits, side-by-side diffs against prior revisions) can clone `Vizzuality/project-contexts` wherever they want, edit `<slug>/CLAUDE.md`, commit, push. Other team members will get the change on their next session via the pull-with-merge flow. No convention on clone location — not our concern.

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

## Flows

### First-time linking

```
Dev cd's into ~/work/acme-corp (public project repo, no CLAUDE.md yet)
  └─ claude
     └─ Session start → devstack-sync skill runs
        ├─ Neither .claude/.devstack-context nor .devstack-skip exist
        ├─ Skill asks once: "Private context slug, or N to skip?"
        ├─ Dev: "acme-corp"
        ├─ Skill writes .claude/.devstack-context (slug line only)
        ├─ Skill ensures .gitignore entries
        ├─ Skill calls devstack_get_project_context("acme-corp")
        │   └─ Backend returns {remote_content, remote_sha}
        ├─ First-sync fast path: atomic write ./CLAUDE.md = remote_content
        └─ Marker updated: sha=remote_sha, local_hash=sha256(remote_content)
```

### Subsequent sessions (pull-automatic)

```
Session start
  └─ Marker exists → read {slug, sha=base_sha, local_hash}
     └─ devstack_get_project_context(slug) → remote_sha, remote_content
        ├─ remote_sha == base_sha  AND  local unchanged   → silent no-op
        ├─ remote_sha == base_sha  AND  local changed     → soft reminder "unpublished changes"
        ├─ remote_sha != base_sha  AND  local unchanged   → fast-forward pull (deterministic overwrite)
        └─ remote_sha != base_sha  AND  local changed     → LLM-mediated merge (see next flow)
```

### Pull with LLM-mediated merge (both diverged)

```
Session start detects both local and remote changed:
  └─ Skill: devstack_get_project_context(slug, at_sha=marker.sha)
     └─ Receives base_content (common ancestor)
        └─ LLM compares base / remote / local in its own context
           └─ Summarises to dev in chat:
              "Team changed the Testing section to require 80% coverage.
               You added a paragraph about using vitest. Proposal: keep
               both — your vitest note + their 80% threshold. OK?"
              └─ Dev: "aprobado" / edits the proposal / asks for raw diffs
                 └─ Skill writes agreed content → ./CLAUDE.md (atomic)
                    └─ Marker: sha=remote_sha, local_hash=sha256(agreed)
```

### Push (explicit, natural language)

```
Dev: "publica los cambios del contexto" / "push my CLAUDE.md changes"
  └─ Skill reads ./CLAUDE.md + marker.sha (→ expected_remote_sha)
     └─ devstack_update_project_context(slug, content, expected_remote_sha)
        ├─ local == remote → up_to_date (marker local_hash refreshed)
        ├─ remote still at expected_remote_sha → direct push
        │   └─ Backend: blob → tree → commit(author=dev) → update ref
        │       └─ Command queue row created + auto-approved in same txn
        │           └─ Returns {committed, new_sha, command_id}
        │               └─ Skill updates marker (sha=new_sha, local_hash)
        └─ remote advanced (optimistic lock failed)
            └─ Returns {conflict, remote_sha}
                └─ Skill re-enters LLM-mediated merge flow against new remote
                   └─ After dev approval, retry with expected_remote_sha=new
```

### Unlinking

```
Dev: "desvincula este proyecto de DevStack"
  ├─ Claude deletes .claude/.devstack-context and ./CLAUDE.md
  └─ Claude creates .claude/.devstack-skip → future sessions silent
```

## Open questions resolved during brainstorming

| Question | Resolution |
|----------|------------|
| Local clone required? | **No.** Backend fetches and pushes via GitHub API. Devs may clone the private repo as an alternative edit path, but the primary workflow is local-edit + natural-language push. |
| Read-only or read + write in v1? | **Read + write** via 3-way merge + command queue. Motivation: in read-only, any local edit gets silently overwritten on next pull — footgun that would discourage editing from the checkout. |
| Pull / push cadence | **Pull-automatic, push-explicit.** Session start always pulls (with merge if needed). Push only on natural-language dev intent. Separates iteration (stay local) from publishing (deliberate act). |
| Slug detection | **Two marker files**: `.claude/.devstack-context` (linked) and `.claude/.devstack-skip` (opted out). Dev is asked exactly once when neither exists. |
| SHA and local-hash storage | **Outside `CLAUDE.md`**, stored in `.claude/.devstack-context` as `sha` (remote blob SHA at last sync) and `local_hash` (sha256 of `CLAUDE.md` at last sync). Keeps the live `CLAUDE.md` content-only and lets the skill detect local edits vs. remote drift independently. |
| Mutability of slug | **Immutable after creation**. API rejects changes (HTTP 400); UI disables the field in edit mode. Rename == delete + recreate. |
| New section or extend Catalog? | **New section** in UI; new table in DB (no shared model). |
| Link to VizzHub project? | Yes, **NOT NULL** FK `project_id`. UI dropdown picks from existing projects, auto-slugs from name. |
| Target path | Fixed: `CLAUDE.md` at project root. |
| Write/edit from the DevStack UI? | **No.** v1 accepts writes only via the skill (natural-language push) or direct git on the private repo. A UI editor is a v2 nice-to-have. |
| Multiple private repos? | **Removed from v1 model.** Single repo URL lives in backend config (`DEVSTACK_PROJECT_CONTEXTS_REPO`). Columns can be added later if a concrete need appears. |
| Merge strategy | **LLM-mediated, not server-side**. The skill fetches the base blob via `devstack_get_project_context(slug, at_sha=base_sha)`, compares base / remote / local in the LLM's context, presents the changes to the dev in natural language, proposes a merged version, writes only after dev approval. Rationale: `CLAUDE.md` is human-authored prose — semantic merging by an LLM-in-the-loop outperforms byte-level `diff3` on this content type, and the dev's review-before-write is the safety net. Server-side stays dumb: blob fetch + optimistic-locked commit. |
| Optimistic locking on push | Push sends `(content, expected_remote_sha)`. Backend commits only if current remote still matches — otherwise returns `conflict` with the new head SHA. Skill re-enters the merge flow against the new remote and retries. No server-side merge attempt, ever. |
| Commit attribution | **`author` = dev (name + email from MCP session JWT), `committer` = VizzHub bot**. Keeps `git blame` correct in the private repo while keeping push mechanics under the service token. Commit message includes the dev's email for audit grep. |
| Approval model | **Auto-approve in v1**: every `devstack_update_project_context` call creates a command-queue row that is marked approved in the same DB transaction as the GitHub push. The explicit natural-language push IS the approval semantically. Cross-approval is a clean v2 extension via a per-context `requires_cross_approval` flag — no infra needs to be built now. |
| Propose-update permission | **No new action**. `DEVSTACK_VIEW` covers both read and propose-update. Since every authenticated dev can already read the content, letting them propose changes is no privilege escalation. |
| Conflict UX | **Conversational by default**. The LLM presents the three versions (base / remote / local) in chat, proposes a merged version, and writes only after the dev agrees. If the dev wants to reason in their editor instead, they can ask the LLM to paste the three raw versions into the chat and copy them out — no formal `.conflict` file support in v1. A dedicated `./CLAUDE.md.conflict` fallback can be added in v2 if real demand appears. |
| Project-scoped permissions? | **No.** Trust-based; real gate is GitHub repo access. |
| Behaviour when context is deleted in VizzHub | Skill warns the dev on next sync (MCP returns `NOT_FOUND`) but does **not** delete the local `./CLAUDE.md`. Dev chooses to unlink explicitly. |

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Dev forgets to gitignore `CLAUDE.md` / marker files and commits them to the public repo | Skill enforces `.gitignore` entries on every sync (for `CLAUDE.md`, `.claude/.devstack-context`, `.claude/.devstack-skip`). Also add to public-repo onboarding template. |
| Slug collision between contexts | DB unique constraint on `slug`. UI validates on form submit. |
| Backend GitHub token loses read or write access to `project-contexts` repo | MCP returns `FETCH_FAILED` or `COMMIT_FAILED` with clear error shape. Skill surfaces the error to the dev and does not advance markers. Ops monitors via structlog. |
| Two devs push nearly simultaneously | The second push's `expected_remote_sha` no longer matches — backend returns `conflict` without any merge attempt. Skill enters the LLM-mediated merge flow, presents the other dev's changes to the current dev, and only retries push after explicit approval. Race is always visible, never silent. |
| Private content ends up in VizzHub logs | MCP tool response content is NOT logged (only SHA + slug + status). Enforced by: (1) an integration test that drives `devstack_get_project_context` (HEAD and `at_sha`) and `devstack_update_project_context` calls through the MCP layer and asserts that neither the input `content` nor the returned `content` substrings appear in captured `structlog` output; (2) explicit review of the Sentry/APM configuration to exclude request & response bodies from breadcrumbs and error payloads for both the REST endpoints (`/api/devstack/project-contexts/*`) and the MCP tool endpoints. |
| Concurrent Claude sessions (terminal + IDE) racing the `./CLAUDE.md` write | Skill uses tempfile + `os.rename` for every write (atomic on POSIX within the same filesystem). Worst case: one session's content wins; neither leaves a truncated file. |
| Dev publishes an accidental edit (typo, iteration mid-thought) that propagates to the team | Explicit natural-language push is the approval gate — the dev can't push by accident. Every commit is attributed to the dev in both the Git log and the auto-approved command queue row, so revert is `git revert <sha>` on the private repo; the next pull distributes the revert. For contexts where this risk is unacceptable, v2 introduces a `requires_cross_approval` flag that holds the commit in the pending queue until a second party approves. |
| LLM produces a flawed merge proposal (drops a bullet, hallucinates a word, misinterprets a change) | The dev reviews the proposal in chat before any write happens — nothing is applied without explicit *"aprobado"*. If the dev misses an error, the revert path is `git revert` on the private repo; the error is attributed to the dev, not the LLM, which keeps the audit trail meaningful. To reduce error rate, the skill instructs the LLM to quote relevant snippets from all three versions when proposing and to ask the dev when any change overlaps semantically (not just textually). |
| Non-determinism across devs merging the same conflict | Two devs merging the same divergence can produce slightly different text — both semantically valid for prose. The commit-queue row + git history record what was actually pushed, which is the compliance-relevant artefact. This is explicitly accepted as a trade-off for better prose-merge quality. |
| GitHub push fails mid-transaction (e.g. ref advanced between our SHA check and our update-ref) | Backend returns `COMMIT_FAILED`. Skill re-fetches remote head, re-enters merge flow if needed, and retries. No marker advancement unless push succeeds. |
| Command-queue table grows unbounded | DevStack context updates are infrequent (a few per project per week at most). Rely on the existing command-queue retention/archival policy; no special handling here. |

## Roadmap

1. **v1** (this spec) — read + write for `CLAUDE.md` at project root. Pull-automatic, push-explicit, LLM-mediated merge, auto-approved command queue.
2. **v2 — cross-approval flag** — optional `requires_cross_approval` boolean on `devstack_project_contexts`. When true, `devstack_update_project_context` enqueues a pending command that must be approved by a different dev through the existing command-queue UI. Targets high-sensitivity contexts where compliance requires peer review.
3. **v2 — per-project artifacts** — extend folder layout with `<slug>/skills/`, `<slug>/commands/`, etc.; add `devstack_list_project_artifacts(slug)` and a sibling `get` tool. Reuses the same optimistic-locked push infra.
4. **v2 — `.conflict` fallback** — if real demand emerges for file-based conflict resolution (dev prefers their editor), add an optional `./CLAUDE.md.conflict` output path and a `.gitignore` rule. Not built in v1.
5. **v3** (if needed) — project-scoped read permissions tied to VizzHub project membership (cross-references `project_users` or similar).
6. **v3** (if needed) — DevStack UI context editor (inline markdown, diff preview) that wraps `devstack_update_project_context` for admins without a Claude session.

## File locations

- Backend config: add `DEVSTACK_PROJECT_CONTEXTS_REPO` and `DEVSTACK_PROJECT_CONTEXTS_COMMITTER_NAME`/`_EMAIL` (bot identity) to `app/config.py`
- Backend model: `app/modules/devstack/models/project_context.py`
- Backend CRUD service: `app/modules/devstack/services/project_context_service.py`
- Backend GitHub I/O: `app/modules/devstack/services/project_context_github.py` — blob fetch (HEAD or by `at_sha`), optimistic-locked commit pipeline (verify current SHA → blob → tree → commit → update ref), author-field handling. No merge logic lives here.
- Backend API: `app/modules/devstack/api/project_contexts.py`
- MCP tools: add to `app/mcp/tools/devstack.py` (list / get / update — 3 tools)
- Command-queue integration: reuse `app/mcp/command_queue.py` (no new infra). A dedicated `command_type = "devstack_update_project_context"` string.
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
- A dev who edits `./CLAUDE.md` locally and says *"publica los cambios"* sees the commit appear in the private repo within seconds, with `author = <dev>` and `committer = <VizzHub bot>`, accompanied by a command-queue audit entry in the approved state.
- Two devs editing the same context concurrently experience a visible, never-silent outcome: whoever pushes second sees the optimistic lock fail, the skill enters the LLM-mediated merge flow, the dev reviews and approves a merge proposal, and the retry push commits cleanly.
- A dev who has iterated on `./CLAUDE.md` across multiple sessions without publishing receives the soft reminder once per session and never has their unpublished edits silently overwritten by pull.
- After a dev opts out (`N` at the prompt) the skill never prompts again for that project on any subsequent session.
- `CLAUDE.md` never appears in the public project's git history; `.claude/.devstack-context` and `.claude/.devstack-skip` also remain uncommitted.
- Integration tests confirm private content never appears in `structlog` or Sentry payloads for any of the three MCP tools (list / get / update) or the REST endpoints.
- Backend has no merge library dependency: the only string-manipulation code on the server side is the optimistic-lock check (SHA equality) and the commit pipeline (blob / tree / commit / update ref).
