import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../api_service.dart';
import '../models.dart';
import '../theme.dart';

class ScanScreen extends StatefulWidget {
  final ApiService api;
  final Usuario usuario;
  const ScanScreen({super.key, required this.api, required this.usuario});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final _manualCtrl = TextEditingController();
  final _manualFocus = FocusNode();
  MobileScannerController? _scanner;

  bool _processando = false;
  bool _modoManual = false;
  bool _cameraErro = false;
  ResultadoScan? _resultado;
  String? _erro;
  int? _opPendenteVidro;

  @override
  void initState() {
    super.initState();
    _modoManual = kIsWeb && !_contextoSeguro();
    if (!_modoManual) {
      _scanner = MobileScannerController(
        detectionSpeed: DetectionSpeed.noDuplicates,
        formats: const [BarcodeFormat.qrCode],
      );
    }
  }

  bool _contextoSeguro() {
    final u = Uri.base;
    return u.scheme == 'https' || u.host == 'localhost' || u.host == '127.0.0.1';
  }

  @override
  void dispose() {
    _scanner?.dispose();
    _manualCtrl.dispose();
    _manualFocus.dispose();
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

  void _alternarModo() {
    setState(() {
      _modoManual = !_modoManual;
      _erro = null;
      _cameraErro = false;
    });
    if (!_modoManual) {
      _scanner ??= MobileScannerController(detectionSpeed: DetectionSpeed.noDuplicates);
    } else {
      WidgetsBinding.instance.addPostFrameCallback((_) => _manualFocus.requestFocus());
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF0B3882), Color(0xFF062254)],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              _buildHeader(),
              Expanded(child: _buildCorpo()),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back, color: Colors.white),
            onPressed: () => Navigator.of(context).pop(),
          ),
          const Expanded(
            child: Text(
              'Escanear OP',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          IconButton(
            icon: Icon(_modoManual ? Icons.qr_code_scanner : Icons.keyboard, color: Colors.white),
            onPressed: _alternarModo,
          ),
        ],
      ),
    );
  }

  Widget _buildCorpo() {
    if (_opPendenteVidro != null) return _buildPerguntaVidro();
    if (_resultado != null) return _buildSucesso();
    if (_erro != null) return _buildErro();
    return _modoManual ? _buildManual() : _buildCamera();
  }

  Widget _buildCamera() {
    if (_cameraErro) return _buildCameraIndisponivel();
    return Stack(
      alignment: Alignment.center,
      children: [
        MobileScanner(
          controller: _scanner,
          onDetect: _onDetect,
          errorBuilder: (context, error, child) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              if (mounted && !_cameraErro) setState(() => _cameraErro = true);
            });
            return _buildCameraIndisponivel();
          },
        ),
        IgnorePointer(
          child: Container(
            width: 280,
            height: 170,
            decoration: BoxDecoration(
              border: Border.all(color: Colors.white, width: 3),
              borderRadius: BorderRadius.circular(16),
            ),
          ),
        ),
        if (_processando)
          Container(
            color: Colors.black54,
            child: const Center(child: CircularProgressIndicator(color: Colors.white)),
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
              'Aponte para o QR Code da OP',
              style: TextStyle(color: Colors.white, fontSize: 13),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildCameraIndisponivel() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.no_photography_outlined, size: 56, color: Color(0xFFF59E0B)),
            const SizedBox(height: 14),
            const Text(
              'Câmera indisponível',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Colors.white),
            ),
            const SizedBox(height: 8),
            const Text(
              'O navegador só libera a câmera em HTTPS. Use o leitor Bluetooth ou digite o ID.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Color(0xB3FFFFFF), fontSize: 13, height: 1.5),
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: () {
                  setState(() {
                    _modoManual = true;
                    _cameraErro = false;
                  });
                  WidgetsBinding.instance.addPostFrameCallback((_) => _manualFocus.requestFocus());
                },
                icon: const Icon(Icons.keyboard),
                label: const Text('Digitar ID'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildManual() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          Container(
            width: 72,
            height: 72,
            decoration: const BoxDecoration(
              color: Color(0x1A4DA6FF),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.keyboard, size: 36, color: Color(0xFF4DA6FF)),
          ),
          const SizedBox(height: 16),
          const Text(
            'Digite o ID da OP',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Colors.white),
          ),
          const SizedBox(height: 4),
          const Text(
            'Use o leitor Bluetooth ou digite o ID da OP.',
            style: TextStyle(color: Color(0xB3FFFFFF), fontSize: 13),
          ),
          const SizedBox(height: 24),
          TextField(
            controller: _manualCtrl,
            focusNode: _manualFocus,
            autofocus: true,
            keyboardType: TextInputType.number,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: Colors.white),
            decoration: InputDecoration(
              hintText: 'ID da OP',
              hintStyle: const TextStyle(color: Color(0x80FFFFFF)),
              prefixIcon: const Icon(Icons.tag, color: Color(0x80FFFFFF)),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: Color(0x33FFFFFF)),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: Color(0xFF4DA6FF)),
              ),
            ),
            onSubmitted: (v) {
              if (v.trim().isNotEmpty) _processar(v.trim());
            },
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _processando
                  ? null
                  : () {
                      if (_manualCtrl.text.trim().isNotEmpty) {
                        _processar(_manualCtrl.text.trim());
                      }
                    },
              icon: const Icon(Icons.check),
              label: const Text('Consultar'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPerguntaVidro() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: const BoxDecoration(
                color: Color(0x1A4DA6FF),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.help_outline, size: 36, color: Color(0xFF4DA6FF)),
            ),
            const SizedBox(height: 16),
            const Text(
              'Esta OP tem vidro?',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white),
            ),
            const SizedBox(height: 8),
            const Text(
              'A OP está na Mesa. Informe para definir o próximo setor.',
              textAlign: TextAlign.center,
              style: TextStyle(color: Color(0xB3FFFFFF), fontSize: 13),
            ),
            const SizedBox(height: 24),
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _processando ? null : () => _processar(_opPendenteVidro.toString(), vidro: 'sim'),
                    icon: const Icon(Icons.check),
                    label: const Text('Sim'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _processando ? null : () => _processar(_opPendenteVidro.toString(), vidro: 'nao'),
                    style: OutlinedButton.styleFrom(
                      side: const BorderSide(color: Color(0x33FFFFFF)),
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
    );
  }

  Widget _buildSucesso() {
    final r = _resultado!.rastreio;
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: const Color(0xFF16A34A).withValues(alpha: 0.15),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.check_circle, size: 40, color: Color(0xFF16A34A)),
            ),
            const SizedBox(height: 16),
            Text(
              _resultado!.iniciou ? 'Rastreio Iniciado!' : 'Movimentação Registrada!',
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white),
            ),
            const SizedBox(height: 18),
            if (r != null) ...[
              _linhaInfo('OP', r.titulo),
              _linhaInfo('Setor', _resultado!.setor?.nome ?? r.setorAtualNome),
              if (r.obra.isNotEmpty) _linhaInfo('Obra', r.obra),
              if (r.produto.isNotEmpty) _linhaInfo('Produto', r.produto),
            ],
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: () {
                  setState(() {
                    _resultado = null;
                    _manualCtrl.clear();
                  });
                  if (_modoManual) {
                    WidgetsBinding.instance.addPostFrameCallback((_) => _manualFocus.requestFocus());
                  }
                },
                icon: const Icon(Icons.qr_code),
                label: const Text('Consultar outra OP'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErro() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: const Color(0xFFDC2626).withValues(alpha: 0.15),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.error_outline, size: 40, color: Color(0xFFDC2626)),
            ),
            const SizedBox(height: 16),
            const Text(
              'Não foi possível registrar',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Colors.white),
            ),
            const SizedBox(height: 14),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: const Color(0xFFDC2626).withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFDC2626).withValues(alpha: 0.3)),
              ),
              child: Text(
                _erro!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Color(0xFFDC2626), fontSize: 13),
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: () {
                  setState(() {
                    _erro = null;
                    _manualCtrl.clear();
                  });
                  if (_modoManual) {
                    WidgetsBinding.instance.addPostFrameCallback((_) => _manualFocus.requestFocus());
                  }
                },
                icon: const Icon(Icons.refresh),
                label: const Text('Tentar novamente'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _linhaInfo(String label, String valor) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
            child: Text(
              label,
              style: const TextStyle(
                color: Color(0xB3FFFFFF),
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          Expanded(
            child: Text(
              valor,
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                color: Colors.white,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
