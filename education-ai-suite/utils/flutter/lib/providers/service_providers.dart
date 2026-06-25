import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/content_search_api_service.dart';
import '../models/health_status.dart';

// ─── API Service ─────────────────────────────────────────────────────────────

/// Singleton service instance shared across all notifiers.
/// Equivalent of the module-level BASE_URL / CONTENT_SEARCH_API_URL constants
/// and the shared fetch setup in React's api.ts.
final contentSearchApiServiceProvider = Provider<ContentSearchApiService>(
  (ref) => ContentSearchApiService(),
);

// ─── Tags ─────────────────────────────────────────────────────────────────────

/// Global tags list — updated after ingestion completes or file is deleted.
/// Equivalent of csTags in React's uiSlice Redux state.
final tagsProvider = StateProvider<List<String>>((ref) => const []);

// ─── Health ───────────────────────────────────────────────────────────────────

/// Manages GET /api/v1/system/health state.
/// Equivalent of the getCsHealth() call triggered at app start and on retry.
class HealthNotifier extends StateNotifier<HealthStatus> {
  HealthNotifier(this._service) : super(HealthStatus.unknown()) {
    check(); // auto-check on creation
  }

  final ContentSearchApiService _service;

  Future<void> check() async {
    state = HealthStatus.unknown();
    final status = await _service.checkHealth();
    state = status;
  }
}

final healthNotifierProvider =
    StateNotifierProvider<HealthNotifier, HealthStatus>(
  (ref) => HealthNotifier(ref.read(contentSearchApiServiceProvider)),
);
