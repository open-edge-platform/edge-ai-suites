import 'package:flutter/material.dart';
import '../models/upload_entry.dart';

/// Displays one file's upload state as a card row.
/// Equivalent of the per-entry row rendering in React's UploadSection.tsx.
class UploadEntryTile extends StatelessWidget {
  final UploadEntry entry;
  final VoidCallback? onRemove;

  const UploadEntryTile({
    super.key,
    required this.entry,
    this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _FileTypeIcon(extension: entry.extension),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Filename + status badge
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Text(
                          entry.filename,
                          style: theme.textTheme.bodyMedium
                              ?.copyWith(fontWeight: FontWeight.w600),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 6),
                      _StatusBadge(status: entry.status),
                    ],
                  ),
                  const SizedBox(height: 2),
                  // File meta
                  Text(
                    '${entry.fileTypeLabel} · ${entry.formattedSize}',
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: cs.onSurface.withOpacity(0.5)),
                  ),
                  // Upload progress bar (multipart in-flight)
                  if (entry.status == TaskStatus.uploading) ...[
                    const SizedBox(height: 8),
                    LinearProgressIndicator(
                      value: entry.uploadProgress > 0
                          ? entry.uploadProgress
                          : null,
                      color: cs.primary,
                      backgroundColor: cs.primary.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      entry.uploadProgress > 0
                          ? 'Uploading ${(entry.uploadProgress * 100).toStringAsFixed(0)}%'
                          : 'Uploading...',
                      style: theme.textTheme.bodySmall
                          ?.copyWith(color: cs.primary, fontSize: 11),
                    ),
                  ],
                  // Ingest/index progress bar (task polling)
                  if (entry.status == TaskStatus.processing) ...[
                    const SizedBox(height: 8),
                    LinearProgressIndicator(
                      value: entry.progress > 0
                          ? entry.progress / 100.0
                          : null,
                      color: cs.tertiary,
                      backgroundColor: cs.tertiary.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Indexing ${entry.progress}%',
                      style: theme.textTheme.bodySmall?.copyWith(
                          color: cs.tertiary, fontSize: 11),
                    ),
                  ],
                  // Queued indicator
                  if (entry.status == TaskStatus.queued) ...[
                    const SizedBox(height: 6),
                    Text(
                      'Waiting for embedder...',
                      style: theme.textTheme.bodySmall?.copyWith(
                          color: Colors.orange.shade700, fontSize: 11),
                    ),
                  ],
                  // Error message
                  if (entry.status == TaskStatus.failed &&
                      entry.error != null) ...[
                    const SizedBox(height: 6),
                    Text(
                      entry.error!,
                      style: theme.textTheme.bodySmall
                          ?.copyWith(color: cs.error, fontSize: 11),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
            // Remove button (only when not actively processing)
            if (onRemove != null)
              IconButton(
                onPressed: onRemove,
                icon: const Icon(Icons.close, size: 16),
                color: Colors.grey.shade500,
                tooltip: 'Remove',
                padding: EdgeInsets.zero,
                constraints:
                    const BoxConstraints(minWidth: 28, minHeight: 28),
              ),
          ],
        ),
      ),
    );
  }
}

// ─── Sub-widgets ─────────────────────────────────────────────────────────────

class _FileTypeIcon extends StatelessWidget {
  final String extension;
  const _FileTypeIcon({required this.extension});

  @override
  Widget build(BuildContext context) {
    final ext = extension.toLowerCase();
    final IconData icon;
    final Color color;

    if (['mp4', 'avi', 'mov', 'mkv'].contains(ext)) {
      icon = Icons.video_file_outlined;
      color = Colors.purple.shade400;
    } else if (['jpg', 'jpeg', 'png'].contains(ext)) {
      icon = Icons.image_outlined;
      color = Colors.teal.shade400;
    } else if (ext == 'pdf') {
      icon = Icons.picture_as_pdf_outlined;
      color = Colors.red.shade400;
    } else {
      icon = Icons.description_outlined;
      color = Colors.blue.shade500;
    }

    return Container(
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(icon, color: color, size: 22),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  final TaskStatus status;
  const _StatusBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    final Color bg;
    final Color fg;
    Widget? leading;

    switch (status) {
      case TaskStatus.staged:
        bg = Colors.grey.shade100;
        fg = Colors.grey.shade600;
        break;
      case TaskStatus.uploading:
        bg = Colors.blue.shade50;
        fg = Colors.blue.shade700;
        leading = SizedBox(
          width: 10,
          height: 10,
          child: CircularProgressIndicator(
              strokeWidth: 1.5, color: Colors.blue.shade700),
        );
        break;
      case TaskStatus.queued:
        bg = Colors.orange.shade50;
        fg = Colors.orange.shade800;
        break;
      case TaskStatus.processing:
        bg = Colors.blue.shade50;
        fg = Colors.blue.shade700;
        leading = SizedBox(
          width: 10,
          height: 10,
          child: CircularProgressIndicator(
              strokeWidth: 1.5, color: Colors.blue.shade700),
        );
        break;
      case TaskStatus.completed:
        bg = Colors.green.shade50;
        fg = Colors.green.shade700;
        leading = Icon(Icons.check, size: 11, color: Colors.green.shade700);
        break;
      case TaskStatus.failed:
        bg = Colors.red.shade50;
        fg = Colors.red.shade700;
        leading =
            Icon(Icons.error_outline, size: 11, color: Colors.red.shade700);
        break;
      case TaskStatus.alreadyExists:
        bg = Colors.grey.shade100;
        fg = Colors.grey.shade600;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (leading != null) ...[leading, const SizedBox(width: 4)],
          Text(
            status.label,
            style: TextStyle(
                fontSize: 10, fontWeight: FontWeight.w600, color: fg),
          ),
        ],
      ),
    );
  }
}
