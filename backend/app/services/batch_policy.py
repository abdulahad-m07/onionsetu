# backend/app/services/batch_policy.py
"""Deterministic OnionSetu batch grading policy: validated AI signals in,
ONE final grade (A/B/C/Reject) out.

"OnionSetu v0.2-provisional" — these thresholds are NOT claimed to be
official AGMARK/APMC grade boundaries. No official A/B/C/Reject thresholds
exist in this repository; every threshold below is an explicitly named
PROVISIONAL constant that must be replaced by officially signed-off values.
The policy invents no measurements — it only applies these configured,
reviewable rules to validated AI outputs.

Grade driver (PRIMARY): URS% = (URS onions / assessed onions) x 100,
computed from the assessment provider's estimated URS evidence:

    URS% <= 5%   -> Grade A
    URS% > 5-10% -> Grade B
    URS% > 10-20% -> Grade C
    URS% > 20%   -> Reject

Separation of responsibilities enforced here:
- Roboflow provides perception (counts/boxes/real confidence).
- The assessment provider (Qwen2.5-VL 72B via OpenRouter) provides
  batch-level visual assessment (observations, issues, URS estimates,
  assessment_confidence, review flag, and at most a SUGGESTION).
- THIS policy owns the final grade. The provider suggestion is supporting
  evidence only: it is recorded, and any mismatch with the URS-derived
  grade forces human review. It can never override the URS-based policy.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from backend.app.config.settings import settings
from backend.app.schemas.batch import BatchGradeEnum, BatchVisualAssessment

# --- OnionSetu v0.2-provisional URS band edges (NOT official thresholds) ---
URS_GRADE_A_MAX = 5.0
URS_GRADE_B_MAX = 10.0
URS_GRADE_C_MAX = 20.0

# Lower index = better grade. Used ONLY for deterministic min/max
# comparisons inside the configured rules — not a measurement.
GRADE_ORDER = {
    BatchGradeEnum.A: 0,
    BatchGradeEnum.B: 1,
    BatchGradeEnum.C: 2,
    BatchGradeEnum.REJECT: 3,
}

# Decimals kept when deriving URS% from integer counts, so binary
# floating-point division artifacts (e.g. x.9999999) cannot flip a band edge
# while exact boundary literals (5.0, 10.0, 20.0) still map exactly.
URS_PERCENT_PRECISION = 4


@dataclass
class BatchGradeDecision:
    final_grade: BatchGradeEnum
    review_required: bool
    reasons: List[str] = field(default_factory=list)


def _as_grade(value: str, setting_name: str) -> BatchGradeEnum:
    try:
        return BatchGradeEnum(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid {setting_name}={value!r}; must be one of "
            f"{sorted(GRADE_ORDER, key=GRADE_ORDER.get)}. "
            "Fix server configuration — refusing to grade."
        ) from exc


def grade_for_urs_percent(urs_percent: float) -> BatchGradeEnum:
    """Map a URS% value to its v0.2-provisional band (pure, total function).

    Boundaries are inclusive on the better side: 5.0 -> A, 10.0 -> B,
    20.0 -> C; anything above a bound falls to the next band.
    """
    if urs_percent <= URS_GRADE_A_MAX:
        return BatchGradeEnum.A
    if urs_percent <= URS_GRADE_B_MAX:
        return BatchGradeEnum.B
    if urs_percent <= URS_GRADE_C_MAX:
        return BatchGradeEnum.C
    return BatchGradeEnum.REJECT


def compute_urs_percent(
    urs_onions: Optional[int], assessed_onions: Optional[int]
) -> Optional[float]:
    """Derive URS% from estimated URS evidence, or None when unknowable.

    Returns None (never raises, never divides by zero) when either count is
    missing or when nothing was assessed — the caller must then force human
    review and fall back safely. Callers must guarantee
    0 <= urs_onions <= assessed_onions (schema-validated upstream).
    """
    if urs_onions is None or assessed_onions is None:
        return None
    if assessed_onions <= 0:
        return None
    return round((urs_onions / assessed_onions) * 100, URS_PERCENT_PRECISION)


class BatchGradingPolicy:
    @staticmethod
    def grade_batch(
        assessment: BatchVisualAssessment,
        total_detections: int,
        has_high_severity_issue: bool,
    ) -> BatchGradeDecision:
        """Apply the versioned provisional policy deterministically."""
        reasons: List[str] = []
        review_required = False

        if assessment.review_required:
            review_required = True
            reasons.append("Assessment provider requested human review.")

        min_conf = settings.BATCH_MIN_ASSESSMENT_CONFIDENCE
        if assessment.assessment_confidence < min_conf:
            review_required = True
            reasons.append(
                f"Assessment confidence {assessment.assessment_confidence:.2f} "
                f"below policy minimum {min_conf:.2f}."
            )

        if total_detections <= 0:
            review_required = True
            reasons.append("No onions detected in the batch images.")

        fallback = _as_grade(settings.BATCH_FALLBACK_GRADE, "BATCH_FALLBACK_GRADE")
        cap = _as_grade(
            settings.BATCH_MAX_GRADE_WITH_HIGH_SEVERITY,
            "BATCH_MAX_GRADE_WITH_HIGH_SEVERITY",
        )

        # PRIMARY driver: URS% band. Unknown URS% (missing/empty evidence)
        # cannot ground a grade -> configured fallback + forced review.
        urs_percent = compute_urs_percent(
            assessment.urs_onions, assessment.assessed_onions
        )
        if urs_percent is None:
            candidate = fallback
            review_required = True
            reasons.append(
                "URS evidence missing or empty (urs_onions/assessed_onions "
                f"unavailable); applied configured fallback grade "
                f"{fallback.value} pending human review."
            )
        else:
            candidate = grade_for_urs_percent(urs_percent)
            reasons.append(
                f"URS {assessment.urs_onions}/{assessment.assessed_onions} = "
                f"{urs_percent}% -> band {candidate.value} "
                f"(v0.2-provisional: A<=5, B<=10, C<=20, else Reject)."
            )

        # Supporting evidence only: a valid suggestion is recorded, and any
        # mismatch with the URS-derived grade forces human review. The
        # suggestion can never override the URS-based policy.
        if assessment.suggested_grade is not None:
            reasons.append(
                f"AI suggestion: {assessment.suggested_grade.value} "
                f"(supporting evidence only)."
            )
            if assessment.suggested_grade != candidate:
                review_required = True
                reasons.append(
                    f"AI suggestion ({assessment.suggested_grade.value}) "
                    f"differs from URS-derived grade ({candidate.value}); "
                    f"human review required."
                )
        else:
            reasons.append("No AI suggestion provided.")

        if has_high_severity_issue and GRADE_ORDER[candidate] < GRADE_ORDER[cap]:
            candidate = cap
            review_required = True
            reasons.append(
                f"High-severity issue present; capped at {cap.value} "
                "pending human review."
            )

        return BatchGradeDecision(
            final_grade=candidate,
            review_required=review_required,
            reasons=reasons,
        )
