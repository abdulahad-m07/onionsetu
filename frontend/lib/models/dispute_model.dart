// lib/models/dispute_model.dart

enum DisputeStatus {
  pendingReview,
  inReview,
  upheld, // Resolution favored farmer / revised grade
  rejected, // Original grade maintained
}

class DisputeRecord {
  final String id;
  final String scanId;
  final String filedByUserId;
  final String reason;
  final List<String> evidenceUrls;
  final DisputeStatus status;
  final String? reviewerNotes;
  final String? reviewerId;
  final String? revisedGradeId;
  final DateTime createdAt;
  final DateTime? resolvedAt;

  DisputeRecord({
    required this.id,
    required this.scanId,
    required this.filedByUserId,
    required this.reason,
    this.evidenceUrls = const [],
    this.status = DisputeStatus.pendingReview,
    this.reviewerNotes,
    this.reviewerId,
    this.revisedGradeId,
    DateTime? createdAt,
    this.resolvedAt,
  }) : createdAt = createdAt ?? DateTime.now();

  Map<String, dynamic> toJson() => {
    'id': id,
    'scan_id': scanId,
    'filed_by_user_id': filedByUserId,
    'reason': reason,
    'evidence_urls': evidenceUrls,
    'status': status.name,
    'reviewer_notes': reviewerNotes,
    'reviewer_id': reviewerId,
    'revised_grade_id': revisedGradeId,
    'created_at': createdAt.toIso8601String(),
    'resolved_at': resolvedAt?.toIso8601String(),
  };

  factory DisputeRecord.fromJson(Map<String, dynamic> json) {
    return DisputeRecord(
      id: json['id'] as String,
      scanId: json['scan_id'] as String,
      filedByUserId: json['filed_by_user_id'] as String,
      reason: json['reason'] as String,
      evidenceUrls: (json['evidence_urls'] as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
      status: DisputeStatus.values.firstWhere(
        (s) => s.name == json['status'],
        orElse: () => DisputeStatus.pendingReview,
      ),
      reviewerNotes: json['reviewer_notes'] as String?,
      reviewerId: json['reviewer_id'] as String?,
      revisedGradeId: json['revised_grade_id'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      resolvedAt: json['resolved_at'] != null ? DateTime.parse(json['resolved_at'] as String) : null,
    );
  }
}
