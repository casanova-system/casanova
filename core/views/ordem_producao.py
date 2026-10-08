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
        'Documento': obra_op.codigo_formatado,
        'CodigoFormatado': obra_op.codigo_formatado,
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


def _conteudo_barcode(obra_op_id):
    """Conteúdo do QR Code: JSON com as informações completa da OP.

    O QR Code contém todos os dados da OP (ObraOP) para rastreio e identificação.
    O leitor escaneia e o sistema extrai o ID da OP do JSON.
    """
    import json

    from core.models import ObraOP

    # Busca dados da OP na rotina de ordem de produção
    obra_op = ObraOP.objects.filter(pk=obra_op_id).first()
    if obra_op:
        dados = {
            'id': obra_op.pk,
            'op': obra_op.codigo_formatado,
            'esquadria': obra_op.codigo_esquadria,
            'obra': obra_op.obra.codigo if obra_op.obra else '',
            'descricao': obra_op.descricao or '',
            'quantidade': obra_op.quantidade,
            'largura': obra_op.largura,
            'altura': obra_op.altura,
        }
        return json.dumps(dados, ensure_ascii=False)

    # Fallback: apenas o ID
    return json.dumps({'id': obra_op_id, 'op': str(obra_op_id)}, ensure_ascii=False)


def _gerar_barcode_svg(conteudo):
    """Gera um QR Code como SVG usando a biblioteca qrcode.

    O QR Code contém o ID da OP (ex: "65427"). O leitor de QR code escaneia
    e retorna o ID, que é usado no rastreio da produção.
    """
    import qrcode
    import qrcode.image.svg

    data = str(conteudo)

    # Gera o QR Code como SVG (vetorial, sem dependências externas)
    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.QRCode(
        version=None,  # Auto-dimensionar
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(image_factory=factory)
    svg_string = img.to_string().decode('utf-8')

    # Remove os atributos width/height originais e define o tamanho para impressão
    import re
    svg_string = re.sub(r'width="[^"]*"\s*', '', svg_string, count=1)
    svg_string = re.sub(r'height="[^"]*"\s*', '', svg_string, count=1)
    svg_string = svg_string.replace(
        '<svg ',
        '<svg width="150mm" height="150mm" ',
        1
    )

    return svg_string


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def barcode_ordem_producao(request, op_id):
    """Gera o QR Code de uma OP em SVG com todas as informações."""
    svg = _gerar_barcode_svg(_conteudo_barcode(op_id))
    return HttpResponse(svg, content_type='image/svg+xml')


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def imprimir_barcode_ordem_producao(request, op_id):
    """Página de impressão do QR Code em folha A4.

    Os dados vêm da OP (ObraOP) da rotina de ordem de produção.
    """
    from core.models import ObraOP

    obra_op = ObraOP.objects.filter(pk=op_id).first()
    if obra_op:
        dados = {
            'NumeroDocumento': obra_op.codigo_formatado,
            'ProjetoObra': obra_op.obra.codigo if obra_op.obra else '—',
            'Produto': obra_op.descricao or '—',
            'Variante': obra_op.codigo_esquadria or '—',
            'DataNecessidade': '—',
            'QtdProduzir': str(obra_op.quantidade),
        }
    else:
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
