"""Estoque — saldo, movimentacao e consumo em produção.

O ponto que liga o estoque a producao: quando a OP consome perfil, vidro ou
componente, o movimento e registrado com origem PRODUCAO e ligado a OP. Assim
o custo do material entra na OP e o saldo baixa sozinho.
"""
import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render

from core.models import (GrupoEstoque, LocalEstoque, MovimentoEstoque,
                         ObraOP, ProdutoEstoque, SaldoEstoque)
from core.views.permissao import requer_rotina

logger = logging.getLogger(__name__)

ITENS_POR_PAGINA = 15


def _decimal(valor, padrao=Decimal('0')):
    """Converte texto em Decimal, aceitando vírgula."""
    if valor in (None, ''):
        return padrao
    try:
        return Decimal(str(valor).replace('.', '').replace(',', '.')
                       if ',' in str(valor) else str(valor))
    except (InvalidOperation, ValueError):
        return padrao


@login_required(login_url='login')
@requer_rotina('lista_estoque')
def lista_estoque(request):
    """Saldo do estoque com filtros e alerta de mínimo."""
    query = request.GET.get('q', '').strip()
    grupo_id = request.GET.get('grupo', '').strip()
    local_id = request.GET.get('local', '').strip()
    filtro = request.GET.get('filtro', '').strip()

    saldos = SaldoEstoque.objects.select_related('produto', 'produto__grupo', 'local')

    if query:
        saldos = saldos.filter(
            Q(produto__codigo__icontains=query)
            | Q(produto__descricao__icontains=query)
            | Q(produto__cor__icontains=query)
        )
    if grupo_id:
        saldos = saldos.filter(produto__grupo_id=grupo_id)
    if local_id:
        saldos = saldos.filter(local_id=local_id)
    if filtro == 'abaixo':
        # saldo abaixo do minimo
        ids = [p.pk for p in ProdutoEstoque.objects.filter(ativo=True)
               if p.abaixo_minimo]
        saldos = saldos.filter(produto_id__in=ids)
    elif filtro == 'positivo':
        saldos = saldos.filter(quantidade__gt=0)

    saldos = saldos.order_by('produto__codigo', 'local__nome')

    paginator = Paginator(saldos, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)

    # KPIs
    produtos = ProdutoEstoque.objects.filter(ativo=True)
    total_itens = produtos.count()
    abaixo = sum(1 for p in produtos if p.abaixo_minimo)
    # o valor vem do proprio saldo (guardado na importacao), nao de
    # quantidade x custo unitario: derivar acumula erro de arredondamento e o
    # total deixa de fechar com o ERP
    valor_total = sum(float(s.valor or 0) for s in SaldoEstoque.objects.all())

    context = {
        'saldos': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'grupo_id': grupo_id,
        'local_id': local_id,
        'filtro': filtro,
        'grupos': GrupoEstoque.objects.filter(ativo=True),
        'locais': LocalEstoque.objects.filter(ativo=True),
        'kpi': {
            'itens': total_itens,
            'abaixo': abaixo,
            'valor': round(valor_total, 2),
        },
    }
    return render(request, 'core/estoque/lista_estoque.html', context)


