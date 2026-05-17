"""Tests for projects API.

Tests cover:
- Jira project key uppercase conversion
- Pagination, filtering, sorting, lightweight mode
- Project manager filter and project-managers endpoint
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text


@pytest_asyncio.fixture
async def pm_user(db_session) -> dict:
    """Create a user to serve as project manager."""
    await db_session.execute(
        text(
            "INSERT INTO users (id, email, name, first_name, last_name, active) "
            "VALUES (gen_random_uuid(), 'pm@test.com', 'pm@test.com', 'Alice', 'Manager', true) "
            "RETURNING id"
        )
    )
    result = await db_session.execute(text("SELECT id FROM users WHERE email = 'pm@test.com'"))
    row = result.one()
    await db_session.commit()
    return {"id": str(row.id), "name": "Alice Manager"}


class TestJiraProjectKeyUppercase:
    """Test that jira_project_key is always uppercased via the API."""

    @pytest.mark.asyncio
    async def test_create_uppercases_key(self, client: AsyncClient) -> None:
        """POST /projects should uppercase jira_project_key."""
        response = await client.post(
            "/api/projects", json={"name": "Test", "code": "Test", "jira_project_key": "fip"}
        )
        assert response.status_code == 201
        assert response.json()["jira_project_key"] == "FIP"

    @pytest.mark.asyncio
    async def test_create_preserves_none(self, client: AsyncClient) -> None:
        """POST /projects should preserve None for jira_project_key."""
        response = await client.post("/api/projects", json={"name": "Test", "code": "Test"})
        assert response.status_code == 201
        assert response.json()["jira_project_key"] is None

    @pytest.mark.asyncio
    async def test_create_uppercases_mixed_case(self, client: AsyncClient) -> None:
        """POST /projects should uppercase mixed case keys."""
        for input_key, expected in [("Fip", "FIP"), ("fIp", "FIP"), ("proj-123", "PROJ-123")]:
            response = await client.post(
                "/api/projects",
                json={
                    "name": f"Test {input_key}",
                    "code": f"T{input_key}",
                    "jira_project_key": input_key,
                },
            )
            assert response.json()["jira_project_key"] == expected, f"Failed for {input_key}"


class TestProjectPagination:
    """Test paginated list endpoint."""

    @pytest.mark.asyncio
    async def test_default_pagination_shape(self, client: AsyncClient) -> None:
        """Response has correct pagination envelope."""
        response = await client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "pages" in data
        assert data["page"] == 1
        assert data["page_size"] == 45

    @pytest.mark.asyncio
    async def test_pagination_navigation(self, client: AsyncClient) -> None:
        """Page navigation returns correct slices."""
        for i in range(5):
            await client.post("/api/projects", json={"name": f"Project {i}", "code": f"P{i}"})

        response = await client.get("/api/projects", params={"page_size": 2, "page": 1})
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["pages"] == 3

        response = await client.get("/api/projects", params={"page_size": 2, "page": 3})
        data = response.json()
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, client: AsyncClient) -> None:
        """Search filters by name case-insensitively."""
        await client.post("/api/projects", json={"name": "Alpha Bravo", "code": "Alpha Bravo"})
        await client.post("/api/projects", json={"name": "Charlie Delta", "code": "Charlie Delta"})

        response = await client.get("/api/projects", params={"search": "alpha"})
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Alpha Bravo"

    @pytest.mark.asyncio
    async def test_search_escapes_wildcards(self, client: AsyncClient) -> None:
        """Search with SQL wildcards should not match everything."""
        await client.post("/api/projects", json={"name": "Alpha", "code": "Alpha"})
        await client.post("/api/projects", json={"name": "Bravo", "code": "Bravo"})

        response = await client.get("/api/projects", params={"search": "%"})
        assert response.json()["total"] == 0

        response = await client.get("/api/projects", params={"search": "_"})
        assert response.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_status_filter(self, client: AsyncClient) -> None:
        """Status filter returns only matching projects."""
        resp = await client.post("/api/projects", json={"name": "Active", "code": "Active"})
        pid = resp.json()["id"]
        await client.post("/api/projects", json={"name": "Done", "code": "Done"})
        await client.patch(f"/api/projects/{pid}", json={"status": "live"})

        response = await client.get("/api/projects", params={"status": "live"})
        data = response.json()
        for item in data["items"]:
            assert item["status"] == "live"

    @pytest.mark.asyncio
    async def test_date_range_filter(self, client: AsyncClient) -> None:
        """Date range filter returns matching projects."""
        await client.post(
            "/api/projects",
            json={"name": "Early", "code": "Early", "start_date": "2025-01-15"},
        )
        await client.post(
            "/api/projects",
            json={"name": "Late", "code": "Late", "start_date": "2025-06-15"},
        )

        response = await client.get(
            "/api/projects",
            params={"start_date_from": "2025-05-01"},
        )
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Late"

    @pytest.mark.asyncio
    async def test_combined_filters(self, client: AsyncClient) -> None:
        """Multiple filters combine with AND logic."""
        await client.post(
            "/api/projects",
            json={"name": "Alpha Active", "code": "Alpha Active", "start_date": "2025-03-01"},
        )
        await client.post(
            "/api/projects",
            json={"name": "Alpha Old", "code": "Alpha Old", "start_date": "2024-01-01"},
        )
        await client.post(
            "/api/projects",
            json={"name": "Bravo Active", "code": "Bravo Active", "start_date": "2025-03-01"},
        )

        response = await client.get(
            "/api/projects",
            params={
                "search": "Alpha",
                "start_date_from": "2025-01-01",
            },
        )
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Alpha Active"

    @pytest.mark.asyncio
    async def test_sort_asc(self, client: AsyncClient) -> None:
        """Sort by name ascending."""
        await client.post("/api/projects", json={"name": "Zulu", "code": "Zulu"})
        await client.post("/api/projects", json={"name": "Alpha", "code": "Alpha"})

        response = await client.get("/api/projects", params={"sort": "name", "order": "asc"})
        data = response.json()
        assert data["items"][0]["name"] == "Alpha"
        assert data["items"][1]["name"] == "Zulu"

    @pytest.mark.asyncio
    async def test_sort_desc(self, client: AsyncClient) -> None:
        """Sort by name descending."""
        await client.post("/api/projects", json={"name": "Alpha", "code": "Alpha"})
        await client.post("/api/projects", json={"name": "Zulu", "code": "Zulu"})

        response = await client.get("/api/projects", params={"sort": "name", "order": "desc"})
        data = response.json()
        assert data["items"][0]["name"] == "Zulu"
        assert data["items"][1]["name"] == "Alpha"

    @pytest.mark.asyncio
    async def test_invalid_sort_ignored(self, client: AsyncClient) -> None:
        """Invalid sort field falls back to created_at."""
        await client.post("/api/projects", json={"name": "Test", "code": "Test"})

        response = await client.get("/api/projects", params={"sort": "invalid_field"})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_results(self, client: AsyncClient) -> None:
        """Search with no matches returns empty items."""
        await client.post("/api/projects", json={"name": "Alpha", "code": "Alpha"})

        response = await client.get("/api/projects", params={"search": "nonexistent"})
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["pages"] == 1

    @pytest.mark.asyncio
    async def test_pagination_metadata(self, client: AsyncClient) -> None:
        """Pagination metadata is accurate."""
        for i in range(7):
            await client.post("/api/projects", json={"name": f"Project {i}", "code": f"P{i}"})

        response = await client.get("/api/projects", params={"page_size": 3, "page": 2})
        data = response.json()
        assert data["total"] == 7
        assert data["page"] == 2
        assert data["page_size"] == 3
        assert data["pages"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.asyncio
    async def test_search_resets_pagination_context(self, client: AsyncClient) -> None:
        """Searching while on page 2 returns from beginning of results."""
        for i in range(5):
            await client.post("/api/projects", json={"name": f"Project {i}", "code": f"P{i}"})

        response = await client.get(
            "/api/projects", params={"search": "Project", "page": 1, "page_size": 2}
        )
        data = response.json()
        assert data["total"] == 5
        assert data["page"] == 1
        assert len(data["items"]) == 2


class TestLightweightMode:
    """Test lightweight=true returns ProjectSummary list."""

    @pytest.mark.asyncio
    async def test_lightweight_returns_summaries(self, client: AsyncClient) -> None:
        """Lightweight mode returns id and name only."""
        await client.post("/api/projects", json={"name": "Project A", "code": "Project A"})
        await client.post("/api/projects", json={"name": "Project B", "code": "Project B"})

        response = await client.get("/api/projects", params={"lightweight": "true"})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        for item in data:
            assert "id" in item
            assert "name" in item
            assert "created_at" not in item

    @pytest.mark.asyncio
    async def test_lightweight_sorted_by_name(self, client: AsyncClient) -> None:
        """Lightweight results are sorted alphabetically by name."""
        await client.post("/api/projects", json={"name": "Zulu", "code": "Zulu"})
        await client.post("/api/projects", json={"name": "Alpha", "code": "Alpha"})

        response = await client.get("/api/projects", params={"lightweight": "true"})
        data = response.json()
        assert data[0]["name"] == "Alpha"
        assert data[1]["name"] == "Zulu"


class TestProjectManagerFilter:
    """Test project_manager_id filter and /project-managers endpoint."""

    @pytest.mark.asyncio
    async def test_project_managers_endpoint_empty(self, client: AsyncClient) -> None:
        """Returns empty list when no projects have PMs."""
        response = await client.get("/api/projects/project-managers")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_project_managers_endpoint_returns_assigned(
        self,
        client: AsyncClient,
        pm_user: dict,
    ) -> None:
        """Returns only users assigned as PM on at least one project."""
        await client.post(
            "/api/projects",
            json={"name": "PM Project", "code": "PMP", "project_manager_id": pm_user["id"]},
        )
        await client.post("/api/projects", json={"name": "No PM", "code": "NP"})

        response = await client.get("/api/projects/project-managers")
        assert response.status_code == 200
        pms = response.json()
        assert len(pms) == 1
        assert pms[0]["id"] == pm_user["id"]
        assert pms[0]["name"] == pm_user["name"]

    @pytest.mark.asyncio
    async def test_filter_by_project_manager(
        self,
        client: AsyncClient,
        pm_user: dict,
    ) -> None:
        """project_manager_id filter returns only matching projects."""
        await client.post(
            "/api/projects",
            json={"name": "Managed", "code": "MAN", "project_manager_id": pm_user["id"]},
        )
        await client.post("/api/projects", json={"name": "Unmanaged", "code": "UNM"})

        response = await client.get(
            "/api/projects",
            params={"project_manager_id": pm_user["id"]},
        )
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Managed"
