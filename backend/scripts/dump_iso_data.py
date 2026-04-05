"""Dump ISO Docs data as SQL INSERT statements for production migration.

Generates a self-contained SQL script that:
1. Resolves the target user by email
2. Inserts registry_types, iso_doc_nodes (roots then children), iso_doc_metadata,
   iso_doc_versions, and registry_rows in FK-safe order
3. Maps all created_by_id/updated_by_id to the target user

Run: python -m scripts.dump_iso_data > iso_data_dump.sql
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import Base  # noqa: F401
from app.core.models.user import UserDB  # noqa: F401

TARGET_EMAIL = "miguel.mendoza@vizzuality.com"


def sql_val(v: object) -> str:
    """Format a Python value as a SQL literal."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, UUID):
        return f"'{v}'"
    if isinstance(v, datetime):
        return f"'{v.isoformat()}'"
    if isinstance(v, date):
        return f"'{v.isoformat()}'"
    if isinstance(v, (dict, list)):
        return f"'{json.dumps(v, default=str).replace(chr(39), chr(39)+chr(39))}'"
    s = str(v).replace("'", "''")
    return f"'{s}'"


def sql_array(arr: list[str] | None) -> str:
    """Format a Python list as a PostgreSQL ARRAY literal."""
    if arr is None:
        return "NULL"
    items = ", ".join(f"'{s.replace(chr(39), chr(39)+chr(39))}'" for s in arr)
    return f"ARRAY[{items}]"


