# Code Quality Rollout — VizzHub Pilot

This document is the phased plan for adopting the Vizzuality code quality
baseline on this repository. VizzHub is the pilot site; the goal of the
pilot is **content validation**, not infrastructure construction. Anything
that survives the pilot unchanged becomes a candidate for the `baseline`
artifact type in DevStack.

> The full org-wide proposal (30 repos, reusable workflow, nightly security,
> branch protection as code, baseline debt strategy) lives outside this
> repo. This document is its VizzHub-scoped subset.

## Strategic principles

Three rules drive every phase decision:

1. **The pilot validates content, not infra.** Any file we add must be one
   we'd want in literally every other Vizzuality repo, byte-for-byte. If a
   file needs per-repo tweaks during the pilot, it's not baseline material
   yet — set it aside.
2. **Order by feedback-loop value, not by completeness.** Each phase brings
   in the smallest unit that teaches us something concrete before the next
   decision. Cheap to roll back if a piece doesn't pull its weight.
3. **No time commitments.** Phases gate on exit criteria, not on calendar.
   A phase ships when its signal is stable, not when its week is up.

## Out of scope for this pilot

These belong to the org-wide rollout, not the pilot:

- **Biome migration.** ESLint works; tooling swap in the middle of a pilot
  confounds the signal. Decide post-pilot, migrate all repos together.
- **CodeQL.** Free only on public repos; on private repos requires
  GitHub Advanced Security (~$49/committer/month), which would exceed
  the cost of SonarCloud at Vizzuality scale. Semgrep covers SAST at
  the baseline level; SonarCloud covers it deeper in repos that adopt
  it. CodeQL adds no signal worth the licensing cost.
- **Branch protection as Terraform.** The TF module pays for itself
  starting at repo #2 or #3. For one repo, manual + drift is cheaper
  than the abstraction.
- **CODEOWNERS.** Routing value kicks in once 3+ teams ship to the repo.
  Single-team repos don't justify the maintenance.
- **Renovate at full org policy.** The pilot installs Renovate to measure
  PR volume, but does not commit to the org's automerge policy yet.

---

## Phase 0 — Policy + local interface ✅ Done (2026-05-17)

**Goal:** lock the pieces that have zero CI impact and that define the
policy everything else hangs on.

**Adds:**
- `SECURITY.md` at repo root — vuln policy, remediation SLAs, exception
  process, and the baseline-debt strategy in writing.
- `[tool.ruff]` section in `backend/pyproject.toml` — formalizes ad-hoc
  use already evident from `.ruff_cache`.
- `justfile` at repo root with `lint`, `format`, `security`, `ci`
  recipes — the same interface every future repo will have. `just` is
  the task runner; install with `brew install just` (one-time per dev,
  ~3s in CI via `extractions/setup-just@v2` pinned by SHA).

**Exit criteria:**
- ✅ `just lint` and `just format` run clean on a fresh checkout.
- ✅ `just` (no args) lists the four recipes with their doc comments.
- ✅ `SECURITY.md` SLA numbers and exception language treated as
  final-enough to ship verbatim to other repos.

**Why first:** zero CI churn, zero developer disruption, but it commits
the policy that every later phase relies on (the baseline-debt discipline
in particular).

**Implementation notes (2026-05-17):**

- **Line-length set to 100, not 88.** Codebase p99 line length is 89
  chars; bumping the limit to 100 covered existing code without forcing
  a reformatting wave. Recorded in Decision log below.
- **One-time mechanical commit was ~400 backend files.** `ruff --fix`
  applied I001/UP017/UP043/UP035/UP037/SIM* auto-fixes; `ruff format`
  ran Black-equivalent formatting. All 1936 backend tests pass post-
  change. Risk profile: pure mechanical, no semantic change.
- **Three pre-existing ESLint errors surfaced.** Frontend CI was only
  running `npm test`, not `npm run lint`. Phase 0 added the missing
  step in the same series of commits (`e1ee69b0`, ci.yml update in
  `71ee6265`). The fix is generic and should be carried into every
  repo's baseline going forward.
- **Ruff's auto-fix removed `# noqa: F401`-protected re-exports** when
  the noqa marker was on the opening line of a multi-line
  `from X import (...)` block. Six files affected (alembic env,
  `schemas/page.py` in two modules, `services/asset_service.py` in
  two modules, `worker/dependabot/shared.py`). Workaround: reverted
  to HEAD and added `F401` + `I001` to per-file-ignores. DevStack
  baseline should ship guidance to put noqa per-imported-name or use
  `__all__` instead of relying on the opening-line marker.
