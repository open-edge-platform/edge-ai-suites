enum ChatRole { user, assistant }

// ─── QaSource ────────────────────────────────────────────────────────────────

/// A single source citation returned with an assistant answer.
class QaSource {
  final String? type;           // "document" | "video" | "image"
  final String displayName;     // human-readable file name / title
  final String? formattedTimestamp; // e.g. "01:23" for video sources
  final double? score;          // relevance score 0–100

  const QaSource({
    this.type,
    required this.displayName,
    this.formattedTimestamp,
    this.score,
  });

  factory QaSource.fromJson(Map<String, dynamic> json) {
    // Score: backend may return 0–1 float; normalise to 0–100 for display
    final rawScore = json['score'];
    double? score;
    if (rawScore != null) {
      final s = (rawScore as num).toDouble();
      score = s <= 1.0 ? s * 100 : s;
    }

    return QaSource(
      type: json['type'] as String?,
      displayName: (json['display_name'] as String?) ??
          (json['file_name'] as String?) ??
          'Source',
      formattedTimestamp: json['timestamp'] as String?,
      score: score,
    );
  }
}

// ─── ChatEntry ───────────────────────────────────────────────────────────────

/// One message bubble in the conversation (user or assistant).
class ChatEntry {
  final String id;
  final ChatRole role;
  final String content;
  final List<QaSource> sources;
  final bool isError;

  const ChatEntry({
    required this.id,
    required this.role,
    required this.content,
    this.sources = const [],
    this.isError = false,
  });
}

// ─── QaHistoryMessage ────────────────────────────────────────────────────────

/// Compact representation sent to POST /api/v1/object/qa as conversation history.
class QaHistoryMessage {
  final String role;    // "user" | "assistant"
  final String content;

  const QaHistoryMessage({required this.role, required this.content});

  Map<String, dynamic> toJson() => {'role': role, 'content': content};
}

// ─── QaRequest ───────────────────────────────────────────────────────────────

/// Request body for POST /api/v1/object/qa.
class QaRequest {
  final String question;
  final List<QaHistoryMessage> history;
  final Map<String, dynamic>? filter;

  const QaRequest({
    required this.question,
    this.history = const [],
    this.filter,
  });

  Map<String, dynamic> toJson() => {
        'question': question,
        if (history.isNotEmpty)
          'history': history.map((h) => h.toJson()).toList(),
        if (filter != null) 'filter': filter,
      };
}

// ─── QaResult ────────────────────────────────────────────────────────────────

class QaResult {
  final String answer;
  final List<QaSource> sources;

  const QaResult({required this.answer, this.sources = const []});

  factory QaResult.fromJson(Map<String, dynamic> json) {
    final data = json.containsKey('data') && json['data'] is Map<String, dynamic>
        ? json['data'] as Map<String, dynamic>
        : json;

    final rawSources = data['sources'] as List<dynamic>? ?? [];
    return QaResult(
      answer: (data['answer'] as String?) ?? '',
      sources: rawSources
          .whereType<Map<String, dynamic>>()
          .map(QaSource.fromJson)
          .toList(),
    );
  }
}
