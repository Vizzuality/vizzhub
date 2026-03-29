"""Tests for PublishService tree query and navigation building."""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.modules.playbook.services.publish_service import (
    NavTree,
    PublicNode,
    PublishService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(
    *,
    title: str = "Page",
    slug: str = "page",
    node_type: str = "page",
    is_public: bool = True,
    parent_id: str | None = None,
    position: int = 0,
    content: str | None = None,
) -> PublicNode:
    return PublicNode(
        id=str(uuid4()),
        title=title,
        slug=slug,
        type=node_type,
        is_public=is_public,
        parent_id=parent_id,
        position=position,
        content=content,
    )


# ===========================================================================
# _build_nav_tree (pure logic, no DB)
# ===========================================================================


class TestBuildNavTree:
    """Pure tests for _build_nav_tree using PublicNode objects directly."""

    def setup_method(self) -> None:
        self.svc = PublishService()

    def test_empty_list_returns_empty_tree(self) -> None:
        tree = self.svc._build_nav_tree([])
        assert tree.roots == []
        assert tree.all_pages == []

    def test_root_level_public_page(self) -> None:
        page = _make_node(title="Welcome", slug="welcome")
        tree = self.svc._build_nav_tree([page])

        assert len(tree.roots) == 1
        assert tree.roots[0].title == "Welcome"
        assert tree.roots[0].path == "welcome.html"
        assert tree.roots[0].breadcrumb == []

    def test_private_page_excluded(self) -> None:
        page = _make_node(slug="secret", is_public=False)
        tree = self.svc._build_nav_tree([page])

        assert tree.roots == []
        assert tree.all_pages == []

    def test_group_with_public_descendant_included(self) -> None:
        group = _make_node(
            title="Culture",
            slug="culture",
            node_type="group",
            is_public=False,
        )
        page = _make_node(
            title="Values",
            slug="values",
            parent_id=group.id,
        )
        tree = self.svc._build_nav_tree([group, page])

        assert len(tree.roots) == 1
        nav_group = tree.roots[0]
        assert nav_group.title == "Culture"
        assert nav_group.type == "group"
        assert len(nav_group.children) == 1
        assert nav_group.children[0].title == "Values"

    def test_group_without_public_descendants_excluded(self) -> None:
        group = _make_node(
            title="Empty",
            slug="empty",
            node_type="group",
            is_public=False,
        )
        private_page = _make_node(
            slug="draft",
            is_public=False,
            parent_id=group.id,
        )
        tree = self.svc._build_nav_tree([group, private_page])

        assert tree.roots == []

    def test_paths_built_from_slug_hierarchy(self) -> None:
        group = _make_node(
            title="Culture",
            slug="culture",
            node_type="group",
            is_public=False,
        )
        page = _make_node(
            title="Values",
            slug="values",
            parent_id=group.id,
        )
        tree = self.svc._build_nav_tree([group, page])

        assert tree.roots[0].children[0].path == "culture/values.html"

    def test_group_path_has_no_html_extension(self) -> None:
        group = _make_node(
            title="Culture",
            slug="culture",
            node_type="group",
            is_public=True,
        )
        page = _make_node(slug="values", parent_id=group.id)
        tree = self.svc._build_nav_tree([group, page])

        assert tree.roots[0].path == "culture"

    def test_prev_next_across_groups_in_tree_order(self) -> None:
        """Pages in different groups are linked sequentially in tree order."""
        g1 = _make_node(
            title="G1", slug="g1", node_type="group", is_public=False, position=0,
        )
        p1 = _make_node(
            title="P1", slug="p1", parent_id=g1.id, position=0,
        )
        p2 = _make_node(
            title="P2", slug="p2", parent_id=g1.id, position=1,
        )
        g2 = _make_node(
            title="G2", slug="g2", node_type="group", is_public=False, position=1,
        )
        p3 = _make_node(
            title="P3", slug="p3", parent_id=g2.id, position=0,
        )
        tree = self.svc._build_nav_tree([g1, p1, p2, g2, p3])

        assert len(tree.all_pages) == 3
        assert tree.all_pages[0].title == "P1"
        assert tree.all_pages[1].title == "P2"
        assert tree.all_pages[2].title == "P3"

        assert tree.all_pages[0].prev_page is None
        assert tree.all_pages[0].next_page is tree.all_pages[1]
        assert tree.all_pages[1].prev_page is tree.all_pages[0]
        assert tree.all_pages[1].next_page is tree.all_pages[2]
        assert tree.all_pages[2].prev_page is tree.all_pages[1]
        assert tree.all_pages[2].next_page is None

    def test_breadcrumbs_built_from_ancestor_chain(self) -> None:
        root_group = _make_node(
            title="Company", slug="company", node_type="group", is_public=False,
        )
        sub_group = _make_node(
            title="Engineering",
            slug="engineering",
            node_type="group",
            is_public=False,
            parent_id=root_group.id,
        )
        page = _make_node(
            title="Standards",
            slug="standards",
            parent_id=sub_group.id,
        )
        tree = self.svc._build_nav_tree([root_group, sub_group, page])

        nav_page = tree.roots[0].children[0].children[0]
        assert nav_page.title == "Standards"
        assert len(nav_page.breadcrumb) == 2
        assert nav_page.breadcrumb[0]["title"] == "Company"
        assert nav_page.breadcrumb[0]["url"] == "company/index.html"
        assert nav_page.breadcrumb[1]["title"] == "Engineering"
        assert nav_page.breadcrumb[1]["url"] == "company/engineering/index.html"

    def test_root_page_has_empty_breadcrumb(self) -> None:
        page = _make_node(title="Home", slug="home")
        tree = self.svc._build_nav_tree([page])

        assert tree.roots[0].breadcrumb == []

    def test_children_sorted_by_position(self) -> None:
        group = _make_node(
            slug="g", node_type="group", is_public=False,
        )
        p_b = _make_node(title="B", slug="b", parent_id=group.id, position=2)
        p_a = _make_node(title="A", slug="a", parent_id=group.id, position=1)
        p_c = _make_node(title="C", slug="c", parent_id=group.id, position=3)

        tree = self.svc._build_nav_tree([group, p_b, p_a, p_c])

        titles = [c.title for c in tree.roots[0].children]
        assert titles == ["A", "B", "C"]

    def test_deeply_nested_public_descendant_includes_ancestors(self) -> None:
        g1 = _make_node(slug="a", node_type="group", is_public=False)
        g2 = _make_node(slug="b", node_type="group", is_public=False, parent_id=g1.id)
        g3 = _make_node(slug="c", node_type="group", is_public=False, parent_id=g2.id)
        page = _make_node(slug="deep", parent_id=g3.id)

        tree = self.svc._build_nav_tree([g1, g2, g3, page])

        assert len(tree.roots) == 1
        assert tree.roots[0].children[0].children[0].children[0].slug == "deep"


# ===========================================================================
# _query_public_tree (DB integration)
# ===========================================================================


@pytest.mark.asyncio
class TestQueryPublicTree:
    """DB integration tests for _query_public_tree."""

    async def test_empty_db_returns_empty_list(self, db_session: AsyncSession) -> None:
        svc = PublishService()
        result = await svc._query_public_tree(db_session)
        assert result == []

    async def test_returns_all_nodes_with_content(
        self, db_session: AsyncSession,
    ) -> None:
        svc = PublishService()

        group_id = uuid4()
        page_id = uuid4()

        group = PlaybookNodeDB(
            id=group_id,
            title="Culture",
            slug="culture",
            type="group",
            parent_id=None,
            position=0,
            is_public=False,
        )
        page = PlaybookNodeDB(
            id=page_id,
            title="Values",
            slug="values",
            type="page",
            parent_id=group_id,
            position=0,
            is_public=True,
        )
        version = PlaybookPageVersionDB(
            id=uuid4(),
            node_id=page_id,
            content="# Our Values",
            version=1,
        )

        db_session.add_all([group, page, version])
        await db_session.flush()

        result = await svc._query_public_tree(db_session)

        assert len(result) == 2
        by_slug = {n.slug: n for n in result}

        assert by_slug["culture"].type == "group"
        assert by_slug["culture"].content is None

        assert by_slug["values"].type == "page"
        assert by_slug["values"].content == "# Our Values"
        assert by_slug["values"].parent_id == str(group_id)

    async def test_returns_latest_version_content(
        self, db_session: AsyncSession,
    ) -> None:
        svc = PublishService()
        page_id = uuid4()

        page = PlaybookNodeDB(
            id=page_id,
            title="Page",
            slug="page",
            type="page",
            parent_id=None,
            position=0,
            is_public=True,
        )
        v1 = PlaybookPageVersionDB(
            id=uuid4(), node_id=page_id, content="old content", version=1,
        )
        v2 = PlaybookPageVersionDB(
            id=uuid4(), node_id=page_id, content="new content", version=2,
        )

        db_session.add_all([page, v1, v2])
        await db_session.flush()

        result = await svc._query_public_tree(db_session)

        assert len(result) == 1
        assert result[0].content == "new content"
