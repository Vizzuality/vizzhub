"""Seed ISO documentation from a folder of markdown files with YAML frontmatter.

Usage:
    python scripts/seed_iso_docs.py /path/to/md-docs [--clear]

Each .md file must have YAML frontmatter with at least `title` and `category`.
Tree structure: groups from categories, pages from documents.
"""

import asyncio
import re
import sys
from pathlib import Path
from uuid import uuid4

import yaml
from sqlalchemy import select, delete

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.services.tree_service import generate_slug
from app.database import async_session_maker
from app.core.models.user import UserDB  # noqa: F401
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB


CATEGORY_ORDER = ["manual", "policy", "procedure", "plan", "record", "report"]
CATEGORY_LABELS = {
    "manual": "Manual",
    "policy": "Policies",
    "procedure": "Procedures",
    "plan": "Plans",
    "record": "Records",
    "report": "Reports",
}


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and remaining content from markdown."""
    if not text.startswith("---"):
        return {}, text

    end = text.find("---", 3)
    if end == -1:
        return {}, text

    yaml_block = text[3:end].strip()
    content = text[end + 3:].strip()

    try:
        meta = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        meta = {}

    return meta, content


def resolve_cross_links(content: str, slug_by_filename: dict[str, str]) -> str:
    """Replace .md cross-references with internal navigation links.

    Handles two formats:
    - Proper markdown: [text](filename.md) → [text](/iso/docs?page=slug)
    - Malformed (missing parens): [text]filename.md → [text](/iso/docs?page=slug)
    """
    def replace_proper(m: re.Match) -> str:
        filename = m.group(1)
        slug = slug_by_filename.get(filename)
        if slug:
            return f"(/iso/docs?page={slug})"
        return m.group(0)

    def replace_malformed(m: re.Match) -> str:
        text = m.group(1)
        filename = m.group(2)
        slug = slug_by_filename.get(filename)
        if slug:
            return f"[{text}](/iso/docs?page={slug})"
        return m.group(0)

    # First: proper markdown links [text](filename.md)
    content = re.sub(r"\(([a-z0-9][a-z0-9-]*\.md)\)", replace_proper, content)
    # Second: malformed links [text]filename.md (missing parens)
    content = re.sub(
        r"\[([^\]]+)\]([a-z0-9][a-z0-9-]*\.md)",
        replace_malformed,
        content,
    )
    return content


def scan_docs(source: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Parse all .md files, return (nodes, versions, metadata_records)."""
    nodes: list[dict] = []
    versions: list[dict] = []
    metadata_records: list[dict] = []

    docs_by_category: dict[str, list[tuple[dict, str, str]]] = {}

    for f in sorted(source.glob("*.md"), key=lambda p: p.name.lower()):
        if f.name.startswith("."):
            continue

        text = f.read_text(encoding="utf-8")
        meta, content = parse_frontmatter(text)

        if not meta.get("title"):
            print(f"  Skipping {f.name}: no title in frontmatter")
            continue

        category = meta.get("category", "record")
        if category not in docs_by_category:
            docs_by_category[category] = []
        docs_by_category[category].append((meta, content, f.name))

    # Build filename -> full slug path (group/page) for cross-link resolution
    slug_by_filename: dict[str, str] = {}
    for category, cat_docs in docs_by_category.items():
        group_label = CATEGORY_LABELS.get(category, category.title())
        group_slug = generate_slug(group_label)
        for meta, _, filename in cat_docs:
            page_slug = generate_slug(meta["title"])
            slug_by_filename[filename] = f"{group_slug}/{page_slug}"

    def _add_category_group(
        category: str,
        cat_docs: list[tuple[dict, str, str]],
        group_position: int,
    ) -> int:
        """Create a group node and its child pages. Returns next group_position."""
        group_label = CATEGORY_LABELS.get(category, category.title())
        group_id = uuid4()

        nodes.append({
            "id": group_id,
            "title": group_label,
            "slug": generate_slug(group_label),
            "type": "group",
            "parent_id": None,
            "position": group_position,
        })

        for page_pos, (meta, content, filename) in enumerate(cat_docs):
            content = resolve_cross_links(content, slug_by_filename)
            page_id = uuid4()

            nodes.append({
                "id": page_id,
                "title": meta["title"],
                "slug": generate_slug(meta["title"]),
                "type": "page",
                "parent_id": group_id,
                "position": page_pos,
            })

            versions.append({
                "id": uuid4(),
                "node_id": page_id,
                "content": content,
                "version": 1,
                "created_by_id": None,
            })

            changelog = meta.get("changelog")
            if changelog:
                changelog = [
                    {
                        "version": str(entry.get("version", "")),
                        "date": str(entry.get("date", "")),
                        "author": str(entry.get("author", "")),
                        "description": str(entry.get("description", "")),
                    }
                    for entry in changelog
                ]

            clauses = meta.get("clauses")
            if clauses:
                clauses = [str(c) for c in clauses]
            standard = meta.get("standard")
            if standard:
                standard = [str(s) for s in standard]

            metadata_records.append({
                "id": uuid4(),
                "node_id": page_id,
                "code": meta.get("code") or None,
                "standard": standard,
                "clauses": clauses,
                "category": meta.get("category"),
                "doc_version": str(meta.get("version", "")) or None,
                "status": meta.get("status"),
                "original_filename": meta.get("original_filename"),
                "changelog": changelog,
            })

        return group_position + 1

    # Create groups and pages in defined order, then any remaining categories
    group_position = 0
    for category in CATEGORY_ORDER:
        cat_docs = docs_by_category.pop(category, [])
        if not cat_docs:
            continue
        group_position = _add_category_group(category, cat_docs, group_position)

    for category, cat_docs in docs_by_category.items():
        group_position = _add_category_group(category, cat_docs, group_position)

    return nodes, versions, metadata_records


async def seed_iso_docs(source_dir: str, clear: bool = False) -> None:
    source = Path(source_dir)
    if not source.is_dir():
        print(f"Error: {source_dir} is not a directory")
        sys.exit(1)

    nodes, versions, metadata_records = scan_docs(source)

    groups = sum(1 for n in nodes if n["type"] == "group")
    pages = sum(1 for n in nodes if n["type"] == "page")
    print(f"Found {len(nodes)} nodes ({groups} groups, {pages} pages)")
    print(f"  {len(versions)} page versions, {len(metadata_records)} metadata records")

    async with async_session_maker() as db:
        if clear:
            await db.execute(delete(IsoDocMetadataDB))
            await db.execute(delete(IsoDocVersionDB))
            await db.execute(delete(IsoDocNodeDB))
            print("Cleared existing ISO docs data")

        existing = await db.execute(select(IsoDocNodeDB.id).limit(1))
        if existing.scalar_one_or_none() is not None and not clear:
            print("ISO docs already has data. Use --clear to replace it.")
            return

        for node_data in nodes:
            db.add(IsoDocNodeDB(**node_data))
        await db.flush()

        for version_data in versions:
            db.add(IsoDocVersionDB(**version_data))

        for meta_data in metadata_records:
            db.add(IsoDocMetadataDB(**meta_data))

        await db.commit()
        print(f"Seeded {len(nodes)} nodes, {len(versions)} versions, "
              f"{len(metadata_records)} metadata records")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python scripts/seed_iso_docs.py "/path/to/md docs" [--clear]')
        sys.exit(1)

    source_path = sys.argv[1]
    clear_flag = "--clear" in sys.argv

    asyncio.run(seed_iso_docs(source_path, clear=clear_flag))
