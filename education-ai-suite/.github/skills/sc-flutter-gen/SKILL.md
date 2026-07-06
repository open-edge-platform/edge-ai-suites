---
name: sc-flutter-gen
description: >
  Comprehensive skill that generates a complete Smart Classroom RAG Flutter
  application from scratch at utils/flutter/, including all Dart code (main.dart,
  models, providers, services, screens), pubspec.yaml, and .env configuration.
  Connects to the existing Content Search backend. Use when the user says
  "generate flutter app", "create smart classroom from scratch", "write complete
  flutter code", or "build the app with all code".
license: Apache-2.0
metadata:
  version: "1.0.0"
  tags: "sc flutter generate fullstack code-gen"
---

<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# SC Flutter Generator

Generate a complete Smart Classroom RAG Flutter application from scratch with
all source code, configuration, and startup scripts.

**Agent: execute all commands directly using your terminal tool** and create all
files. This skill is self-contained and writes the entire application.

---

## What This Skill Does

Creates a brand-new Flutter application with:
- Complete Dart source code (models, providers, services, screens)
- Three main screens: Upload, Q&A, Files
- Riverpod state management
- Dio HTTP client
- Connection to existing Content Search backend
- Configuration files (pubspec.yaml, .env, .metadata)
- Startup workflow via direct commands

**Default location**: `utils/flutter/` (can be customized if needed)

---

## Prerequisites

- Flutter SDK 3.22+ in PATH
- Python 3.11+ in PATH
- Existing Content Search backend at `smart-classroom/content_search/`
- Repository root: `education-ai-suite/`

---

## Workflow

### 1. Create Flutter app directory

```powershell
# Default location - change if utils/flutter/ already exists and you want a separate copy
New-Item -ItemType Directory -Force -Path "utils\flutter"
Push-Location utils\flutter
```

> **Note**: If `utils/flutter/` already has a Flutter app, you can generate to
> `utils/flutter_generated/` instead to avoid overwriting.

### 2. Initialize Flutter project

```powershell
flutter create --platforms windows,web --org com.intel.smartclassroom --project-name smart_classroom_rag .
```

### 3. Create pubspec.yaml with dependencies

Create `utils/flutter/pubspec.yaml`:

```yaml
name: smart_classroom_rag
description: Smart Classroom RAG - AI-powered educational content assistant
publish_to: 'none'
version: 1.0.0+1

environment:
  sdk: '>=3.3.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  
  # State management
  flutter_riverpod: ^2.5.1
  
  # HTTP client
  dio: ^5.4.0
  
  # File picker
  file_picker: ^8.0.0+1
  
  # Environment configuration
  flutter_dotenv: ^5.1.0
  
  # UI
  cupertino_icons: ^1.0.6

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0

flutter:
  uses-material-design: true
  assets:
    - assets/.env
```

### 4. Create .env configuration

Create `utils/flutter/assets/.env`:

```env
CONTENT_SEARCH_API_URL=http://127.0.0.1:9011
MAIN_API_URL=http://127.0.0.1:8000
```

### 5. Create lib/main.dart

Create `utils/flutter/lib/main.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'screens/home_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  try {
    await dotenv.load(fileName: "assets/.env");
  } catch (e) {
    debugPrint('Error loading .env file: $e');
  }
  
  runApp(
    const ProviderScope(
      child: SmartClassroomApp(),
    ),
  );
}

class SmartClassroomApp extends StatelessWidget {
  const SmartClassroomApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Smart Classroom RAG',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.blue,
          brightness: Brightness.light,
        ),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}
```

### 6. Create lib/app_config.dart

Create `utils/flutter/lib/app_config.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConfig {
  static String get contentSearchApiUrl =>
      dotenv.env['CONTENT_SEARCH_API_URL'] ?? 'http://127.0.0.1:9011';

  static String get mainApiUrl =>
      dotenv.env['MAIN_API_URL'] ?? 'http://127.0.0.1:8000';
}
```

