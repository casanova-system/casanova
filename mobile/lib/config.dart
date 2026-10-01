import 'package:flutter/foundation.dart' show kIsWeb;

/// Configuração do app — endereço da API Django.
///
/// Quando o app roda no **navegador** (web), a API é acessada na **mesma
/// origem** da página — ou seja, funciona automaticamente em qualquer
/// endereço (localhost, 10.12.50.99, etc.) sem precisar recompilar.
///
/// Quando roda como app nativo (Android/iOS), usa o `baseUrl` fixo abaixo.
class AppConfig {
  /// URL fixa usada apenas no app nativo (Android/iOS).
  ///   - Servidor da empresa (celular físico):  http://10.12.50.99:8000
  ///   - Emulador Android:                      http://10.0.2.2:8000
  ///   - Simulador iOS:                         http://127.0.0.1:8000
  static const String _baseUrlNativo = 'http://10.12.50.99:8000';

  /// Endereço efetivo da API.
  ///
  /// No web devolve a origem atual (ex.: `http://10.12.50.99:8000`).
  /// No nativo devolve `_baseUrlNativo`.
  static String get baseUrl {
    if (kIsWeb) {
      final origem = Uri.base;
      return '${origem.scheme}://${origem.host}:${origem.port}';
    }
    return _baseUrlNativo;
  }

  // Cores da identidade Casanova
  static const int corAzul = 0xFF0B3882;
  static const int corAzulEscuro = 0xFF062254;
  static const int corAccent = 0xFF4DA6FF;
}
