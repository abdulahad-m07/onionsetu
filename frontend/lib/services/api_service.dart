// lib/services/api_service.dart
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import '../config/environment.dart';
import '../models/scan_model.dart';
import '../models/dispute_model.dart';
import '../models/roboflow_inference.dart';
import '../models/batch_assessment.dart';

/// Thrown for transport-level inference failures (network/timeout/5xx)
/// that are safe to retry. HTTP 4xx and malformed bodies are NOT retried.
class RetryableInferenceException implements Exception {
  final String message;
  const RetryableInferenceException(this.message);
  @override
  String toString() => 'RetryableInferenceException: $message';
}

class ApiService {
  final String baseUrl;
  final http.Client _client;
  final int maxInferenceAttempts;

  ApiService({String? baseUrl, http.Client? client, int? maxInferenceAttempts})
      : baseUrl = baseUrl ?? EnvironmentConfig.apiBaseUrl,
        _client = client ?? http.Client(),
        maxInferenceAttempts =
            maxInferenceAttempts ?? EnvironmentConfig.maxRetryAttempts;

  Map<String, String> _headers(String? token) => {
    'Content-Type': 'application/json',
    if (token != null) 'Authorization': 'Bearer $token',
  };

  Future<bool> sendOtp(String phone) async {
    final response = await _client.post(
      Uri.parse('$baseUrl/auth/send-otp'),
      headers: _headers(null),
      body: jsonEncode({'phone': phone}),
    );
    return response.statusCode == 200;
  }

  Future<Map<String, dynamic>> verifyOtp({
    required String phone,
    required String otp,
    required String role,
    String? name,
  }) async {
    final response = await _client.post(
      Uri.parse('$baseUrl/auth/verify-otp'),
      headers: _headers(null),
      body: jsonEncode({
        'phone': phone,
        'otp': otp,
        'role': role,
        'name': name ?? 'Farmer',
      }),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } else {
      throw Exception('OTP verification failed: ${response.body}');
    }
  }

  Future<bool> submitScan(ScanSession scan, String token) async {
    final response = await _client.post(
      Uri.parse('$baseUrl/scans/'),
      headers: _headers(token),
      body: jsonEncode(scan.toJson()),
    );
    return response.statusCode == 201 || response.statusCode == 200;
  }

  Future<Map<String, dynamic>> syncBatch(String deviceId, List<ScanSession> scans, String token) async {
    final response = await _client.post(
      Uri.parse('$baseUrl/sync/batch'),
      headers: _headers(token),
      body: jsonEncode({
        'client_device_id': deviceId,
        'scans': scans.map((s) => s.toJson()).toList(),
      }),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } else {
      throw Exception('Batch sync failed: ${response.body}');
    }
  }

  Future<bool> fileDispute(DisputeRecord dispute, String token) async {
    final response = await _client.post(
      Uri.parse('$baseUrl/disputes/'),
      headers: _headers(token),
      body: jsonEncode({
        'scan_id': dispute.scanId,
        'reason': dispute.reason,
        'evidence_urls': dispute.evidenceUrls,
      }),
    );
    return response.statusCode == 201;
  }

