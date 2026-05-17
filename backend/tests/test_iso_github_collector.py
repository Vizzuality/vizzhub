"""Tests for GitHub collector."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.models.integration_setting import IntegrationSettingDB
from app.core.models.oauth import OAuthTokenDB
from app.core.token_encryption import encrypt_token
from app.modules.iso.models.access_snapshot import AccessSnapshotDB


def _setup_collector_with_client(db_session):
    """Create a collector with a manually configured httpx client for unit tests."""
    from app.modules.iso.services.collectors.github import GitHubCollector

    collector = GitHubCollector(db_session)
    collector._org = "my-org"
    collector._client = httpx.AsyncClient(
        base_url="https://api.github.com",
        headers={
            "Authorization": "Bearer ghp_test",
            "Accept": "application/vnd.github+json",
        },
        timeout=30.0,
    )
    return collector


def _make_response(json_data, link_header: str = "", status_code: int = 200):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.headers = {"Link": link_header} if link_header else {}
    return resp


class TestCaptureValidation:
    @pytest.mark.asyncio
    async def test_capture_raises_when_no_token(self, db_session) -> None:
        from app.modules.iso.services.collectors.github import GitHubCollector

        collector = GitHubCollector(db_session)
        with pytest.raises(ValueError, match="not configured"):
            await collector.capture()

    @pytest.mark.asyncio
    async def test_capture_raises_when_no_org_name(self, db_session) -> None:
        from app.modules.iso.services.collectors.github import GitHubCollector

        token = OAuthTokenDB(
            provider="github",
            access_token=encrypt_token("ghp_test"),
        )
        db_session.add(token)
        await db_session.flush()

        collector = GitHubCollector(db_session)
        with pytest.raises(ValueError, match="organization name not configured"):
            await collector.capture()


class TestParseLinkHeader:
    def test_parses_next_link(self) -> None:
        from app.modules.iso.services.collectors.github import GitHubCollector

        header = '<https://api.github.com/orgs/my-org/members?page=2>; rel="next", <https://api.github.com/orgs/my-org/members?page=5>; rel="last"'
        result = GitHubCollector._parse_next_link(header)
        assert result == "https://api.github.com/orgs/my-org/members?page=2"

    def test_returns_none_on_empty(self) -> None:
        from app.modules.iso.services.collectors.github import GitHubCollector

        assert GitHubCollector._parse_next_link("") is None

    def test_returns_none_when_no_next(self) -> None:
        from app.modules.iso.services.collectors.github import GitHubCollector

        header = '<https://api.github.com/orgs/my-org/members?page=1>; rel="prev", <https://api.github.com/orgs/my-org/members?page=5>; rel="last"'
        assert GitHubCollector._parse_next_link(header) is None


class TestPagination:
    @pytest.mark.asyncio
    async def test_paginate_single_page(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        resp = _make_response([{"login": "alice", "id": 1}])

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            result = await collector._paginate("/orgs/my-org/members")

        assert len(result) == 1
        assert result[0]["login"] == "alice"
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_paginate_multiple_pages(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        page1 = _make_response(
            [{"login": "alice"}],
            link_header='<https://api.github.com/orgs/my-org/members?page=2>; rel="next"',
        )
        page2 = _make_response([{"login": "bob"}])

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[page1, page2],
        ):
            result = await collector._paginate("/orgs/my-org/members")

        assert len(result) == 2
        assert result[0]["login"] == "alice"
        assert result[1]["login"] == "bob"
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_paginate_stops_on_non_list_response(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        resp = _make_response({"message": "Not Found"})

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            result = await collector._paginate("/orgs/my-org/members")

        assert result == []
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_paginate_sets_default_per_page(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        resp = _make_response([])
        mock_get = AsyncMock(return_value=resp)

        with patch.object(collector._client, "get", mock_get):
            await collector._paginate("/orgs/my-org/members")

        call_kwargs = mock_get.call_args
        assert call_kwargs.kwargs["params"]["per_page"] == 100
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_paginate_does_not_mutate_params(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        resp = _make_response([])

        original_params = {"type": "all"}

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            await collector._paginate("/orgs/my-org/repos", original_params)

        assert "per_page" not in original_params
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_paginate_optional_returns_empty_on_403(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        resp = _make_response({"message": "Forbidden"}, status_code=403)

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            result = await collector._paginate("/orgs/my-org/teams", optional=True)

        assert result == []
        await collector._client.aclose()


class TestCollectMembers:
    @pytest.mark.asyncio
    async def test_returns_members_with_roles_from_filter(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        admins_resp = _make_response([{"login": "alice", "id": 1}])
        all_members_resp = _make_response(
            [
                {"login": "alice", "id": 1},
                {"login": "bob", "id": 2},
            ]
        )
        alice_profile = _make_response({"name": "Alice A", "email": "alice@co.com"})
        bob_profile = _make_response({"name": "Bob B", "email": None})

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[admins_resp, all_members_resp, alice_profile, bob_profile],
        ):
            members = await collector.collect_members()

        assert len(members) == 2
        assert members[0] == {
            "login": "alice",
            "id": 1,
            "name": "Alice A",
            "email": "alice@co.com",
            "role": "admin",
        }
        assert members[1] == {
            "login": "bob",
            "id": 2,
            "name": "Bob B",
            "email": None,
            "role": "member",
        }
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_all_members_when_admin_filter_forbidden(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        admins_403 = _make_response({"message": "Forbidden"}, status_code=403)
        all_members_resp = _make_response([{"login": "carol", "id": 3}])
        carol_profile = _make_response({"name": None, "email": None})

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[admins_403, all_members_resp, carol_profile],
        ):
            members = await collector.collect_members()

        assert len(members) == 1
        assert members[0]["role"] == "member"
        await collector._client.aclose()


class TestCollectTeams:
    @pytest.mark.asyncio
    async def test_returns_normalized_teams(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        teams_resp = _make_response(
            [
                {
                    "id": 10,
                    "name": "Backend",
                    "slug": "backend",
                    "parent": {"slug": "engineering"},
                    "description": "Backend team",
                    "privacy": "closed",
                },
                {
                    "id": 11,
                    "name": "Frontend",
                    "slug": "frontend",
                    "parent": None,
                    "description": "",
                    "privacy": "secret",
                },
            ]
        )

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            return_value=teams_resp,
        ):
            teams = await collector.collect_teams()

        assert len(teams) == 2
        assert teams[0] == {
            "id": 10,
            "name": "Backend",
            "slug": "backend",
            "parent_slug": "engineering",
            "description": "Backend team",
            "privacy": "closed",
        }
        assert teams[1]["parent_slug"] is None
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_handles_missing_parent_key(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        teams_resp = _make_response(
            [
                {"id": 12, "name": "Ops", "slug": "ops"},
            ]
        )

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            return_value=teams_resp,
        ):
            teams = await collector.collect_teams()

        assert teams[0]["parent_slug"] is None
        await collector._client.aclose()


class TestCollectTeamMembers:
    @pytest.mark.asyncio
    async def test_returns_per_team_member_dict(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        maintainers_resp = _make_response([{"login": "alice"}])
        all_team_resp = _make_response(
            [
                {"login": "alice"},
                {"login": "bob"},
            ]
        )
        teams = [{"slug": "backend"}]

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[maintainers_resp, all_team_resp],
        ):
            result = await collector.collect_team_members(teams)

        assert "backend" in result
        assert len(result["backend"]) == 2
        assert result["backend"][0] == {"login": "alice", "role": "maintainer"}
        assert result["backend"][1] == {"login": "bob", "role": "member"}
        await collector._client.aclose()

    @pytest.mark.asyncio
    async def test_empty_team(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        empty_resp = _make_response([])
        teams = [{"slug": "empty-team"}]

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[empty_resp, empty_resp],
        ):
            result = await collector.collect_team_members(teams)

        assert result["empty-team"] == []
        await collector._client.aclose()


class TestCollectOutsideCollaborators:
    @pytest.mark.asyncio
    async def test_returns_normalized_list_with_profile(self, db_session) -> None:
        collector = _setup_collector_with_client(db_session)

        outside_resp = _make_response(
            [
                {"login": "external-user", "id": 999},
            ]
        )
        profile_resp = _make_response({"name": "Ext User", "email": "ext@co.com"})

        with patch.object(
            collector._client,
            "get",
            new_callable=AsyncMock,
            side_effect=[outside_resp, profile_resp],
        ):
            result = await collector.collect_outside_collaborators()

        assert len(result) == 1
        assert result[0] == {
            "login": "external-user",
            "id": 999,
            "name": "Ext User",
            "email": "ext@co.com",
        }
        await collector._client.aclose()


class TestBuildSummary:
    def test_correct_counts(self) -> None:
        from app.modules.iso.services.collectors.github import GitHubCollector

        collector = GitHubCollector.__new__(GitHubCollector)
        collector._org = "my-org"

        data = {
            "members": [
                {"login": "alice", "id": 1, "role": "admin"},
                {"login": "bob", "id": 2, "role": "member"},
                {"login": "carol", "id": 3, "role": "admin"},
            ],
            "teams": [
                {"id": 10, "name": "Backend", "slug": "backend"},
                {"id": 11, "name": "Frontend", "slug": "frontend"},
            ],
            "outside_collaborators": [
                {"login": "ext", "id": 999},
            ],
        }

        summary = collector._build_summary(data)

        assert summary["total_members"] == 3
        assert summary["total_admins"] == 2
        assert summary["total_teams"] == 2
        assert summary["outside_collaborators"] == 1
        assert "total_repos" not in summary


class TestBuildSourceMetadata:
    def test_build_source_metadata(self) -> None:
        from app.modules.iso.services.collectors.github import GitHubCollector

        collector = GitHubCollector.__new__(GitHubCollector)
        collector._org = "my-org"

        meta = collector._build_source_metadata("manual")

        assert meta["org"] == "my-org"
        assert meta["collector"] == "github"
        assert meta["collector_version"] == "2"
        assert meta["run_mode"] == "manual"
        assert "read:org" in meta["scopes"]


class TestCapture:
    @pytest.mark.asyncio
    async def test_capture_creates_snapshot(self, db_session) -> None:
        from app.modules.iso.services.collectors.github import GitHubCollector

        token = OAuthTokenDB(
            provider="github",
            access_token=encrypt_token("ghp_test"),
        )
        db_session.add(token)
        setting = IntegrationSettingDB(
            provider="github",
            key="iso_org_name",
            value="my-org",
        )
        db_session.add(setting)
        await db_session.flush()

        admins_resp = _make_response([{"login": "alice", "id": 1}])
        all_members_resp = _make_response([{"login": "alice", "id": 1}])
        alice_profile = _make_response({"name": "Alice", "email": "a@co.com"})
        teams_resp = _make_response(
            [
                {"id": 10, "name": "Backend", "slug": "backend", "parent": None},
            ]
        )
        maintainers_resp = _make_response([{"login": "alice"}])
        team_all_resp = _make_response([{"login": "alice"}])
        outside_resp = _make_response([{"login": "ext-user", "id": 500}])
        ext_profile = _make_response({"name": "Ext", "email": None})

        collector = GitHubCollector(db_session)

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=[
                admins_resp,
                all_members_resp,
                alice_profile,
                teams_resp,
                maintainers_resp,
                team_all_resp,
                outside_resp,
                ext_profile,
            ],
        ):
            snapshot = await collector.capture(run_mode="manual")

        assert isinstance(snapshot, AccessSnapshotDB)
        assert snapshot.provider == "github"
        assert snapshot.data_version == "2"
        assert len(snapshot.data["members"]) == 1
        assert snapshot.data["members"][0]["role"] == "admin"
        assert snapshot.data["members"][0]["name"] == "Alice"
        assert len(snapshot.data["teams"]) == 1
        assert "repos" not in snapshot.data
        assert len(snapshot.data["outside_collaborators"]) == 1
        assert snapshot.summary["total_members"] == 1
        assert snapshot.summary["total_admins"] == 1
        assert snapshot.summary["total_teams"] == 1
        assert "total_repos" not in snapshot.summary
        assert snapshot.summary["outside_collaborators"] == 1
        assert snapshot.source_metadata["org"] == "my-org"

    @pytest.mark.asyncio
    async def test_capture_with_empty_org(self, db_session) -> None:
        from app.modules.iso.services.collectors.github import GitHubCollector

        token = OAuthTokenDB(
            provider="github",
            access_token=encrypt_token("ghp_test"),
        )
        db_session.add(token)
        setting = IntegrationSettingDB(
            provider="github",
            key="iso_org_name",
            value="empty-org",
        )
        db_session.add(setting)
        await db_session.flush()

        empty_resp = _make_response([])

        collector = GitHubCollector(db_session)

        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=[empty_resp, empty_resp, empty_resp, empty_resp],
        ):
            snapshot = await collector.capture(run_mode="scheduled")

        assert snapshot.summary["total_members"] == 0
        assert snapshot.summary["total_admins"] == 0
        assert snapshot.summary["total_teams"] == 0
        assert snapshot.summary["outside_collaborators"] == 0
        assert snapshot.source_metadata["run_mode"] == "scheduled"
