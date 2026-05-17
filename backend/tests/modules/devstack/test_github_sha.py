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

    def test_raw_url_with_refs_heads(self) -> None:
        result = parse_github_url(
            "https://raw.githubusercontent.com/Vizzuality/claude-code-standards/refs/heads/main/Skills/finalize.md"
        )
        assert result == ("Vizzuality", "claude-code-standards", "main", "Skills/finalize.md")

    def test_raw_url_with_refs_tags(self) -> None:
        result = parse_github_url(
            "https://raw.githubusercontent.com/Vizzuality/devstack/refs/tags/v1.0.0/file.md"
        )
        assert result == ("Vizzuality", "devstack", "v1.0.0", "file.md")

    def test_nested_path(self) -> None:
        result = parse_github_url(
            "https://github.com/Vizzuality/devstack/blob/main/deep/nested/file.md"
        )
        assert result == ("Vizzuality", "devstack", "main", "deep/nested/file.md")

    def test_commit_sha_as_ref(self) -> None:
        result = parse_github_url("https://github.com/Vizzuality/devstack/blob/abc123def/file.md")
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

    @pytest.mark.asyncio
    async def test_returns_none_on_rate_limit(self, respx_mock) -> None:
        """GitHub 429 must surface as None without raising — never block sync."""
        import httpx

        respx_mock.get(
            "https://api.github.com/repos/Vizzuality/devstack/contents/skills/test.md"
        ).mock(
            return_value=httpx.Response(
                429,
                headers={"X-RateLimit-Remaining": "0"},
                json={"message": "API rate limit exceeded"},
            )
        )
        result = await fetch_github_sha(
            "https://github.com/Vizzuality/devstack/blob/main/skills/test.md",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_malformed_json(self, respx_mock) -> None:
        """Body that isn't JSON must not crash the worker."""
        import httpx

        respx_mock.get(
            "https://api.github.com/repos/Vizzuality/devstack/contents/skills/test.md"
        ).mock(return_value=httpx.Response(200, text="<html>not json</html>"))
        result = await fetch_github_sha(
            "https://github.com/Vizzuality/devstack/blob/main/skills/test.md",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_sha_missing(self, respx_mock) -> None:
        """Valid JSON but no 'sha' key → None."""
        import httpx

        respx_mock.get(
            "https://api.github.com/repos/Vizzuality/devstack/contents/skills/test.md"
        ).mock(return_value=httpx.Response(200, json={"name": "test.md"}))
        result = await fetch_github_sha(
            "https://github.com/Vizzuality/devstack/blob/main/skills/test.md",
        )
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

    @pytest.mark.asyncio
    async def test_returns_none_on_malformed_json(self, respx_mock) -> None:
        """Malformed JSON body must not raise."""
        import httpx

        respx_mock.get(
            "https://api.github.com/repos/Vizzuality/devstack/contents/skills/test.md"
        ).mock(return_value=httpx.Response(200, text="not-json"))
        result = await fetch_github_content(
            "https://github.com/Vizzuality/devstack/blob/main/skills/test.md",
        )
        assert result is None
