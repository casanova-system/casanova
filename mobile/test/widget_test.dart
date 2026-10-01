import 'package:flutter_test/flutter_test.dart';

import 'package:casanova_mobile/main.dart';

void main() {
  testWidgets('App inicia na tela de splash', (WidgetTester tester) async {
    await tester.pumpWidget(const CasanovaApp());
    expect(find.byType(CasanovaApp), findsOneWidget);
  });
}
