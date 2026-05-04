"""Tests for mcp_server.data.iso — registry queries."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models import (
    IsoDocMetadataDB,
    IsoDocNodeDB,
    IsoDocVersionDB,
    RegistryRowDB,
    RegistryTypeDB,
)


@pytest_asyncio.fixture
async def seed_registry_types(db_session: AsyncSession) -> list[RegistryTypeDB]:
    rt1 = RegistryTypeDB(
        name="Incident Register",
        slug="incident-register",
        description="Security incidents per ISO 27001 A.16",
        is_yearly=True,
        schema=[
            {"key": "number", "label": "Number", "type": "string", "required": True},
            {"key": "date", "label": "Date", "type": "date"},
            {"key": "severity", "label": "Severity", "type": "select",
             "options": ["Critical", "High", "Medium", "Low"]},
        ],
    )
    rt2 = RegistryTypeDB(
        name="Risk Treatment Plan",
        slug="risk-treatment-plan",
        description="Risk treatment actions per ISO 27001 6.1.3",
        is_yearly=False,
        schema=[
            {"key": "risk", "label": "Risk", "type": "string", "required": True},
            {"key": "treatment", "label": "Treatment", "type": "string"},
        ],
    )
    db_session.add_all([rt1, rt2])
    await db_session.commit()
    return [rt1, rt2]


@pytest.mark.asyncio
async def test_get_registry_types_returns_all(
    db_session: AsyncSession, seed_registry_types: list[RegistryTypeDB],
) -> None:
    from mcp_server.data.iso import get_registry_types

    result = await get_registry_types(db_session)
    assert len(result) == 2
    type_slugs = [rt.slug for rt, _ in result]
    assert "incident-register" in type_slugs
    assert "risk-treatment-plan" in type_slugs


@pytest.mark.asyncio
async def test_get_registry_types_ordered_by_name(
    db_session: AsyncSession, seed_registry_types: list[RegistryTypeDB],
) -> None:
    from mcp_server.data.iso import get_registry_types

    result = await get_registry_types(db_session)
    names = [rt.name for rt, _ in result]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_get_registry_types_returns_node_slug_when_mounted(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import get_registry_types

    result = await get_registry_types(db_session)
    by_type = {rt.slug: node_slug for rt, node_slug in result}
    # incident-register is mounted (fixture creates a node), risk-treatment-plan is not
    assert by_type["incident-register"] == "incident-register"
    assert by_type["risk-treatment-plan"] is None


@pytest.mark.asyncio
async def test_get_registry_types_node_slug_can_diverge_from_type_slug(
    db_session: AsyncSession,
) -> None:
    """Regression: when the title contains non-URL-safe chars, the node
    slug is sanitised but the registry type slug isn't, so the two diverge.
    The MCP read tool must surface the node slug as the canonical id."""
    from mcp_server.data.iso import get_registry_types

    rt = RegistryTypeDB(
        name="Audit Plan & Results",
        slug="audit-plan-&-results",
        description="Annual audit plan",
        is_yearly=True,
        schema=[{"key": "title", "label": "Title", "type": "string"}],
    )
    db_session.add(rt)
    await db_session.flush()
    db_session.add(IsoDocNodeDB(
        title="Audit Plan & Results",
        slug="audit-plan-results",
        type="registry",
        registry_type_id=rt.id,
    ))
    await db_session.commit()

    result = await get_registry_types(db_session)
    by_type = {rt.slug: node_slug for rt, node_slug in result}
    assert by_type["audit-plan-&-results"] == "audit-plan-results"


@pytest_asyncio.fixture
async def seed_registry_with_rows(
    db_session: AsyncSession, seed_registry_types: list[RegistryTypeDB],
) -> dict:
    rt = seed_registry_types[0]  # incident-register, is_yearly=True
    node = IsoDocNodeDB(
        title="Incident Register",
        slug="incident-register",
        type="registry",
        registry_type_id=rt.id,
    )
    db_session.add(node)
    await db_session.flush()

    rows = [
        RegistryRowDB(
            node_id=node.id, year=2026, row_index=0,
            data={"number": "INC-001", "date": "2026-01-15", "severity": "High"},
        ),
        RegistryRowDB(
            node_id=node.id, year=2026, row_index=1,
            data={"number": "INC-002", "date": "2026-03-22", "severity": "Low"},
        ),
        RegistryRowDB(
            node_id=node.id, year=2025, row_index=0,
            data={"number": "INC-003", "date": "2025-11-01", "severity": "Medium"},
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    return {"registry_type": rt, "node": node, "rows": rows}


@pytest.mark.asyncio
async def test_resolve_registry_node_found(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import resolve_registry_node

    rt, node_id, node_slug = await resolve_registry_node(
        db_session, "incident-register",
    )
    assert rt.slug == "incident-register"
    assert node_id == seed_registry_with_rows["node"].id
    assert node_slug == "incident-register"


@pytest.mark.asyncio
async def test_resolve_registry_node_not_found(db_session: AsyncSession) -> None:
    from mcp_server.data.iso import resolve_registry_node

    with pytest.raises(ValueError, match="not found"):
        await resolve_registry_node(db_session, "nonexistent-slug")


@pytest.mark.asyncio
async def test_resolve_registry_node_accepts_divergent_slugs(
    db_session: AsyncSession,
) -> None:
    """Regression: the resolver must accept BOTH the node slug (canonical)
    and the registry type slug (backwards-compat) when they diverge."""
    from mcp_server.data.iso import resolve_registry_node

    rt = RegistryTypeDB(
        name="Audit Plan & Results",
        slug="audit-plan-&-results",
        description="Annual audit plan",
        is_yearly=False,
        schema=[{"key": "title", "label": "Title", "type": "string"}],
    )
    db_session.add(rt)
    await db_session.flush()
    node = IsoDocNodeDB(
        title="Audit Plan & Results",
        slug="audit-plan-results",
        type="registry",
        registry_type_id=rt.id,
    )
    db_session.add(node)
    await db_session.commit()

    by_node = await resolve_registry_node(db_session, "audit-plan-results")
    assert by_node[0].id == rt.id
    assert by_node[1] == node.id
    assert by_node[2] == "audit-plan-results"

    by_type = await resolve_registry_node(db_session, "audit-plan-&-results")
    assert by_type[0].id == rt.id
    assert by_type[1] == node.id
    assert by_type[2] == "audit-plan-results"


@pytest.mark.asyncio
async def test_get_registry_rows_filters_by_year(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import get_registry_rows

    node_id = seed_registry_with_rows["node"].id
    rows = await get_registry_rows(db_session, node_id, year=2026)
    assert len(rows) == 2
    numbers = [r.data["number"] for r in rows]
    assert "INC-001" in numbers
    assert "INC-002" in numbers


@pytest.mark.asyncio
async def test_get_registry_rows_all_years(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import get_registry_rows

    node_id = seed_registry_with_rows["node"].id
    rows = await get_registry_rows(db_session, node_id, year=None)
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_get_registry_rows_ordered_by_index(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import get_registry_rows

    node_id = seed_registry_with_rows["node"].id
    rows = await get_registry_rows(db_session, node_id, year=2026)
    indices = [r.row_index for r in rows]
    assert indices == sorted(indices)


@pytest_asyncio.fixture
async def seed_documents(db_session: AsyncSession) -> list[IsoDocNodeDB]:
    policies_group = IsoDocNodeDB(
        title="Policies",
        slug="policies",
        type="group",
    )
    procedures_group = IsoDocNodeDB(
        title="Procedures",
        slug="procedures",
        type="group",
    )
    db_session.add_all([policies_group, procedures_group])
    await db_session.flush()

    page1 = IsoDocNodeDB(
        title="Information Security Policy",
        slug="information-security-policy",
        type="page",
        parent_id=policies_group.id,
    )
    page2 = IsoDocNodeDB(
        title="Access Control Procedure",
        slug="access-control-procedure",
        type="page",
        parent_id=procedures_group.id,
    )
    db_session.add_all([page1, page2])
    await db_session.flush()

    meta1 = IsoDocMetadataDB(
        node_id=page1.id,
        doc_version="2.1",
    )
    meta2 = IsoDocMetadataDB(
        node_id=page2.id,
        doc_version="1.0",
    )
    db_session.add_all([meta1, meta2])

    v1 = IsoDocVersionDB(
        node_id=page1.id, version=1,
        content="## 1. Purpose\n\nThis policy establishes information security controls.",
    )
    v2 = IsoDocVersionDB(
        node_id=page1.id, version=2,
        content="## 1. Purpose\n\nThis policy establishes information security controls.\n\n## 2. Scope\n\nApplies to all employees and remote access.",
    )
    v3 = IsoDocVersionDB(
        node_id=page2.id, version=1,
        content="## 1. Overview\n\nAccess control procedure for VPN and encryption.",
    )
    db_session.add_all([v1, v2, v3])
    await db_session.commit()
    return [page1, page2]


@pytest.mark.asyncio
async def test_get_documents_returns_pages_only(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import get_documents

    docs = await get_documents(db_session)
    assert len(docs) == 2
    slugs = [d["slug"] for d in docs]
    assert "information-security-policy" in slugs
    assert "policies" not in slugs  # group excluded


@pytest.mark.asyncio
async def test_get_documents_filters_by_category(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import get_documents

    docs = await get_documents(db_session, category="Policies")
    assert len(docs) == 1
    assert docs[0]["slug"] == "information-security-policy"


@pytest.mark.asyncio
async def test_get_documents_filters_by_title(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import get_documents

    docs = await get_documents(db_session, title_search="Access")
    assert len(docs) == 1
    assert docs[0]["slug"] == "access-control-procedure"


@pytest.mark.asyncio
async def test_get_documents_includes_latest_version_metadata(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import get_documents

    docs = await get_documents(db_session)
    policy = next(d for d in docs if d["slug"] == "information-security-policy")
    assert policy["doc_version"] == "2.1"
    assert policy["category"] == "Policies"
    assert "summary" in policy
    assert "Purpose" in policy["summary"]


@pytest.mark.asyncio
async def test_get_document_returns_latest_content(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import get_document

    doc = await get_document(db_session, "information-security-policy")
    assert doc["slug"] == "information-security-policy"
    assert doc["doc_version"] == "2.1"
    assert "## 2. Scope" in doc["content"]  # only in version 2


@pytest.mark.asyncio
async def test_get_document_not_found(db_session: AsyncSession) -> None:
    from mcp_server.data.iso import get_document

    with pytest.raises(ValueError, match="not found"):
        await get_document(db_session, "nonexistent-doc")


@pytest.mark.asyncio
async def test_search_documents_finds_matching_content(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import search_documents

    results = await search_documents(db_session, "encryption VPN")
    assert len(results) >= 1
    slugs = [r["slug"] for r in results]
    assert "access-control-procedure" in slugs


@pytest.mark.asyncio
async def test_search_documents_returns_snippets(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import search_documents

    results = await search_documents(db_session, "remote access")
    assert len(results) >= 1
    result = results[0]
    assert "snippet" in result
    assert "rank" in result
    assert "slug" in result
    assert "title" in result


@pytest.mark.asyncio
async def test_search_documents_only_latest_version(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import search_documents

    # "Scope" only exists in version 2 of the security policy
    results = await search_documents(db_session, "Scope employees")
    assert len(results) >= 1
    assert results[0]["slug"] == "information-security-policy"


@pytest.mark.asyncio
async def test_search_documents_no_results(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import search_documents

    results = await search_documents(db_session, "xyznonexistent")
    assert results == []


@pytest.mark.asyncio
async def test_search_documents_extracts_section_heading(
    db_session: AsyncSession, seed_documents: list[IsoDocNodeDB],
) -> None:
    from mcp_server.data.iso import search_documents

    results = await search_documents(db_session, "employees remote")
    matching = [r for r in results if r["slug"] == "information-security-policy"]
    assert len(matching) >= 1
    # Section should be "## 2. Scope" (nearest heading before match)
    assert matching[0]["section"] is not None
    assert "Scope" in matching[0]["section"]
