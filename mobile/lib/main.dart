import 'package:flutter/material.dart';

import 'api_service.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'theme.dart';

void main() {
  runApp(const CasanovaApp());
}

class CasanovaApp extends StatelessWidget {
  const CasanovaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Casanova Esquadrias',
      debugShowCheckedModeBanner: false,
      theme: Cv.theme(),
      home: const SplashScreen(),
    );
  }
}

/// Verifica se há token salvo e decide a tela inicial.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  final _api = ApiService();

  @override
  void initState() {
    super.initState();
    _verificar();
  }

  Future<void> _verificar() async {
    final temToken = await _api.carregarToken();
    if (!mounted) return;
    if (temToken) {
      try {
        final usuario = await _api.perfil();
        if (!mounted) return;
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => HomeScreen(api: _api, usuario: usuario)),
        );
        return;
      } catch (_) {
        await _api.logout();
      }
    }
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => LoginScreen(api: _api)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}