### 7. Create models

Create `utils/flutter/lib/models/upload_entry.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

enum TaskStatus {
  pending,
  running,
  completed,
  failed,
  unknown,
}

class UploadEntry {
  final String fileName;
  final String taskId;
  TaskStatus status;
  String? errorMessage;
  double progress;

  UploadEntry({
    required this.fileName,
    required this.taskId,
    this.status = TaskStatus.pending,
    this.errorMessage,
    this.progress = 0.0,
  });

  UploadEntry copyWith({
    String? fileName,
    String? taskId,
    TaskStatus? status,
    String? errorMessage,
    double? progress,
  }) {
    return UploadEntry(
      fileName: fileName ?? this.fileName,
      taskId: taskId ?? this.taskId,
      status: status ?? this.status,
      errorMessage: errorMessage ?? this.errorMessage,
      progress: progress ?? this.progress,
    );
  }
}
```

Create `utils/flutter/lib/models/file_asset.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

class FileAsset {
  final String fileHash;
  final String fileName;
  final String fileType;
  final int fileSize;
  final String uploadDate;
  final List<String> tags;

  FileAsset({
    required this.fileHash,
    required this.fileName,
    required this.fileType,
    required this.fileSize,
    required this.uploadDate,
    required this.tags,
  });

  factory FileAsset.fromJson(Map<String, dynamic> json) {
    return FileAsset(
      fileHash: json['file_hash'] ?? '',
      fileName: json['file_name'] ?? '',
      fileType: json['file_type'] ?? '',
      fileSize: json['file_size'] ?? 0,
      uploadDate: json['upload_date'] ?? '',
      tags: List<String>.from(json['tags'] ?? []),
    );
  }
}
```

Create `utils/flutter/lib/models/qa_models.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

enum ChatRole { user, assistant }

class ChatEntry {
  final ChatRole role;
  final String message;
  final List<QaSource>? sources;
  final DateTime timestamp;

  ChatEntry({
    required this.role,
    required this.message,
    this.sources,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();
}

class QaSource {
  final String documentName;
  final String documentType;
  final double relevanceScore;

  QaSource({
    required this.documentName,
    required this.documentType,
    required this.relevanceScore,
  });

  factory QaSource.fromJson(Map<String, dynamic> json) {
    return QaSource(
      documentName: json['document_name'] ?? '',
      documentType: json['document_type'] ?? '',
      relevanceScore: (json['relevance_score'] ?? 0.0).toDouble(),
    );
  }
}

class QaHistoryMessage {
  final String role;
  final String content;

  QaHistoryMessage({required this.role, required this.content});

  Map<String, dynamic> toJson() => {'role': role, 'content': content};
}

class QaRequest {
  final String question;
  final List<QaHistoryMessage> history;
  final List<String>? tags;

  QaRequest({
    required this.question,
    required this.history,
    this.tags,
  });

  Map<String, dynamic> toJson() {
    return {
      'question': question,
      'history': history.map((h) => h.toJson()).toList(),
      if (tags != null) 'tags': tags,
    };
  }
}

class QaResult {
  final String answer;
  final List<QaSource> sources;

  QaResult({required this.answer, required this.sources});

  factory QaResult.fromJson(Map<String, dynamic> json) {
    return QaResult(
      answer: json['answer'] ?? '',
      sources: (json['sources'] as List?)
              ?.map((s) => QaSource.fromJson(s))
              .toList() ??
          [],
    );
  }
}
```

Create `utils/flutter/lib/models/health_status.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

enum HealthState { healthy, unhealthy, checking, unknown }

class HealthStatus {
  final HealthState state;
  final String? message;
  final DateTime lastChecked;

  HealthStatus({
    required this.state,
    this.message,
    DateTime? lastChecked,
  }) : lastChecked = lastChecked ?? DateTime.now();
}
```

### 8. Create services

