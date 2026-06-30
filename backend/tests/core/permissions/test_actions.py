"""Tests for permission action constants."""

from app.core.permissions.actions import Action


def test_action_strings_follow_module_action_format():
    for attr in dir(Action):
        if attr.startswith("_") or attr == "ALL":
            continue
        value = getattr(Action, attr)
        assert ":" in value, f"Action.{attr} = '{value}' missing ':' separator"


def test_no_duplicate_action_values():
    values = [getattr(Action, attr) for attr in dir(Action) if not attr.startswith("_")]
    assert len(values) == len(set(values)), "Duplicate action values found"


def test_portfolio_actions_exist():
    assert Action.PORTFOLIO_VIEW == "portfolio:view"
    assert Action.PORTFOLIO_MANAGE == "portfolio:manage"