- **~140 violations tracked as baseline-debt** in
  `docs/audits/audit_findings.md` under "Minor → Phase 0 baseline-debt".
  PR gate enforces these rules going forward; existing violations are
  not back-fixed. Each `ignore = [...]` entry in `pyproject.toml` is
  removable once its category reaches zero violations.
- **Frontend CI now runs `npm run lint`.** Added in the same Phase 0
  series so the policy is operational from day one, not deferred to
  Phase 2 when the callable workflow lands.

**Shipped in commits:** `18a4ba65` (plan) · `4937788b` + `0948b359`
(backend mechanical) · `e1ee69b0` (frontend lint fixes) · `fa8b43c2`
(ruff config + SECURITY.md + justfile) · `71ee6265` (CI lint + audit
tracking).

---

## Phase 1 — Local pre-commit + secret scanning

**Goal:** catch secrets and lint regressions before they reach `origin`.

**Adds:**
- `.pre-commit-config.yaml` (the YAML format is compatible with both
  `pre-commit` and `prek`; we install `prek` per the Tech Radar — it's
  in Trial as a multi-language Husky replacement and is the radar's
  preferred path). Hooks:
  - `gitleaks` (first — fail before formatting runs)
  - `ruff-check --fix`
  - `ruff-format`
- `.gitleaks.toml` with the baseline allowlist (test fixtures, snapshots,
  `*.example`, common false positives).

**Exit criteria:**
- Hooks installed on Miguel's machine via `pre-commit install`.
- Two weeks of normal commits without `--no-verify` workarounds.
- Zero false-positive secret findings on existing fixtures/snapshots.
- If false positives appear, `.gitleaks.toml` is tuned **once** to fix
  them. If it needs tuning a second time, the rule is wrong, not the
  config — escalate before adding the second exception.

**Why second:** first contact with daily-work friction. Calibrating
`.gitleaks.toml` on one repo is much cheaper than calibrating it on 30.