Create `utils/flutter/lib/services/content_search_api_service.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import 'dart:io';
import 'package:dio/dio.dart';
import '../app_config.dart';
import '../models/file_asset.dart';
import '../models/qa_models.dart';

class ContentSearchApiService {
  late final Dio _dio;
  final String baseUrl;

  ContentSearchApiService({String? baseUrl})
      : baseUrl = baseUrl ?? AppConfig.contentSearchApiUrl {
    _dio = Dio(BaseOptions(
      baseUrl: this.baseUrl,
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 30),
    ));
  }

  Future<Map<String, dynamic>> checkHealth() async {
    try {
      final response = await _dio.get('/api/v1/system/health');
      return response.data;
    } catch (e) {
      throw Exception('Health check failed: $e');
    }
  }

  Future<String> uploadAndIngest(File file, List<String> tags) async {
    try {
      final formData = FormData.fromMap({
        'file': await MultipartFile.fromFile(file.path,
            filename: file.path.split(Platform.pathSeparator).last),
        'tags': tags.join(','),
      });

      final response = await _dio.post(
        '/api/v1/object/upload-ingest',
        data: formData,
      );

      return response.data['task_id'];
    } catch (e) {
      throw Exception('Upload failed: $e');
    }
  }

  Future<Map<String, dynamic>> queryTaskStatus(String taskId) async {
    try {
      final response = await _dio.get('/api/v1/task/query/$taskId');
      return response.data;
    } catch (e) {
      throw Exception('Task query failed: $e');
    }
  }

  Future<void> cleanupTask(String taskId) async {
    try {
      await _dio.delete('/api/v1/object/cleanup-task/$taskId');
    } catch (e) {
      throw Exception('Cleanup failed: $e');
    }
  }

  Future<QaResult> askQuestion(QaRequest request) async {
    try {
      final response = await _dio.post(
        '/api/v1/object/qa',
        data: request.toJson(),
      );
      return QaResult.fromJson(response.data);
    } catch (e) {
      throw Exception('Q&A failed: $e');
    }
  }

  Future<List<String>> listTags() async {
    try {
      final response = await _dio.get('/api/v1/object/tags');
      return List<String>.from(response.data['tags']);
    } catch (e) {
      throw Exception('List tags failed: $e');
    }
  }

  Future<List<FileAsset>> listFiles() async {
    try {
      final response = await _dio.get('/api/v1/object/files/list');
      return (response.data['files'] as List)
          .map((f) => FileAsset.fromJson(f))
          .toList();
    } catch (e) {
      throw Exception('List files failed: $e');
    }
  }

  Future<void> deleteFile(String fileHash) async {
    try {
      await _dio.delete('/api/v1/object/files/$fileHash');
    } catch (e) {
      throw Exception('Delete file failed: $e');
    }
  }
}
```

### 9. Create providers

