"""Tests for export metric definitions."""

from app.modules.scorecard.services.export_definitions import (
    DIMENSION_DEFINITIONS,
    INDICATOR_DEFINITIONS,
    get_metric_rows,
)


class TestExportDefinitions:
    def test_all_eight_dimensions_defined(self):
        dims = [d["key"] for d in DIMENSION_DEFINITIONS]
        expected = [
            "p_time",
            "p_cost",
            "p_quality",
            "p_value",
            "p_satisfaction",
            "p_flow",
            "p_engineering",
            "p_risk",
        ]
        assert dims == expected

    def test_dimension_has_required_fields(self):
        for dim in DIMENSION_DEFINITIONS:
            assert "key" in dim
            assert "name" in dim
            assert "description" in dim
            assert "formula" in dim
            assert "indicators" in dim

    def test_indicator_has_required_fields(self):
        for key, ind in INDICATOR_DEFINITIONS.items():
            assert "name" in ind, f"Missing name for {key}"
            assert "description" in ind, f"Missing description for {key}"
            assert "formula" in ind, f"Missing formula for {key}"

    def test_get_metric_rows_returns_hierarchical_list(self):
        rows = get_metric_rows()
        assert len(rows) > 0
        assert rows[0]["level"] == 0
        assert rows[0]["key"] == "final_score"
        dim_rows = [r for r in rows if r["level"] == 1]
        assert len(dim_rows) == 8
        ind_rows = [r for r in rows if r["level"] == 2]
        assert len(ind_rows) > 0

    def test_each_dimension_has_at_least_one_indicator(self):
        rows = get_metric_rows()
        current_dim = None
        dim_has_indicators = {}
        for row in rows:
            if row["level"] == 1:
                current_dim = row["key"]
                dim_has_indicators[current_dim] = False
            elif row["level"] == 2 and current_dim:
                dim_has_indicators[current_dim] = True
        for dim, has in dim_has_indicators.items():
            assert has, f"Dimension {dim} has no indicators"
