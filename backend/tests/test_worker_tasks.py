"""Tests for ARQ worker tasks."""

from app.worker.tasks import generate_month_range


def test_generate_month_range_returns_expected_months() -> None:
    """Test that generate_month_range produces correct list of (year, month) tuples."""
    result = generate_month_range(2024, 10, 2025, 2)

    expected = [
        (2024, 10),
        (2024, 11),
        (2024, 12),
        (2025, 1),
        (2025, 2),
    ]

    assert result == expected
