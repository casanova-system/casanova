"""Rotina de Ordem de Produção (OP) — integração com o banco Faktory (MSSQL).

Espelha a tela "Ordens de Produção" do ERP Faktory, no padrão visual do
sistema Casanova. A grid inicia VAZIA e só carrega quando o usuário aplica
algum filtro (evita varrer ~31 mil registros sem necessidade).
"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connections
from django.shortcuts import render

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
    'estabelecimento', 'tipo', 'documento', 'numero', 'produto', 'variante',
    'projeto', 'item_projeto', 'etapa_projeto', 'status', 'data_necessidade',
    'localizacao', 'q',
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

    numero = request.GET.get('numero', '').strip()
    if numero:
        # Busca tanto pelo número do documento quanto pelo número da OP
        where.append(
            '(CAST(OP.NM_DOCUMENTO AS VARCHAR) LIKE %s '
            'OR CAST(OP.ID_ORDEMPRODUCAO AS VARCHAR) LIKE %s)'
        )
        params.extend([f'%{numero}%', f'%{numero}%'])

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

    etapa_projeto = request.GET.get('etapa_projeto', '').strip()
    if etapa_projeto:
        where.append('PE.DS_PROJETOESTAGIO LIKE %s')
        params.append(f'%{etapa_projeto}%')

    status = request.GET.get('status', '').strip()
    if status.isdigit():
        where.append('OP.TP_STATUSATENDIMENTO = %s')
        params.append(int(status))

    data_necessidade = request.GET.get('data_necessidade', '').strip()
    if data_necessidade:
        where.append('CAST(OP.DT_NECESSIDADE AS DATE) = %s')
        params.append(data_necessidade)

    localizacao = request.GET.get('localizacao', '').strip()
    if localizacao:
        where.append('OP.DS_LOCALIZACAOOBRA LIKE %s')
        params.append(f'%{localizacao}%')

    # Busca livre (código da OP, produto, projeto, localização)
    q = request.GET.get('q', '').strip()
    if q:
        where.append(
            '(CAST(OP.ID_ORDEMPRODUCAO AS VARCHAR) LIKE %s '
            'OR PROD.DS_PRODUTO LIKE %s '
            'OR PRJ.DS_PROJETO LIKE %s '
            'OR OP.DS_LOCALIZACAOOBRA LIKE %s)'
        )
        params.extend([f'%{q}%'] * 4)

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
    """Busca os dados de uma OP específica no Faktory (para o QR Code)."""
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


def _conteudo_qrcode(dados):
    """Monta o texto que vai dentro do QR Code (a OP é o número do documento)."""
    linhas = [
        f"OP: {dados.get('NumeroDocumento') or '—'}",
        f"Obra: {dados.get('ProjetoObra')}",
        f"Produto: {dados.get('Produto') or '—'}",
        f"Variante: {dados.get('Variante') or '—'}",
        f"Necessidade: {dados.get('DataNecessidade')}",
        f"Qtd: {dados.get('QtdProduzir')}",
    ]
    return '\n'.join(linhas)


def _gerar_qrcode_svg(conteudo):
    """Gera o QR Code como SVG (string). Não depende do Pillow."""
    import qrcode
    import qrcode.image.svg

    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(conteudo, image_factory=factory)
    import io

    buffer = io.BytesIO()
    img.save(buffer)
    return buffer.getvalue().decode('utf-8')


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def qrcode_ordem_producao(request, op_id):
    """Gera o QR Code de uma OP em SVG."""
    from django.http import HttpResponse

    try:
        dados = _buscar_op_por_id(op_id)
    except Exception:  # noqa: BLE001
        dados = None

    if not dados:
        return HttpResponse('OP não encontrada.', status=404)

    try:
        svg = _gerar_qrcode_svg(_conteudo_qrcode(dados))
    except ImportError:
        return HttpResponse(
            'A biblioteca "qrcode" não está instalada neste servidor. '
            'Execute: pip install qrcode',
            status=500,
            content_type='text/plain; charset=utf-8',
        )

    return HttpResponse(svg, content_type='image/svg+xml')


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def imprimir_qrcode_ordem_producao(request, op_id):
    """Página de impressão do QR Code em folha A4 (QR pequeno e centralizado)."""
    try:
        dados = _buscar_op_por_id(op_id)
    except Exception:  # noqa: BLE001
        dados = None

    if not dados:
        return render(request, 'core/industria/imprimir_qrcode_op.html', {
            'erro': 'OP não encontrada.',
        })

    conteudo = _conteudo_qrcode(dados)

    try:
        qr_svg = _gerar_qrcode_svg(conteudo)
        erro_qr = None
    except ImportError:
        qr_svg = None
        erro_qr = (
            'A biblioteca "qrcode" não está instalada neste servidor. '
            'Execute: pip install qrcode'
        )

    context = {
        'dados': dados,
        'qr_svg': qr_svg,
        'erro_qr': erro_qr,
        'conteudo_qr': conteudo,
    }
    return render(request, 'core/industria/imprimir_qrcode_op.html', context)
