// test/batch_assessment_test.dart
//
// Batch A/B/C/Reject pipeline tests with MOCKED transport only.
// No test touches the network, a model file, or a real provider.
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/models/batch_assessment.dart';
import 'package:frontend/models/scan_model.dart';
import 'package:frontend/services/api_service.dart';

Map<String, dynamic> _okBody() => {
      'batch_id': 'batch_01',
      'final_grade': 'B',
      'assessment_confidence': 0.87,
      'sample_size': 150,
      'sample_size_estimated': true,
      'images_analyzed': 8,
      'urs_percent': 8.0,
      'assessed_onions_declared': 150,
      'evidence': [],
      'observations': ['Uniform bulbs across views'],
      'visible_quality_issues': [
        {'issue': 'Minor skin blemish', 'severity': 'low', 'evidence_ref': 'image 2'},
      ],
      'review_required': false,
      'review_reasons': ['Sample size is estimated.'],
      'policy_version': 'v0.1-provisional',
      'roboflow_model': 'onion-yhzc7-mo9ib/1',
      'assessment_model': 'qwen/qwen2.5-vl-72b-instruct:free',
      'calculated_at': '2026-09-12T10:00:00.000Z',
    };

void main() {
  group('BatchAssessmentResult strict parsing', () {
    test('Accepts a valid batch body with exactly one final grade', () {
      final result = BatchAssessmentResult.fromJson(_okBody());
      expect(result.finalGrade, equals(BatchGrade.b));
      expect(result.assessmentConfidence, equals(0.87));
      expect(result.sampleSize, equals(150));
      expect(result.sampleSizeEstimated, isTrue);
      expect(result.reviewRequired, isFalse);
      expect(result.visibleQualityIssues.length, equals(1));
      // URS driver: the single URS% + the grader-declared denominator.
      expect(result.ursPercent, equals(8.0));
      expect(result.assessedOnionsDeclared, equals(150));
    });

    test('URS fields are optional (absent stays null, never zero)', () {
      final body = _okBody()
        ..remove('urs_percent')
        ..remove('assessed_onions_declared');
      final result = BatchAssessmentResult.fromJson(body);
      expect(result.ursPercent, isNull);
      expect(result.assessedOnionsDeclared, isNull);
      expect(result.finalGrade, equals(BatchGrade.b));
    });

    test('Rejects grades outside A/B/C/Reject instead of coercing', () {
      for (final bad in ['A+', 'a', 'Grade A', 'PASS', '', 'onion']) {
        final body = _okBody()..['final_grade'] = bad;
        expect(
          () => BatchAssessmentResult.fromJson(body),
          throwsFormatException,
          reason: 'grade $bad must not become a final grade',
        );
      }
    });

    test('Rejects confidence outside [0, 1]', () {
      final body = _okBody()..['assessment_confidence'] = 9.9;
      expect(() => BatchAssessmentResult.fromJson(body), throwsFormatException);
    });

    test('Defaults review to required when the flag is absent', () {
      final body = _okBody()..remove('review_required');
      expect(BatchAssessmentResult.fromJson(body).reviewRequired, isTrue);
    });

    test('Legacy gemini_model payloads still parse (migration tolerance)', () {
      final body = _okBody()
        ..remove('assessment_model')
        ..['gemini_model'] = 'gemini-3.1-pro-preview';
      expect(
        BatchAssessmentResult.fromJson(body).assessmentModel,
        equals('gemini-3.1-pro-preview'),
      );
    });
  });

  group('requestBatchAssessment client (mocked transport)', () {
    test('Posts all images + scan id + declared count, parses final grade',
        () async {
      var calls = 0;
      final mockClient = MockClient((request) async {
        calls++;
        expect(request.headers['Authorization'], equals('Bearer tok'));
        // Grader-declared denominator travels as a multipart field
        // (MockClient finalizes the request, so assert on the body).
        final body = (request as http.Request).body;
        expect(body.contains('name="assessed_onions"'), isTrue);
        expect(body.contains('150'), isTrue);
        expect(body.contains('name="scan_id"'), isTrue);
        return http.Response(jsonEncode(_okBody()), 200);
      });

      final api = ApiService(baseUrl: 'http://test/v1', client: mockClient);
      final result = await api.requestBatchAssessment(
        imageBytes: [
          Uint8List.fromList([1, 2, 3]),
          Uint8List.fromList([4, 5, 6]),
        ],
        filenames: ['a.jpg', 'b.jpg'],
        token: 'tok',
        assessedOnions: 150,
        scanId: 'scan_1',
      );
      expect(calls, equals(1));
      expect(result.finalGrade, equals(BatchGrade.b));
      expect(result.ursPercent, equals(8.0));
      expect(result.assessedOnionsDeclared, equals(150));
      expect(result.assessmentModel,
          equals('qwen/qwen2.5-vl-72b-instruct:free'));
    });

    test('Request carries only the JWT, never provider credentials', () async {
      final mockClient = MockClient((request) async {
        expect(request.headers['Authorization'], equals('Bearer tok'));
        expect(request.headers.containsKey('x-goog-api-key'), isFalse);
        expect(request.url.queryParameters.containsKey('api_key'), isFalse);
        return http.Response(jsonEncode(_okBody()), 200);
      });

      final api = ApiService(baseUrl: 'http://test/v1', client: mockClient);
      await api.requestBatchAssessment(
        imageBytes: [Uint8List.fromList([1])],
        filenames: ['a.jpg'],
        token: 'tok',
        assessedOnions: 150,
      );
    });

    test('Retries transport failures, then succeeds', () async {
      var calls = 0;
      final mockClient = MockClient((_) async {
        calls++;
        if (calls < 3) return http.Response('down', 503);
        return http.Response(jsonEncode(_okBody()), 200);
      });

      final api = ApiService(
        baseUrl: 'http://test/v1',
        client: mockClient,
        maxInferenceAttempts: 3,
      );
      final result = await api.requestBatchAssessment(
        imageBytes: [Uint8List.fromList([1])],
        filenames: ['a.jpg'],
        token: 'tok',
        assessedOnions: 150,
      );
      expect(calls, equals(3));
      expect(result.finalGrade, equals(BatchGrade.b));
    });

    test('4xx is not retried and surfaces immediately', () async {
      var calls = 0;
      final mockClient = MockClient((_) async {
        calls++;
        return http.Response('too many', 400);
      });
      final api = ApiService(baseUrl: 'http://test/v1', client: mockClient);
      await expectLater(
        () => api.requestBatchAssessment(
          imageBytes: [Uint8List.fromList([1])],
          filenames: ['a.jpg'],
          token: 'tok',
          assessedOnions: 150,
        ),
        throwsException,
      );
      expect(calls, equals(1));
    });

    test('Response never carries provider credentials', () async {
      final mockClient = MockClient(
        (_) async => http.Response(jsonEncode(_okBody()), 200),
      );
      final api = ApiService(baseUrl: 'http://test/v1', client: mockClient);
      final result = await api.requestBatchAssessment(
        imageBytes: [Uint8List.fromList([1])],
        filenames: ['a.jpg'],
        token: 'tok',
        assessedOnions: 150,
      );
      final encoded = jsonEncode(result.toJson());
      expect(encoded.contains('API_KEY'), isFalse);
      expect(encoded.contains('api_key'), isFalse);
      // URS driver survives the client round-trip (sync payload intact).
      expect(result.toJson()['urs_percent'], equals(8.0));
      expect(result.toJson()['assessed_onions_declared'], equals(150));
    });
  });

  group('Offline batch state', () {
    test('Sessions start without a batch grade and round-trip it', () {
      final session = ScanSession(
        id: 'scan_off_01',
        lotNumber: 'LOT-OFF-01',
        farmerName: 'Suresh',
        farmerPhone: '+919800000000',
        procurementCenterId: 'APMC-01',
        graderId: 'grader_01',
        assessedOnions: 150,
      );
      // Offline: no grade exists and none is implied.
      expect(session.batchAssessment, isNull);
      expect(ScanSession.fromJson(session.toJson()).batchAssessment, isNull);
      // The grader-declared denominator survives the offline round-trip.
      expect(
        ScanSession.fromJson(session.toJson()).assessedOnions,
        equals(150),
      );

      final graded = session.copyWith(
        batchAssessment: BatchAssessmentResult.fromJson(_okBody()),
      );
      final restored = ScanSession.fromJson(graded.toJson());
      expect(restored.batchAssessment, isNotNull);
      expect(restored.batchAssessment!.finalGrade, equals(BatchGrade.b));
      expect(restored.batchAssessment!.sampleSizeEstimated, isTrue);
    });
  });
}
