// lib/screens/history_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../providers/history_provider.dart';
import '../providers/scan_provider.dart';
import '../models/scan_model.dart';
import '../theme/app_theme.dart';
import 'results_screen.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<HistoryProvider>().loadScans();
    });
  }

  @override
  Widget build(BuildContext context) {
    final history = context.watch<HistoryProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Offline Scan History'),
      ),
      body: Column(
        children: [
          // Search & Filter Header
          Container(
            padding: const EdgeInsets.all(12),
            color: Colors.white,
            child: Column(
              children: [
                TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'Search by Lot # or Farmer Name...',
                    prefixIcon: const Icon(Icons.search),
                    suffixIcon: _searchController.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear),
                            onPressed: () {
                              _searchController.clear();
                              history.setSearchQuery('');
                            },
                          )
                        : null,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                    ),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12),
                  ),
                  onChanged: (val) => history.setSearchQuery(val),
                ),
                const SizedBox(height: 8),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _buildFilterChip(history, 'All', null),
                      const SizedBox(width: 8),
                      _buildFilterChip(history, 'Grade A ≥ 80%', 'Grade A >= 80%'),
                      const SizedBox(width: 8),
                      _buildFilterChip(history, 'High URS > 20%', 'URS > 20%'),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // Scans List
          Expanded(
            child: history.isLoading
                ? const Center(child: CircularProgressIndicator())
                : history.scans.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(Icons.history_outlined, size: 64, color: AppTheme.textSecondary),
                            const SizedBox(height: 12),
                            const Text(
                              'No local scans found.',
                              style: TextStyle(fontSize: 16, color: AppTheme.textSecondary),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              history.searchQuery.isNotEmpty
                                  ? 'Try adjusting your search criteria.'
                                  : 'Completed assessments will appear here offline.',
                              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                            ),
                          ],
                        ),
                      )
                    : RefreshIndicator(
                        onRefresh: () => history.loadScans(),
                        child: ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          itemCount: history.scans.length,
                          itemBuilder: (context, index) {
                            final scan = history.scans[index];
                            final res = scan.result;
                            final dateFormatted = DateFormat('dd MMM yyyy, hh:mm a').format(scan.createdAt);

                            return Card(
                              margin: const EdgeInsets.symmetric(vertical: 6),
                              child: InkWell(
                                borderRadius: BorderRadius.circular(12),
                                onTap: () {
                                  // Open in results view
                                  // Set as current session for inspection
                                  // (handled smoothly via Navigator)
                                },
                                child: Padding(
                                  padding: const EdgeInsets.all(14.0),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Text(
                                            scan.lotNumber,
                                            style: const TextStyle(
                                              fontSize: 15,
                                              fontWeight: FontWeight.bold,
                                              color: AppTheme.primaryDark,
                                            ),
                                          ),
                                          Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                            decoration: BoxDecoration(
                                              color: scan.syncStatus == ScanSyncStatus.synced
                                                  ? AppTheme.secondaryGreen.withOpacity(0.12)
                                                  : AppTheme.warningOrange.withOpacity(0.12),
                                              borderRadius: BorderRadius.circular(4),
                                            ),
                                            child: Text(
                                              scan.syncStatus.name.toUpperCase(),
                                              style: TextStyle(
                                                fontSize: 10,
                                                fontWeight: FontWeight.bold,
                                                color: scan.syncStatus == ScanSyncStatus.synced
                                                    ? AppTheme.secondaryGreen
                                                    : AppTheme.warningOrange,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 6),
                                      Text(
                                        'Farmer: ${scan.farmerName} (${scan.farmerPhone})',
                                        style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary),
                                      ),
                                      const SizedBox(height: 4),
                                      Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Text(
                                            dateFormatted,
                                            style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                                          ),
                                          if (res != null)
                                            Text(
                                              'Grade A: ${res.gradeAPercentage.toStringAsFixed(1)}% | URS: ${res.ursPercentage.toStringAsFixed(1)}%',
                                              style: const TextStyle(
                                                fontSize: 12,
                                                fontWeight: FontWeight.bold,
                                                color: AppTheme.secondaryGreen,
                                              ),
                                            ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            );
                          },
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(HistoryProvider history, String label, String? filterValue) {
    final isSelected = history.selectedFilterGrade == filterValue;
    return ChoiceChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (_) => history.setFilterGrade(filterValue),
      selectedColor: AppTheme.primaryAmber,
      labelStyle: TextStyle(
        color: isSelected ? Colors.white : AppTheme.textPrimary,
        fontSize: 11,
        fontWeight: FontWeight.w600,
      ),
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }
}