async def dump() -> None:
    engine = create_async_engine(get_settings().database_url)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    out = sys.stdout
    out.write("-- ISO Docs data migration\n")
    out.write("-- Generated from local dev database\n")
    out.write(f"-- Target user: {TARGET_EMAIL}\n\n")
    # Everything inside a DO block so target_uid variable is available
    out.write(f"DO $$\nDECLARE\n  target_uid UUID;\nBEGIN\n")
    out.write(f"  -- Resolve target user\n")
    out.write(f"  SELECT id INTO target_uid FROM users WHERE email = '{TARGET_EMAIL}';\n")
    out.write(f"  IF target_uid IS NULL THEN\n")
    out.write(f"    RAISE EXCEPTION 'User {TARGET_EMAIL} not found in production';\n")
    out.write(f"  END IF;\n\n")
    out.write(f"  -- Clean existing ISO data (FK-safe order)\n")
    out.write(f"  DELETE FROM registry_rows;\n")
    out.write(f"  DELETE FROM registry_attachments;\n")
    out.write(f"  DELETE FROM iso_doc_versions;\n")
    out.write(f"  DELETE FROM iso_doc_metadata;\n")
    out.write(f"  DELETE FROM iso_doc_drive_mappings;\n")
    out.write(f"  DELETE FROM iso_doc_nodes;\n")
    out.write(f"  DELETE FROM registry_types;\n\n")

    async with sm() as db:
        # 1. Registry types
        rows = (await db.execute(text(
            "SELECT id, name, slug, description, is_yearly, schema, default_sort_key, "
            "created_at, updated_at FROM registry_types ORDER BY name"
        ))).all()
        out.write(f"  -- Registry types ({len(rows)})\n")
        for r in rows:
            out.write(
                f"  INSERT INTO registry_types (id, name, slug, description, is_yearly, schema, "
                f"default_sort_key, created_by_id, updated_by_id, created_at, updated_at) VALUES ("
                f"{sql_val(r.id)}, {sql_val(r.name)}, {sql_val(r.slug)}, {sql_val(r.description)}, "
                f"{sql_val(r.is_yearly)}, {sql_val(r.schema)}, {sql_val(r.default_sort_key)}, "
                f"target_uid, target_uid, {sql_val(r.created_at)}, {sql_val(r.updated_at)}"
                f") ON CONFLICT (slug) DO NOTHING;\n"
            )
        out.write("\n")

        # 2. ISO doc nodes — topological order (parents before children)
        all_nodes = (await db.execute(text(
            "SELECT id, title, slug, type, parent_id, position, registry_type_id, "
            "created_at, updated_at FROM iso_doc_nodes ORDER BY position"
        ))).all()
        by_id = {r.id: r for r in all_nodes}
        ordered: list = []
        visited: set = set()

        def visit(node_id: object) -> None:
            if node_id in visited:
                return
            node = by_id[node_id]
            if node.parent_id and node.parent_id not in visited:
                visit(node.parent_id)
            visited.add(node_id)
            ordered.append(node)

        for n in all_nodes:
            visit(n.id)

        out.write(f"  -- ISO doc nodes ({len(ordered)})\n")
        for r in ordered:
            out.write(
                f"  INSERT INTO iso_doc_nodes (id, title, slug, type, parent_id, position, "
                f"registry_type_id, created_by_id, updated_by_id, created_at, updated_at) VALUES ("
                f"{sql_val(r.id)}, {sql_val(r.title)}, {sql_val(r.slug)}, {sql_val(r.type)}, "
                f"{sql_val(r.parent_id)}, {sql_val(r.position)}, {sql_val(r.registry_type_id)}, "
                f"target_uid, target_uid, {sql_val(r.created_at)}, {sql_val(r.updated_at)}"
                f") ON CONFLICT (id) DO NOTHING;\n"
            )
        out.write("\n")

        # 3. ISO doc metadata
        rows = (await db.execute(text(
            "SELECT id, node_id, code, standard, clauses, category, doc_version, status, "
            "classification, document_date, original_filename, guidance, changelog, "
            "created_at, updated_at FROM iso_doc_metadata ORDER BY code"
        ))).all()
        out.write(f"  -- ISO doc metadata ({len(rows)})\n")
        for r in rows:
            out.write(
                f"  INSERT INTO iso_doc_metadata (id, node_id, code, standard, clauses, category, "
                f"doc_version, status, classification, document_date, original_filename, guidance, "
                f"changelog, created_at, updated_at) VALUES ("
                f"{sql_val(r.id)}, {sql_val(r.node_id)}, {sql_val(r.code)}, "
                f"{sql_array(r.standard)}, {sql_array(r.clauses)}, "
                f"{sql_val(r.category)}, {sql_val(r.doc_version)}, {sql_val(r.status)}, "
                f"{sql_val(r.classification)}, {sql_val(r.document_date)}, "
                f"{sql_val(r.original_filename)}, {sql_val(r.guidance)}, "
                f"{sql_val(r.changelog)}, {sql_val(r.created_at)}, {sql_val(r.updated_at)}"
                f") ON CONFLICT ON CONSTRAINT uq_iso_doc_metadata_node DO NOTHING;\n"
            )
        out.write("\n")

        # 4. ISO doc versions (page content)
        rows = (await db.execute(text(
            "SELECT id, node_id, version, content, created_at "
            "FROM iso_doc_versions ORDER BY node_id, version"
        ))).all()
        out.write(f"  -- ISO doc versions ({len(rows)})\n")
        for r in rows:
            out.write(
                f"  INSERT INTO iso_doc_versions (id, node_id, version, content, "
                f"created_by_id, created_at) VALUES ("
                f"{sql_val(r.id)}, {sql_val(r.node_id)}, {sql_val(r.version)}, "
                f"{sql_val(r.content)}, target_uid, {sql_val(r.created_at)}"
                f") ON CONFLICT (id) DO NOTHING;\n"
            )
        out.write("\n")

        # 5. Registry rows
        rows = (await db.execute(text(
            "SELECT id, node_id, year, row_index, data, created_at, updated_at "
            "FROM registry_rows ORDER BY node_id, row_index"
        ))).all()
        out.write(f"  -- Registry rows ({len(rows)})\n")
        for r in rows:
            out.write(
                f"  INSERT INTO registry_rows (id, node_id, year, row_index, data, "
                f"created_by_id, updated_by_id, created_at, updated_at) VALUES ("
                f"{sql_val(r.id)}, {sql_val(r.node_id)}, {sql_val(r.year)}, "
                f"{sql_val(r.row_index)}, {sql_val(r.data)}, "
                f"target_uid, target_uid, {sql_val(r.created_at)}, {sql_val(r.updated_at)}"
                f") ON CONFLICT (id) DO NOTHING;\n"
            )
        out.write("\n")

    out.write("END;\n$$;\n")
    out.write("\n-- Done. Verify with:\n")
    out.write("-- SELECT count(*) FROM iso_doc_nodes;\n")
    out.write("-- SELECT count(*) FROM registry_types;\n")
    out.write("-- SELECT count(*) FROM registry_rows;\n")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(dump())
