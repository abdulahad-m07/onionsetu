// lib/providers/auth_provider.dart
import 'package:flutter/material.dart';
import '../models/user_model.dart';

class AuthProvider extends ChangeNotifier {
  User? _currentUser;
  String? _authToken;
  bool _isLoading = false;
  String? _errorMessage;

  User? get currentUser => _currentUser;
  String? get authToken => _authToken;
  bool get isAuthenticated => _currentUser != null && _authToken != null;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  AuthProvider() {
    // Initialize default demo user for offline-first grader workflow
    _currentUser = User(
      id: 'grader_101',
      name: 'Ramesh Patil',
      phone: '+91 98765 43210',
      role: UserRole.grader,
      procurementCenterId: 'APMC-LASALGAON-01',
    );
    _authToken = 'mock_jwt_token_grader_101';
  }

  void setUser(User user, String token) {
    _currentUser = user;
    _authToken = token;
    notifyListeners();
  }

  Future<bool> sendOtp(String phone) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    await Future.delayed(const Duration(milliseconds: 600));
    _isLoading = false;
    notifyListeners();
    return true;
  }

  Future<bool> verifyOtp(String phone, String otp, UserRole role, String name) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    await Future.delayed(const Duration(milliseconds: 600));
    if (otp.length == 6 || otp == '123456') {
      _currentUser = User(
        id: 'user_${DateTime.now().millisecondsSinceEpoch}',
        name: name.isNotEmpty ? name : 'Verified User',
        phone: phone,
        role: role,
        procurementCenterId: 'APMC-LASALGAON-01',
      );
      _authToken = 'jwt_session_${_currentUser!.id}';
      _isLoading = false;
      notifyListeners();
      return true;
    } else {
      _errorMessage = 'Invalid OTP code. Please try again.';
      _isLoading = false;
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
