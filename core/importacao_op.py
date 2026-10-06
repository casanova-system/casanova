"""Leitura da planilha de Ordens de Produção gerada pelo Alumisoft (CEM Pro).

Formato do arquivo
------------------
Uma única aba (``Page 1``) onde cada OP ocupa uma faixa vertical da planilha.
A OP é identificada pelo valor da coluna **E** no formato ``J01``, ``J02``...

::

    E1   J01                              <- identificação da OP
    A4   Emitido por: <nome>      O4 <data>
    A5   Cód Esqd:    <código>    E5 Proj.: <projeto>
    A6   Descrição:   <texto>
    A8   Qtde: <qtd>  C8 <largura vão>  E8 <altura vão>
    A9   Tratamento:  <texto>
    A10  Cód. Obra:   <código>
    A12  Cliente:     <nome>
    A13  Obra:        <nome>
    A16  Vidros: <descrição>      N16 <localização>
    A21  Perfis       -> tabela de perfis
    A52  Componentes  -> tabela de componentes
    A93  Vidros       -> tabela de vidros

Repetição de blocos
-------------------
Quando o relatório passa de página, o Alumisoft **repete o cabeçalho** das
tabelas: ``Perfis``/``Componentes``/``Vidros`` aparecem mais de uma vez dentro
da mesma OP (ex.: a OP J01 tem 2 blocos de Perfis e 2 de Componentes).

O leitor percorre a OP inteira e **soma todos os blocos**. Parar na primeira
linha em branco — comportamento anterior — descartava silenciosamente metade
dos perfis e componentes de cada OP.
"""
from decimal import Decimal, InvalidOperation
import re
import unicodedata

import openpyxl
from django.db import transaction

from core.models import Obra, ObraOP, ObraOPComponente, ObraOPItem, ObraOPVidro

ABA_PADRAO = 'Page 1'

# Identificação da OP na coluna E (ex.: J01, J02, ...)
PADRAO_DOCUMENTO = re.compile(r'^(J\d+)$')

# Seções (tabelas) que podem se repetir dentro da mesma OP
SECOES = ('Perfis', 'Componentes', 'Vidros')

# ---------------------------------------------------------------------------
# Mapa de colunas (1 = A)
# ---------------------------------------------------------------------------
COL_ROTULO = 1                 # A  rótulo do cabeçalho
COL_VALOR = 2                  # B  valor do cabeçalho
COL_DOCUMENTO = 5              # E  identificação da OP (J01...)
COL_LARGURA_VAO = 3            # C  largura do vão acabado
COL_ALTURA_VAO = 5             # E  altura do vão acabado
COL_DATA_EMISSAO = 15          # O  data de emissão
COL_LOCALIZACAO_ROTULO = 13    # M  rótulo "Localização:"
COL_LOCALIZACAO_VALOR = 14     # N  localização do vidro

COLS_PERFIL = {
    'codigo': 2,        # B
    'tipo': 4,          # D  (ID: CM, SA, TA, AZ, SBRUTO...)
    'orientacao': 6,    # F  (L/H)
    'corte': 8,         # H
    'tamanho': 11,      # K
    'quantidade': 13,   # M
    'peso': 14,         # N
    'observacao': 16,   # P
}
COLS_COMPONENTE = {
    'codigo': 3,        # C
    'descricao': 5,     # E
    'quantidade': 14,   # N
    'unidade': 16,      # P
    'observacao': 17,   # Q
}
COLS_VIDRO = {
    'codigo': 2,        # B
    'descricao': 4,     # D
    'cor': 9,           # I
    'quantidade': 13,   # M
    'largura': 14,      # N
    'altura': 15,       # O
    'observacao': 17,   # Q
}

# Rótulos do cabeçalho da OP -> chave interna
ROTULOS_CABECALHO = {
    'cod esqd': 'codigo_esquadria',
    'descricao': 'descricao',
    'tratamento': 'tratamento',
    'cod. obra': 'codigo_obra',
    'cliente': 'cliente',
    'obra': 'nome_obra',
    'proj.': 'projeto',
    'emitido por': 'emitido_por',
    'qtde': 'quantidade',
    'vidros': 'vidro_descricao',
}

