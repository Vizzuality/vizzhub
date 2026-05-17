# Security Policy

## Reporting a vulnerability

Email `security@vizzuality.com`. Do not open public issues for security
findings. We acknowledge within two business days.

## Supported versions

The `main` branch and the most recent tagged release. Older releases
are not patched unless contractually required.

## Vulnerability handling

### Sources

Findings reach the GitHub Security tab through:

- Static analysis (SAST) on every PR and on a nightly schedule.
- Secrets detection in pre-commit hooks, PR scans, and nightly full-
  history scans.
- Dependency vulnerability scanning (Python and JavaScript ecosystems).
- Container, filesystem, and infrastructure-as-code vulnerability
  scanning (when applicable).
- GitHub Dependabot security advisories.
- SonarCloud, in repositories where it is enabled.

Each tool category uploads results to a separate SARIF category so that
dismissals and tracking history do not collide across tools.

### Triage

Every finding is routed to the owning team via `CODEOWNERS` and
relevant labels. The owning team triages within five business days.
Possible dispositions:

- **Fix.** PR opened, labeled `security`, prioritized per the SLA below.
- **Baseline.** Legacy finding pre-dating policy activation. Tracked
  in the baseline backlog (`tech-debt:security` label) and reviewed
  quarterly. Not blocking.
- **Risk-accepted.** Documented in the appropriate ignore file or in
  the GitHub Security tab dismissal with CVE/finding reference,
  decision date, review date, and approver.
- **False positive.** Dismissed with reason. If the false positive is
  structural (recurs across the codebase), tune the rule rather than
  dismissing case-by-case.

### Remediation SLAs

| Severity | Fix SLA          | Notes                                          |
| -------- | ---------------- | ---------------------------------------------- |
| Critical | 7 calendar days  | Patch or compensating control                  |
| High     | 30 calendar days | Patch or compensating control                  |
| Medium   | 90 calendar days | Batched with sprint planning                   |
| Low      | Quarterly review | Aggregated; addressed during dependency sweeps |

SLAs start at finding-detection time, not at triage time.

### Exception process

Risk-accepted findings require:

1. CVE ID or finding reference.
2. Reason the fix is deferred (no upstream patch, breaking change,
   compensating control in place, etc.).
3. Compensating control, if applicable.
4. Approver: engineering manager for High and below, CTO for Critical.
5. Review date no more than six months out.

Entries live in the appropriate ignore file (`.gitleaksignore`,
`.trivyignore`, `.pip-audit-ignore`, or a Security tab dismissal) with
the above fields recorded as a comment or dismissal reason.

### Baseline debt

Findings that existed before this policy activated on a repository are
tracked as `tech-debt:security` issues, reviewed quarterly. They are
not blocking. The PR gate fails only on findings introduced **after
baseline activation** for the repository.

This applies equally to lint rules, type-checking rules, and security
scanners. The principle is the same: existing violations are frozen,
new violations fail. Without this discipline, rolling new rules out
across a long-lived codebase floods the backlog and trains the team
to dismiss findings indiscriminately — the opposite of the policy's
purpose.

The baseline backlog is opportunistically reduced as code is touched
for other reasons (boy-scout cleanup). It is not a blocking quality
gate by itself.
