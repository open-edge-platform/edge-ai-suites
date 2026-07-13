// ─── TaskStatus ───────────────────────────────────────────────────────────────

enum TaskStatus {
  staged,
  uploading,
  queued,
  processing,
  completed,
  failed,
  alreadyExists;

  /// Map the backend status string to a [TaskStatus].
  static TaskStatus fromBackendString(String s) {
    switch (s.toUpperCase()) {
      case 'QUEUED':
        return TaskStatus.queued;
      case 'PROCESSING':
        return TaskStatus.processing;
      case 'COMPLETED':
        return TaskStatus.completed;
      case 'FAILED':
      case 'ERROR':
        return TaskStatus.failed;
      case 'ALREADY_EXISTS':
        return TaskStatus.alreadyExists;
      default:
        return TaskStatus.queued;
    }
  }

  /// Whether the entry is still in-flight (blocks UI actions like remove).
  bool get isActive =>
      this == TaskStatus.uploading ||
      this == TaskStatus.queued ||
      this == TaskStatus.processing;

  /// Whether the entry has reached a terminal state (no further transitions).
  bool get isTerminal =>
      this == TaskStatus.completed ||
      this == TaskStatus.failed ||
      this == TaskStatus.alreadyExists;

  /// Display label shown in _StatusBadge.
  String get label {
    switch (this) {
      case TaskStatus.staged:
        return 'Staged';
      case TaskStatus.uploading:
        return 'Uploading';
      case TaskStatus.queued:
        return 'Queued';
      case TaskStatus.processing:
        return 'Processing';
      case TaskStatus.completed:
        return 'Completed';
      case TaskStatus.failed:
        return 'Failed';
      case TaskStatus.alreadyExists:
        return 'Duplicate';
    }
  }
}

// ─── UploadEntry ─────────────────────────────────────────────────────────────

/// Tracks one file through the full upload → ingest lifecycle.
class UploadEntry {
  final String id;
  final String filename;
  final String extension;      // lowercase, no dot (e.g. "pdf")
  final int fileSize;          // bytes
  final TaskStatus status;
  final String? taskId;
  final String? fileKey;
  final double uploadProgress; // 0.0 – 1.0 during upload phase
  final int progress;          // 0–100 from task polling
  final String? error;
  final List<String> tags;     // user-defined labels sent in meta at ingest time

  const UploadEntry({
    required this.id,
    required this.filename,
    required this.extension,
    required this.fileSize,
    required this.status,
    this.taskId,
    this.fileKey,
    this.uploadProgress = 0.0,
    this.progress = 0,
    this.error,
    this.tags = const [],
  });

  /// Human-readable file type label derived from [extension].
  String get fileTypeLabel {
    switch (extension.toLowerCase()) {
      case 'pdf':
        return 'PDF';
      case 'mp4':
      case 'mkv':
      case 'avi':
      case 'mov':
        return 'Video';
      case 'mp3':
      case 'wav':
      case 'aac':
      case 'm4a':
        return 'Audio';
      case 'jpg':
      case 'jpeg':
      case 'png':
      case 'gif':
      case 'webp':
        return 'Image';
      case 'doc':
      case 'docx':
        return 'Word';
      case 'ppt':
      case 'pptx':
        return 'PowerPoint';
      case 'txt':
        return 'Text';
      default:
        return extension.isEmpty ? 'File' : extension.toUpperCase();
    }
  }

  String get formattedSize {
    if (fileSize < 1024) return '$fileSize B';
    if (fileSize < 1024 * 1024) {
      return '${(fileSize / 1024).toStringAsFixed(1)} KB';
    }
    if (fileSize < 1024 * 1024 * 1024) {
      return '${(fileSize / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(fileSize / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }

  UploadEntry copyWith({
    String? taskId,
    String? fileKey,
    TaskStatus? status,
    int? progress,
    double? uploadProgress,
    String? error,
    List<String>? tags,
  }) {
    return UploadEntry(
      id: id,
      filename: filename,
      extension: extension,
      fileSize: fileSize,
      status: status ?? this.status,
      taskId: taskId ?? this.taskId,
      fileKey: fileKey ?? this.fileKey,
      uploadProgress: uploadProgress ?? this.uploadProgress,
      progress: progress ?? this.progress,
      error: error ?? this.error,
      tags: tags ?? this.tags,
    );
  }
}