Create `utils/flutter/lib/providers/upload_provider.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import 'dart:async';
import 'dart:io';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/upload_entry.dart';
import '../services/content_search_api_service.dart';

final apiServiceProvider = Provider((ref) => ContentSearchApiService());

final uploadProvider =
    StateNotifierProvider<UploadNotifier, List<UploadEntry>>((ref) {
  return UploadNotifier(ref.read(apiServiceProvider));
});

class UploadNotifier extends StateNotifier<List<UploadEntry>> {
  final ContentSearchApiService _apiService;
  final Map<String, Timer> _pollingTimers = {};

  UploadNotifier(this._apiService) : super([]);

  Future<void> uploadFile(File file, List<String> tags) async {
    try {
      final taskId = await _apiService.uploadAndIngest(file, tags);
      final entry = UploadEntry(
        fileName: file.path.split(Platform.pathSeparator).last,
        taskId: taskId,
        status: TaskStatus.pending,
      );

      state = [...state, entry];
      _startPolling(taskId);
    } catch (e) {
      // Handle error
    }
  }

  void _startPolling(String taskId) {
    _pollingTimers[taskId] = Timer.periodic(
      const Duration(seconds: 2),
      (_) => _pollTaskStatus(taskId),
    );
  }

  Future<void> _pollTaskStatus(String taskId) async {
    try {
      final result = await _apiService.queryTaskStatus(taskId);
      final statusStr = result['status'] as String?;

      TaskStatus newStatus;
      switch (statusStr?.toUpperCase()) {
        case 'PENDING':
          newStatus = TaskStatus.pending;
          break;
        case 'RUNNING':
          newStatus = TaskStatus.running;
          break;
        case 'COMPLETED':
          newStatus = TaskStatus.completed;
          _pollingTimers[taskId]?.cancel();
          break;
        case 'FAILED':
          newStatus = TaskStatus.failed;
          _pollingTimers[taskId]?.cancel();
          break;
        default:
          newStatus = TaskStatus.unknown;
      }

      state = [
        for (final entry in state)
          if (entry.taskId == taskId)
            entry.copyWith(
              status: newStatus,
              progress: result['progress'] ?? 0.0,
              errorMessage: result['error'],
            )
          else
            entry,
      ];
    } catch (e) {
      // Handle error
    }
  }

  @override
  void dispose() {
    for (final timer in _pollingTimers.values) {
      timer.cancel();
    }
    super.dispose();
  }
}
```

Create `utils/flutter/lib/providers/qa_provider.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/qa_models.dart';
import '../services/content_search_api_service.dart';
import 'upload_provider.dart';

final qaProvider = StateNotifierProvider<QaNotifier, List<ChatEntry>>((ref) {
  return QaNotifier(ref.read(apiServiceProvider));
});

class QaNotifier extends StateNotifier<List<ChatEntry>> {
  final ContentSearchApiService _apiService;

  QaNotifier(this._apiService) : super([]);

  Future<void> askQuestion(String question, {List<String>? tags}) async {
    final userEntry = ChatEntry(role: ChatRole.user, message: question);
    state = [...state, userEntry];

    try {
      final history = state
          .where((e) => e.role == ChatRole.user || e.role == ChatRole.assistant)
          .map((e) => QaHistoryMessage(
                role: e.role == ChatRole.user ? 'user' : 'assistant',
                content: e.message,
              ))
          .toList();

      final request = QaRequest(
        question: question,
        history: history.length > 6 ? history.sublist(history.length - 6) : history,
        tags: tags,
      );

      final result = await _apiService.askQuestion(request);

      final assistantEntry = ChatEntry(
        role: ChatRole.assistant,
        message: result.answer,
        sources: result.sources,
      );

      state = [...state, assistantEntry];
    } catch (e) {
      final errorEntry = ChatEntry(
        role: ChatRole.assistant,
        message: 'Error: ${e.toString()}',
      );
      state = [...state, errorEntry];
    }
  }

  void clearHistory() {
    state = [];
  }
}
```

Create `utils/flutter/lib/providers/health_provider.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/health_status.dart';
import '../services/content_search_api_service.dart';
import 'upload_provider.dart';

final healthProvider =
    StateNotifierProvider<HealthNotifier, HealthStatus>((ref) {
  return HealthNotifier(ref.read(apiServiceProvider));
});

class HealthNotifier extends StateNotifier<HealthStatus> {
  final ContentSearchApiService _apiService;

  HealthNotifier(this._apiService)
      : super(HealthStatus(state: HealthState.unknown));

  Future<void> checkHealth() async {
    state = HealthStatus(state: HealthState.checking);

    try {
      final result = await _apiService.checkHealth();
      final isHealthy = result['status'] == 'healthy';

      state = HealthStatus(
        state: isHealthy ? HealthState.healthy : HealthState.unhealthy,
        message: result['message'],
      );
    } catch (e) {
      state = HealthStatus(
        state: HealthState.unhealthy,
        message: e.toString(),
      );
    }
  }
}
```