# ID do perfil (coluna D) -> tipo de perfil do sistema. Casa pelo prefixo
# porque o Excel traz o acabamento junto (ex.: AZ-P-RAL9005F).
MAPA_TIPO_PERFIL = (
    ('SBRUTO', 'CONEXAO'),
    ('CUNHA', 'CUNHA'),
    ('CM', 'CM'),
    ('SA', 'MARCO'),
    ('TA', 'FOLHA'),
    ('AZ', 'ARREMATE'),
    ('MARCO', 'MARCO'),
    ('ARREMATE', 'ARREMATE'),
    ('FOLHA', 'FOLHA'),
    ('CONEXAO', 'CONEXAO'),
)

# Limites dos campos de texto (evita erro de banco em descrições longas)
LIMITE_CODIGO = 50
LIMITE_OBSERVACAO = 255
LIMITE_UNIDADE = 10
LIMITE_ORIENTACAO = 10
LIMITE_CORTE = 20
LIMITE_APLICACAO = 50


class ErroImportacaoOP(Exception):
    """Erro de leitura/validação do arquivo de Ordens de Produção."""


# ---------------------------------------------------------------------------
# Conversores
# ---------------------------------------------------------------------------
def _normalizar(texto):
    """Minúsculas, sem acento e sem ':' final — para casar rótulos."""
    texto = str(texto or '').strip().rstrip(':').lower()
    texto = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in texto if not unicodedata.combining(c))


def _celula(ws, linha, coluna):
    """Conteúdo de uma célula como texto limpo ('' quando vazia)."""
    if linha < 1 or coluna < 1:
        return ''
    valor = ws.cell(row=linha, column=coluna).value
    if valor is None:
        return ''
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _eh_numero(valor):
    """True se o valor puder ser interpretado como número."""
    if isinstance(valor, (int, float, Decimal)):
        return True
    texto = str(valor or '').strip().replace(' ', '')
    if not texto:
        return False
    if ',' in texto and '.' in texto:
        texto = (
            texto.replace('.', '').replace(',', '.')
            if texto.rfind(',') > texto.rfind('.')
            else texto.replace(',', '')
        )
    else:
        texto = texto.replace(',', '.')
    try:
        float(texto)
        return True
    except ValueError:
        return False


def _inteiro(valor, padrao=0):
    """Converte para inteiro tolerando '2.289,7', '2289.7' ou vazio."""
    if isinstance(valor, bool):
        return padrao
    if isinstance(valor, (int, float, Decimal)):
        try:
            return int(round(float(valor)))
        except (TypeError, ValueError):
            return padrao
    texto = str(valor or '').strip().replace(' ', '')
    if not texto:
        return padrao
    if ',' in texto and '.' in texto:
        texto = (
            texto.replace('.', '').replace(',', '.')
            if texto.rfind(',') > texto.rfind('.')
            else texto.replace(',', '')
        )
    else:
        texto = texto.replace(',', '.')
    try:
        return int(round(float(texto)))
    except (TypeError, ValueError):
        return padrao


def _decimal(valor, padrao=None):
    """Converte para Decimal tolerando separadores pt-BR.

    ``padrao`` é devolvido quando o valor não é numérico (o chamador decide se
    usa ``Decimal('0')`` ou ``None`` para "não informado").
    """
    if isinstance(valor, bool):
        return padrao
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, float)):
        try:
            return Decimal(str(valor))
        except InvalidOperation:
            return padrao
    texto = str(valor or '').strip().replace(' ', '')
    if not texto:
        return padrao
    if ',' in texto and '.' in texto:
        texto = (
            texto.replace('.', '').replace(',', '.')
            if texto.rfind(',') > texto.rfind('.')
            else texto.replace(',', '')
        )
    elif ',' in texto:
        texto = texto.replace(',', '.')
    try:
        return Decimal(texto)
    except InvalidOperation:
        return padrao


