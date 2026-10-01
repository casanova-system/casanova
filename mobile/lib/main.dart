import 'package:flutter/material.dart';

import 'api_service.dart';
import 'config.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';

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
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(AppConfig.corAzul),
          primary: const Color(AppConfig.corAzul),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(AppConfig.corAzul),
          foregroundColor: Colors.white,
          elevation: 0,
        ),
      ),
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
