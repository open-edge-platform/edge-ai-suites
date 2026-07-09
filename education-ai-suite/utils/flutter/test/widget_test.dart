// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Smart Classroom Widget Tests
//
// Basic widget tests for the Smart Classroom RAG application

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:smart_classroom/main.dart';

void main() {
  testWidgets('Smart Classroom app loads', (WidgetTester tester) async {
    // Build our app and trigger a frame
    await tester.pumpWidget(const ProviderScope(child: SmartClassroomApp()));

    // Verify that the app title is present
    await tester.pumpAndSettle();
    expect(find.text('Smart Classroom RAG'), findsOneWidget);
    expect(find.text('Upload'), findsOneWidget);
  });

  testWidgets('Smart Classroom app has correct theme', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: SmartClassroomApp()));

    final MaterialApp app = tester.widget(find.byType(MaterialApp));
    final expected = ColorScheme.fromSeed(seedColor: const Color(0xFF0071C5));
    
    // Verify Intel Blue color scheme
    expect(app.theme?.colorScheme.primary, expected.primary);
    expect(app.debugShowCheckedModeBanner, false);
  });
}