@login_required(login_url='login')
@requer_rotina('lista_estoque')
def movimentar(request):
    """Entrada ou saída de material (nota fiscal, consumo, ajuste)."""
    if request.method == 'POST':
        produto_id = request.POST.get('produto', '').strip()
        local_id = request.POST.get('local', '').strip()
        tipo = request.POST.get('tipo', 'ENTRADA').strip()
        origem = request.POST.get('origem', 'MANUAL').strip()
        quantidade = _decimal(request.POST.get('quantidade'))
        valor_unit = _decimal(request.POST.get('valor_unitario'))
        documento = request.POST.get('documento', '').strip()
        observacao = request.POST.get('observacao', '').strip()
        op_id = request.POST.get('obra_op', '').strip()

        erros = []
        produto = ProdutoEstoque.objects.filter(pk=produto_id).first()
        local = LocalEstoque.objects.filter(pk=local_id).first()
        if not produto:
            erros.append('Escolha o produto.')
        if not local:
            erros.append('Escolha o local.')
        if quantidade <= 0:
            erros.append('A quantidade tem de ser maior que zero.')

        if erros:
            for e in erros:
                messages.error(request, e)
            return redirect('movimentar_estoque')

        valor_total = (quantidade * valor_unit) if valor_unit else Decimal('0')

        with transaction.atomic():
            mov = MovimentoEstoque.objects.create(
                produto=produto, local=local, tipo=tipo, origem=origem,
                quantidade=quantidade, valor_unitario=valor_unit,
                valor_total=valor_total, documento=documento,
                observacao=observacao, usuario=request.user,
                obra_op_id=int(op_id) if op_id.isdigit() else None,
            )
            mov.aplicar_no_saldo()

            # entrada atualiza o custo da ultima compra
            if tipo == 'ENTRADA' and valor_unit:
                produto.custo_ultima_compra = valor_unit
                produto.save(update_fields=['custo_ultima_compra'])

        logger.info(
            'Estoque: %s de %s %s em %s por %s',
            tipo, quantidade, produto.codigo, local.nome, request.user.username,
        )
        messages.success(
            request,
            f'{mov.tipo_nome} de {quantidade} {produto.unidade_efetiva} '
            f'— {produto.codigo} em {local.nome}.',
        )
        return redirect('lista_estoque')

    # GET
    produto_id = request.GET.get('produto', '').strip()
    context = {
        'produtos': ProdutoEstoque.objects.filter(ativo=True).select_related('grupo').order_by('codigo'),
        'locais': LocalEstoque.objects.filter(ativo=True),
        'produto_selecionado': produto_id,
        'ops': ObraOP.objects.order_by('-data_importacao')[:200],
        'ultimos': MovimentoEstoque.objects.select_related(
            'produto', 'local', 'usuario')[:20],
    }
    return render(request, 'core/estoque/movimentar.html', context)


@login_required(login_url='login')
@requer_rotina('lista_estoque')
def movimentos(request):
    """Histórico de movimentação com filtros."""
    query = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    origem = request.GET.get('origem', '').strip()

    qs = MovimentoEstoque.objects.select_related(
        'produto', 'produto__grupo', 'local', 'usuario', 'obra_op')

    if query:
        qs = qs.filter(
            Q(produto__codigo__icontains=query)
            | Q(produto__descricao__icontains=query)
            | Q(documento__icontains=query)
        )
    if tipo:
        qs = qs.filter(tipo=tipo)
    if origem:
        qs = qs.filter(origem=origem)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'movimentos': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'tipo_atual': tipo,
        'origem_atual': origem,
        'tipos': MovimentoEstoque._meta.get_field('tipo').choices,
        'origens': MovimentoEstoque._meta.get_field('origem').choices,
    }
    return render(request, 'core/estoque/movimentos.html', context)


@login_required(login_url='login')
@requer_rotina('lista_estoque')
def lista_produtos(request):
    """Cadastro de produtos do estoque."""
    query = request.GET.get('q', '').strip()
    grupo_id = request.GET.get('grupo', '').strip()

    produtos = ProdutoEstoque.objects.select_related('grupo').filter(ativo=True)
    if query:
        produtos = produtos.filter(
            Q(codigo__icontains=query) | Q(descricao__icontains=query)
            | Q(cor__icontains=query))
    if grupo_id:
        produtos = produtos.filter(grupo_id=grupo_id)
    produtos = produtos.order_by('codigo')

    paginator = Paginator(produtos, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'produtos': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'grupo_id': grupo_id,
        'grupos': GrupoEstoque.objects.filter(ativo=True),
    }
    return render(request, 'core/estoque/lista_produtos.html', context)


