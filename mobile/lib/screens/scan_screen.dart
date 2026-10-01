import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../api_service.dart';
import '../config.dart';
import '../models.dart';

/// Tela de escaneamento do código de barras da OP.
///
/// Usa a câmera do celular. Também aceita digitação manual (para leitores
/// Bluetooth que funcionam como teclado).
class ScanScreen extends StatefulWidget {
  final ApiService api;
  final Usuario usuario;
  const ScanScreen({super.key, required this.api, required this.usuario});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final _manualCtrl = TextEditingController();
  final MobileScannerController _scanner = MobileScannerController(
    detectionSpeed: DetectionSpeed.noDuplicates,
  );

  bool _processando = false;
  bool _modoManual = false;
  ResultadoScan? _resultado;
  String? _erro;
  int? _opPendenteVidro;

  @override
  void dispose() {
    _scanner.dispose();
    _manualCtrl.dispose();
    super.dispose();
  }

  Future<void> _processar(String codigo, {String? vidro}) async {
    if (_processando) return;
    setState(() {
      _processando = true;
      _erro = null;
      _resultado = null;
    });

    try {
      final res = await widget.api.escanear(codigo, vidro: vidro);
      if (!mounted) return;

      if (res.erro != null) {
        setState(() => _erro = res.erro);
      } else if (res.precisaVidro) {
        setState(() => _opPendenteVidro = res.opId);
      } else {
        setState(() => _resultado = res);
      }
    } catch (e) {
      setState(() => _erro = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _processando = false);
    }
  }

