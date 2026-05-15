"""Publish service — tree query, navigation, rendering, and S3 upload."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import structlog
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.core.services.s3 import get_s3_client
from app.modules.playbook.services.asset_service import S3_PREFIX as IMAGES_S3_PREFIX
from app.modules.playbook.services.publish_renderer import render_markdown

logger = structlog.get_logger()

TEMPLATES_DIR = Path(__file__).parent / "publish_templates"
S3_PREFIX = "playbook/public/"

INDEX_HTML = "index.html"
NOT_FOUND_HTML = "404.html"
HTML_EXT = ".html"
INDEX_SUFFIX = "/index.html"

STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

CONTENT_TYPES = {
    HTML_EXT: "text/html; charset=utf-8",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
}


def _get_jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _base_url(path: str) -> str:
    depth = path.count("/")
    return "../" * depth if depth > 0 else ""


@dataclass
class PublicNode:
    id: str
    title: str
    slug: str
    type: str  # "page" | "group"
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
    node_map: dict[str, PublicNode] = field(default_factory=dict)


class PublishService:
    async def publish(self, db: AsyncSession, publish_log_id: str) -> None:
        from app.modules.playbook.models.publish_log import PlaybookPublishLogDB

        log_uuid = UUID(publish_log_id)
        log = await db.get(PlaybookPublishLogDB, log_uuid)

        try:
            logger.info("publish_started", publish_log_id=publish_log_id)
            files = await self._generate_site(db)
            await self._cleanup_orphans(set(files.keys()))
            await self._upload_site(files)
            await self._invalidate_cache()

            log.status = STATUS_COMPLETED
            log.page_count = len([
                k for k in files
                if k.endswith(HTML_EXT)
                and k not in (INDEX_HTML, NOT_FOUND_HTML)
                and INDEX_SUFFIX not in k
            ])
            log.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(
                "publish_completed",
                publish_log_id=publish_log_id,
                page_count=log.page_count,
            )

        except Exception as e:
            log.status = STATUS_FAILED
            log.error_message = str(e)
            log.completed_at = datetime.now(timezone.utc)
            await db.commit()
            logger.exception("publish_failed", publish_log_id=publish_log_id)

    async def _query_public_tree(self, db: AsyncSession) -> list[PublicNode]:
        """Fetch ALL nodes (pages + groups) with latest version content for pages."""
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

    def _has_public_descendant(
        self,
        node_id: str,
        node_map: dict[str, PublicNode],
        children_by_parent: dict[str | None, list[PublicNode]],
    ) -> bool:
        n = node_map[node_id]
        if n.type == "page" and n.is_public:
            return True
        return any(
            self._has_public_descendant(c.id, node_map, children_by_parent)
            for c in children_by_parent.get(node_id, [])
        )

    def _build_path(self, node: PublicNode, node_map: dict[str, PublicNode]) -> str:
        parts: list[str] = []
        current: PublicNode | None = node
        while current:
            parts.append(current.slug)
            current = node_map.get(current.parent_id) if current.parent_id else None
        parts.reverse()
        path = "/".join(parts)
        if node.type == "page":
            path += HTML_EXT
        return path

    def _build_breadcrumb(
        self, node: PublicNode, node_map: dict[str, PublicNode],
    ) -> list[dict]:
        parts: list[dict] = []
        current = node_map.get(node.parent_id) if node.parent_id else None
        while current:
            parts.append({
                "title": current.title,
                "url": self._build_path(current, node_map) + INDEX_SUFFIX,
            })
            current = node_map.get(current.parent_id) if current.parent_id else None
        parts.reverse()
        return parts

    def _build_subtree(
        self,
        parent_id: str | None,
        included_ids: set[str],
        node_map: dict[str, PublicNode],
        children_by_parent: dict[str | None, list[PublicNode]],
    ) -> list[NavNode]:
        children = sorted(
            [n for n in children_by_parent.get(parent_id, []) if n.id in included_ids],
            key=lambda n: n.position,
        )
        result: list[NavNode] = []
        for n in children:
            nav = NavNode(
                id=n.id,
                title=n.title,
                slug=n.slug,
                type=n.type,
                is_public=n.is_public,
                path=self._build_path(n, node_map),
                breadcrumb=self._build_breadcrumb(n, node_map),
            )
            if n.type == "group":
                nav.children = self._build_subtree(
                    n.id, included_ids, node_map, children_by_parent,
                )
            result.append(nav)
        return result

    def _collect_pages(self, nav_nodes: list[NavNode]) -> list[NavNode]:
        pages: list[NavNode] = []
        for n in nav_nodes:
            if n.type == "page" and n.is_public:
                pages.append(n)
            pages.extend(self._collect_pages(n.children))
        return pages

    def _build_nav_tree(self, nodes: list[PublicNode]) -> NavTree:
        """Build hierarchical navigation from flat node list."""
        node_map = {n.id: n for n in nodes}
        children_by_parent: dict[str | None, list[PublicNode]] = {}
        for n in nodes:
            children_by_parent.setdefault(n.parent_id, []).append(n)

        included_ids = {
            n.id for n in nodes
            if self._has_public_descendant(n.id, node_map, children_by_parent)
        }

        roots = self._build_subtree(None, included_ids, node_map, children_by_parent)
        all_pages = self._collect_pages(roots)

        for i, page in enumerate(all_pages):
            page.prev_page = all_pages[i - 1] if i > 0 else None
            page.next_page = all_pages[i + 1] if i < len(all_pages) - 1 else None

        return NavTree(roots=roots, all_pages=all_pages, node_map=node_map)

    @staticmethod
    def _rewrite_image_urls_relative(html: str, s3_image_prefix: str) -> str:
        """Replace S3 image URLs with site-relative /images/ paths."""
        if not s3_image_prefix:
            return html
        return html.replace(s3_image_prefix, "/images/")

    def _render_pages(
        self,
        nav: NavTree,
        node_map: dict[str, PublicNode],
        env: Environment,
        year: int,
    ) -> dict[str, bytes]:
        page_tpl = env.get_template("page.html")
        files: dict[str, bytes] = {}
        bucket_url = get_settings().assets_bucket_url
        s3_image_prefix = f"{bucket_url}/{IMAGES_S3_PREFIX}" if bucket_url else ""

        for page_nav in nav.all_pages:
            source_node = node_map.get(page_nav.id)
            raw_content = source_node.content if source_node else None
            content_html = render_markdown(raw_content, strip_leading_h1=True)
            content_html = self._rewrite_image_urls_relative(content_html, s3_image_prefix)

            html = page_tpl.render(
                title=page_nav.title,
                content=content_html,
                nav_tree=nav.roots,
                current_path=page_nav.path,
                base_url=_base_url(page_nav.path),
                breadcrumb=page_nav.breadcrumb,
                prev_page=page_nav.prev_page,
                next_page=page_nav.next_page,
                year=year,
            )
            files[page_nav.path] = html.encode()

        return files

    def _render_group_indexes(
        self,
        nav: NavTree,
        env: Environment,
        year: int,
    ) -> dict[str, bytes]:
        group_tpl = env.get_template("group.html")
        files: dict[str, bytes] = {}
        self._collect_group_indexes(nav.roots, "", group_tpl, nav, year, files)
        return files

    def _collect_group_indexes(
        self,
        nav_nodes: list[NavNode],
        parent_path: str,
        group_tpl: Template,
        nav: NavTree,
        year: int,
        files: dict[str, bytes],
    ) -> None:
        for node in nav_nodes:
            if node.type != "group":
                continue
            group_path = f"{parent_path}/{node.slug}" if parent_path else node.slug
            index_path = f"{group_path}{INDEX_SUFFIX}"
            first_child_page = self._first_public_child(node.children)

            html = group_tpl.render(
                title=node.title,
                children=self._build_children_links(node.children),
                nav_tree=nav.roots,
                current_path=node.path,
                base_url=_base_url(index_path),
                breadcrumb=node.breadcrumb,
                prev_page=first_child_page.prev_page if first_child_page else None,
                next_page=first_child_page,
                year=year,
            )
            files[index_path] = html.encode()

            self._collect_group_indexes(
                node.children, group_path, group_tpl, nav, year, files,
            )

    @staticmethod
    def _build_children_links(children: list[NavNode]) -> list[dict]:
        links: list[dict] = []
        for child in children:
            if child.type == "page" and child.is_public:
                links.append({"title": child.title, "url": child.path})
            elif child.type == "group":
                links.append({
                    "title": child.title,
                    "url": child.path + INDEX_SUFFIX,
                })
        return links

    @staticmethod
    def _first_public_child(children: list[NavNode]) -> NavNode | None:
        for child in children:
            if child.type == "page" and child.is_public:
                return child
        return None

    def _render_static_files(self) -> dict[str, bytes]:
        return {
            "assets/style.css": (TEMPLATES_DIR / "style.css").read_bytes(),
            "assets/navigation.js": (TEMPLATES_DIR / "navigation.js").read_bytes(),
        }

    def _build_manifest(self, files: dict[str, bytes], page_count: int) -> bytes:
        manifest = {
            "published_at": datetime.now(timezone.utc).isoformat(),
            "page_count": page_count,
            "files": sorted(files.keys()),
        }
        return json.dumps(manifest, indent=2).encode()

    async def _generate_site(self, db: AsyncSession) -> dict[str, bytes]:
        """Render all public pages into a static site file map (key -> bytes)."""
        nodes = await self._query_public_tree(db)
        nav = self._build_nav_tree(nodes)

        if not nav.all_pages:
            raise ValueError("No public pages to publish")

        env = _get_jinja_env()
        year = datetime.now(timezone.utc).year

        files: dict[str, bytes] = {}
        files.update(self._render_pages(nav, nav.node_map, env, year))
        files.update(self._render_group_indexes(nav, env, year))

        index_tpl = env.get_template(INDEX_HTML)
        not_found_tpl = env.get_template(NOT_FOUND_HTML)

        files[INDEX_HTML] = index_tpl.render(
            title="Vizzuality Playbook",
            nav_tree=nav.roots,
            current_path="",
            base_url="",
            breadcrumb=[],
            prev_page=None,
            next_page=None,
            year=year,
        ).encode()

        files[NOT_FOUND_HTML] = not_found_tpl.render(
            base_url="",
            year=year,
        ).encode()

        files.update(self._render_static_files())
        files["manifest.json"] = self._build_manifest(files, len(nav.all_pages))

        return files

    async def _upload_site(self, files: dict[str, bytes]) -> None:
        """Upload all generated files to S3."""
        settings = get_settings()
        s3 = get_s3_client()

        for key, body in files.items():
            ext = Path(key).suffix
            content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
            await asyncio.to_thread(
                s3.put_object,
                Bucket=settings.assets_bucket_name,
                Key=f"{S3_PREFIX}{key}",
                Body=body,
                ContentType=content_type,
            )

    async def _cleanup_orphans(self, current_files: set[str]) -> int:
        """Delete S3 files from previous publish that are no longer in current set."""
        settings = get_settings()
        s3 = get_s3_client()

        try:
            response = await asyncio.to_thread(
                s3.get_object,
                Bucket=settings.assets_bucket_name,
                Key=f"{S3_PREFIX}manifest.json",
            )
            old_manifest = json.loads(response["Body"].read())
        except s3.exceptions.NoSuchKey:
            return 0

        old_files = set(old_manifest.get("files", []))
        orphans = old_files - current_files
        deleted = 0

        for orphan_key in orphans:
            await asyncio.to_thread(
                s3.delete_object,
                Bucket=settings.assets_bucket_name,
                Key=f"{S3_PREFIX}{orphan_key}",
            )
            deleted += 1

        if deleted:
            logger.info("publish_orphans_cleaned", count=deleted)

        return deleted

    async def _invalidate_cache(self) -> None:
        """Create CloudFront invalidation for all playbook paths."""
        settings = get_settings()
        distribution_id = settings.playbook_cloudfront_distribution_id
        if not distribution_id:
            return

        import boto3
        cf = boto3.client("cloudfront")
        caller_ref = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

        await asyncio.to_thread(
            cf.create_invalidation,
            DistributionId=distribution_id,
            InvalidationBatch={
                "Paths": {"Quantity": 1, "Items": ["/*"]},
                "CallerReference": caller_ref,
            },
        )
        logger.info("cloudfront_cache_invalidated", distribution_id=distribution_id)
