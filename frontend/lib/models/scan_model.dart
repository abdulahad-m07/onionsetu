// lib/models/scan_model.dart
import 'detection_model.dart';
import 'grading_result.dart';
import 'batch_assessment.dart';

enum ScanSyncStatus {
  pendingOffline,
  uploading,
  synced,
  failed,
}

/// Truthful AI inference lifecycle for cloud (Roboflow hosted) inference.
/// A scan is NEVER marked completed unless the backend inference endpoint
/// was called successfully and returned validated predictions.
enum AiInferenceStatus {
  /// Captured + quality-passed, stored locally, awaiting connectivity/inference.
  pendingAi,
  /// Inference request in flight.
  processing,
  /// Validated predictions received and graded.
  completed,
  /// Inference failed (network/API/timeout); safe to retry.
  failed,
  /// Predictions received but need a human (low confidence or
  /// quality classes unavailable from the current model).
  humanReviewRequired,
}

enum SamplingAngle {
  topView,
  sideView,
  spreadView,
}

class CapturedImageEvidence {
  final String id;
  final String localPath;
  final String? remoteStorageUrl;
  final SamplingAngle angle;
  final double? sharpnessScore;
  final double? brightnessScore;
  final bool qualityPassed;
  final DateTime capturedAt;

  CapturedImageEvidence({
    required this.id,
    required this.localPath,
    this.remoteStorageUrl,
    required this.angle,
    this.sharpnessScore,
    this.brightnessScore,
    this.qualityPassed = true,
    DateTime? capturedAt,
  }) : capturedAt = capturedAt ?? DateTime.now();

  Map<String, dynamic> toJson() => {
    'id': id,
    'local_path': localPath,
    'remote_storage_url': remoteStorageUrl,
    'angle': angle.name,
    'sharpness_score': sharpnessScore,
    'brightness_score': brightnessScore,
    'quality_passed': qualityPassed,
    'captured_at': capturedAt.toIso8601String(),
  };

  factory CapturedImageEvidence.fromJson(Map<String, dynamic> json) {
    return CapturedImageEvidence(
      id: json['id'] as String,
      localPath: json['local_path'] as String,
      remoteStorageUrl: json['remote_storage_url'] as String?,
      angle: SamplingAngle.values.firstWhere(
        (e) => e.name == json['angle'],
        orElse: () => SamplingAngle.topView,
      ),
      sharpnessScore: (json['sharpness_score'] as num?)?.toDouble(),
      brightnessScore: (json['brightness_score'] as num?)?.toDouble(),
      qualityPassed: json['quality_passed'] as bool? ?? true,
      capturedAt: DateTime.parse(json['captured_at'] as String),
    );
  }
}

class ScanSession {
  final String id;
  final String lotNumber;
  final String farmerName;
  final String farmerPhone;
  final String procurementCenterId;
  final String graderId;
  /// Grader-declared physical batch size (100-200 onions). This user-entered
  /// count is the ONLY denominator for URS% — per-view detection tallies are
  /// never summed as unique onions. Required before batch assessment.
  final int? assessedOnions;
  final List<CapturedImageEvidence> images;
  final List<DetectionItem> detections;
  final GradingResult? result;
  /// Batch-level A/B/C/Reject outcome (the ONE final product grade).
  /// Null while the batch assessment is pending/failed — never fabricated.
  final BatchAssessmentResult? batchAssessment;
  final ScanSyncStatus syncStatus;
  final AiInferenceStatus aiStatus;
  final String? reportUrl;
  final String? auditHash;
  final DateTime createdAt;

  ScanSession({
    required this.id,
    required this.lotNumber,
    required this.farmerName,
    required this.farmerPhone,
    required this.procurementCenterId,
    required this.graderId,
    this.assessedOnions,
    this.images = const [],
    this.detections = const [],
    this.result,
    this.batchAssessment,
    this.syncStatus = ScanSyncStatus.pendingOffline,
    this.aiStatus = AiInferenceStatus.pendingAi,
    this.reportUrl,
    this.auditHash,
    DateTime? createdAt,
  }) : createdAt = createdAt ?? DateTime.now();

  ScanSession copyWith({
    String? id,
    String? lotNumber,
    String? farmerName,
    String? farmerPhone,
    String? procurementCenterId,
    String? graderId,
    int? assessedOnions,
    List<CapturedImageEvidence>? images,
    List<DetectionItem>? detections,
    GradingResult? result,
    BatchAssessmentResult? batchAssessment,
    ScanSyncStatus? syncStatus,
    AiInferenceStatus? aiStatus,
    String? reportUrl,
    String? auditHash,
    DateTime? createdAt,
  }) {
    return ScanSession(
      id: id ?? this.id,
      lotNumber: lotNumber ?? this.lotNumber,
      farmerName: farmerName ?? this.farmerName,
      farmerPhone: farmerPhone ?? this.farmerPhone,
        procurementCenterId: procurementCenterId ?? this.procurementCenterId,
        graderId: graderId ?? this.graderId,
        assessedOnions: assessedOnions ?? this.assessedOnions,
      images: images ?? this.images,
      detections: detections ?? this.detections,
      result: result ?? this.result,
      batchAssessment: batchAssessment ?? this.batchAssessment,
      syncStatus: syncStatus ?? this.syncStatus,
      aiStatus: aiStatus ?? this.aiStatus,
      reportUrl: reportUrl ?? this.reportUrl,
      auditHash: auditHash ?? this.auditHash,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'lot_number': lotNumber,
    'farmer_name': farmerName,
    'farmer_phone': farmerPhone,
    'procurement_center_id': procurementCenterId,
    'grader_id': graderId,
    'assessed_onions': assessedOnions,
    'images': images.map((i) => i.toJson()).toList(),
    'detections': detections.map((d) => d.toJson()).toList(),
    'result': result?.toJson(),
    'batch_assessment': batchAssessment?.toJson(),
    'sync_status': syncStatus.name,
    'ai_status': aiStatus.name,
    'report_url': reportUrl,
    'audit_hash': auditHash,
    'created_at': createdAt.toIso8601String(),
  };

  factory ScanSession.fromJson(Map<String, dynamic> json) {
    return ScanSession(
      id: json['id'] as String,
      lotNumber: json['lot_number'] as String,
      farmerName: json['farmer_name'] as String,
      farmerPhone: json['farmer_phone'] as String,
      procurementCenterId: json['procurement_center_id'] as String,
      graderId: json['grader_id'] as String,
      assessedOnions: (json['assessed_onions'] as num?)?.toInt(),
      images: (json['images'] as List<dynamic>?)
              ?.map((i) => CapturedImageEvidence.fromJson(i as Map<String, dynamic>))
              .toList() ??
          [],
      detections: (json['detections'] as List<dynamic>?)
              ?.map((d) => DetectionItem.fromJson(d as Map<String, dynamic>))
              .toList() ??
          [],
      result: json['result'] != null
          ? GradingResult.fromJson(json['result'] as Map<String, dynamic>)
          : null,
      batchAssessment: json['batch_assessment'] != null
          ? BatchAssessmentResult.fromJson(
              Map<String, dynamic>.from(json['batch_assessment'] as Map))
          : null,
      syncStatus: ScanSyncStatus.values.firstWhere(
        (s) => s.name == json['sync_status'],
        orElse: () => ScanSyncStatus.pendingOffline,
      ),
      aiStatus: AiInferenceStatus.values.firstWhere(
        (s) => s.name == json['ai_status'],
        orElse: () => AiInferenceStatus.pendingAi,
      ),
      reportUrl: json['report_url'] as String?,
      auditHash: json['audit_hash'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}
