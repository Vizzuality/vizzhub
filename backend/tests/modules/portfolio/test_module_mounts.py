"""Verify that the portfolio module scaffold is wired into the app."""

from pathlib import Path


def test_portfolio_module_imports() -> None:
    """The portfolio module must be importable without errors."""
    from app.modules.portfolio import public  # noqa: F401
    from app.modules.portfolio.router import router  # noqa: F401


def test_portfolio_router_wired_in_main() -> None:
    """main.py must import and include the portfolio router at /api/portfolio."""
    main_src = (Path(__file__).parents[3] / "app" / "main.py").read_text()
    assert "from app.modules.portfolio.router import router as portfolio_router" in main_src, (
        "portfolio_router import not found in main.py"
    )
    assert 'include_router(portfolio_router, prefix="/api/portfolio"' in main_src, (
        "include_router(portfolio_router, ...) not found in main.py"
    )


def test_app_boots_without_portfolio_errors() -> None:
    """The FastAPI app must initialise (import app.main) without raising errors."""
    from app.main import app  # noqa: F401

    assert app is not None


def test_taxonomies_route_registered() -> None:
    """GET /api/taxonomies must be registered (non-404 even without auth)."""
    import httpx
    from httpx import ASGITransport

    from app.main import app

    async def _check() -> int:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/taxonomies")
            return resp.status_code

    import asyncio

    status = asyncio.run(_check())
    assert status in (200, 401, 403), f"Expected non-404, got {status}"
