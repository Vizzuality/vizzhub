"""Debug OAuth token and API access."""

import asyncio

from app.database import get_db
from app.core.services.oauth_service import OAuthService


async def debug_oauth():
    """Debug OAuth configuration."""
    async for db in get_db():
        # Get token info
        token = await OAuthService.get_valid_jira_token(db)
        site_info = await OAuthService.get_jira_site_info(db)

        print("🔍 OAuth Token Debug\n")
        print(f"Token exists: {token is not None}")
        if token:
            print(f"Token (first 20 chars): {token[:20]}...")
            print(f"Token length: {len(token)}")

        print("\n📍 Site Info:")
        print(f"Cloud ID: {site_info.get('cloud_id')}")
        print(f"Site URL: {site_info.get('site_url')}")

        # Test the actual API call
        import httpx

        if token and site_info:
            cloud_id = site_info["cloud_id"]
            base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"

            print("\n🌐 Testing API Call:")
            print(f"Base URL: {base_url}")
            print("Endpoint: /rest/api/3/myself")

            async with httpx.AsyncClient(
                base_url=base_url,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=30.0,
            ) as client:
                try:
                    response = await client.get("/rest/api/3/myself")
                    print(f"\n✅ Status: {response.status_code}")
                    if response.status_code == 200:
                        print(f"Response: {response.json()}")
                    else:
                        print(f"❌ Error: {response.text}")
                except Exception as e:
                    print(f"❌ Exception: {e}")

        break


if __name__ == "__main__":
    asyncio.run(debug_oauth())
