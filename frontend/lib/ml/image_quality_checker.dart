// lib/ml/image_quality_checker.dart
import 'dart:typed_data';
import 'package:image/image.dart' as img;

class ImageQualityResult {
  final bool isSharp;
  final bool isAdequatelyLit;
  final bool isFramedWell;
  final double sharpnessScore; // Higher is sharper (> 15.0 is adequate)
  final double brightnessScore; // [0..255], optimal is 70..200
  final String? rejectionReason;

  bool get isValid => isSharp && isAdequatelyLit && isFramedWell;

  ImageQualityResult({
    required this.isSharp,
    required this.isAdequatelyLit,
    required this.isFramedWell,
    required this.sharpnessScore,
    required this.brightnessScore,
    this.rejectionReason,
  });
}

class ImageQualityChecker {
  static const double minSharpnessThreshold = 12.0;
  static const double minBrightness = 45.0;
  static const double maxBrightness = 230.0;

  /// Evaluates blur/sharpness, lighting, and framing from image bytes
  static ImageQualityResult validateImageBytes(Uint8List imageBytes) {
    final image = img.decodeImage(imageBytes);
    if (image == null) {
      return ImageQualityResult(
        isSharp: false,
        isAdequatelyLit: false,
        isFramedWell: false,
        sharpnessScore: 0.0,
        brightnessScore: 0.0,
        rejectionReason: 'Failed to decode image format.',
      );
    }

    return validateImage(image);
  }

  static ImageQualityResult validateImage(img.Image image) {
    // 1. Calculate Average Luminance / Brightness
    double totalLuminance = 0;
    int pixelCount = 0;
    
    // Sample every 4th pixel for high speed
    for (int y = 0; y < image.height; y += 4) {
      for (int x = 0; x < image.width; x += 4) {
        final pixel = image.getPixel(x, y);
        final lum = 0.299 * pixel.r + 0.587 * pixel.g + 0.114 * pixel.b;
        totalLuminance += lum;
        pixelCount++;
      }
    }

    final double avgBrightness = pixelCount > 0 ? (totalLuminance / pixelCount) : 0.0;
    final bool adequatelyLit = avgBrightness >= minBrightness && avgBrightness <= maxBrightness;

    // 2. Calculate Sharpness via Gradient Edge Energy (Sobel / Laplacian approximation)
    double edgeEnergy = 0;
    int edgeCount = 0;

    for (int y = 4; y < image.height - 4; y += 4) {
      for (int x = 4; x < image.width - 4; x += 4) {
        final center = image.getPixel(x, y).luminance;
        final right = image.getPixel(x + 2, y).luminance;
        final down = image.getPixel(x, y + 2).luminance;
        
        final dx = (right - center).abs();
        final dy = (down - center).abs();
        edgeEnergy += (dx + dy);
        edgeCount++;
      }
    }

    final double sharpnessScore = edgeCount > 0 ? (edgeEnergy / edgeCount) : 0.0;
    final bool isSharp = sharpnessScore >= minSharpnessThreshold;

    // 3. Framing Check - Ensure non-zero dimensions and reasonable aspect ratio
    final bool isFramedWell = image.width >= 320 && image.height >= 320;

    String? rejectionReason;
    if (avgBrightness < minBrightness) {
      rejectionReason = 'Lighting is too dark. Increase illumination or move closer to light.';
    } else if (avgBrightness > maxBrightness) {
      rejectionReason = 'Image is overexposed/glary. Avoid direct harsh glare on onions.';
    } else if (!isFramedWell) {
      rejectionReason = 'Image resolution too small. Please frame the onion sample clearly.';
    } else if (!isSharp) {
      rejectionReason = 'Image is blurry. Please hold camera steady and tap to focus.';
    }

    return ImageQualityResult(
      isSharp: isSharp,
      isAdequatelyLit: adequatelyLit,
      isFramedWell: isFramedWell,
      sharpnessScore: sharpnessScore,
      brightnessScore: avgBrightness,
      rejectionReason: rejectionReason,
    );
  }
}