Create `utils/flutter/lib/providers/files_provider.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/file_asset.dart';
import '../services/content_search_api_service.dart';
import 'upload_provider.dart';

final filesProvider =
    StateNotifierProvider<FilesNotifier, AsyncValue<List<FileAsset>>>((ref) {
  return FilesNotifier(ref.read(apiServiceProvider));
});

class FilesNotifier extends StateNotifier<AsyncValue<List<FileAsset>>> {
  final ContentSearchApiService _apiService;

  FilesNotifier(this._apiService) : super(const AsyncValue.loading()) {
    loadFiles();
  }

  Future<void> loadFiles() async {
    state = const AsyncValue.loading();
    try {
      final files = await _apiService.listFiles();
      state = AsyncValue.data(files);
    } catch (e, stack) {
      state = AsyncValue.error(e, stack);
    }
  }

  Future<void> deleteFile(String fileHash) async {
    try {
      await _apiService.deleteFile(fileHash);
      await loadFiles();
    } catch (e) {
      // Handle error
    }
  }
}
```

### 10. Create screens

Create `utils/flutter/lib/screens/home_screen.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/health_provider.dart';
import '../models/health_status.dart';
import 'upload_screen.dart';
import 'qa_screen.dart';
import 'files_screen.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  int _selectedIndex = 0;

  static const List<Widget> _screens = [
    UploadScreen(),
    QaScreen(),
    FilesScreen(),
  ];

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(healthProvider.notifier).checkHealth());
  }

  @override
  Widget build(BuildContext context) {
    final health = ref.watch(healthProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Smart Classroom RAG'),
        actions: [
          _buildHealthIndicator(health),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => ref.read(healthProvider.notifier).checkHealth(),
            tooltip: 'Check backend health',
          ),
        ],
      ),
      body: _screens[_selectedIndex],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) {
          setState(() => _selectedIndex = index);
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.upload_file),
            label: 'Upload',
          ),
          NavigationDestination(
            icon: Icon(Icons.question_answer),
            label: 'Q&A',
          ),
          NavigationDestination(
            icon: Icon(Icons.folder),
            label: 'Files',
          ),
        ],
      ),
    );
  }

  Widget _buildHealthIndicator(HealthStatus health) {
    Color color;
    IconData icon;

    switch (health.state) {
      case HealthState.healthy:
        color = Colors.green;
        icon = Icons.check_circle;
        break;
      case HealthState.unhealthy:
        color = Colors.red;
        icon = Icons.error;
        break;
      case HealthState.checking:
        color = Colors.orange;
        icon = Icons.sync;
        break;
      case HealthState.unknown:
        color = Colors.grey;
        icon = Icons.help;
        break;
    }

    return Padding(
      padding: const EdgeInsets.all(8.0),
      child: Icon(icon, color: color),
    );
  }
}
```

