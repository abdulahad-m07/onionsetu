// lib/screens/results_screen.dart
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:image/image.dart' as img;
import '../models/scan_model.dart';
import '../models/batch_assessment.dart';
import '../providers/auth_provider.dart';
import '../providers/scan_provider.dart';
import '../providers/history_provider.dart';
import '../widgets/grade_summary_card.dart';
import '../widgets/detection_overlay.dart';
import '../theme/app_theme.dart';
import 'dispute_screen.dart';

class ResultsScreen extends StatefulWidget {
  const ResultsScreen({super.key});

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

/// Final batch grade card: exactly ONE overall A/B/C/Reject for the lot,
/// with AI confidence kept separate from any percentage.
class _BatchGradeCard extends StatelessWidget {
  final BatchAssessmentResult batch;

  const _BatchGradeCard({required this.batch});

  Color _gradeColor(BatchGrade grade) {
    switch (grade) {
      case BatchGrade.a:
        return AppTheme.secondaryGreen;
      case BatchGrade.b:
        return const Color(0xFF2E7D32);
      case BatchGrade.c:
        return AppTheme.warningOrange;
      case BatchGrade.reject:
        return AppTheme.defectRed;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _gradeColor(batch.finalGrade);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color, width: 2),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Center(
                    child: Text(
                      batch.finalGrade == BatchGrade.reject
                          ? 'R'
                          : batch.finalGrade.value,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 32,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'FINAL BATCH GRADE',
                        style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.textSecondary),
                      ),
                      Text(
                        batch.finalGrade.displayName,
                        style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                            color: color),
                      ),
                      Text(
                        'AI confidence: ${(batch.assessmentConfidence * 100).toStringAsFixed(1)}% • '
                        'Views: ${batch.imagesAnalyzed} • '
                        'View detections: ~${batch.sampleSize}'
                        '${batch.sampleSizeEstimated ? ' (est.)' : ''}',
                        style: const TextStyle(
                            fontSize: 11, color: AppTheme.textSecondary),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        // URS driver row (§14 card contract): the single URS%
                        // that grounded the grade + the grader-declared batch.
                        // View detections are NOT unique onions, so they are
                        // never labeled as the batch size.
                        batch.ursPercent != null
                            ? 'URS ${batch.ursPercent!.toStringAsFixed(2)}% of '
                                '${batch.assessedOnionsDeclared} declared • '
                                'Batch: ${batch.assessedOnionsDeclared} onions'
                            : 'URS unknown — fallback grade, human review • '
                                'Batch: ${batch.assessedOnionsDeclared ?? '—'} onions',
                        style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.textSecondary),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (batch.reviewRequired) ...[
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFF8E1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppTheme.warningOrange),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.person_search_outlined,
                        size: 18, color: AppTheme.warningOrange),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'HUMAN REVIEW REQUIRED — ${batch.reviewReasons.isNotEmpty ? batch.reviewReasons.first : 'see reasons'}.',
                        style: const TextStyle(fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ],
            if (batch.observations.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Text('AI observations',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              ...batch.observations
                  .take(5)
                  .map((o) => Padding(
                        padding: const EdgeInsets.only(bottom: 2),
                        child: Text('• $o',
                            style: const TextStyle(fontSize: 12)),
                      )),
            ],
            if (batch.visibleQualityIssues.isNotEmpty) ...[
              const SizedBox(height: 8),
              const Text('Visible quality issues',
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              ...batch.visibleQualityIssues.map((i) => Padding(
                    padding: const EdgeInsets.only(bottom: 2),
                    child: Text(
                      '• ${i.issue} [${i.severity}]'
                      '${i.evidenceRef != null ? ' (${i.evidenceRef})' : ''}',
                      style: const TextStyle(fontSize: 12),
                    ),
                  )),
            ],
            const SizedBox(height: 8),
            Text(
              'Policy ${batch.policyVersion} • Detection: ${batch.roboflowModel} • '
              'Assessment: ${batch.assessmentModel}',
              style: const TextStyle(
                  fontSize: 10, color: AppTheme.textSecondary),
            ),
            if (batch.policyVersion.toLowerCase().contains('provisional')) ...[
              const SizedBox(height: 6),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFF8E1),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: AppTheme.warningOrange),
                ),
                child: const Text(
                  'Provisional grading policy — thresholds require APMC validation; not an official government standard.',
                  style: TextStyle(fontSize: 10, color: AppTheme.textSecondary),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ResultsScreenState extends State<ResultsScreen> {
  int _selectedImageIndex = 0;
  bool _isSavedLocally = false;

  String _pendingTitle(AiInferenceStatus status) {
    switch (status) {
      case AiInferenceStatus.processing:
        return 'AI analysis in progress...';
      case AiInferenceStatus.failed:
        return 'AI analysis failed — scan kept as pending';
      case AiInferenceStatus.pendingAi:
        return 'Awaiting AI analysis';
      case AiInferenceStatus.completed:
      case AiInferenceStatus.humanReviewRequired:
        return 'Awaiting AI analysis';
    }
  }

  /// Resolves real pixel dimensions for overlay scaling; null when the
  /// file is missing/unreadable (caller falls back to a 640 square).
  Future<Size?> _resolveImageSize(File file) async {
    try {
      final decoded = img.decodeImage(await file.readAsBytes());
      if (decoded == null) return null;
      return Size(decoded.width.toDouble(), decoded.height.toDouble());
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final scanProvider = context.watch<ScanProvider>();
    final session = scanProvider.currentSession;
    final result = session?.result;

    if (session == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Assessment Result')),
        body: const Center(
          child: Text('No active scan result found.'),
        ),
      );
    }

    // Pending-AI state: captured + quality-passed, stored offline, but cloud
    // (Roboflow) inference has not completed. Never show a fake result here.
    // A validated batch assessment IS shown when present (it arrives via its
    // own pipeline and carries exactly one final grade).
    if (result == null) {
      return Scaffold(
        appBar: AppBar(title: Text('Lot: ${session.lotNumber}')),
        body: SingleChildScrollView(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  session.aiStatus == AiInferenceStatus.failed
                      ? Icons.cloud_off_outlined
                      : Icons.cloud_queue_outlined,
                  size: 56,
                  color: AppTheme.textSecondary,
                ),
                const SizedBox(height: 12),
                Text(
                  _pendingTitle(session.aiStatus),
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'Captured ${session.images.length} photo(s), stored offline. '
                  'AI analysis needs connectivity (Roboflow hosted model).',
                  style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 20),
                ElevatedButton.icon(
                  onPressed: scanProvider.isProcessing
                      ? null
                      : () async {
                          final token =
                              context.read<AuthProvider>().authToken ?? '';
                          final ok = await scanProvider.requestAiAnalysis(
                            token: token,
                          );
                          if (!ok && context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text(
                                  'AI analysis failed. Stay offline-safe: scan kept as pending, retry when online.',
                                ),
                              ),
                            );
                          }
                        },
                  icon: scanProvider.isProcessing
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.cloud_upload_outlined),
                  label: Text(scanProvider.isProcessing
                      ? (scanProvider.statusMessage ?? 'Analyzing...')
                      : 'Run AI Analysis (Online)'),
                ),
                const SizedBox(height: 12),
                Text(
                  'Batch views: ${scanProvider.viewsCaptured}/${ScanProvider.maxBatchViews} '
                  '(min ${ScanProvider.minBatchViews}) • '
                  'Declared batch: ${session.assessedOnions ?? '—'} onions',
                  style: const TextStyle(
                      fontSize: 12, color: AppTheme.textSecondary),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                ElevatedButton.icon(
                  onPressed: scanProvider.isProcessing ||
                          !scanProvider.canFinishBatchCapture
                      ? null
                      : () async {
                          final token =
                              context.read<AuthProvider>().authToken ?? '';
                          final ok = await scanProvider.requestBatchAssessment(
                            token: token,
                          );
                          if (!ok && context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text(
                                  scanProvider.statusMessage ??
                                      'Batch grading failed. Scan kept as pending — retry when online.',
                                ),
                              ),
                            );
                          } else if (context.mounted) {
                            setState(() {});
                          }
                        },
                  icon: const Icon(Icons.workspace_premium_outlined),
                  label: Text(scanProvider.isProcessing
                      ? (scanProvider.statusMessage ?? 'Grading batch...')
                      : 'Run Batch Grading (A / B / C / Reject)'),
                ),
                if (!scanProvider.canFinishBatchCapture)
                  const Padding(
                    padding: EdgeInsets.only(top: 6),
                    child: Text(
                      'Capture at least 10 views of the same batch to enable grading.',
                      style: TextStyle(
                          fontSize: 11, color: AppTheme.textSecondary),
                      textAlign: TextAlign.center,
                    ),
                  ),
                // Validated batch result (ONE final grade) — shown even while
                // the per-onion pipeline is still pending.
                if (session.batchAssessment != null) ...[
                  const SizedBox(height: 12),
                  _BatchGradeCard(batch: session.batchAssessment!),
                ],
              ],
            ),
          ),
        ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('Lot: ${session.lotNumber}'),
        actions: [
          IconButton(
            icon: const Icon(Icons.share_outlined),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Sharing digital grading summary...')),
              );
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Farmer & Lot Metadata Header
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              color: Colors.white,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        session.farmerName,
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                      Text(
                        'Phone: ${session.farmerPhone} • ${session.procurementCenterId}',
                        style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                      ),
                    ],
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryAmber.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      session.syncStatus.name.toUpperCase(),
                      style: const TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryAmber,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),

            // Grade Summary Card (Grade A %, URS %, Defect Breakdown, Confidence Gate)
            GradeSummaryCard(result: result),

            // Honest AI-limitation banner: current model has no quality classes.
            if (!result.qualityClassificationAvailable)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFF8E1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppTheme.warningOrange),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.person_search_outlined,
                          size: 20, color: AppTheme.warningOrange),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Quality classification unavailable from the current AI model '
                          '(${result.unclassifiedCount} unclassified detection(s)). '
                          'Counts are real detections; percentages are provisional '
                          'pending human review.',
                          style: const TextStyle(fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

            // FINAL BATCH GRADE (A/B/C/Reject) — the ONE product result.
            // Per-onion A/B/C grades are never shown: that is not the product.
            if (session.batchAssessment != null)
              _BatchGradeCard(batch: session.batchAssessment!)
            else
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: scanProvider.isProcessing
                        ? null
                        : () async {
                            final token =
                                context.read<AuthProvider>().authToken ?? '';
                            final ok =
                                await scanProvider.requestBatchAssessment(
                              token: token,
                            );
                            if (!ok && context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text(
                                    'Batch grading failed. Scan kept as pending — retry when online.',
                                  ),
                                ),
                              );
                            }
                          },
                    icon: const Icon(Icons.workspace_premium_outlined),
                    label: Text(scanProvider.isProcessing
                        ? (scanProvider.statusMessage ?? 'Grading batch...')
                        : 'Run Batch Grading (A / B / C / Reject)'),
                  ),
                ),
              ),

            // Visual Evidence & AI Detection Overlay Section
            if (session.images.isNotEmpty) ...[
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'AI Visual Evidence (Bounding Boxes)',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                    ),
                    Text(
                      'Photo ${_selectedImageIndex + 1} of ${session.images.length}',
                      style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                    ),
                  ],
                ),
              ),
              
              // Image Container with CustomPainter overlay
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 16),
                height: 260,
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(12),
                ),
                clipBehavior: Clip.antiAlias,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    // Render image file if exists, or placeholder
                    if (File(session.images[_selectedImageIndex].localPath).existsSync())
                      Image.file(
                        File(session.images[_selectedImageIndex].localPath),
                        fit: BoxFit.contain,
                      )
                    else
                      Container(
                        color: const Color(0xFF2C2C2C),
                        child: const Center(
                          child: Icon(Icons.image, color: Colors.white38, size: 48),
                        ),
                      ),

                    // Draw Roboflow detection boxes & labels, scaled from the
                    // ACTUAL submitted-image dimensions (boxes are stored in
                    // submitted-image pixels, not a fixed 640 grid).
                    FutureBuilder<Size?>(
                      future: _resolveImageSize(File(session
                          .images[_selectedImageIndex].localPath)),
                      builder: (context, snapshot) {
                        final dims = snapshot.data ?? const Size(640, 640);
                        return CustomPaint(
                          painter: DetectionOverlayPainter(
                            detections: session.detections
                                .where((d) =>
                                    d.viewAngle ==
                                    session.images[_selectedImageIndex].angle.name)
                                .toList(),
                            sourceImageSize: dims,
                            showLabels: true,
                          ),
                        );
                      },
                    ),
                  ],
                ),
              ),

              // Multi-View Selector Tabs (Top, Side, Spread)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(session.images.length, (idx) {
                    final isSelected = idx == _selectedImageIndex;
                    final angle = session.images[idx].angle.name.toUpperCase();
                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 4.0),
                      child: ChoiceChip(
                        label: Text(angle),
                        selected: isSelected,
                        onSelected: (_) => setState(() => _selectedImageIndex = idx),
                        selectedColor: AppTheme.primaryAmber,
                        labelStyle: TextStyle(
                          color: isSelected ? Colors.white : AppTheme.textPrimary,
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    );
                  }),
                ),
              ),
            ],

            // SHA-256 Audit Integrity Hash Record
            if (result.auditHash != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                child: Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade100,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppTheme.borderLight),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.lock_outline, size: 16, color: AppTheme.textSecondary),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'SHA-256 Hash: ${result.auditHash!.substring(0, 24)}...',
                          style: const TextStyle(
                            fontSize: 11,
                            fontFamily: 'monospace',
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

            const SizedBox(height: 16),

            // Action Buttons (Save Offline, File Dispute, New Scan)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0),
              child: Column(
                children: [
                  ElevatedButton.icon(
                    onPressed: _isSavedLocally
                        ? null
                        : () async {
                            await scanProvider.saveCurrentScanLocally();
                            if (context.mounted) {
                              await context.read<HistoryProvider>().loadScans();
                              setState(() => _isSavedLocally = true);
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Scan saved to offline database successfully.'),
                                  backgroundColor: AppTheme.secondaryGreen,
                                ),
                              );
                            }
                          },
                    icon: Icon(_isSavedLocally ? Icons.check : Icons.save_alt_outlined),
                    label: Text(_isSavedLocally ? 'Saved to Offline DB' : 'Save Scan Locally (Offline)'),
                  ),
                  const SizedBox(height: 10),

                  OutlinedButton.icon(
                    onPressed: () {
                      Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => DisputeScreen(scanId: session.id, lotNumber: session.lotNumber),
                        ),
                      );
                    },
                    icon: const Icon(Icons.gavel_outlined),
                    label: const Text('File Grade Dispute / Re-inspection'),
                  ),
                  const SizedBox(height: 10),

                  TextButton(
                    onPressed: () {
                      scanProvider.resetSession();
                      Navigator.popUntil(context, (route) => route.isFirst);
                    },
                    child: const Text('Start Another Assessment'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }
}
