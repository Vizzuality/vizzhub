"""Tests for cost/days calculation service."""

from decimal import Decimal

from app.modules.tracker.services.cost_service import calculate_cost_and_days


class TestCalculateCostAndDays:
    def test_standard_calculation(self):
        """Band B, 20% time, dedication 0.74, contract=base=175."""
        cost, days = calculate_cost_and_days(
            percentage=Decimal("0.20"),
            rate_value=Decimal("15365"),
            dedication=Decimal("0.74"),
            contract_rate=Decimal("175"),
            base_rate=Decimal("175"),
        )
        expected_cost = Decimal("0.20") * Decimal("15365") * Decimal("0.74") * Decimal("1")
        expected_days = Decimal("0.20") * Decimal("20") * Decimal("0.74")
        assert cost == expected_cost
        assert days == expected_days

    def test_different_contract_rate(self):
        """Contract rate 210 with base 175 → multiplier 1.2."""
        cost, days = calculate_cost_and_days(
            percentage=Decimal("0.20"),
            rate_value=Decimal("15365"),
            dedication=Decimal("0.74"),
            contract_rate=Decimal("210"),
            base_rate=Decimal("175"),
        )
        multiplier = Decimal("210") / Decimal("175")
        expected_cost = Decimal("0.20") * Decimal("15365") * Decimal("0.74") * multiplier
        assert cost == expected_cost

    def test_zero_percentage(self):
        cost, days = calculate_cost_and_days(
            percentage=Decimal("0"),
            rate_value=Decimal("15365"),
            dedication=Decimal("0.74"),
            contract_rate=Decimal("175"),
            base_rate=Decimal("175"),
        )
        assert cost == Decimal("0")
        assert days == Decimal("0")

    def test_full_time_full_dedication(self):
        """100% time, dedication 1.0 → 20 working days/month."""
        cost, days = calculate_cost_and_days(
            percentage=Decimal("1.0"),
            rate_value=Decimal("15365"),
            dedication=Decimal("1.0"),
            contract_rate=Decimal("175"),
            base_rate=Decimal("175"),
        )
        assert cost == Decimal("15365")
        assert days == Decimal("20")

    def test_all_rate_bands(self):
        """Verify different rate bands produce proportional costs."""
        bands = {
            "A": Decimal("11853"),
            "B": Decimal("15365"),
            "C": Decimal("21072"),
            "D": Decimal("24876.67"),
        }
        results = {}
        for band, value in bands.items():
            cost, _ = calculate_cost_and_days(
                percentage=Decimal("0.20"),
                rate_value=value,
                dedication=Decimal("0.74"),
                contract_rate=Decimal("175"),
                base_rate=Decimal("175"),
            )
            results[band] = cost

        assert results["A"] < results["B"] < results["C"] < results["D"]

    def test_low_contract_rate(self):
        """Contract rate below base → multiplier < 1.0."""
        cost, _ = calculate_cost_and_days(
            percentage=Decimal("0.20"),
            rate_value=Decimal("15365"),
            dedication=Decimal("0.74"),
            contract_rate=Decimal("152"),
            base_rate=Decimal("175"),
        )
        standard_cost, _ = calculate_cost_and_days(
            percentage=Decimal("0.20"),
            rate_value=Decimal("15365"),
            dedication=Decimal("0.74"),
            contract_rate=Decimal("175"),
            base_rate=Decimal("175"),
        )
        assert cost < standard_cost

    def test_changed_base_rate(self):
        """Company raises base rate to 190 → same contract_rate yields lower multiplier."""
        cost_old_base, _ = calculate_cost_and_days(
            percentage=Decimal("0.20"),
            rate_value=Decimal("15365"),
            dedication=Decimal("0.74"),
            contract_rate=Decimal("175"),
            base_rate=Decimal("175"),
        )
        cost_new_base, _ = calculate_cost_and_days(
            percentage=Decimal("0.20"),
            rate_value=Decimal("15365"),
            dedication=Decimal("0.74"),
            contract_rate=Decimal("175"),
            base_rate=Decimal("190"),
        )
        assert cost_new_base < cost_old_base
