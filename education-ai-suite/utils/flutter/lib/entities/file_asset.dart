class FileAsset {
  final String fileName;
  final String fileHash;    // SHA-256 hex (64 chars) — used for deletion
  final String fileType;    // "document" | "video" | "image"
  final int fileSizeBytes;
  final bool indexed;
  final int totalVectors;

  const FileAsset({
    required this.fileName,
    required this.fileHash,
    required this.fileType,
    required this.fileSizeBytes,
    required this.indexed,
    required this.totalVectors,
  });

  // ── Derived display helpers ──────────────────────────────────────────────

  String get fileTypeLabel {
    switch (fileType.toLowerCase()) {
      case 'video':
        return 'Video';
      case 'image':
        return 'Image';
      default:
        return 'Document';
    }
  }

  String get formattedSize {
    if (fileSizeBytes <= 0) return '—';
    if (fileSizeBytes < 1024) return '$fileSizeBytes B';
    if (fileSizeBytes < 1024 * 1024) {
      return '${(fileSizeBytes / 1024).toStringAsFixed(1)} KB';
    }
    if (fileSizeBytes < 1024 * 1024 * 1024) {
      return '${(fileSizeBytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(fileSizeBytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }

  factory FileAsset.fromJson(Map<String, dynamic> json) {
    final index = json['index'] as Map<String, dynamic>? ?? {};
    final meta  = json['meta']  as Map<String, dynamic>? ?? {};

    String fileType = (meta['type'] as String?)?.toLowerCase() ?? '';
    if (fileType.isEmpty) {
      final ct = (json['content_type'] as String? ?? '').toLowerCase();
      if (ct.startsWith('video/')) {
        fileType = 'video';
      } else if (ct.startsWith('image/')) {
        fileType = 'image';
      } else {
        fileType = 'document';
      }
    }

    return FileAsset(
      fileName:      (json['file_name'] as String?) ?? '',
      fileHash:      (json['file_hash'] as String?) ?? '',
      fileType:      fileType,
      fileSizeBytes: (json['size_bytes'] as num?)?.toInt() ?? 0,
      indexed:       (index['indexed'] as bool?) ?? false,
      totalVectors:  (index['vector_count'] as num?)?.toInt() ?? 0,
    );
  }
}
