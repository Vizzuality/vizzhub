# Code Quality Rollout — VizzHub Pilot

This document is the plan for adopting a Vizzuality code quality and
security baseline, with VizzHub as the pilot site.

> **Revised 2026-10-14.** The original six-phase plan (2026-05-17) stalled
> after Phase 3 for lack of capacity. A review of what actually shipped,
> what the data says, and what changed in the Tech Radar since then led to
> the leaner plan below. Shipped phases are kept under
> [What is in place](#what-is-in-place) so existing references
> ("Phase 1", "Phase 3") still resolve.

## Why the plan was revised

Five findings from the 2026-10-14 review:

1. **The PR gate never fires in VizzHub.** Semgrep and Gitleaks only fail
   on pull requests, but VizzHub had zero PRs in the previous 90 days:
   work is pushed straight to `dev`/`main` and neither branch is
   protected. The CI scans only report. VizzHub cannot validate a
   PR-centric design, and several Phase 1/3 exit criteria are unmeetable
   here.
2. **Findings are not triaged.** The Security tab held 55 open findings
   (43 Semgrep, 12 CodeQL), almost all from May, with zero dismissed or
   fixed. A scanner nobody reads adds noise, not safety.
3. **Three overlapping SAST tools.** SonarQube Cloud, Semgrep and CodeQL
   all run on VizzHub. CodeQL was dropped from the original plan for
   licensing cost, but the repo went public on 2026-05-19, which makes
   code scanning free.
4. **Phase 5 duplicated what already works.** Trivy fs, pip-audit and npm
   audit find the same thing as Dependabot alerts: vulnerable
   dependencies. VizzHub's Dependabot Slack alerts ("Peek") cut the
   median time-to-resolve for high/critical alerts from ~67 days to ~7
   days across 10 repos. The only dependency gap Dependabot leaves is OS
   packages inside Docker images.
5. **The Tech Radar moved.** ADR 001 made oxlint and oxfmt Adopt and put
   ESLint and Prettier on Hold, which settles the old "post-plan
   linter/formatter decision". Pyright is Adopt.

The lesson behind 2 and 4: **issues get fixed when someone is notified in
Slack with reminders, not when a scanner adds a row to a tab.** More
scanners have low marginal value; routing what existing scanners find to
a person has high value.

## Principles

1. **Every finding has an owner and a notification path.** A tool whose
   output nobody triages is removed, not kept "for visibility".
2. **One tool per job.** One SAST tool per repo, one dependency scanner
   (Dependabot), one secrets scanner (Gitleaks, plus GitHub secret
   scanning where free).
3. **Reuse what has proven itself** (Dependabot + Peek) before adding
   new infrastructure.
4. **Distribution by copy, not by framework.** At current capacity, a
   DevStack installable that copies a handful of files beats a versioned
   callable-workflow repo. Drift between copies is an accepted cost.
5. **No time commitments.** Steps gate on their exit criteria, not on the
   calendar.

---

## The plan

### Step 1 — Triage the backlog and pick one SAST tool per repo type

**Goal:** get the Security tab to zero untriaged findings, then stop
running overlapping scanners.

**Work:**
- Go through every open code scanning finding once. Fix the real ones;
  dismiss the rest with a reason (`false positive`, `won't fix` +
  justification), following the exception process in `SECURITY.md`.
- Decide the SAST tool per repo type:
  - **Public repos:** CodeQL (free; GitHub-native triage).
  - **Private repos:** SonarQube Cloud (Adopt; already paid).
  - **Semgrep** only where there is a real PR workflow that its
    diff-aware gate can protect.
- For VizzHub (public, no PRs): keep CodeQL + Sonar, remove the Semgrep
  job from `security.yml`, keep the Gitleaks job.

**Exit criteria:**
- Zero open findings without a triage decision.
- `security.yml` runs only the tools chosen above.

### Step 2 — Route code scanning and secret scanning alerts through Peek

**Goal:** apply the mechanism that demonstrably works to the findings
that currently sit unread.

**Work:**
- Extend VizzHub's alert job so that, for projects with alerts enabled,
  new **code scanning** alerts (high/critical, or error-level for tools
  without security severity) and new **secret scanning** alerts are
  posted to the project's Slack channel with the same reminder cadence
  as Dependabot (critical every 2 days, high every 7).
- Track them like Dependabot alerts so resolution time is measurable.
- Fix the known data-quality issues in the Dependabot tracker while there
  (a non-200 GitHub response currently marks every tracked alert as
  resolved; only the first page of alerts is read).

**Exit criteria:**
- A new finding of each kind reaches Slack within a day.
- Resolution-time metrics (median, P75, P90 by severity) are visible in
  the notifications Statistics tab.

### Step 3 — Minimum baseline for other repos, distributed via DevStack

**Goal:** give every Vizzuality repo the floor that VizzHub has proven,
with the least infrastructure.

**The baseline is only:**
- `SECURITY.md` (policy, SLAs, exception process).
- Gitleaks: `.gitleaks.toml`, the pre-commit hook, and the CI job.
- Dependabot alerts enabled on the repo.
- The project registered in VizzHub with alerts enabled (Peek).

**Distribution:** a DevStack installable that writes the files; enabling
Dependabot and registering the project are documented manual steps.

**Exit criteria:**
- The baseline is installed on two other repos without per-repo edits to
  the shared files.
- Both repos show up in Peek's metrics.

### Optional — Trivy image scan for repos that ship Docker images

Dependabot does not cover OS packages inside container images. For repos
that build images (VizzHub does), add a Trivy image scan at HIGH+ with
`--ignore-unfixed` to the deploy workflow. Trivy is Tech Radar **Trial**:
adopting it here needs the usual Trial confirmation.

---

## Dropped from the original plan

| Item | Why it was dropped |
|---|---|
| Phase 2 — `Vizzuality/quality-templates` callable workflow | Versioned workflow infrastructure is heavier than the value it adds at current capacity. Replaced by copy-based distribution (Step 3). |
| Phase 4 — Renovate in measuring mode | No current pain it solves; Dependabot is Adopt and its alerts already drive fixes. |
| Phase 5 — Trivy fs, pip-audit, npm audit nightlies | Duplicate Dependabot alerts. Only the image-scan gap survives (optional step). |
| Phase 5 — nightly Semgrep full scan | Superseded by one-SAST-per-repo (Step 1). |
| Phase 6 — Pyright as a CI gate | Pyright is Adopt and runs in editors via Pylance; a CI gate on an untyped codebase is the highest-friction item and has no owner today. Revisit only with capacity. |
| Post-plan linter/formatter evaluation | Settled by ADR 001 (oxlint/oxfmt Adopt, ESLint/Prettier Hold). VizzHub migrates opportunistically, as a small standalone task. |
| CodeQL exclusion | Reversed for public repos: code scanning is free there. |

---

## What is in place

### Phase 0 — Policy + local interface ✅ (2026-05-17)

- `SECURITY.md` at repo root: vulnerability policy, remediation SLAs
  (Critical 7d / High 30d / Medium 90d / Low quarterly), exception
  process, baseline-debt strategy.
- `[tool.ruff]` in `backend/pyproject.toml` (line-length 100, `py313`,
  E/F/I/B/UP/SIM). ~140 pre-existing violations tracked as baseline debt
  in `docs/audits/audit_findings.md`.
- `justfile` with `lint`, `format`, `security`, `ci`, `hooks` recipes.
- Frontend CI runs `npm run lint` (it previously only ran tests, which
  had hidden 3 ESLint errors).

**Notes worth keeping:**
- Ruff's auto-fix removed `# noqa: F401`-protected re-exports when the
  marker sat on the opening line of a multi-line import. Put `noqa` per
  imported name, or use `__all__`.
- The one-time mechanical reformat touched ~400 backend files with no
  semantic change; all tests passed.

Commits: `18a4ba65`, `4937788b`, `0948b359`, `e1ee69b0`, `fa8b43c2`,
`71ee6265`.

### Phase 1 — Local pre-commit + secret scanning ✅ (2026-05-19)

- `.pre-commit-config.yaml` run with `prek`: `gitleaks` → `ruff` →
  `ruff-format`. Install once per dev: `brew install prek && just hooks`.
- `.gitleaks.toml` (baseline allowlist) and `.gitleaksignore`
  (per-commit fingerprints, repo-specific).
- Zero findings across the full history with the calibrated config.

**Notes worth keeping:**
- Prefer `.gitleaksignore` fingerprints for one-off false positives;
  use config regexes only for whole families of placeholders.
- Both gitleaks config files contain secret-shaped strings by design and
  are allowlisted by path.
- `AKIAIOSFODNN7EXAMPLE` is allowlisted by gitleaks defaults; sanity-test
  with a fake `ghp_…` token instead.
- Hook versions are pinned to match `backend/pyproject.toml` so local
  hooks and CI stay in lockstep.

Commit: `90a68c0c`.

### Phase 3 — SAST + secrets in CI (SARIF) ✅ (2026-05-19)

`.github/workflows/security.yml`, VizzHub-local:
- Semgrep (`semgrep scan --config p/default`; diff-aware with
  `--baseline-commit` on PRs, full scan on push).
- Gitleaks via the upstream binary (the v2 action is paid for private
  org repos), pinned to the same version as the pre-commit hook.
- SARIF uploaded to the Security tab; PRs fail on net-new findings,
  pushes only report.
- Adds ~1 minute on parallel runners, nothing on the critical path.

Step 1 removes the Semgrep job from VizzHub.

Commits: `e8d4694a`, `4b1f2f83`.

### Outside the original plan

- **SonarQube Cloud** (Adopt) on VizzHub.
- **CodeQL** code scanning (free since the repo went public).
- **Dependabot alerts + Peek**: Slack notification with reminders for
  high/critical alerts; resolution tracked in
  `dependabot_alerts_tracked`.

---

## Decision log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-05-17 | Use `just`, not Make, as task runner | Tech Radar Trial; cleaner syntax, recipe discovery via `just --list`. |
| 2026-05-17 | Use `prek` for hooks | Tech Radar Trial; YAML compatible with `pre-commit`. |
| 2026-05-17 | `[tool.ruff] line-length = 100` | p99 of backend code was 89 chars; 100 avoided a reformatting wave. |
| 2026-05-17 | Ruff target `py313` | Matches `requires-python`. |
| 2026-05-17 | Drop CodeQL | GHAS licensing on private repos exceeds SonarQube Cloud spend. *Reversed for public repos on 2026-10-14.* |
| 2026-05-17 | SonarQube Cloud stays Adopt | Coexists with the baseline; one does not replace the other. |
| 2026-05-17 | `npm run lint` in frontend CI | Pre-existing ESLint errors had never failed CI. |
| 2026-05-19 | Gitleaks fingerprints for one-off exceptions | Surgical and self-expiring; regexes risk hiding real secrets. |
| 2026-05-19 | Pin hook versions to the backend's ruff version | Local hooks and CI stay in lockstep. |
| 2026-05-19 | Ship Phase 3 VizzHub-local, defer Phase 2 | A new org-wide repo was heavier than the unblocking value. |
| 2026-05-19 | Semgrep via `semgrep scan --baseline-commit`, not `semgrep ci` | `semgrep ci` needs a platform account. |
| 2026-05-19 | Gitleaks via upstream binary, not `gitleaks-action@v2` | Action v2 is paid for private org repos. |
| 2026-10-14 | Replace phases 2, 4, 5, 6 with Steps 1–3 | See [Why the plan was revised](#why-the-plan-was-revised). |
| 2026-10-14 | One SAST tool per repo type (CodeQL public, Sonar private, Semgrep only with PRs) | Three overlapping tools, none triaged. |
| 2026-10-14 | Route code/secret scanning alerts through Peek | Slack + reminders is the mechanism with measured results (~67d → ~7d median for Dependabot). |
| 2026-10-14 | Copy-based baseline distribution via DevStack | A versioned callable workflow is more infrastructure than current capacity supports. |

## Open questions

- Does the GitHub token VizzHub uses for Dependabot alerts also have
  access to code scanning and secret scanning alerts across orgs, or does
  Step 2 need an extra scope?
- After Step 1, do Sonar and CodeQL still report the same issue twice on
  VizzHub? If so, keep only one.
- Which two repos validate the Step 3 baseline? They should have a real
  PR workflow, unlike VizzHub.
