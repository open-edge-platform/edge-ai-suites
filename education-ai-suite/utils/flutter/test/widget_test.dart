import 'package:flutter/material.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:smart_classroom/main.dart';

void main() {
  setUpAll(() async {
    // Load a minimal .env so dotenv.get() calls in the app don't throw.
    dotenv.testLoad(fileInput: 'BACKEND_URL=http://127.0.0.1:9011');
  });

  testWidgets('SmartClassroomApp renders HomeScreen', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: SmartClassroomApp()),
    );

    // The app bar title is always present on the HomeScreen.
    expect(find.text('Smart Classroom RAG'), findsOneWidget);

    // The bottom navigation bar has three destinations.
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.byIcon(Icons.upload_file_outlined), findsOneWidget);
  });
}
