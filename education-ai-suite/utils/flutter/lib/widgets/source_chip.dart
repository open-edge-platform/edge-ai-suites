import 'package:flutter/material.dart';
import '../models/qa_models.dart';

/// Small chip showing a source citation on an assistant message.
/// Equivalent of the source label rendering in React's QASection.tsx
/// (getSourceLabel / getSourceTypeIcon functions).
class SourceChip extends StatelessWidget {
  final QaSource source;
  const SourceChip({super.key, required this.source});

  @override
  Widget build(BuildContext context) {
    final type = (source.type ?? '').toLowerCase();
    final Color color;
    final IconData icon;

    if (type == 'video') {
      color = Colors.purple.shade400;
      icon = Icons.video_file_outlined;
    } else if (type == 'image') {
      color = Colors.teal.shade400;
      icon = Icons.image_outlined;
    } else {
      color = Colors.blue.shade500;
      icon = Icons.description_outlined;
    }

    final label = source.formattedTimestamp != null
        ? '${source.displayName} @ ${source.formattedTimestamp}'
        : source.displayName;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              label,
              style: TextStyle(
                fontSize: 11,
                color: color,
                fontWeight: FontWeight.w500,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (source.score != null) ...[
            const SizedBox(width: 4),
            Text(
              '${source.score!.toStringAsFixed(0)}%',
              style: TextStyle(
                fontSize: 10,
                color: color.withOpacity(0.7),
                fontWeight: FontWeight.w400,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
