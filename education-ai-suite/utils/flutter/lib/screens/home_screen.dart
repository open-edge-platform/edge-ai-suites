import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'upload_screen.dart';
import 'qa_screen.dart';
import 'files_screen.dart';
import '../providers/upload_notifier.dart';
import '../providers/service_providers.dart';

/// Root shell with a NavigationBar.
/// Three tabs: Upload → Q&A → Files
/// Q&A tab is disabled until at least one file is indexed (hasCompletedUploads).
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  int _index = 0;

  static const _screens = [
    UploadScreen(),
    QaScreen(),
    FilesScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final hasCompleted = ref.watch(hasCompletedUploadsProvider);
    final isActive = ref.watch(isAnyUploadActiveProvider);

    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.school_outlined,
                color: Theme.of(context).colorScheme.primary, size: 22),
            const SizedBox(width: 10),
            const Text(
              'Smart Classroom RAG',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 17),
            ),
          ],
        ),
        actions: [
          IconButton(
            onPressed: () =>
                ref.read(healthNotifierProvider.notifier).check(),
            icon: const Icon(Icons.refresh_outlined),
            tooltip: 'Check service health',
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: IndexedStack(
        index: _index,
        children: _screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) {
          // Block Q&A tab until indexing is done
          if (i == 1 && !hasCompleted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text(
                    'Upload and index at least one file before asking questions'),
                duration: Duration(seconds: 2),
                behavior: SnackBarBehavior.floating,
              ),
            );
            return;
          }
          setState(() => _index = i);
        },
        destinations: [
          NavigationDestination(
            icon: Badge(
              isLabelVisible: isActive,
              child: const Icon(Icons.cloud_upload_outlined),
            ),
            selectedIcon: const Icon(Icons.cloud_upload),
            label: 'Upload',
          ),
          NavigationDestination(
            icon: Icon(
              Icons.chat_outlined,
              color: hasCompleted ? null : Colors.grey.shade400,
            ),
            selectedIcon: const Icon(Icons.chat),
            label: 'Q&A',
          ),
          const NavigationDestination(
            icon: Icon(Icons.folder_outlined),
            selectedIcon: Icon(Icons.folder),
            label: 'Files',
          ),
        ],
      ),
    );
  }
}
