import 'package:flutter_dotenv/flutter_dotenv.dart';

/// Central configuration — reads from assets/.env
/// Unlike React/Vite, Flutter has no dev-proxy, so BOTH URLs must be explicit.
class AppConfig {
  AppConfig._();
  /// Content Search Service — RAG pipeline (upload, ingest, Q&A)
  static String get contentSearchBaseUrl => dotenv.env['CONTENT_SEARCH_API_URL'] ?? 'http://127.0.0.1:9011';
  /// Main Smart Classroom API (not used in this POC)
  static String get mainApiBaseUrl =>
      dotenv.env['MAIN_API_URL'] ?? 'http://127.0.0.1:8000';

  /// Allowed file extensions 
  static const Set<String> allowedExtensions = {
    // Documents
    'pdf', 'txt', 'docx', 'doc', 'pptx', 'ppt', 'xlsx', 'xls',
    // Images
    'jpg', 'jpeg', 'png',
    // Videos
    'mp4', 'avi', 'mov', 'mkv',
  };

  /// Task polling interval 
  static const int pollIntervalMs = 3000;

  /// Max time to wait for ingestion before marking timed out locally
  static const Duration pollTimeout = Duration(minutes: 10);

  /// Max conversation history turns sent to /qa endpoint
  /// Must match backend QA_MAX_HISTORY_TURNS env var (default: 3)
  static const int maxHistoryTurns = 3;
}
