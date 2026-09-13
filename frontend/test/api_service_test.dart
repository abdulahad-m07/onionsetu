// test/api_service_test.dart
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/services/api_service.dart';
import 'package:frontend/models/scan_model.dart';
import 'package:frontend/models/dispute_model.dart';

void main() {
  group('Frontend ApiService Integration Tests', () {
    test('sendOtp sends phone and returns success', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, contains('/auth/send-otp'));
        final body = jsonDecode(request.body);
        expect(body['phone'], equals('+919823011223'));
        return http.Response(jsonEncode({'status': 'success'}), 200);
      });

      final apiService = ApiService(baseUrl: 'http://test/v1', client: mockClient);
      final result = await apiService.sendOtp('+919823011223');
      expect(result, isTrue);
    });

    test('submitScan serializes ScanSession and posts with auth header', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, contains('/scans/'));
        expect(request.headers['Authorization'], equals('Bearer test_jwt_token'));
        final body = jsonDecode(request.body);
        expect(body['id'], equals('scan_mock_01'));
        expect(body['lot_number'], equals('LOT-MOCK-01'));
        return http.Response(jsonEncode({'id': 'scan_mock_01'}), 201);
      });

      final apiService = ApiService(baseUrl: 'http://test/v1', client: mockClient);
      final scan = ScanSession(
        id: 'scan_mock_01',
        lotNumber: 'LOT-MOCK-01',
        farmerName: 'Ramesh',
        farmerPhone: '+919811223344',
        procurementCenterId: 'APMC-01',
        graderId: 'grader_01',
      );

      final result = await apiService.submitScan(scan, 'test_jwt_token');
      expect(result, isTrue);
    });

    test('syncBatch sends offline queue list', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, contains('/sync/batch'));
        final body = jsonDecode(request.body);
        expect(body['client_device_id'], equals('tab_01'));
        expect(body['scans'].length, equals(1));
        return http.Response(jsonEncode({
          'processed_count': 1,
          'synced_ids': ['scan_offline_01'],
          'failed_ids': [],
          'message': 'OK',
        }), 200);
      });

      final apiService = ApiService(baseUrl: 'http://test/v1', client: mockClient);
      final scan = ScanSession(
        id: 'scan_offline_01',
        lotNumber: 'LOT-OFFLINE-01',
        farmerName: 'Suresh',
        farmerPhone: '+919800000000',
        procurementCenterId: 'APMC-01',
        graderId: 'grader_01',
      );

      final result = await apiService.syncBatch('tab_01', [scan], 'test_jwt_token');
      expect(result['processed_count'], equals(1));
      expect(result['synced_ids'], contains('scan_offline_01'));
    });
  });
}
