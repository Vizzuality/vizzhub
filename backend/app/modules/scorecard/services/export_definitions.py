"""Metric definitions for XLSX export — names, descriptions, formulas for ISO audits."""


INDICATOR_DEFINITIONS: dict[str, dict[str, str]] = {
    "spi": {
        "name": "Schedule Performance Index",
        "description": "Ratio of earned value to planned value. Measures schedule efficiency.",
        "formula": "EV / PV (where EV = budget_total * percent_completed, PV = budget_total * percent_planned)",
    },
    "on_time_milestones": {
        "name": "On-Time Milestones",
        "description": "Weighted ratio of milestones delivered on time, with grace period.",
        "formula": "Sum(weight * on_time) / Sum(weight) for each milestone",
    },
    "cpi": {
        "name": "Cost Performance Index",
        "description": "Ratio of earned value to actual cost. Measures cost efficiency.",
        "formula": "EV / AC (where EV = budget_total * percent_completed, AC = cost_to_date)",
    },
    "budget_variance": {
        "name": "Budget Variance",
        "description": "Percentage of budget overrun.",
        "formula": "(cost_to_date - planned_cost) / budget_total * 100",
    },
    "defect_density": {
        "name": "Defect Density",
        "description": "Number of bugs per 100 completed tasks.",
        "formula": "(bugs_total / tasks_completed) * 100",
    },
    "escaped_rate": {
        "name": "Escaped Defect Rate",
        "description": "Escaped defects per 100 completed tasks.",
        "formula": "(escaped_defects / tasks_completed) * 100",
    },
    "mttr_hours": {
        "name": "Mean Time to Recovery",
        "description": "Average hours to resolve incidents.",
        "formula": "mttr_hours (from Jira resolution times)",
    },
    "governance_compliance": {
        "name": "Governance Compliance",
        "description": "Compliance based on number of governance exceptions.",
        "formula": "max(0, 1 - (exceptions / target)). Zero exceptions = 1.0",
    },
    "story_review_ratio": {
        "name": "Story Review Ratio",
        "description": "Ratio of stories that had a reviewer assigned.",
        "formula": "stories_with_reviewer / total_stories",
    },
    "pr_review_ratio": {
        "name": "PR Review Ratio",
        "description": "Ratio of PRs merged with at least one review.",
        "formula": "(total_merged_prs - prs_without_review) / total_merged_prs",
    },
    "change_failure_rate": {
        "name": "Change Failure Rate",
        "description": "Percentage of releases that caused failures (DORA metric).",
        "formula": "failed_releases / total_releases * 100",
    },
    "post_contract_tasks": {
        "name": "Post-Contract Tasks",
        "description": "Tasks created more than 30 days after contract end date.",
        "formula": "Count of tasks created > 30 days after project end_date",
    },
    "okr_impact": {
        "name": "Strategic Impact",
        "description": "Assessment of project's strategic value to the organization.",
        "formula": "LOW=0.25, MEDIUM=0.55, HIGH=0.80, TRANSFORMATIONAL=1.0",
    },
    "pm_satisfaction": {
        "name": "PM Satisfaction",
        "description": "Project manager's estimation of client satisfaction.",
        "formula": "Weighted score from delivery complaints, design complaints, overall estimation",
    },
    "client_satisfaction": {
        "name": "Client Survey Score",
        "description": "Weighted average of 8 client survey questions (1-5 scale).",
        "formula": "Sum(question_score * question_weight) / Sum(question_weight), normalized to 0-1",
    },
    "lead_time_days": {
        "name": "Lead Time",
        "description": "Average days from issue creation to completion.",
        "formula": "Average (done_date - created_date) for completed issues",
    },
    "commitment_reliability": {
        "name": "Commitment Reliability",
        "description": "Ratio of issues completed within a single sprint.",
        "formula": "single_sprint_issues / committed_issues",
    },
    "pr_size_median": {
        "name": "PR Size (Median)",
        "description": "Median number of changed lines per pull request.",
        "formula": "Median(additions + deletions) across merged PRs",
    },
    "review_turnaround_hours": {
        "name": "Review Turnaround",
        "description": "Median hours from PR creation to first review.",
        "formula": "Median(first_review_time - pr_created_time) for reviewed PRs",
    },
    "deployment_frequency": {
        "name": "Deployment Frequency",
        "description": "Average releases per day over 90-day window (DORA metric).",
        "formula": "release_count_90d / 90",
    },
    "test_maturity": {
        "name": "Test Maturity",
        "description": "Weighted score across 5 testing dimensions (1-5 scale each).",
        "formula": "Sum(dimension_score * dimension_weight) / (5 * Sum(weights)), normalized to 0-1",
    },
    "arch_checklist": {
        "name": "Architecture Checklist",
        "description": "Completion ratio of architecture best practices.",
        "formula": "completed_items / total_items (docs, IaC, ADRs, diagrams)",
    },
    "prs_without_review": {
        "name": "PRs Without Review",
        "description": "Count of pull requests merged without any review.",
        "formula": "Count of PRs with 0 reviews at merge time",
    },
    "high_vulns": {
        "name": "High Severity Vulnerabilities",
        "description": "High/critical vulnerabilities unresolved for >30 days.",
        "formula": "Count from Dependabot alerts (high + critical, open > 30 days)",
    },
}


