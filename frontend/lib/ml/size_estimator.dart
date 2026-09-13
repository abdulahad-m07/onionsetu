// lib/ml/size_estimator.dart
import 'dart:math';

enum OnionSizeCategory {
  undersized, // < 35mm (Rejection / Secondary)
  small, // 35 - 45mm
  medium, // 45 - 65mm (Grade A standard)
  large, // 65 - 85mm (Grade A standard)
  extraLarge, // > 85mm
}

class OnionSizeEstimator {
  // Standard calibration factor: pixels per mm at standard 40cm capture height
  // In procurement tray setup with 640x640 frame, ~3.8 pixels = 1mm
  static const double defaultPixelsPerMm = 3.8;

  /// Estimates diameter in mm from normalized or pixel bounding box coordinates
  static double estimateDiameterMm({
    required double boxWidthPx,
    required double boxHeightPx,
    double pixelsPerMm = defaultPixelsPerMm,
  }) {
    // Onion is roughly elliptical/spherical, diameter ~ geometric mean of width & height
    final double avgPx = sqrt(boxWidthPx * boxHeightPx);
    final double diameterMm = avgPx / pixelsPerMm;
    // Bound to realistic onion dimensions (20mm - 130mm)
    return diameterMm.clamp(15.0, 140.0);
  }

  static OnionSizeCategory categorizeSize(double diameterMm) {
    if (diameterMm < 35.0) {
      return OnionSizeCategory.undersized;
    } else if (diameterMm < 45.0) {
      return OnionSizeCategory.small;
    } else if (diameterMm <= 65.0) {
      return OnionSizeCategory.medium;
    } else if (diameterMm <= 85.0) {
      return OnionSizeCategory.large;
    } else {
      return OnionSizeCategory.extraLarge;
    }
  }

  static bool isSizeGradeACompatible(double diameterMm) {
    // APMC Grade A standards typically require 45mm - 85mm diameter
    return diameterMm >= 40.0 && diameterMm <= 90.0;
  }
}
