import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/qa_notifier.dart';
import '../providers/upload_notifier.dart';
import '../providers/service_providers.dart';
import '../widgets/chat_bubble.dart';

/// Q&A chat screen — multi-turn conversation over ingested content.
///
/// Mapping to React's QASection.tsx:
///   messages: ChatEntry[]     → ref.watch(qaNotifierProvider).messages
///   isLoading                 → qaState.isLoading
///   selectedTags              → _selectedTags (local widget state)
///   Auto-scroll on new msg    → ref.listen + _scrollToBottom()
///   Send on Enter / button    → _send()
class QaScreen extends ConsumerStatefulWidget {
  const QaScreen({super.key});

  @override
  ConsumerState<QaScreen> createState() => _QaScreenState();
}

class _QaScreenState extends ConsumerState<QaScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<String> _selectedTags = [];

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() async {
    final q = _controller.text.trim();
    if (q.isEmpty) return;
    _controller.clear();
    await ref
        .read(qaNotifierProvider.notifier)
        .askQuestion(q, tags: List.unmodifiable(_selectedTags));
    _scrollToBottom();
  }

  void _toggleTag(String tag) {
    setState(() {
      if (_selectedTags.contains(tag)) {
        _selectedTags.remove(tag);
      } else {
        _selectedTags.add(tag);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final qaState = ref.watch(qaNotifierProvider);
    final tags = ref.watch(tagsProvider);
    final hasCompleted = ref.watch(hasCompletedUploadsProvider);
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    // Auto-scroll when a new message is added
    ref.listen(qaNotifierProvider, (prev, next) {
      if (next.messages.length != (prev?.messages.length ?? 0)) {
        _scrollToBottom();
      }
    });

    return Column(
      children: [
        // ── Tag filter bar ─────────────────────────────────────────────────
        if (tags.isNotEmpty)
          _TagBar(
            tags: tags,
            selected: _selectedTags,
            onToggle: _toggleTag,
          ),

        // ── Chat messages ──────────────────────────────────────────────────
        Expanded(
          child: !hasCompleted
              ? const _Placeholder(
                  icon: Icons.upload_file_outlined,
                  title: 'No indexed files yet',
                  subtitle: 'Go to Upload and wait for indexing to complete',
                )
              : qaState.messages.isEmpty
                  ? const _Placeholder(
                      icon: Icons.chat_bubble_outline,
                      title: 'Ask a question',
                      subtitle:
                          'Questions are answered using the uploaded content',
                    )
                  : ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
                      itemCount: qaState.messages.length +
                          (qaState.isLoading ? 1 : 0),
                      itemBuilder: (_, i) {
                        if (i == qaState.messages.length) {
                          return const TypingIndicator();
                        }
                        return ChatBubble(entry: qaState.messages[i]);
                      },
                    ),
        ),

        // ── Input area ─────────────────────────────────────────────────────
        Container(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
          decoration: BoxDecoration(
            color: theme.scaffoldBackgroundColor,
            border: Border(
              top: BorderSide(
                  color: cs.outline.withValues(alpha: 0.15), width: 1),
            ),
          ),
          child: SafeArea(
            top: false,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                // Clear chat
                if (qaState.messages.isNotEmpty)
                  Tooltip(
                    message: 'Clear chat history',
                    child: IconButton(
                      onPressed: () =>
                          ref.read(qaNotifierProvider.notifier).clearChat(),
                      icon: Icon(Icons.delete_outline,
                          size: 20,
                          color: cs.onSurface.withValues(alpha: 0.4)),
                    ),
                  ),
                // Text field
                Expanded(
                  child: TextField(
                    controller: _controller,
                    minLines: 1,
                    maxLines: 5,
                    enabled: hasCompleted && !qaState.isLoading,
                    decoration: InputDecoration(
                      hintText: hasCompleted
                          ? 'Ask about the uploaded content...'
                          : 'Upload and index files first',
                      hintStyle: TextStyle(
                        color: cs.onSurface.withValues(alpha: 0.38),
                        fontSize: 14,
                      ),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: BorderSide.none,
                      ),
                      filled: true,
                      fillColor:
                          cs.surfaceContainerHighest.withValues(alpha: 0.6),
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 11),
                      isDense: true,
                    ),
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _send(),
                  ),
                ),
                const SizedBox(width: 8),
                // Send button
                FilledButton(
                  onPressed:
                      hasCompleted && !qaState.isLoading ? _send : null,
                  style: FilledButton.styleFrom(
                    shape: const CircleBorder(),
                    padding: const EdgeInsets.all(13),
                    minimumSize: Size.zero,
                  ),
                  child: qaState.isLoading
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.send, size: 18),
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

class _TagBar extends StatelessWidget {
  final List<String> tags;
  final List<String> selected;
  final void Function(String) onToggle;

  const _TagBar(
      {required this.tags,
      required this.selected,
      required this.onToggle});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      height: 48,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        border: Border(
            bottom:
                BorderSide(color: cs.outline.withValues(alpha: 0.15))),
      ),
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: tags.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (_, i) {
          final tag = tags[i];
          return FilterChip(
            label: Text(tag, style: const TextStyle(fontSize: 12)),
            selected: selected.contains(tag),
            onSelected: (_) => onToggle(tag),
            padding: const EdgeInsets.symmetric(horizontal: 2),
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            visualDensity: VisualDensity.compact,
          );
        },
      ),
    );
  }
}

class _Placeholder extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;

  const _Placeholder({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

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
            Icon(icon, size: 56, color: cs.primary.withValues(alpha: 0.22)),
            const SizedBox(height: 14),
            Text(title,
                style: theme.textTheme.titleMedium
                    ?.copyWith(color: cs.onSurface.withValues(alpha: 0.35))),
            const SizedBox(height: 4),
            Text(subtitle,
                style: theme.textTheme.bodySmall?.copyWith(
                    color: cs.onSurface.withValues(alpha: 0.22)),
                textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}