def _corta(texto, limite):
    return str(texto or '').strip()[:limite]


def mapear_tipo_perfil(valor):
    """Traduz o ID do perfil do Excel para o tipo do sistema."""
    texto = str(valor or '').strip().upper()
    if not texto:
        return 'OUTRO'
    for prefixo, tipo in MAPA_TIPO_PERFIL:
        if texto == prefixo or texto.startswith(f'{prefixo}-') or texto.startswith(f'{prefixo}_'):
            return tipo
    return 'OUTRO'


# ---------------------------------------------------------------------------
# Leitura da planilha
# ---------------------------------------------------------------------------
def _localizar_marcadores(ws):
    """Linhas (1-based) onde começa cada OP (coluna E com J01, J02...)."""
    return [
        linha
        for linha in range(1, ws.max_row + 1)
        if PADRAO_DOCUMENTO.match(_celula(ws, linha, COL_DOCUMENTO))
    ]


def _localizar_blocos(ws, linha_inicio, linha_fim):
    """Faixas das tabelas dentro de uma OP.

    Devolve ``[(nome, linha_cabecalho, linha_fim_exclusiva), ...]``. Como o
    Alumisoft repete os cabeçalhos a cada quebra de página, podem existir
    vários blocos com o mesmo nome — todos são devolvidos.
    """
    marcadores = []
    for linha in range(linha_inicio, linha_fim):
        marcador = _celula(ws, linha, COL_ROTULO)
        if marcador in SECOES:
            marcadores.append((marcador, linha))

    blocos = []
    for indice, (nome, linha_marcador) in enumerate(marcadores):
        proximo = marcadores[indice + 1][1] if indice + 1 < len(marcadores) else linha_fim
        # linha_marcador + 1 é a linha de títulos ("Pos.", "Código"...)
        blocos.append((nome, linha_marcador + 1, proximo))
    return blocos


def _linha_de_dados(ws, linha):
    """False para linhas de título ('Pos.') ou vazias."""
    return _celula(ws, linha, COL_ROTULO) != 'Pos.'


def _ler_cabecalho(ws, linha_inicio, linha_fim):
    """Extrai o cabeçalho da OP casando os rótulos da coluna A."""
    dados = {
        'documento': _celula(ws, linha_inicio, COL_DOCUMENTO),
        'codigo_esquadria': '',
        'descricao': '',
        'tratamento': '',
        'codigo_obra': '',
        'cliente': '',
        'nome_obra': '',
        'projeto': '',
        'emitido_por': '',
        'data_emissao': '',
        'quantidade': 1,
        'largura': 0,
        'altura': 0,
        'vidro_descricao': '',
        'vidro_localizacao': '',
    }

    limite = min(linha_inicio + 24, linha_fim)
    for linha in range(linha_inicio, limite):
        chave = ROTULOS_CABECALHO.get(_normalizar(_celula(ws, linha, COL_ROTULO)))
        if not chave:
            continue

        valor = _celula(ws, linha, COL_VALOR)
        if chave == 'quantidade':
            dados['quantidade'] = _inteiro(valor, 1) or 1
            dados['largura'] = _inteiro(_celula(ws, linha, COL_LARGURA_VAO), 0)
            dados['altura'] = _inteiro(_celula(ws, linha, COL_ALTURA_VAO), 0)
        elif chave == 'vidro_descricao':
            dados['vidro_descricao'] = valor
            if _normalizar(_celula(ws, linha, COL_LOCALIZACAO_ROTULO)) == 'localizacao':
                dados['vidro_localizacao'] = _celula(ws, linha, COL_LOCALIZACAO_VALOR)
        elif chave == 'emitido_por':
            dados['emitido_por'] = valor
            dados['data_emissao'] = _celula(ws, linha, COL_DATA_EMISSAO)
        else:
            dados[chave] = valor

    return dados


