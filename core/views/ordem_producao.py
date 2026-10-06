"""Rotina de Ordem de Produção (OP).

A grid lista as OPs/Tipologias **importadas** do Excel do Alumisoft e,
quando há filtro e o ERP Faktory está configurado, também as OPs vindas do
ERP. Clicar duas vezes em uma OP abre o detalhe com perfis, componentes e
vidros.

Regras de paginação
-------------------
As duas origens (ERP e local) são combinadas em memória antes de paginar,
porque o ERP responde em SQL Server e o local em Django — paginar cada uma
isoladamente produziria páginas com quantidade errada de itens.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connections, models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.importacao_op import ErroImportacaoOP, importar_ops
from core.models import ObraOP, RastreioOP
from core.views.permissao import requer_rotina

ITENS_POR_PAGINA = 12

# Teto de linhas trazidas do ERP numa consulta. Uma busca livre (ex.: "RAFAEL")
# casa com centenas de OPs no Faktory; sem teto, tudo iria para a memória.
LIMITE_ERP = 200

# ---------------------------------------------------------------------------
# Mapeamentos do ERP Faktory
# ---------------------------------------------------------------------------
TIPOS_OP = {
    0: 'Fabricado',
    1: 'Revenda',
    2: 'Beneficiamento',
    3: 'Industrialização',
}

STATUS_ELABORACAO = {
    0: 'Em Edição',
    1: 'Finalizada',
    2: 'Cancelada',
}

STATUS_ATENDIMENTO = {
    0: 'Aberto',
    1: 'Atendido Parcialmente',
    2: 'Totalmente Atendido',
}

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

COLUNAS_ERP = """
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
"""

# Critério de ordenação -> ORDER BY aceito pelo SQL Server
ORDENACAO_ERP = {
    'op_asc': 'OP.ID_ORDEMPRODUCAO ASC',
    'op_desc': 'OP.ID_ORDEMPRODUCAO DESC',
    'necessidade_asc': 'OP.DT_NECESSIDADE ASC',
    'necessidade_desc': 'OP.DT_NECESSIDADE DESC',
    'produto_asc': 'PROD.DS_PRODUTO ASC',
    'produto_desc': 'PROD.DS_PRODUTO DESC',
}

MSG_DRIVER_FAKTORY = (
    'O driver de conexão com o ERP Faktory não está instalado neste servidor. '
    'Instale os pacotes "mssql-django" e "pyodbc" e o "ODBC Driver 18 for '
    'SQL Server". Consulte DEPLOY_FAKTORY.md.'
)


# ---------------------------------------------------------------------------
# Filtros do ERP
# ---------------------------------------------------------------------------
def _montar_filtros(request):
    """Monta a cláusula WHERE e os parâmetros do ERP a partir da querystring."""
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
        params.extend([f'%{projeto}%'] * 3)

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
    return clausula, params


def _tem_filtro(request):
    """O ERP só é consultado quando há filtro (evita varrer 33k OPs)."""
    campos = (
        'estabelecimento', 'tipo', 'documento', 'produto', 'variante',
        'projeto', 'item_projeto', 'status', 'data_necessidade', 'q',
    )
    return any(request.GET.get(campo, '').strip() for campo in campos)


def _normalizar_registro_erp(registro):
    """Completa o registro do ERP com rótulos e campos já formatados."""
    registro['TipoLabel'] = TIPOS_OP.get(registro.get('Tipo'), '—')
    registro['StatusElaboracaoLabel'] = STATUS_ELABORACAO.get(
        registro.get('StatusElaboracao'), '—'
    )
    registro['StatusAtendimentoLabel'] = STATUS_ATENDIMENTO.get(
        registro.get('StatusAtendimento'), '—'
    )

    data_nec = registro.get('DataNecessidade')
    registro['DataNecessidade'] = data_nec.strftime('%d/%m/%Y') if data_nec else '—'

    partes = [
        registro.get('ObraTipoDocumento'),
        registro.get('ObraNumero'),
        registro.get('ObraCodigo'),
        registro.get('ObraDescricao'),
    ]
    registro['ProjetoObra'] = ' - '.join(
        str(parte) for parte in partes if parte not in (None, '')
    ) or '—'

    registro['fonte'] = 'faktory'
    registro['obra_op_id'] = None
    return registro


def _consultar_erp(clausula, params, order_by):
    """Consulta o ERP Faktory. Devolve ``(registros, erro)``.

    A consulta é limitada a ``LIMITE_ERP`` linhas: uma busca livre pode casar
    com centenas de OPs e trazer tudo para a memória derrubaria a página.
    """
    sql_dados = f"""
        SELECT TOP {LIMITE_ERP} {COLUNAS_ERP}
        {FROM_JOINS}
        LEFT JOIN dbo.DOCUMENTO DOCP ON PRJ.ID_DOCUMENTO = DOCP.ID_DOCUMENTO
        {clausula}
        ORDER BY {order_by}
    """
    try:
        with connections['faktory'].cursor() as cur:
            cur.execute(sql_dados, params)
            colunas = [descricao[0] for descricao in cur.description]
            return [
                _normalizar_registro_erp(dict(zip(colunas, linha)))
                for linha in cur.fetchall()
            ], None
    except Exception as exc:  # noqa: BLE001 — o ERP é opcional
        erro = str(exc)
        if 'available database backend' in erro or 'mssql' in erro.lower():
            erro = MSG_DRIVER_FAKTORY
        return [], erro


# ---------------------------------------------------------------------------
# Filtros das OPs locais (importadas do Excel)
# ---------------------------------------------------------------------------
def _filtrar_ops_locais(request):
    """Queryset das OPs importadas, com busca e ordenação já aplicadas."""
    consulta = ObraOP.objects.select_related('obra')

    q = request.GET.get('q', '').strip()
    if q:
        consulta = consulta.filter(
            models.Q(codigo_documento__icontains=q)
            | models.Q(codigo_esquadria__icontains=q)
            | models.Q(descricao__icontains=q)
            | models.Q(obra__codigo__icontains=q)
            | models.Q(obra__nome__icontains=q)
            | models.Q(obra__cliente__icontains=q)
        )

    projeto = request.GET.get('projeto', '').strip()
    if projeto:
        consulta = consulta.filter(
            models.Q(obra__codigo__icontains=projeto)
            | models.Q(obra__nome__icontains=projeto)
        )

    produto = request.GET.get('produto', '').strip()
    if produto:
        consulta = consulta.filter(
            models.Q(descricao__icontains=produto)
            | models.Q(codigo_esquadria__icontains=produto)
        )

    documento = request.GET.get('documento', '').strip()
    if documento:
        consulta = consulta.filter(codigo_documento__icontains=documento)

    ordenar = request.GET.get('ordenar', '')
    ordenacoes = {
        'op_asc': ('codigo_documento', 'codigo_esquadria'),
        'op_desc': ('-codigo_documento', '-codigo_esquadria'),
        'produto_asc': ('descricao',),
        'produto_desc': ('-descricao',),
        'obra_asc': ('obra__codigo', 'codigo_documento'),
        'obra_desc': ('-obra__codigo', '-codigo_documento'),
    }
    return consulta.order_by(*ordenacoes.get(ordenar, ('-data_importacao', '-id')))


def _converter_op_local(obra_op):
    """Converte uma ObraOP no mesmo dicionário usado pela grid do ERP."""
    return {
        'IdOrdemProducao': obra_op.pk,
        'obra_op_id': obra_op.pk,
        'Documento': obra_op.codigo_documento or obra_op.codigo_esquadria,
        'CodEsquadria': obra_op.codigo_esquadria,
        'Descricao': obra_op.descricao or obra_op.codigo_esquadria,
        'ObraCodigo': obra_op.obra.codigo,
        'ObraNome': obra_op.obra.nome,
        'Cliente': obra_op.obra.cliente or '—',
        'Quantidade': obra_op.quantidade,
        'Largura': obra_op.largura,
        'Altura': obra_op.altura,
        'Tratamento': obra_op.tratamento or '—',
        'DataImportacao': (
            obra_op.data_importacao.strftime('%d/%m/%Y')
            if obra_op.data_importacao else '—'
        ),
        'fonte': 'importado',
    }


def _ordenar_combinado(registros, ordenar):
    """Reordena a lista combinada (ERP + local) conforme o critério escolhido."""
    if ordenar in ('produto_asc', 'produto_desc'):
        return sorted(
            registros,
            key=lambda r: (r.get('Descricao') or '').lower(),
            reverse=ordenar.endswith('desc'),
        )

    if ordenar == 'op_asc':
        return sorted(registros, key=lambda r: (r.get('Documento') or ''))
    if ordenar == 'op_desc':
        return sorted(
            registros, key=lambda r: (r.get('Documento') or ''), reverse=True
        )

    # Padrão: importadas primeiro (o queryset local já vem mais recente primeiro)
    return sorted(
        registros, key=lambda r: 0 if r.get('fonte') == 'importado' else 1
    )


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def lista_ordem_producao(request):
    """Lista as Ordens de Produção importadas (e as do ERP quando há filtro)."""
    ordenar = request.GET.get('ordenar', '')
    erro_conexao = None

    # 1. OPs importadas do Excel (fonte principal)
    ordens = [_converter_op_local(op) for op in _filtrar_ops_locais(request)]

    # 2. OPs do ERP Faktory — somente quando há filtro
    erp_truncado = False
    if _tem_filtro(request):
        clausula, params = _montar_filtros(request)
        order_by = ORDENACAO_ERP.get(ordenar, 'OP.ID_ORDEMPRODUCAO DESC')
        registros_erp, erro_conexao = _consultar_erp(clausula, params, order_by)
        erp_truncado = len(registros_erp) >= LIMITE_ERP
        ordens.extend(registros_erp)

    ordens = _ordenar_combinado(ordens, ordenar)

    paginator = Paginator(ordens, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    params_qs = request.GET.copy()
    params_qs.pop('page', None)

    context = {
        'ordens': page_obj.object_list,
        'page_obj': page_obj,
        'querystring': params_qs.urlencode(),
        'ordenacao_atual': ordenar,
        'erro_conexao': erro_conexao,
        'erp_truncado': erp_truncado,
        'limite_erp': LIMITE_ERP,
        'filtros': request.GET,
        'total': paginator.count,
        'query': request.GET.get('q', '').strip(),
        'tipos_op': TIPOS_OP,
        'status_atendimento': STATUS_ATENDIMENTO,
    }
    return render(request, 'core/industria/lista_op.html', context)


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def importar_op_excel(request):
    """Importa Ordens de Produção a partir do Excel gerado pelo Alumisoft."""
    if request.method == 'POST':
        arquivo = request.FILES.get('excel_file')
        if not arquivo:
            messages.error(request, 'Selecione um arquivo .xlsx ou .xls para importar.')
            return redirect('importar_op_excel')

        if not arquivo.name.lower().endswith(('.xlsx', '.xls')):
            messages.error(request, 'O arquivo deve ter a extensão .xlsx ou .xls.')
            return redirect('importar_op_excel')

        try:
            resumo = importar_ops(arquivo)
        except ErroImportacaoOP as exc:
            messages.error(request, str(exc))
            return redirect('importar_op_excel')
        except Exception as exc:  # noqa: BLE001 — arquivo corrompido/formato inesperado
            messages.error(request, f'Não foi possível processar o arquivo: {exc}')
            return redirect('importar_op_excel')

        messages.success(request, resumo.mensagem())
        return redirect('lista_ordem_producao')

    return render(request, 'core/industria/importar_op_excel.html')


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def detalhe_obra_op(request, obra_op_id):
    """Detalhe de uma OP/Tipologia: perfis, componentes, vidros e resumo."""
    obra_op = get_object_or_404(
        ObraOP.objects.select_related('obra'),
        pk=obra_op_id,
    )

    itens = list(obra_op.itens.all())
    componentes = list(obra_op.componentes.all())
    vidros = list(obra_op.vidros.all())

    # Agrupa os perfis por tipo, preservando a ordem de posição
    itens_por_tipo = {}
    for item in itens:
        itens_por_tipo.setdefault(item.get_tipo_perfil_display(), []).append(item)

    context = {
        'obra_op': obra_op,
        'itens': itens,
        'itens_por_tipo': itens_por_tipo,
        'componentes': componentes,
        'vidros': vidros,
        'total_perfis': len(itens),
        'total_pecas': sum(item.quantidade or 0 for item in itens),
        'total_peso': sum((item.peso or 0) for item in itens),
        'total_componentes': len(componentes),
        'total_vidros': len(vidros),
        'qtd_vidros': sum((vidro.quantidade or 0) for vidro in vidros),
    }
    return render(request, 'core/industria/detalhe_obra_op.html', context)


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
@require_POST
def excluir_op(request, obra_op_id):
    """Exclui uma OP/Tipologia importada (exclusão sempre via POST)."""
    obra_op = get_object_or_404(ObraOP, pk=obra_op_id)
    identificacao = obra_op.identificacao
    obra_op.delete()
    messages.success(request, f'OP {identificacao} excluída com sucesso.')
    return redirect('lista_ordem_producao')


# ---------------------------------------------------------------------------
# Código de barras
# ---------------------------------------------------------------------------
def _buscar_op_por_id(op_id):
    """Busca os dados de uma OP no Faktory (usado pelo rastreio/código de barras)."""
    sql = f"""
        SELECT TOP 1 {COLUNAS_ERP}
        {FROM_JOINS}
        LEFT JOIN dbo.DOCUMENTO DOCP ON PRJ.ID_DOCUMENTO = DOCP.ID_DOCUMENTO
        WHERE OP.ID_ORDEMPRODUCAO = %s
    """
    with connections['faktory'].cursor() as cur:
        cur.execute(sql, [op_id])
        colunas = [descricao[0] for descricao in cur.description]
        linha = cur.fetchone()
        if not linha:
            return None
        return _normalizar_registro_erp(dict(zip(colunas, linha)))


def _conteudo_barcode(op_id):
    """Conteúdo do código de barras: apenas o ID da OP.

    O leitor funciona como teclado (digita o valor e pressiona Enter), então o
    código precisa ser curto e numérico.
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
    """Gera o código de barras Code128 como SVG — sem dependências externas."""
    data = str(conteudo)

    if data.isdigit() and len(data) >= 2 and len(data) % 2 == 0:
        codes = [105]  # Start C (pares de dígitos)
        for i in range(0, len(data), 2):
            codes.append(int(data[i:i + 2]))
    else:
        codes = [104]  # Start B
        for caractere in data:
            codes.append(ord(caractere) - 32)

    checksum = codes[0]
    for posicao, code in enumerate(codes[1:], start=1):
        checksum += posicao * code
    codes.append(checksum % 103)
    codes.append(106)  # Stop

    modulo = 0.5
    altura = 15.0
    quiet = 2.5
    altura_texto = 5.0

    x = quiet
    barras = []
    for code in codes:
        barra = True
        for largura in _CODE128_PATTERNS[code]:
            largura_modulo = int(largura) * modulo
            if barra:
                barras.append(
                    f'<rect x="{x:.3f}" y="0" width="{largura_modulo:.3f}" '
                    f'height="{altura}"/>'
                )
            x += largura_modulo
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
    """Gera o código de barras de uma OP em SVG (não depende do ERP)."""
    svg = _gerar_barcode_svg(_conteudo_barcode(op_id))
    return HttpResponse(svg, content_type='image/svg+xml')


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def imprimir_barcode_ordem_producao(request, op_id):
    """Página de impressão do código de barras em folha A4.

    Os dados vêm do ERP quando disponível; senão do rastreio local; e, em
    último caso, apenas o ID (o código de barras continua válido).
    """
    dados = None
    try:
        dados = _buscar_op_por_id(op_id)
    except Exception:  # noqa: BLE001 — a impressão não pode depender do ERP
        dados = None

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

    if not dados:
        dados = {
            'NumeroDocumento': str(op_id),
            'ProjetoObra': '—',
            'Produto': '—',
            'Variante': '—',
            'DataNecessidade': '—',
            'QtdProduzir': '—',
        }

    context = {
        'dados': dados,
        'barcode_svg': _gerar_barcode_svg(_conteudo_barcode(op_id)),
        'codigo': _conteudo_barcode(op_id),
    }
    return render(request, 'core/industria/imprimir_barcode_op.html', context)
