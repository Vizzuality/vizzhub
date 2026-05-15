"""Tests for `core/services/doc_asset_service`.

Validates:
- `sanitize_filename` strips/normalises hostile inputs
- `upload_image` builds the S3 key correctly and uses the provided url-builder
"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.services.doc_asset_service import (
    ALLOWED_CONTENT_TYPES,
    MAX_FILE_SIZE,
    sanitize_filename,
    upload_image,
)


class TestSanitizeFilename:
    def test_lowercases(self) -> None:
        assert sanitize_filename("Photo.PNG") == "photo.png"

    def test_replaces_spaces_and_special_chars_with_hyphen(self) -> None:
        assert sanitize_filename("my image (1).png") == "my-image-1-.png"

    def test_collapses_consecutive_hyphens(self) -> None:
        assert sanitize_filename("a---b.png") == "a-b.png"

    def test_strips_leading_trailing_hyphens(self) -> None:
        assert sanitize_filename("--name--.png") == "name-.png"

    def test_handles_empty_input(self) -> None:
        assert sanitize_filename("") == "image"

    def test_handles_only_special_chars(self) -> None:
        # All chars get replaced with hyphens, then stripped → "image"
        assert sanitize_filename("///***///") == "image"

    def test_preserves_dots_and_underscores(self) -> None:
        assert sanitize_filename("snapshot_2026-05.png") == "snapshot_2026-05.png"


class TestUploadImage:
    @patch("app.core.services.doc_asset_service.get_s3_client")
    @patch("app.core.services.doc_asset_service.get_settings")
    def test_uploads_with_correct_key_and_returns_url(
        self, mock_settings: MagicMock, mock_get_s3: MagicMock,
    ) -> None:
        mock_settings.return_value.assets_bucket_name = "test-bucket"
        fake_s3 = MagicMock()
        mock_get_s3.return_value = fake_s3

        captured_key: dict[str, str] = {}

        def build_url(key: str) -> str:
            captured_key["key"] = key
            return f"https://cdn.example.com/{key}"

        url = upload_image(
            file_bytes=b"FAKE_BYTES",
            filename="My Photo.png",
            content_type="image/png",
            s3_prefix="playbook/images/",
            build_url=build_url,
        )

        # Key has the prefix and ends with .png, with a unique 8-hex segment
        # inserted between stem and extension.
        assert captured_key["key"].startswith("playbook/images/my-photo-")
        assert captured_key["key"].endswith(".png")
        assert url == f"https://cdn.example.com/{captured_key['key']}"

        # S3 put_object called with the right kwargs
        fake_s3.put_object.assert_called_once()
        call_kwargs = fake_s3.put_object.call_args.kwargs
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Body"] == b"FAKE_BYTES"
        assert call_kwargs["ContentType"] == "image/png"

    @patch("app.core.services.doc_asset_service.get_s3_client")
    @patch("app.core.services.doc_asset_service.get_settings")
    def test_uploads_svg_with_correct_extension(
        self, mock_settings: MagicMock, mock_get_s3: MagicMock,
    ) -> None:
        """svg+xml MIME normalises to .svg extension when filename has no ext."""
        mock_settings.return_value.assets_bucket_name = "test-bucket"
        captured: dict[str, str] = {}

        def build_url(key: str) -> str:
            captured["key"] = key
            return key

        upload_image(
            file_bytes=b"<svg/>",
            filename="diagram",  # no extension on input
            content_type="image/svg+xml",
            s3_prefix="iso/images/",
            build_url=build_url,
        )

        assert captured["key"].startswith("iso/images/diagram-")
        assert captured["key"].endswith(".svg")


def test_allowed_content_types_includes_only_safe_image_mimes() -> None:
    """Whitelist must include exactly the 5 image MIMEs we support — guard against drift."""
    assert ALLOWED_CONTENT_TYPES == {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/svg+xml",
    }


def test_max_file_size_is_5mb() -> None:
    """5 MB ceiling — guard against accidental loosening."""
    assert MAX_FILE_SIZE == 5 * 1024 * 1024
