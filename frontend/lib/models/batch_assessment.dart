// lib/models/batch_assessment.dart
//
// Client-side model of the backend POST /v1/inference/batch-assess response:
// exactly ONE final batch grade (A/B/C/Reject) for the whole sampled lot.
// Strict parsing: anything outside the contract throws FormatException
// instead of producing an invented grade.

enum BatchGrade { a, b, c, reject }

extension BatchGradeExtension on BatchGrade {
  /// Wire value used by the backend (A/B/C/Reject — the only legal values).
  String get value {
    switch (this) {
      case BatchGrade.a:
        return 'A';
      case BatchGrade.b:
        return 'B';
      case BatchGrade.c:
        return 'C';
      case BatchGrade.reject:
        return 'Reject';
    }
  }

  String get displayName {
    switch (this) {
      case BatchGrade.a:
        return 'Grade A';
      case BatchGrade.b:
        return 'Grade B';
      case BatchGrade.c:
        return 'Grade C';
      case BatchGrade.reject:
        return 'Reject';
    }
  }

  /// Returns null for anything outside A/B/C/Reject — callers must treat
  /// null as "no valid grade", never coerce it into one.
  static BatchGrade? fromValue(String? value) {
    switch (value) {
      case 'A':
        return BatchGrade.a;
      case 'B':
        return BatchGrade.b;
      case 'C':
        return BatchGrade.c;
      case 'Reject':
        return BatchGrade.reject;
      default:
        return null;
    }
  }
}

class BatchQualityIssue {
  final String issue;
  final String severity; // low | medium | high (validated server-side)
  final String? evidenceRef;

  BatchQualityIssue({
    required this.issue,
    required this.severity,
    this.evidenceRef,
  });

  factory BatchQualityIssue.fromJson(Map<String, dynamic> json) {
    return BatchQualityIssue(
      issue: json['issue'] as String? ?? '',
      severity: json['severity'] as String? ?? 'medium',
      evidenceRef: json['evidence_ref'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'issue': issue,
        'severity': severity,
        'evidence_ref': evidenceRef,
      };
}

class BatchAssessmentResult {
  final String batchId;
  final BatchGrade finalGrade;
  /// AI assessment confidence [0..1]. This is the model's certainty in its
  /// assessment — it is NOT a grade percentage and NOT a share of onions.
  final double assessmentConfidence;
  /// Estimated onion count (Roboflow view detections across all views; see
  /// [sampleSizeEstimated]). View detections are NOT unique onions — the same
  /// physical onions may appear in multiple views. Never presented as an
  /// exact census unless [sampleSizeEstimated] is false.
  final int sampleSize;
  final bool sampleSizeEstimated;
  final int imagesAnalyzed;
  /// URS% that drove the policy decision (URS onions / grader-declared batch
  /// size x 100). Null when URS evidence was unusable/unknown and the
  /// fallback grade applied — never treated as zero.
  final double? ursPercent;
  /// Grader-declared physical batch size (100-200), echoed exactly by the
  /// backend. Null only for payloads predating the field.
  final int? assessedOnionsDeclared;
  final List<String> observations;
  final List<BatchQualityIssue> visibleQualityIssues;
  final bool reviewRequired;
  final List<String> reviewReasons;
  final String policyVersion;
  final String roboflowModel;
  /// Provider-neutral assessment model id (e.g. qwen/... via OpenRouter).
  final String assessmentModel;
  final DateTime calculatedAt;

  BatchAssessmentResult({
    required this.batchId,
    required this.finalGrade,
    required this.assessmentConfidence,
    required this.sampleSize,
    required this.sampleSizeEstimated,
    required this.imagesAnalyzed,
    this.ursPercent,
    this.assessedOnionsDeclared,
    required this.observations,
    required this.visibleQualityIssues,
    required this.reviewRequired,
    required this.reviewReasons,
    required this.policyVersion,
    required this.roboflowModel,
    required this.assessmentModel,
    DateTime? calculatedAt,
  }) : calculatedAt = calculatedAt ?? DateTime.now();

  factory BatchAssessmentResult.fromJson(Map<String, dynamic> json) {
    final grade = BatchGradeExtension.fromValue(json['final_grade'] as String?);
    if (grade == null) {
      throw FormatException(
          'Invalid final_grade: ${json['final_grade']}. '
          'Only A/B/C/Reject are legal — refusing to invent a grade.');
    }
    final confidence = (json['assessment_confidence'] as num?)?.toDouble();
    if (confidence == null || confidence < 0.0 || confidence > 1.0) {
      throw const FormatException('assessment_confidence outside [0, 1].');
    }
    return BatchAssessmentResult(
      batchId: json['batch_id'] as String? ?? '',
      finalGrade: grade,
      assessmentConfidence: confidence,
      sampleSize: (json['sample_size'] as num?)?.toInt() ?? 0,
      sampleSizeEstimated: json['sample_size_estimated'] as bool? ?? true,
      imagesAnalyzed: (json['images_analyzed'] as num?)?.toInt() ?? 0,
      ursPercent: (json['urs_percent'] as num?)?.toDouble(),
      assessedOnionsDeclared:
          (json['assessed_onions_declared'] as num?)?.toInt(),
      observations: ((json['observations'] as List?) ?? [])
          .map((e) => e.toString())
          .toList(),
      visibleQualityIssues: ((json['visible_quality_issues'] as List?) ?? [])
          .map((e) => BatchQualityIssue.fromJson(
              Map<String, dynamic>.from(e as Map)))
          .toList(),
      reviewRequired: json['review_required'] as bool? ?? true,
      reviewReasons: ((json['review_reasons'] as List?) ?? [])
          .map((e) => e.toString())
          .toList(),
      policyVersion: json['policy_version'] as String? ?? 'unknown',
      roboflowModel: json['roboflow_model'] as String? ?? 'unknown',
      // Legacy fallback: pre-migration payloads used `gemini_model`.
      assessmentModel: (json['assessment_model'] ?? json['gemini_model'])
              as String? ??
          'unknown',
      calculatedAt: json['calculated_at'] != null
          ? DateTime.parse(json['calculated_at'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'batch_id': batchId,
        'final_grade': finalGrade.value,
        'assessment_confidence': assessmentConfidence,
        'sample_size': sampleSize,
        'sample_size_estimated': sampleSizeEstimated,
        'images_analyzed': imagesAnalyzed,
        'urs_percent': ursPercent,
        'assessed_onions_declared': assessedOnionsDeclared,
        'observations': observations,
        'visible_quality_issues':
            visibleQualityIssues.map((e) => e.toJson()).toList(),
        'review_required': reviewRequired,
        'review_reasons': reviewReasons,
        'policy_version': policyVersion,
        'roboflow_model': roboflowModel,
        'assessment_model': assessmentModel,
        'calculated_at': calculatedAt.toIso8601String(),
      };
}
