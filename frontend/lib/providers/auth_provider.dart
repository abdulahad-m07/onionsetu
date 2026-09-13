// lib/providers/auth_provider.dart
//
// Production authentication against the deployed OnionSetu backend
// (POST /v1/auth/send-otp, POST /v1/auth/verify-otp). The provider starts
// logged OUT: no demo user and no mock token exist anywhere in this file,
// so no API call can succeed without a real backend-issued JWT.
// Transport failures and invalid OTPs return false with a user-safe
// message — never a fabricated session.
import 'package:flutter/material.dart';
import '../models/user_model.dart';
import '../services/api_service.dart';

class AuthProvider extends ChangeNotifier {
  ApiService _apiService;
  User? _currentUser;
  String? _authToken;
  bool _isLoading = false;
  String? _errorMessage;

  User? get currentUser => _currentUser;
  String? get authToken => _authToken;
  bool get isAuthenticated => _currentUser != null && _authToken != null;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  AuthProvider({ApiService? apiService})
      : _apiService = apiService ?? ApiService();

  /// Overridable for tests / environments with a custom backend client.
  // ignore: unnecessary_setters
  set apiService(ApiService service) => _apiService = service;

  void setUser(User user, String token) {
    _currentUser = user;
    _authToken = token;
    notifyListeners();
  }

  Future<bool> sendOtp(String phone) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final ok = await _apiService.sendOtp(phone);
      _isLoading = false;
      if (!ok) {
        _errorMessage =
            'Could not request OTP. Check connectivity and retry.';
      }
      notifyListeners();
      return ok;
    } catch (_) {
      _isLoading = false;
      _errorMessage =
          'Authentication service unreachable. Check connectivity and retry.';
      notifyListeners();
      return false;
    }
  }

  Future<bool> verifyOtp(
      String phone, String otp, UserRole role, String name) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final body = await _apiService.verifyOtp(
        phone: phone,
        otp: otp,
        role: role.name,
        name: name.isNotEmpty ? name : 'Verified User',
      );
      final token = body['access_token'] as String?;
      final userId = body['user_id'] as String?;
      if (token == null || token.isEmpty || userId == null || userId.isEmpty) {
        _errorMessage = 'Invalid OTP code. Please try again.';
        _isLoading = false;
        notifyListeners();
        return false;
      }
      _currentUser = User(
        id: userId,
        name: (body['name'] as String?)?.isNotEmpty == true
            ? body['name'] as String
            : (name.isNotEmpty ? name : 'Verified User'),
        phone: phone,
        role: UserRole.values.firstWhere(
          (r) => r.name == body['role'],
          orElse: () => role,
        ),
        procurementCenterId:
            body['procurement_center_id'] as String? ?? 'APMC-LASALGAON-01',
      );
      _authToken = token;
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _isLoading = false;
      final message = e.toString();
      _errorMessage = message.contains('Invalid or expired')
          ? 'Invalid OTP code. Please try again.'
          : 'Authentication service unreachable. Check connectivity and retry.';
      notifyListeners();
      return false;
    }
  }

  void logout() {
    _currentUser = null;
    _authToken = null;
    notifyListeners();
  }
}