def _ler_perfis(ws, linha_inicio, linha_fim):
    """Perfis de todos os blocos + o 'Peso Total:' impresso pelo Alumisoft."""
    perfis = []
    peso_total = None

    for nome, linha_cabecalho, fim in _localizar_blocos(ws, linha_inicio, linha_fim):
        if nome != 'Perfis':
            continue
        for linha in range(linha_cabecalho + 1, fim):
            if not _linha_de_dados(ws, linha):
                continue

            tamanho = _celula(ws, linha, COLS_PERFIL['tamanho'])
            if tamanho.lower().startswith('peso total'):
                peso_total = _decimal(_celula(ws, linha, COLS_PERFIL['peso']), None)
                continue

            quantidade = _celula(ws, linha, COLS_PERFIL['quantidade'])
            if not _eh_numero(tamanho) or not _eh_numero(quantidade):
                continue

            perfis.append({
                'codigo': _celula(ws, linha, COLS_PERFIL['codigo']),
                'tipo': _celula(ws, linha, COLS_PERFIL['tipo']),
                'orientacao': _celula(ws, linha, COLS_PERFIL['orientacao']),
                'corte': _celula(ws, linha, COLS_PERFIL['corte']),
                'tamanho': _inteiro(tamanho, 0),
                'quantidade': _inteiro(quantidade, 1) or 1,
                'peso': _decimal(_celula(ws, linha, COLS_PERFIL['peso'])),
                'observacao': _celula(ws, linha, COLS_PERFIL['observacao']),
            })

    return perfis, peso_total


def _ler_componentes(ws, linha_inicio, linha_fim):
    """Componentes de todos os blocos, guardando a aplicação (Fábrica/Obra)."""
    componentes = []
    aplicacao = ''

    for nome, linha_cabecalho, fim in _localizar_blocos(ws, linha_inicio, linha_fim):
        if nome != 'Componentes':
            continue
        for linha in range(linha_cabecalho + 1, fim):
            if _normalizar(_celula(ws, linha, COL_ROTULO)) == 'aplicacao':
                aplicacao = _corta(_celula(ws, linha, COL_VALOR), LIMITE_APLICACAO)
                continue
            if not _linha_de_dados(ws, linha):
                continue

            codigo = _celula(ws, linha, COLS_COMPONENTE['codigo'])
            descricao = _celula(ws, linha, COLS_COMPONENTE['descricao'])
            quantidade = _celula(ws, linha, COLS_COMPONENTE['quantidade'])
            if not (codigo or descricao) or not _eh_numero(quantidade):
                continue

            componentes.append({
                'codigo': codigo,
                'descricao': descricao,
                'aplicacao': aplicacao,
                'quantidade': _inteiro(quantidade, 1) or 1,
                'unidade': _celula(ws, linha, COLS_COMPONENTE['unidade']),
                'observacao': _celula(ws, linha, COLS_COMPONENTE['observacao']),
            })

    return componentes


def _ler_vidros(ws, linha_inicio, linha_fim):
    """Vidros de todos os blocos da OP."""
    vidros = []

    for nome, linha_cabecalho, fim in _localizar_blocos(ws, linha_inicio, linha_fim):
        if nome != 'Vidros':
            continue
        for linha in range(linha_cabecalho + 1, fim):
            if not _linha_de_dados(ws, linha):
                continue

            codigo = _celula(ws, linha, COLS_VIDRO['codigo'])
            descricao = _celula(ws, linha, COLS_VIDRO['descricao'])
            if not (codigo or descricao):
                continue

            vidros.append({
                'codigo': codigo,
                'descricao': descricao,
                'cor': _celula(ws, linha, COLS_VIDRO['cor']),
                'quantidade': _inteiro(_celula(ws, linha, COLS_VIDRO['quantidade']), 1) or 1,
                'largura': _inteiro(_celula(ws, linha, COLS_VIDRO['largura']), 0),
                'altura': _inteiro(_celula(ws, linha, COLS_VIDRO['altura']), 0),
                'observacao': _celula(ws, linha, COLS_VIDRO['observacao']),
            })

    return vidros