  Future<Map<String, dynamic>> verifyAuditChain(String token) async {
    final response = await _client.get(
      Uri.parse('$baseUrl/audit/verify'),
      headers: _headers(token),
    );
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  /// Sends one captured image to the backend Roboflow inference adapter
  /// (POST /v1/inference/analyze) and returns validated predictions.
  ///
  /// The Roboflow API key lives server-side; only the user's JWT is sent.
  /// Retries transport failures/5xx up to [maxInferenceAttempts]; 4xx and
  /// malformed bodies throw immediately (retrying cannot help).
  Future<RoboflowInferenceResult> analyzeImage({
    required Uint8List imageBytes,
    required String filename,
    required String token,
  }) async {
    Object? lastError;
    for (var attempt = 1; attempt <= maxInferenceAttempts; attempt++) {
      try {
        final request = http.MultipartRequest(
          'POST',
          Uri.parse('$baseUrl/inference/analyze'),
        );
        request.headers['Authorization'] = 'Bearer $token';
        request.files.add(http.MultipartFile.fromBytes(
          'image',
          imageBytes,
          filename: filename,
        ));
        final streamed = await _client.send(request).timeout(
              const Duration(seconds: 60),
            );
        final response = await http.Response.fromStream(streamed);

        if (response.statusCode == 200) {
          final Map<String, dynamic> body =
              Map<String, dynamic>.from(jsonDecode(response.body) as Map);
          return RoboflowInferenceResult.fromJson(body);
        }
        if (response.statusCode >= 500 || response.statusCode == 408) {
          lastError = RetryableInferenceException(
            'Inference server error HTTP ${response.statusCode} '
            '(attempt $attempt/$maxInferenceAttempts).',
          );
          continue;
        }
        throw Exception(
          'AI inference rejected (HTTP ${response.statusCode}): ${response.body}',
        );
      } on FormatException {
        rethrow; // Malformed contract body: never retry, never invent.
      } on TimeoutException catch (e) {
        lastError = RetryableInferenceException('Inference timed out: $e');
      } on http.ClientException catch (e) {
        lastError = RetryableInferenceException('Inference transport failed: $e');
      }
    }
    throw lastError ?? const RetryableInferenceException('Inference failed.');
  }

  /// Sends representative batch images to the backend batch pipeline
  /// (POST /v1/inference/batch-assess: Roboflow detection + provider batch
  /// assessment + deterministic A/B/C/Reject policy) and returns the ONE
  /// validated final grade. The grader-declared physical batch size
  /// (100-200) travels as `assessed_onions`: the backend requires it as the
  /// ONLY URS% denominator and rejects the request otherwise. Provider keys
  /// stay server-side; only the JWT is sent. Same retry contract as
  /// [analyzeImage]: transport/5xx retried,
  /// 4xx and malformed bodies throw immediately.
  Future<BatchAssessmentResult> requestBatchAssessment({
    required List<Uint8List> imageBytes,
    required List<String> filenames,
    required String token,
    required int assessedOnions,
    String? scanId,
  }) async {
    if (imageBytes.isEmpty || imageBytes.length != filenames.length) {
      throw ArgumentError('imageBytes and filenames must be non-empty and aligned.');
    }
    Object? lastError;
    for (var attempt = 1; attempt <= maxInferenceAttempts; attempt++) {
      try {
        final request = http.MultipartRequest(
          'POST',
          Uri.parse('$baseUrl/inference/batch-assess'),
        );
        request.headers['Authorization'] = 'Bearer $token';
        if (scanId != null) request.fields['scan_id'] = scanId;
        request.fields['assessed_onions'] = assessedOnions.toString();
        for (var i = 0; i < imageBytes.length; i++) {
          request.files.add(http.MultipartFile.fromBytes(
            'images',
            imageBytes[i],
            filename: filenames[i],
          ));
        }
        final streamed = await _client.send(request).timeout(
              const Duration(seconds: 120),
            );
        final response = await http.Response.fromStream(streamed);

        if (response.statusCode == 200) {
          final Map<String, dynamic> body =
              Map<String, dynamic>.from(jsonDecode(response.body) as Map);
          return BatchAssessmentResult.fromJson(body);
        }
        if (response.statusCode >= 500 || response.statusCode == 408) {
          lastError = RetryableInferenceException(
            'Batch assessment server error HTTP ${response.statusCode} '
            '(attempt $attempt/$maxInferenceAttempts).',
          );
          continue;
        }
        throw Exception(
          'Batch assessment rejected (HTTP ${response.statusCode}): ${response.body}',
        );
      } on FormatException {
        rethrow; // Malformed contract body: never retry, never invent.
      } on TimeoutException catch (e) {
        lastError = RetryableInferenceException('Batch assessment timed out: $e');
      } on http.ClientException catch (e) {
        lastError =
            RetryableInferenceException('Batch assessment transport failed: $e');
      }
    }
    throw lastError ?? const RetryableInferenceException('Batch assessment failed.');
  }
}