Create `utils/flutter/lib/screens/upload_screen.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/upload_provider.dart';
import '../models/upload_entry.dart';

class UploadScreen extends ConsumerStatefulWidget {
  const UploadScreen({super.key});

  @override
  ConsumerState<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends ConsumerState<UploadScreen> {
  final _tagsController = TextEditingController();

  @override
  void dispose() {
    _tagsController.dispose();
    super.dispose();
  }

  Future<void> _pickAndUploadFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: [
        'pdf',
        'txt',
        'docx',
        'doc',
        'pptx',
        'ppt',
        'xlsx',
        'xls',
        'jpg',
        'jpeg',
        'png',
        'mp4',
        'avi',
        'mov',
        'mkv'
      ],
    );

    if (result != null && result.files.single.path != null) {
      final file = File(result.files.single.path!);
      final tags = _tagsController.text
          .split(',')
          .map((t) => t.trim())
          .where((t) => t.isNotEmpty)
          .toList();

      await ref.read(uploadProvider.notifier).uploadFile(file, tags);
    }
  }

  @override
  Widget build(BuildContext context) {
    final uploads = ref.watch(uploadProvider);

    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _tagsController,
            decoration: const InputDecoration(
              labelText: 'Tags (comma-separated)',
              hintText: 'e.g., math, lecture, chapter1',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: _pickAndUploadFile,
            icon: const Icon(Icons.upload_file),
            label: const Text('Select and Upload File'),
          ),
          const SizedBox(height: 24),
          const Text(
            'Upload History',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: uploads.isEmpty
                ? const Center(child: Text('No uploads yet'))
                : ListView.builder(
                    itemCount: uploads.length,
                    itemBuilder: (context, index) {
                      final entry = uploads[uploads.length - 1 - index];
                      return _buildUploadCard(entry);
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildUploadCard(UploadEntry entry) {
    IconData icon;
    Color color;

    switch (entry.status) {
      case TaskStatus.completed:
        icon = Icons.check_circle;
        color = Colors.green;
        break;
      case TaskStatus.failed:
        icon = Icons.error;
        color = Colors.red;
        break;
      case TaskStatus.running:
        icon = Icons.sync;
        color = Colors.blue;
        break;
      case TaskStatus.pending:
        icon = Icons.hourglass_empty;
        color = Colors.orange;
        break;
      case TaskStatus.unknown:
        icon = Icons.help;
        color = Colors.grey;
        break;
    }

    return Card(
      child: ListTile(
        leading: Icon(icon, color: color),
        title: Text(entry.fileName),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Status: ${entry.status.name}'),
            if (entry.status == TaskStatus.running)
              LinearProgressIndicator(value: entry.progress),
            if (entry.errorMessage != null) Text('Error: ${entry.errorMessage}'),
          ],
        ),
      ),
    );
  }
}
```

Create `utils/flutter/lib/screens/qa_screen.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/qa_provider.dart';
import '../models/qa_models.dart';

class QaScreen extends ConsumerStatefulWidget {
  const QaScreen({super.key});

  @override
  ConsumerState<QaScreen> createState() => _QaScreenState();
}

class _QaScreenState extends ConsumerState<QaScreen> {
  final _questionController = TextEditingController();
  final _scrollController = ScrollController();

  @override
  void dispose() {
    _questionController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _askQuestion() {
    final question = _questionController.text.trim();
    if (question.isEmpty) return;

    ref.read(qaProvider.notifier).askQuestion(question);
    _questionController.clear();

    Future.delayed(const Duration(milliseconds: 100), () {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final chatHistory = ref.watch(qaProvider);

    return Column(
      children: [
        Expanded(
          child: chatHistory.isEmpty
              ? const Center(
                  child: Text('Ask a question about your uploaded content'))
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(16),
                  itemCount: chatHistory.length,
                  itemBuilder: (context, index) {
                    final entry = chatHistory[index];
                    return _buildChatBubble(entry);
                  },
                ),
        ),
        Padding(
          padding: const EdgeInsets.all(16.0),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _questionController,
                  decoration: const InputDecoration(
                    hintText: 'Ask a question...',
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: (_) => _askQuestion(),
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                icon: const Icon(Icons.send),
                onPressed: _askQuestion,
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildChatBubble(ChatEntry entry) {
    final isUser = entry.role == ChatRole.user;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 8),
        padding: const EdgeInsets.all(12),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.7,
        ),
        decoration: BoxDecoration(
          color: isUser ? Colors.blue[100] : Colors.grey[200],
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              entry.message,
              style: const TextStyle(fontSize: 16),
            ),
            if (entry.sources != null && entry.sources!.isNotEmpty) ...[
              const SizedBox(height: 8),
              const Divider(),
              const Text(
                'Sources:',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12),
              ),
              ...entry.sources!.map((source) => Text(
                    '• ${source.documentName} (${source.relevanceScore.toStringAsFixed(2)})',
                    style: const TextStyle(fontSize: 12),
                  )),
            ],
          ],
        ),
      ),
    );
  }
}
```

