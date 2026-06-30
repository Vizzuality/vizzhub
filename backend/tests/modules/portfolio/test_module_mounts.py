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
    """GET /api/taxonomies must be registered as a route on the app."""
    from app.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/taxonomies" in paths, (
        f"/api/taxonomies not found in routes: {sorted(p for p in paths if p)}"
    )
