import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../app_config.dart';
import '../models/qa_models.dart';
import 'service_providers.dart';

// ─── State ───────────────────────────────────────────────────────────────────

class QaState {
  final List<ChatEntry> messages;
  final bool isLoading;
  final String? errorMessage;

  const QaState({
    this.messages = const [],
    this.isLoading = false,
    this.errorMessage,
  });

  QaState copyWith({
    List<ChatEntry>? messages,
    bool? isLoading,
    String? errorMessage,
  }) {
    return QaState(
      messages: messages ?? this.messages,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage,
    );
  }
}

// ─── Notifier ─────────────────────────────────────────────────────────────────

/// Manages Q&A chat state.
/// Equivalent of the useState / useCallback hooks in React's QASection.tsx.
///
/// State mapping:
///   messages: ChatEntry[]    → List<ChatEntry>
///   isLoading: bool          → bool
///   Multi-turn history        → built from last N messages before API call
class QaNotifier extends StateNotifier<QaState> {
  QaNotifier(this._ref) : super(const QaState());

  final Ref _ref;
  int _idCounter = 0;

  String _genId() =>
      'm_${DateTime.now().millisecondsSinceEpoch}_${_idCounter++}';

  /// Build the conversation history sent to /qa.
  /// Backend accepts last QA_MAX_HISTORY_TURNS (3) pairs.
  /// Matches the history slice in React's QASection.tsx sendQuestion().
  List<QaHistoryMessage> _buildHistory() {
    final completed = state.messages.where((m) => !m.isError).toList();
    final maxMessages = AppConfig.maxHistoryTurns * 2;
    final slice = completed.length > maxMessages
        ? completed.sublist(completed.length - maxMessages)
        : completed;

    return slice
        .map((m) => QaHistoryMessage(
              role: m.role == ChatRole.user ? 'user' : 'assistant',
              content: m.content,
            ))
        .toList();
  }

  // ── Ask question ───────────────────────────────────────────────────────────

  Future<void> askQuestion(
    String question, {
    List<String> tags = const [],
  }) async {
    final trimmed = question.trim();
    if (trimmed.isEmpty) return;

    // 1. Append user message immediately (optimistic update)
    final userEntry = ChatEntry(
      id: _genId(),
      role: ChatRole.user,
      content: trimmed,
    );
    state = state.copyWith(
      messages: [...state.messages, userEntry],
      isLoading: true,
    );

    // 2. Build filter from selected tags
    final filter =
        tags.isNotEmpty ? <String, dynamic>{'tags': tags} : null;

    // 3. Call POST /api/v1/object/qa
    try {
      final service = _ref.read(contentSearchApiServiceProvider);
      final result = await service.askQuestion(
        QaRequest(
          question: trimmed,
          history: _buildHistory(),
          filter: filter,
        ),
      );

      final assistantEntry = ChatEntry(
        id: _genId(),
        role: ChatRole.assistant,
        content: result.answer,
        sources: result.sources,
      );

      state = state.copyWith(
        messages: [...state.messages, assistantEntry],
        isLoading: false,
      );
    } on Exception catch (e) {
      final errorEntry = ChatEntry(
        id: _genId(),
        role: ChatRole.assistant,
        content: 'Error: ${e.toString().replaceFirst('Exception: ', '')}',
        isError: true,
      );
      state = state.copyWith(
        messages: [...state.messages, errorEntry],
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  void clearChat() => state = const QaState();
}

// ─── Provider ────────────────────────────────────────────────────────────────

final qaNotifierProvider =
    StateNotifierProvider<QaNotifier, QaState>(
  (ref) => QaNotifier(ref),
);
