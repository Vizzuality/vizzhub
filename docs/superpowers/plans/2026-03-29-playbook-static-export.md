# Playbook Static Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export public playbook pages as a standalone static site to S3 with Vizzuality branding, collapsible sidebar navigation, and admin-triggered publish.

**Architecture:** Backend ARQ job renders markdown→HTML via `markdown-it-py`, wraps in Jinja2 templates with branding, uploads to S3 `playbook/public/`. Frontend adds a Publish button (admin-only) that triggers the job and polls for status.

**Tech Stack:** Python (`markdown-it-py`, `mdit-py-plugins`, Jinja2, boto3), FastAPI, ARQ, React (TanStack Query), S3

**Spec:** `docs/superpowers/specs/2026-03-29-playbook-static-export-design.md`

---

### Task 1: Add Python dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add markdown-it-py and plugins to requirements**

Add to `backend/requirements.txt`:
```
markdown-it-py>=3.0.0,<4.0.0
mdit-py-plugins>=0.4.0,<1.0.0
linkify-it-py>=2.0.0,<3.0.0
```

- [ ] **Step 2: Install dependencies**

Run: `cd backend && pip install -r requirements.txt`
Expected: Successfully installed markdown-it-py, mdit-py-plugins

- [ ] **Step 3: Verify import works**

Run: `cd backend && python -c "from markdown_it import MarkdownIt; from mdit_py_plugins.wordcount import wordcount_plugin; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat(playbook): add markdown-it-py dependencies for static export"
```

---

### Task 2: Markdown renderer service

**Files:**
- Create: `backend/app/modules/playbook/services/publish_renderer.py`
- Create: `backend/tests/playbook/test_publish_renderer.py`

- [ ] **Step 1: Write failing tests for markdown rendering**

Create `backend/tests/playbook/test_publish_renderer.py`:
```python
import pytest
from app.modules.playbook.services.publish_renderer import render_markdown


class TestRenderMarkdown:
    def test_basic_paragraph(self):
        result = render_markdown("Hello world")
        assert "<p>Hello world</p>" in result

    def test_heading(self):
        result = render_markdown("## Section Title")
        assert "<h2>Section Title</h2>" in result

    def test_bold_and_italic(self):
        result = render_markdown("**bold** and *italic*")
        assert "<strong>bold</strong>" in result
        assert "<em>italic</em>" in result

    def test_single_newline_becomes_br(self):
        result = render_markdown("line one\nline two")
        assert "<br" in result

    def test_unordered_list(self):
        result = render_markdown("- item one\n- item two")
        assert "<ul>" in result
        assert "<li>item one</li>" in result

    def test_link(self):
        result = render_markdown("[Vizz](https://vizzuality.com)")
        assert 'href="https://vizzuality.com"' in result

    def test_image(self):
        result = render_markdown("![alt](https://example.com/img.png)")
        assert '<img src="https://example.com/img.png"' in result

    def test_code_block(self):
        result = render_markdown("```python\nprint('hi')\n```")
        assert "<code>" in result
        assert "print(" in result

    def test_inline_code(self):
        result = render_markdown("Use `foo()` here")
        assert "<code>foo()</code>" in result

    def test_blockquote(self):
        result = render_markdown("> A quote")
        assert "<blockquote>" in result

    def test_linkify_bare_url(self):
        result = render_markdown("Visit https://vizzuality.com today")
        assert 'href="https://vizzuality.com"' in result

    def test_empty_input(self):
        result = render_markdown("")
        assert result == ""

    def test_none_input(self):
        result = render_markdown(None)
        assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/playbook/test_publish_renderer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.modules.playbook.services.publish_renderer'`

- [ ] **Step 3: Implement the renderer**

Create `backend/app/modules/playbook/services/publish_renderer.py`:
```python
from markdown_it import MarkdownIt
from mdit_py_plugins.linkify import linkify_plugin


def _create_renderer() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"breaks": True, "linkify": True})
    linkify_plugin(md)
    return md


_md = _create_renderer()


def render_markdown(source: str | None) -> str:
    if not source:
        return ""
    return _md.render(source).strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/playbook/test_publish_renderer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/playbook/services/publish_renderer.py backend/tests/playbook/test_publish_renderer.py
git commit -m "feat(playbook): add markdown-to-HTML renderer for static export"
```

---

### Task 3: Jinja2 templates for static site

**Files:**
- Create: `backend/app/modules/playbook/services/publish_templates/page.html`
- Create: `backend/app/modules/playbook/services/publish_templates/index.html`
- Create: `backend/app/modules/playbook/services/publish_templates/group.html`
- Create: `backend/app/modules/playbook/services/publish_templates/404.html`
- Create: `backend/app/modules/playbook/services/publish_templates/style.css`
- Create: `backend/app/modules/playbook/services/publish_templates/navigation.js`

Reference the approved mockup at `.superpowers/brainstorm/41423-1774803824/playbook-site-mockup.html` for exact styles and structure.

- [ ] **Step 1: Create the page template**

Create `backend/app/modules/playbook/services/publish_templates/page.html` — a full HTML document with:
- `<head>`: meta charset, viewport, Google Fonts `DM Sans` link, link to `assets/style.css`
- Header: Vizzuality SVG logo (inline, from `VizzualityLogo.tsx`) + divider + "Playbook" title + hamburger button (mobile)
- Sidebar: `<nav>` with tree from `{{ nav_tree }}` — groups as collapsible `<details>` elements, pages as `<a>` links, current page gets `class="active"`
- Content: breadcrumb from `{{ breadcrumb }}`, `<h1>{{ title }}</h1>`, `{{ content }}` (rendered HTML), prev/next links from `{{ prev_page }}` / `{{ next_page }}`
- Footer: `© {{ year }} Vizzuality`
- Script tag loading `assets/navigation.js`

Template variables: `title`, `content`, `breadcrumb` (list of `{title, url}`), `nav_tree` (nested structure), `current_path`, `prev_page` (`{title, url}` or None), `next_page` (`{title, url}` or None), `year`, `base_url`

- [ ] **Step 2: Create the root index template**

