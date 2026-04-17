"""Tests for npm version service."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.modules.devstack.services.npm_version import fetch_npm_latest_version


class TestFetchNpmLatestVersion:
    @pytest.mark.asyncio
    async def test_returns_version_on_success(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"version": "18.3.1"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("app.modules.devstack.services.npm_version.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await fetch_npm_latest_version("react")

        assert result == "18.3.1"

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self) -> None:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPError("Not found")

        with patch("app.modules.devstack.services.npm_version.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await fetch_npm_latest_version("does-not-exist")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_version_missing(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("app.modules.devstack.services.npm_version.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await fetch_npm_latest_version("some-package")

        assert result is None
