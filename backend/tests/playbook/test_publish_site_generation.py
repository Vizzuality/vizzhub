"""Tests for PublishService site generation, S3 upload, and orphan cleanup."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.modules.playbook.services.publish_service import PublishService


class TestGenerateSite:
    @pytest.mark.asyncio
    async def test_generates_all_expected_files(self, db_session):
        svc = PublishService()
        group = PlaybookNodeDB(
            title="Culture",
            slug="culture",
            type="group",
            position=0,
            is_public=True,
        )
        db_session.add(group)
        await db_session.flush()
        page = PlaybookNodeDB(
            title="Values",
            slug="values",
            type="page",
            parent_id=group.id,
            position=0,
            is_public=True,
        )
        db_session.add(page)
        await db_session.flush()
        db_session.add(
            PlaybookPageVersionDB(
                node_id=page.id,
                content="# Our Values\n\nWe believe in **impact**.",
                version=1,
            ),
        )
        await db_session.flush()

        files = await svc._generate_site(db_session)

        assert "index.html" in files
        assert "404.html" in files
        assert "assets/style.css" in files
        assert "assets/navigation.js" in files
        assert "culture/values.html" in files
        assert "culture/index.html" in files
        assert "manifest.json" in files

    @pytest.mark.asyncio
    async def test_page_html_contains_rendered_content(self, db_session):
        svc = PublishService()
        page = PlaybookNodeDB(
            title="Hello",
            slug="hello",
            type="page",
            position=0,
            is_public=True,
        )
        db_session.add(page)
        await db_session.flush()
        db_session.add(
            PlaybookPageVersionDB(node_id=page.id, content="**bold text**", version=1),
        )
        await db_session.flush()

        files = await svc._generate_site(db_session)
        html = files["hello.html"].decode()

        assert "<strong>bold text</strong>" in html
        assert "Hello" in html
        assert "Vizzuality" in html

    @pytest.mark.asyncio
    async def test_empty_public_pages_raises(self, db_session):
        svc = PublishService()
        page = PlaybookNodeDB(
            title="Private",
            slug="private",
            type="page",
            position=0,
            is_public=False,
        )
        db_session.add(page)
        await db_session.flush()
        db_session.add(
            PlaybookPageVersionDB(node_id=page.id, content="secret", version=1),
        )
        await db_session.flush()

        with pytest.raises(ValueError, match="No public pages"):
            await svc._generate_site(db_session)

    @pytest.mark.asyncio
    async def test_manifest_contains_file_list(self, db_session):
        svc = PublishService()
        page = PlaybookNodeDB(
            title="Test",
            slug="test",
            type="page",
            position=0,
            is_public=True,
        )
        db_session.add(page)
        await db_session.flush()
        db_session.add(
            PlaybookPageVersionDB(node_id=page.id, content="Hi", version=1),
        )
        await db_session.flush()

        files = await svc._generate_site(db_session)
        manifest = json.loads(files["manifest.json"])
        assert "test.html" in manifest["files"]
        assert manifest["page_count"] >= 1


class TestUploadSite:
    @pytest.mark.asyncio
    async def test_uploads_all_files_to_s3(self):
        svc = PublishService()
        files = {
            "index.html": b"<html>test</html>",
            "assets/style.css": b"body {}",
        }
        with patch(
            "app.modules.playbook.services.publish_service.get_s3_client",
        ) as mock_fn:
            mock_s3 = MagicMock()
            mock_fn.return_value = mock_s3
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
        with patch(
            "app.modules.playbook.services.publish_service.get_s3_client",
        ) as mock_fn:
            mock_s3 = MagicMock()
            mock_fn.return_value = mock_s3
            await svc._upload_site(files)
            calls_by_key = {}
            for call in mock_s3.put_object.call_args_list:
                key = call.kwargs.get("Key", call[1].get("Key", ""))
                ct = call.kwargs.get("ContentType", call[1].get("ContentType", ""))
                filename = key.split("/")[-1]
                calls_by_key[filename] = ct
            assert calls_by_key["page.html"] == "text/html; charset=utf-8"
            assert calls_by_key["style.css"] == "text/css"
            assert calls_by_key["navigation.js"] == "application/javascript"
            assert calls_by_key["manifest.json"] == "application/json"


class TestCleanupOrphans:
    @pytest.mark.asyncio
    async def test_first_publish_skips_cleanup(self):
        svc = PublishService()
        with patch(
            "app.modules.playbook.services.publish_service.get_s3_client",
        ) as mock_fn:
            mock_s3 = MagicMock()
            mock_fn.return_value = mock_s3
            error = type(mock_s3).exceptions = MagicMock()
            no_such_key = type("NoSuchKey", (Exception,), {})
            error.NoSuchKey = no_such_key
            mock_s3.get_object.side_effect = no_such_key()

            count = await svc._cleanup_orphans({"file.html"})
            assert count == 0
            mock_s3.delete_object.assert_not_called()

    @pytest.mark.asyncio
    async def test_deletes_orphan_files(self):
        svc = PublishService()
        old_manifest = json.dumps(
            {"files": ["old-page.html", "still-here.html"]},
        ).encode()
        with patch(
            "app.modules.playbook.services.publish_service.get_s3_client",
        ) as mock_fn:
            mock_s3 = MagicMock()
            mock_fn.return_value = mock_s3
            body_mock = MagicMock()
            body_mock.read.return_value = old_manifest
            mock_s3.get_object.return_value = {"Body": body_mock}

            count = await svc._cleanup_orphans({"still-here.html"})
            assert count == 1
            mock_s3.delete_object.assert_called_once()
