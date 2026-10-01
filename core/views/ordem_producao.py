"""Rotina de Ordem de Produção (OP) — integração com o banco Faktory (MSSQL).

Espelha a tela "Ordens de Produção" do ERP Faktory, no padrão visual do
sistema Casanova. A grid inicia VAZIA e só carrega quando o usuário aplica
algum filtro (evita varrer ~31 mil registros sem necessidade).
"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connections
from django.shortcuts import render

from core.models import RastreioOP
from core.views.permissao import requer_rotina

ITENS_POR_PAGINA = 12

# Mapeamento dos códigos de tipo de OP do Faktory
TIPOS_OP = {
    0: 'Fabricado',
    1: 'Revenda',
    2: 'Beneficiamento',
    3: 'Industrialização',
}

# Mapeamento dos status de elaboração
STATUS_ELABORACAO = {
    0: 'Em Edição',
    1: 'Finalizada',
    2: 'Cancelada',
}

# Mapeamento dos status de atendimento
STATUS_ATENDIMENTO = {
    0: 'Aberto',
    1: 'Atendido Parcialmente',
    2: 'Totalmente Atendido',
}

# Campos de filtro considerados para decidir se a grid deve carregar
CAMPOS_FILTRO = (
    'estabelecimento', 'tipo', 'documento', 'produto', 'variante',
    'projeto', 'item_projeto', 'status', 'data_necessidade', 'q',
)

FROM_JOINS = """
    FROM dbo.ORDEMPRODUCAO OP
    LEFT JOIN dbo.ESTABELECIMENTO EST ON OP.ID_ESTABELECIMENTO = EST.ID_ESTABELECIMENTO
    LEFT JOIN dbo.DOCUMENTO DOC      ON OP.ID_DOCUMENTO = DOC.ID_DOCUMENTO
    LEFT JOIN dbo.PRODUTO PROD       ON OP.ID_PRODUTO = PROD.ID_PRODUTO
    LEFT JOIN dbo.PRODUTOVARIANTE PV ON OP.ID_PRODUTOVARIANTE = PV.ID_PRODUTOVARIANTE
    LEFT JOIN dbo.PROJETO PRJ        ON OP.ID_PROJETO = PRJ.ID_PROJETO
    LEFT JOIN dbo.PROJETOITEM PI     ON OP.ID_PROJETOITEM = PI.ID_PROJETOITEM
    LEFT JOIN dbo.PROJETOESTAGIO PE  ON OP.ID_PROJETOESTAGIO = PE.ID_PROJETOESTAGIO
