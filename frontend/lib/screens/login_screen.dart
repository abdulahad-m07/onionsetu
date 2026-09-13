// lib/screens/login_screen.dart
//
// Grader sign-in against the deployed OnionSetu backend over OTP.
// Two steps (request OTP -> verify OTP) using AuthProvider, which talks to
// POST /v1/auth/send-otp and POST /v1/auth/verify-otp. Failures surface the
// provider message; a session is never fabricated.
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/user_model.dart';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';
import 'main_navigation_shell.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _phoneController = TextEditingController(text: '+91 ');
  final _nameController = TextEditingController();
  final _otpController = TextEditingController();
  UserRole _role = UserRole.grader;
  bool _otpSent = false;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    return Scaffold(
      appBar: AppBar(title: const Text('OnionSetu Login')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.primaryAmber.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                      color: AppTheme.primaryAmber.withOpacity(0.3)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.verified_user_outlined,
                        color: AppTheme.primaryAmber),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Sign in with your registered mobile number. An OTP verifies you against the APMC backend.',
                        style: TextStyle(
                            fontSize: 12, color: AppTheme.textPrimary),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              TextFormField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                enabled: !_otpSent,
                decoration: const InputDecoration(
                  labelText: 'Mobile Number *',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.phone_outlined),
                ),
                validator: (val) => val == null || val.trim().length < 10
                    ? 'Enter a valid mobile number'
                    : null,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _nameController,
                enabled: !_otpSent,
                decoration: const InputDecoration(
                  labelText: 'Full Name',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.person_outline),
                ),
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<UserRole>(
                value: _role,
                decoration: const InputDecoration(
                  labelText: 'Role',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.badge_outlined),
                ),
                items: UserRole.values
                    .map((r) => DropdownMenuItem(
                          value: r,
                          child: Text(r.name.toUpperCase()),
                        ))
                    .toList(),
                onChanged: _otpSent
                    ? null
                    : (val) => setState(() => _role = val ?? _role),
              ),
              if (_otpSent) ...[
                const SizedBox(height: 16),
                TextFormField(
                  controller: _otpController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'OTP Code *',
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.lock_outline),
                  ),
                  validator: (val) => val == null || val.trim().isEmpty
                      ? 'Enter the OTP code'
                      : null,
                ),
              ],
              if (auth.errorMessage != null) ...[
                const SizedBox(height: 12),
                Text(
                  auth.errorMessage!,
                  style: const TextStyle(color: AppTheme.defectRed),
                ),
              ],
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: auth.isLoading
                    ? null
                    : () async {
                        final provider = context.read<AuthProvider>();
                        if (!_formKey.currentState!.validate()) return;
                        if (!_otpSent) {
                          final ok = await provider.sendOtp(
                            _phoneController.text.trim(),
                          );
                          if (ok && mounted) {
                            setState(() => _otpSent = true);
                          }
                        } else {
                          final ok = await provider.verifyOtp(
                            _phoneController.text.trim(),
                            _otpController.text.trim(),
                            _role,
                            _nameController.text.trim(),
                          );
                          if (ok && mounted) {
                            Navigator.pushReplacement(
                              context,
                              MaterialPageRoute(
                                  builder: (_) =>
                                      const MainNavigationShell()),
                            );
                          }
                        }
                      },
                icon: auth.isLoading
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Icon(_otpSent
                        ? Icons.login_outlined
                        : Icons.sms_outlined),
                label: Text(auth.isLoading
                    ? 'Please wait...'
                    : (_otpSent ? 'Verify OTP & Login' : 'Send OTP')),
              ),
              if (_otpSent)
                TextButton(
                  onPressed: auth.isLoading
                      ? null
                      : () => setState(() {
                            _otpSent = false;
                            _otpController.clear();
                          }),
                  child: const Text('Change number / resend OTP'),
                ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _phoneController.dispose();
    _nameController.dispose();
    _otpController.dispose();
    super.dispose();
  }
}
