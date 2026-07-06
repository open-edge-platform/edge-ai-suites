<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# SC Flutter Generator Skill

## Overview

This skill generates a **complete Smart Classroom RAG Flutter application from scratch** in the directory `utils/flutter/`. Unlike the other skills that orchestrate existing code and scripts, this skill writes every single line of Dart code needed for the application.

## What Gets Generated

### Directory Structure
```
utils/flutter/
├── lib/
│   ├── main.dart                          # App entry point
│   ├── app_config.dart                     # Configuration loader
│   ├── models/
│   │   ├── upload_entry.dart              # Upload task models
│   │   ├── file_asset.dart                # File listing models
│   │   ├── qa_models.dart                 # Q&A conversation models
│   │   └── health_status.dart             # Backend health models
│   ├── services/
│   │   └── content_search_api_service.dart # HTTP API client (Dio)
│   ├── providers/
│   │   ├── upload_provider.dart           # Upload state (Riverpod)
│   │   ├── qa_provider.dart               # Q&A state (Riverpod)
│   │   ├── health_provider.dart           # Health check state
│   │   └── files_provider.dart            # File management state
│   └── screens/
│       ├── home_screen.dart               # Navigation + health indicator
│       ├── upload_screen.dart             # File upload UI
│       ├── qa_screen.dart                 # Chat interface
│       └── files_screen.dart              # File browser
├── assets/
│   └── .env                                # Backend URL configuration
├── pubspec.yaml                            # Dependencies
├── windows/                                # Windows platform files
└── web/                                    # Web platform files
```

### Complete Source Code

The skill creates **~1,500 lines of production-ready Dart code**:

- **Models**: Data classes for uploads, files, Q&A, health status
- **Services**: HTTP client that calls all Content Search API endpoints
- **Providers**: Riverpod state management for reactive UI updates
- **Screens**: Four fully functional screens with Material Design 3
- **Configuration**: Environment-based config, pub dependencies, SPDX headers

### Key Features

- ✅ **Upload Screen**: File picker + tag input + live ingestion status tracking
- ✅ **Q&A Screen**: Chat interface with multi-turn conversation and source citations
- ✅ **Files Screen**: Browse indexed files, view metadata, delete files
- ✅ **Health Monitoring**: Live backend status indicator in app bar
- ✅ **Reactive State**: Real-time UI updates via Riverpod providers
- ✅ **Error Handling**: User-friendly error messages for API failures
- ✅ **Cross-platform**: Runs on Windows and Web

## Usage

### Invoke the Skill

To generate the complete Flutter app:

```
sc-flutter-gen
```

Or tell the agent:
- "generate flutter app"
- "create smart classroom from scratch"
- "write complete flutter code"

### Prerequisites

Before running this skill, ensure:

1. **Flutter SDK 3.22+** is installed and in PATH
2. **Python 3.11+** is installed
3. **Backend exists** at `smart-classroom/content_search/`
4. **Python venv exists** at `venv_content_search/`

If the backend venv doesn't exist, run `sc-setup` first to create it.

### What the Agent Will Do

The skill autonomously:

1. Creates `utils/flutter/` directory
2. Runs `flutter create` to initialize the project
3. Writes `pubspec.yaml` with all dependencies (Riverpod, Dio, file_picker, dotenv)
4. Creates the `.env` file with backend URL
5. Generates all 13 Dart source files with complete implementation
6. Runs `flutter pub get` to install dependencies

### Running the Generated App

After generation completes:

After generation, use the `sc-up` skill to start the application:

```
sc-up
```

Or start manually:
```powershell
# Terminal 1 - Backend
cd smart-classroom\content_search
..\..\venv_content_search\Scripts\python.exe start_services.py

# Terminal 2 - Flutter app
cd utils\flutter
flutter run -d windows
```

## Architecture

### API Communication

All screens communicate with the Content Search backend at `http://127.0.0.1:9011`:

| Screen | Endpoints Used |
|--------|---------------|
| Upload | `POST /api/v1/object/upload-ingest`, `GET /api/v1/task/query/{task_id}` |
| Q&A | `POST /api/v1/object/qa` |
| Files | `GET /api/v1/object/files/list`, `DELETE /api/v1/object/files/{file_hash}` |
| Health | `GET /api/v1/system/health` |

### State Management Flow

```
User Action → Screen → Provider.notifier.method()
                            ↓
                    API Service Call
                            ↓
                    Update Provider State
                            ↓
                    UI Rebuilds (Consumer/watch)
```

Example: Uploading a file
1. User picks file in `UploadScreen`
2. Calls `ref.read(uploadProvider.notifier).uploadFile(file, tags)`
3. `UploadNotifier` calls `ContentSearchApiService.uploadAndIngest()`
4. Creates `UploadEntry` with `taskId`, adds to state
5. Starts polling timer: every 2s, calls `queryTaskStatus()`
6. Updates entry status: `pending` → `running` → `completed`
7. `UploadScreen` rebuilds with updated progress via `ref.watch(uploadProvider)`

## Comparison with Other Skills

| Aspect | Existing Code | `sc-flutter-gen` |
|--------|--------------|------------------|
| **Approach** | Uses pre-existing code in `utils/flutter/` | Generates all code from scratch |
| **When to Use** | Code already exists in the repo | Code is missing or you need a fresh start |
| **Location** | `utils/flutter/` | `utils/flutter/` (generates if missing) |
| **Use Case** | Standard development workflow | Recovery, learning, or fresh setup |
| **Invoked By** | User or `sc-setup` (if code missing) | User or `sc-setup` (auto-invoked) |

## When to Use This Skill

**Use `sc-flutter-gen` when:**
- The Flutter code is missing from `utils/flutter/`
- You want to regenerate the entire application
- You need a fresh start or the code is corrupted
- You want to learn how the complete app is structured

**Use `sc-setup` when:**
- The Flutter code already exists in `utils/flutter/`
- You just need to install dependencies and set up the environment
- You're following the standard development workflow

Note: `sc-setup` automatically invokes `sc-flutter-gen` if the Flutter code is missing.

## Extending the Generated App

After generation, you can freely modify the code:

### Add a New Screen
1. Create `lib/screens/new_screen.dart`
2. Add route in `home_screen.dart` navigation
3. Add destination to `NavigationBar`

### Add a New API Endpoint
1. Add method to `ContentSearchApiService`
2. Create or update model in `lib/models/`
3. Create or update provider in `lib/providers/`
4. Call from screen via `ref.read(provider.notifier).method()`

### Change Backend URL
Edit `assets/.env`:
```env
CONTENT_SEARCH_API_URL=http://192.168.1.100:9011
```

### Add Mobile Support
```powershell
flutter create --platforms android,ios .
flutter build apk    # Android
flutter build ios    # iOS (requires Mac + Xcode)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `flutter: command not found` | Install Flutter SDK, add to PATH, restart terminal |
| Pub dependencies fail to download | Check internet/proxy, run `flutter pub get --verbose` |
| Backend unreachable (red health icon) | Start backend: `cd smart-classroom\content_search; ..\..\venv_content_search\Scripts\python.exe start_services.py` |
| Files already exist error | Backup existing `utils\flutter\`, delete it, then regenerate |
| App builds but can't reach backend | Check `.env` has correct URL, ensure backend is running on port 9011 |

## License

All generated code includes SPDX headers:
```dart
// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
```

The generated application is licensed under Apache 2.0, same as the parent repository.

---

**Ready to generate?** Just say: `sc-flutter-gen` 🚀
