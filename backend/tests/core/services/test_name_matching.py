from app.core.services.name_matching import normalize, rank, similarity


def test_normalize_strips_parens_years_and_program_suffix() -> None:
    assert normalize("Global Forest Watch (GFW)") == "global forest watch"
    assert normalize("Marxan 2023") == "marxan"
    assert normalize("Aqueduct program") == "aqueduct"


def test_identical_after_normalize_scores_one() -> None:
    assert similarity("Global Forest Watch (GFW)", "Global Forest Watch") == 1.0


def test_partial_overlap_between_thresholds() -> None:
    score = similarity("Aqueduct maintenance", "Aqueduct")
    assert 0.35 < score < 0.85


def test_unrelated_below_threshold() -> None:
    assert similarity("4Growth", "Aqueduct") < 0.35


def test_rank_orders_and_filters() -> None:
    cands = [("Aqueduct", "A"), ("Aqueduct maintenance", "B"), ("Zebra", "Z")]
    result = rank("Aqueduct", cands, limit=5, threshold=0.35)
    assert result[0].payload == "A"
    assert result[0].score == 1.0
    assert all(s.score >= 0.35 for s in result)
    assert "Z" not in [s.payload for s in result]
