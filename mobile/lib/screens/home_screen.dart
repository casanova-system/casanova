import 'package:flutter/material.dart';

import '../api_service.dart';
import '../config.dart';
import '../models.dart';
import 'detail_screen.dart';
import 'login_screen.dart';
import 'scan_screen.dart';

class HomeScreen extends StatefulWidget {
  final ApiService api;
  final Usuario usuario;
  const HomeScreen({super.key, required this.api, required this.usuario});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  List<Rastreio> _rastreios = [];
  bool _carregando = true;
  String? _erro;
  String _filtroStatus = '';

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
      final lista = await widget.api.rastreios(status: _filtroStatus);
      setState(() => _rastreios = lista);
    } catch (e) {
      setState(() => _erro = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      setState(() => _carregando = false);
    }
  }

  Future<void> _sair() async {
    await widget.api.logout();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => LoginScreen(api: widget.api)),
    );
  }

  Future<void> _abrirScanner() async {
    final resultado = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => ScanScreen(api: widget.api, usuario: widget.usuario),
      ),
    );
    if (resultado == true) _carregar();
  }

  Color _corStatus(Rastreio r) =>
      r.concluida ? Colors.green : Colors.orange;

  @override
  Widget build(BuildContext context) {
    final u = widget.usuario;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Rastreio de Produção'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Sair',
            onPressed: _sair,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _abrirScanner,
        backgroundColor: const Color(AppConfig.corAzul),
        foregroundColor: Colors.white,
        icon: const Icon(Icons.qr_code_scanner),
        label: const Text('Escanear'),
      ),
      body: Column(
        children: [
          // Cartão do usuário
          Container(
            width: double.infinity,
            color: const Color(AppConfig.corAzul),
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Row(
              children: [
                const CircleAvatar(
                  backgroundColor: Colors.white24,
                  child: Icon(Icons.person, color: Colors.white),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        u.nome,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),
                      Text(
                        u.setorProducao != null
                            ? 'Setor: ${u.setorProducao!.nome}'
                            : 'Sem setor de produção vinculado',
                        style: const TextStyle(color: Colors.white70, fontSize: 13),
                      ),
                    ],
                  ),
                ),
                if (u.podeGerenciar)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.green.shade400,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Text(
                      'Gerência',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.bold),
                    ),
                  ),
              ],
            ),
          ),

          // Filtros
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(value: '', label: Text('Todas')),
                      ButtonSegment(value: 'EM_PRODUCAO', label: Text('Produção')),
                      ButtonSegment(value: 'CONCLUIDA', label: Text('Concluídas')),
                    ],
                    selected: {_filtroStatus},
                    onSelectionChanged: (s) {
                      setState(() => _filtroStatus = s.first);
                      _carregar();
                    },
                  ),
                ),
              ],
            ),
          ),

          // Lista
          Expanded(child: _buildLista()),
        ],
      ),
    );
  }

  Widget _buildLista() {
    if (_carregando) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_erro != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.red),
              const SizedBox(height: 12),
              Text(_erro!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              OutlinedButton.icon(
                onPressed: _carregar,
                icon: const Icon(Icons.refresh),
                label: const Text('Tentar novamente'),
              ),
            ],
          ),
        ),
      );
    }
    if (_rastreios.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.inbox_outlined, size: 64, color: Colors.grey.shade400),
            const SizedBox(height: 12),
            Text(
              'Nenhuma OP em rastreio',
              style: TextStyle(color: Colors.grey.shade600, fontSize: 16),
            ),
            const SizedBox(height: 4),
            Text(
              'Escaneie o código de barras para iniciar.',
              style: TextStyle(color: Colors.grey.shade500, fontSize: 13),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _carregar,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(12, 0, 12, 90),
        itemCount: _rastreios.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (context, i) {
          final r = _rastreios[i];
          return Card(
            elevation: 1,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: Colors.grey.shade200),
            ),
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              leading: CircleAvatar(
                backgroundColor: _corStatus(r).withValues(alpha: 0.15),
                child: Icon(
                  r.concluida ? Icons.check_circle : Icons.precision_manufacturing,
                  color: _corStatus(r),
                ),
              ),
              title: Text(
                'OP ${r.titulo}',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              subtitle: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (r.obra.isNotEmpty)
                    Text(r.obra, maxLines: 1, overflow: TextOverflow.ellipsis),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(Icons.location_on,
                          size: 14, color: Colors.grey.shade600),
                      const SizedBox(width: 4),
                      Text(
                        r.setorAtualNome,
                        style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey.shade700,
                            fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ],
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () async {
                await Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => DetailScreen(api: widget.api, opId: r.opId),
                  ),
                );
                _carregar();
              },
            ),
          );
        },
      ),
    );
  }
}