def _ler_op(ws, linha_inicio, linha_fim):
    """Lê uma OP completa (cabeçalho + perfis + componentes + vidros)."""
    cabecalho = _ler_cabecalho(ws, linha_inicio, linha_fim)
    perfis, peso_total = _ler_perfis(ws, linha_inicio, linha_fim)
    componentes = _ler_componentes(ws, linha_inicio, linha_fim)
    vidros = _ler_vidros(ws, linha_inicio, linha_fim)

    # Fallback: sem as dimensões do vão no cabeçalho, usa as do primeiro vidro
    if vidros:
        if not cabecalho['largura']:
            cabecalho['largura'] = vidros[0]['largura']
        if not cabecalho['altura']:
            cabecalho['altura'] = vidros[0]['altura']
        if not cabecalho['vidro_descricao']:
            cabecalho['vidro_descricao'] = vidros[0]['descricao']

    return {
        'cabecalho': cabecalho,
        'perfis': perfis,
        'componentes': componentes,
        'vidros': vidros,
        'peso_total': peso_total,
    }


def ler_ops(origem):
    """Lê o arquivo (caminho ou upload) e devolve a lista de OPs encontradas."""
    wb = openpyxl.load_workbook(origem, data_only=True)
    try:
        if ABA_PADRAO in wb.sheetnames:
            ws = wb[ABA_PADRAO]
        else:
            ws = wb.active
        if ws is None:
            return []

        marcadores = _localizar_marcadores(ws)
        if not marcadores:
            return []

        limites = marcadores + [ws.max_row + 1]
        return [
            _ler_op(ws, marcadores[i], limites[i + 1])
            for i in range(len(marcadores))
        ]
    finally:
        wb.close()


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------
class ResumoImportacao:
    """Contadores do que foi gravado, para a mensagem de retorno."""

    def __init__(self):
        self.obras = 0
        self.ops_criadas = 0
        self.ops_atualizadas = 0
        self.perfis = 0
        self.componentes = 0
        self.vidros = 0
        self.ignoradas = 0

    @property
    def ops(self):
        return self.ops_criadas + self.ops_atualizadas

    def mensagem(self):
        texto = (
            f'Importação concluída: {self.ops} OP(s) — '
            f'{self.ops_criadas} nova(s), {self.ops_atualizadas} atualizada(s), '
            f'{self.perfis} perfil(is), {self.componentes} componente(s), '
            f'{self.vidros} vidro(s) em {self.obras} obra(s).'
        )
        if self.ignoradas:
            texto += (
                f' {self.ignoradas} OP(s) ignorada(s) por não terem '
                f'código de obra no cabeçalho.'
            )
        return texto


def _obter_obra(codigo, cabecalho):
    """Obra existente ou nova; completa campos vazios com o que veio do Excel."""
    obra, criada = Obra.objects.get_or_create(
        codigo=_corta(codigo, 50),
        defaults={
            'nome': _corta(cabecalho.get('nome_obra') or f'Obra {codigo}', 255),
            'cliente': _corta(cabecalho.get('cliente'), 255),
            'tratamento_cor': _corta(cabecalho.get('tratamento'), 100),
        },
    )
    if criada:
        return obra

    alterados = []
    if not obra.nome and cabecalho.get('nome_obra'):
        obra.nome = _corta(cabecalho['nome_obra'], 255)
        alterados.append('nome')
    if not obra.cliente and cabecalho.get('cliente'):
        obra.cliente = _corta(cabecalho['cliente'], 255)
        alterados.append('cliente')
    if not obra.tratamento_cor and cabecalho.get('tratamento'):
        obra.tratamento_cor = _corta(cabecalho['tratamento'], 100)
        alterados.append('tratamento_cor')
    if alterados:
        obra.save(update_fields=alterados)
    return obra


