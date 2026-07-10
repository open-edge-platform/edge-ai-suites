import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../entities/health_status.dart';
import '../providers/service_providers.dart';

class HealthBanner extends ConsumerWidget {
  const HealthBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final health = ref.watch(healthNotifierProvider);

    Color bg;
    Color fg;
    IconData icon;

    switch (health.state) {
      case HealthState.ok:
        bg = Colors.green.shade50;
        fg = Colors.green.shade800;
        icon = Icons.check_circle_outline;
        break;
      case HealthState.degraded:
        bg = Colors.orange.shade50;
        fg = Colors.orange.shade800;
        icon = Icons.warning_amber_outlined;
        break;
      case HealthState.unreachable:
        bg = Colors.red.shade50;
        fg = Colors.red.shade800;
        icon = Icons.error_outline;
        break;
      case HealthState.unknown:
        bg = Colors.grey.shade100;
        fg = Colors.grey.shade600;
        icon = Icons.hourglass_empty_outlined;
        break;
    }

    return Material(
      color: bg,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
        child: Row(
          children: [
            health.state == HealthState.unknown
                ? SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: fg,
                    ),
                  )
                : Icon(icon, size: 15, color: fg),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                health.label,
                style: TextStyle(
                  fontSize: 12,
                  color: fg,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            // Service detail tooltip
            if (health.services.isNotEmpty)
              Tooltip(
                message: health.services.entries
                    .map((e) => '${e.key}: ${e.value}')
                    .join('\n'),
                child: Icon(Icons.info_outline,
                    size: 15, color: fg.withValues(alpha: 0.6)),
              ),
            const SizedBox(width: 4),
            // Retry button
            TextButton(
              onPressed: () =>
                  ref.read(healthNotifierProvider.notifier).check(),
              style: TextButton.styleFrom(
                foregroundColor: fg,
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                minimumSize: const Size(0, 28),
                textStyle: const TextStyle(fontSize: 12),
              ),
              child: const Text('Refresh'),
            ),
          ],
        ),
      ),
    );
  }
}
