"""Quick test to check what data exists in the FIP project."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Configure logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

from app.database import get_db
from app.modules.scorecard.services.collectors.jira import JiraCollector

JIRA_SEARCH_ENDPOINT = "/rest/api/3/search/jql"


async def _execute_jira_request(
    client: Any,
    method: str,
    project_key: str,
    jql_suffix: str = "",
    max_results: int = 1,
    fields: str | None = None,
) -> dict | None:
    """Execute a Jira API request and return the response data or None on error."""
    jql = f"project = {project_key}{jql_suffix}"

    try:
        if method == "POST":
            response = await client.post(
                JIRA_SEARCH_ENDPOINT,
                json={"jql": jql, "maxResults": max_results},
            )
        else:
            params: dict[str, Any] = {"jql": jql, "maxResults": max_results}
            if fields:
                params["fields"] = fields
            response = await client.get(JIRA_SEARCH_ENDPOINT, params=params)

        if response.status_code != 200:
            print(f"   Error {response.status_code}: {response.text[:200]}")
            return None

        return response.json()
    except Exception as e:
        print(f"   Exception: {e}")
        return None


def _print_total_issues(data: dict) -> None:
    """Print total issues count from response data."""
    print(f"   Total: {data.get('total', 0)}")
    print(f"   Full response: {data}")


def _print_sample_issues(data: dict) -> None:
    """Print sample issues from response data."""
    issues = data.get("issues", [])
    for issue in issues:
        print(f"   - {issue['key']}: {issue['fields']['summary']}")
        print(f"     Type: {issue['fields']['issuetype']['name']}")
        print(f"     Status: {issue['fields']['status']['name']}")


async def _count_issues_by_type(client: Any, project_key: str) -> None:
    """Count and print issues by type."""
    for issue_type in ["Bug", "Story", "Task", "Epic"]:
        data = await _execute_jira_request(
            client,
            method="GET",
            project_key=project_key,
            jql_suffix=f" AND type = {issue_type}",
            max_results=1,
        )
        if data:
            print(f"   {issue_type}: {data.get('total', 0)}")


async def test_basic_queries(project_key: str) -> None:
    """Test basic queries to understand project data."""
    print(f"\n Exploring project: {project_key}\n")

    async for db in get_db():
        collector = JiraCollector(db=db)
        client = await collector._get_client()

        print("1. Total issues in project (POST request):")
        data = await _execute_jira_request(
            client, method="POST", project_key=project_key, max_results=1
        )
        if data:
            _print_total_issues(data)

        print("\n2. Sample issues (first 3):")
        data = await _execute_jira_request(
            client,
            method="GET",
            project_key=project_key,
            jql_suffix=" ORDER BY created DESC",
            max_results=3,
            fields="summary,issuetype,status",
        )
        if data:
            _print_sample_issues(data)

        print("\n3. Counting by issue type:")
        await _count_issues_by_type(client, project_key)

        await collector.close()
        break


if __name__ == "__main__":
    import sys

    project_key = sys.argv[1].upper() if len(sys.argv) > 1 else "FIP"
    asyncio.run(test_basic_queries(project_key))