def _gravar_op(obra, dados):
    """Cria/atualiza a OP e substitui perfis, componentes e vidros."""
    cabecalho = dados['cabecalho']
    documento = _corta(cabecalho['documento'], 20)

    op_obj, criada = ObraOP.objects.update_or_create(
        obra=obra,
        codigo_documento=documento,
        defaults={
            'codigo_esquadria': _corta(
                cabecalho.get('codigo_esquadria') or documento, 50
            ),
            'descricao': cabecalho.get('descricao') or '',
            'quantidade': cabecalho.get('quantidade') or 1,
            'largura': cabecalho.get('largura') or 0,
            'altura': cabecalho.get('altura') or 0,
            'tratamento': _corta(cabecalho.get('tratamento'), 100),
            'vidro_descricao': _corta(cabecalho.get('vidro_descricao'), 255),
            'vidro_localizacao': _corta(cabecalho.get('vidro_localizacao'), 255),
        },
    )

    op_obj.itens.all().delete()
    ObraOPItem.objects.bulk_create([
        ObraOPItem(
            op=op_obj,
            posicao=indice,
            codigo=_corta(perfil['codigo'], LIMITE_CODIGO),
            tipo_perfil=mapear_tipo_perfil(perfil['tipo']),
            orientacao=_corta(perfil['orientacao'], LIMITE_ORIENTACAO),
            corte=_corta(perfil['corte'], LIMITE_CORTE),
            tamanho=perfil['tamanho'],
            quantidade=perfil['quantidade'],
            peso=perfil['peso'],
            observacao=_corta(perfil['observacao'], LIMITE_OBSERVACAO),
        )
        for indice, perfil in enumerate(dados['perfis'])
    ])

    op_obj.componentes.all().delete()
    ObraOPComponente.objects.bulk_create([
        ObraOPComponente(
            op=op_obj,
            posicao=indice,
            codigo=_corta(componente['codigo'], LIMITE_CODIGO),
            descricao=componente['descricao'] or '',
            aplicacao=_corta(componente['aplicacao'], LIMITE_APLICACAO),
            quantidade=componente['quantidade'],
            unidade=_corta(componente['unidade'], LIMITE_UNIDADE),
            observacao=_corta(componente['observacao'], LIMITE_OBSERVACAO),
        )
        for indice, componente in enumerate(dados['componentes'])
    ])

    op_obj.vidros.all().delete()
    ObraOPVidro.objects.bulk_create([
        ObraOPVidro(
            op=op_obj,
            posicao=indice,
            codigo=_corta(vidro['codigo'], LIMITE_CODIGO),
            descricao=_corta(vidro['descricao'], LIMITE_OBSERVACAO),
            cor=_corta(vidro['cor'], 100),
            quantidade=vidro['quantidade'],
            largura=vidro['largura'],
            altura=vidro['altura'],
            observacao=_corta(vidro['observacao'], LIMITE_OBSERVACAO),
        )
        for indice, vidro in enumerate(dados['vidros'])
    ])

    return op_obj, criada


@transaction.atomic
def importar_ops(origem):
    """Importa todas as OPs do arquivo numa única transação.

    Se qualquer OP falhar, nada é gravado — evita importação pela metade.
    """
    ops = ler_ops(origem)
    if not ops:
        raise ErroImportacaoOP(
            'Nenhuma OP foi encontrada no arquivo. Confirme que o relatório foi '
            'gerado pelo Alumisoft (aba "Page 1", OPs identificadas na coluna E '
            'como J01, J02...).'
        )

    resumo = ResumoImportacao()
    obras_vistas = set()

    for dados in ops:
        codigo_obra = (dados['cabecalho'].get('codigo_obra') or '').strip()
        if not codigo_obra:
            resumo.ignoradas += 1
            continue

        obra = _obter_obra(codigo_obra, dados['cabecalho'])
        if obra.pk not in obras_vistas:
            obras_vistas.add(obra.pk)
            resumo.obras += 1

        _op_obj, criada = _gravar_op(obra, dados)
        if criada:
            resumo.ops_criadas += 1
        else:
            resumo.ops_atualizadas += 1

        resumo.perfis += len(dados['perfis'])
        resumo.componentes += len(dados['componentes'])
        resumo.vidros += len(dados['vidros'])

    return resumo
