// lib/db/scan_database.dart
import 'dart:convert';
import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';
import '../models/scan_model.dart';
import '../models/detection_model.dart';
import '../models/grading_result.dart';
import '../models/batch_assessment.dart';

class ScanDatabase {
  static final ScanDatabase instance = ScanDatabase._init();
  static Database? _database;

  ScanDatabase._init();

  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDB('onionsetu_local.db');
    return _database!;
  }

  Future<Database> _initDB(String filePath) async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, filePath);

    return await openDatabase(
      path,
      version: 5,
      onCreate: _createDB,
      onUpgrade: _upgradeDB,
    );
  }

  static Future<void> _createBatchAssessmentsTable(DatabaseExecutor db) async {
    await db.execute('''
      CREATE TABLE IF NOT EXISTS batch_assessments (
        id TEXT PRIMARY KEY,
        scan_id TEXT NOT NULL,
        final_grade TEXT NOT NULL,
        assessment_confidence REAL NOT NULL,
        sample_size INTEGER NOT NULL,
        sample_size_estimated INTEGER NOT NULL DEFAULT 1,
        images_analyzed INTEGER NOT NULL,
        observations_json TEXT,
        issues_json TEXT,
        review_required INTEGER NOT NULL DEFAULT 0,
        review_reasons_json TEXT,
        policy_version TEXT NOT NULL,
        roboflow_model TEXT NOT NULL,
        assessment_model TEXT NOT NULL,
        urs_percent REAL,
        assessed_onions_declared INTEGER,
        calculated_at TEXT NOT NULL,
        FOREIGN KEY (scan_id) REFERENCES scans (id) ON DELETE CASCADE
      )
    ''');
  }

  /// v1 -> v2: truthful AI lifecycle columns for cloud (Roboflow) inference.
  /// Fresh installs get them via _createDB; existing installs via ALTER TABLE.
  /// v2 -> v3: batch_assessments table for A/B/C/Reject outcomes.
  /// v3 -> v4: rename batch_assessments.gemini_model -> assessment_model
  /// (provider-neutral contract; data-preserving, no rows touched otherwise).
  /// v4 -> v5: grader-declared batch size on scans (assessed_onions) + URS
  /// driver on batch_assessments (urs_percent, assessed_onions_declared).
  /// All added columns are nullable so pre-existing rows stay intact.
  Future<void> _upgradeDB(Database db, int oldVersion, int newVersion) async {
    if (oldVersion < 2) {
      await db.execute(
        'ALTER TABLE scans ADD COLUMN ai_status TEXT NOT NULL DEFAULT \'pendingAi\'',
      );
      await db.execute(
        'ALTER TABLE detections ADD COLUMN raw_label TEXT',
      );
      await db.execute(
        'ALTER TABLE grading_results ADD COLUMN unclassified_count INTEGER NOT NULL DEFAULT 0',
      );
      await db.execute(
        'ALTER TABLE grading_results ADD COLUMN quality_classification_available INTEGER NOT NULL DEFAULT 1',
      );
    }
    if (oldVersion < 3) {
      await _createBatchAssessmentsTable(db);
    }
    if (oldVersion < 4) {
      final cols = await db.rawQuery(
        'PRAGMA table_info(batch_assessments)',
      );
      final names = {for (final c in cols) c['name'] as String};
      if (names.contains('gemini_model') && !names.contains('assessment_model')) {
        await db.execute(
          'ALTER TABLE batch_assessments RENAME COLUMN gemini_model TO assessment_model',
        );
      }
    }
    if (oldVersion < 5) {
      final scanCols = await db.rawQuery('PRAGMA table_info(scans)');
      final scanNames = {for (final c in scanCols) c['name'] as String};
      if (!scanNames.contains('assessed_onions')) {
        await db.execute(
          'ALTER TABLE scans ADD COLUMN assessed_onions INTEGER',
        );
      }
      final batchCols = await db.rawQuery(
        'PRAGMA table_info(batch_assessments)',
      );
      final batchNames = {for (final c in batchCols) c['name'] as String};
      if (!batchNames.contains('urs_percent')) {
        await db.execute(
          'ALTER TABLE batch_assessments ADD COLUMN urs_percent REAL',
        );
      }
      if (!batchNames.contains('assessed_onions_declared')) {
        await db.execute(
          'ALTER TABLE batch_assessments ADD COLUMN assessed_onions_declared INTEGER',
        );
      }
    }
  }

  Future<void> _createDB(Database db, int version) async {
    // 1. Scans Table (v2: ai_status tracks cloud inference lifecycle;
    // v5: assessed_onions stores the grader-declared batch size)
    await db.execute('''
      CREATE TABLE scans (
        id TEXT PRIMARY KEY,
        lot_number TEXT NOT NULL,
        farmer_name TEXT NOT NULL,
        farmer_phone TEXT NOT NULL,
        procurement_center_id TEXT NOT NULL,
        grader_id TEXT NOT NULL,
        assessed_onions INTEGER,
        sync_status TEXT NOT NULL,
        ai_status TEXT NOT NULL DEFAULT 'pendingAi',
        report_url TEXT,
        audit_hash TEXT,
        created_at TEXT NOT NULL
      )
    ''');

    // 2. Images Table
    await db.execute('''
      CREATE TABLE captured_images (
        id TEXT PRIMARY KEY,
        scan_id TEXT NOT NULL,
        local_path TEXT NOT NULL,
        remote_storage_url TEXT,
        angle TEXT NOT NULL,
        sharpness_score REAL,
        brightness_score REAL,
        quality_passed INTEGER NOT NULL,
        captured_at TEXT NOT NULL,
        FOREIGN KEY (scan_id) REFERENCES scans (id) ON DELETE CASCADE
      )
    ''');

    // 3. Detections Table (v2: raw_label preserves the verbatim model class)
    await db.execute('''
      CREATE TABLE detections (
        id TEXT PRIMARY KEY,
        scan_id TEXT NOT NULL,
        x REAL NOT NULL,
        y REAL NOT NULL,
        width REAL NOT NULL,
        height REAL NOT NULL,
        defect_type TEXT NOT NULL,
        confidence REAL NOT NULL,
        estimated_diameter_mm REAL,
        view_angle TEXT,
        raw_label TEXT,
        FOREIGN KEY (scan_id) REFERENCES scans (id) ON DELETE CASCADE
      )
    ''');

    // 4. Grading Results Table (v2: unclassified tracking for models
    // without quality classes)
    await db.execute('''
      CREATE TABLE grading_results (
        id TEXT PRIMARY KEY,
        scan_id TEXT NOT NULL UNIQUE,
        grade_a_percentage REAL NOT NULL,
        urs_percentage REAL NOT NULL,
        average_ai_confidence REAL NOT NULL,
        confidence_status TEXT NOT NULL,
        policy_version TEXT NOT NULL,
        total_onions_count INTEGER NOT NULL,
        grade_a_count INTEGER NOT NULL,
        damaged_count INTEGER NOT NULL,
        rotten_count INTEGER NOT NULL,
        sprouted_count INTEGER NOT NULL,
        undersized_count INTEGER NOT NULL,
        unclassified_count INTEGER NOT NULL DEFAULT 0,
        quality_classification_available INTEGER NOT NULL DEFAULT 1,
        avg_size_mm REAL,
        audit_hash TEXT,
        calculated_at TEXT NOT NULL,
        FOREIGN KEY (scan_id) REFERENCES scans (id) ON DELETE CASCADE
      )
    ''');

    // 5. Sync Queue Table
    await db.execute('''
      CREATE TABLE sync_queue (
        id TEXT PRIMARY KEY,
        scan_id TEXT NOT NULL,
        action TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        retry_count INTEGER NOT NULL DEFAULT 0,
        last_attempt TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL
      )
    ''');

    // 6. Batch Assessments Table (v3: ONE A/B/C/Reject per batch)
    await _createBatchAssessmentsTable(db);
  }

  Future<void> saveScan(ScanSession scan) async {
    final db = await database;
    await db.transaction((txn) async {
      // Upsert scan
      await txn.insert(
        'scans',
        {
          'id': scan.id,
          'lot_number': scan.lotNumber,
          'farmer_name': scan.farmerName,
          'farmer_phone': scan.farmerPhone,
          'procurement_center_id': scan.procurementCenterId,
          'grader_id': scan.graderId,
          'assessed_onions': scan.assessedOnions,
          'sync_status': scan.syncStatus.name,
          'ai_status': scan.aiStatus.name,
          'report_url': scan.reportUrl,
          'audit_hash': scan.auditHash,
          'created_at': scan.createdAt.toIso8601String(),
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );

      // Save images
      for (final img in scan.images) {
        await txn.insert(
          'captured_images',
          {
            'id': img.id,
            'scan_id': scan.id,
            'local_path': img.localPath,
            'remote_storage_url': img.remoteStorageUrl,
            'angle': img.angle.name,
            'sharpness_score': img.sharpnessScore,
            'brightness_score': img.brightnessScore,
            'quality_passed': img.qualityPassed ? 1 : 0,
            'captured_at': img.capturedAt.toIso8601String(),
          },
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
      }

      // Save detections
      for (final det in scan.detections) {
        await txn.insert(
          'detections',
          {
            'id': det.id,
            'scan_id': scan.id,
            'x': det.x,
            'y': det.y,
            'width': det.width,
            'height': det.height,
            'defect_type': det.defectType.name,
            'confidence': det.confidence,
            'estimated_diameter_mm': det.estimatedDiameterMm,
            'view_angle': det.viewAngle,
            'raw_label': det.rawLabel,
          },
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
      }

      // Save grading result
      if (scan.result != null) {
        final res = scan.result!;
        await txn.insert(
          'grading_results',
          {
            'id': res.id,
            'scan_id': scan.id,
            'grade_a_percentage': res.gradeAPercentage,
            'urs_percentage': res.ursPercentage,
            'average_ai_confidence': res.averageAiConfidence,
            'confidence_status': res.confidenceStatus.name,
            'policy_version': res.policyVersion,
            'total_onions_count': res.totalOnionsCount,
            'grade_a_count': res.gradeACount,
            'damaged_count': res.damagedCount,
            'rotten_count': res.rottenCount,
            'sprouted_count': res.sproutedCount,
            'undersized_count': res.undersizedCount,
            'unclassified_count': res.unclassifiedCount,
            'quality_classification_available':
                res.qualityClassificationAvailable ? 1 : 0,
            'avg_size_mm': res.avgSizeMm,
            'audit_hash': res.auditHash,
            'calculated_at': res.calculatedAt.toIso8601String(),
          },
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
      }

      // Save batch assessment (ONE A/B/C/Reject per batch)
      if (scan.batchAssessment != null) {
        final b = scan.batchAssessment!;
        await txn.insert(
          'batch_assessments',
          {
            'id': b.batchId,
            'scan_id': scan.id,
            'final_grade': b.finalGrade.value,
            'assessment_confidence': b.assessmentConfidence,
            'sample_size': b.sampleSize,
            'sample_size_estimated': b.sampleSizeEstimated ? 1 : 0,
            'images_analyzed': b.imagesAnalyzed,
            'observations_json': jsonEncode(b.observations),
            'issues_json':
                jsonEncode(b.visibleQualityIssues.map((e) => e.toJson()).toList()),
            'review_required': b.reviewRequired ? 1 : 0,
            'review_reasons_json': jsonEncode(b.reviewReasons),
            'policy_version': b.policyVersion,
            'roboflow_model': b.roboflowModel,
            'assessment_model': b.assessmentModel,
            'urs_percent': b.ursPercent,
            'assessed_onions_declared': b.assessedOnionsDeclared,
            'calculated_at': b.calculatedAt.toIso8601String(),
          },
          conflictAlgorithm: ConflictAlgorithm.replace,
        );
      }
    });
  }

  Future<List<ScanSession>> getAllScans() async {
    final db = await database;
    final scanMaps = await db.query('scans', orderBy: 'created_at DESC');

    List<ScanSession> sessions = [];
    for (final map in scanMaps) {
      final scanId = map['id'] as String;

      // Load images
      final imageMaps = await db.query(
        'captured_images',
        where: 'scan_id = ?',
        whereArgs: [scanId],
      );
      final images = imageMaps.map((m) => CapturedImageEvidence(
        id: m['id'] as String,
        localPath: m['local_path'] as String,
        remoteStorageUrl: m['remote_storage_url'] as String?,
        angle: SamplingAngle.values.firstWhere((e) => e.name == m['angle']),
        sharpnessScore: (m['sharpness_score'] as num?)?.toDouble(),
        brightnessScore: (m['brightness_score'] as num?)?.toDouble(),
        qualityPassed: (m['quality_passed'] as int) == 1,
        capturedAt: DateTime.parse(m['captured_at'] as String),
      )).toList();

      // Load detections
      final detMaps = await db.query(
        'detections',
        where: 'scan_id = ?',
        whereArgs: [scanId],
      );
      final detections = detMaps.map((m) => DetectionItem(
        id: m['id'] as String,
        x: (m['x'] as num).toDouble(),
        y: (m['y'] as num).toDouble(),
        width: (m['width'] as num).toDouble(),
        height: (m['height'] as num).toDouble(),
        defectType: OnionDefectExtension.fromString(m['defect_type'] as String),
        confidence: (m['confidence'] as num).toDouble(),
        estimatedDiameterMm: (m['estimated_diameter_mm'] as num?)?.toDouble(),
        viewAngle: m['view_angle'] as String?,
        rawLabel: m['raw_label'] as String?,
      )).toList();

      // Load grading result
      final resMaps = await db.query(
        'grading_results',
        where: 'scan_id = ?',
        whereArgs: [scanId],
      );
      GradingResult? result;
      if (resMaps.isNotEmpty) {
        final r = resMaps.first;
        result = GradingResult(
          id: r['id'] as String,
          scanId: r['scan_id'] as String,
          gradeAPercentage: (r['grade_a_percentage'] as num).toDouble(),
          ursPercentage: (r['urs_percentage'] as num).toDouble(),
          averageAiConfidence: (r['average_ai_confidence'] as num).toDouble(),
          confidenceStatus: r['confidence_status'] == 'borderlineReview'
              ? ConfidenceGateStatus.borderlineReview
              : ConfidenceGateStatus.highConfidence,
          policyVersion: r['policy_version'] as String,
          totalOnionsCount: (r['total_onions_count'] as num).toInt(),
          gradeACount: (r['grade_a_count'] as num).toInt(),
          damagedCount: (r['damaged_count'] as num).toInt(),
          rottenCount: (r['rotten_count'] as num).toInt(),
          sproutedCount: (r['sprouted_count'] as num).toInt(),
          undersizedCount: (r['undersized_count'] as num).toInt(),
          unclassifiedCount: (r['unclassified_count'] as num?)?.toInt() ?? 0,
          qualityClassificationAvailable:
              ((r['quality_classification_available'] as num?)?.toInt() ?? 1) == 1,
          avgSizeMm: (r['avg_size_mm'] as num?)?.toDouble(),
          auditHash: r['audit_hash'] as String?,
          calculatedAt: DateTime.parse(r['calculated_at'] as String),
        );
      }

      // Load batch assessment (latest wins; one row per batch id)
      final batchMaps = await db.query(
        'batch_assessments',
        where: 'scan_id = ?',
        whereArgs: [scanId],
        orderBy: 'calculated_at DESC',
        limit: 1,
      );
      BatchAssessmentResult? batchAssessment;
      if (batchMaps.isNotEmpty) {
        final b = batchMaps.first;
        final grade =
            BatchGradeExtension.fromValue(b['final_grade'] as String?);
        if (grade != null) {
          List<String> decodeStrings(Object? value) {
            if (value == null) return [];
            try {
              return (jsonDecode(value as String) as List)
                  .map((e) => e.toString())
                  .toList();
            } catch (_) {
              return [];
            }
          }

          batchAssessment = BatchAssessmentResult(
            batchId: b['id'] as String,
            finalGrade: grade,
            assessmentConfidence:
                (b['assessment_confidence'] as num).toDouble(),
            sampleSize: (b['sample_size'] as num).toInt(),
            sampleSizeEstimated:
                ((b['sample_size_estimated'] as num?)?.toInt() ?? 1) == 1,
            imagesAnalyzed: (b['images_analyzed'] as num).toInt(),
            observations: decodeStrings(b['observations_json']),
            visibleQualityIssues: (() {
              try {
                return (jsonDecode(b['issues_json'] as String) as List)
                    .map((e) => BatchQualityIssue.fromJson(
                        Map<String, dynamic>.from(e as Map)))
                    .toList();
              } catch (_) {
                return <BatchQualityIssue>[];
              }
            })(),
            reviewRequired:
                ((b['review_required'] as num?)?.toInt() ?? 0) == 1,
            reviewReasons: decodeStrings(b['review_reasons_json']),
            policyVersion: b['policy_version'] as String,
            roboflowModel: b['roboflow_model'] as String,
            // Legacy fallback: pre-migration rows used `gemini_model`.
            assessmentModel: ((b['assessment_model'] ?? b['gemini_model'])
                    as String?) ??
                'unknown',
            ursPercent: (b['urs_percent'] as num?)?.toDouble(),
            assessedOnionsDeclared:
                (b['assessed_onions_declared'] as num?)?.toInt(),
            calculatedAt: DateTime.parse(b['calculated_at'] as String),
          );
        }
      }

      sessions.add(ScanSession(
        id: scanId,
        lotNumber: map['lot_number'] as String,
        farmerName: map['farmer_name'] as String,
        farmerPhone: map['farmer_phone'] as String,
        procurementCenterId: map['procurement_center_id'] as String,
        graderId: map['grader_id'] as String,
        assessedOnions: (map['assessed_onions'] as num?)?.toInt(),
        images: images,
        detections: detections,
        result: result,
        batchAssessment: batchAssessment,
        syncStatus: ScanSyncStatus.values.firstWhere(
          (s) => s.name == map['sync_status'],
          orElse: () => ScanSyncStatus.pendingOffline,
        ),
        aiStatus: AiInferenceStatus.values.firstWhere(
          (s) => s.name == (map['ai_status'] as String? ?? 'pendingAi'),
          orElse: () => AiInferenceStatus.pendingAi,
        ),
        reportUrl: map['report_url'] as String?,
        auditHash: map['audit_hash'] as String?,
        createdAt: DateTime.parse(map['created_at'] as String),
      ));
    }

    return sessions;
  }

  Future<void> updateSyncStatus(String scanId, ScanSyncStatus status, {String? reportUrl}) async {
    final db = await database;
    await db.update(
      'scans',
      {
        'sync_status': status.name,
        if (reportUrl != null) 'report_url': reportUrl,
      },
      where: 'id = ?',
      whereArgs: [scanId],
    );
  }

  Future<void> deleteScan(String scanId) async {
    final db = await database;
    // Explicit child cleanup (SQLite FK enforcement is off by default).
    await db.delete('batch_assessments', where: 'scan_id = ?', whereArgs: [scanId]);
    await db.delete('scans', where: 'id = ?', whereArgs: [scanId]);
  }

  Future<void> close() async {
    final db = await database;
    await db.close();
    _database = null;
  }
}
