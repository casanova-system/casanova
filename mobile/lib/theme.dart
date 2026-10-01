import 'package:flutter/material.dart';

/// Design System Casanova — espelha os tokens do `casanova.css` do sistema web.
///
/// Mantém a identidade visual (azul #0b3882, accent #4da6ff) e os mesmos
/// raios, sombras e tipografia usados no Django, para que o app Flutter
/// pareça parte do mesmo sistema.
class Cv {
  // ---- Cores de marca ----
  static const Color blue = Color(0xFF0B3882);
  static const Color blueDark = Color(0xFF062254);
  static const Color accent = Color(0xFF4DA6FF);
  static const Color blueSoft = Color(0x140B3882); // rgba(11,56,130,.08)
  static const Color blueRing = Color(0x2E0B3882); // rgba(11,56,130,.18)

  // ---- Superfícies (tema claro) ----
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surface2 = Color(0xFFF8FAFC);
  static const Color canvas = Color(0xFFF4F6F9);
  static const Color line = Color(0xFFE6EBF2);
  static const Color lineStrong = Color(0xFFD7DEE8);

  // ---- Texto ----
  static const Color text = Color(0xFF1E293B);
  static const Color textMuted = Color(0xFF64748B);
  static const Color textFaint = Color(0xFF94A3B8);

  // ---- Semânticas ----
  static const Color success = Color(0xFF16A34A);
  static const Color successSoft = Color(0xFFDCFCE7);
  static const Color warning = Color(0xFFEA580C);
  static const Color warningSoft = Color(0xFFFFEDD5);
  static const Color danger = Color(0xFFDC2626);
  static const Color dangerSoft = Color(0xFFFEE2E2);

  // ---- Raios ----
  static const double radiusSm = 8;
  static const double radius = 12;
  static const double radiusLg = 16;
  static const double radiusXl = 20;

  // ---- Sombras (sutis, em camadas — iguais ao CSS) ----
  static const List<BoxShadow> shadowSm = [
    BoxShadow(color: Color(0x0F0F172A), blurRadius: 3, offset: Offset(0, 1)),
    BoxShadow(color: Color(0x0A0F172A), blurRadius: 2, offset: Offset(0, 1)),
  ];
  static const List<BoxShadow> shadowMd = [
    BoxShadow(color: Color(0x120F172A), blurRadius: 12, offset: Offset(0, 4)),
    BoxShadow(color: Color(0x0A0F172A), blurRadius: 4, offset: Offset(0, 2)),
  ];
  static const List<BoxShadow> shadowLg = [
    BoxShadow(color: Color(0x1A0F172A), blurRadius: 28, offset: Offset(0, 12)),
    BoxShadow(color: Color(0x0D0F172A), blurRadius: 10, offset: Offset(0, 4)),
  ];
  static const List<BoxShadow> shadowBlue = [
    BoxShadow(color: Color(0x380B3882), blurRadius: 22, offset: Offset(0, 8)),
  ];

  /// Gradiente da marca (usado no painel de login e cabeçalhos).
  static const LinearGradient brandGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF092C6B), Color(0xFF031330)],
  );

  /// Fundo com os mesmos "glows" radiais do login web.
  static BoxDecoration canvasDecoration() => const BoxDecoration(
        color: canvas,
        gradient: RadialGradient(
          center: Alignment.topLeft,
          radius: 1.4,
          colors: [Color(0x140B3882), Color(0x00F4F6F9)],
        ),
      );

  /// Tema Material do app.
  static ThemeData theme() {
    final base = ThemeData(useMaterial3: true);
    return base.copyWith(
      scaffoldBackgroundColor: canvas,
      colorScheme: ColorScheme.fromSeed(
        seedColor: blue,
        primary: blue,
        secondary: accent,
        surface: surface,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: blue,
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: Colors.white,
          fontSize: 18,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.2,
        ),
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radius),
          side: const BorderSide(color: line),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusSm),
          borderSide: const BorderSide(color: lineStrong),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusSm),
          borderSide: const BorderSide(color: lineStrong),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusSm),
          borderSide: const BorderSide(color: accent, width: 1.6),
        ),
        labelStyle: const TextStyle(color: textMuted, fontSize: 13),
        floatingLabelStyle: const TextStyle(color: blue, fontSize: 13),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: blue,
          foregroundColor: Colors.white,
          minimumSize: const Size(0, 50),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusSm),
          ),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: blue,
          minimumSize: const Size(0, 50),
          side: const BorderSide(color: lineStrong),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusSm),
          ),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
      dividerTheme: const DividerThemeData(color: line, thickness: 1, space: 1),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: text,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusSm),
        ),
      ),
    );
  }
}

/// Logotipo CASANOVA ESQUADRIAS (texto estilizado, igual ao web).
class CvBrand extends StatelessWidget {
  final double fontSize;
  final Color casanovaColor;
  final Color esquadriasColor;
  const CvBrand({
    super.key,
    this.fontSize = 20,
    this.casanovaColor = Cv.blue,
    this.esquadriasColor = Cv.accent,
  });

  @override
  Widget build(BuildContext context) {
    return RichText(
      text: TextSpan(
        style: TextStyle(
          fontSize: fontSize,
          fontWeight: FontWeight.w900,
          letterSpacing: 1.2,
        ),
        children: [
          TextSpan(
            text: 'CASANOVA ',
            style: TextStyle(color: casanovaColor),
          ),
          TextSpan(
            text: 'ESQUADRIAS',
            style: TextStyle(
              color: esquadriasColor,
              fontWeight: FontWeight.w300,
            ),
          ),
        ],
      ),
    );
  }
}

/// Cartão padrão do sistema (superfície + borda + sombra sutil).
class CvCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final List<BoxShadow>? shadow;
  final Color? color;
  final Color? borderColor;
  final double radius;
  const CvCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.shadow,
    this.color,
    this.borderColor,
    this.radius = Cv.radius,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color ?? Cv.surface,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: borderColor ?? Cv.line),
        boxShadow: shadow ?? Cv.shadowSm,
      ),
      child: child,
    );
  }
}

/// Badge/pílula (ex.: "Gerência", status).
class CvBadge extends StatelessWidget {
  final String texto;
  final Color cor;
  final IconData? icone;
  const CvBadge({
    super.key,
    required this.texto,
    required this.cor,
    this.icone,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: cor.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: cor.withValues(alpha: 0.30)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icone != null) ...[
            Icon(icone, size: 13, color: cor),
            const SizedBox(width: 5),
          ],
          Text(
            texto,
            style: TextStyle(
              color: cor,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}