  void _onDetect(BarcodeCapture capture) {
    if (_processando || _resultado != null || _opPendenteVidro != null) return;
    final codigo = capture.barcodes.firstOrNull?.rawValue;
    if (codigo != null && codigo.isNotEmpty) {
      _processar(codigo);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Escanear OP'),
        actions: [
          IconButton(
            icon: Icon(_modoManual ? Icons.qr_code_scanner : Icons.keyboard),
            tooltip: _modoManual ? 'Usar câmera' : 'Digitar código',
            onPressed: () => setState(() => _modoManual = !_modoManual),
          ),
        ],
      ),
      body: Column(
        children: [
          _buildInfoUsuario(),
          Expanded(child: _buildCorpo()),
        ],
      ),
    );
  }

  Widget _buildInfoUsuario() {
    final s = widget.usuario.setorProducao;
    return Container(
      width: double.infinity,
      color: const Color(AppConfig.corAzul).withValues(alpha: 0.06),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          const Icon(Icons.person_pin_circle,
              color: Color(AppConfig.corAzul), size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              s != null
                  ? 'Registrando como: ${s.nome}'
                  : 'Sem setor de produção vinculado',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: s != null ? Colors.black87 : Colors.red.shade700,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCorpo() {
    // 1) Pergunta de vidro
    if (_opPendenteVidro != null) {
      return _buildPerguntaVidro();
    }
    // 2) Resultado de sucesso
    if (_resultado != null) {
      return _buildSucesso();
    }
    // 3) Erro
    if (_erro != null) {
      return _buildErro();
    }
    // 4) Scanner / manual
    return _modoManual ? _buildManual() : _buildCamera();
  }

  Widget _buildCamera() {
    return Stack(
      alignment: Alignment.center,
      children: [
        MobileScanner(controller: _scanner, onDetect: _onDetect),
        // Moldura de mira
        Container(
          width: 260,
          height: 160,
          decoration: BoxDecoration(
            border: Border.all(color: Colors.white, width: 3),
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        if (_processando)
          Container(
            color: Colors.black54,
            child: const Center(
              child: CircularProgressIndicator(color: Colors.white),
            ),
          ),
        Positioned(
          bottom: 24,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.black54,
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Text(
              'Aponte para o código de barras da OP',
              style: TextStyle(color: Colors.white, fontSize: 13),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildManual() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          const Icon(Icons.keyboard, size: 56, color: Color(AppConfig.corAzul)),
          const SizedBox(height: 12),
          const Text(
            'Digite o código da OP',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          Text(
            'Use o leitor Bluetooth ou digite o número.',
            style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
          ),
          const SizedBox(height: 24),
          TextField(
            controller: _manualCtrl,
            autofocus: true,
            keyboardType: TextInputType.number,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
            decoration: const InputDecoration(
              hintText: '00000',
              border: OutlineInputBorder(),
            ),
            onSubmitted: (v) {
              if (v.trim().isNotEmpty) _processar(v.trim());
            },
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            height: 50,
            child: FilledButton.icon(
              onPressed: _processando
                  ? null
                  : () {
                      if (_manualCtrl.text.trim().isNotEmpty) {
                        _processar(_manualCtrl.text.trim());
                      }
                    },
              style: FilledButton.styleFrom(
                backgroundColor: const Color(AppConfig.corAzul),
              ),
              icon: const Icon(Icons.check),
              label: const Text('Registrar'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPerguntaVidro() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Card(
          elevation: 3,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.help_outline, size: 56, color: Colors.blue),
                const SizedBox(height: 12),
                const Text(
                  'Esta OP tem vidro?',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                Text(
                  'A OP está na Mesa. Informe para definir o próximo setor.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                ),
                const SizedBox(height: 24),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: _processando
                            ? null
                            : () => _processar(
                                _opPendenteVidro.toString(), vidro: 'sim'),
                        style: FilledButton.styleFrom(
                          backgroundColor: Colors.blue,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                        ),
                        icon: const Icon(Icons.check),
                        label: const Text('Sim'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _processando
                            ? null
                            : () => _processar(
                                _opPendenteVidro.toString(), vidro: 'nao'),
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 14),
                        ),
                        icon: const Icon(Icons.close),
                        label: const Text('Não'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSucesso() {
    final r = _resultado!.rastreio;
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Card(
          elevation: 3,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.check_circle, size: 64, color: Colors.green),
                const SizedBox(height: 12),
                Text(
                  _resultado!.iniciou
                      ? 'Rastreio iniciado!'
                      : 'Movimentação registrada!',
                  style: const TextStyle(
                      fontSize: 20, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 16),
                if (r != null) ...[
                  _linhaInfo('OP', r.titulo),
                  _linhaInfo('Setor', _resultado!.setor?.nome ?? r.setorAtualNome),
                  if (r.obra.isNotEmpty) _linhaInfo('Obra', r.obra),
                  if (r.produto.isNotEmpty) _linhaInfo('Produto', r.produto),
                ],
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: FilledButton.icon(
                    onPressed: () {
                      setState(() {
                        _resultado = null;
                        _manualCtrl.clear();
                      });
                    },
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(AppConfig.corAzul),
                    ),
                    icon: const Icon(Icons.qr_code_scanner),
                    label: const Text('Escanear outra OP'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildErro() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Card(
          elevation: 3,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.error_outline, size: 64, color: Colors.red.shade600),
                const SizedBox(height: 12),
                const Text(
                  'Não foi possível registrar',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.red.shade50,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    _erro!,
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.red.shade800),
                  ),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: FilledButton.icon(
                    onPressed: () {
                      setState(() {
                        _erro = null;
                        _manualCtrl.clear();
                      });
                    },
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(AppConfig.corAzul),
                    ),
                    icon: const Icon(Icons.refresh),
                    label: const Text('Tentar novamente'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _linhaInfo(String label, String valor) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 70,
            child: Text(
              '$label:',
              style: TextStyle(
                  color: Colors.grey.shade600, fontWeight: FontWeight.w600),
            ),
          ),
          Expanded(
            child: Text(valor, style: const TextStyle(fontWeight: FontWeight.w500)),
          ),
        ],
      ),
    );
  }
}
