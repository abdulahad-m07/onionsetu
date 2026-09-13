// test/size_estimator_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/ml/size_estimator.dart';

void main() {
  group('OnionSizeEstimator Tests', () {
    test('Calculates diameter within realistic bounds and categories', () {
      // 200px box width/height at 3.8 px/mm -> ~52.6 mm
      final diameter = OnionSizeEstimator.estimateDiameterMm(
        boxWidthPx: 200.0,
        boxHeightPx: 200.0,
      );

      expect(diameter, closeTo(52.6, 0.5));
      expect(OnionSizeEstimator.categorizeSize(diameter), equals(OnionSizeCategory.medium));
      expect(OnionSizeEstimator.isSizeGradeACompatible(diameter), isTrue);
    });

    test('Identifies undersized onions correctly', () {
      final diameter = OnionSizeEstimator.estimateDiameterMm(
        boxWidthPx: 100.0,
        boxHeightPx: 100.0,
      ); // ~26.3 mm

      expect(diameter, lessThan(35.0));
      expect(OnionSizeEstimator.categorizeSize(diameter), equals(OnionSizeCategory.undersized));
      expect(OnionSizeEstimator.isSizeGradeACompatible(diameter), isFalse);
    });
  });
}
