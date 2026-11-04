"""Leitura da planilha de Ordens de Produção gerada pelo Alumisoft (CEM Pro).

Dois formatos são suportados:
- Consolidado (01.xlsx): OP na coluna E, largura na C, altura na E
- Individual (Documents/op/*.xlsx): OP na coluna F, largura na D, altura na F

O formato é detectado automaticamente na primeira linha da planilha.
"""
from decimal import Decimal, InvalidOperation
import re
import unicodedata

import openpyxl
from django.db import transaction

from core.models import Obra, ObraOP, ObraOPComponente, ObraOPItem, ObraOPVidro

ABA_PADRAO = 'Page 1'

# Identificação da OP (ex.: J01, J02, P01, ...).
#
# HISTÓRICO: este padrão era `^([JP]\d+)(?:[_\-\s].*)?$` — aceitava só códigos
# que começam com J ou P seguido de número (J01, P03, P32_PROD). Mas o Alumisoft
# passou a gerar tipologias com outros prefixos (VF4 BD, VF6 PROD, BD P32,
# GC13, ...) e a importação lia só as 4 primeiras OPs do arquivo, silenciosamente.
# Agora aceitamos QUALQUER prefixo de letras (J, P, VF, BD, GC, ...) seguido de
# número, tolerando espaço entre o prefixo e o número ("BD P32"). O sufixo de
# revisão (_1, _REV01, _PROD) continua fora da identidade.
PADRAO_DOCUMENTO = re.compile(r'^([A-Za-z]{1,6}\s*[A-Za-z]?\d+)(?:[_\-\s].*)?$')


def documento_base(valor):
    """Extrai o documento (J01, P03) de um código possivelmente com sufixo.

    'J01_2'      -> 'J01'
    'P03_REV01'  -> 'P03'
    'J01'        -> 'J01'
    """
    texto = str(valor or '').strip()
    m = PADRAO_DOCUMENTO.match(texto)
    return m.group(1) if m else texto

# Seções (tabelas) que podem se repetir dentro da mesma OP
SECOES = ('Perfis', 'Componentes', 'Vidros')

# Rótulos que encerram um bloco de dados. Sem isto, a ÚLTIMA OP do arquivo
# (cujo limite é ws.max_row + 1) nunca encontra o fechamento e o leitor de
# perfis/componentes/vidros engole o rodapé do Alumisoft, a página seguinte e
# as tabelas das OPs seguintes — uma OP saiu com 103 perfis, 159 componentes e
# 257 vidros de contaminação.
FIM_DE_BLOCO = (
    'cems',              # 'CEM Pro - Alumisoft Sistemas' (rodapé de página)
    'av.',               # endereço da fábrica (rodapé de página)
    'caixilhoespecial',  # título da OP seguinte
)

# ---------------------------------------------------------------------------
# Detecção de formato
# ---------------------------------------------------------------------------
class Formato:
    """Armazena as posições das colunas conforme o formato detectado."""
    
    def __init__(self, col_op, col_largura, col_altura, col_data, col_loc_rotulo, col_loc_valor):
        self.col_op = col_op
        self.col_largura = col_largura
        self.col_altura = col_altura
        self.col_data = col_data
        self.col_loc_rotulo = col_loc_rotulo
        self.col_loc_valor = col_loc_valor


def detectar_formato(ws):
    """Detecta o formato do arquivo.

    Procura o codigo da OP (PADRAO_DOCUMENTO) nas primeiras 20 linhas,
    em qualquer coluna. Suporta:
      - consolidado: OP na coluna E, linha 1
      - individual: OP na coluna F, linha 1
      - individual por OP (BD P32_1): OP na coluna Q, apos 'Cod Esqd:'
    """
    # 1) Formatos conhecidos (linha 1)
    for col in range(3, 9):
        valor = _celula(ws, 1, col)
        if PADRAO_DOCUMENTO.match(valor):
            if col == 5:
                return Formato(5, 3, 5, 15, 13, 14)
            elif col == 6:
                return Formato(6, 4, 6, 16, 14, 15)

    # 2) Formato individual por OP: OP na coluna Q (17), rotulo 'Cod Esqd:' na col 3
    for linha in range(1, 21):
        if _normalizar(_celula(ws, linha, 3)) in ('cod esqd', 'cod. esqd', 'cod esq'):
            valor = _celula(ws, linha, 17)
            if PADRAO_DOCUMENTO.match(valor):
                # col_op=17, largura=16, altura=16, data=15? usar fallback
                return Formato(17, 16, 16, 9, 13, 18)

    # 3) Busca generica: qualquer celula nas primeiras 20 linhas
    for linha in range(1, 21):
        for col in range(1, ws.max_column + 1):
            valor = _celula(ws, linha, col)
            if PADRAO_DOCUMENTO.match(valor):
                # Assume layout individual por OP com OP na col encontrada
                return Formato(col, col - 1, col, col - 2, 13, 14)
    return None


