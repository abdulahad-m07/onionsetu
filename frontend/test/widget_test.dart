// test/widget_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/main.dart';
import 'package:frontend/screens/sampling_session_screen.dart';
import 'package:frontend/screens/history_screen.dart';
import 'package:frontend/screens/settings_screen.dart';

void main() {
  testWidgets('App shell renders navigation tabs and switches cleanly', (WidgetTester tester) async {
    await tester.pumpWidget(const OnionSetuApp());
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
}
