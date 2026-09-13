// lib/ml/ml_inference_service.dart
//
// RETIRED on-device pipeline. The YOLOv8 + MobileNetV2 + TFLite design has
// been removed from the production path (see docs/MODEL_INTEGRATION_SPEC.md).
// Production inference is server-side: Flutter captures -> quality gate ->
// FastAPI POST /v1/inference/analyze (Roboflow hosted model) -> validated
// predictions -> grading engine.
//
// Retained here (still unit-tested, NOT part of the production AI path):
// - preprocessImage: legacy resize/normalize helper (kept for test compat).
// - applyNonMaxSuppression / calculateIoU: deterministic geometry helpers.
// Everything that previously generated grid detections, pixel-heuristic
// defect labels, or brightness-derived confidence has been DELETED, not
// replaced. Do NOT reintroduce fake inference in this file.
import 'dart:math';
import 'package:image/image.dart' as img;
import '../models/detection_model.dart';
import 'model_contract.dart';

class MLModelStatus {
  final bool isLoaded;
  final String? yoloModelName;
  final String? classifierModelName;
  final String? errorMessage;

  MLModelStatus({
    required this.isLoaded,
    this.yoloModelName,
    this.classifierModelName,
    this.errorMessage,
  });
}

class MLInferenceService {
  static const int inputWidth = 640;
  static const int inputHeight = 640;
  static const double defaultConfidenceThreshold = ModelContract.minConfidence;
  static const double iouNmsThreshold = 0.45;

  /// Always reports unavailable: there are no on-device production models.
  Future<MLModelStatus> initializeModels() async {
    return MLModelStatus(
      isLoaded: false,
      errorMessage:
          'On-device TFLite inference is retired. Use server-side Roboflow '
          'inference via POST /v1/inference/analyze.',
    );
  }

  /// Legacy helper retained for test compatibility. NOT used by production.
  static List<List<List<List<double>>>> preprocessImage(img.Image image) {
    final img.Image resized = img.copyResize(
      image,
      width: inputWidth,
      height: inputHeight,
      interpolation: img.Interpolation.linear,
    );

    final inputTensor = List.generate(
      1,
      (_) => List.generate(
        inputHeight,
        (y) => List.generate(
          inputWidth,
          (x) {
            final pixel = resized.getPixel(x, y);
            return [
              pixel.r / 255.0,
              pixel.g / 255.0,
              pixel.b / 255.0,
            ];
          },
        ),
      ),
    );

    return inputTensor;
  }

  /// Non-Maximum Suppression (NMS) to eliminate overlapping redundant bounding boxes
  static List<DetectionItem> applyNonMaxSuppression(
    List<DetectionItem> detections, {
    double iouThreshold = 0.45,
  }) {
    if (detections.isEmpty) return [];

    final sorted = List<DetectionItem>.from(detections)
      ..sort((a, b) => b.confidence.compareTo(a.confidence));

    final List<DetectionItem> kept = [];

    for (final candidate in sorted) {
      bool overlapFound = false;
      for (final selected in kept) {
        final iou = calculateIoU(candidate, selected);
        if (iou > iouThreshold) {
          overlapFound = true;
          break;
        }
      }
      if (!overlapFound) {
        kept.add(candidate);
      }
    }

    return kept;
  }

  static double calculateIoU(DetectionItem a, DetectionItem b) {
    final double x1 = max(a.x, b.x);
    final double y1 = max(a.y, b.y);
    final double x2 = min(a.x + a.width, b.x + b.width);
    final double y2 = min(a.y + a.height, b.y + b.height);

    final double interArea = max(0.0, x2 - x1) * max(0.0, y2 - y1);
    final double areaA = a.width * a.height;
    final double areaB = b.width * b.height;
    final double unionArea = areaA + areaB - interArea;

    if (unionArea <= 0) return 0.0;
    return interArea / unionArea;
  }
}
