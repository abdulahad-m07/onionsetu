// lib/config/environment.dart

enum AppEnvironment { dev, test, prod }

class EnvironmentConfig {
  static AppEnvironment environment = AppEnvironment.dev;

  /// Single central API base URL for the whole app.
  ///
  /// Localhost switching (no code changes, no backend changes):
  /// - Flutter Web on this PC: run with
  ///   --dart-define=API_BASE_URL=http://127.0.0.1:8000/v1
  /// - Android emulator: default below (10.0.2.2 routes to the host PC).
  /// - Physical device: --dart-define=API_BASE_URL=http://<PC-LAN-IP>:8000/v1
  static String get apiBaseUrl {
    switch (environment) {
      case AppEnvironment.prod:
        return const String.fromEnvironment(
          'API_BASE_URL',
          defaultValue: 'https://api.onionsetu.org/v1',
        );
      case AppEnvironment.test:
        return const String.fromEnvironment(
          'API_BASE_URL',
          defaultValue: 'http://127.0.0.1:8000/v1',
        );
      case AppEnvironment.dev:
      default:
        return const String.fromEnvironment(
          'API_BASE_URL',
          defaultValue: 'http://10.0.2.2:8000/v1',
        );
    }
  }

  static const String appName = 'OnionSetu';
  static const String appVersion = '1.0.0';
  static const String gradingPolicyVersion = 'v1.0.0';
  static const int syncBatchSize = 50;
  static const int maxRetryAttempts = 3;
}
