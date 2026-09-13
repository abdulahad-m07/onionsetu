// test/model_contract_test.dart
//
// CONTRACT tests for the Roboflow hosted vision layer. These tests verify
// the client-side contract (class mapping, detection building, strict
// response parsing) WITHOUT network access and WITHOUT model files.
//
// They never assert detection results from real images, because the Roboflow
// API key is server-side and automated tests MUST mock Roboflow.
// See docs/MODEL_INTEGRATION_SPEC.md.
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/ml/model_contract.dart';
import 'package:frontend/models/detection_model.dart';
import 'package:frontend/models/roboflow_inference.dart';

void main() {
  group('Roboflow contract (offline, mocked shapes only)', () {
    test('Serving model id is pinned and documented', () {
      expect(ModelContract.roboflowModelId, equals('onion-yhzc7-mo9ib/1'));
    });

    test('Client thresholds match the server configuration', () {
      // Backend: ROBOFLOW_MIN_CONFIDENCE=45 (0-100) and ROBOFLOW_OVERLAP=30.
      expect(ModelContract.minConfidence, equals(0.45));
      expect(ModelContract.nmsIouThreshold, equals(0.30));
    });

    test('Known quality labels map; anything else stays unknown', () {
      expect(ModelContract.defectTypeForRoboflowClass('gradeA'),
          equals(OnionDefectType.gradeA));
      expect(ModelContract.defectTypeForRoboflowClass(' Grade A '),
          equals(OnionDefectType.gradeA));
      expect(ModelContract.defectTypeForRoboflowClass('DAMAGED'),
          equals(OnionDefectType.damaged));
      expect(ModelContract.defectTypeForRoboflowClass('rotten'),
          equals(OnionDefectType.rotten));
      expect(ModelContract.defectTypeForRoboflowClass('Sprouted'),
          equals(OnionDefectType.sprouted));
      expect(ModelContract.defectTypeForRoboflowClass('undersized'),
          equals(OnionDefectType.undersized));

      // A generic detector label must NEVER become a quality class.
      expect(ModelContract.defectTypeForRoboflowClass('onion'),
          equals(OnionDefectType.unknown));
      expect(ModelContract.defectTypeForRoboflowClass(''),
          equals(OnionDefectType.unknown));
      expect(ModelContract.isQualityClass('onion'), isFalse);
      expect(ModelContract.isQualityClass('gradeA'), isTrue);
    });

    test('detectionFromPrediction keeps real geometry, class, confidence', () {
      final det = ModelContract.detectionFromPrediction(
        x: 100.0,
        y: 50.0,
        width: 200.0,
        height: 200.0,
        roboflowClass: 'onion',
        confidence: 0.91,
        viewAngle: 'topView',
      );
      expect(det.x, equals(100.0));
      expect(det.y, equals(50.0));
      expect(det.confidence, equals(0.91));
      expect(det.defectType, equals(OnionDefectType.unknown));
      expect(det.rawLabel, equals('onion'));
      expect(det.viewAngle, equals('topView'));
      // Size from real box geometry (200px @ 3.8px/mm ~= 52.6mm).
      expect(det.estimatedDiameterMm, closeTo(52.6, 0.5));
    });

    test('Strict response parsing accepts a real-shaped backend body', () {
      final result = RoboflowInferenceResult.fromJson({
        'model_id': 'onion-yhzc7-mo9ib/1',
        'image_width': 800,
        'image_height': 600,
        'predictions': [
          {
            'x': 100.0,
            'y': 100.0,
            'width': 120.0,
            'height': 120.0,
            'roboflow_class': 'onion',
            'class_id': 0,
            'confidence': 0.93,
            'detection_id': 'det_1',
            'defect_type': 'unknown',
            'quality_mapped': false,
          },
        ],
        'observed_classes': ['onion'],
        'quality_classification_available': false,
        'dropped_invalid_predictions': 0,
      });
      expect(result.predictions.length, equals(1));
      expect(result.predictions.first.roboflowClass, equals('onion'));
      expect(result.predictions.first.confidence, equals(0.93));
      expect(result.qualityClassificationAvailable, isFalse);
      expect(result.observedClasses, equals(['onion']));
    });

    test('Malformed prediction bodies throw instead of inventing data', () {
      expect(
        () => NormalizedPredictionItem.fromJson({
          'x': 1.0,
          'y': 2.0,
          // width missing
          'height': 10.0,
          'roboflow_class': 'onion',
          'confidence': 0.9,
        }),
        throwsFormatException,
      );
      expect(
        () => NormalizedPredictionItem.fromJson({
          'x': 1.0,
          'y': 2.0,
          'width': 10.0,
          'height': 10.0,
          'roboflow_class': 'onion',
          'confidence': 1.5, // outside [0,1]
        }),
        throwsFormatException,
      );
      expect(
        () => RoboflowInferenceResult.fromJson({'model_id': 'x'}),
        throwsFormatException,
      );
    });
  });
}
