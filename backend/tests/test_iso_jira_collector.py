"""Tests for Jira ISO collector."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from app.core.token_encryption import encrypt_token
from app.core.models.oauth import OAuthTokenDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB


def _setup_collector_with_client(db_session):
    """Create a collector with a manually configured httpx client for unit tests."""
    from app.modules.iso.services.collectors.jira import JiraCollector

    collector = JiraCollector(db_session)
    collector._site_url = "https://company.atlassian.net"
    collector._cloud_id = "cloud-123"
    collector._token = "test-token"
    collector._client = httpx.AsyncClient(
        base_url="https://api.atlassian.com/ex/jira/cloud-123",
        headers={"Authorization": "Bearer test-token", "Accept": "application/json"},
        timeout=30.0,
    )
    return collector


def _make_response(json_data, status_code: int = 200):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


class TestCaptureValidation:
    @pytest.mark.asyncio
    async def test_capture_raises_when_no_token(self, db_session) -> None:
        from app.modules.iso.services.collectors.jira import JiraCollector

        collector = JiraCollector(db_session)
        with pytest.raises(ValueError, match="not configured"):
            await collector.capture()

    @pytest.mark.asyncio
    async def test_capture_raises_when_no_site_info(self, db_session) -> None:
        from app.modules.iso.services.collectors.jira import JiraCollector

        token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("test-token"),
            cloud_id=None,
            site_url=None,
        )
        db_session.add(token)
        await db_session.flush()

        collector = JiraCollector(db_session)
        with pytest.raises(ValueError, match="site info not configured"):
            await collector.capture()


class TestCollectUsers:
    @pytest.mark.asyncio
    async def test_returns_active_users(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        page1 = _make_response([
            {
                "accountId": "user-1",
                "emailAddress": "alice@company.com",
                "displayName": "Alice",
                "accountType": "atlassian",
                "active": True,
            },
            {
                "accountId": "user-2",
                "emailAddress": "bob@company.com",
                "displayName": "Bob",
                "accountType": "atlassian",
                "active": True,
            },
        ])
        page2 = _make_response([])

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[page1, page2],
        ):
            users = await collector.collect_users()

        assert len(users) == 2
        assert users[0] == {
            "account_id": "user-1",
            "email": "alice@company.com",
            "display_name": "Alice",
            "account_type": "atlassian",
            "is_external": False,
        }
        assert users[1]["account_id"] == "user-2"
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_filters_inactive_users(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        resp = _make_response([
            {
                "accountId": "user-1",
                "emailAddress": "alice@company.com",
                "displayName": "Alice",
                "accountType": "atlassian",
                "active": True,
            },
            {
                "accountId": "user-inactive",
                "emailAddress": "gone@company.com",
                "displayName": "Gone User",
                "accountType": "atlassian",
                "active": False,
            },
        ])
        empty = _make_response([])

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[resp, empty],
        ):
            users = await collector.collect_users()

        assert len(users) == 1
        assert users[0]["account_id"] == "user-1"
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_filters_app_and_customer_accounts(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        resp = _make_response([
            {
                "accountId": "user-1",
                "emailAddress": "alice@company.com",
                "displayName": "Alice",
                "accountType": "atlassian",
                "active": True,
            },
            {
                "accountId": "app-bot",
                "emailAddress": None,
                "displayName": "Automation Bot",
                "accountType": "app",
                "active": True,
            },
            {
                "accountId": "jsm-portal",
                "emailAddress": "alice@gmail.com",
                "displayName": "Alice Portal",
                "accountType": "customer",
                "active": True,
            },
        ])
        empty = _make_response([])

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[resp, empty],
        ):
            users = await collector.collect_users()

        assert len(users) == 1
        assert users[0]["account_id"] == "user-1"
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_detects_external_by_site_domain(self, db_session) -> None:
        """External = email domain != org domain derived from site_url."""
        collector = _setup_collector_with_client(db_session)
        # site_url is https://company.atlassian.net → org domain = company.com

        resp = _make_response([
            {
                "accountId": "user-1",
                "emailAddress": "alice@company.com",
                "displayName": "Alice",
                "accountType": "atlassian",
                "active": True,
            },
            {
                "accountId": "ext-1",
                "emailAddress": "external@vendor.com",
                "displayName": "External User",
                "accountType": "atlassian",
                "active": True,
            },
        ])
        empty = _make_response([])

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[resp, empty],
        ):
            users = await collector.collect_users()

        assert len(users) == 2
        assert users[0]["is_external"] is False
        assert users[1]["is_external"] is True
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_no_email_is_external(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        resp = _make_response([
            {
                "accountId": "user-1",
                "emailAddress": None,
                "displayName": "No Email",
                "accountType": "atlassian",
                "active": True,
            },
        ])
        empty = _make_response([])

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[resp, empty],
        ):
            users = await collector.collect_users()

        assert len(users) == 1
        assert users[0]["is_external"] is True
        await collector._client.aclose()


class TestGetOrgDomain:
    def test_derives_domain_from_site_url(self) -> None:
        from app.modules.iso.services.collectors.jira import JiraCollector

        collector = JiraCollector.__new__(JiraCollector)
        collector._site_url = "https://vizzuality.atlassian.net"
        assert collector._get_org_domain() == "vizzuality.com"

    def test_returns_none_when_no_site_url(self) -> None:
        from app.modules.iso.services.collectors.jira import JiraCollector

        collector = JiraCollector.__new__(JiraCollector)
        collector._site_url = None
        assert collector._get_org_domain() is None


class TestCollectGroups:
    @pytest.mark.asyncio
    async def test_returns_groups_from_bulk_api(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        page1 = _make_response({
            "values": [
                {"groupId": "grp-1", "name": "jira-administrators"},
                {"groupId": "grp-2", "name": "developers"},
            ],
            "isLast": False,
        })
        page2 = _make_response({
            "values": [
                {"groupId": "grp-3", "name": "design"},
            ],
            "isLast": True,
        })

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[page1, page2],
        ):
            groups = await collector.collect_groups()

        assert len(groups) == 3
        assert groups[0] == {"group_id": "grp-1", "name": "jira-administrators"}
        assert groups[1] == {"group_id": "grp-2", "name": "developers"}
        assert groups[2] == {"group_id": "grp-3", "name": "design"}
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_single_page(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        resp = _make_response({
            "values": [{"groupId": "grp-1", "name": "admins"}],
            "isLast": True,
        })

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            groups = await collector.collect_groups()

        assert len(groups) == 1
        await collector._client.aclose()


class TestCollectGroupMembers:
    @pytest.mark.asyncio
    async def test_builds_members_from_user_groups(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        users = [
            {"account_id": "user-1", "display_name": "Alice"},
            {"account_id": "user-2", "display_name": "Bob"},
        ]
        groups = [
            {"group_id": "grp-1", "name": "jira-administrators"},
            {"group_id": "grp-2", "name": "developers"},
        ]

        alice_groups = _make_response([
            {"name": "jira-administrators", "groupId": "grp-1"},
            {"name": "developers", "groupId": "grp-2"},
        ])
        bob_groups = _make_response([
            {"name": "developers", "groupId": "grp-2"},
        ])

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[alice_groups, bob_groups],
        ):
            result = await collector.collect_group_members(users, groups)

        assert "jira-administrators" in result
        assert "developers" in result
        assert len(result["jira-administrators"]) == 1
        assert result["jira-administrators"][0] == {
            "account_id": "user-1",
            "display_name": "Alice",
        }
        assert len(result["developers"]) == 2
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_skips_user_on_error(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        users = [
            {"account_id": "user-1", "display_name": "Alice"},
            {"account_id": "user-2", "display_name": "Bob"},
        ]
        groups = [{"group_id": "grp-1", "name": "developers"}]

        alice_groups = _make_response([{"name": "developers", "groupId": "grp-1"}])
        bob_error = _make_response([], status_code=403)

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[alice_groups, bob_error],
        ):
            result = await collector.collect_group_members(users, groups)

        assert len(result["developers"]) == 1
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_ignores_groups_not_in_list(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        users = [{"account_id": "user-1", "display_name": "Alice"}]
        groups = [{"group_id": "grp-1", "name": "developers"}]

        alice_groups = _make_response([
            {"name": "developers", "groupId": "grp-1"},
            {"name": "unknown-group", "groupId": "grp-99"},
        ])

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[alice_groups],
        ):
            result = await collector.collect_group_members(users, groups)

        assert len(result) == 1
        assert "unknown-group" not in result
        await collector._client.aclose()


class TestBuildSummary:
    def test_correct_counts(self) -> None:
        from app.modules.iso.services.collectors.jira import JiraCollector

        collector = JiraCollector.__new__(JiraCollector)

        data = {
            "users": [
                {"account_id": "user-1", "display_name": "Alice", "account_type": "atlassian", "is_external": False},
                {"account_id": "user-2", "display_name": "Bob", "account_type": "atlassian", "is_external": False},
                {"account_id": "ext-1", "display_name": "External", "account_type": "customer", "is_external": True},
            ],
            "groups": [
                {"group_id": "grp-1", "name": "jira-administrators"},
                {"group_id": "grp-2", "name": "developers"},
            ],
            "group_members": {
                "jira-administrators": [
                    {"account_id": "user-1", "display_name": "Alice"},
                ],
                "developers": [
                    {"account_id": "user-1", "display_name": "Alice"},
                    {"account_id": "user-2", "display_name": "Bob"},
                ],
            },
        }

        summary = collector._build_summary(data)

        assert summary["total_users"] == 3
        assert summary["total_admins"] == 1
        assert summary["total_groups"] == 2
        assert summary["external_users"] == 1

    def test_admins_from_site_admins_group(self) -> None:
        from app.modules.iso.services.collectors.jira import JiraCollector

        collector = JiraCollector.__new__(JiraCollector)

        data = {
            "users": [
                {"account_id": "user-1", "display_name": "Alice", "account_type": "atlassian", "is_external": False},
            ],
            "groups": [
                {"group_id": "grp-1", "name": "site-admins"},
            ],
            "group_members": {
                "site-admins": [
                    {"account_id": "user-1", "display_name": "Alice"},
                ],
            },
        }

        summary = collector._build_summary(data)
        assert summary["total_admins"] == 1

    def test_deduplicates_admins_across_groups(self) -> None:
        from app.modules.iso.services.collectors.jira import JiraCollector

        collector = JiraCollector.__new__(JiraCollector)

        data = {
            "users": [
                {"account_id": "user-1", "display_name": "Alice", "account_type": "atlassian", "is_external": False},
            ],
            "groups": [
                {"group_id": "grp-1", "name": "jira-administrators"},
                {"group_id": "grp-2", "name": "site-admins"},
            ],
            "group_members": {
                "jira-administrators": [
                    {"account_id": "user-1", "display_name": "Alice"},
                ],
                "site-admins": [
                    {"account_id": "user-1", "display_name": "Alice"},
                ],
            },
        }

        summary = collector._build_summary(data)
        assert summary["total_admins"] == 1


class TestBuildSourceMetadata:
    def test_build_source_metadata(self) -> None:
        from app.modules.iso.services.collectors.jira import JiraCollector

        collector = JiraCollector.__new__(JiraCollector)
        collector._site_url = "https://company.atlassian.net"

        meta = collector._build_source_metadata("manual")

        assert meta["site_url"] == "https://company.atlassian.net"
        assert meta["collector"] == "jira"
        assert meta["collector_version"] == "2"
        assert meta["run_mode"] == "manual"
        assert "read:jira-user" in meta["scopes"]


class TestCapture:
    @pytest.mark.asyncio
    async def test_capture_creates_snapshot(self, db_session) -> None:
        from app.modules.iso.services.collectors.jira import JiraCollector

        token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("test-token"),
            cloud_id="cloud-123",
            site_url="https://company.atlassian.net",
        )
        db_session.add(token)
        await db_session.flush()

        users_page = _make_response([
            {
                "accountId": "user-1",
                "emailAddress": "alice@company.com",
                "displayName": "Alice",
                "accountType": "atlassian",
                "active": True,
            },
        ])
        users_empty = _make_response([])
        groups_resp = _make_response({
            "values": [
                {"groupId": "grp-1", "name": "jira-administrators"},
                {"groupId": "grp-2", "name": "developers"},
            ],
            "isLast": True,
        })
        # /user/groups response for Alice (she's in both groups)
        alice_user_groups = _make_response([
            {"name": "jira-administrators", "groupId": "grp-1"},
            {"name": "developers", "groupId": "grp-2"},
        ])

        collector = JiraCollector(db_session)

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=[
                users_page,
                users_empty,
                groups_resp,
                alice_user_groups,
            ],
        ):
            snapshot = await collector.capture(run_mode="manual")

        assert isinstance(snapshot, AccessSnapshotDB)
        assert snapshot.provider == "jira"
        assert snapshot.data_version == "2"
        assert len(snapshot.data["users"]) == 1
        assert snapshot.data["users"][0]["display_name"] == "Alice"
        assert len(snapshot.data["groups"]) == 2
        assert "jira-administrators" in snapshot.data["group_members"]
        assert snapshot.summary["total_users"] == 1
        assert snapshot.summary["total_admins"] == 1
        assert snapshot.summary["total_groups"] == 2
        assert snapshot.summary["external_users"] == 0
        assert snapshot.source_metadata["site_url"] == "https://company.atlassian.net"

    @pytest.mark.asyncio
    async def test_capture_with_empty_site(self, db_session) -> None:
        from app.modules.iso.services.collectors.jira import JiraCollector

        token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("test-token"),
            cloud_id="cloud-123",
            site_url="https://empty.atlassian.net",
        )
        db_session.add(token)
        await db_session.flush()

        empty_users = _make_response([])
        empty_groups = _make_response({"values": [], "isLast": True})

        collector = JiraCollector(db_session)

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=[empty_users, empty_groups],
        ):
            snapshot = await collector.capture(run_mode="scheduled")

        assert snapshot.summary["total_users"] == 0
        assert snapshot.summary["total_admins"] == 0
        assert snapshot.summary["total_groups"] == 0
        assert snapshot.summary["external_users"] == 0
        assert snapshot.source_metadata["run_mode"] == "scheduled"
