// lib/providers/history_provider.dart
import 'package:flutter/material.dart';
import '../models/scan_model.dart';
import '../db/scan_database.dart';

class HistoryProvider extends ChangeNotifier {
  final ScanDatabase _database = ScanDatabase.instance;
  List<ScanSession> _scans = [];
  bool _isLoading = false;
  String _searchQuery = '';
  String? _selectedFilterGrade;

  List<ScanSession> get scans {
    return _scans.where((scan) {
      final matchesSearch = _searchQuery.isEmpty ||
          scan.lotNumber.toLowerCase().contains(_searchQuery.toLowerCase()) ||
          scan.farmerName.toLowerCase().contains(_searchQuery.toLowerCase()) ||
          scan.farmerPhone.contains(_searchQuery);

      if (!matchesSearch) return false;

      if (_selectedFilterGrade == 'Grade A >= 80%') {
        return (scan.result?.gradeAPercentage ?? 0) >= 80.0;
      } else if (_selectedFilterGrade == 'URS > 20%') {
        return (scan.result?.ursPercentage ?? 0) > 20.0;
      }

      return true;
    }).toList();
  }

  bool get isLoading => _isLoading;
  String get searchQuery => _searchQuery;
  String? get selectedFilterGrade => _selectedFilterGrade;

  Future<void> loadScans() async {
    _isLoading = true;
    notifyListeners();

    try {
      _scans = await _database.getAllScans();
    } catch (e) {
      _scans = [];
    }

    _isLoading = false;
    notifyListeners();
  }

  void setSearchQuery(String query) {
    _searchQuery = query;
    notifyListeners();
  }

  void setFilterGrade(String? filter) {
    _selectedFilterGrade = filter;
    notifyListeners();
  }

  Future<void> deleteScan(String scanId) async {
    await _database.deleteScan(scanId);
    await loadScans();
  }
}
