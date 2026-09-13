# backend/tests/test_batch_policy.py
"""Unit tests for the deterministic batch grading policy.

No network, no AI calls: the policy maps validated assessment signals to
exactly one of A/B/C/Reject using configured (provisional) rules.
"""
import pytest

from backend.app.schemas.batch import BatchGradeEnum, BatchVisualAssessment
from backend.app.services import batch_policy as policy_mod
from backend.app.services.batch_policy import BatchGradingPolicy


def _assessment(**overrides):
    base = {
        "batch_assessment": "Uniform batch.",
        "observations": ["Uniform bulbs"],
        "visible_quality_issues": [],
        "assessment_confidence": 0.9,
        "suggested_grade": BatchGradeEnum.B,
        "review_required": False,
        "images_analyzed": 3,
    }
    base.update(overrides)
    return BatchVisualAssessment(**base)


def _assessment(**overrides):
    base = {
        "batch_assessment": "Uniform batch.",
        "observations": ["Uniform bulbs"],
        "visible_quality_issues": [],
        "assessment_confidence": 0.9,
        "suggested_grade": BatchGradeEnum.B,
        "review_required": False,
        "images_analyzed": 3,
        # URS evidence: 3/150 = 2.0% -> band A unless overridden.
        "urs_onions": 3,
        "assessed_onions": 150,
    }
    base.update(overrides)
    return BatchVisualAssessment(**base)


def test_urs_band_boundaries_exact():
    # v0.2-provisional bands: A<=5, B<=10, C<=20, else Reject.
    cases = [
        (0.0, BatchGradeEnum.A),
        (5.0, BatchGradeEnum.A),
        (5.0001, BatchGradeEnum.B),
        (10.0, BatchGradeEnum.B),
        (10.0001, BatchGradeEnum.C),
        (20.0, BatchGradeEnum.C),
        (20.0001, BatchGradeEnum.REJECT),
        (100.0, BatchGradeEnum.REJECT),
    ]
    for urs_percent, expected in cases:
        # Drive the exact percentage via matching counts.
        urs, assessed = {
            0.0: (0, 100), 5.0: (5, 100), 5.0001: (50001, 1000000),
            10.0: (10, 100), 10.0001: (100001, 1000000),
            20.0: (20, 100), 20.0001: (200001, 1000000),
            100.0: (100, 100),
        }[urs_percent]
        decision = BatchGradingPolicy.grade_batch(
            assessment=_assessment(
                urs_onions=urs, assessed_onions=assessed,
                suggested_grade=None,  # isolate the URS driver
            ),
            total_detections=150, has_high_severity_issue=False,
        )
        assert decision.final_grade == expected, f"URS%={urs_percent}"
        assert isinstance(decision.final_grade, BatchGradeEnum)


def test_zero_urs_grades_a():
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(urs_onions=0, assessed_onions=200,
                               suggested_grade=BatchGradeEnum.A),
        total_detections=200, has_high_severity_issue=False,
    )
    assert decision.final_grade == BatchGradeEnum.A
    assert decision.review_required is False


def test_full_urs_grades_reject():
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(urs_onions=200, assessed_onions=200,
                               suggested_grade=BatchGradeEnum.REJECT),
        total_detections=200, has_high_severity_issue=False,
    )
    assert decision.final_grade == BatchGradeEnum.REJECT


def test_zero_assessed_never_divides_and_fails_safe():
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(urs_onions=0, assessed_onions=0,
                               suggested_grade=BatchGradeEnum.A),
        total_detections=10, has_high_severity_issue=False,
    )
    assert decision.review_required is True
    assert decision.final_grade == BatchGradeEnum.REJECT  # configured fallback


def test_fractional_counts_round_safely():
    # 1/3 = 33.3333% -> Reject; 1/20 = 5.0% exactly -> A (no float artifact).
    reject = BatchGradingPolicy.grade_batch(
        assessment=_assessment(urs_onions=1, assessed_onions=3,
                               suggested_grade=None),
        total_detections=3, has_high_severity_issue=False,
    )
    assert reject.final_grade == BatchGradeEnum.REJECT
    exact = BatchGradingPolicy.grade_batch(
        assessment=_assessment(urs_onions=1, assessed_onions=20,
                               suggested_grade=None),
        total_detections=20, has_high_severity_issue=False,
    )
    assert exact.final_grade == BatchGradeEnum.A


def test_missing_urs_evidence_falls_back_with_review():
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(urs_onions=None, assessed_onions=None,
                               suggested_grade=None),
        total_detections=150, has_high_severity_issue=False,
    )
    assert decision.final_grade == BatchGradeEnum.REJECT  # configured fallback
    assert decision.review_required is True
    assert any("fallback" in r for r in decision.reasons)


