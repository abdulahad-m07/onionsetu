// test/widget_test.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend/main.dart';
import 'package:frontend/models/user_model.dart';
import 'package:frontend/providers/auth_provider.dart';
import 'package:frontend/services/api_service.dart';

/// Builds an AuthProvider authenticated through MOCKED transport only
/// (backend TokenResponse shape, no network, no mock tokens).
Future<AuthProvider> _authenticatedAuth() async {
  final mockClient = MockClient((request) async {
    if (request.url.path.endsWith('/auth/verify-otp')) {
      return http.Response(
          jsonEncode({
            'access_token': 'test-jwt-for-widget',
            'token_type': 'bearer',
            'expires_in': 7200,
            'user_id': 'grader_widget_01',
            'name': 'Widget Grader',
            'role': 'grader',
            'procurement_center_id': 'APMC-LASALGAON-01',
          }),
          200);
    }
    return http.Response('not found', 404);
  });
  final auth = AuthProvider(
    apiService: ApiService(baseUrl: 'http://test/v1', client: mockClient),
  );
  final ok = await auth.verifyOtp(
    '+910000000000',
    '123456',
    UserRole.grader,
    'Widget Grader',
  );
  assert(ok, 'test auth setup must succeed through the mocked transport');
  return auth;
}

void main() {
  testWidgets('Login screen shows first when logged out',
      (WidgetTester tester) async {
    await tester.pumpWidget(const OnionSetuApp());
    await tester.pumpAndSettle();

    expect(find.text('OnionSetu Login'), findsOneWidget);
    expect(find.text('Send OTP'), findsOneWidget);
  });

  testWidgets('App shell renders navigation tabs and switches cleanly',
      (WidgetTester tester) async {
    await tester.pumpWidget(
        OnionSetuApp(authProvider: await _authenticatedAuth()));
    await tester.pumpAndSettle();

    // Verify New Scan / Sampling Session screen is displayed
    expect(find.text('New Assessment Session'), findsOneWidget);
    expect(find.text('Start Guided Capture'), findsOneWidget);

    // Switch to History tab
    await tester.tap(find.byIcon(Icons.history_outlined));
    await tester.pumpAndSettle();

    expect(find.text('Offline Scan History'), findsOneWidget);

    // Switch to Settings tab
    await tester.tap(find.byIcon(Icons.settings_outlined));
    await tester.pumpAndSettle();

    expect(find.text('Settings & Configuration'), findsOneWidget);
    expect(find.text('Grading Policy Engine'), findsOneWidget);
  });

  test('Authenticated session carries a backend-issued token shape', () async {
    final auth = await _authenticatedAuth();
    expect(auth.isAuthenticated, isTrue);
    expect(auth.authToken, equals('test-jwt-for-widget'));
    expect(auth.currentUser?.id, equals('grader_widget_01'));
    expect(auth.currentUser?.procurementCenterId,
        equals('APMC-LASALGAON-01'));
  });
}
