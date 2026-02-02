"""
Test script to verify Jira OAuth is working and collect metrics.

Usage:
    python test_jira_oauth.py <PROJECT_KEY>

Example:
    python test_jira_oauth.py FIP
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from pprint import pprint

from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)

from app.database import get_db
from app.services.collectors.jira import JiraCollector


async def test_jira_connection(project_key: str) -> None:
    """Test Jira OAuth connection and collect metrics."""
    print("\n🔍 Testing Jira OAuth connection...")
    print(f"📊 Project Key: {project_key}\n")

    async for db in get_db():
        collector = JiraCollector(db=db)

        # Test connection
        print("1️⃣ Testing connection...")
        try:
            is_connected = await collector.test_connection()
            if is_connected:
                print("   ✅ Connection successful!\n")
            else:
                print("   ❌ Connection failed!\n")
                print("   Trying to get more details...\n")
                # Try to see what's happening
                client = await collector._get_client()
                print(f"   Base URL: {client.base_url}")
                print(f"   Headers: {dict(client.headers)}")
                try:
                    response = await client.get("/rest/api/3/myself")
                    print(f"   Response status: {response.status_code}")
                    print(f"   Response body: {response.text[:500]}")
                except Exception as e:
                    print(f"   Error details: {type(e).__name__}: {e}")
                return
        except Exception as e:
            print(f"   ❌ Exception during test: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return

        # Collect metrics
        print("2️⃣ Collecting metrics...")
        try:
            metrics = await collector.collect(project_key=project_key)
            print("   ✅ Metrics collected successfully!\n")
            print("📈 Collected Metrics:")
            print("=" * 60)
            pprint(metrics, width=60)
            print("=" * 60)
        except Exception as e:
            print(f"   ❌ Error collecting metrics: {e}")
        finally:
            await collector.close()

        break


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_jira_oauth.py <PROJECT_KEY>")
        print("\nExample: python test_jira_oauth.py FIP")
        sys.exit(1)

    project_key = sys.argv[1].upper()
    asyncio.run(test_jira_connection(project_key))
