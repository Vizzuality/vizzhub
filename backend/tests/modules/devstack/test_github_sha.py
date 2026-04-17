"""Tests for GitHub SHA resolution service."""

import pytest

from app.modules.devstack.services.github_sha import (
    fetch_github_content,
    fetch_github_sha,
    parse_github_url,
)


class TestParseGithubUrl:
    def test_blob_url(self) -> None:
        result = parse_github_url(
            "https://github.com/Vizzuality/devstack/blob/main/skills/finalize.md"
        )
        assert result == ("Vizzuality", "devstack", "main", "skills/finalize.md")

    def test_raw_url(self) -> None:
        result = parse_github_url(
            "https://raw.githubusercontent.com/Vizzuality/devstack/main/org-claude.md"
        )
        assert result == ("Vizzuality", "devstack", "main", "org-claude.md")

    def test_nested_path(self) -> None:
        result = parse_github_url(
            "https://github.com/Vizzuality/devstack/blob/main/deep/nested/file.md"
        )
        assert result == ("Vizzuality", "devstack", "main", "deep/nested/file.md")

    def test_commit_sha_as_ref(self) -> None:
        result = parse_github_url(
            "https://github.com/Vizzuality/devstack/blob/abc123def/file.md"
        )
        assert result == ("Vizzuality", "devstack", "abc123def", "file.md")

    def test_non_github_url_returns_none(self) -> None:
        assert parse_github_url("https://example.com/file.md") is None

    def test_repo_root_url_returns_none(self) -> None:
        assert parse_github_url("https://github.com/Vizzuality/devstack") is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_github_url("") is None


class TestFetchGithubSha:
    @pytest.mark.asyncio
    async def test_returns_none_for_unparseable_url(self) -> None:
        result = await fetch_github_sha("https://example.com/not-github")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_url(self) -> None:
        result = await fetch_github_sha("")
        assert result is None


class TestFetchGithubContent:
    @pytest.mark.asyncio
    async def test_returns_none_for_unparseable_url(self) -> None:
        result = await fetch_github_content("https://example.com/not-github")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_url(self) -> None:
        result = await fetch_github_content("")
        assert result is None
