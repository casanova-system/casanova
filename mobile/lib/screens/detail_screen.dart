import 'package:flutter/material.dart';

import '../api_service.dart';
import '../config.dart';
import '../models.dart';

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
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _carregar,
          ),
        ],
      ),
      body: _buildCorpo(),
    );
  }

  Widget _buildCorpo() {
    if (_carregando) {
      return const Center(child: CircularProgressIndicator());
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
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Status
          Card(
            color: r.concluida ? Colors.green.shade50 : Colors.orange.shade50,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(
                color: r.concluida ? Colors.green.shade200 : Colors.orange.shade200,
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Icon(
                    r.concluida ? Icons.check_circle : Icons.precision_manufacturing,
                    color: r.concluida ? Colors.green : Colors.orange,
                    size: 32,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          r.concluida ? 'OP Concluída' : 'Em Produção',
                          style: const TextStyle(
                              fontWeight: FontWeight.bold, fontSize: 16),
                        ),
                        Text(
                          'Setor atual: ${r.setorAtualNome}',
                          style: TextStyle(color: Colors.grey.shade700),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Dados da OP
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
          const SizedBox(height: 16),

          // Histórico
          _secao('Histórico de Movimentações', [
            if (r.movimentacoes.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(
                  'Nenhuma movimentação registrada.',
                  style: TextStyle(color: Colors.grey.shade600),
                ),
              )
            else
              ...r.movimentacoes.map(_itemMovimentacao),
          ]),
        ],
      ),
    );
  }

  Widget _secao(String titulo, List<Widget> filhos) {
    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: Colors.grey.shade200),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              titulo,
              style: const TextStyle(
                fontWeight: FontWeight.bold,
                fontSize: 15,
                color: Color(AppConfig.corAzul),
              ),
            ),
            const Divider(height: 20),
            ...filhos,
          ],
        ),
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

  Widget _itemMovimentacao(Movimentacao m) {
    final data =
        '${m.dataHora.day.toString().padLeft(2, '0')}/${m.dataHora.month.toString().padLeft(2, '0')} '
        '${m.dataHora.hour.toString().padLeft(2, '0')}:${m.dataHora.minute.toString().padLeft(2, '0')}';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: const BoxDecoration(
              color: Color(AppConfig.corAzul),
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  m.setorNome,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                Text(
                  '${m.usuario ?? "—"} • $data',
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
