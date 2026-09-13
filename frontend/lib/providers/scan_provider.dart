// lib/providers/scan_provider.dart
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import 'package:path_provider/path_provider.dart';
import '../models/scan_model.dart';
import '../models/detection_model.dart';
import '../models/grading_result.dart';
import '../models/batch_assessment.dart';
import '../ml/image_quality_checker.dart';
import '../ml/model_contract.dart';
import '../services/api_service.dart';
import '../services/grading_engine.dart';
import '../db/scan_database.dart';

class ScanProvider extends ChangeNotifier {
  /// Multi-view batch capture contract: every batch is photographed from
  /// several angles (the SAME physical batch — views are not new onions).
  /// At least [minBatchViews] views are required for a representative
  /// assessment; the set is capped at [maxBatchViews] (backend limit).
  static const int minBatchViews = 10;
  static const int maxBatchViews = 15;

  final GradingEngine _gradingEngine = const GradingEngine();
  final ScanDatabase _database = ScanDatabase.instance;
  ApiService _apiService = ApiService();

  /// Overridable for tests / environments with a custom backend client.
  // ignore: unnecessary_setters
  set apiService(ApiService service) => _apiService = service;

  ScanSession? _currentSession;
  bool _isProcessing = false;
  String? _statusMessage;
  ImageQualityResult? _lastQualityResult;
  String? _lastCapturedImagePath;

  ScanSession? get currentSession => _currentSession;
  bool get isProcessing => _isProcessing;
  String? get statusMessage => _statusMessage;
  ImageQualityResult? get lastQualityResult => _lastQualityResult;
  String? get lastCapturedImagePath => _lastCapturedImagePath;

  /// Number of quality-passed views captured in the active session.
  int get viewsCaptured => _currentSession?.images.length ?? 0;

  /// True once enough views exist to request a batch assessment.
  bool get canFinishBatchCapture => viewsCaptured >= minBatchViews;

  /// True when the view set is full (no more captures accepted).
  bool get batchCaptureFull => viewsCaptured >= maxBatchViews;

  /// Suggested angle for the next capture: cycles top/side/spread so the
  /// multi-view set keeps covering fresh perspectives of the same batch.
  SamplingAngle get nextAngle =>
      SamplingAngle.values[viewsCaptured % SamplingAngle.values.length];

  void startNewSession({
    required String lotNumber,
    required String farmerName,
    required String farmerPhone,
    required String procurementCenterId,
    required String graderId,
    required int assessedOnions,
  }) {
    if (assessedOnions < 100 || assessedOnions > 200) {
      throw ArgumentError(
        'assessedOnions must be between 100 and 200 (got $assessedOnions).',
      );
    }
    final newId = const Uuid().v4();
    _currentSession = ScanSession(
      id: newId,
      lotNumber: lotNumber,
      farmerName: farmerName,
      farmerPhone: farmerPhone,
      procurementCenterId: procurementCenterId,
      graderId: graderId,
      assessedOnions: assessedOnions,
      images: [],
      detections: [],
      syncStatus: ScanSyncStatus.pendingOffline,
      aiStatus: AiInferenceStatus.pendingAi,
    );
    _lastQualityResult = null;
    _lastCapturedImagePath = null;
    notifyListeners();
  }

  /// Captures one view: quality validation -> local persistence.
  /// Cloud (Roboflow) inference requires connectivity, so NO AI runs here:
  /// the session stays [AiInferenceStatus.pendingAi] until
  /// [requestAiAnalysis] succeeds. Works fully offline.
  Future<bool> processCapturedImage(Uint8List imageBytes, SamplingAngle angle) async {
    if (_currentSession == null) return false;
    if (_currentSession!.images.length >= maxBatchViews) {
      _statusMessage =
          'View set is full ($maxBatchViews views). Finish capture to grade the batch.';
      notifyListeners();
      return false;
    }

    _isProcessing = true;
    _statusMessage = 'Checking image quality...';
    notifyListeners();

    // 1. Image Quality Validation Gate (on-device, OpenCV-style heuristics)
    final quality = ImageQualityChecker.validateImageBytes(imageBytes);
    _lastQualityResult = quality;

    if (!quality.isValid) {
      _isProcessing = false;
      _statusMessage = quality.rejectionReason ?? 'Image quality validation failed.';
      notifyListeners();
      return false; // Quality gate rejected
    }

    _statusMessage = 'Saving capture locally...';
    notifyListeners();

    // 2. Persist Image to Local Storage (offline-first)
    final dir = await getApplicationDocumentsDirectory();
    final imageId = const Uuid().v4();
    final filePath = '${dir.path}/scan_${_currentSession!.id}_${angle.name}_$imageId.jpg';
    final file = File(filePath);
    await file.writeAsBytes(imageBytes);
    _lastCapturedImagePath = filePath;

    // 3. Record evidence; AI inference happens later via requestAiAnalysis.
    final evidence = CapturedImageEvidence(
      id: imageId,
      localPath: filePath,
      angle: angle,
      sharpnessScore: quality.sharpnessScore,
      brightnessScore: quality.brightnessScore,
      qualityPassed: true,
    );

    final updatedImages = List<CapturedImageEvidence>.from(_currentSession!.images)..add(evidence);

    _currentSession = _currentSession!.copyWith(
      images: updatedImages,
      aiStatus: AiInferenceStatus.pendingAi,
    );

    _isProcessing = false;
    _statusMessage = null;
    notifyListeners();
    return true;
  }

