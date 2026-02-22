"""Tests for ISO module foundation."""

import pytest
import pytest_asyncio
from datetime import datetime, date, timezone
from uuid import uuid4


class TestIsoRouterMount:
    def test_iso_router_imported(self) -> None:
        from app.modules.iso.router import router
        assert router is not None
