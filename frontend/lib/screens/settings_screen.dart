// lib/screens/settings_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../config/environment.dart';
import '../theme/app_theme.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final user = auth.currentUser;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings & Configuration'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          // User Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 28,
                    backgroundColor: AppTheme.primaryAmber,
                    child: Text(
                      user?.name.substring(0, 1).toUpperCase() ?? 'U',
                      style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          user?.name ?? 'Anonymous Grader',
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                        ),
                        Text(
                          'Role: ${user?.role.name.toUpperCase()} • ${user?.procurementCenterId}',
                          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          user?.phone ?? '',
                          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Grading Policy Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Grading Policy Engine',
                        style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                      ),
                      Chip(
                        label: Text(EnvironmentConfig.gradingPolicyVersion, style: TextStyle(fontSize: 11)),
                        backgroundColor: AppTheme.surfaceLight,
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  _buildPolicyRow('Standard Target Grade A', 'Diameter 40mm - 90mm'),
                  _buildPolicyRow('Min Model Confidence Gate', '70.0% (Borderline triggers flag)'),
                  _buildPolicyRow('Max Tolerable Defect %', '10.0% Lot allowance'),
                  _buildPolicyRow('AI Vision Model', 'Roboflow Hosted (server-side)'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Sync & Backend Status
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'System & Sync Status',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  _buildPolicyRow('Backend API', EnvironmentConfig.apiBaseUrl),
                  _buildPolicyRow('Local Offline Persistence', 'SQLite (Active)'),
                  _buildPolicyRow('File Storage', 'Supabase Cloud Storage'),
                  _buildPolicyRow('Audit Hash System', 'SHA-256 Hash Chain'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

          OutlinedButton.icon(
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Triggered sync queue check...')),
              );
            },
            icon: const Icon(Icons.sync),
            label: const Text('Force Cloud Sync Queue'),
          ),
        ],
      ),
    );
  }

  Widget _buildPolicyRow(String label, String val) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
          Text(val, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
