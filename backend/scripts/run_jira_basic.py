"""Quick test to check what data exists in the FIP project."""

import asyncio
import logging
from pathlib import Path
from pprint import pprint

from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')

from app.database import get_db
from app.services.collectors.jira import JiraCollector


async def test_basic_queries(project_key: str) -> None:
    """Test basic queries to understand project data."""
    print(f"\n🔍 Exploring project: {project_key}\n")

    async for db in get_db():
        collector = JiraCollector(db=db)
        client = await collector._get_client()

        # Test 1: Count ALL issues in project (using POST)
        print("1️⃣ Total issues in project (POST request):")
        try:
            response = await client.post(
                "/rest/api/3/search/jql",
                json={"jql": f"project = {project_key}", "maxResults": 1},
            )
            if response.status_code == 200:
                data = response.json()
                print(f"   Total: {data.get('total', 0)}")
                print(f"   Full response: {data}")
            else:
                print(f"   Error {response.status_code}: {response.text[:200]}")
        except Exception as e:
            print(f"   Exception: {e}")

        # Test 2: Get sample issues to see their structure
        print("\n2️⃣ Sample issues (first 3):")
        try:
            response = await client.get(
                "/rest/api/3/search/jql",
                params={
                    "jql": f"project = {project_key} ORDER BY created DESC",
                    "maxResults": 3,
                    "fields": "summary,issuetype,status",
                },
            )
            if response.status_code == 200:
                data = response.json()
                issues = data.get("issues", [])
                for issue in issues:
                    print(f"   - {issue['key']}: {issue['fields']['summary']}")
                    print(f"     Type: {issue['fields']['issuetype']['name']}")
                    print(f"     Status: {issue['fields']['status']['name']}")
            else:
                print(f"   Error {response.status_code}: {response.text[:200]}")
        except Exception as e:
            print(f"   Exception: {e}")

        # Test 3: Count by issue type
        print("\n3️⃣ Counting by issue type:")
        for issue_type in ["Bug", "Story", "Task", "Epic"]:
            try:
                response = await client.get(
                    "/rest/api/3/search/jql",
                    params={
                        "jql": f"project = {project_key} AND type = {issue_type}",
                        "maxResults": 1,
                    },
                )
                if response.status_code == 200:
                    total = response.json().get("total", 0)
                    print(f"   {issue_type}: {total}")
            except Exception:
                pass

        await collector.close()
        break


if __name__ == "__main__":
    import sys
    project_key = sys.argv[1].upper() if len(sys.argv) > 1 else "FIP"
    asyncio.run(test_basic_queries(project_key))
