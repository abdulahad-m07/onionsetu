// lib/main.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/auth_provider.dart';
import 'providers/scan_provider.dart';
import 'providers/history_provider.dart';
import 'theme/app_theme.dart';
import 'screens/login_screen.dart';
import 'screens/main_navigation_shell.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const OnionSetuApp());
}

class OnionSetuApp extends StatelessWidget {
  /// Optional override for tests; production always starts logged out and
  /// shows [LoginScreen] until the backend issues a real JWT.
  final AuthProvider? authProvider;

  const OnionSetuApp({super.key, this.authProvider});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
            create: (_) => authProvider ?? AuthProvider()),
        ChangeNotifierProvider(create: (_) => ScanProvider()),
        ChangeNotifierProvider(create: (_) => HistoryProvider()),
      ],
      child: MaterialApp(
        title: 'OnionSetu',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        home: Consumer<AuthProvider>(
          builder: (_, auth, __) => auth.isAuthenticated
              ? const MainNavigationShell()
              : const LoginScreen(),
        ),
      ),
    );
  }
}
