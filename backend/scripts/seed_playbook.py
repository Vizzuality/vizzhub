"""Seed playbook from a folder of markdown files.

Usage:
    python scripts/seed_playbook.py /path/to/playbook [--clear]

Tree structure is derived from folders (-> groups) and .md files (-> pages).
Files prefixed with "private_" or "private " are marked is_public=False.
Images are ignored. README.md at root is ignored.
Internal GitHub links are converted to /playbook?page=<slug-path>.
"""

import asyncio
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote
from uuid import uuid4

from sqlalchemy import select, delete

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker
from app.core.models.user import UserDB  # noqa: F401 -- registers 'users' table for FK resolution
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB

IGNORED_FILES = {"README.md", ".DS_Store", ".gitignore", ".gitmodules"}
IGNORED_DIRS = {".git", "images", "__pycache__"}

GITHUB_LINK_RE = re.compile(
    r"https?://github\.com/Vizzuality/playbook/blob/[^/]+/([^#)\s]+)(?:#[^\s)]*)?(?=\))"
)
VIZZUALITY_LINK_RE = re.compile(
    r"https?://playbook\.vizzuality\.com/view-md/([^#)\s]+)(?:#[^\s)]*)?(?=\))"
)


def generate_slug(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    no_quotes = re.sub(r"['\"]", "", ascii_text)
    lowered = no_quotes.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "untitled"


def parse_filename(filename: str) -> tuple[str, bool]:
    """Extract title and is_public from filename. Returns (title, is_public)."""
    name = filename.removesuffix(".md").strip()
    is_private = name.startswith("private_") or name.startswith("private ")
    if is_private:
        name = re.sub(r"^private[_ ]", "", name).strip()
    return name, not is_private


def _build_file_to_slug_map(
    directory: Path,
    root: Path,
    parent_slug_path: str = "",
) -> dict[str, str]:
    """Build a map from relative file path -> slug path for link conversion."""
    mapping: dict[str, str] = {}
    entries = sorted(directory.iterdir(), key=lambda p: p.name.lower())

    dirs = [e for e in entries if e.is_dir() and e.name not in IGNORED_DIRS]
    files = [
        e for e in entries
        if e.is_file() and e.suffix == ".md"
        and e.name not in IGNORED_FILES
        and not e.name.startswith("._")
    ]

    for d in dirs:
        group_slug = generate_slug(d.name.strip())
        group_path = f"{parent_slug_path}/{group_slug}" if parent_slug_path else group_slug
        child_map = _build_file_to_slug_map(d, root, group_path)
        mapping.update(child_map)

    for f in files:
        title, _ = parse_filename(f.name)
        page_slug = generate_slug(title)
        slug_path = f"{parent_slug_path}/{page_slug}" if parent_slug_path else page_slug
        rel_path = str(f.relative_to(root))
        mapping[rel_path] = slug_path

    return mapping


def _extract_anchor(full_match: str) -> str:
    hash_idx = full_match.find("#")
    return full_match[hash_idx:] if hash_idx != -1 else ""


def _resolve_path(raw_path: str, file_slug_map: dict[str, str]) -> str | None:
    """Try to match a raw path (with or without .md) against the slug map."""
    for file_path, slug_path in file_slug_map.items():
        bare = file_path.removesuffix(".md")
        if raw_path in (file_path, bare) or raw_path.endswith(file_path) or raw_path.endswith(bare):
            return slug_path
    return None


def _convert_links(content: str, file_slug_map: dict[str, str]) -> str:
    """Replace GitHub and playbook.vizzuality.com links with /playbook?page=<slug-path>."""
    def replace_match(m: re.Match) -> str:
        raw_path = unquote(m.group(1))
        slug_path = _resolve_path(raw_path, file_slug_map)
        if slug_path:
            anchor = _extract_anchor(m.group(0))
            return f"/playbook?page={slug_path}{anchor}"
        return m.group(0)

    content = GITHUB_LINK_RE.sub(replace_match, content)
    content = VIZZUALITY_LINK_RE.sub(replace_match, content)
    return content


def scan_directory(
    directory: Path,
    parent_id=None,
    position_start: int = 0,
    file_slug_map: dict[str, str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Recursively scan a directory and return (nodes, versions) to insert."""
    nodes = []
    versions = []
    position = position_start

    entries = sorted(directory.iterdir(), key=lambda p: p.name.lower())

    dirs = [e for e in entries if e.is_dir() and e.name not in IGNORED_DIRS]
    files = [
        e
        for e in entries
        if e.is_file() and e.suffix == ".md"
        and e.name not in IGNORED_FILES
        and not e.name.startswith("._")
    ]

    for d in dirs:
        group_title = d.name.strip()
        group_id = uuid4()
        group_slug = generate_slug(group_title)

        nodes.append({
            "id": group_id,
            "title": group_title,
            "slug": group_slug,
            "type": "group",
            "parent_id": parent_id,
            "position": position,
            "is_public": False,
        })
        position += 1

        child_nodes, child_versions = scan_directory(
            d, parent_id=group_id, file_slug_map=file_slug_map,
        )
        nodes.extend(child_nodes)
        versions.extend(child_versions)

    for f in files:
        title, is_public = parse_filename(f.name)
        page_id = uuid4()
        page_slug = generate_slug(title)

        nodes.append({
            "id": page_id,
            "title": title,
            "slug": page_slug,
            "type": "page",
            "parent_id": parent_id,
            "position": position,
            "is_public": is_public,
        })
        position += 1

        try:
            content = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = f.read_text(encoding="latin-1")
        if file_slug_map:
            content = _convert_links(content, file_slug_map)
        versions.append({
            "id": uuid4(),
            "node_id": page_id,
            "content": content,
            "version": 1,
            "created_by_id": None,
        })

    return nodes, versions


async def seed_playbook(source_dir: str, clear: bool = False) -> None:
    source = Path(source_dir)
    if not source.is_dir():
        print(f"Error: {source_dir} is not a directory")
        sys.exit(1)

    file_slug_map = _build_file_to_slug_map(source, source)
    nodes, versions = scan_directory(source, file_slug_map=file_slug_map)

    print(f"Found {len(nodes)} nodes ({sum(1 for n in nodes if n['type'] == 'group')} groups, "
          f"{sum(1 for n in nodes if n['type'] == 'page')} pages)")

    async with async_session_maker() as db:
        if clear:
            await db.execute(delete(PlaybookPageVersionDB))
            await db.execute(delete(PlaybookNodeDB))
            print("Cleared existing playbook data")

        existing = await db.execute(select(PlaybookNodeDB.id).limit(1))
        if existing.scalar_one_or_none() is not None and not clear:
            print("Playbook already has data. Use --clear to replace it.")
            return

        for node_data in nodes:
            node = PlaybookNodeDB(**node_data)
            db.add(node)
        await db.flush()

        for version_data in versions:
            version = PlaybookPageVersionDB(**version_data)
            db.add(version)

        await db.commit()
        print(f"Seeded {len(nodes)} nodes and {len(versions)} page versions")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_playbook.py /path/to/playbook [--clear]")
        sys.exit(1)

    source_path = sys.argv[1]
    clear_flag = "--clear" in sys.argv

    asyncio.run(seed_playbook(source_path, clear=clear_flag))
