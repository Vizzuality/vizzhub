"""Tests for require_permission FastAPI dependency."""

import pytest
from fastapi import HTTPException

from app.core.auth import TokenData
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission


def test_admin_wildcard_passes_any_permission():
    user = TokenData(user_id="1", permissions=["*"])
    checker = require_permission(Action.ADMIN_JOBS)
    result = checker(user)
    assert result.user_id == "1"


def test_user_with_permission_passes():
    user = TokenData(user_id="1", permissions=["scorecard:view", "tracker:view"])
    checker = require_permission(Action.SCORECARD_VIEW)
    result = checker(user)
    assert result.user_id == "1"


def test_user_without_permission_raises_403():
    user = TokenData(user_id="1", permissions=["scorecard:view"])
    checker = require_permission(Action.TRACKER_MANAGE)
    with pytest.raises(HTTPException) as exc_info:
        checker(user)
    assert exc_info.value.status_code == 403


def test_multiple_permissions_all_required():
    user = TokenData(user_id="1", permissions=["scorecard:view"])
    checker = require_permission(Action.SCORECARD_VIEW, Action.TRACKER_VIEW)
    with pytest.raises(HTTPException) as exc_info:
        checker(user)
    assert exc_info.value.status_code == 403


def test_multiple_permissions_all_present_passes():
    user = TokenData(
        user_id="1",
        permissions=["scorecard:view", "tracker:view", "projects:view"],
    )
    checker = require_permission(Action.SCORECARD_VIEW, Action.TRACKER_VIEW)
    result = checker(user)
    assert result.user_id == "1"
