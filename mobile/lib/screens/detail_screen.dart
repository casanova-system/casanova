import 'package:flutter/material.dart';

import '../api_service.dart';
import '../models.dart';
import '../theme.dart';

class DetailScreen extends StatefulWidget {
  final ApiService api;
  final int opId;
  const DetailScreen({super.key, required this.api, required this.opId});

  @override
  State<DetailScreen> createState() => _DetailScreenState();
}

class _DetailScreenState extends State<DetailScreen> {
  Rastreio? _rastreio;
  bool _carregando = true;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      final r = await widget.api.rastreioDetalhe(widget.opId);
      setState(() => _rastreio = r);
    } catch (e) {
      setState(() => _erro = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      setState(() => _carregando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('OP ${_rastreio?.titulo ?? widget.opId}'),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _carregar),
        ],
      ),
      body: _buildCorpo(),
    );
  }

  Widget _buildCorpo() {
    if (_carregando) {
      return const Center(child: CircularProgressIndicator(color: Cv.blue));
    }
    if (_erro != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(_erro!, textAlign: TextAlign.center),
        ),
      );
    }
    final r = _rastreio!;
    return RefreshIndicator(
      onRefresh: _carregar,
      color: Cv.blue,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildStatus(r),
          const SizedBox(height: 16),
          _secao('Dados da OP', [
            _linha('OP', r.titulo),
            if (r.obra.isNotEmpty) _linha('Obra', r.obra),
            if (r.produto.isNotEmpty) _linha('Produto', r.produto),
            if (r.variante.isNotEmpty) _linha('Variante', r.variante),
            _linha(
              'Tem vidro?',
              r.temVidro == null ? 'A definir' : (r.temVidro! ? 'Sim' : 'Não'),
            ),
          ]),

        ],
      ),
    );
  }

  Widget _buildStatus(Rastreio r) {
    final cor = r.concluida ? Cv.success : Cv.warning;
    final fundo = r.concluida ? Cv.successSoft : Cv.warningSoft;
    return CvCard(
      color: fundo,
      borderColor: cor.withValues(alpha: 0.3),
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: cor.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(Cv.radiusSm),
            ),
            child: Icon(
              r.concluida ? Icons.check_circle : Icons.precision_manufacturing,
              color: cor,
              size: 28,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  r.concluida ? 'OP Concluída' : 'Em Produção',
                  style: const TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                      color: Cv.text),
                ),
                const SizedBox(height: 2),
                Text(
                  'Setor atual: ${r.setorAtualNome}',
                  style: const TextStyle(color: Cv.textMuted, fontSize: 13),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _secao(String titulo, List<Widget> filhos) {
    return CvCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            titulo,
            style: const TextStyle(
              fontWeight: FontWeight.w700,
              fontSize: 15,
              color: Cv.blue,
            ),
          ),
          const Divider(height: 20),
          ...filhos,
        ],
      ),
    );
  }

  Widget _linha(String label, String valor) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              label,
              style: const TextStyle(
                  color: Cv.textMuted, fontWeight: FontWeight.w600),
            ),
          ),
          Expanded(
            child: Text(
              valor,
              style: const TextStyle(
                  fontWeight: FontWeight.w500, color: Cv.text),
            ),
          ),
        ],
      ),
    );
  }


}
