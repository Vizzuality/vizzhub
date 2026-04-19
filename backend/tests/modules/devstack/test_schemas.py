"""Tests for devstack Pydantic schemas."""

from datetime import datetime, timezone
from uuid import uuid4

from app.modules.devstack.schemas import EntryResponse


def test_entry_response_includes_new_fields():
    now = datetime.now(timezone.utc)
    response = EntryResponse(
        id=uuid4(),
        name="test",
        description="d",
        type="skill",
        install_method="github",
        required=False,
        origin="internal",
        active=True,
        featured=False,
        install_count=42,
        last_installed_at=now,
        deprecated=True,
        deprecation_message="use other",
        vulnerabilities={
            "critical": 1,
            "high": 0,
            "moderate": 0,
            "low": 0,
            "advisories": [{"id": "GHSA-x", "severity": "critical", "title": "t", "url": "u"}],
        },
        created_at=now,
        updated_at=now,
    )

    dumped = response.model_dump()
    assert dumped["install_count"] == 42
    assert dumped["deprecated"] is True
    assert dumped["vulnerabilities"]["critical"] == 1
