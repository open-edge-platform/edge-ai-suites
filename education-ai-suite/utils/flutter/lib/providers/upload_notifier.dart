import 'dart:async';
import 'package:file_picker/file_picker.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app_config.dart';
import '../models/upload_entry.dart';
import '../models/ingest_task_result.dart';
import '../services/content_search_api_service.dart';
import 'service_providers.dart';

/// Manages the list of UploadEntry objects and their full lifecycle:
///   staged → uploading → queued → processing → completed / failed
///
/// Flutter equivalent of React's UploadSection.tsx state + useEffect hooks:
///   useState<UploadEntry[]>     → StateNotifier<List<UploadEntry>>
///   setInterval / clearInterval → Timer.periodic / timer.cancel()
///   useEffect cleanup           → dispose()
class UploadNotifier extends StateNotifier<List<UploadEntry>> {
  UploadNotifier(this._ref) : super(const []);

  final Ref _ref;

  /// Active polling timers — one per entry.id while status is QUEUED/PROCESSING.
  /// Equivalent of the pollTimers ref in React's UploadSection.tsx.
  final Map<String, Timer> _pollTimers = {};
  final Map<String, DateTime> _pollStartTimes = {};
  int _idCounter = 0;

  String _genId() =>
      'e_${DateTime.now().millisecondsSinceEpoch}_${_idCounter++}';

  // ── Stage files (add to list before upload) ────────────────────────────────

  /// Add picked files to state with STAGED status.
  /// Returns the generated IDs so the screen can map id → PlatformFile.
  List<String> stageFiles(List<PlatformFile> files) {
    final newEntries = files.map((file) {
      final ext = file.name.contains('.')
          ? file.name.split('.').last.toLowerCase()
          : '';
      return UploadEntry(
        id: _genId(),
        filename: file.name,
        extension: ext,
        fileSize: file.size,
        status: TaskStatus.staged,
      );
    }).toList();

    state = [...state, ...newEntries];
    return newEntries.map((e) => e.id).toList();
  }

  // ── Upload one file ────────────────────────────────────────────────────────

  /// Upload + ingest a single file. Handles the duplicate (40901) corner case.
  /// Called from UploadScreen — the screen owns the PlatformFile reference.
  Future<void> uploadEntry(String entryId, PlatformFile file) async {
    _updateEntry(entryId, status: TaskStatus.uploading, uploadProgress: 0.0);

    final service = _ref.read(contentSearchApiServiceProvider);
    final ext = file.name.contains('.')
        ? file.name.split('.').last.toLowerCase()
        : '';
    final meta = <String, dynamic>{
      'file_name': file.name,
      'type': _inferType(ext),
    };

    try {
      var result = await service.uploadAndIngest(
        file,
        meta,
        onSendProgress: (sent, total) {
          if (total > 0) {
            _updateEntry(entryId, uploadProgress: sent / total);
          }
        },
      );

      // ── Duplicate handling (code=40901) ──────────────────────────────────
      // Backend returns the stale task_id. Clean it up, then retry.
      // Mirrors the if (data.code === 40901) block in React's UploadSection.tsx.
      if (result.isDuplicate) {
        if (result.taskId.isNotEmpty) {
          await service.cleanupTask(result.taskId);
        }
        result = await service.uploadAndIngest(file, meta);
      }

      _updateEntry(
        entryId,
        taskId: result.taskId,
        fileKey: result.fileKey,
        status: TaskStatus.fromBackendString(result.status),
        uploadProgress: 1.0,
      );

      // Start polling if a task was created
      if (result.taskId.isNotEmpty) {
        _startPolling(entryId, result.taskId);
      }
    } on Exception catch (e) {
      _updateEntry(
        entryId,
        status: TaskStatus.failed,
        error: e.toString().replaceFirst('Exception: ', ''),
        uploadProgress: 0.0,
      );
    }
  }

  // ── Task polling ───────────────────────────────────────────────────────────

