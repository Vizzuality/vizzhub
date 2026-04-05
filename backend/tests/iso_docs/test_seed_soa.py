"""Tests for SOA controls seed script."""

import pytest

from scripts.seed_soa_controls import (
    ANNEX_A_CONTROLS_EN,
    build_soa_rows,
)


def test_annex_a_has_93_controls() -> None:
    assert len(ANNEX_A_CONTROLS_EN) == 93


def test_annex_a_section_counts() -> None:
    by_section: dict[str, int] = {}
    for code in ANNEX_A_CONTROLS_EN:
        section = code.split(".")[0]
        by_section[section] = by_section.get(section, 0) + 1

    assert by_section == {"5": 37, "6": 8, "7": 14, "8": 34}


def test_build_soa_rows_produces_93_rows() -> None:
    rows = build_soa_rows()
    assert len(rows) == 93


def test_build_soa_rows_have_required_fields() -> None:
    rows = build_soa_rows()
    required_keys = {"control_id", "control_name", "applicable", "implementation_status"}

    for row in rows:
        missing = required_keys - row.keys()
        assert not missing, f"Row {row.get('control_id')} missing keys: {missing}"
        assert row["control_id"].startswith("A.")
        assert isinstance(row["control_name"], str) and len(row["control_name"]) > 0
        assert isinstance(row["applicable"], bool)
        assert row["implementation_status"] in {
            "Implemented", "Partially Implemented", "Planned", "Not Implemented", "N/A",
        }


def test_build_soa_rows_control_ids_are_sequential() -> None:
    rows = build_soa_rows()
    ids = [r["control_id"] for r in rows]

    assert ids[0] == "A.5.1"
    assert ids[-1] == "A.8.34"
    assert "A.6.1" in ids
    assert "A.7.1" in ids
    assert "A.8.1" in ids


def test_build_soa_rows_categories() -> None:
    rows = build_soa_rows()
    cats = {}
    for r in rows:
        cat = r["category"]
        cats[cat] = cats.get(cat, 0) + 1

    assert cats == {
        "Organizational": 37,
        "People": 8,
        "Physical": 14,
        "Technological": 34,
    }


def test_build_soa_rows_have_spanish_names() -> None:
    """Excel data should populate control_name_es for most controls."""
    rows = build_soa_rows()
    with_es = [r for r in rows if r.get("control_name_es")]
    assert len(with_es) >= 90, f"Only {len(with_es)} rows have Spanish names"


def test_build_soa_rows_control_types_are_valid() -> None:
    rows = build_soa_rows()
    valid_types = {"Preventive", "Detective", "Corrective", None}
    for row in rows:
        assert row.get("control_type") in valid_types, (
            f"Row {row['control_id']} has invalid type: {row.get('control_type')}"
        )


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session, client) -> None:
    """Running seed twice should not create duplicate rows."""
    from sqlalchemy import func, select

    from app.modules.iso_docs.models.node import IsoDocNodeDB
    from app.modules.iso_docs.models.registry_row import RegistryRowDB
    from app.modules.iso_docs.models.registry_type import RegistryTypeDB

    rt = RegistryTypeDB(
        name="Statement of Applicability",
        slug="statement-of-applicability",
        description="Test SOA",
        schema=[{"key": "control_id", "label": "Control ID", "type": "string", "required": True}],
    )
    db_session.add(rt)
    await db_session.flush()

    node = IsoDocNodeDB(
        title="SOA Test",
        slug="statement-of-applicability",
        type="registry",
        position=0,
        registry_type_id=rt.id,
    )
    db_session.add(node)
    await db_session.flush()

    db_session.add(RegistryRowDB(node_id=node.id, row_index=0, data={"control_id": "A.5.1"}))
    await db_session.flush()

    from scripts.seed_soa_controls import seed

    count = await seed(db_url=str(db_session.bind.url))
    assert count == 0

    row_count = (await db_session.execute(
        select(func.count()).where(RegistryRowDB.node_id == node.id)
    )).scalar()
    assert row_count == 1
