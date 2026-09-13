// lib/models/roboflow_inference.dart
//
// Client-side model of the backend POST /v1/inference/analyze response.
// Strict parsing: malformed envelopes throw FormatException instead of
// producing invented detections.
import 'detection_model.dart';
import '../ml/model_contract.dart';

/// One normalized prediction returned by the backend inference adapter.
/// Coordinates are top-left pixels in the submitted image space.
class NormalizedPredictionItem {
  final double x;
  final double y;
  final double width;
  final double height;
  final String roboflowClass;
  final int? classId;
  final double confidence;
  final String? detectionId;
  final OnionDefectType defectType;
  final bool qualityMapped;

  NormalizedPredictionItem({
    required this.x,
    required this.y,
    required this.width,
    required this.height,
    required this.roboflowClass,
    this.classId,
    required this.confidence,
    this.detectionId,
    required this.defectType,
    required this.qualityMapped,
  });

  factory NormalizedPredictionItem.fromJson(Map<String, dynamic> json) {
    final x = (json['x'] as num?)?.toDouble();
    final y = (json['y'] as num?)?.toDouble();
    final width = (json['width'] as num?)?.toDouble();
    final height = (json['height'] as num?)?.toDouble();
    final rawClass = json['roboflow_class'] as String?;
    final confidence = (json['confidence'] as num?)?.toDouble();
    if (x == null ||
        y == null ||
        width == null ||
        height == null ||
        rawClass == null ||
        confidence == null) {
      throw const FormatException('Malformed normalized prediction.');
    }
    if (width <= 0 || height <= 0) {
      throw const FormatException('Prediction has non-positive dimensions.');
    }
    if (confidence < 0.0 || confidence > 1.0) {
      throw const FormatException('Prediction confidence outside [0, 1].');
    }
    return NormalizedPredictionItem(
      x: x,
      y: y,
      width: width,
      height: height,
      roboflowClass: rawClass,
      classId: (json['class_id'] as num?)?.toInt(),
      confidence: confidence,
      detectionId: json['detection_id'] as String?,
      defectType: ModelContract.defectTypeForRoboflowClass(rawClass),
      qualityMapped: ModelContract.isQualityClass(rawClass),
    );
  }
}

/// Full backend inference response for one image.
class RoboflowInferenceResult {
  final String modelId;
  final int imageWidth;
  final int imageHeight;
  final List<NormalizedPredictionItem> predictions;
  final List<String> observedClasses;
  final bool qualityClassificationAvailable;
  final int droppedInvalidPredictions;

  RoboflowInferenceResult({
    required this.modelId,
    required this.imageWidth,
    required this.imageHeight,
    required this.predictions,
    required this.observedClasses,
    required this.qualityClassificationAvailable,
    required this.droppedInvalidPredictions,
  });

  factory RoboflowInferenceResult.fromJson(Map<String, dynamic> json) {
    final preds = json['predictions'];
    if (preds is! List) {
      throw const FormatException('Inference response missing predictions array.');
    }
    return RoboflowInferenceResult(
      modelId: json['model_id'] as String? ?? 'unknown',
      imageWidth: (json['image_width'] as num?)?.toInt() ?? 0,
      imageHeight: (json['image_height'] as num?)?.toInt() ?? 0,
      predictions: preds
          .map((p) => NormalizedPredictionItem.fromJson(
              Map<String, dynamic>.from(p as Map)))
          .toList(),
      observedClasses: ((json['observed_classes'] as List?) ?? [])
          .map((e) => e.toString())
          .toList(),
      qualityClassificationAvailable:
          json['quality_classification_available'] as bool? ?? false,
      droppedInvalidPredictions:
          (json['dropped_invalid_predictions'] as num?)?.toInt() ?? 0,
    );
  }
}