def test_partial_urs_evidence_is_unknown_not_zero():
    # Only one of the pair present => cannot compute => unknown, not 0%.
    for kwargs in ({"urs_onions": None}, {"assessed_onions": None}):
        base = {"urs_onions": 5, "assessed_onions": 100}
        base.update(kwargs)
        decision = BatchGradingPolicy.grade_batch(
            assessment=_assessment(suggested_grade=None, **base),
            total_detections=100, has_high_severity_issue=False,
        )
        assert decision.review_required is True
        assert decision.final_grade == BatchGradeEnum.REJECT


def test_suggestion_mismatch_forces_review_but_urs_grade_stands():
    # URS 2% -> A, but AI suggested C: grade stays URS-derived, review forced.
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(suggested_grade=BatchGradeEnum.C),
        total_detections=150, has_high_severity_issue=False,
    )
    assert decision.final_grade == BatchGradeEnum.A
    assert decision.review_required is True
    assert any("differs from URS-derived grade" in r for r in decision.reasons)


def test_matching_suggestion_is_supporting_evidence_only():
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(suggested_grade=BatchGradeEnum.A),
        total_detections=150, has_high_severity_issue=False,
    )
    assert decision.final_grade == BatchGradeEnum.A
    assert decision.review_required is False
    assert any("supporting evidence only" in r for r in decision.reasons)


def test_known_urs_without_suggestion_grades_without_forced_review():
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(suggested_grade=None),
        total_detections=150, has_high_severity_issue=False,
    )
    assert decision.final_grade == BatchGradeEnum.A
    assert decision.review_required is False
    assert any("No AI suggestion provided" in r for r in decision.reasons)


def test_low_confidence_forces_review_but_keeps_urs_grade():
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(assessment_confidence=0.4),
        total_detections=150, has_high_severity_issue=False,
    )
    # URS 2% -> A stands; low confidence only forces review.
    assert decision.final_grade == BatchGradeEnum.A
    assert decision.review_required is True
    assert any("below policy minimum" in r for r in decision.reasons)


def test_missing_suggestion_uses_configured_fallback_and_review(monkeypatch):
    monkeypatch.setattr(policy_mod.settings, "BATCH_FALLBACK_GRADE", "Reject")
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(suggested_grade=None,
                               urs_onions=None, assessed_onions=None),
        total_detections=150, has_high_severity_issue=False,
    )
    assert decision.final_grade == BatchGradeEnum.REJECT
    assert decision.review_required is True
    assert any("fallback" in r for r in decision.reasons)


def test_high_severity_caps_grade_and_forces_review(monkeypatch):
    monkeypatch.setattr(
        policy_mod.settings, "BATCH_MAX_GRADE_WITH_HIGH_SEVERITY", "C"
    )
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(suggested_grade=BatchGradeEnum.A),
        total_detections=150, has_high_severity_issue=True,
    )
    assert decision.final_grade == BatchGradeEnum.C
    assert decision.review_required is True


def test_high_severity_caps_urs_grade_regardless_of_suggestion(monkeypatch):
    # URS 2% -> A, but a high-severity issue caps at C. The Reject
    # suggestion is supporting evidence only: it cannot set the grade,
    # and the cap applies to the URS-derived grade either way.
    monkeypatch.setattr(
        policy_mod.settings, "BATCH_MAX_GRADE_WITH_HIGH_SEVERITY", "C"
    )
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(suggested_grade=BatchGradeEnum.REJECT),
        total_detections=150, has_high_severity_issue=True,
    )
    assert decision.final_grade == BatchGradeEnum.C
    assert decision.review_required is True


def test_zero_detections_forces_review():
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(), total_detections=0,
        has_high_severity_issue=False,
    )
    assert decision.review_required is True
    assert any("No onions detected" in r for r in decision.reasons)


def test_provider_review_flag_propagates():
    decision = BatchGradingPolicy.grade_batch(
        assessment=_assessment(review_required=True,
                               suggested_grade=BatchGradeEnum.A),
        total_detections=150, has_high_severity_issue=False,
    )
    assert decision.final_grade == BatchGradeEnum.A
    assert decision.review_required is True


def test_invalid_policy_configuration_refuses_to_grade(monkeypatch):
    monkeypatch.setattr(policy_mod.settings, "BATCH_FALLBACK_GRADE", "Z")
    with pytest.raises(ValueError):
        BatchGradingPolicy.grade_batch(
            assessment=_assessment(suggested_grade=None),
            total_detections=10, has_high_severity_issue=False,
        )


def test_final_grade_restricted_to_enum():
    for grade in (
        BatchGradeEnum.A, BatchGradeEnum.B, BatchGradeEnum.C, BatchGradeEnum.REJECT,
    ):
        decision = BatchGradingPolicy.grade_batch(
            assessment=_assessment(suggested_grade=grade),
            total_detections=50, has_high_severity_issue=False,
        )
        assert isinstance(decision.final_grade, BatchGradeEnum)
