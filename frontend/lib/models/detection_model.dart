// lib/models/detection_model.dart

enum OnionDefectType {
  gradeA,
  damaged,
  rotten,
  sprouted,
  undersized,
  unknown,
}

extension OnionDefectExtension on OnionDefectType {
  String get displayName {
    switch (this) {
      case OnionDefectType.gradeA:
        return 'Grade A (Healthy)';
      case OnionDefectType.damaged:
        return 'Damaged';
      case OnionDefectType.rotten:
        return 'Rotten';
      case OnionDefectType.sprouted:
        return 'Sprouted';
      case OnionDefectType.undersized:
        return 'Undersized';
      case OnionDefectType.unknown:
        return 'Unclassified';
    }
  }

  static OnionDefectType fromString(String val) {
    final lower = val.toLowerCase().trim();
    if (lower.contains('grade a') || lower.contains('healthy')) return OnionDefectType.gradeA;
    if (lower.contains('damage')) return OnionDefectType.damaged;
    if (lower.contains('rot')) return OnionDefectType.rotten;
    if (lower.contains('sprout')) return OnionDefectType.sprouted;
    if (lower.contains('undersize') || lower.contains('small')) return OnionDefectType.undersized;
    return OnionDefectType.unknown;
  }
}

class DetectionItem {
  final String id;
  final double x; // Normalized [0..1] or pixel coordinates
  final double y;
  final double width;
  final double height;
  final OnionDefectType defectType;
  final double confidence; // Real model prediction confidence [0..1]
  final double? estimatedDiameterMm; // Size estimation in mm
  final String? viewAngle; // 'top', 'side', 'bottom'
  /// Raw vision-model class label, passed through verbatim (e.g. "onion").
  /// Null only for legacy/locally-created items. When [defectType] is
  /// [OnionDefectType.unknown], this preserves what the model actually said
  /// instead of inventing a quality class.
  final String? rawLabel;

  DetectionItem({
    required this.id,
    required this.x,
    required this.y,
    required this.width,
    required this.height,
    required this.defectType,
    required this.confidence,
    this.estimatedDiameterMm,
    this.viewAngle,
    this.rawLabel,
  });

  Map<String, dynamic> toJson() => {
    'id': id,
    'x': x,
    'y': y,
    'width': width,
    'height': height,
    'defect_type': defectType.name,
    'defect_name': defectType.displayName,
    'confidence': confidence,
    'estimated_diameter_mm': estimatedDiameterMm,
    'view_angle': viewAngle,
    'raw_label': rawLabel,
  };

  factory DetectionItem.fromJson(Map<String, dynamic> json) {
    return DetectionItem(
      id: json['id'] as String? ?? '',
      x: (json['x'] as num).toDouble(),
      y: (json['y'] as num).toDouble(),
      width: (json['width'] as num).toDouble(),
      height: (json['height'] as num).toDouble(),
      defectType: OnionDefectExtension.fromString(json['defect_type'] as String? ?? ''),
      confidence: (json['confidence'] as num).toDouble(),
      estimatedDiameterMm: (json['estimated_diameter_mm'] as num?)?.toDouble(),
      viewAngle: json['view_angle'] as String?,
      rawLabel: json['raw_label'] as String?,
    );
  }
}