  /// Poll GET /api/v1/task/query/{taskId} every 3 s until terminal.
  ///
  /// React equivalent:
  ///   const id = setInterval(async () => { ... }, POLL_INTERVAL_MS);
  ///   return () => clearInterval(id);  // useEffect cleanup
  ///
  /// Flutter:
  ///   _pollTimers[entryId] = Timer.periodic(...)
  ///   timer.cancel() in dispose()
  void _startPolling(String entryId, String taskId) {
    _pollStartTimes[entryId] = DateTime.now();
    _pollTimers[entryId]?.cancel();

    _pollTimers[entryId] = Timer.periodic(
      Duration(milliseconds: AppConfig.pollIntervalMs),
      (timer) async {
        // Guard: local timeout (10 min) — backend may be unresponsive
        final start = _pollStartTimes[entryId];
        if (start != null &&
            DateTime.now().difference(start) > AppConfig.pollTimeout) {
          timer.cancel();
          _pollTimers.remove(entryId);
          _pollStartTimes.remove(entryId);
          _updateEntry(
            entryId,
            status: TaskStatus.failed,
            error:
                'Timed out after ${AppConfig.pollTimeout.inMinutes} min — check backend logs',
          );
          return;
        }

        try {
          final service = _ref.read(contentSearchApiServiceProvider);
          final result = await service.queryTask(taskId);

          _updateEntry(
            entryId,
            status: TaskStatus.fromBackendString(result.status),
            progress: result.progress,
          );

          if (result.isTerminal) {
            timer.cancel();
            _pollTimers.remove(entryId);
            _pollStartTimes.remove(entryId);

            // Refresh tags list after successful indexing
            if (result.isCompleted) {
              _refreshTags();
            }
          }
        } catch (_) {
          // Network blip during poll — keep retrying until timeout
        }
      },
    );
  }

  Future<void> _refreshTags() async {
    final tags =
        await _ref.read(contentSearchApiServiceProvider).getTags();
    _ref.read(tagsProvider.notifier).state = tags;
  }

  // ── Remove / clear ─────────────────────────────────────────────────────────

  void removeEntry(String entryId) {
    _pollTimers[entryId]?.cancel();
    _pollTimers.remove(entryId);
    _pollStartTimes.remove(entryId);
    state = state.where((e) => e.id != entryId).toList();
  }

  void clearCompleted() {
    final ids = state
        .where((e) => e.status == TaskStatus.completed)
        .map((e) => e.id)
        .toSet();
    for (final id in ids) {
      _pollTimers[id]?.cancel();
      _pollTimers.remove(id);
    }
    state = state.where((e) => !ids.contains(e.id)).toList();
  }

  // ── Internal state mutation ────────────────────────────────────────────────

  void _updateEntry(
    String id, {
    String? taskId,
    String? fileKey,
    TaskStatus? status,
    int? progress,
    double? uploadProgress,
    String? error,
  }) {
    state = [
      for (final e in state)
        if (e.id == id)
          e.copyWith(
            taskId: taskId,
            fileKey: fileKey,
            status: status,
            progress: progress,
            uploadProgress: uploadProgress,
            error: error,
          )
        else
          e,
    ];
  }

  static String _inferType(String ext) {
    if (['mp4', 'avi', 'mov', 'mkv'].contains(ext)) return 'video';
    if (['jpg', 'jpeg', 'png'].contains(ext)) return 'image';
    return 'document';
  }

  // ── Dispose — cancel ALL timers (equivalent to useEffect cleanup) ──────────

  @override
  void dispose() {
    for (final timer in _pollTimers.values) {
      timer.cancel();
    }
    _pollTimers.clear();
    _pollStartTimes.clear();
    super.dispose();
  }
}

// ─── Provider ────────────────────────────────────────────────────────────────

final uploadNotifierProvider =
    StateNotifierProvider<UploadNotifier, List<UploadEntry>>(
  (ref) => UploadNotifier(ref),
);

// ─── Derived providers (computed from upload state) ───────────────────────────
// Equivalent of csHasUploads / csUploadsComplete / csProcessing in Redux uiSlice

final hasUploadsProvider = Provider<bool>(
  (ref) => ref.watch(uploadNotifierProvider).isNotEmpty,
);

final hasCompletedUploadsProvider = Provider<bool>(
  (ref) => ref
      .watch(uploadNotifierProvider)
      .any((e) => e.status == TaskStatus.completed),
);

final isAnyUploadActiveProvider = Provider<bool>(
  (ref) =>
      ref.watch(uploadNotifierProvider).any((e) => e.status.isActive),
);
