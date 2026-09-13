// lib/screens/dispute_screen.dart
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../models/dispute_model.dart';
import '../theme/app_theme.dart';

class DisputeScreen extends StatefulWidget {
  final String scanId;
  final String lotNumber;

  const DisputeScreen({
    super.key,
    required this.scanId,
    required this.lotNumber,
  });

  @override
  State<DisputeScreen> createState() => _DisputeScreenState();
}

class _DisputeScreenState extends State<DisputeScreen> {
  final _reasonController = TextEditingController();
  String _disputeCategory = 'Grade A percentage judged too low';
  bool _isSubmitting = false;

  final List<String> _categories = [
    'Grade A percentage judged too low',
    'Defect classification dispute (Sprout / Rot / Damaged)',
    'Size estimation mismatch',
    'Image capture lighting/framing anomaly',
    'Other procedural objection',
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('File Quality Dispute'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Card(
              color: AppTheme.primaryAmber.withOpacity(0.06),
              child: Padding(
                padding: const EdgeInsets.all(14.0),
                child: Row(
                  children: [
                    const Icon(Icons.gavel_outlined, color: AppTheme.primaryDark),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Dispute on Lot: ${widget.lotNumber}',
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                          ),
                          const SizedBox(height: 2),
                          const Text(
                            'Evidence photos and audit trail will be linked to this case for officer re-grading.',
                            style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),

            const Text(
              'Select Primary Reason *',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              value: _disputeCategory,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
              ),
              items: _categories.map((c) => DropdownMenuItem(value: c, child: Text(c, style: const TextStyle(fontSize: 13)))).toList(),
              onChanged: (val) => setState(() => _disputeCategory = val ?? _disputeCategory),
            ),
            const SizedBox(height: 16),

            const Text(
              'Detailed Observations / Notes *',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _reasonController,
              maxLines: 4,
              decoration: const InputDecoration(
                hintText: 'Describe why the automated grade is disputed...',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 24),

            ElevatedButton.icon(
              onPressed: _isSubmitting
                  ? null
                  : () async {
                      if (_reasonController.text.trim().isEmpty) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Please enter detailed observations.')),
                        );
                        return;
                      }

                      setState(() => _isSubmitting = true);
                      await Future.delayed(const Duration(milliseconds: 600));

                      final dispute = DisputeRecord(
                        id: const Uuid().v4(),
                        scanId: widget.scanId,
                        filedByUserId: 'farmer_current',
                        reason: '$_disputeCategory: ${_reasonController.text.trim()}',
                        status: DisputeStatus.pendingReview,
                      );

                      if (mounted) {
                        setState(() => _isSubmitting = false);
                        showDialog(
                          context: context,
                          builder: (ctx) => AlertDialog(
                            title: const Text('Dispute Registered'),
                            content: Text(
                              'Dispute Case ID: ${dispute.id.substring(0, 8)}\n\n'
                              'Status: PENDING REVIEW.\nAn APMC Review Officer has been assigned to re-examine the evidence.',
                            ),
                            actions: [
                              TextButton(
                                onPressed: () {
                                  Navigator.pop(ctx);
                                  Navigator.pop(context);
                                },
                                child: const Text('OK'),
                              ),
                            ],
                          ),
                        );
                      }
                    },
              icon: _isSubmitting
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.send_outlined),
              label: Text(_isSubmitting ? 'Submitting Dispute...' : 'Submit Quality Dispute'),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _reasonController.dispose();
    super.dispose();
  }
}
