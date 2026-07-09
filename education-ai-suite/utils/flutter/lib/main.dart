 // SPDX-FileCopyrightText: (C) 2026 Intel Corporation
 // SPDX-License-Identifier: Apache-2.0

// Smart Classroom — Flutter
//
// Integrates with the Content Search Service (port 9011) for:
//   Upload → Ingest → Task Polling → Q&A
//
// SETUP (run once in this directory):
//   .\setup.ps1
//
// OR manually:
//   flutter create --project-name smart_classroom --org com.intel.smartclassroom --platforms windows,web .
//   flutter pub get
//   flutter run -d windows

import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'screens/home_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: 'assets/.env');
  runApp(const ProviderScope(child: SmartClassroomApp()));
}

class SmartClassroomApp extends StatelessWidget {
  const SmartClassroomApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Smart Classroom',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF0071C5), // Intel Blue
        ),
        useMaterial3: true,
        appBarTheme: const AppBarTheme(
          centerTitle: false,
          elevation: 0,
          scrolledUnderElevation: 1,
        ),
        cardTheme: CardThemeData(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(color: Colors.grey.shade200),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          filled: true,
        ),
      ),
      home: const HomeScreen(),
    );
  }
}
