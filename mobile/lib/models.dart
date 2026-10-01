// Modelos de dados do app.

class Setor {
  final String codigo;
  final String nome;
  final int ordem;
  final bool requerVidro;

  Setor({
    required this.codigo,
    required this.nome,
    required this.ordem,
    required this.requerVidro,
  });

  factory Setor.fromJson(Map<String, dynamic> j) => Setor(
        codigo: j['codigo'] ?? '',
        nome: j['nome'] ?? '',
        ordem: j['ordem'] ?? 0,
        requerVidro: j['requer_vidro'] ?? false,
      );
}

class Usuario {
  final int id;
  final String username;
  final String nome;
  final String? nivelAcesso;
  final Setor? setorProducao;
  final bool podeGerenciar;

  Usuario({
    required this.id,
    required this.username,
    required this.nome,
    this.nivelAcesso,
    this.setorProducao,
    required this.podeGerenciar,
  });

  factory Usuario.fromJson(Map<String, dynamic> j) => Usuario(
        id: j['id'] ?? 0,
        username: j['username'] ?? '',
        nome: j['nome'] ?? '',
        nivelAcesso: j['nivel_acesso'],
        setorProducao: j['setor_producao'] != null
            ? Setor.fromJson(j['setor_producao'])
            : null,
        podeGerenciar: j['pode_gerenciar'] ?? false,
      );
}

class Movimentacao {
  final String setor;
  final String setorNome;
  final String? usuario;
  final String observacao;
  final DateTime dataHora;

  Movimentacao({
    required this.setor,
    required this.setorNome,
    this.usuario,
    required this.observacao,
    required this.dataHora,
  });

  factory Movimentacao.fromJson(Map<String, dynamic> j) => Movimentacao(
        setor: j['setor'] ?? '',
        setorNome: j['setor_nome'] ?? '',
        usuario: j['usuario'],
        observacao: j['observacao'] ?? '',
        dataHora: DateTime.tryParse(j['data_hora'] ?? '')?.toLocal() ??
            DateTime.now(),
      );
}

class Rastreio {
  final int opId;
  final String opNumero;
  final String obra;
  final String produto;
  final String variante;
  final bool? temVidro;
  final String setorAtual;
  final String setorAtualNome;
  final String status;
  final bool concluida;
  final DateTime atualizadoEm;
  final List<Movimentacao> movimentacoes;

  Rastreio({
    required this.opId,
    required this.opNumero,
    required this.obra,
    required this.produto,
    required this.variante,
    this.temVidro,
    required this.setorAtual,
    required this.setorAtualNome,
    required this.status,
    required this.concluida,
    required this.atualizadoEm,
    this.movimentacoes = const [],
  });

  factory Rastreio.fromJson(Map<String, dynamic> j) => Rastreio(
        opId: j['op_id'] ?? 0,
        opNumero: j['op_numero'] ?? '',
        obra: j['obra'] ?? '',
        produto: j['produto'] ?? '',
        variante: j['variante'] ?? '',
        temVidro: j['tem_vidro'],
        setorAtual: j['setor_atual'] ?? '',
        setorAtualNome: j['setor_atual_nome'] ?? '',
        status: j['status'] ?? '',
        concluida: j['concluida'] ?? false,
        atualizadoEm:
            DateTime.tryParse(j['atualizado_em'] ?? '')?.toLocal() ?? DateTime.now(),
        movimentacoes: (j['movimentacoes'] as List<dynamic>? ?? [])
            .map((m) => Movimentacao.fromJson(m))
            .toList(),
      );

  String get titulo => opNumero.isNotEmpty ? opNumero : opId.toString();
}

/// Resultado de uma leitura de código de barras.
class ResultadoScan {
  final bool ok;
  final bool precisaVidro;
  final int? opId;
  final String? erro;
  final String? mensagem;
  final bool iniciou;
  final Setor? setor;
  final Rastreio? rastreio;

  ResultadoScan({
    required this.ok,
    this.precisaVidro = false,
    this.opId,
    this.erro,
    this.mensagem,
    this.iniciou = false,
    this.setor,
    this.rastreio,
  });

  factory ResultadoScan.fromJson(Map<String, dynamic> j) => ResultadoScan(
        ok: j['ok'] ?? false,
        precisaVidro: j['precisa_vidro'] ?? false,
        opId: j['op_id'],
        erro: j['erro'],
        mensagem: j['mensagem'],
        iniciou: j['iniciou'] ?? false,
        setor: j['setor'] != null ? Setor.fromJson(j['setor']) : null,
        rastreio: j['rastreio'] != null ? Rastreio.fromJson(j['rastreio']) : null,
      );
}
