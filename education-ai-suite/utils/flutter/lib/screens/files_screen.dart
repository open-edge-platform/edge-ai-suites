import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../entities/file_asset.dart';
import '../providers/service_providers.dart';

class FilesScreen extends ConsumerStatefulWidget {
  const FilesScreen({super.key});

  @override
  ConsumerState<FilesScreen> createState() => _FilesScreenState();
}

class _FilesScreenState extends ConsumerState<FilesScreen> {
  List<FileAsset> _files = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final svc = ref.read(contentSearchApiServiceProvider);
      final files = await svc.getFilesList();
      if (mounted) {
        setState(() {
          _files = files;
          _loading = false;
        });
        ref.read(serverHasFilesProvider.notifier).state = files.isNotEmpty;
        if (files.isEmpty) {
          ref.read(tagsProvider.notifier).state = [];
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
        _error = e.toString();
        _loading = false;
      });
      }
    }
  }

  Future<void> _delete(FileAsset file) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete file'),
        content: Text(
          'Remove "${file.fileName}" from storage and the vector index?\nThis cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;

    final svc = ref.read(contentSearchApiServiceProvider);
    final ok = await svc.deleteFile(file.fileHash);

    if (ok && mounted) {
      setState(() =>
          _files.removeWhere((f) => f.fileHash == file.fileHash));
      // Refresh tags and server-files state after deletion
      final tags = await svc.getTags();
      ref.read(tagsProvider.notifier).state = tags;
      ref.read(serverHasFilesProvider.notifier).state = _files.isNotEmpty;
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('"${file.fileName}" deleted'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Column(
      children: [
        // ── Toolbar ─────────────────────────────────────────────────────────
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 12, 0),
          child: Row(
            children: [
              Text(
                '${_files.length} file${_files.length == 1 ? '' : 's'} indexed',
                style: theme.textTheme.titleSmall
                    ?.copyWith(color: cs.onSurface.withValues(alpha: 0.5)),
              ),
              const Spacer(),
              IconButton.outlined(
                onPressed: _loading ? null : _load,
                icon: _loading
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child:
                            CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.refresh, size: 18),
                tooltip: 'Refresh',
              ),
            ],
          ),
        ),

        // ── Content ──────────────────────────────────────────────────────────
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? _ErrorState(error: _error!, onRetry: _load)
                  : _files.isEmpty
                      ? _EmptyState()
                      : ListView.separated(
                          padding: const EdgeInsets.all(16),
                          itemCount: _files.length,
                          separatorBuilder: (_, __) =>
                              const SizedBox(height: 6),
                          itemBuilder: (_, i) => _FileTile(
                            file: _files[i],
                            onDelete: () => _delete(_files[i]),
                          ),
                        ),
        ),
      ],
    );
  }
}

// ─── Sub-widgets ─────────────────────────────────────────────────────────────

class _FileTile extends StatelessWidget {
  final FileAsset file;
  final VoidCallback onDelete;

  const _FileTile({required this.file, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Card(
      child: ListTile(
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
        leading: _TypeIcon(type: file.fileTypeLabel),
        title: Text(
          file.fileName,
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: Text(
          '${file.fileTypeLabel} · ${file.formattedSize}'
          '${file.indexed ? ' · ${file.totalVectors} vectors' : ''}',
          style: theme.textTheme.bodySmall
              ?.copyWith(color: cs.onSurface.withValues(alpha: 0.5)),
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [

            IconButton(
              onPressed: onDelete,
              icon: Icon(Icons.delete_outline,
                  size: 18, color: cs.error.withValues(alpha: 0.65)),
              tooltip: 'Delete',
            ),
          ],
        ),
      ),
    );
  }
}

class _TypeIcon extends StatelessWidget {
  final String type;
  const _TypeIcon({required this.type});

  @override
  Widget build(BuildContext context) {
    final IconData icon;
    final Color color;
    switch (type) {
      case 'Video':
        icon = Icons.video_file_outlined;
        color = Colors.purple.shade400;
        break;
      case 'Image':
        icon = Icons.image_outlined;
        color = Colors.teal.shade400;
        break;
      case 'PDF':
        icon = Icons.picture_as_pdf_outlined;
        color = Colors.red.shade400;
        break;
      default:
        icon = Icons.description_outlined;
        color = Colors.blue.shade500;
    }
    return Container(
      width: 38,
      height: 38,
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Icon(icon, color: color, size: 21),
    );
  }
}

class _EmptyState extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final theme = Theme.of(context);
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.folder_open_outlined,
              size: 56, color: cs.primary.withValues(alpha: 0.22)),
          const SizedBox(height: 14),
          Text('No files indexed yet',
              style: theme.textTheme.titleMedium
                  ?.copyWith(color: cs.onSurface.withValues(alpha: 0.32))),
          const SizedBox(height: 4),
          Text('Upload files in the Upload tab',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: cs.onSurface.withValues(alpha: 0.22))),
        ],
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String error;
  final VoidCallback onRetry;
  const _ErrorState({required this.error, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline,
                size: 48, color: cs.error.withValues(alpha: 0.6)),
            const SizedBox(height: 10),
            Text('Failed to load files',
                style: theme.textTheme.titleSmall),
            const SizedBox(height: 4),
            Text(error,
                style: theme.textTheme.bodySmall
                    ?.copyWith(color: cs.error.withValues(alpha: 0.6)),
                textAlign: TextAlign.center),
            const SizedBox(height: 14),
            TextButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}
