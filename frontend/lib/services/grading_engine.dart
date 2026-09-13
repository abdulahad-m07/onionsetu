// lib/services/grading_engine.dart
import 'dart:convert';
import 'package:crypto/crypto.dart';
import 'package:uuid/uuid.dart';
import '../models/detection_model.dart';
import '../models/grading_result.dart';

class GradingPolicy {
  final String version;
  final double minConfidenceThreshold; // Minimum AI confidence to avoid Human Review Flag (e.g. 0.70)
  final double minDiameterMmGradeA; // Minimum diameter for Grade A (e.g. 40mm)
  final double maxDiameterMmGradeA; // Maximum diameter for Grade A (e.g. 90mm)
  final double maxTolerableDefectPercent; // Max defect % before whole lot downgraded

  const GradingPolicy({
    this.version = 'v1.0.0',
    this.minConfidenceThreshold = 0.70,
    this.minDiameterMmGradeA = 40.0,
    this.maxDiameterMmGradeA = 90.0,
    this.maxTolerableDefectPercent = 10.0,
  });

  Map<String, dynamic> toJson() => {
    'version': version,
    'min_confidence_threshold': minConfidenceThreshold,
    'min_diameter_mm_grade_a': minDiameterMmGradeA,
    'max_diameter_mm_grade_a': maxDiameterMmGradeA,
    'max_tolerable_defect_percent': maxTolerableDefectPercent,
  };
}

class GradingEngine {
  final GradingPolicy policy;

  const GradingEngine({this.policy = const GradingPolicy()});

  /// Computes deterministic GradingResult from VALIDATED vision-model
  /// detections and versioned policy.
  /// The model provides perception (boxes, classes, real confidence); this
  /// engine calculates Grade A / URS outcomes. AI confidence describes
  /// prediction certainty; Grade A / URS are calculated grading outcomes.
  ///
  /// Truthfulness rule: detections whose label is not a known quality class
  /// ([OnionDefectType.unknown]) are counted in [GradingResult.unclassifiedCount]
  /// and total, excluded from the Grade A numerator, and ALWAYS force
  /// [ConfidenceGateStatus.borderlineReview] with
  /// [GradingResult.qualityClassificationAvailable] = false. They are never
  /// converted into gradeA or any defect class to "make percentages work".
  GradingResult calculateGrading({
    required String scanId,
    required List<DetectionItem> detections,
  }) {
    if (detections.isEmpty) {
      return GradingResult(
        id: const Uuid().v4(),
        scanId: scanId,
        gradeAPercentage: 0.0,
        ursPercentage: 100.0,
        averageAiConfidence: 0.0,
        confidenceStatus: ConfidenceGateStatus.borderlineReview,
        policyVersion: policy.version,
        totalOnionsCount: 0,
        gradeACount: 0,
        damagedCount: 0,
        rottenCount: 0,
        sproutedCount: 0,
        undersizedCount: 0,
        unclassifiedCount: 0,
        qualityClassificationAvailable: false,
        avgSizeMm: 0.0,
        calculatedAt: DateTime.now(),
      );
    }

    int gradeACount = 0;
    int damagedCount = 0;
    int rottenCount = 0;
    int sproutedCount = 0;
    int undersizedCount = 0;
    int unclassifiedCount = 0;

    double totalConfidence = 0;
    double totalDiameter = 0;
    int diameterCount = 0;

    for (final item in detections) {
      totalConfidence += item.confidence;
      if (item.estimatedDiameterMm != null && item.estimatedDiameterMm! > 0) {
        totalDiameter += item.estimatedDiameterMm!;
        diameterCount++;
      }

      switch (item.defectType) {
        case OnionDefectType.gradeA:
          // Verify size compatibility with policy
          final diam = item.estimatedDiameterMm ?? 55.0;
          if (diam >= policy.minDiameterMmGradeA && diam <= policy.maxDiameterMmGradeA) {
            gradeACount++;
          } else {
            undersizedCount++;
          }
          break;
        case OnionDefectType.damaged:
          damagedCount++;
          break;
        case OnionDefectType.rotten:
          rottenCount++;
          break;
        case OnionDefectType.sprouted:
          sproutedCount++;
          break;
        case OnionDefectType.undersized:
          undersizedCount++;
          break;
        case OnionDefectType.unknown:
          // Model label carries no quality information: count honestly,
          // classify never.
          unclassifiedCount++;
          break;
      }
    }

    final int total = detections.length;
    final double avgConfidence = total > 0 ? (totalConfidence / total) : 0.0;
    final double avgSizeMm = diameterCount > 0 ? (totalDiameter / diameterCount) : 55.0;

    final double gradeAPercent = total > 0
        ? double.parse(((gradeACount / total) * 100.0).toStringAsFixed(1))
        : 0.0;
    final double ursPercent = double.parse((100.0 - gradeAPercent).toStringAsFixed(1));

    // Quality availability: true only when every detection carries a genuine
    // quality class. Awaiting a five-class Roboflow model otherwise.
    final bool qualityAvailable =
        total > 0 && unclassifiedCount == 0;

    // Confidence Gate: mean REAL model confidence vs policy threshold, OR
    // forced human review when quality classification is unavailable.
    final confidenceStatus =
        (avgConfidence >= policy.minConfidenceThreshold && qualityAvailable)
            ? ConfidenceGateStatus.highConfidence
            : ConfidenceGateStatus.borderlineReview;

    // Compute deterministic SHA-256 hash for audit verification
    final String resultId = const Uuid().v4();
    final String auditPayload = jsonEncode({
      'result_id': resultId,
      'scan_id': scanId,
      'grade_a_percent': gradeAPercent,
      'urs_percent': ursPercent,
      'total_count': total,
      'policy_version': policy.version,
    });
    final String auditHash = sha256.convert(utf8.encode(auditPayload)).toString();

    return GradingResult(
      id: resultId,
      scanId: scanId,
      gradeAPercentage: gradeAPercent,
      ursPercentage: ursPercent,
      averageAiConfidence: double.parse(avgConfidence.toStringAsFixed(3)),
      confidenceStatus: confidenceStatus,
      policyVersion: policy.version,
      totalOnionsCount: total,
      gradeACount: gradeACount,
      damagedCount: damagedCount,
      rottenCount: rottenCount,
      sproutedCount: sproutedCount,
      undersizedCount: undersizedCount,
      unclassifiedCount: unclassifiedCount,
      qualityClassificationAvailable: qualityAvailable,
      avgSizeMm: double.parse(avgSizeMm.toStringAsFixed(1)),
      auditHash: auditHash,
      calculatedAt: DateTime.now(),
    );
  }
}
