import 'package:flutter/material.dart';

import '../api_service.dart';
import '../models.dart';
import '../theme.dart';
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const CvBrand(
          fontSize: 17,
          casanovaColor: Colors.white,
          esquadriasColor: Cv.accent,
        ),
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
        backgroundColor: Cv.blue,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.qr_code_scanner),
        label: const Text('Escanear'),
      ),
      body: Column(
        children: [
          _buildCartaoUsuario(),
          _buildFiltros(),
          Expanded(child: _buildLista()),
        ],
      ),
    );
  }

  Widget _buildCartaoUsuario() {
    final u = widget.usuario;
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: Cv.brandGradient,
        borderRadius: BorderRadius.only(
          bottomLeft: Radius.circular(Cv.radiusLg),
          bottomRight: Radius.circular(Cv.radiusLg),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 18),
      child: Row(
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.14),
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white.withValues(alpha: 0.25)),
            ),
            child: const Icon(Icons.person, color: Colors.white),
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
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  u.setorProducao != null
                      ? 'Setor: ${u.setorProducao!.nome}'
                      : 'Sem setor de produção vinculado',
                  style: const TextStyle(color: Color(0xB3FFFFFF), fontSize: 13),
                ),
              ],
            ),
          ),
          if (u.podeGerenciar)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: Cv.success.withValues(alpha: 0.9),
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.verified_user, size: 13, color: Colors.white),
                  SizedBox(width: 5),
                  Text(
                    'Gerência',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildFiltros() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 14, 12, 6),
      child: Row(
        children: [
          Expanded(
            child: SegmentedButton<String>(
              showSelectedIcon: false,
              style: ButtonStyle(
                visualDensity: VisualDensity.compact,
                textStyle: WidgetStateProperty.all(
                  const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                ),
              ),
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
    );
  }

  Widget _buildLista() {
    if (_carregando) {
      return const Center(child: CircularProgressIndicator(color: Cv.blue));
    }
    if (_erro != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Cv.danger),
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
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.inbox_outlined, size: 64, color: Cv.textFaint),
            SizedBox(height: 12),
            Text(
              'Nenhuma OP em rastreio',
              style: TextStyle(color: Cv.textMuted, fontSize: 16),
            ),
            SizedBox(height: 4),
            Text(
              'Escaneie o código de barras para iniciar.',
              style: TextStyle(color: Cv.textFaint, fontSize: 13),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _carregar,
      color: Cv.blue,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(12, 6, 12, 90),
        itemCount: _rastreios.length,
        separatorBuilder: (_, __) => const SizedBox(height: 10),
        itemBuilder: (context, i) => _buildItem(_rastreios[i]),
      ),
    );
  }

  Widget _buildItem(Rastreio r) {
    final cor = r.concluida ? Cv.success : Cv.warning;
    return CvCard(
      padding: EdgeInsets.zero,
      shadow: Cv.shadowSm,
      child: InkWell(
        borderRadius: BorderRadius.circular(Cv.radius),
        onTap: () async {
          await Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => DetailScreen(api: widget.api, opId: r.opId),
            ),
          );
          _carregar();
        },
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: cor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(Cv.radiusSm),
                ),
                child: Icon(
                  r.concluida
                      ? Icons.check_circle
                      : Icons.precision_manufacturing,
                  color: cor,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'OP ${r.titulo}',
                            style: const TextStyle(
                              fontWeight: FontWeight.w700,
                              fontSize: 15,
                              color: Cv.text,
                            ),
                          ),
                        ),
                        CvBadge(
                          texto: r.concluida ? 'Concluída' : 'Em produção',
                          cor: cor,
                        ),
                      ],
                    ),
                    if (r.obra.isNotEmpty) ...[
                      const SizedBox(height: 3),
                      Text(
                        r.obra,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                            color: Cv.textMuted, fontSize: 13),
                      ),
                    ],
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        const Icon(Icons.location_on,
                            size: 14, color: Cv.textMuted),
                        const SizedBox(width: 4),
                        Text(
                          r.setorAtualNome,
                          style: const TextStyle(
                            fontSize: 12,
                            color: Cv.textMuted,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: Cv.textFaint),
            ],
          ),
        ),
      ),
    );
  }
}