**Explicitly excluded from pre-commit:** Pyright (too slow, encourages
`--no-verify`), Biome (still using ESLint), npm/eslint (project scripts
already cover it; pre-commit duplication isn't worth it for the pilot).

---

## Phase 2 — Reusable quality workflow (skeleton)

**Goal:** validate the callable-workflow distribution pattern with the
cheapest possible content, before piling features on it.

**Adds:**
- New repo `Vizzuality/quality-templates` with a callable workflow
  `python-ts-quality.yml`. First version contains **only**:
  - Ruff (`check` + `format --check`).
  - Conditional Biome step (skipped while `biome.json` is absent, kept
    in the workflow for forward-compat).
- In VizzHub, new `.github/workflows/quality.yml` — a 10-line caller
  pinned to `@v0.1.0`.
- Existing `ci.yml` untouched. The two workflows run in parallel.

**Exit criteria:**
- A bump from `@v0.1.0 → @v0.1.1` in the caller is a one-line PR and
  Renovate picks it up cleanly when added in Phase 4.
- The callable runs end-to-end on a real PR.
- No flakiness on three consecutive runs.

**Why before any scanner:** the workflow plumbing is what gets touched
most over time. Stress-test the callable pattern with trivial content
first — if it doesn't work for `ruff check`, it won't work for Semgrep
either. Failing early here is cheap.

---

## Phase 3 — SAST + secrets in PR gate (SARIF)

**Goal:** route security findings through GitHub's Security tab with
stable categories and SARIF history.

**Adds, into the same callable workflow:**
- Semgrep step. On `pull_request`: `semgrep ci` (diff-aware against
  base ref). On `push`: `semgrep scan` (full). SARIF uploaded with
  `category: semgrep`.
- Gitleaks action (PR-scoped). SARIF uploaded with `category: gitleaks`.
- `security-events: write` permission added to the caller in VizzHub.

**Exit criteria:**
- One PR that intentionally introduces a finding shows up in the
  Security tab under the correct category and **blocks merge**.
- Three weeks of real PRs without Semgrep + Sonar producing duplicate
  blocking findings on the same line. If duplicates happen, decide
  category dedup strategy before any other repo joins.
- The baseline-debt policy in `SECURITY.md` is exercised at least once
  — a legacy finding triaged as `baseline` instead of fixed.

**Why now and not earlier:** running SAST against a repo with years of
history without the baseline-debt policy in place would either flood the
backlog or train the team to dismiss findings. Phase 0 wrote the policy;
this phase is the first time we exercise it.

---

## Phase 4 — Renovate (measuring mode)

**Goal:** measure real PR volume and triage cost before committing to
the org-wide automerge policy.

**Adds:**
- Renovate App installed on the VizzHub repo (org-level install,
  scoped to VizzHub for now).
- `renovate.json` at repo root with `config:recommended`,
  `:dependencyDashboard`, weekly schedule, `prConcurrentLimit: 10`,
  grouping for quality tooling and GitHub Actions, **automerge OFF**.

**Exit criteria:**
- Four weeks of Renovate activity logged. Counted: PRs/week, time-to-
  merge, share of PRs that would have been safe to automerge in
  retrospect.
- A go/no-go decision on patch-automerge documented in this file
  (Decision Log below) with the measured numbers.

**Why this position in the sequence:** Renovate's overhead is the most
political item in the rollout. Measuring it on one repo first gives a
defensible number to bring to the team when proposing org-wide automerge.

---

## Phase 5 — Nightly security workflow

**Goal:** heavy scans that don't belong on the PR critical path.

**Adds:**
- `.github/workflows/nightly-security.yml` with a `detect` job that
  exports `has-python`, `has-js`, `has-node-lock`, `has-docker` outputs
  consumed by the rest.
- Jobs (each uploads SARIF with its own category):
  - Semgrep full scan
  - Gitleaks full history (CLI, explicit `--log-opts="--all"`)
  - Trivy fs (always, `--ignore-unfixed`)
  - Trivy image (only if Dockerfile present)
  - `pip-audit` via `scripts/pip-audit.sh` (lockfile-aware)
  - npm/pnpm/yarn audit at HIGH+

**Exit criteria:**
- Three consecutive nightly runs complete green or with only triaged
  findings.
- The detector job correctly enables/disables Python and Docker jobs
  (validated by `workflow_dispatch` on a Python-only and a JS-only
  fork or stub).
- Nightly Security-tab findings are routed (manually for now) to the
  right owner within five business days for two consecutive weeks.

**Why now and not earlier:** the PR-gate work (Phases 2–3) is the
critical path for developer experience. Nightlies are asynchronous and
add load to the Security tab — moving them in too early before the
triage rhythm exists creates an alert backlog with no owner.

**Explicitly excluded:** CodeQL. GHAS licensing cost on private repos
makes it economically worse than the current SonarCloud spend at
Vizzuality scale. Reconsider only if GitHub bundles CodeQL outside GHAS
or if the org adopts GHAS for other reasons.

---

## Phase 6 — Pyright with baseline debt

**Goal:** introduce static type checking on Python without flooding the
backlog or training the team to dismiss findings.

**Adds:**
- `pyrightconfig.json` at repo root, `typeCheckingMode: "standard"`,
  `pythonVersion: "3.13"`.
- Pyright step added to the callable workflow, behind a `run-pyright`
  input that defaults to `true`.
- A one-time baseline dump: all current Pyright findings dismissed via
  inline `# pyright: ignore[ruleName]` or moved into `pyrightconfig.json`
  `exclude`/`ignore` lists, tracked as `tech-debt:type-coverage` issues.

**Exit criteria:**
- New PRs fail on net-new Pyright findings; legacy findings stay green.
- Two weeks of PRs where the gate fires correctly (catches real
  regressions, no flood of legacy noise).
- A measurable downward trend in the `tech-debt:type-coverage` backlog
  over two months — or an explicit decision to freeze it.

**Why last:** Pyright on an untyped codebase is the highest-friction
single addition in the whole plan. Putting it last means every other
piece is stable; Pyright noise can be tuned in isolation without
contaminating the signal from other tools. Also gives the baseline-debt
policy (Phase 0 + 3) its hardest test before any of this leaves VizzHub.

---

## Promotion to DevStack `baseline` type

The pilot is ready to promote a piece of content to the DevStack catalog
(as part of the future `baseline` artifact type) when:

1. The file has not been edited for three weeks of normal work.
2. The file would apply byte-for-byte to **two other Vizzuality repos**
   without modification (validated by reading them, not by guessing).
3. The exit criteria of the phase that introduced the file have all
   been met.

Files that pass these checks become entries in `quality-templates`,
tagged with a SHA, and surfaced through `devstack_get_installable`
once the `baseline` artifact type is implemented in DevStack.

Files that fail these checks stay in VizzHub as repo-local. That's a
useful signal: VizzHub is more idiosyncratic than the baseline assumes,
and the baseline should not be forced onto it.

## What stays out of DevStack permanently

- `CODEOWNERS` — every repo needs its own.
- `renovate.json` `packageRules` overrides — repo-specific.
- Branch protection state — managed via Terraform module, not the
  catalog.
- `.gitleaksignore` (per-commit, per-repo) and `.trivyignore`
  (per-repo CVE acceptances) — these are exceptions, not baseline.

The DevStack baseline distributes only **policy and configuration that
should look identical across the org**. Anything per-repo lives in the
repo.

## Post-plan: linter/formatter decision

Out of scope for this pilot, but on the docket once it closes.

VizzHub currently uses ESLint v9 with a 35-line flat config (no Prettier).
The Tech Radar has three relevant entries:

- **Prettier** — Adopt (default formatter).
- **Biome** — Trial ("potential Prettier + ESLint replacement").
- **Oxlint + Oxfmt** — Trial ("replacement for ESLint" and "replacement
  for Prettier, 100% conformance").

The radar is hedging between Biome and Oxc for the same role. Promoting
one in the DevStack baseline is an org-level decision, not a VizzHub
one, but VizzHub is a reasonable proving ground for it.

**Working preference (subject to validation):** Oxc over Biome.
Rationale:

- Oxfmt's "100% Prettier conformance" means repos that already use
  Prettier migrate with zero formatting diff. Biome reformats and
  produces a 500-file diff per repo.
- Oxc is modular (Oxlint or Oxfmt independently); Biome is all-or-nothing.
- Switching back from Oxc to Prettier is cost-free; switching back from
  Biome requires another formatting diff. Reversible decisions beat
  irreversible ones when the upside is similar.
- The radar's own wording is more confident about Oxc ("replacement")
  than about Biome ("potential replacement").

**Pre-requisite before committing:** confirm Oxfmt has a stable release
(not RC, not beta) at decision time. If it's still pre-release, fall
back to Biome.

**What this looks like as an evaluation post-pilot:**

1. Pick one VizzHub branch. Apply Prettier (Adopt) first — produces
   a formatting baseline commit.
2. In a follow-up commit, swap Prettier for Oxfmt. Diff should be
   empty if conformance is real.
3. In a third commit, swap ESLint for Oxlint with the migration tool.
   Compare findings against current ESLint output.
4. Decide. Bring the data to the team. Update the radar entry from
   Trial to Adopt (or Hold) based on the result.

This evaluation only starts after Phase 6 exit criteria are met.

## Decision log

A running log of decisions made during the pilot. Add entries here as
phases conclude; this file is the durable record once memory ages out.

| Date | Phase | Decision | Reason |
|------|-------|----------|--------|
| 2026-05-17 | 0 | Use `just`, not Make, as task runner | Tech Radar Trial entry; cleaner syntax, no tab footguns, native recipe discovery via `just --list`. One-time `brew install just` cost accepted. |
| 2026-05-17 | 0 | Use `prek`, not `pre-commit` framework, for hooks | Tech Radar Trial entry positions `prek` as the Husky replacement; YAML format is `pre-commit`-compatible so no rewrite needed when prek matures. |
| 2026-05-17 | 0 | `[tool.ruff] line-length = 100` (not 88) | p99 of current backend code is 89 chars; setting to 100 covers existing code without forcing a reformatting wave. The user's personal CLAUDE.md prefers 88 but the project's reality wins at the project level. |
| 2026-05-17 | 0 | Target version `py313` | `pyproject.toml` already pins `requires-python = ">=3.13,<3.14"`; matching the runtime is uncontroversial. |
| 2026-05-17 | 0 | Drop CodeQL from the plan entirely | GHAS licensing on private repos (~$49/committer/month) exceeds current SonarCloud spend at Vizzuality scale. Semgrep covers SAST baseline; Sonar goes deeper where adopted. Reconsider only if GitHub unbundles CodeQL or org adopts GHAS for other reasons. |
| 2026-05-17 | 0 | Sonar stays Adopt (no sunset implied) | Sonar works where it's adopted; the new baseline (Semgrep, Gitleaks, Trivy) puts a floor under repos that don't have Sonar. They coexist; one does not replace the other. |
| 2026-05-17 | 0 | Add `npm run lint` to frontend CI as part of Phase 0 | Discovery surfaced during implementation: frontend job only ran `npm test`, so 3 pre-existing ESLint errors had never failed CI. Fix is generic, belongs in the baseline. |

## Open questions

- Does Sonar deduplicate well with Semgrep findings via SARIF category,
  or do we see the same finding twice in the Security tab? Resolved
  in Phase 3.
- What's the realistic Renovate PR volume per week on VizzHub, and how
  much of it is safe to automerge in retrospect? Resolved in Phase 4.
- Does `pyrightconfig.json` at repo root cause friction with the
  `backend/` subdirectory layout, or does the `exclude` glob handle it
  cleanly? Resolved in Phase 6.
- When is the right moment to promote `quality-templates` from "internal
  experimentation repo" to "DevStack-published baseline"? Answer depends
  on the outcome of all six phases.
