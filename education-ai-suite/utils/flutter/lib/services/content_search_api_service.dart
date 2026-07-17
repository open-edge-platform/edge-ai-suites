import 'dart:convert';
import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show debugPrint, kIsWeb;
import '../app_config.dart';
import '../entities/ingest_task_result.dart';
import '../entities/qa_models.dart';
import '../entities/health_status.dart';
import '../entities/file_asset.dart';

/// Result of POST /api/v1/object/upload-ingest
class UploadIngestResult {
  final String taskId;
  final String status;
  final String? fileKey;
  final bool isDuplicate; // true when backend returns code=40901

  const UploadIngestResult({
    required this.taskId,
    required this.status,
    this.fileKey,
    this.isDuplicate = false,
  });
}

/// HTTP service layer for the Content Search RAG pipeline.
/// Key difference from React: uses Dio instead of browser fetch(), which gives
/// us built-in interceptors, upload progress callbacks, and typed exceptions.
class ContentSearchApiService {
  late final Dio _dio;

  ContentSearchApiService() {
    _dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.contentSearchBaseUrl,
        connectTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(minutes: 10), // VLM answer generation
        sendTimeout: const Duration(minutes: 15),    // large video uploads
        headers: {'Accept': 'application/json'},
      ),
    );

     assert(() {
       _dio.interceptors.add(
         LogInterceptor(
           requestHeader: true,
           requestBody: true,
           responseHeader: true,
           responseBody: true,
           logPrint: (o) => debugPrint('[ContentSearch] $o'),
         ),
       );
       return true;
     }());
  }

  // ─── Helper ───────────────────────────────────────────────────────────────

  /// Unwrap the backend's standard {code, data, message} envelope.
  Map<String, dynamic> _data(dynamic body) {
    if (body is Map<String, dynamic>) {
      return body['data'] as Map<String, dynamic>? ?? body;
    }
    return {};
  }

  // ─── Health — GET /api/v1/system/health ───────────────────────────────────

  /// Pre-flight check before any upload.
  /// Equivalent of getCsHealth() in React's api.ts.
  Future<HealthStatus> checkHealth() async {
    try {
      final res = await _dio.get('/api/v1/system/health');
      return HealthStatus.fromJson(res.data as Map<String, dynamic>);
    } catch (_) {
      return HealthStatus.unreachable();
    }
  }

  // ─── Upload + Ingest — POST /api/v1/object/upload-ingest ─────────────────

  /// Upload a file and trigger ingestion in one request.

  /// Corner-case: if isDuplicate=true, caller must call cleanupTask(taskId)
  /// then retry — matches the code=40901 handling in UploadSection.tsx.
  Future<UploadIngestResult> uploadAndIngest(
    PlatformFile file,
    Map<String, dynamic> meta, {
    void Function(int sent, int total)? onSendProgress,
  }) async {
    FormData formData;

    if (kIsWeb) {
      // Web: PlatformFile.path is null — use bytes instead
      final bytes = file.bytes ?? Uint8List(0);
      formData = FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: file.name),
        'meta': jsonEncode(meta),
      });
    } else {
      // Desktop / mobile: stream directly from disk (avoids loading to RAM)
      final path = file.path;
      if (path == null) throw Exception('File path unavailable');
      formData = FormData.fromMap({
        'file': await MultipartFile.fromFile(path, filename: file.name),
        'meta': jsonEncode(meta),
      });
    }

    final res = await _dio.post(
      '/api/v1/object/upload-ingest',
      data: formData,
      onSendProgress: onSendProgress, // drives uploadProgress in UploadEntry
    );

    final body = res.data as Map<String, dynamic>;
    final code = body['code'] as int? ?? 20000;
    final data = body['data'] as Map<String, dynamic>? ?? {};

    if (code == 40901) {
      // Duplicate detected - use actual backend status from existing task
      return UploadIngestResult(
        taskId: data['task_id'] as String? ?? '',
        status: data['status'] as String? ?? 'UNKNOWN',
        fileKey: data['file_key'] as String?,
        isDuplicate: true,
      );
    }

    return UploadIngestResult(
      taskId: data['task_id'] as String? ?? '',
      status: data['status'] as String? ?? 'QUEUED',
      fileKey: data['file_key'] as String?,
    );
  }

  // ─── Task Polling — GET /api/v1/task/query/{task_id} ─────────────────────

  /// Poll ingestion task status every 3 s until isTerminal.
  Future<IngestTaskResult> queryTask(String taskId) async {
    final res = await _dio.get('/api/v1/task/query/$taskId');
    return IngestTaskResult.fromJson(_data(res.data));
  }

  // ─── Cleanup — DELETE /api/v1/object/cleanup-task/{task_id} ──────────────

  Future<void> cleanupTask(String taskId) async {
    try {
      await _dio.delete('/api/v1/object/cleanup-task/$taskId');
    } catch (e) {
      debugPrint('cleanupTask failed (non-critical): $e');
    }
  }

  // ─── Q&A — POST /api/v1/object/qa ────────────────────────────────────────

  /// RAG question answering over ingested content.
  Future<QaResult> askQuestion(QaRequest request) async {
    final res = await _dio.post(
      '/api/v1/object/qa',
      data: request.toJson(),
    );
    return QaResult.fromJson(res.data as Map<String, dynamic>);
  }

  // ─── Tags — GET /api/v1/object/tags ──────────────────────────────────────

  Future<List<String>> getTags() async {
    try {
      final res = await _dio.get('/api/v1/object/tags');
      final body = res.data as Map<String, dynamic>;
      final data = body['data'] as List<dynamic>?;
      return data?.map((e) => e.toString()).toList() ?? [];
    } catch (_) {
      return [];
    }
  }

  // ─── Files list — GET /api/v1/object/files/list ───────────────────────────

  Future<List<FileAsset>> getFilesList({
    int page = 1,
    int pageSize = 50,
    String? fileType,
  }) async {
    try {
      final res = await _dio.get(
        '/api/v1/object/files/list',
        queryParameters: {
          'page': page,
          'page_size': pageSize,
          if (fileType != null) 'file_type': fileType,
        },
      );
      final outer = res.data as Map<String, dynamic>;
      final data = outer['data'] as Map<String, dynamic>? ?? {};
      final files = data['files'] as List<dynamic>? ?? [];
      return files
          .whereType<Map<String, dynamic>>()
          .map(FileAsset.fromJson)
          .toList();
    } catch (_) {
      return [];
    }
  }

  // ─── Delete file — DELETE /api/v1/object/files/{file_hash} ───────────────

  Future<bool> deleteFile(String fileHash) async {
    try {
      await _dio.delete('/api/v1/object/files/$fileHash');
      return true;
    } catch (_) {
      return false;
    }
  }
}
