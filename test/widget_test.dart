import 'package:flutter_test/flutter_test.dart';
import 'package:pocket_ai_server/main.dart';

void main() {
  testWidgets('PocketAI dashboard renders', (tester) async {
    await tester.pumpWidget(const PocketAiApp());
    expect(find.text('PocketAI Server'), findsOneWidget);
    expect(find.text('No model loaded'), findsOneWidget);
  });
}
