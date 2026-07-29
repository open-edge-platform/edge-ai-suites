class IngestTaskResult {
  final String status;   // backend string: QUEUED, PROCESSING, COMPLETED, FAILED, etc.
  final int progress;    // 0–100

  const IngestTaskResult({required this.status, this.progress = 0});

  /// Whether the task has reached a terminal state (no more polling needed).
  bool get isTerminal {
    final s = status.toUpperCase();
    return s == 'COMPLETED' || s == 'FAILED' || s == 'ERROR';
  }

  bool get isCompleted => status.toUpperCase() == 'COMPLETED';

  factory IngestTaskResult.fromJson(Map<String, dynamic> json) {
    return IngestTaskResult(
      status: (json['status'] as String?) ?? 'UNKNOWN',
      progress: (json['progress'] as num?)?.toInt() ?? 0,
    );
  }
}
