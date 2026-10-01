import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'config.dart';
import 'models.dart';

/// Cliente HTTP da API Django.
class ApiService {
  static const String _tokenKey = 'casanova_token';
  String? _token;

  String? get token => _token;

  /// Carrega o token salvo (login persistente).
  Future<bool> carregarToken() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString(_tokenKey);
    return _token != null;
  }

  Future<void> _salvarToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
  }

  Future<void> _limparToken() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
  }

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Token $_token',
      };

  /// Login — devolve o usuário ou lança exceção com a mensagem de erro.
  Future<Usuario> login(String username, String password) async {
    final resp = await http.post(
      Uri.parse('${AppConfig.baseUrl}/api/login/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );

    final data = jsonDecode(utf8.decode(resp.bodyBytes));
    if (resp.statusCode != 200) {
      throw Exception(data['erro'] ?? 'Falha no login.');
    }

    await _salvarToken(data['token']);
    return Usuario.fromJson(data['usuario']);
  }

  Future<void> logout() async {
    try {
      await http.post(
        Uri.parse('${AppConfig.baseUrl}/api/logout/'),
        headers: _headers,
      );
    } catch (_) {}
    await _limparToken();
  }

  Future<Usuario> perfil() async {
    final resp = await http.get(
      Uri.parse('${AppConfig.baseUrl}/api/perfil/'),
      headers: _headers,
    );
    if (resp.statusCode != 200) throw Exception('Sessão expirada.');
    return Usuario.fromJson(jsonDecode(utf8.decode(resp.bodyBytes)));
  }

  Future<List<Setor>> setores() async {
    final resp = await http.get(
      Uri.parse('${AppConfig.baseUrl}/api/setores/'),
      headers: _headers,
    );
    if (resp.statusCode != 200) throw Exception('Falha ao carregar setores.');
    final lista = jsonDecode(utf8.decode(resp.bodyBytes)) as List<dynamic>;
    return lista.map((s) => Setor.fromJson(s)).toList();
  }

  Future<List<Rastreio>> rastreios({String? q, String? setor, String? status}) async {
    final params = <String, String>{};
    if (q != null && q.isNotEmpty) params['q'] = q;
    if (setor != null && setor.isNotEmpty) params['setor'] = setor;
    if (status != null && status.isNotEmpty) params['status'] = status;

    final uri = Uri.parse('${AppConfig.baseUrl}/api/rastreios/')
        .replace(queryParameters: params.isEmpty ? null : params);
    final resp = await http.get(uri, headers: _headers);
    if (resp.statusCode != 200) throw Exception('Falha ao carregar rastreios.');
    final lista = jsonDecode(utf8.decode(resp.bodyBytes)) as List<dynamic>;
    return lista.map((r) => Rastreio.fromJson(r)).toList();
  }

  Future<Rastreio> rastreioDetalhe(int opId) async {
    final resp = await http.get(
      Uri.parse('${AppConfig.baseUrl}/api/rastreios/$opId/'),
      headers: _headers,
    );
    if (resp.statusCode != 200) throw Exception('Rastreio não encontrado.');
    return Rastreio.fromJson(jsonDecode(utf8.decode(resp.bodyBytes)));
  }

  /// Registra a leitura do código de barras.
  Future<ResultadoScan> escanear(String codigo, {String? vidro}) async {
    final resp = await http.post(
      Uri.parse('${AppConfig.baseUrl}/api/escanear/'),
      headers: _headers,
      body: jsonEncode({
        'codigo': codigo,
        if (vidro != null) 'vidro': vidro,
      }),
    );
    final data = jsonDecode(utf8.decode(resp.bodyBytes));
    return ResultadoScan.fromJson(data);
  }
}
