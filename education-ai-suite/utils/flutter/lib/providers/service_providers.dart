import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/content_search_api_service.dart';
import '../entities/health_status.dart';

/// Singleton service instance shared across all notifiers.
final contentSearchApiServiceProvider = Provider<ContentSearchApiService>(
  (ref) => ContentSearchApiService(),
);

// ─── Tags ─────────────────────────────────────────────────────────────────────

final tagsProvider = StateProvider<List<String>>((ref) => const []);

// ─── Server files state ───────────────────────────────────────────────────────

final serverHasFilesProvider = StateProvider<bool>((ref) => false);

// ─── Health ───────────────────────────────────────────────────────────────────

/// Manages GET /api/v1/system/health state.
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