@login_required(login_url='login')
@requer_rotina('lista_estoque')
def novo_produto(request):
    """Cadastra um produto do estoque."""
    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip().upper()
        descricao = request.POST.get('descricao', '').strip()
        grupo_id = request.POST.get('grupo', '').strip()

        if not codigo or not descricao or not grupo_id:
            messages.error(request, 'Código, descrição e grupo são obrigatórios.')
            return redirect('novo_produto_estoque')

        if ProdutoEstoque.objects.filter(codigo=codigo).exists():
            messages.error(request, f'O código {codigo} já existe.')
            return redirect('novo_produto_estoque')

        grupo = get_object_or_404(GrupoEstoque, pk=grupo_id)
        produto = ProdutoEstoque.objects.create(
            codigo=codigo,
            descricao=descricao,
            grupo=grupo,
            unidade=request.POST.get('unidade', '').strip() or grupo.unidade,
            largura=_decimal(request.POST.get('largura'), None),
            altura=_decimal(request.POST.get('altura'), None),
            comprimento=_decimal(request.POST.get('comprimento'), None),
            cor=request.POST.get('cor', '').strip(),
            custo_medio=_decimal(request.POST.get('custo_medio')),
            estoque_minimo=_decimal(request.POST.get('estoque_minimo')),
            ponto_pedido=_decimal(request.POST.get('ponto_pedido')),
            codigo_ean=request.POST.get('codigo_ean', '').strip(),
            codigo_faktory=request.POST.get('codigo_faktory', '').strip(),
        )
        logger.info('Produto %s cadastrado por %s', codigo, request.user.username)
        messages.success(request, f'Produto {codigo} cadastrado.')
        return redirect('lista_produtos_estoque')

    context = {'grupos': GrupoEstoque.objects.filter(ativo=True)}
    return render(request, 'core/estoque/novo_produto.html', context)


@login_required(login_url='login')
@requer_rotina('lista_estoque')
def saldo_produto(request, produto_id):
    """Ficha do produto: saldo por local e histórico de movimentação."""
    produto = get_object_or_404(
        ProdutoEstoque.objects.select_related('grupo'), pk=produto_id)
    context = {
        'produto': produto,
        'saldos': produto.saldos.select_related('local'),
        'movimentos': produto.movimentos.select_related('local', 'usuario')[:50],
        'locais': LocalEstoque.objects.filter(ativo=True),
    }
    return render(request, 'core/estoque/saldo_produto.html', context)

@login_required(login_url='login')
@requer_rotina('lista_movimentos_hist')
def lista_movimentos_hist(request):
    """Movimentos de estoque importados do ERP (histórico).

    São 307.933 movimentos que vieram do Faktory. Ficam SEPARADOS dos
    movimentos vivos (MovimentoEstoque) porque não mexem no saldo atual —
    o saldo já veio correto na importação. Aqui é consulta e
    rastreabilidade.
    """
    from core.models import MovimentoEstoqueHistorico

    query = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    dias = request.GET.get('dias', '').strip()

    qs = MovimentoEstoqueHistorico.objects.all()
    if query:
        qs = qs.filter(
            Q(produto_codigo__icontains=query)
            | Q(produto_descricao__icontains=query)
            | Q(documento__icontains=query))
    if tipo:
        qs = qs.filter(tipo=tipo)

    from datetime import timedelta
    hoje = timezone.localdate()
    if dias and dias.isdigit():
        qs = qs.filter(data_movimento__gte=hoje - timedelta(days=int(dias)))

    qs = qs.order_by('-data_movimento', '-id')
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'movimentos': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'tipo_atual': tipo,
        'dias': dias,
        'kpi': {
            'total': MovimentoEstoqueHistorico.objects.count(),
            'entradas': MovimentoEstoqueHistorico.objects.filter(
                tipo='ENTRADA').count(),
            'saidas': MovimentoEstoqueHistorico.objects.filter(
                tipo='SAIDA').count(),
        },
    }
    return render(request, 'core/estoque/movimentos_hist.html', context)
