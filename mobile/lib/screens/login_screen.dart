import 'package:flutter/material.dart';

import '../api_service.dart';
import '../theme.dart';
import 'home_screen.dart';

class LoginScreen extends StatefulWidget {
  final ApiService api;
  const LoginScreen({super.key, required this.api});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _userCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  bool _carregando = false;
  bool _verSenha = false;
  String? _erro;

  Future<void> _entrar() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      final usuario = await widget.api.login(
        _userCtrl.text.trim(),
        _passCtrl.text,
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => HomeScreen(api: widget.api, usuario: usuario),
        ),
      );
    } catch (e) {
      setState(() => _erro = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: Cv.canvasDecoration(),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _buildPainelMarca(),
                    const SizedBox(height: 20),
                    _buildFormulario(),
                    const SizedBox(height: 20),
                    const Text(
                      'System V.1.0 · Casanova Esquadrias',
                      style: TextStyle(color: Cv.textFaint, fontSize: 11),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  /// Painel superior com a identidade da marca (igual ao login web).
  Widget _buildPainelMarca() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(28, 32, 28, 28),
      decoration: BoxDecoration(
        gradient: Cv.brandGradient,
        borderRadius: BorderRadius.circular(Cv.radiusXl),
        boxShadow: Cv.shadowLg,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'ACESSO RESTRITO',
            style: TextStyle(
              color: Color(0x8CFFFFFF),
              fontSize: 11,
              letterSpacing: 1.8,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 20),
          Image.asset('assets/logo.png', width: 64, height: 64),
          const SizedBox(height: 16),
          const CvBrand(
            fontSize: 24,
            casanovaColor: Colors.white,
            esquadriasColor: Cv.accent,
          ),
          const SizedBox(height: 10),
          const Text(
            'Rastreio de Produção — acompanhe a Ordem de Produção '
            'por setor, do Estoque à Expedição.',
            style: TextStyle(
              color: Color(0xC7E2E8F0),
              fontSize: 13,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFormulario() {
    return CvCard(
      padding: const EdgeInsets.all(24),
      shadow: Cv.shadowMd,
      radius: Cv.radiusXl,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'ENTRAR',
            style: TextStyle(
              color: Cv.blue,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.6,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Bem-vindo de volta',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: Cv.text,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Use suas credenciais do sistema.',
            style: TextStyle(color: Cv.textMuted, fontSize: 13),
          ),
          const SizedBox(height: 22),
          TextField(
            controller: _userCtrl,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              labelText: 'Usuário',
              prefixIcon: Icon(Icons.person_outline, color: Cv.textMuted),
            ),
          ),
          const SizedBox(height: 14),
          TextField(
            controller: _passCtrl,
            obscureText: !_verSenha,
            onSubmitted: (_) => _entrar(),
            decoration: InputDecoration(
              labelText: 'Senha',
              prefixIcon: const Icon(Icons.lock_outline, color: Cv.textMuted),
              suffixIcon: IconButton(
                icon: Icon(
                  _verSenha ? Icons.visibility_off : Icons.visibility,
                  color: Cv.textMuted,
                ),
                onPressed: () => setState(() => _verSenha = !_verSenha),
              ),
            ),
          ),
          if (_erro != null) ...[
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Cv.dangerSoft,
                borderRadius: BorderRadius.circular(Cv.radiusSm),
                border: Border.all(color: Cv.danger.withValues(alpha: 0.3)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline, color: Cv.danger, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _erro!,
                      style: const TextStyle(color: Cv.danger, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 22),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _carregando ? null : _entrar,
              child: _carregando
                  ? const SizedBox(
                      width: 22,
                      height: 22,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Text('Entrar'),
            ),
          ),
        ],
      ),
    );
  }
}
