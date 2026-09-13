// test/ml_inference_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:frontend/ml/ml_inference_service.dart';
import 'package:frontend/models/detection_model.dart';

void main() {
  group('MLInferenceService Tests', () {
    test('Preprocesses image to [1, 640, 640, 3] float tensor', () {
      final image = img.Image(width: 800, height: 600);
      img.fill(image, color: img.ColorRgb8(255, 128, 0));

      final tensor = MLInferenceService.preprocessImage(image);

      expect(tensor.length, equals(1)); // Batch size 1
      expect(tensor[0].length, equals(640)); // Height 640
      expect(tensor[0][0].length, equals(640)); // Width 640
      expect(tensor[0][0][0].length, equals(3)); // Channels (R, G, B)
      expect(tensor[0][0][0][0], closeTo(1.0, 0.01)); // Red channel normalized
      expect(tensor[0][0][0][1], closeTo(0.5, 0.02)); // Green channel normalized
      expect(tensor[0][0][0][2], closeTo(0.0, 0.01)); // Blue channel normalized
    });

    test('Non-Maximum Suppression filters overlapping redundant bounding boxes', () {
      final item1 = DetectionItem(
        id: 'det_1',
        x: 100,
        y: 100,
        width: 80,
        height: 80,
        defectType: OnionDefectType.gradeA,
        confidence: 0.95,
      );

      // Overlapping item with lower confidence
      final item2 = DetectionItem(
        id: 'det_2',
        x: 105,
        y: 105,
        width: 80,
        height: 80,
        defectType: OnionDefectType.gradeA,
        confidence: 0.82,
      );

      // Distant non-overlapping item
      final item3 = DetectionItem(
        id: 'det_3',
        x: 300,
        y: 300,
        width: 80,
        height: 80,
        defectType: OnionDefectType.damaged,
        confidence: 0.90,
      );

      final nmsResult = MLInferenceService.applyNonMaxSuppression([item1, item2, item3], iouThreshold: 0.45);

      expect(nmsResult.length, equals(2));
      expect(nmsResult.map((e) => e.id), containsAll(['det_1', 'det_3']));
      expect(nmsResult.map((e) => e.id), isNot(contains('det_2')));
    });
  });
}
