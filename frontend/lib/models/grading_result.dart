// lib/models/grading_result.dart
import 'detection_model.dart';

enum ConfidenceGateStatus {
  highConfidence, // Automatic pass to versioned grading policy
  borderlineReview, // Low or borderline AI confidence -> Human Review Flag
}

class GradingResult {
  final String id;
  final String scanId;
  final double gradeAPercentage; // e.g. 85.0%
  final double ursPercentage; // Under-grade / Rejection / Secondary percentage e.g. 15.0%
  final double averageAiConfidence; // Mean model confidence [0..1]
  final ConfidenceGateStatus confidenceStatus;
  final String policyVersion; // e.g. 'v1.0.0'
  final int totalOnionsCount;
  final int gradeACount;
  final int damagedCount;
  final int rottenCount;
  final int sproutedCount;
  final int undersizedCount;
  /// Detections whose model label is NOT a known quality class (e.g. a
  /// generic "onion" detector label). Counted in [totalOnionsCount] but
  /// excluded from the Grade A numerator; any value > 0 forces human review
  /// and marks [qualityClassificationAvailable] false. Never invented.
  final int unclassifiedCount;
  /// False when the serving model cannot provide quality classification
  /// (current Roboflow deployment). Percentages are then provisional and
  /// the result must go through human review.
  final bool qualityClassificationAvailable;
  final double? avgSizeMm;
  final String? auditHash;
  final DateTime calculatedAt;

  GradingResult({
    required this.id,
    required this.scanId,
    required this.gradeAPercentage,
    required this.ursPercentage,
    required this.averageAiConfidence,
    required this.confidenceStatus,
    required this.policyVersion,
    required this.totalOnionsCount,
    required this.gradeACount,
    required this.damagedCount,
    required this.rottenCount,
    required this.sproutedCount,
    required this.undersizedCount,
    this.unclassifiedCount = 0,
    this.qualityClassificationAvailable = true,
    this.avgSizeMm,
    this.auditHash,
    DateTime? calculatedAt,
  }) : calculatedAt = calculatedAt ?? DateTime.now();

  Map<String, dynamic> toJson() => {
    'id': id,
    'scan_id': scanId,
    'grade_a_percentage': gradeAPercentage,
    'urs_percentage': ursPercentage,
    'average_ai_confidence': averageAiConfidence,
    'confidence_status': confidenceStatus.name,
    'policy_version': policyVersion,
    'total_onions_count': totalOnionsCount,
    'grade_a_count': gradeACount,
    'damaged_count': damagedCount,
    'rotten_count': rottenCount,
    'sprouted_count': sproutedCount,
    'undersized_count': undersizedCount,
    'unclassified_count': unclassifiedCount,
    'quality_classification_available': qualityClassificationAvailable,
    'avg_size_mm': avgSizeMm,
    'audit_hash': auditHash,
    'calculated_at': calculatedAt.toIso8601String(),
  };

  factory GradingResult.fromJson(Map<String, dynamic> json) {
    return GradingResult(
      id: json['id'] as String,
      scanId: json['scan_id'] as String,
      gradeAPercentage: (json['grade_a_percentage'] as num).toDouble(),
      ursPercentage: (json['urs_percentage'] as num).toDouble(),
      averageAiConfidence: (json['average_ai_confidence'] as num).toDouble(),
      confidenceStatus: json['confidence_status'] == 'borderlineReview'
          ? ConfidenceGateStatus.borderlineReview
          : ConfidenceGateStatus.highConfidence,
      policyVersion: json['policy_version'] as String? ?? 'v1.0.0',
      totalOnionsCount: (json['total_onions_count'] as num).toInt(),
      gradeACount: (json['grade_a_count'] as num).toInt(),
      damagedCount: (json['damaged_count'] as num).toInt(),
      rottenCount: (json['rotten_count'] as num).toInt(),
      sproutedCount: (json['sprouted_count'] as num).toInt(),
      undersizedCount: (json['undersized_count'] as num).toInt(),
      unclassifiedCount: (json['unclassified_count'] as num?)?.toInt() ?? 0,
      qualityClassificationAvailable:
          json['quality_classification_available'] as bool? ?? true,
      avgSizeMm: (json['avg_size_mm'] as num?)?.toDouble(),
      auditHash: json['audit_hash'] as String?,
      calculatedAt: DateTime.parse(json['calculated_at'] as String),
    );
  }
}
