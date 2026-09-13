// lib/models/user_model.dart

enum UserRole {
  farmer,
  grader,
  admin,
}

class User {
  final String id;
  final String name;
  final String phone;
  final UserRole role;
  final String procurementCenterId;
  final DateTime createdAt;

  User({
    required this.id,
    required this.name,
    required this.phone,
    required this.role,
    required this.procurementCenterId,
    DateTime? createdAt,
  }) : createdAt = createdAt ?? DateTime.now();

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'phone': phone,
    'role': role.name,
    'procurement_center_id': procurementCenterId,
    'created_at': createdAt.toIso8601String(),
  };

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as String,
      name: json['name'] as String,
      phone: json['phone'] as String,
      role: UserRole.values.firstWhere(
        (r) => r.name == json['role'],
        orElse: () => UserRole.farmer,
      ),
      procurementCenterId: json['procurement_center_id'] as String? ?? 'APMC-001',
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}
