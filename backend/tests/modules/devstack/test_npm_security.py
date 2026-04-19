"""Tests for npm_security service."""

import pytest
import httpx

from app.modules.devstack.services.npm_security import fetch_npm_advisories


class MockResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("e", request=None, response=None)

    def json(self):
        return self._data


@pytest.mark.asyncio
async def test_fetch_advisories_empty(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return MockResponse(200, [])

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await fetch_npm_advisories("lodash", "4.17.0", token="t")

    assert result == {
        "critical": 0,
        "high": 0,
        "moderate": 0,
        "low": 0,
        "advisories": [],
    }


@pytest.mark.asyncio
async def test_fetch_advisories_counts_by_severity(monkeypatch):
    payload = [
        {"ghsa_id": "GHSA-1", "severity": "critical", "summary": "s1", "html_url": "u1"},
        {"ghsa_id": "GHSA-2", "severity": "high", "summary": "s2", "html_url": "u2"},
        {"ghsa_id": "GHSA-3", "severity": "high", "summary": "s3", "html_url": "u3"},
        {"ghsa_id": "GHSA-4", "severity": "moderate", "summary": "s4", "html_url": "u4"},
    ]

    async def fake_get(self, url, **kwargs):
        return MockResponse(200, payload)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await fetch_npm_advisories("lodash", "4.17.0", token="t")

    assert result["critical"] == 1
    assert result["high"] == 2
    assert result["moderate"] == 1
    assert result["low"] == 0
    assert len(result["advisories"]) == 4
    assert result["advisories"][0] == {
        "id": "GHSA-1",
        "severity": "critical",
        "title": "s1",
        "url": "u1",
    }


@pytest.mark.asyncio
async def test_fetch_advisories_unknown_severity_ignored(monkeypatch):
    payload = [
        {"ghsa_id": "GHSA-X", "severity": "unknown", "summary": "s", "html_url": "u"},
    ]

    async def fake_get(self, url, **kwargs):
        return MockResponse(200, payload)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await fetch_npm_advisories("x", "1.0.0", token="t")

    assert result["critical"] == 0
    assert result["high"] == 0
    assert result["moderate"] == 0
    assert result["low"] == 0
    assert result["advisories"] == [
        {"id": "GHSA-X", "severity": "unknown", "title": "s", "url": "u"}
    ]


@pytest.mark.asyncio
async def test_fetch_advisories_http_error_returns_none(monkeypatch):
    async def fake_get(self, url, **kwargs):
        raise httpx.HTTPError("boom")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    result = await fetch_npm_advisories("lodash", "4.17.0", token="t")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_advisories_sends_auth_header(monkeypatch):
    captured = {}

    async def fake_get(self, url, **kwargs):
        captured["headers"] = kwargs.get("headers", {})
        captured["params"] = kwargs.get("params", {})
        return MockResponse(200, [])

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    await fetch_npm_advisories("lodash", "4.17.0", token="ghp_test123")

    assert captured["headers"]["Authorization"] == "token ghp_test123"
    assert captured["params"]["ecosystem"] == "npm"
    assert captured["params"]["affects"] == "lodash@4.17.0"
