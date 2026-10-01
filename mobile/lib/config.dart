/// Configuração do app — endereço da API Django.
///
/// Ajuste conforme o ambiente:
///   - Emulador Android:  http://10.0.2.2:8000
///   - Simulador iOS:     http://127.0.0.1:8000
///   - Celular físico:    http://<IP-DO-SERVIDOR>:8000  (ex.: 10.12.50.99)
class AppConfig {
  // Troque conforme o ambiente:
  //   - Servidor da empresa (celular físico):  http://10.12.50.99:8000
  //   - Dev local (web/desktop):               http://127.0.0.1:8000
  //   - Emulador Android:                      http://10.0.2.2:8000
  //   - Simulador iOS:                         http://127.0.0.1:8000
  static const String baseUrl = 'http://10.12.50.99:8000';

  // Cores da identidade Casanova
  static const int corAzul = 0xFF0B3882;
  static const int corAzulEscuro = 0xFF062254;
  static const int corAccent = 0xFF4DA6FF;
}