# ---------------------------------------------------------------------------
# Mapa de colunas (1 = A) - Fixo para todos os formatos
# ---------------------------------------------------------------------------
COL_ROTULO = 3                 # C  rótulo do cabeçalho (formato individual por OP)
COL_VALOR = 2                  # B  valor do cabeçalho

# Posições base das tabelas (formato individual - OP na coluna F)
# No formato consolidado (OP na coluna E), todas as posições são deslocadas -1
COLS_PERFIL_BASE = {
    'codigo': 3,        # C
    'tipo': 5,          # E
    'orientacao': 7,    # G
    'corte': 9,         # I
    'tamanho': 12,      # L
    'quantidade': 14,   # N
    'peso': 15,         # O
    'observacao': 17,   # Q
}
COLS_COMPONENTE_BASE = {
    'codigo': 3,        # C
    'descricao': 6,     # F
    'quantidade': 15,   # O
    'unidade': 17,      # Q
    'observacao': 18,   # R
}
COLS_VIDRO_BASE = {
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

# ID do perfil (coluna D) -> tipo de perfil do sistema
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

# Limites dos campos de texto
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
    """Converte para Decimal tolerando separadores pt-BR."""
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
def _localizar_marcadores(ws, formato):
    """Linhas (1-based) onde começa cada OP."""
    return [
        linha
        for linha in range(1, ws.max_row + 1)
        if (PADRAO_DOCUMENTO.match(_celula(ws, linha, formato.col_op))
            and len(_celula(ws, linha, formato.col_op)) <= 20)
    ]


def _localizar_blocos(ws, linha_inicio, linha_fim):
    """Faixas das tabelas dentro de uma OP.

    O limite de cada bloco é a PRÓXIMA seção/OP, nunca o fim da planilha: sem
    isto, o último bloco da última OP corria até ws.max_row e engolia o rodapé
    do Alumisoft e as tabelas das OPs seguintes.
    """
    marcadores = []
    for linha in range(linha_inicio, linha_fim):
        marcador = _celula(ws, linha, 1) or _celula(ws, linha, COL_ROTULO)
        if marcador in SECOES:
            marcadores.append((marcador, linha))
        elif _normalizar(marcador) in FIM_DE_BLOCO:
            marcadores.append((marcador, linha))

    blocos = []
    for indice, (nome, linha_marcador) in enumerate(marcadores):
        proximo = marcadores[indice + 1][1] if indice + 1 < len(marcadores) else linha_fim
        blocos.append((nome, linha_marcador + 1, proximo))
    return blocos


def _linha_de_dados(ws, linha):
    """False para linhas de título ('Pos.'), rodapé e vazias."""
    rotulo = _celula(ws, linha, COL_ROTULO) or _celula(ws, linha, 1) or _celula(ws, linha, 2)
    if rotulo == 'Pos.':
        return False
    if _normalizar(rotulo) in FIM_DE_BLOCO:
        return False
    return True


def _ler_cabecalho(ws, linha_inicio, linha_fim, formato):
    """Extrai o cabeçalho da OP casando os rótulos da coluna A."""
    dados = {
        'documento': documento_base(_celula(ws, linha_inicio, formato.col_op)),
        'documento_completo': _celula(ws, linha_inicio, formato.col_op),
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

        # Valores podem estar em colunas diferentes conforme o formato
        if chave == 'codigo_obra':
            valor = _celula(ws, linha, formato.col_loc_valor)
        elif chave == 'cliente':
            valor = _celula(ws, linha, 13)
        elif chave == 'nome_obra':
            valor = _celula(ws, linha, 11)
        elif chave == 'codigo_esquadria':
            valor = _celula(ws, linha, formato.col_op)
        elif chave == 'descricao':
            valor = _celula(ws, linha, formato.col_op + (0 if formato.col_op == 17 else 0))
            # descricao esta na col 17 (Q) neste formato
            valor = _celula(ws, linha, 17) if formato.col_op == 17 else valor
        elif chave == 'tratamento':
            valor = _celula(ws, linha, 17) if formato.col_op == 17 else _celula(ws, linha, COL_VALOR)
        elif chave == 'quantidade':
            valor = _celula(ws, linha, 9)
        elif chave == 'vidro_descricao':
            valor = _celula(ws, linha, 13)
        else:
            valor = _celula(ws, linha, COL_VALOR)

        if chave == 'quantidade':
            dados['quantidade'] = _inteiro(valor, 1) or 1
            dados['largura'] = _inteiro(_celula(ws, linha, formato.col_largura), 0)
            dados['altura'] = _inteiro(_celula(ws, linha, formato.col_altura), 0)
        elif chave == 'vidro_descricao':
            dados['vidro_descricao'] = valor
        else:
            dados[chave] = valor

    return dados


def _mapa_colunas(ws, linha_header, mapeamento):
    """Detecta dinamicamente as colunas de uma secao pelo header.

    mapeamento: dict campo -> lista de rotulos aceitos (normalizados).
    Retorna dict campo -> numero da coluna (ou None).
    """
    resultado = {campo: None for campo in mapeamento}
    for col in range(1, ws.max_column + 1):
        texto = _normalizar(_celula(ws, linha_header, col))
        if not texto:
            continue
        for campo, rotulos in mapeamento.items():
            if texto in rotulos:
                resultado[campo] = col
    return resultado


MAPEAMENTO_PERFIL = {
    'codigo': ['codigo'],
    'tipo': ['tipo'],
    'orientacao': ['orientacao'],
    'corte': ['corte'],
    'tamanho': ['tamanho'],
    'quantidade': ['quantidade', 'qtde'],
    'peso': ['peso'],
    'observacao': ['observacao'],
}


def _ler_perfis(ws, linha_inicio, linha_fim, deslocamento=0):
    """Perfis de todos os blocos + o 'Peso Total:' impresso pelo Alumisoft."""
    perfis = []
    peso_total = None

    for nome, linha_cabecalho, fim in _localizar_blocos(ws, linha_inicio, linha_fim):
        if nome != 'Perfis':
            continue
        # Header esta na linha seguinte ao marcador 'Perfis'
        colunas = _mapa_colunas(ws, linha_cabecalho + 1, MAPEAMENTO_PERFIL)
        # Fallback para formato antigo (posicoes fixas) se header nao detectado
        if colunas['codigo'] is None:
            colunas = {k: (v + deslocamento) for k, v in COLS_PERFIL_BASE.items()}
        for linha in range(linha_cabecalho + 1, fim):
            if not _linha_de_dados(ws, linha):
                continue
            col_cod = colunas['codigo']
            codigo = _celula(ws, linha, col_cod) if col_cod else ''
            tamanho = _celula(ws, linha, colunas['tamanho']) if colunas['tamanho'] else ''
            if tamanho.lower().startswith('peso total'):
                col_peso = colunas['peso']
                peso_total = _decimal(_celula(ws, linha, col_peso), None) if col_peso else None
                continue

            quantidade = _celula(ws, linha, colunas['quantidade']) if colunas['quantidade'] else ''
            # Se nao ha tamanho nem quantidade, tenta aceitar so pelo codigo
            tem_dados = _eh_numero(tamanho) or _eh_numero(quantidade) or codigo
            if not tem_dados:
                continue
            if tamanho and not _eh_numero(tamanho):
                tamanho = ''
            if quantidade and not _eh_numero(quantidade):
                quantidade = ''

            perfis.append({
                'codigo': codigo,
                'tipo': _celula(ws, linha, colunas['tipo']) if colunas['tipo'] else '',
                'orientacao': _celula(ws, linha, colunas['orientacao']) if colunas['orientacao'] else '',
                'corte': _celula(ws, linha, colunas['corte']) if colunas['corte'] else '',
                'tamanho': _inteiro(tamanho, 0) if tamanho else 0,
                'quantidade': (_inteiro(quantidade, 1) or 1) if quantidade else 1,
                'peso': (_decimal(_celula(ws, linha, colunas['peso'])) or Decimal('0')) if colunas['peso'] else Decimal('0'),
                'observacao': _celula(ws, linha, colunas['observacao']) if colunas['observacao'] else '',
            })

    return perfis, peso_total


def _ler_componentes(ws, linha_inicio, linha_fim, deslocamento=0):
    """Componentes de todos os blocos, guardando a aplicação (Fábrica/Obra)."""
    componentes = []
    aplicacao = ''
    C = {k: v + deslocamento for k, v in COLS_COMPONENTE_BASE.items()}
    # Fallback para formato BD P32_1: codigo em col 15
    C['codigo'] = 15

    for nome, linha_cabecalho, fim in _localizar_blocos(ws, linha_inicio, linha_fim):
        if nome != 'Componentes':
            continue
        for linha in range(linha_cabecalho + 1, fim):
            if _normalizar(_celula(ws, linha, COL_ROTULO)) == 'aplicacao':
                aplicacao = _corta(_celula(ws, linha, COL_VALOR), LIMITE_APLICACAO)
                continue
            if not _linha_de_dados(ws, linha):
                continue

            codigo = _celula(ws, linha, C['codigo'])
            descricao = _celula(ws, linha, C['descricao']) if C['descricao'] else ''
            quantidade = _celula(ws, linha, C['quantidade']) if C['quantidade'] else ''
            if not (codigo or descricao):
                continue
            if 'cem pro' in codigo.lower() or codigo.lower().startswith('av.'):
                continue
            if quantidade and not _eh_numero(quantidade):
                quantidade = ''

            componentes.append({
                'codigo': codigo,
                'descricao': descricao,
                'aplicacao': aplicacao,
                'quantidade': (_inteiro(quantidade, 1) or 1) if quantidade else 1,
                'unidade': _celula(ws, linha, C['unidade']) if C['unidade'] else '',
                'observacao': _celula(ws, linha, C['observacao']) if C['observacao'] else '',
            })

    return componentes


def _ler_vidros(ws, linha_inicio, linha_fim, deslocamento=0):
    """Vidros de todos os blocos da OP."""
    vidros = []
    C = {k: v + deslocamento for k, v in COLS_VIDRO_BASE.items()}

    for nome, linha_cabecalho, fim in _localizar_blocos(ws, linha_inicio, linha_fim):
        if nome != 'Vidros':
            continue
        for linha in range(linha_cabecalho + 1, fim):
            if not _linha_de_dados(ws, linha):
                continue

            codigo = _celula(ws, linha, C['codigo'])
            descricao = _celula(ws, linha, C['descricao'])
            if not (codigo or descricao):
                continue

            vidros.append({
                'codigo': codigo,
                'descricao': descricao,
                'cor': _celula(ws, linha, C['cor']),
                'quantidade': _inteiro(_celula(ws, linha, C['quantidade']), 1) or 1,
                'largura': _inteiro(_celula(ws, linha, C['largura']), 0),
                'altura': _inteiro(_celula(ws, linha, C['altura']), 0),
                'observacao': _celula(ws, linha, C['observacao']),
            })

    return vidros


def _ler_op(ws, linha_inicio, linha_fim, formato):
    """Lê uma OP completa (cabeçalho + perfis + componentes + vidros)."""
    # No formato consolidado (OP na coluna E), as tabelas são deslocadas -1
    deslocamento = -1 if formato.col_op == 5 else 0
    cabecalho = _ler_cabecalho(ws, linha_inicio, linha_fim, formato)
    perfis, peso_total = _ler_perfis(ws, linha_inicio, linha_fim, deslocamento)
    componentes = _ler_componentes(ws, linha_inicio, linha_fim, deslocamento)
    vidros = _ler_vidros(ws, linha_inicio, linha_fim, deslocamento)

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
    """Lê o arquivo (caminho ou upload) e devolve a lista de OPs encontradas.

    Levanta ErroImportacaoOP com o motivo REAL quando nada é encontrado. Antes
    devolvia [] e a view mostrava uma mensagem genérica sobre "coluna E" — o
    operador ficava sem saber o que havia de errado no arquivo dele.
    """
    wb = openpyxl.load_workbook(origem, data_only=True)
    try:
        if ABA_PADRAO in wb.sheetnames:
            ws = wb[ABA_PADRAO]
        else:
            ws = wb.active

        if ws is None:
            raise ErroImportacaoOP('A planilha não tem nenhuma aba com dados.')

        formato = detectar_formato(ws)
        if formato is None:
            amostra = [_celula(ws, 1, c) for c in range(1, 10)]
            amostra = [v for v in amostra if v]
            raise ErroImportacaoOP(
                f'Não reconheci o formato desta planilha (aba "{ws.title}"). '
                f'O código da OP deve estar na coluna E (ex.: J01, J02, P01) ou '
                f'na coluna F, na primeira linha. '
                f'Conteúdo da primeira linha: {amostra or "vazia"}. '
                f'Confirme que é o relatório de OP gerado pelo Alumisoft.'
            )

        marcadores = _localizar_marcadores(ws, formato)
        if not marcadores:
            raise ErroImportacaoOP(
                'O formato foi reconhecido, mas nenhuma OP foi encontrada na '
                'planilha. Verifique se o relatório está completo.'
            )

        limites = marcadores + [ws.max_row + 1]
        return [
            _ler_op(ws, marcadores[i], limites[i + 1], formato)
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
    # IDENTIDADE DA OP. `codigo_documento` não pode ser só o prefixo alfanumérico
    # (ex.: "VF4"): na lista de caixilhos a MESMA esquadria aparece em várias
    # unidades com medidas diferentes (VF4 1350x550, 802x550, 1167x550...), e
    # unique_together = ['obra', 'codigo_documento'] faria todas colidirem —
    # cada importação sobrescreveria a anterior e só a última sobraria.
    #
    # Usamos o rótulo de seção da coluna E (o documento impresso: "VF4 BD",
    # "VF6_1 BD", "BD P32"), que é único por OP. Sem ele, caímos no documento
    # base para não perder a OP (melhor um nome genérico do que descartar).
    documento = _corta(cabecalho.get('documento_completo') or cabecalho['documento'], 20)

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
    """Importa todas as OPs do arquivo numa única transação."""
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