  /// Runs server-side Roboflow inference for every captured image and grades
  /// the session from VALIDATED predictions only. Requires connectivity.
  ///
  /// Multi-view limitation (documented): detections from the Top/Side/Spread
  /// views are unioned — the same physical onion may appear in multiple
  /// views. No cross-view identity matching is implemented; counts may
  /// double-count onions visible in more than one view.
  ///
  /// Returns true only when the backend was reached and validated
  /// predictions were graded. Any failure leaves aiStatus=failed with
  /// existing local data intact (safe to retry when online).
  Future<bool> requestAiAnalysis({required String token}) async {
    final session = _currentSession;
    if (session == null || session.images.isEmpty) return false;

    _isProcessing = true;
    _statusMessage = 'Contacting AI service...';
    _currentSession = session.copyWith(aiStatus: AiInferenceStatus.processing);
    notifyListeners();

    try {
      final List<DetectionItem> allDetections = [];
      var index = 0;
      for (final evidence in session.images) {
        index++;
        _statusMessage = 'Analyzing photo $index of ${session.images.length}...';
        notifyListeners();

        final bytes = await File(evidence.localPath).readAsBytes();
        final inference = await _apiService.analyzeImage(
          imageBytes: bytes,
          filename: 'scan_${session.id}_${evidence.angle.name}.jpg',
          token: token,
        );

        for (final pred in inference.predictions) {
          allDetections.add(
            ModelContract.detectionFromPrediction(
              x: pred.x,
              y: pred.y,
              width: pred.width,
              height: pred.height,
              roboflowClass: pred.roboflowClass,
              confidence: pred.confidence,
              viewAngle: evidence.angle.name,
            ),
          );
        }
      }

      final gradingResult = _gradingEngine.calculateGrading(
        scanId: session.id,
        detections: allDetections,
      );

      final AiInferenceStatus finalStatus =
          gradingResult.confidenceStatus == ConfidenceGateStatus.highConfidence
              ? AiInferenceStatus.completed
              : AiInferenceStatus.humanReviewRequired;

      _currentSession = _currentSession!.copyWith(
        detections: allDetections,
        result: gradingResult,
        auditHash: gradingResult.auditHash,
        aiStatus: finalStatus,
      );
      await _database.saveScan(_currentSession!);

      _isProcessing = false;
      _statusMessage = null;
      notifyListeners();
      return true;
    } catch (_) {
      _currentSession = _currentSession?.copyWith(
        aiStatus: AiInferenceStatus.failed,
      );
      if (_currentSession != null) {
        try {
          await _database.saveScan(_currentSession!);
        } catch (_) {
          // Local persistence failure must not mask the inference error.
        }
      }
      _isProcessing = false;
      _statusMessage = 'AI analysis failed. Check connectivity and retry.';
      notifyListeners();
      return false;
    }
  }

  BatchAssessmentResult? get batchAssessment => _currentSession?.batchAssessment;

  /// Runs the server-side batch pipeline (Roboflow detection + provider batch
  /// assessment + deterministic A/B/C/Reject policy) over the captured
  /// representative views. Requires connectivity AND the grader-declared
  /// batch size recorded at session start (the ONLY URS% denominator).
  ///
  /// Returns true only when the backend returned a validated batch result.
  /// Offline/provider/Roboflow failures leave aiStatus=failed with all local
  /// captures and evidence intact (safe to retry). Never fabricates a grade.
  Future<bool> requestBatchAssessment({required String token}) async {
    final session = _currentSession;
    if (session == null || session.images.isEmpty) return false;
    final declared = session.assessedOnions;
    if (declared == null) {
      _statusMessage =
          'Batch size not recorded. Restart the session and enter the onion count (100-200).';
      notifyListeners();
      return false;
    }

    _isProcessing = true;
    _statusMessage = 'Running batch assessment...';
    _currentSession = session.copyWith(aiStatus: AiInferenceStatus.processing);
    notifyListeners();

    try {
      final imageBytes = <Uint8List>[];
      final filenames = <String>[];
      for (final evidence in session.images) {
        imageBytes.add(await File(evidence.localPath).readAsBytes());
        filenames.add('scan_${session.id}_${evidence.angle.name}.jpg');
      }

      final batch = await _apiService.requestBatchAssessment(
        imageBytes: imageBytes,
        filenames: filenames,
        token: token,
        assessedOnions: declared,
        scanId: session.id,
      );

      _currentSession = _currentSession!.copyWith(
        batchAssessment: batch,
        aiStatus: batch.reviewRequired
            ? AiInferenceStatus.humanReviewRequired
            : AiInferenceStatus.completed,
      );
      await _database.saveScan(_currentSession!);

      _isProcessing = false;
      _statusMessage = null;
      notifyListeners();
      return true;
    } catch (_) {
      _currentSession = _currentSession?.copyWith(
        aiStatus: AiInferenceStatus.failed,
      );
      if (_currentSession != null) {
        try {
          await _database.saveScan(_currentSession!);
        } catch (_) {
          // Local persistence failure must not mask the batch error.
        }
      }
      _isProcessing = false;
      _statusMessage = 'Batch assessment failed. Check connectivity and retry.';
      notifyListeners();
      return false;
    }
  }

  /// Saves the complete scan session to SQLite local persistence
  Future<void> saveCurrentScanLocally() async {
    if (_currentSession == null) return;
    _isProcessing = true;
    _statusMessage = 'Saving scan to local storage...';
    notifyListeners();

    await _database.saveScan(_currentSession!);

    _isProcessing = false;
    _statusMessage = null;
    notifyListeners();
  }

  void resetSession() {
    _currentSession = null;
    _lastQualityResult = null;
    _lastCapturedImagePath = null;
    _isProcessing = false;
    _statusMessage = null;
    notifyListeners();
  }
}
