// lib/ml/model_contract.dart
//
// ROBOFLOW VISION CONTRACT (no inference runs on-device).
//
// AI layer: ONE hosted Roboflow vision model, called server-side through
// FastAPI POST /v1/inference/analyze. The Flutter app NEVER holds the
// Roboflow API key and NEVER runs TFLite models. The retired on-device
// YOLOv8/MobileNetV2 pipeline must not be reintroduced here.
//
// This file holds pure constants and mapping helpers for the normalized
// prediction schema. It performs NO detection, NO classification, and
// produces NO confidence values.
//
// Model truth (verified 2026-09-13): model onion-yhzc7-mo9ib/1 is live on
// Roboflow Serverless, but its class list is undiscovered (no API key
// available at migration time). Labels outside the quality map below pass
// through as OnionDefectType.unknown with quality classification flagged
// unavailable — never converted into gradeA or any other invented class.
// Full specification: docs/MODEL_INTEGRATION_SPEC.md
import 'package:uuid/uuid.dart';
import '../models/detection_model.dart';
import 'size_estimator.dart';

/// Thrown when production code attempts retired on-device inference.
class RetiredInferenceException implements Exception {
  final String message;
  const RetiredInferenceException(this.message);

  @override
  String toString() => 'RetiredInferenceException: $message';
}

/// Pure contract for the Roboflow hosted vision layer.
class ModelContract {
  /// Roboflow model id served by the backend (informational on-device only;
  /// the backend owns the configured value — see ROBOFLOW_MODEL_ID).
  static const String roboflowModelId = 'onion-yhzc7-mo9ib/1';

  /// Minimum model confidence surfaced to grading (must match backend
  /// ROBOFLOW_MIN_CONFIDENCE=45, expressed here as 0..1).
  static const double minConfidence = 0.45;

  /// NMS IoU limit applied server-side (matches ROBOFLOW_OVERLAP=30).
  static const double nmsIouThreshold = 0.30;

  /// Raw Roboflow label (lowercased, trimmed) -> quality defect type.
  /// ONLY these labels count as quality classification. Any other model
  /// label (e.g. a generic "onion" detector class) is NOT mapped.
  static const Map<String, OnionDefectType> qualityClassMap = {
    'gradea': OnionDefectType.gradeA,
    'grade a': OnionDefectType.gradeA,
    'grade_a': OnionDefectType.gradeA,
    'healthy': OnionDefectType.gradeA,
    'damaged': OnionDefectType.damaged,
    'damage': OnionDefectType.damaged,
    'bruised': OnionDefectType.damaged,
    'rotten': OnionDefectType.rotten,
    'rot': OnionDefectType.rotten,
    'decay': OnionDefectType.rotten,
    'mold': OnionDefectType.rotten,
    'sprouted': OnionDefectType.sprouted,
    'sprout': OnionDefectType.sprouted,
    'undersized': OnionDefectType.undersized,
    'undersize': OnionDefectType.undersized,
    'small': OnionDefectType.undersized,
  };

  /// True only for labels that carry genuine quality information.
  static bool isQualityClass(String rawLabel) {
    return qualityClassMap.containsKey(rawLabel.trim().toLowerCase());
  }

  /// Maps a raw Roboflow class label to a defect type.
  /// Unknown labels -> OnionDefectType.unknown (honest, never invented).
  static OnionDefectType defectTypeForRoboflowClass(String rawLabel) {
    return qualityClassMap[rawLabel.trim().toLowerCase()] ??
        OnionDefectType.unknown;
  }

  /// Builds a [DetectionItem] from one validated backend prediction.
  /// Size comes from real box geometry via [OnionSizeEstimator]; when the
  /// camera setup cannot provide calibration, the mm value is an estimate
  /// (see docs/LIMITATIONS.md) — it is never a neural-network output.
  static DetectionItem detectionFromPrediction({
    required double x,
    required double y,
    required double width,
    required double height,
    required String roboflowClass,
    required double confidence,
    String? viewAngle,
    String? id,
  }) {
    final diameterMm = OnionSizeEstimator.estimateDiameterMm(
      boxWidthPx: width,
      boxHeightPx: height,
    );
    return DetectionItem(
      id: id ?? const Uuid().v4(),
      x: x,
      y: y,
      width: width,
      height: height,
      defectType: defectTypeForRoboflowClass(roboflowClass),
      confidence: confidence,
      estimatedDiameterMm: double.parse(diameterMm.toStringAsFixed(1)),
      viewAngle: viewAngle,
      rawLabel: roboflowClass,
    );
  }
}
