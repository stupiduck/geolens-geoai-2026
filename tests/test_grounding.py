import pytest
from geolens.model import validate_claims
from geolens.sources import candidate_matches


def test_false_comparison_cannot_be_rendered():
    options = {"a": {"score": 50, "conditions": {"temperature": 32}}, "b": {"score": 60, "conditions": {"temperature": 27}}}
    with pytest.raises(ValueError):
        validate_claims([{"predicate": "cooler_than", "subject": "a", "object": "b"}], options)


def test_unknown_model_entity_cannot_enter_answer():
    with pytest.raises(ValueError):
        validate_claims([{"predicate": "higher_score", "subject": "invented", "object": "b"}], {})


def test_tennis_selector_requires_tennis_evidence():
    assert candidate_matches({"sport": "tennis", "leisure": "pitch"}, "tennis")
    assert not candidate_matches({"leisure": "park"}, "tennis")
