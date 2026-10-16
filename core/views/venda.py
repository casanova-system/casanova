"""Venda — pedidos e propostas comerciais.

Importado do ERP: 3.808 pedidos com 41.030 itens e 2.327 propostas.

O valor vem do proprio pedido (soma dos itens gravada na importacao), nao
de recalculo na tela: assim o total na tela e o mesmo do ERP.
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from core.models import VendaPedido, VendaPedidoItem, VendaProposta, VendaPropostaItem
from core.views.permissao import requer_rotina

logger = logging.getLogger(__name__)

ITENS_POR_PAGINA = 20


def _periodo(request):
    """Le o filtro de periodo da querystring.

    Aceita data_inicio/data_fim e tambem o atalho 'dias', que e o que o
    usuario realmente usa no dia a dia ("ultimos 30 dias").
    """
    hoje = timezone.localdate()
    dias = request.GET.get('dias', '').strip()
    de = request.GET.get('de', '').strip()
    ate = request.GET.get('ate', '').strip()

    def parse(s):
        for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
            try:
                return datetime.strptime(s, fmt).date()
            except (ValueError, TypeError):
                continue
        return None

    if dias and dias.isdigit():
        return hoje - timedelta(days=int(dias)), hoje
    d1, d2 = parse(de), parse(ate)
    return d1, d2


def _filtra_periodo(qs, campo, request):
    de, ate = _periodo(request)
    if de:
        qs = qs.filter(**{f'{campo}__gte': de})
    if ate:
        qs = qs.filter(**{f'{campo}__lte': ate})
    return qs, de, ate


@login_required(login_url='login')
@requer_rotina('lista_vendas')
def lista_vendas(request):
    """Lista de pedidos de venda."""
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    participante = request.GET.get('participante', '').strip()
    projeto = request.GET.get('projeto', '').strip()

    qs = VendaPedido.objects.all()
    if query:
        qs = qs.filter(
            Q(numero__icontains=query)
            | Q(cliente_nome__icontains=query)
            | Q(observacao__icontains=query))
    if status:
        qs = qs.filter(status=status)
    if participante:
        qs = qs.filter(cliente_nome__icontains=participante)
    if projeto:
        qs = qs.filter(obra__codigo__icontains=projeto)

    qs, de, ate = _filtra_periodo(qs, 'data_cadastro', request)
    qs = qs.order_by('-data_cadastro', '-id')

    paginator = Paginator(qs, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    # KPIs do periodo filtrado (nao do banco todo: o numero tem que casar
    # com o que esta na tela)
    agg = qs.aggregate(t=Sum('valor_total'), n=Count('id'))
    total = float(agg['t'] or 0)
    n = agg['n'] or 0

    por_status = (qs.values('status').annotate(
        n=Count('id'), t=Sum('valor_total')).order_by('-t'))

    context = {
        'pedidos': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'status_atual': status,
        'participante': participante,
        'projeto': projeto,
        'status_opcoes': VendaPedido._meta.get_field('status').choices,
        'de': de, 'ate': ate,
        'dias': request.GET.get('dias', ''),
        'kpi': {
            'pedidos': n,
            'total': round(total, 2),
            'ticket': round(total / n, 2) if n else 0,
            'itens': VendaPedidoItem.objects.filter(
                pedido__in=qs.values('id')).count() if n else 0,
        },
        'por_status': [
            {'nome': dict(VendaPedido._meta.get_field('status').choices)
                     .get(x['status'], x['status']),
             'n': x['n'], 'total': float(x['t'] or 0)}
            for x in por_status
        ],
    }
    return render(request, 'core/venda/lista_vendas.html', context)


@login_required(login_url='login')
@requer_rotina('lista_vendas')
def detalhe_venda(request, venda_id):
    """Detalhe do pedido: itens, valores e o que ja foi faturado."""
    pedido = get_object_or_404(VendaPedido, pk=venda_id)
    itens = pedido.itens.select_related('produto').all()

    # contas a receber ligadas a este pedido (quando o vinculo existe)
    from core.models import ContaReceber
    contas = ContaReceber.objects.filter(venda=pedido)

    context = {
        'pedido': pedido,
        'itens': itens,
        'contas': contas,
        'total_itens': itens.count(),
        'valor_itens': round(sum(float(i.valor_total or 0) for i in itens), 2),
    }
    return render(request, 'core/venda/detalhe_venda.html', context)


@login_required(login_url='login')
@requer_rotina('lista_propostas')
def lista_propostas(request):
    """Lista de propostas comerciais."""
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    participante = request.GET.get('participante', '').strip()

    qs = VendaProposta.objects.all()
    if query:
        qs = qs.filter(
            Q(numero__icontains=query) | Q(cliente_nome__icontains=query))
    if status:
        qs = qs.filter(status=status)
    if participante:
        qs = qs.filter(cliente_nome__icontains=participante)

    qs, de, ate = _filtra_periodo(qs, 'data_cadastro', request)
    qs = qs.order_by('-data_cadastro', '-id')

    paginator = Paginator(qs, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    agg = qs.aggregate(t=Sum('valor_total'), n=Count('id'))
    total = float(agg['t'] or 0)
    n = agg['n'] or 0

    context = {
        'propostas': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'status_atual': status,
        'participante': participante,
        'status_opcoes': VendaProposta._meta.get_field('status').choices,
        'de': de, 'ate': ate,
        'dias': request.GET.get('dias', ''),
        'kpi': {
            'propostas': n,
            'total': round(total, 2),
            'media': round(total / n, 2) if n else 0,
        },
    }
    return render(request, 'core/venda/lista_propostas.html', context)


@login_required(login_url='login')
@requer_rotina('lista_propostas')
def detalhe_proposta(request, proposta_id):
    """Detalhe da proposta."""
    proposta = get_object_or_404(VendaProposta, pk=proposta_id)
    itens = proposta.itens.all()
    context = {
        'proposta': proposta,
        'itens': itens,
        'total_itens': itens.count(),
        'valor_itens': round(sum(float(i.valor_total or 0) for i in itens), 2),
    }
    return render(request, 'core/venda/detalhe_proposta.html', context)