"""


def _montar_filtros(request):
    """Monta a cláusula WHERE, os parâmetros e se há algum filtro aplicado."""
    where = []
    params = []

    estabelecimento = request.GET.get('estabelecimento', '').strip()
    if estabelecimento:
        where.append('EST.DS_FANTASIA LIKE %s')
        params.append(f'%{estabelecimento}%')

    tipo = request.GET.get('tipo', '').strip()
    if tipo.isdigit():
        where.append('OP.TP_ORDEMPRODUCAO = %s')
        params.append(int(tipo))

    # Documento: aceita tanto o código (ex.: "OP") quanto o número (ex.: 69272)
    documento = request.GET.get('documento', '').strip()
    if documento:
        where.append('(DOC.CD_DOCUMENTO LIKE %s OR CAST(OP.NM_DOCUMENTO AS VARCHAR) LIKE %s)')
        params.extend([f'%{documento}%', f'%{documento}%'])

    produto = request.GET.get('produto', '').strip()
    if produto:
        where.append('PROD.DS_PRODUTO LIKE %s')
        params.append(f'%{produto}%')

    variante = request.GET.get('variante', '').strip()
    if variante:
        where.append('PV.CD_PRODUTOVARIANTE LIKE %s')
        params.append(f'%{variante}%')

    projeto = request.GET.get('projeto', '').strip()
    if projeto:
        where.append(
            '(PRJ.DS_PROJETO LIKE %s OR PRJ.NM_CODIGO LIKE %s '
            'OR CAST(PRJ.NM_DOCUMENTO AS VARCHAR) LIKE %s)'
        )
        params.extend([f'%{projeto}%', f'%{projeto}%', f'%{projeto}%'])

    item_projeto = request.GET.get('item_projeto', '').strip()
    if item_projeto:
        where.append('PI.DS_PROJETOITEM LIKE %s')
        params.append(f'%{item_projeto}%')

    status = request.GET.get('status', '').strip()
    if status.isdigit():
        where.append('OP.TP_STATUSATENDIMENTO = %s')
        params.append(int(status))

    data_necessidade = request.GET.get('data_necessidade', '').strip()
    if data_necessidade:
        where.append('CAST(OP.DT_NECESSIDADE AS DATE) = %s')
        params.append(data_necessidade)

    # Busca livre (código da OP, produto, obra)
    q = request.GET.get('q', '').strip()
    if q:
        where.append(
            '(CAST(OP.ID_ORDEMPRODUCAO AS VARCHAR) LIKE %s '
            'OR PROD.DS_PRODUTO LIKE %s '
            'OR PRJ.DS_PROJETO LIKE %s)'
        )
        params.extend([f'%{q}%'] * 3)

    if request.GET.get('exibir_cancelados') != 'on':
        where.append('OP.DT_CANCELAMENTO IS NULL')

    clausula = ('WHERE ' + ' AND '.join(where)) if where else ''
    tem_filtro = any(request.GET.get(campo, '').strip() for campo in CAMPOS_FILTRO)
    return clausula, params, tem_filtro


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def lista_ordem_producao(request):
    """Lista as Ordens de Produção vindas do ERP Faktory (somente após filtrar)."""
    clausula, params, tem_filtro = _montar_filtros(request)

    ordenar = request.GET.get('ordenar', '')
    mapa_ordenacao = {
        'op_asc': 'OP.ID_ORDEMPRODUCAO ASC',
        'op_desc': 'OP.ID_ORDEMPRODUCAO DESC',
        'necessidade_asc': 'OP.DT_NECESSIDADE ASC',
        'necessidade_desc': 'OP.DT_NECESSIDADE DESC',
        'produto_asc': 'PROD.DS_PRODUTO ASC',
        'produto_desc': 'PROD.DS_PRODUTO DESC',
    }
    order_by = mapa_ordenacao.get(ordenar, 'OP.ID_ORDEMPRODUCAO DESC')

    erro_conexao = None
    ordens = []
    total = 0
    pagina = request.GET.get('page') or 1
    try:
        pagina = max(int(pagina), 1)
    except (TypeError, ValueError):
        pagina = 1
    offset = (pagina - 1) * ITENS_POR_PAGINA

    # Só consulta o ERP quando houver algum filtro aplicado
    if tem_filtro:
        sql_count = f'SELECT COUNT(*) {FROM_JOINS} {clausula}'
        sql_dados = f"""
            SELECT
                OP.ID_ORDEMPRODUCAO        AS IdOrdemProducao,
                EST.DS_FANTASIA            AS Estabelecimento,
                DOC.CD_DOCUMENTO           AS Documento,
                OP.NM_DOCUMENTO            AS NumeroDocumento,
                OP.TP_ORDEMPRODUCAO        AS Tipo,
                PROD.DS_PRODUTO            AS Produto,
                PV.CD_PRODUTOVARIANTE      AS Variante,
                OP.DT_NECESSIDADE          AS DataNecessidade,
                OP.DS_ESPECIFICACAO        AS Especificacao,
                PI.DS_PROJETOITEM          AS ItemProjeto,
                PE.DS_PROJETOESTAGIO       AS EtapaProjeto,
                OP.QT_PRODUZIR             AS QtdProduzir,
                OP.QT_PRODUZIDA            AS QtdProduzida,
                OP.TP_STATUSELABORACAO     AS StatusElaboracao,
                OP.TP_STATUSATENDIMENTO    AS StatusAtendimento,
                PRJ.NM_DOCUMENTO           AS ObraNumero,
                PRJ.NM_CODIGO              AS ObraCodigo,
                PRJ.DS_PROJETO             AS ObraDescricao,
                DOCP.CD_DOCUMENTO          AS ObraTipoDocumento
            {FROM_JOINS}
            LEFT JOIN dbo.DOCUMENTO DOCP ON PRJ.ID_DOCUMENTO = DOCP.ID_DOCUMENTO
            {clausula}
            ORDER BY {order_by}
            OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
        """
        try:
            with connections['faktory'].cursor() as cur:
                cur.execute(sql_count, params)
                total = cur.fetchone()[0] or 0

                cur.execute(sql_dados, params + [offset, ITENS_POR_PAGINA])
                colunas = [d[0] for d in cur.description]
                for linha in cur.fetchall():
                    registro = dict(zip(colunas, linha))
                    registro['TipoLabel'] = TIPOS_OP.get(registro.get('Tipo'), '—')
                    registro['StatusElaboracaoLabel'] = STATUS_ELABORACAO.get(
                        registro.get('StatusElaboracao'), '—'
                    )
                    registro['StatusAtendimentoLabel'] = STATUS_ATENDIMENTO.get(
                        registro.get('StatusAtendimento'), '—'
                    )
                    # Data de necessidade sem hora (apenas dd/mm/aaaa)
                    data_nec = registro.get('DataNecessidade')
                    registro['DataNecessidade'] = (
                        data_nec.strftime('%d/%m/%Y') if data_nec else '—'
                    )
                    # Monta o texto do Projeto/Obra (ex.: "OBR - 1334 - 25-3629-00 - KARTËDROMO")
                    partes_obra = [
                        registro.get('ObraTipoDocumento'),
                        registro.get('ObraNumero'),
                        registro.get('ObraCodigo'),
                        registro.get('ObraDescricao'),
                    ]
                    registro['ProjetoObra'] = ' - '.join(
                        str(p) for p in partes_obra if p not in (None, '')
                    ) or '—'
                    ordens.append(registro)
        except Exception as exc:  # noqa: BLE001
            erro_conexao = str(exc)
            # Mensagem amigável para o caso mais comum: backend/driver ausente
            if 'available database backend' in erro_conexao or 'mssql' in erro_conexao.lower():
                erro_conexao = (
                    'O driver de conexão com o ERP Faktory não está instalado neste '
                    'servidor. Instale os pacotes "mssql-django" e "pyodbc" e o '
                    '"ODBC Driver 18 for SQL Server". Consulte DEPLOY_FAKTORY.md.'
                )

    # Paginador "leve": já paginado no banco, mas mantém a interface do partial
    paginator = Paginator(range(total), ITENS_POR_PAGINA)
    page_obj = paginator.get_page(pagina)

    params_qs = request.GET.copy()
    params_qs.pop('page', None)
    querystring = params_qs.urlencode()

    context = {
        'page_obj': page_obj,
        'ordens': ordens,
        'querystring': querystring,
        'ordenacao_atual': ordenar,
        'erro_conexao': erro_conexao,
        'filtros': request.GET,
        'tipos_op': TIPOS_OP,
        'status_atendimento': STATUS_ATENDIMENTO,
        'tem_filtro': tem_filtro,
    }
    return render(request, 'core/industria/lista_op.html', context)


def _buscar_op_por_id(op_id):
    """Busca os dados de uma OP específica no Faktory (para o código de barras)."""
    sql = f"""
        SELECT TOP 1
            OP.ID_ORDEMPRODUCAO        AS IdOrdemProducao,
            EST.DS_FANTASIA            AS Estabelecimento,
            DOC.CD_DOCUMENTO           AS Documento,
            OP.NM_DOCUMENTO            AS NumeroDocumento,
            OP.TP_ORDEMPRODUCAO        AS Tipo,
            PROD.DS_PRODUTO            AS Produto,
            PV.CD_PRODUTOVARIANTE      AS Variante,
            OP.DT_NECESSIDADE          AS DataNecessidade,
            PI.DS_PROJETOITEM          AS ItemProjeto,
            PE.DS_PROJETOESTAGIO       AS EtapaProjeto,
            OP.QT_PRODUZIR             AS QtdProduzir,
            OP.QT_PRODUZIDA            AS QtdProduzida,
            OP.TP_STATUSELABORACAO     AS StatusElaboracao,
            OP.TP_STATUSATENDIMENTO    AS StatusAtendimento,
            PRJ.NM_DOCUMENTO           AS ObraNumero,
            PRJ.NM_CODIGO              AS ObraCodigo,
            PRJ.DS_PROJETO             AS ObraDescricao,
            DOCP.CD_DOCUMENTO          AS ObraTipoDocumento
        {FROM_JOINS}
        LEFT JOIN dbo.DOCUMENTO DOCP ON PRJ.ID_DOCUMENTO = DOCP.ID_DOCUMENTO
        WHERE OP.ID_ORDEMPRODUCAO = %s
    """
    with connections['faktory'].cursor() as cur:
        cur.execute(sql, [op_id])
        colunas = [d[0] for d in cur.description]
        linha = cur.fetchone()
        if not linha:
            return None
        registro = dict(zip(colunas, linha))
        registro['TipoLabel'] = TIPOS_OP.get(registro.get('Tipo'), '—')
        registro['StatusElaboracaoLabel'] = STATUS_ELABORACAO.get(
            registro.get('StatusElaboracao'), '—'
        )
        registro['StatusAtendimentoLabel'] = STATUS_ATENDIMENTO.get(
            registro.get('StatusAtendimento'), '—'
        )
        data_nec = registro.get('DataNecessidade')
        registro['DataNecessidade'] = (
            data_nec.strftime('%d/%m/%Y') if data_nec else '—'
        )
        partes_obra = [
            registro.get('ObraTipoDocumento'),
            registro.get('ObraNumero'),
            registro.get('ObraCodigo'),
            registro.get('ObraDescricao'),
        ]
        registro['ProjetoObra'] = ' - '.join(
            str(p) for p in partes_obra if p not in (None, '')
        ) or '—'
        return registro


def _conteudo_barcode(op_id):
    """Conteúdo do código de barras: o ID da OP (curto e legível pelo leitor).

    O leitor de código de barras funciona como teclado: digita o valor e
    pressiona Enter. Por isso usamos apenas o ID numérico da OP.
    """
    return str(op_id)


# Tabela de padrões Code128 (larguras barra/espaço em módulos).
# Índices 0-102 = dados, 103 = Start A, 104 = Start B, 105 = Start C, 106 = Stop.
_CODE128_PATTERNS = [
    '212222', '222122', '222221', '121223', '121322', '131222', '122213',
    '122312', '132212', '221213', '221312', '231212', '112232', '122132',
    '122231', '113222', '123122', '123221', '223211', '221132', '221231',
    '213212', '223112', '312131', '311222', '321122', '321221', '312212',
    '322112', '322211', '212123', '212321', '232121', '111323', '131123',
    '131321', '112313', '132113', '132311', '211313', '231113', '231311',
    '112133', '112331', '132131', '113123', '113321', '133121', '313121',
    '211331', '231131', '213113', '213311', '213131', '311123', '311321',
    '331121', '312113', '312311', '332111', '314111', '221411', '431111',
    '111224', '111422', '121124', '121421', '141122', '141221', '112214',
    '112412', '122114', '122411', '142112', '142211', '241211', '221114',
    '413111', '241112', '134111', '111242', '121142', '121241', '114212',
    '124112', '124211', '411212', '421112', '421211', '212141', '214121',
    '412121', '111143', '111341', '131141', '114113', '114311', '411113',
    '411311', '113141', '114131', '311141', '411131', '211412', '211214',
    '211232', '2331112',
]


def _gerar_barcode_svg(conteudo):
    """Gera o código de barras Code128 como SVG — SEM dependências externas.

    Implementação em Python puro (não precisa de python-barcode/Pillow),
    garantindo que funcione em qualquer servidor.
    """
    data = str(conteudo)

    # Conjunto C (pares de dígitos) é mais compacto; senão usa o conjunto B
    if data.isdigit() and len(data) >= 2 and len(data) % 2 == 0:
        codes = [105]  # Start C
        for i in range(0, len(data), 2):
            codes.append(int(data[i:i + 2]))
    else:
        codes = [104]  # Start B
        for ch in data:
            codes.append(ord(ch) - 32)

    # Dígito verificador (checksum)
    checksum = codes[0]
    for pos, code in enumerate(codes[1:], start=1):
        checksum += pos * code
    codes.append(checksum % 103)
    codes.append(106)  # Stop

    # Dimensões em milímetros
    modulo = 0.5
    altura = 15.0
    quiet = 2.5
    altura_texto = 5.0

    x = quiet
    barras = []
    for code in codes:
        padrao = _CODE128_PATTERNS[code]
        barra = True
        for largura in padrao:
            w = int(largura) * modulo
            if barra:
                barras.append(
                    f'<rect x="{x:.3f}" y="0" width="{w:.3f}" height="{altura}"/>'
                )
            x += w
            barra = not barra

    largura_total = x + quiet
    altura_total = altura + altura_texto

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{largura_total:.2f}mm" height="{altura_total:.2f}mm" '
        f'viewBox="0 0 {largura_total:.2f} {altura_total:.2f}">'
        f'<rect width="100%" height="100%" fill="#ffffff"/>'
        f'<g fill="#000000">{"".join(barras)}</g>'
        f'<text x="{largura_total / 2:.2f}" y="{altura_total - 1:.2f}" '
        f'text-anchor="middle" font-family="monospace" font-size="4">{data}</text>'
        f'</svg>'
    )


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def barcode_ordem_producao(request, op_id):
    """Gera o código de barras de uma OP em SVG.

    NÃO depende do ERP Faktory: o código contém apenas o ID da OP, então
    funciona mesmo se o ERP estiver indisponível.
    """
    from django.http import HttpResponse

    svg = _gerar_barcode_svg(_conteudo_barcode(op_id))
    return HttpResponse(svg, content_type='image/svg+xml')


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def imprimir_barcode_ordem_producao(request, op_id):
    """Página de impressão do código de barras em folha A4.

    Os dados da OP vêm do ERP quando disponível; caso contrário, usa o
    rastreio local ou apenas o ID (o código de barras sempre é gerado).
    """
    dados = None
    try:
        dados = _buscar_op_por_id(op_id)
    except Exception:  # noqa: BLE001
        dados = None

    # Fallback: dados do rastreio local (se a OP já foi escaneada)
    if not dados:
        rastreio = RastreioOP.objects.filter(op_id=op_id).first()
        if rastreio:
            dados = {
                'NumeroDocumento': rastreio.op_numero or str(op_id),
                'ProjetoObra': rastreio.obra or '—',
                'Produto': rastreio.produto or '—',
                'Variante': rastreio.variante or '—',
                'DataNecessidade': '—',
                'QtdProduzir': '—',
            }

    # Último recurso: apenas o ID (o código de barras continua válido)
    if not dados:
        dados = {
            'NumeroDocumento': str(op_id),
            'ProjetoObra': '—',
            'Produto': '—',
            'Variante': '—',
            'DataNecessidade': '—',
            'QtdProduzir': '—',
        }

    barcode_svg = _gerar_barcode_svg(_conteudo_barcode(op_id))
    erro_barcode = None

    context = {
        'dados': dados,
        'barcode_svg': barcode_svg,
        'erro_barcode': erro_barcode,
        'codigo': _conteudo_barcode(op_id),
    }
    return render(request, 'core/industria/imprimir_barcode_op.html', context)