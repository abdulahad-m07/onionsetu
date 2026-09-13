// test/image_quality_test.dart
import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;
import 'package:frontend/ml/image_quality_checker.dart';

void main() {
  group('Image Quality Validation Gate Tests', () {
    test('Valid sharp and well-lit image passes quality check', () {
      final image = img.Image(width: 400, height: 400);
      img.fill(image, color: img.ColorRgb8(180, 180, 180));
      // Add sharp gradient lines
      for (int i = 50; i < 350; i += 20) {
        img.drawLine(image, x1: i, y1: 50, x2: i, y2: 350, color: img.ColorRgb8(20, 20, 20));
      }

      final result = ImageQualityChecker.validateImage(image);
      expect(result.isValid, isTrue);
      expect(result.isSharp, isTrue);
      expect(result.isAdequatelyLit, isTrue);
      expect(result.isFramedWell, isTrue);
    });

    test('Dark / underexposed image is flagged with actionable feedback', () {
      final image = img.Image(width: 400, height: 400);
      img.fill(image, color: img.ColorRgb8(20, 20, 20)); // Below minBrightness (45)

      final result = ImageQualityChecker.validateImage(image);
      expect(result.isValid, isFalse);
      expect(result.isAdequatelyLit, isFalse);
      expect(result.rejectionReason, contains('dark'));
    });

    test('Blurry / low-contrast flat image is rejected for sharpness', () {
      final image = img.Image(width: 400, height: 400);
      img.fill(image, color: img.ColorRgb8(150, 150, 150)); // Zero gradient edges

      final result = ImageQualityChecker.validateImage(image);
      expect(result.isValid, isFalse);
      expect(result.isSharp, isFalse);
      expect(result.rejectionReason, contains('blurry'));
    });
  });
}