Create `utils/flutter/lib/screens/files_screen.dart`:

```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/files_provider.dart';
import '../models/file_asset.dart';

class FilesScreen extends ConsumerWidget {
  const FilesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final filesAsync = ref.watch(filesProvider);

    return Scaffold(
      body: filesAsync.when(
        data: (files) {
          if (files.isEmpty) {
            return const Center(child: Text('No files uploaded yet'));
          }
          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: files.length,
            itemBuilder: (context, index) {
              final file = files[index];
              return _buildFileCard(context, ref, file);
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stack) => Center(child: Text('Error: $error')),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => ref.read(filesProvider.notifier).loadFiles(),
        child: const Icon(Icons.refresh),
      ),
    );
  }

  Widget _buildFileCard(BuildContext context, WidgetRef ref, FileAsset file) {
    return Card(
      child: ListTile(
        leading: Icon(_getFileIcon(file.fileType)),
        title: Text(file.fileName),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Type: ${file.fileType}'),
            Text('Size: ${_formatFileSize(file.fileSize)}'),
            if (file.tags.isNotEmpty) Text('Tags: ${file.tags.join(", ")}'),
          ],
        ),
        trailing: IconButton(
          icon: const Icon(Icons.delete, color: Colors.red),
          onPressed: () => _confirmDelete(context, ref, file),
        ),
      ),
    );
  }

  IconData _getFileIcon(String fileType) {
    if (fileType.contains('pdf')) return Icons.picture_as_pdf;
    if (fileType.contains('image')) return Icons.image;
    if (fileType.contains('video')) return Icons.video_file;
    if (fileType.contains('document')) return Icons.description;
    return Icons.insert_drive_file;
  }

  String _formatFileSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  void _confirmDelete(BuildContext context, WidgetRef ref, FileAsset file) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete File'),
        content: Text('Are you sure you want to delete ${file.fileName}?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              ref.read(filesProvider.notifier).deleteFile(file.fileHash);
              Navigator.pop(context);
            },
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }
}
```

### 11. Install dependencies

```powershell
flutter pub get
Pop-Location
```

### 12. Verify setup

```powershell
# Check that the app was created
Test-Path "utils\flutter\lib\main.dart"
Test-Path "utils\flutter\pubspec.yaml"
Test-Path "utils\flutter\assets\.env"

Write-Host "`nFlutter app generated successfully at utils\flutter\" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Run 'sc-setup' to install dependencies" -ForegroundColor Cyan
Write-Host "  2. Run 'sc-up' to start the application" -ForegroundColor Cyan
```

---

## Output

Report: **Flutter app generated ✓** → **All source code created ✓** → 
**Dependencies installed ✓** → **Ready to run ✓**

---

## File Structure Created

```
utils/flutter_generated/
├── lib/
│   ├── main.dart
│   ├── app_config.dart
│   ├── models/
│   │   ├── upload_entry.dart
│   │   ├── file_asset.dart
│   │   ├── qa_models.dart
│   │   └── health_status.dart
│   ├── services/
│   │   └── content_search_api_service.dart
│   ├── providers/
│   │   ├── upload_provider.dart
│   │   ├── qa_provider.dart
│   │   ├── health_provider.dart
│   │   └── files_provider.dart
│   └── screens/
│       ├── home_screen.dart
│       ├── upload_screen.dart
│       ├── qa_screen.dart
│       └── files_screen.dart
├── assets/
│   └── .env
├── pubspec.yaml
├── windows/
└── web/
```

---

## Notes

- Backend must be running at `http://127.0.0.1:9011` before starting the app
- Existing backend at `smart-classroom/content_search/` is used
- Python venv at `venv_content_search/` must exist
- All files include SPDX headers
- App supports Windows and Web platforms
- Use `sc-up` skill to start the application after generation
