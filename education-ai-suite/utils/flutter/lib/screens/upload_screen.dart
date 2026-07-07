import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import '../app_config.dart';
import '../entities/upload_entry.dart';
import '../providers/upload_notifier.dart';
import '../widgets/health_banner.dart';
import '../widgets/upload_entry_tile.dart';

/// Upload screen — file picker, upload list, progress per file.
///
/// State architecture (vs React's UploadSection.tsx):
///   _stagedFiles  — local Map<id, PlatformFile> owned by the SCREEN
///                   (React: files are in the UploadEntry directly as a File object)
///                   Flutter can't store PlatformFile in the Riverpod notifier
///                   because Riverpod state must be serialisable/comparable.
///   Riverpod state — List<UploadEntry> owned by UploadNotifier
///                   (React: useState<UploadEntry[]>)
class UploadScreen extends ConsumerStatefulWidget {
  const UploadScreen({super.key});

  @override
  ConsumerState<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends ConsumerState<UploadScreen> {
  /// Maps entry.id → PlatformFile so the screen can hand the file to
  /// UploadNotifier.uploadEntry() when the user presses Upload.
  final Map<String, PlatformFile> _stagedFiles = {};

  // ── File picking ───────────────────────────────────────────────────────────

  Future<void> _pickFiles() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: AppConfig.allowedExtensions.toList(),
    );
    if (result == null || result.files.isEmpty) return;
    _addFiles(result.files);
  }

  void _addFiles(List<PlatformFile> files) {
    // stageFiles() returns the generated entry IDs in the same order as files
    final ids =
        ref.read(uploadNotifierProvider.notifier).stageFiles(files);
    for (int i = 0; i < ids.length && i < files.length; i++) {
      _stagedFiles[ids[i]] = files[i];
    }
  }

  // ── Upload ─────────────────────────────────────────────────────────────────

  void _uploadAll() {
    final entries = ref.read(uploadNotifierProvider);
    final staged =
        entries.where((e) => e.status == TaskStatus.staged).toList();
    final notifier = ref.read(uploadNotifierProvider.notifier);

    for (final entry in staged) {
      final file = _stagedFiles.remove(entry.id);
      if (file != null) {
        // Fire without await — each upload runs independently
        notifier.uploadEntry(entry.id, file);
      }
    }
  }

  // ── Build ──────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final entries = ref.watch(uploadNotifierProvider);
    final notifier = ref.read(uploadNotifierProvider.notifier);
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    final stagedCount =
        entries.where((e) => e.status == TaskStatus.staged).length;
    final isAnyActive = entries.any((e) => e.status.isActive);
    final hasCompleted =
        entries.any((e) => e.status == TaskStatus.completed);

    return Column(
      children: [
        const HealthBanner(),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // ── Pick zone ──────────────────────────────────────────────
                _PickZone(onTap: _pickFiles),
                const SizedBox(height: 12),

                // ── Action row ─────────────────────────────────────────────
                Row(
                  children: [
                    FilledButton.icon(
                      onPressed: stagedCount > 0 && !isAnyActive
                          ? _uploadAll
                          : null,
                      icon: isAnyActive
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.upload, size: 18),
                      label: Text(isAnyActive
                          ? 'Uploading...'
                          : stagedCount > 0
                              ? 'Upload ($stagedCount)'
                              : 'Upload'),
                    ),
                    const SizedBox(width: 8),
                    if (hasCompleted)
                      OutlinedButton.icon(
                        onPressed: notifier.clearCompleted,
                        icon: const Icon(Icons.done_all, size: 18),
                        label: const Text('Clear done'),
                      ),
                    const Spacer(),
                    Text(
                      '${entries.length} file${entries.length == 1 ? '' : 's'}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: cs.onSurface.withValues(alpha: 0.38),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),

                // ── File list ──────────────────────────────────────────────
                Expanded(
                  child: entries.isEmpty
                      ? const _EmptyState()
                      : ListView.builder(
                          itemCount: entries.length,
                          itemBuilder: (_, i) {
                            final e = entries[i];
                            return UploadEntryTile(
                              entry: e,
                              onTagsChanged: e.status == TaskStatus.staged
                                  ? (tags) => notifier.updateEntryTags(
                                      e.id, tags)
                                  : null,
                              onRemove: (e.status == TaskStatus.staged ||
                                      e.status.isTerminal)
                                  ? () {
                                      _stagedFiles.remove(e.id);
                                      notifier.removeEntry(e.id);
                                    }
                                  : null,
                            );
                          },
                        ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

// ─── Private widgets ──────────────────────────────────────────────────────────

class _PickZone extends StatelessWidget {
  final VoidCallback onTap;
  const _PickZone({required this.onTap});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final theme = Theme.of(context);

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        height: 120,
        decoration: BoxDecoration(
          border: Border.all(
            color: cs.primary.withValues(alpha: 0.35),
            width: 1.5,
          ),
          borderRadius: BorderRadius.circular(12),
          color: cs.primary.withValues(alpha: 0.03),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.add_circle_outline,
                size: 30, color: cs.primary.withValues(alpha: 0.75)),
            const SizedBox(height: 8),
            Text(
              'Add files',
              style: theme.textTheme.titleSmall?.copyWith(
                  color: cs.primary, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 3),
            Text(
              'PDF · DOCX · PPTX · TXT · JPG · PNG · MP4 · AVI · MOV · MKV',
              style: theme.textTheme.bodySmall?.copyWith(
                  color: cs.onSurface.withValues(alpha: 0.32), fontSize: 11),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final theme = Theme.of(context);
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.cloud_upload_outlined,
              size: 60, color: cs.primary.withValues(alpha: 0.22)),
          const SizedBox(height: 14),
          Text(
            'No files added yet',
            style: theme.textTheme.titleMedium
                ?.copyWith(color: cs.onSurface.withValues(alpha: 0.32)),
          ),
          const SizedBox(height: 4),
          Text(
            'Click "Add files" to upload documents, images, or videos',
            style: theme.textTheme.bodySmall
                ?.copyWith(color: cs.onSurface.withValues(alpha: 0.22)),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