Create `backend/app/modules/playbook/services/publish_templates/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="0;url={{ first_page_url }}">
<title>Vizzuality Playbook</title>
</head>
<body>
<p>Redirecting to <a href="{{ first_page_url }}">{{ first_page_title }}</a>...</p>
</body>
</html>
```

- [ ] **Step 3: Create the group index template**

Create `backend/app/modules/playbook/services/publish_templates/group.html` — same layout as page.html but content section lists child pages as a card grid or link list with descriptions. Template variables: same as page.html plus `children` (list of `{title, url}`).

- [ ] **Step 4: Create the 404 template**

Create `backend/app/modules/playbook/services/publish_templates/404.html` — minimal branded page with "Page not found" message and link back to index.

- [ ] **Step 5: Create style.css**

Create `backend/app/modules/playbook/services/publish_templates/style.css` — extract and adapt styles from the approved mockup. Key sections:
- Reset and base typography (DM Sans, color: #333)
- Site layout (sidebar 280px + content flex)
- Sidebar styles (header with logo, nav groups, active state with teal accent)
- Content styles (max-width 760px, breadcrumb, headings, paragraphs, lists, blockquotes, code, images)
- Prev/next navigation
- Footer
- Responsive: `@media (max-width: 768px)` — hide sidebar, show hamburger, full-width content
- Print styles: hide sidebar and nav

- [ ] **Step 6: Create navigation.js**

Create `backend/app/modules/playbook/services/publish_templates/navigation.js` — vanilla JS for:
- Sidebar toggle on mobile (hamburger button)
- Group collapse/expand with localStorage persistence
- On load: restore saved collapse state, collapse all groups except the one containing the active page

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/playbook/services/publish_templates/
git commit -m "feat(playbook): add Jinja2 templates and static assets for published site"
```

---

### Task 4: Database model and migration for publish log

**Files:**
- Create: `backend/app/modules/playbook/models/publish_log.py`
- Modify: `backend/app/modules/playbook/models/__init__.py`
- Create: `backend/alembic/versions/038_create_playbook_publish_log.py`
- Create: `backend/tests/playbook/test_publish_log_model.py`

- [ ] **Step 1: Write failing test for the model**

Create `backend/tests/playbook/test_publish_log_model.py`:
```python
import pytest
from app.modules.playbook.models.publish_log import PlaybookPublishLogDB


class TestPlaybookPublishLogModel:
    @pytest.mark.asyncio
    async def test_create_publish_log(self, db):
        log = PlaybookPublishLogDB(
            status="running",
            published_by_id=None,
        )
        db.add(log)
        await db.flush()
        assert log.id is not None
        assert log.status == "running"
        assert log.started_at is not None
        assert log.completed_at is None
        assert log.page_count is None
        assert log.error_message is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/playbook/test_publish_log_model.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create the model**

Create `backend/app/modules/playbook/models/publish_log.py`:
```python
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlaybookPublishLogDB(Base):
    __tablename__ = "playbook_publish_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
```

- [ ] **Step 4: Export model from __init__.py**

Add to `backend/app/modules/playbook/models/__init__.py`:
```python
from app.modules.playbook.models.publish_log import PlaybookPublishLogDB
```

- [ ] **Step 5: Create Alembic migration**

Create `backend/alembic/versions/038_create_playbook_publish_log.py`:
```python
"""Create playbook_publish_log table.

Revision ID: 038_pb_publish_log
Revises: 037_capacity_plans
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision = "038_pb_publish_log"
down_revision = "037_capacity_plans"

def upgrade() -> None:
    op.create_table(
        "playbook_publish_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("published_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

def downgrade() -> None:
    op.drop_table("playbook_publish_log")
```

- [ ] **Step 6: Run migration and test**

Run: `cd backend && alembic upgrade head`
Then: `cd backend && python -m pytest tests/playbook/test_publish_log_model.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/playbook/models/publish_log.py backend/app/modules/playbook/models/__init__.py backend/alembic/versions/038_create_playbook_publish_log.py backend/tests/playbook/test_publish_log_model.py
git commit -m "feat(playbook): add publish log model and migration"
```

---

### Task 5: Publish service — tree query and nav building

**Files:**
- Create: `backend/app/modules/playbook/services/publish_service.py`
- Create: `backend/tests/playbook/test_publish_service.py`

- [ ] **Step 1: Write failing tests for tree query and nav building**

Create `backend/tests/playbook/test_publish_service.py`:
```python
import pytest
from uuid import uuid4
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.modules.playbook.services.publish_service import PublishService


class TestQueryPublicTree:
    @pytest.mark.asyncio
    async def test_returns_all_nodes(self, db):
        """Should fetch all nodes regardless of is_public."""
        svc = PublishService()
        group = PlaybookNodeDB(title="Culture", slug="culture", type="group", position=0, is_public=False)
        db.add(group)
        await db.flush()
        page = PlaybookNodeDB(title="Values", slug="values", type="page", parent_id=group.id, position=0, is_public=True)
        db.add(page)
        await db.flush()
        version = PlaybookPageVersionDB(node_id=page.id, content="# Values", version=1)
        db.add(version)
        await db.flush()

        nodes = await svc._query_public_tree(db)
        assert len(nodes) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_nodes(self, db):
        svc = PublishService()
        nodes = await svc._query_public_tree(db)
        assert nodes == []


class TestBuildNavTree:
    def test_filters_out_groups_without_public_descendants(self):
        svc = PublishService()
        # Group with no public children should be excluded
        nodes = [
            _make_node(id="g1", type="group", is_public=False, parent_id=None, slug="empty"),
            _make_node(id="p1", type="page", is_public=False, parent_id="g1", slug="private"),
        ]
        nav = svc._build_nav_tree(nodes)
        assert len(nav.roots) == 0

    def test_includes_non_public_group_with_public_descendant(self):
        svc = PublishService()
        nodes = [
            _make_node(id="g1", type="group", is_public=False, parent_id=None, slug="culture"),
            _make_node(id="p1", type="page", is_public=True, parent_id="g1", slug="values"),
        ]
        nav = svc._build_nav_tree(nodes)
        assert len(nav.roots) == 1
        assert nav.roots[0].slug == "culture"
        assert len(nav.roots[0].children) == 1

    def test_builds_paths_correctly(self):
        svc = PublishService()
        nodes = [
            _make_node(id="g1", type="group", is_public=False, parent_id=None, slug="culture"),
            _make_node(id="p1", type="page", is_public=True, parent_id="g1", slug="values"),
        ]
        nav = svc._build_nav_tree(nodes)
        page = nav.roots[0].children[0]
        assert page.path == "culture/values.html"

    def test_prev_next_within_group(self):
        svc = PublishService()
        nodes = [
            _make_node(id="g1", type="group", is_public=False, parent_id=None, slug="culture"),
            _make_node(id="p1", type="page", is_public=True, parent_id="g1", slug="values", position=0),
            _make_node(id="p2", type="page", is_public=True, parent_id="g1", slug="growth", position=1),
        ]
        nav = svc._build_nav_tree(nodes)
        pages = nav.all_pages
        assert pages[0].next_page == pages[1]
        assert pages[0].prev_page is None
        assert pages[1].prev_page == pages[0]
        assert pages[1].next_page is None


def _make_node(id, type, is_public, parent_id, slug, position=0, content="# Test"):
    """Helper to create a lightweight node-like object for nav tree tests."""
    from app.modules.playbook.services.publish_service import PublicNode
    return PublicNode(
        id=id,
        title=slug.replace("-", " ").title(),
        slug=slug,
        type=type,
        is_public=is_public,
        parent_id=parent_id,
        position=position,
        content=content if type == "page" else None,
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/playbook/test_publish_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement PublishService with query and nav building**

Create `backend/app/modules/playbook/services/publish_service.py`:
```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB

logger = structlog.get_logger()


@dataclass
class PublicNode:
    id: str
    title: str
    slug: str
    type: str
    is_public: bool
    parent_id: str | None
    position: int
    content: str | None = None


@dataclass
class NavNode:
    id: str
    title: str
    slug: str
    type: str
    is_public: bool
    path: str
    children: list[NavNode] = field(default_factory=list)
    prev_page: NavNode | None = field(default=None, repr=False)
    next_page: NavNode | None = field(default=None, repr=False)
    breadcrumb: list[dict] = field(default_factory=list)
    content_html: str = ""


@dataclass
class NavTree:
    roots: list[NavNode]
    all_pages: list[NavNode]


class PublishService:
    async def _query_public_tree(self, db: AsyncSession) -> list[PublicNode]:
        latest_version = (
            select(
                PlaybookPageVersionDB.node_id,
                func.max(PlaybookPageVersionDB.version).label("max_ver"),
            )
            .group_by(PlaybookPageVersionDB.node_id)
            .subquery()
        )

        content_sub = (
            select(PlaybookPageVersionDB.node_id, PlaybookPageVersionDB.content)
            .join(
                latest_version,
                (PlaybookPageVersionDB.node_id == latest_version.c.node_id)
                & (PlaybookPageVersionDB.version == latest_version.c.max_ver),
            )
            .subquery()
        )

        stmt = (
            select(
                PlaybookNodeDB.id,
                PlaybookNodeDB.title,
                PlaybookNodeDB.slug,
                PlaybookNodeDB.type,
                PlaybookNodeDB.is_public,
                PlaybookNodeDB.parent_id,
                PlaybookNodeDB.position,
                content_sub.c.content,
            )
            .outerjoin(content_sub, PlaybookNodeDB.id == content_sub.c.node_id)
            .order_by(PlaybookNodeDB.position)
        )

        rows = (await db.execute(stmt)).all()
        return [
            PublicNode(
                id=str(r.id),
                title=r.title,
                slug=r.slug,
                type=r.type,
                is_public=r.is_public,
                parent_id=str(r.parent_id) if r.parent_id else None,
                position=r.position,
                content=r.content,
            )
            for r in rows
        ]

    def _build_nav_tree(self, nodes: list[PublicNode]) -> NavTree:
        node_map = {n.id: n for n in nodes}

        def has_public_descendant(node_id: str) -> bool:
            n = node_map[node_id]
            if n.type == "page" and n.is_public:
                return True
            children = [c for c in nodes if c.parent_id == node_id]
            return any(has_public_descendant(c.id) for c in children)

        included_ids = {n.id for n in nodes if has_public_descendant(n.id)}

        def build_path(node: PublicNode) -> str:
            parts = []
            current = node
            while current:
                parts.append(current.slug)
                current = node_map.get(current.parent_id) if current.parent_id else None
            parts.reverse()
            path = "/".join(parts)
            if node.type == "page":
                path += ".html"
            return path

        def build_breadcrumb(node: PublicNode) -> list[dict]:
            parts = []
            current = node_map.get(node.parent_id) if node.parent_id else None
            while current:
                parts.append({"title": current.title, "url": build_path(current) + "/index.html"})
                current = node_map.get(current.parent_id) if current.parent_id else None
            parts.reverse()
            return parts

        def build_subtree(parent_id: str | None) -> list[NavNode]:
            children = sorted(
                [n for n in nodes if n.parent_id == parent_id and n.id in included_ids],
                key=lambda n: n.position,
            )
            result = []
            for n in children:
                nav = NavNode(
                    id=n.id,
                    title=n.title,
                    slug=n.slug,
                    type=n.type,
                    is_public=n.is_public,
                    path=build_path(n),
                    breadcrumb=build_breadcrumb(n),
                )
                if n.type == "group":
                    nav.children = build_subtree(n.id)
                result.append(nav)
            return result

        roots = build_subtree(None)

        all_pages = []
        def collect_pages(nav_nodes: list[NavNode]):
            for n in nav_nodes:
                if n.type == "page" and n.is_public:
                    all_pages.append(n)
                collect_pages(n.children)
        collect_pages(roots)

        for i, page in enumerate(all_pages):
            page.prev_page = all_pages[i - 1] if i > 0 else None
            page.next_page = all_pages[i + 1] if i < len(all_pages) - 1 else None

        return NavTree(roots=roots, all_pages=all_pages)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/playbook/test_publish_service.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/playbook/services/publish_service.py backend/tests/playbook/test_publish_service.py
git commit -m "feat(playbook): add publish service with tree query and nav building"
```

---

### Task 6: Publish service — rendering and S3 upload

**Files:**
- Modify: `backend/app/modules/playbook/services/publish_service.py`
- Create: `backend/tests/playbook/test_publish_site_generation.py`

- [ ] **Step 1: Write failing tests for full site generation**

Create `backend/tests/playbook/test_publish_site_generation.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.modules.playbook.services.publish_service import PublishService


class TestGenerateSite:
    @pytest.mark.asyncio
    async def test_generates_all_expected_files(self, db):
        svc = PublishService()
        group = PlaybookNodeDB(title="Culture", slug="culture", type="group", position=0, is_public=True)
        db.add(group)
        await db.flush()
        page = PlaybookNodeDB(title="Values", slug="values", type="page", parent_id=group.id, position=0, is_public=True)
        db.add(page)
        await db.flush()
        db.add(PlaybookPageVersionDB(node_id=page.id, content="# Our Values\n\nWe believe in impact.", version=1))
        await db.flush()

        files = await svc._generate_site(db)

        assert "index.html" in files
        assert "404.html" in files
        assert "assets/style.css" in files
        assert "assets/navigation.js" in files
        assert "culture/values.html" in files
        assert "culture/index.html" in files
        assert "manifest.json" in files

    @pytest.mark.asyncio
    async def test_page_html_contains_rendered_content(self, db):
        svc = PublishService()
        page = PlaybookNodeDB(title="Hello", slug="hello", type="page", position=0, is_public=True)
        db.add(page)
        await db.flush()
        db.add(PlaybookPageVersionDB(node_id=page.id, content="**bold text**", version=1))
        await db.flush()

        files = await svc._generate_site(db)
        html = files["hello.html"].decode()

        assert "<strong>bold text</strong>" in html
        assert "Hello" in html
        assert "Vizzuality" in html

    @pytest.mark.asyncio
    async def test_empty_public_pages_raises(self, db):
        svc = PublishService()
        page = PlaybookNodeDB(title="Private", slug="private", type="page", position=0, is_public=False)
        db.add(page)
        await db.flush()
        db.add(PlaybookPageVersionDB(node_id=page.id, content="secret", version=1))
        await db.flush()

        with pytest.raises(ValueError, match="No public pages"):
            await svc._generate_site(db)

    @pytest.mark.asyncio
    async def test_manifest_contains_file_list(self, db):
        svc = PublishService()
        page = PlaybookNodeDB(title="Hello", slug="hello", type="page", position=0, is_public=True)
        db.add(page)
        await db.flush()
        db.add(PlaybookPageVersionDB(node_id=page.id, content="Hi", version=1))
        await db.flush()

        import json
        files = await svc._generate_site(db)
        manifest = json.loads(files["manifest.json"])
        assert "hello.html" in manifest["files"]


class TestUploadSite:
    @pytest.mark.asyncio
    async def test_uploads_all_files_to_s3(self):
        svc = PublishService()
        files = {
            "index.html": b"<html>test</html>",
            "assets/style.css": b"body {}",
        }
        with patch("app.modules.playbook.services.publish_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            await svc._upload_site(files)
            assert mock_s3.put_object.call_count == 2

    @pytest.mark.asyncio
    async def test_sets_correct_content_types(self):
        svc = PublishService()
        files = {
            "page.html": b"<html></html>",
            "assets/style.css": b"body {}",
            "assets/navigation.js": b"console.log()",
            "manifest.json": b"{}",
        }
        with patch("app.modules.playbook.services.publish_service._get_s3_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3
            await svc._upload_site(files)
            calls = {c.kwargs["Key"].split("/")[-1]: c.kwargs["ContentType"] for c in mock_s3.put_object.call_args_list}
            assert calls["page.html"] == "text/html; charset=utf-8"
            assert calls["style.css"] == "text/css"
            assert calls["navigation.js"] == "application/javascript"
            assert calls["manifest.json"] == "application/json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/playbook/test_publish_site_generation.py -v`
Expected: FAIL — `AttributeError: 'PublishService' has no attribute '_generate_site'`

- [ ] **Step 3: Add _generate_site, _upload_site, _cleanup_orphans to PublishService**

Add to `backend/app/modules/playbook/services/publish_service.py`:

```python
import asyncio
from pathlib import Path
from functools import lru_cache

import boto3
from jinja2 import Environment, FileSystemLoader

from app.config import get_settings
from app.modules.playbook.services.publish_renderer import render_markdown

TEMPLATES_DIR = Path(__file__).parent / "publish_templates"
S3_PREFIX = "playbook/public/"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
}


@lru_cache
def _get_s3_client():
    settings = get_settings()
    region = settings.assets_bucket_url.split(".s3.")[1].split(".")[0] if ".s3." in settings.assets_bucket_url else "eu-west-3"
    return boto3.Session(region_name=region).client("s3")


def _get_jinja_env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)


# Add these methods to the PublishService class:

    async def _generate_site(self, db: AsyncSession) -> dict[str, bytes]:
        nodes = await self._query_public_tree(db)
        nav = self._build_nav_tree(nodes)

        if not nav.all_pages:
            raise ValueError("No public pages to publish")

        node_map = {n.id: n for n in nodes}
        env = _get_jinja_env()
        files: dict[str, bytes] = {}
        year = datetime.now(timezone.utc).year

        # Render each public page
        page_tpl = env.get_template("page.html")
        for page in nav.all_pages:
            source_node = node_map.get(page.id)
            content_html = render_markdown(source_node.content if source_node else "")
            html = page_tpl.render(
                title=page.title,
                content=content_html,
                breadcrumb=page.breadcrumb,
                nav_tree=nav.roots,
                current_path=page.path,
                prev_page=page.prev_page,
                next_page=page.next_page,
                year=year,
                base_url="",
            )
            files[page.path] = html.encode("utf-8")

        # Group index pages
        group_tpl = env.get_template("group.html")
        def render_groups(nav_nodes: list[NavNode]):
            for n in nav_nodes:
                if n.type == "group":
                    children_links = [
                        {"title": c.title, "url": c.path}
                        for c in n.children
                        if c.is_public or c.type == "group"
                    ]
                    html = group_tpl.render(
                        title=n.title,
                        children=children_links,
                        breadcrumb=n.breadcrumb,
                        nav_tree=nav.roots,
                        current_path=n.path,
                        prev_page=None,
                        next_page=None,
                        year=year,
                        base_url="",
                    )
                    files[f"{n.path}/index.html"] = html.encode("utf-8")
                    render_groups(n.children)
        render_groups(nav.roots)

        # Root index
        index_tpl = env.get_template("index.html")
        first = nav.all_pages[0]
        files["index.html"] = index_tpl.render(
            first_page_url=first.path,
            first_page_title=first.title,
        ).encode("utf-8")

        # 404
        four04_tpl = env.get_template("404.html")
        files["404.html"] = four04_tpl.render(year=year, base_url="").encode("utf-8")

        # Static assets
        for asset_name in ("style.css", "navigation.js"):
            asset_path = TEMPLATES_DIR / asset_name
            files[f"assets/{asset_name}"] = asset_path.read_bytes()

        # Manifest
        import json
        manifest = {
            "published_at": datetime.now(timezone.utc).isoformat(),
            "page_count": len(nav.all_pages),
            "files": sorted(files.keys()),
        }
        files["manifest.json"] = json.dumps(manifest, indent=2).encode("utf-8")

        return files

    async def _upload_site(self, files: dict[str, bytes]) -> None:
        settings = get_settings()
        s3 = _get_s3_client()

        for key, content in files.items():
            ext = "." + key.rsplit(".", 1)[-1] if "." in key else ""
            content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
            await asyncio.to_thread(
                s3.put_object,
                Bucket=settings.assets_bucket_name,
                Key=f"{S3_PREFIX}{key}",
                Body=content,
                ContentType=content_type,
            )

    async def _cleanup_orphans(self, current_files: set[str]) -> int:
        settings = get_settings()
        s3 = _get_s3_client()

        try:
            manifest_obj = await asyncio.to_thread(
                s3.get_object,
                Bucket=settings.assets_bucket_name,
                Key=f"{S3_PREFIX}manifest.json",
            )
            old_manifest = json.loads(manifest_obj["Body"].read())
            old_files = set(old_manifest.get("files", []))
        except s3.exceptions.NoSuchKey:
            return 0

        orphans = old_files - current_files
        for orphan_key in orphans:
            await asyncio.to_thread(
                s3.delete_object,
                Bucket=settings.assets_bucket_name,
                Key=f"{S3_PREFIX}{orphan_key}",
            )
            logger.info("publish_orphan_deleted", key=orphan_key)

        return len(orphans)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/playbook/test_publish_site_generation.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/playbook/services/publish_service.py backend/tests/playbook/test_publish_site_generation.py
git commit -m "feat(playbook): add site generation, S3 upload, and orphan cleanup"
```

---

### Task 7: Publish service — orchestration method

**Files:**
- Modify: `backend/app/modules/playbook/services/publish_service.py`
- Create: `backend/tests/playbook/test_publish_orchestration.py`

- [ ] **Step 1: Write failing test for the full publish method**

Create `backend/tests/playbook/test_publish_orchestration.py`:
```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.modules.playbook.models.publish_log import PlaybookPublishLogDB
from app.modules.playbook.services.publish_service import PublishService


class TestPublishOrchestration:
    @pytest.mark.asyncio
    async def test_publish_updates_log_on_success(self, db):
        svc = PublishService()
        page = PlaybookNodeDB(title="Hello", slug="hello", type="page", position=0, is_public=True)
        db.add(page)
        await db.flush()
        db.add(PlaybookPageVersionDB(node_id=page.id, content="Hi", version=1))
        log = PlaybookPublishLogDB(status="running")
        db.add(log)
        await db.flush()

        with patch.object(svc, "_upload_site", new_callable=AsyncMock):
            with patch.object(svc, "_cleanup_orphans", new_callable=AsyncMock, return_value=0):
                await svc.publish(db, str(log.id))

        await db.refresh(log)
        assert log.status == "completed"
        assert log.page_count == 1
        assert log.completed_at is not None

    @pytest.mark.asyncio
    async def test_publish_updates_log_on_failure(self, db):
        svc = PublishService()
        log = PlaybookPublishLogDB(status="running")
        db.add(log)
        await db.flush()

        await svc.publish(db, str(log.id))

        await db.refresh(log)
        assert log.status == "failed"
        assert "No public pages" in log.error_message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/playbook/test_publish_orchestration.py -v`
Expected: FAIL

- [ ] **Step 3: Add the publish orchestration method**

Add to `PublishService` in `publish_service.py`:
```python
    async def publish(self, db: AsyncSession, publish_log_id: str) -> None:
        from app.modules.playbook.models.publish_log import PlaybookPublishLogDB

        log_uuid = UUID(publish_log_id)
        log = await db.get(PlaybookPublishLogDB, log_uuid)

        try:
            logger.info("publish_started", publish_log_id=publish_log_id)
            files = await self._generate_site(db)
            await self._cleanup_orphans(set(files.keys()))
            await self._upload_site(files)

            log.status = "completed"
            log.page_count = len([k for k in files if k.endswith(".html") and k not in ("index.html", "404.html") and "/index.html" not in k])
            log.completed_at = datetime.now(timezone.utc)
            await db.flush()
            logger.info("publish_completed", publish_log_id=publish_log_id, page_count=log.page_count)

        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
            log.completed_at = datetime.now(timezone.utc)
            await db.flush()
            logger.error("publish_failed", publish_log_id=publish_log_id, error=str(e))
```

Add at top of file: `from uuid import UUID`

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/playbook/test_publish_orchestration.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/playbook/services/publish_service.py backend/tests/playbook/test_publish_orchestration.py
git commit -m "feat(playbook): add publish orchestration with log updates"
```

---

### Task 8: ARQ worker job

**Files:**
- Create: `backend/app/worker/publish_playbook.py`
- Modify: `backend/app/worker/settings.py`
- Create: `backend/tests/playbook/test_publish_worker.py`

- [ ] **Step 1: Write failing test for the worker task**

Create `backend/tests/playbook/test_publish_worker.py`:
```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.worker.publish_playbook import publish_playbook_task


class TestPublishPlaybookTask:
    @pytest.mark.asyncio
    async def test_calls_publish_service(self):
        mock_db = AsyncMock()
        ctx = {"db": mock_db}

        with patch("app.worker.publish_playbook.PublishService") as MockSvc:
            instance = MockSvc.return_value
            instance.publish = AsyncMock()
            await publish_playbook_task(ctx, publish_log_id="test-id")
            instance.publish.assert_called_once_with(mock_db, "test-id")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/playbook/test_publish_worker.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create the worker task**

Create `backend/app/worker/publish_playbook.py`:
```python
import structlog
from app.modules.playbook.services.publish_service import PublishService

logger = structlog.get_logger()


async def publish_playbook_task(ctx: dict, publish_log_id: str) -> dict:
    db = ctx["db"]
    svc = PublishService()
    await svc.publish(db, publish_log_id)
    return {"publish_log_id": publish_log_id}
```

- [ ] **Step 4: Register in WorkerSettings**

Add to `backend/app/worker/settings.py`:
- Import: `from app.worker.publish_playbook import publish_playbook_task`
- Add `publish_playbook_task` to `WorkerSettings.functions` list

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/playbook/test_publish_worker.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/worker/publish_playbook.py backend/app/worker/settings.py backend/tests/playbook/test_publish_worker.py
git commit -m "feat(playbook): add ARQ worker task for publish job"
```

---

### Task 9: Publish API endpoints

**Files:**
- Create: `backend/app/modules/playbook/api/publish.py`
- Modify: `backend/app/modules/playbook/router.py`
- Create: `backend/tests/playbook/test_publish_api.py`

- [ ] **Step 1: Write failing tests for the publish endpoints**

Create `backend/tests/playbook/test_publish_api.py`:
```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient


class TestPublishEndpoints:
    @pytest.mark.asyncio
    async def test_publish_requires_admin(self, client: AsyncClient, user_token_headers):
        response = await client.post("/api/playbook/publish", headers=user_token_headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_publish_creates_log_and_enqueues(self, client: AsyncClient, admin_token_headers):
        with patch("app.modules.playbook.api.publish.get_redis_pool") as mock_pool:
            mock_redis = AsyncMock()
            mock_redis.enqueue_job = AsyncMock(return_value=MagicMock(job_id="arq-123"))
            mock_pool.return_value = mock_redis

            response = await client.post("/api/playbook/publish", headers=admin_token_headers)
            assert response.status_code == 201
            data = response.json()
            assert "publish_log_id" in data

    @pytest.mark.asyncio
    async def test_publish_returns_409_when_running(self, client: AsyncClient, admin_token_headers, db):
        from app.modules.playbook.models.publish_log import PlaybookPublishLogDB
        log = PlaybookPublishLogDB(status="running")
        db.add(log)
        await db.flush()

        response = await client.post("/api/playbook/publish", headers=admin_token_headers)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_status_returns_latest(self, client: AsyncClient, admin_token_headers, db):
        from app.modules.playbook.models.publish_log import PlaybookPublishLogDB
        log = PlaybookPublishLogDB(status="completed", page_count=5)
        db.add(log)
        await db.flush()

        response = await client.get("/api/playbook/publish/status", headers=admin_token_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["page_count"] == 5

    @pytest.mark.asyncio
    async def test_status_returns_null_when_never_published(self, client: AsyncClient, admin_token_headers):
        response = await client.get("/api/playbook/publish/status", headers=admin_token_headers)
        assert response.status_code == 200
        assert response.json() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/playbook/test_publish_api.py -v`
Expected: FAIL

- [ ] **Step 3: Create the publish API router**

Create `backend/app/modules/playbook/api/publish.py`:
```python
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, desc

from app.core.auth import AdminUser
from app.database import DBSession
from app.core.deps import get_redis_pool
from app.modules.playbook.models.publish_log import PlaybookPublishLogDB

router = APIRouter()


class PublishResponse(BaseModel):
    publish_log_id: str


class PublishStatusResponse(BaseModel):
    status: str
    page_count: int | None
    started_at: str
    completed_at: str | None
    error_message: str | None

    model_config = {"from_attributes": True}


@router.post("/publish", status_code=status.HTTP_201_CREATED, response_model=PublishResponse)
async def publish_playbook(current_user: AdminUser, db: DBSession):
    running = await db.scalar(
        select(PlaybookPublishLogDB.id).where(PlaybookPublishLogDB.status == "running").limit(1)
    )
    if running:
        raise HTTPException(status_code=409, detail="A publish is already in progress")

    log = PlaybookPublishLogDB(status="running", published_by_id=current_user.user_id)
    db.add(log)
    await db.flush()

    pool = await get_redis_pool()
    await pool.enqueue_job("publish_playbook_task", publish_log_id=str(log.id))

    return PublishResponse(publish_log_id=str(log.id))


@router.get("/publish/status", response_model=PublishStatusResponse | None)
async def get_publish_status(current_user: AdminUser, db: DBSession):
    stmt = select(PlaybookPublishLogDB).order_by(desc(PlaybookPublishLogDB.started_at)).limit(1)
    log = await db.scalar(stmt)
    if not log:
        return None
    return log
```

- [ ] **Step 4: Mount in playbook router**

Add to `backend/app/modules/playbook/router.py`:
```python
from app.modules.playbook.api import publish as publish_router
router.include_router(publish_router.router, tags=["playbook:publish"])
```

Note: no prefix — the routes already include `/publish` in their paths.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/playbook/test_publish_api.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/playbook/api/publish.py backend/app/modules/playbook/router.py backend/tests/playbook/test_publish_api.py
git commit -m "feat(playbook): add publish API endpoints with concurrency guard"
```

---

### Task 10: Frontend — types, service, and query keys

**Files:**
- Modify: `frontend/src/modules/playbook/types/playbook.ts`
- Modify: `frontend/src/modules/playbook/services/playbook.ts`
- Modify: `frontend/src/core/hooks/queryKeys.ts`

- [ ] **Step 1: Add PublishStatus type**

Add to `frontend/src/modules/playbook/types/playbook.ts`:
```typescript
export interface PublishStatus {
  status: 'running' | 'completed' | 'failed';
  page_count: number | null;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}
```

- [ ] **Step 2: Add publish methods to service**

Add to `frontend/src/modules/playbook/services/playbook.ts`:
```typescript
import type { PublishStatus } from '../types/playbook';

// Add to playbookApi object:
  publishPlaybook: async (): Promise<{ publish_log_id: string }> => {
    const { data } = await api.post<{ publish_log_id: string }>('/playbook/publish');
    return data;
  },

  getPublishStatus: async (): Promise<PublishStatus | null> => {
    const { data } = await api.get<PublishStatus | null>('/playbook/publish/status');
    return data;
  },
```

- [ ] **Step 3: Add query key**

Add to `frontend/src/core/hooks/queryKeys.ts` in the `playbook` object:
```typescript
  publishStatus: ['playbook', 'publish', 'status'] as const,
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/playbook/types/playbook.ts frontend/src/modules/playbook/services/playbook.ts frontend/src/core/hooks/queryKeys.ts
git commit -m "feat(playbook): add publish types, service methods, and query keys"
```

---

### Task 11: Frontend — publish hooks

**Files:**
- Create: `frontend/src/modules/playbook/hooks/usePublishPlaybook.ts`
- Create: `frontend/src/modules/playbook/hooks/__tests__/usePublishPlaybook.test.ts`

- [ ] **Step 1: Create the hooks**

Create `frontend/src/modules/playbook/hooks/usePublishPlaybook.ts`:
```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/core/hooks/queryKeys';
import { playbookApi } from '../services/playbook';
import type { PublishStatus } from '../types/playbook';

export function usePublishPlaybook() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => playbookApi.publishPlaybook(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.playbook.publishStatus });
    },
  });
}

export function usePublishStatus() {
  return useQuery<PublishStatus | null>({
    queryKey: queryKeys.playbook.publishStatus,
    queryFn: playbookApi.getPublishStatus,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.status === 'running' ? 3000 : false;
    },
  });
}
```

- [ ] **Step 2: Write tests**

Create `frontend/src/modules/playbook/hooks/__tests__/usePublishPlaybook.test.ts`:
```typescript
import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { createWrapper } from '@/test-utils';
import { usePublishStatus } from '../usePublishPlaybook';
import { playbookApi } from '../../services/playbook';

vi.mock('../../services/playbook');

describe('usePublishStatus', () => {
  it('returns null when never published', async () => {
    vi.mocked(playbookApi.getPublishStatus).mockResolvedValue(null);
    const { result } = renderHook(() => usePublishStatus(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });

  it('returns status when published', async () => {
    vi.mocked(playbookApi.getPublishStatus).mockResolvedValue({
      status: 'completed',
      page_count: 5,
      started_at: '2026-03-29T10:00:00Z',
      completed_at: '2026-03-29T10:00:05Z',
      error_message: null,
    });
    const { result } = renderHook(() => usePublishStatus(), { wrapper: createWrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.status).toBe('completed');
    expect(result.current.data?.page_count).toBe(5);
  });
});
```

- [ ] **Step 3: Run tests**

Run: `cd frontend && npx vitest run src/modules/playbook/hooks/__tests__/usePublishPlaybook.test.ts`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/modules/playbook/hooks/usePublishPlaybook.ts frontend/src/modules/playbook/hooks/__tests__/usePublishPlaybook.test.ts
git commit -m "feat(playbook): add publish hooks with polling"
```

---

### Task 12: Frontend — Publish button in Playbook page

**Files:**
- Modify: `frontend/src/modules/playbook/pages/Playbook.tsx`
- Create: `frontend/src/modules/playbook/components/PublishButton.tsx`

- [ ] **Step 1: Create the PublishButton component**

Create `frontend/src/modules/playbook/components/PublishButton.tsx`:
```typescript
import { useState } from 'react';
import { Globe, Loader2 } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/shared/components/ui/alert-dialog';
import { useToast } from '@/shared/components/ui/use-toast';
import { usePublishPlaybook, usePublishStatus } from '../hooks/usePublishPlaybook';
import { formatDistanceToNow } from 'date-fns';

export function PublishButton() {
  const { toast } = useToast();
  const publish = usePublishPlaybook();
  const { data: status } = usePublishStatus();
  const [open, setOpen] = useState(false);

  const isPublishing = status?.status === 'running' || publish.isPending;

  const handlePublish = async (e: React.MouseEvent) => {
    e.preventDefault();
    setOpen(false);
    try {
      await publish.mutateAsync();
      toast({ title: 'Publishing started', description: 'The playbook is being published.' });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to start publish';
      toast({ title: 'Publish failed', description: message, variant: 'destructive' });
    }
  };

  const statusText = status?.status === 'completed' && status.completed_at
    ? `Published ${formatDistanceToNow(new Date(status.completed_at), { addSuffix: true })} (${status.page_count} pages)`
    : status?.status === 'failed'
    ? 'Last publish failed'
    : null;

  return (
    <div className="flex items-center gap-2">
      {statusText && (
        <span className="text-xs text-muted-foreground hidden sm:inline">{statusText}</span>
      )}
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogTrigger asChild>
          <Button size="sm" variant="outline" disabled={isPublishing}>
            {isPublishing ? (
              <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
            ) : (
              <Globe className="h-4 w-4 mr-1.5" />
            )}
            {isPublishing ? 'Publishing...' : 'Publish'}
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Publish Playbook</AlertDialogTitle>
            <AlertDialogDescription>
              This will publish all public pages to the external playbook site. Continue?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handlePublish}>Publish</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
```

- [ ] **Step 2: Add PublishButton to Playbook page header**

In `frontend/src/modules/playbook/pages/Playbook.tsx`, in the header toolbar area (where Edit button and dropdown live), add the PublishButton for admin users:

```typescript
import { PublishButton } from '../components/PublishButton';

// In the toolbar area, before the Edit button:
{isAdmin && <PublishButton />}
```

Check the existing code for where `isAdmin` or `isEditor` is defined and the exact JSX location for the toolbar.

- [ ] **Step 3: Watch for toast on successful publish completion**

The `usePublishStatus` hook polls while running. Add an effect in `PublishButton` to show a success toast when status transitions from `running` to `completed`:

```typescript
import { useRef, useEffect } from 'react';

// Inside PublishButton:
const prevStatusRef = useRef(status?.status);
useEffect(() => {
  if (prevStatusRef.current === 'running' && status?.status === 'completed') {
    toast({ title: 'Published', description: `${status.page_count} pages published successfully.` });
  }
  if (prevStatusRef.current === 'running' && status?.status === 'failed') {
    toast({ title: 'Publish failed', description: status.error_message || 'Unknown error', variant: 'destructive' });
  }
  prevStatusRef.current = status?.status;
}, [status?.status]);
```

- [ ] **Step 4: Test manually**

Run: `cd frontend && npm run dev`
- Navigate to Playbook page as admin
- Verify Publish button is visible
- Verify non-admin users don't see it
- Click Publish, verify confirmation dialog appears

- [ ] **Step 5: Commit**

```bash
git add frontend/src/modules/playbook/components/PublishButton.tsx frontend/src/modules/playbook/pages/Playbook.tsx
git commit -m "feat(playbook): add Publish button with status polling and confirmation dialog"
```

---

### Task 13: Integration test — full publish flow

**Files:**
- Create: `backend/tests/playbook/test_publish_integration.py`

- [ ] **Step 1: Write integration test**

Create `backend/tests/playbook/test_publish_integration.py`:
```python
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.modules.playbook.services.publish_service import PublishService


class TestPublishIntegration:
    @pytest.mark.asyncio
    async def test_full_publish_flow(self, db):
        """End-to-end: create tree → generate → verify HTML structure."""
        # Create a realistic tree
        culture = PlaybookNodeDB(title="Culture", slug="culture", type="group", position=0, is_public=True)
        db.add(culture)
        await db.flush()

        values = PlaybookNodeDB(title="Our Values", slug="our-values", type="page", parent_id=culture.id, position=0, is_public=True)
        growth = PlaybookNodeDB(title="Growth Framework", slug="growth-framework", type="page", parent_id=culture.id, position=1, is_public=True)
        db.add_all([values, growth])
        await db.flush()

        db.add(PlaybookPageVersionDB(node_id=values.id, content="## Core Values\n\nWe believe in **impact**.", version=1))
        db.add(PlaybookPageVersionDB(node_id=growth.id, content="## Growth\n\nContinuous learning.", version=1))
        await db.flush()

        svc = PublishService()
        files = await svc._generate_site(db)

        # Verify structure
        assert "index.html" in files
        assert "culture/our-values.html" in files
        assert "culture/growth-framework.html" in files
        assert "culture/index.html" in files
        assert "assets/style.css" in files
        assert "assets/navigation.js" in files

        # Verify content rendering
        values_html = files["culture/our-values.html"].decode()
        assert "<strong>impact</strong>" in values_html
        assert "Our Values" in values_html

        # Verify navigation
        assert "Culture" in values_html
        assert "Growth Framework" in values_html

        # Verify prev/next
        assert "growth-framework.html" in values_html

        # Verify manifest
        manifest = json.loads(files["manifest.json"])
        assert manifest["page_count"] == 2
        assert "culture/our-values.html" in manifest["files"]

    @pytest.mark.asyncio
    async def test_private_pages_excluded(self, db):
        """Private pages should not appear in generated site."""
        public = PlaybookNodeDB(title="Public", slug="public", type="page", position=0, is_public=True)
        private = PlaybookNodeDB(title="Private", slug="private", type="page", position=1, is_public=False)
        db.add_all([public, private])
        await db.flush()
        db.add(PlaybookPageVersionDB(node_id=public.id, content="visible", version=1))
        db.add(PlaybookPageVersionDB(node_id=private.id, content="hidden", version=1))
        await db.flush()

        svc = PublishService()
        files = await svc._generate_site(db)

        assert "public.html" in files
        assert "private.html" not in files

    @pytest.mark.asyncio
    async def test_non_public_group_included_if_has_public_children(self, db):
        """Non-public group with public descendants should appear in nav."""
        group = PlaybookNodeDB(title="Internal", slug="internal", type="group", position=0, is_public=False)
        db.add(group)
        await db.flush()
        page = PlaybookNodeDB(title="Visible", slug="visible", type="page", parent_id=group.id, position=0, is_public=True)
        db.add(page)
        await db.flush()
        db.add(PlaybookPageVersionDB(node_id=page.id, content="content", version=1))
        await db.flush()

        svc = PublishService()
        files = await svc._generate_site(db)

        assert "internal/visible.html" in files
        page_html = files["internal/visible.html"].decode()
        assert "Internal" in page_html
```

- [ ] **Step 2: Run tests**

Run: `cd backend && python -m pytest tests/playbook/test_publish_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/playbook/test_publish_integration.py
git commit -m "test(playbook): add integration tests for full publish flow"
```

---

### Task 14: Deploy updates

**Files:**
- Modify: `deploy.yml` or deployment scripts (if applicable)

- [ ] **Step 1: Run full test suite to verify nothing is broken**

Run: `cd backend && python -m pytest -x -q`
Run: `cd frontend && npm test`
Expected: All pass

- [ ] **Step 2: Run Alembic migration locally**

Run: `cd backend && alembic upgrade head`
Expected: Migration 038 applied successfully

- [ ] **Step 3: Commit any deploy config changes**

If deployment config needs updates (e.g., new env vars, Docker rebuild steps), commit them.

```bash
git commit -m "chore: update deploy config for playbook publish feature"
```
