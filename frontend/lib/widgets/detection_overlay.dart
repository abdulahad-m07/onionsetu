// lib/widgets/detection_overlay.dart
import 'package:flutter/material.dart';
import '../models/detection_model.dart';
import '../theme/app_theme.dart';

class DetectionOverlayPainter extends CustomPainter {
  final List<DetectionItem> detections;
  final Size sourceImageSize;
  final bool showLabels;

  DetectionOverlayPainter({
    required this.detections,
    required this.sourceImageSize,
    this.showLabels = true,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (detections.isEmpty || sourceImageSize.width == 0 || sourceImageSize.height == 0) {
      return;
    }

    final double scaleX = size.width / sourceImageSize.width;
    final double scaleY = size.height / sourceImageSize.height;

    for (final det in detections) {
      final Color boxColor = _getColorForDefect(det.defectType);
      
      final Paint boxPaint = Paint()
        ..color = boxColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5;

      final Paint fillPaint = Paint()
        ..color = boxColor.withOpacity(0.15)
        ..style = PaintingStyle.fill;

      final Rect rect = Rect.fromLTWH(
        det.x * scaleX,
        det.y * scaleY,
        det.width * scaleX,
        det.height * scaleY,
      );

      // Draw bounding box
      canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(6)), fillPaint);
      canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(6)), boxPaint);

      // Draw label & confidence
      if (showLabels) {
        final String labelText = '${det.defectType.name.toUpperCase()} ${(det.confidence * 100).toInt()}%'
            '${det.estimatedDiameterMm != null ? ' (${det.estimatedDiameterMm}mm)' : ''}';

        final TextSpan span = TextSpan(
          text: labelText,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 10,
            fontWeight: FontWeight.bold,
          ),
        );

        final TextPainter tp = TextPainter(
          text: span,
          textDirection: TextDirection.ltr,
        )..layout();

        final double badgeW = tp.width + 8;
        final double badgeH = tp.height + 4;
        final double badgeX = rect.left.clamp(0.0, size.width - badgeW);
        final double badgeY = (rect.top - badgeH - 2).clamp(0.0, size.height - badgeH);

        final Paint badgeBg = Paint()
          ..color = boxColor
          ..style = PaintingStyle.fill;

        canvas.drawRRect(
          RRect.fromRectAndRadius(
            Rect.fromLTWH(badgeX, badgeY, badgeW, badgeH),
            const Radius.circular(4),
          ),
          badgeBg,
        );

        tp.paint(canvas, Offset(badgeX + 4, badgeY + 2));
      }
    }
  }

  static Color _getColorForDefect(OnionDefectType type) {
    switch (type) {
      case OnionDefectType.gradeA:
        return AppTheme.secondaryGreen;
      case OnionDefectType.damaged:
        return AppTheme.defectRed;
      case OnionDefectType.rotten:
        return const Color(0xFF4A148C); // Deep purple-black for rot
      case OnionDefectType.sprouted:
        return const Color(0xFF827717); // Olive green/yellow for sprout
      case OnionDefectType.undersized:
        return AppTheme.warningOrange;
      case OnionDefectType.unknown:
        return Colors.grey;
    }
  }

  @override
  bool shouldRepaint(covariant DetectionOverlayPainter oldDelegate) {
    return oldDelegate.detections != detections || oldDelegate.sourceImageSize != sourceImageSize;
  }
}
