"""Unit tests for registry attachment URL construction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.modules.iso_docs.services import registry_attachment_service as svc


def test_get_attachment_url_uses_cloudfront_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = MagicMock()
    settings.playbook_public_url = "https://playbook.vizzuality.com"
    settings.assets_bucket_name = "hub-assets"
    monkeypatch.setattr(svc, "get_settings", lambda: settings)

    url = svc.get_attachment_url("iso-registries/abc-report.pdf")

    assert url == "https://playbook.vizzuality.com/iso-registries/abc-report.pdf"


def test_get_attachment_url_falls_back_to_presigned_locally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = MagicMock()
    settings.playbook_public_url = ""
    settings.assets_bucket_name = "hub-assets"
    monkeypatch.setattr(svc, "get_settings", lambda: settings)

    client = MagicMock()
    client.generate_presigned_url.return_value = "https://s3.example/signed"
    monkeypatch.setattr(svc, "get_s3_client", lambda: client)

    url = svc.get_attachment_url("iso-registries/abc-report.pdf")

    assert url == "https://s3.example/signed"
    client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "hub-assets", "Key": "iso-registries/abc-report.pdf"},
        ExpiresIn=7 * 24 * 3600,
    )
