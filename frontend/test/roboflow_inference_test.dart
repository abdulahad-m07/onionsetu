// test/roboflow_inference_test.dart
//
// Roboflow pipeline tests with MOCKED transport only. No test here touches
// the network, a model file, or the real Roboflow service.
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/models/detection_model.dart';
import 'package:frontend/models/grading_result.dart';
import 'package:frontend/models/scan_model.dart';
import 'package:frontend/services/api_service.dart';
import 'package:frontend/services/grading_engine.dart';

Map<String, dynamic> _okBody() => {
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
    };

void main() {
  group('Roboflow inference client (mocked transport)', () {
    test('Retries transport failures then parses validated predictions', () async {
      var calls = 0;
      final mockClient = MockClient((request) async {
        calls++;
        expect(request.headers['Authorization'], equals('Bearer tok'));
        if (calls < 3) {
          return http.Response('upstream boom', 500);
        }
        return http.Response(jsonEncode(_okBody()), 200);
      });

      final api = ApiService(
        baseUrl: 'http://test/v1',
        client: mockClient,
        maxInferenceAttempts: 3,
      );
      final result = await api.analyzeImage(
        imageBytes: Uint8List.fromList([0xFF, 0xD8, 0xFF]),
        filename: 'scan.jpg',
        token: 'tok',
      );
      expect(calls, equals(3));
      expect(result.predictions.length, equals(1));
      expect(result.predictions.first.confidence, equals(0.93));
      expect(result.qualityClassificationAvailable, isFalse);
    });

    test('Gives up after max attempts instead of inventing output', () async {
      final mockClient = MockClient((_) async => http.Response('down', 503));
      final api = ApiService(
        baseUrl: 'http://test/v1',
        client: mockClient,
        maxInferenceAttempts: 2,
      );
      expect(
        () => api.analyzeImage(
          imageBytes: Uint8List.fromList([1, 2, 3]),
          filename: 'scan.jpg',
          token: 'tok',
        ),
        throwsA(isA<RetryableInferenceException>()),
      );
    });

    test('Client errors are not retried', () async {
      var calls = 0;
      final mockClient = MockClient((_) async {
        calls++;
        return http.Response('bad key mapping', 401);
      });
      final api = ApiService(baseUrl: 'http://test/v1', client: mockClient);
      await expectLater(
        () => api.analyzeImage(
          imageBytes: Uint8List.fromList([1, 2, 3]),
          filename: 'scan.jpg',
          token: 'tok',
        ),
        throwsException,
      );
      expect(calls, equals(1));
    });
  });

  group('Grading with unclassified (non-quality) model labels', () {
    const engine = GradingEngine();

    test('Unknown-class detections force human review, never gradeA', () {
      final detections = List.generate(
        3,
        (i) => DetectionItem(
          id: 'det_$i',
          x: 10.0 * i,
          y: 10.0,
          width: 120.0,
          height: 120.0,
          defectType: OnionDefectType.unknown,
          confidence: 0.95,
          estimatedDiameterMm: 55.0,
          rawLabel: 'onion',
        ),
      );
      final result =
          engine.calculateGrading(scanId: 'scan_rf_01', detections: detections);
      expect(result.totalOnionsCount, equals(3));
      expect(result.unclassifiedCount, equals(3));
      expect(result.gradeACount, equals(0));
      expect(result.qualityClassificationAvailable, isFalse);
      expect(result.confidenceStatus,
          equals(ConfidenceGateStatus.borderlineReview));
      // Real count preserved; percentages honestly reflect zero classified.
      expect(result.averageAiConfidence, equals(0.95));
    });

    test('Mixed known + unknown still requires human review', () {
      final detections = [
        DetectionItem(
          id: 'a',
          x: 0,
          y: 0,
          width: 120,
          height: 120,
          defectType: OnionDefectType.gradeA,
          confidence: 0.96,
          estimatedDiameterMm: 55.0,
          rawLabel: 'gradeA',
        ),
        DetectionItem(
          id: 'b',
          x: 130,
          y: 0,
          width: 120,
          height: 120,
          defectType: OnionDefectType.unknown,
          confidence: 0.90,
          estimatedDiameterMm: 55.0,
          rawLabel: 'onion',
        ),
      ];
      final result =
          engine.calculateGrading(scanId: 'scan_rf_02', detections: detections);
      expect(result.gradeACount, equals(1));
      expect(result.unclassifiedCount, equals(1));
      expect(result.qualityClassificationAvailable, isFalse);
      expect(result.confidenceStatus,
          equals(ConfidenceGateStatus.borderlineReview));
    });
  });

  group('Offline pending-AI state', () {
    test('New sessions default to pendingAi and round-trip losslessly', () {
      final session = ScanSession(
        id: 'scan_off_01',
        lotNumber: 'LOT-OFF-01',
        farmerName: 'Suresh',
        farmerPhone: '+919800000000',
        procurementCenterId: 'APMC-01',
        graderId: 'grader_01',
      );
      expect(session.aiStatus, equals(AiInferenceStatus.pendingAi));
      expect(session.result, isNull);

      final restored = ScanSession.fromJson(session.toJson());
      expect(restored.aiStatus, equals(AiInferenceStatus.pendingAi));

      final failed = session.copyWith(aiStatus: AiInferenceStatus.failed);
      expect(ScanSession.fromJson(failed.toJson()).aiStatus,
          equals(AiInferenceStatus.failed));
    });

    test('Detection raw labels survive serialization', () {
      final det = DetectionItem(
        id: 'd1',
        x: 1,
        y: 2,
        width: 3,
        height: 4,
        defectType: OnionDefectType.unknown,
        confidence: 0.8,
        rawLabel: 'onion',
      );
      expect(
          DetectionItem.fromJson(det.toJson()).rawLabel, equals('onion'));
    });
  });
}
