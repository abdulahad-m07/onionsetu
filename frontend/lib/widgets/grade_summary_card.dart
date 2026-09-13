// lib/widgets/grade_summary_card.dart
import 'package:flutter/material.dart';
import '../models/grading_result.dart';
import '../theme/app_theme.dart';

class GradeSummaryCard extends StatelessWidget {
  final GradingResult result;

  const GradeSummaryCard({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    final isHighConfidence = result.confidenceStatus == ConfidenceGateStatus.highConfidence;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'AI Quality Assessment',
                      style: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Policy: ${result.policyVersion}',
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: isHighConfidence
                        ? AppTheme.secondaryGreen.withOpacity(0.12)
                        : AppTheme.warningOrange.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: isHighConfidence ? AppTheme.secondaryGreen : AppTheme.warningOrange,
                      width: 1,
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        isHighConfidence ? Icons.check_circle : Icons.warning_amber_rounded,
                        size: 14,
                        color: isHighConfidence ? AppTheme.secondaryGreen : AppTheme.warningOrange,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        isHighConfidence ? 'High Confidence' : 'Review Flag',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: isHighConfidence ? AppTheme.secondaryGreen : AppTheme.warningOrange,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const Divider(height: 24),
            Row(
              children: [
                Expanded(
                  child: _buildMetricTile(
                    label: 'Grade A %',
                    value: '${result.gradeAPercentage.toStringAsFixed(1)}%',
                    color: AppTheme.secondaryGreen,
                    subtitle: '${result.gradeACount} / ${result.totalOnionsCount} onions',
                  ),
                ),
                Container(width: 1, height: 50, color: AppTheme.borderLight),
                Expanded(
                  child: _buildMetricTile(
                    label: 'URS / Undergrade %',
                    value: '${result.ursPercentage.toStringAsFixed(1)}%',
                    color: AppTheme.defectRed,
                    subtitle: '${result.totalOnionsCount - result.gradeACount} defect onions',
                  ),
                ),
                Container(width: 1, height: 50, color: AppTheme.borderLight),
                Expanded(
                  child: _buildMetricTile(
                    label: 'Model Confidence',
                    value: '${(result.averageAiConfidence * 100).toStringAsFixed(1)}%',
                    color: AppTheme.infoBlue,
                    subtitle: 'Inference certainty',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const Text(
              'Defect Breakdown',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 8),
            _buildDefectRow('Damaged / Bruised', result.damagedCount, AppTheme.defectRed),
            _buildDefectRow('Rotten / Mold', result.rottenCount, const Color(0xFF4A148C)),
            _buildDefectRow('Sprouted', result.sproutedCount, const Color(0xFF827717)),
            _buildDefectRow('Undersized (<40mm)', result.undersizedCount, AppTheme.warningOrange),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricTile({
    required String label,
    required String value,
    required Color color,
    required String subtitle,
  }) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: color),
        ),
        const SizedBox(height: 2),
        Text(
          subtitle,
          style: const TextStyle(fontSize: 9, color: AppTheme.textSecondary),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }

  Widget _buildDefectRow(String label, int count, Color color) {
    final double pct = result.totalOnionsCount > 0
        ? (count / result.totalOnionsCount) * 100.0
        : 0.0;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3.0),
      child: Row(
        children: [
          Container(
            width: 10,
            height: 10,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(label, style: const TextStyle(fontSize: 12)),
          ),
          Text(
            '$count (${pct.toStringAsFixed(1)}%)',
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
