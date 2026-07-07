enum HealthState { ok, degraded, unreachable, unknown }

class HealthStatus {
  final HealthState state;
  final String label;
  final Map<String, String> services;

  const HealthStatus({
    required this.state,
    required this.label,
    this.services = const {},
  });

  // ── Named constructors ───────────────────────────────────────────────────

  factory HealthStatus.unknown() => const HealthStatus(
        state: HealthState.unknown,
        label: 'Checking service health…',
      );

  factory HealthStatus.unreachable() => const HealthStatus(
        state: HealthState.unreachable,
        label: 'Content Search service unreachable',
      );

  factory HealthStatus.fromJson(Map<String, dynamic> json) {
    // Backend returns {status: "ok"|"degraded"|"error", services: {...}}
    final raw = (json['status'] as String? ?? '').toLowerCase();
    final HealthState state;
    final String label;

    switch (raw) {
      case 'ok':
      case 'healthy':
        state = HealthState.ok;
        label = 'Content Search service is healthy';
        break;
      case 'degraded':
      case 'partial':
        state = HealthState.degraded;
        label = 'Content Search service is degraded';
        break;
      case 'error':
      case 'unhealthy':
        state = HealthState.unreachable;
        label = 'Content Search service reported an error';
        break;
      default:
        state = HealthState.unknown;
        label = 'Content Search status unknown';
    }

    final rawServices = json['services'];
    final Map<String, String> services = {};
    if (rawServices is Map) {
      rawServices.forEach((k, v) => services[k.toString()] = v.toString());
    }

    return HealthStatus(state: state, label: label, services: services);
  }
}
