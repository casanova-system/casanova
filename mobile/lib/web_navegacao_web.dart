// Implementação para Flutter Web — navega para uma URL na mesma aba.
//
// Usa `package:web` (API moderna, substitui o `dart:html`).
import 'package:web/web.dart' as web;

void abrirUrl(String url) {
  web.window.location.href = url;
}
