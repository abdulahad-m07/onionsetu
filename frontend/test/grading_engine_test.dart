// test/grading_engine_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/models/detection_model.dart';
import 'package:frontend/models/grading_result.dart';
import 'package:frontend/services/grading_engine.dart';

void main() {
  group('GradingEngine & Versioned Policy Tests', () {
    const engine = GradingEngine(policy: GradingPolicy(version: 'v1.0.0', minConfidenceThreshold: 0.70));

    test('Deterministic Grade A % and URS % calculation for standard lot', () {
      final detections = [
        // 8 Grade A healthy onions (55mm diameter)
        ...List.generate(
          8,
          (i) => DetectionItem(
            id: 'det_$i',
            x: 50.0 * i,
            y: 50.0,
            width: 100.0,
            height: 100.0,
            defectType: OnionDefectType.gradeA,
            confidence: 0.92,
            estimatedDiameterMm: 55.0,
          ),
        ),
        // 1 Damaged onion
        DetectionItem(
          id: 'det_dam',
          x: 450.0,
          y: 50.0,
          width: 100.0,
          height: 100.0,
          defectType: OnionDefectType.damaged,
          confidence: 0.88,
          estimatedDiameterMm: 50.0,
        ),
        // 1 Sprouted onion
        DetectionItem(
          id: 'det_spr',
          x: 50.0,
          y: 200.0,
          width: 100.0,
          height: 100.0,
          defectType: OnionDefectType.sprouted,
          confidence: 0.90,
          estimatedDiameterMm: 48.0,
        ),
      ];

      final result = engine.calculateGrading(scanId: 'scan_test_01', detections: detections);

      expect(result.totalOnionsCount, equals(10));
      expect(result.gradeACount, equals(8));
      expect(result.damagedCount, equals(1));
      expect(result.sproutedCount, equals(1));
      expect(result.gradeAPercentage, equals(80.0));
      expect(result.ursPercentage, equals(20.0));
      expect(result.averageAiConfidence, closeTo(0.91, 0.02));
      expect(result.confidenceStatus, equals(ConfidenceGateStatus.highConfidence));
      expect(result.policyVersion, equals('v1.0.0'));
      expect(result.auditHash, isNotNull);
      expect(result.auditHash!.length, equals(64)); // Valid SHA-256 string
    });

    test('Low AI confidence triggers Human Review Flag on confidence gate', () {
      final lowConfidenceDetections = [
        DetectionItem(
          id: 'det_low_1',
          x: 50.0,
          y: 50.0,
          width: 100.0,
          height: 100.0,
          defectType: OnionDefectType.gradeA,
          confidence: 0.45, // Below 0.70 threshold
          estimatedDiameterMm: 50.0,
        ),
      ];

      final result = engine.calculateGrading(scanId: 'scan_test_low', detections: lowConfidenceDetections);

      expect(result.confidenceStatus, equals(ConfidenceGateStatus.borderlineReview));
      // Confidence is distinct from Grade A %
      expect(result.gradeAPercentage, equals(100.0));
      expect(result.averageAiConfidence, equals(0.45));
    });

    test('Undersized onion is not counted as Grade A', () {
      final detections = [
        DetectionItem(
          id: 'det_tiny',
          x: 50.0,
          y: 50.0,
          width: 60.0,
          height: 60.0,
          defectType: OnionDefectType.gradeA,
          confidence: 0.90,
          estimatedDiameterMm: 30.0, // Below 40mm Grade A min diameter
        ),
      ];

      final result = engine.calculateGrading(scanId: 'scan_test_tiny', detections: detections);

      expect(result.gradeACount, equals(0));
      expect(result.undersizedCount, equals(1));
      expect(result.gradeAPercentage, equals(0.0));
      expect(result.ursPercentage, equals(100.0));
    });
  });
}
