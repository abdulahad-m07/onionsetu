# backend/app/schemas/batch.py
import enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class BatchGradeEnum(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    REJECT = "Reject"


class IssueSeverityEnum(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VisibleQualityIssue(BaseModel):
    issue: str
    severity: IssueSeverityEnum = IssueSeverityEnum.MEDIUM
    evidence_ref: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _accept_description_alias(cls, data):
        """Accept the provider's `description` key as the issue text.

        Observed live (Qwen2.5-VL 72B): issue objects arrive as
        {"severity": ..., "description": ..., "evidence_ref": ...} with no
        `issue` key. Mapping exactly this one documented alias preserves the
        model's text verbatim under our stable contract field. An explicit
        `issue` always wins; if neither key holds usable text, strict
        validation still fails loudly.
        """
        if isinstance(data, dict) and "issue" not in data:
            alias = data.get("description")
            if isinstance(alias, str) and alias.strip():
                data = {**data, "issue": alias}
        return data


class BatchVisualAssessment(BaseModel):
    """Validated provider batch-level assessment (currently Qwen2.5-VL 72B
    via OpenRouter; previously Gemini — provider-neutral contract).

    `suggested_grade` is an AI SUGGESTION only — the deterministic
    OnionSetu batch policy owns the actual final grade and must re-validate
    it. Unknown extra fields from the model are ignored, never trusted.
    """

    batch_assessment: str = Field(..., min_length=1)
    observations: List[str] = []
    visible_quality_issues: List[VisibleQualityIssue] = []
    uncertainty_notes: Optional[str] = None
    assessment_confidence: float = Field(..., ge=0.0, le=1.0)
    suggested_grade: Optional[BatchGradeEnum] = None
    review_required: bool = False
    images_analyzed: int = Field(default=0, ge=0)
    # Estimated URS evidence (optional). When the assessment provider can
    # estimate how many of the assessed onions show under-grade signs, it
    # reports BOTH counts; the policy derives URS% = urs/assessed * 100.
    # Both absent (or unusable) => URS% unknown => human review + fallback.
    # Absence is never treated as zero: missing evidence is not evidence.
    urs_onions: Optional[int] = Field(default=None, ge=0)
    assessed_onions: Optional[int] = Field(default=None, ge=0)

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _check_urs_counts_consistent(self):
        """Reject internally inconsistent URS evidence as malformed.

        urs_onions > assessed_onions is impossible: the counts cannot ground
        a URS% computation, so the whole assessment is unusable (same
        strictness as an out-of-range confidence). Negative values are
        already rejected by field constraints.
        """
        if (
            self.urs_onions is not None
            and self.assessed_onions is not None
            and self.urs_onions > self.assessed_onions
        ):
            raise ValueError(
                "urs_onions exceeds assessed_onions: inconsistent URS evidence."
            )
        return self

    @field_validator("observations", mode="before")
    @classmethod
    def _coerce_observations_text(cls, value):
        """Accept a plain-text `observations` string losslessly.

        Vision models sometimes return a text field as a single string
        instead of an array of strings. Wrapping the verbatim text as one
        observation preserves the content exactly — no splitting (which
        would fragment sentences) and no invention. Any other type still
        goes through strict list validation and fails loudly.
        """
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        return value


class RoboflowImageEvidence(BaseModel):
    image_index: int
    detection_count: int
    mean_confidence: Optional[float] = None
    observed_classes: List[str] = []
    image_width: int = 0
    image_height: int = 0
    error: Optional[str] = None


class BatchAssessResponse(BaseModel):
    """ONE final batch result. `final_grade` is the ONLY grade output —
    never per-onion grades, never A/B/C percentages."""

    final_grade: BatchGradeEnum
    assessment_confidence: float = Field(..., ge=0.0, le=1.0)
    sample_size: int = Field(..., ge=0)
    sample_size_estimated: bool = True
    images_analyzed: int = Field(..., ge=0)
    # URS% that drove the policy decision (None when URS evidence was
    # unusable/unknown and the fallback grade applied). The denominator is
    # ALWAYS the grader-declared batch size, never summed detections.
    urs_percent: Optional[float] = None
    # Grader-declared physical batch size (100-200), echoed EXACTLY as
    # received. Displayed on the batch card as the assessed batch.
    assessed_onions_declared: Optional[int] = None
    evidence: List[RoboflowImageEvidence] = []
    observations: List[str] = []
    visible_quality_issues: List[VisibleQualityIssue] = []
    review_required: bool = False
    review_reasons: List[str] = []
    policy_version: str
    roboflow_model: str
    assessment_model: str
    batch_id: str
    calculated_at: datetime


class BatchAssessmentSchema(BaseModel):
    """Persisted / synced batch assessment (subset of the response)."""

    id: str
    scan_id: Optional[str] = None
    status: str = "completed"
    final_grade: BatchGradeEnum
    assessment_confidence: float
    sample_size: int
    sample_size_estimated: bool = True
    images_analyzed: int
    urs_percent: Optional[float] = None
    assessed_onions_declared: Optional[int] = None
    review_required: bool = False
    policy_version: str
    roboflow_model: str
    assessment_model: str
    observations_json: Optional[str] = None
    issues_json: Optional[str] = None
    evidence_json: Optional[str] = None
    calculated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
