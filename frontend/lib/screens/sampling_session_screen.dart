// lib/screens/sampling_session_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/scan_provider.dart';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';
import 'camera_capture_screen.dart';

class SamplingSessionScreen extends StatefulWidget {
  const SamplingSessionScreen({super.key});

  @override
  State<SamplingSessionScreen> createState() => _SamplingSessionScreenState();
}

class _SamplingSessionScreenState extends State<SamplingSessionScreen> {
  final _formKey = GlobalKey<FormState>();
  final _lotNumberController = TextEditingController(text: 'LOT-MH-${DateTime.now().millisecondsSinceEpoch % 10000}');
  final _farmerNameController = TextEditingController(text: 'Suresh Shinde');
  final _farmerPhoneController = TextEditingController(text: '+91 98230 11223');
  final _assessedOnionsController = TextEditingController(text: '150');
  String _centerId = 'APMC-LASALGAON-01';

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final graderName = auth.currentUser?.name ?? 'Assigned Grader';

    return Scaffold(
      appBar: AppBar(
        title: const Text('New Assessment Session'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Standardized Sampling Instructions Banner
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.primaryAmber.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppTheme.primaryAmber.withOpacity(0.3)),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.info_outline, color: AppTheme.primaryAmber),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Batch protocol: count the physical batch (100-200 onions), '
                        'enter the count below, then capture 10-15 views of the SAME batch '
                        'from different angles. Views are not new onions.',
                        style: TextStyle(fontSize: 12, color: AppTheme.textPrimary),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              
              TextFormField(
                controller: _lotNumberController,
                decoration: const InputDecoration(
                  labelText: 'Lot / Consignment Number *',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.inventory_2_outlined),
                ),
                validator: (val) => val == null || val.isEmpty ? 'Lot number required' : null,
              ),
              const SizedBox(height: 16),

              TextFormField(
                controller: _farmerNameController,
                decoration: const InputDecoration(
                  labelText: 'Farmer Name *',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.person_outline),
                ),
                validator: (val) => val == null || val.isEmpty ? 'Farmer name required' : null,
              ),
              const SizedBox(height: 16),

              TextFormField(
                controller: _farmerPhoneController,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(
                  labelText: 'Farmer Mobile Number *',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.phone_outlined),
                ),
                validator: (val) => val == null || val.isEmpty ? 'Phone number required' : null,
              ),
              TextFormField(
                controller: _assessedOnionsController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Onions in this batch (100-200) *',
                  helperText:
                      'Count the physical batch. This declared count is the only URS% denominator.',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.numbers_outlined),
                ),
                validator: (val) {
                  final n = int.tryParse((val ?? '').trim());
                  if (n == null) return 'Enter the onion count';
                  if (n < 100 || n > 200) {
                    return 'Batch size must be 100-200 onions';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),

              DropdownButtonFormField<String>(
                value: _centerId,
                decoration: const InputDecoration(
                  labelText: 'Procurement Center',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.location_on_outlined),
                ),
                items: const [
                  DropdownMenuItem(value: 'APMC-LASALGAON-01', child: Text('APMC Lasalgaon (Nashik)')),
                  DropdownMenuItem(value: 'APMC-PIMPALGAON-02', child: Text('APMC Pimpalgaon Baswant')),
                  DropdownMenuItem(value: 'APMC-SOLAPUR-03', child: Text('APMC Solapur')),
                ],
                onChanged: (val) => setState(() => _centerId = val ?? _centerId),
              ),
              const SizedBox(height: 24),

              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12.0),
                  child: Row(
                    children: [
                      const Icon(Icons.badge_outlined, color: AppTheme.textSecondary),
                      const SizedBox(width: 12),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Quality Grader Officer', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                          Text(graderName, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 32),

              ElevatedButton.icon(
                onPressed: () {
                  if (_formKey.currentState!.validate()) {
                    context.read<ScanProvider>().startNewSession(
                      lotNumber: _lotNumberController.text.trim(),
                      farmerName: _farmerNameController.text.trim(),
                      farmerPhone: _farmerPhoneController.text.trim(),
                      procurementCenterId: _centerId,
                      graderId: auth.currentUser?.id ?? 'grader_01',
                      assessedOnions: int.parse(
                        _assessedOnionsController.text.trim(),
                      ),
                    );

                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const CameraCaptureScreen()),
                    );
                  }
                },
                icon: const Icon(Icons.camera_alt_outlined),
                label: const Text('Start Guided Capture'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _lotNumberController.dispose();
    _farmerNameController.dispose();
    _farmerPhoneController.dispose();
    _assessedOnionsController.dispose();
    super.dispose();
  }
}