DIMENSION_DEFINITIONS: list[dict] = [
    {
        "key": "p_time",
        "name": "P_time — Schedule",
        "description": "Schedule adherence measured through earned value and milestone delivery.",
        "formula": "w_spi * normalize(SPI, ideal) + w_milestones * normalize(on_time_milestones, target)",
        "indicators": ["spi", "on_time_milestones"],
    },
    {
        "key": "p_cost",
        "name": "P_cost — Budget",
        "description": "Budget adherence measured through cost performance index and variance.",
        "formula": "w_cpi * normalize(CPI, ideal) + w_variance * normalize(budget_variance, target)",
        "indicators": ["cpi", "budget_variance"],
    },
    {
        "key": "p_quality",
        "name": "P_quality — Quality",
        "description": "Software quality across defects, governance, reviews, and failure rates. Capped at 60 if Sev1 incident.",
        "formula": "weighted_avg(defect_density, escaped_rate, mttr, story_review, governance, pr_review, change_failure_rate, post_contract_tasks). Sev1 cap applied.",
        "indicators": [
            "defect_density", "escaped_rate", "mttr_hours",
            "governance_compliance", "story_review_ratio", "pr_review_ratio",
            "change_failure_rate", "post_contract_tasks",
        ],
    },
    {
        "key": "p_value",
        "name": "P_value — Strategic Value",
        "description": "Strategic impact assessment of the project.",
        "formula": "w_okr * normalize(okr_impact)",
        "indicators": ["okr_impact"],
    },
    {
        "key": "p_satisfaction",
        "name": "P_satisfaction — Satisfaction",
        "description": "Stakeholder satisfaction from PM estimation and client survey.",
        "formula": "w_client * normalize(client_survey) + w_pm * normalize(pm_estimation)",
        "indicators": ["pm_satisfaction", "client_satisfaction"],
    },
    {
        "key": "p_flow",
        "name": "P_flow — Flow & Predictability",
        "description": "Development flow efficiency and predictability.",
        "formula": "weighted_avg(lead_time, commitment_reliability, pr_size, review_turnaround, deployment_frequency)",
        "indicators": [
            "lead_time_days", "commitment_reliability", "pr_size_median",
            "review_turnaround_hours", "deployment_frequency",
        ],
    },
    {
        "key": "p_engineering",
        "name": "P_engineering — Engineering Maturity",
        "description": "Engineering practices maturity across testing, reviews, and architecture.",
        "formula": "weighted_avg(test_maturity, pr_review, architecture)",
        "indicators": ["test_maturity", "pr_review_ratio", "arch_checklist"],
    },
    {
        "key": "p_risk",
        "name": "P_risk — Risk Posture",
        "description": "Risk exposure from unreviewed code and security vulnerabilities.",
        "formula": "weighted_avg(pr_no_review_penalty, high_vulns_penalty)",
        "indicators": ["prs_without_review", "high_vulns"],
    },
]


def get_metric_rows() -> list[dict]:
    """Build hierarchical list of metric rows for the XLSX Metrics sheet.

    Returns list of dicts with keys: level, key, name, description, formula.
    Level 0 = final score, level 1 = dimension, level 2 = indicator.
    """
    rows: list[dict] = []

    rows.append({
        "level": 0,
        "key": "final_score",
        "name": "FINAL SCORE",
        "description": "Weighted aggregate of all 8 dimension scores.",
        "formula": "Sum(dimension_score * global_weight) for active dimensions",
    })

    for dim in DIMENSION_DEFINITIONS:
        rows.append({
            "level": 1,
            "key": dim["key"],
            "name": dim["name"],
            "description": dim["description"],
            "formula": dim["formula"],
        })
        for ind_key in dim["indicators"]:
            ind = INDICATOR_DEFINITIONS[ind_key]
            rows.append({
                "level": 2,
                "key": ind_key,
                "name": ind["name"],
                "description": ind["description"],
                "formula": ind["formula"],
            })

    return rows
