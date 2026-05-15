"""Edge-case tests for `_mondays_in_month` used by planner suggestions."""

from datetime import date

from app.modules.capacity.api.planner import _mondays_in_month


def test_february_normal_year() -> None:
    """Feb 2026 starts on Sunday; first Monday is Feb 2."""
    mondays = _mondays_in_month(date(2026, 2, 1))
    assert mondays == [
        date(2026, 2, 2),
        date(2026, 2, 9),
        date(2026, 2, 16),
        date(2026, 2, 23),
    ]


def test_february_leap_year() -> None:
    """Feb 2024 (leap year). Feb 29 is a Thursday; not included."""
    mondays = _mondays_in_month(date(2024, 2, 1))
    assert mondays == [
        date(2024, 2, 5),
        date(2024, 2, 12),
        date(2024, 2, 19),
        date(2024, 2, 26),
    ]


def test_month_starting_on_monday() -> None:
    """March 2027 starts on Monday — first day itself is in the list."""
    mondays = _mondays_in_month(date(2027, 3, 1))
    assert mondays[0] == date(2027, 3, 1)
    assert mondays[-1] == date(2027, 3, 29)
    assert len(mondays) == 5


def test_month_ending_on_sunday() -> None:
    """May 2026 ends on Sunday — last Monday is May 25."""
    mondays = _mondays_in_month(date(2026, 5, 1))
    assert mondays[-1] == date(2026, 5, 25)
    assert date(2026, 5, 31) not in mondays


def test_december_rolls_year() -> None:
    """December must roll into the next year when computing last_day."""
    mondays = _mondays_in_month(date(2026, 12, 15))
    assert all(m.year == 2026 and m.month == 12 for m in mondays)
    assert mondays[0] == date(2026, 12, 7)
    assert mondays[-1] == date(2026, 12, 28)


def test_input_date_not_first_of_month() -> None:
    """Function must normalize to first-of-month regardless of input day."""
    a = _mondays_in_month(date(2026, 5, 1))
    b = _mondays_in_month(date(2026, 5, 17))
    assert a == b


def test_short_month_4_mondays() -> None:
    """Feb 2025 has only 4 Mondays."""
    mondays = _mondays_in_month(date(2025, 2, 1))
    assert len(mondays) == 4


def test_long_month_5_mondays() -> None:
    """March 2027 starts on Monday → 5 Mondays."""
    mondays = _mondays_in_month(date(2027, 3, 1))
    assert len(mondays) == 5
