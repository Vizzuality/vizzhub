"""Jira issues endpoint for MyReport enrichment."""

import structlog
from calendar import monthrange
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.oauth_service import OAuthService
from app.core.services.jira_client import JiraClient

logger = structlog.get_logger()

router = APIRouter()


@router.get("")
async def get_jira_issues_for_period(
    db: DBSession,
    user: CurrentUser,
    period_date: Annotated[str, Query(description="Period date (YYYY-MM-DD, first of month)")],
) -> dict:
    """Return Jira issues the user worked on during a reporting period.

    Fetches issues that were In Progress during the period
    or moved to Done during the period.
    """
    try:
        parsed = date.fromisoformat(period_date)
    except ValueError:
        return {"issues": [], "error": "Invalid date format"}

    first_day = parsed.replace(day=1)
    last_day = first_day.replace(day=monthrange(first_day.year, first_day.month)[1])

    start_str = first_day.strftime("%Y-%m-%d")
    end_str = last_day.strftime("%Y-%m-%d")

    jql = (
        f'assignee = "{user.email}" AND '
        f'updatedDate >= "{start_str}" AND updatedDate <= "{end_str}" AND '
        f'statusCategory in ("In Progress", "Done")'
    )
    client = JiraClient(db=db)
    try:
        http = await client.get_client()
        response = await http.post(
            "/rest/api/3/search/jql",
            json={
                "jql": jql,
                "fields": ["summary", "status", "project", "issuetype"],
                "maxResults": 50,
            },
        )

        if response.status_code != 200:
            detail = response.text[:500]
            logger.warning(
                "jira_issues_query_failed",
                status_code=response.status_code,
                detail=detail,
                jql=jql,
            )
            return {"issues": [], "error": "Jira query failed"}

        data = response.json()
        issues = []
        for issue in data.get("issues", []):
            fields = issue.get("fields", {})
            project = fields.get("project", {})
            status = fields.get("status", {})
            issue_type = fields.get("issuetype", {})
            issues.append({
                "key": issue["key"],
                "summary": fields.get("summary", ""),
                "status": status.get("name", ""),
                "status_category": status.get("statusCategory", {}).get("name", ""),
                "project_key": project.get("key", ""),
                "project_name": project.get("name", ""),
                "issue_type": issue_type.get("name", ""),
            })

        site_info = await OAuthService.get_jira_site_info(db)
        site_url = site_info.get("site_url", "") if site_info else ""

        return {"issues": issues, "site_url": site_url}

    except Exception as e:
        logger.warning("jira_issues_fetch_failed", error=str(e))
        return {"issues": [], "error": "Jira connection failed"}
    finally:
        await client.close()
