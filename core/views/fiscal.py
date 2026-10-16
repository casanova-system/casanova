"""Fiscal — consulta das notas fiscais.

65.359 notas com 203.135 itens, importadas do ERP (R$ 450,7 mi).

O sistema NAO emite NF-e — isso exige certificado digital e homologacao na
SEFAZ. O que esta tela faz e CONSULTAR o que ja foi faturado, que e o
documento que liga venda, estoque e financeiro.
"""
import logging
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from core.models import NotaFiscal, NotaFiscalItem
from core.views.permissao import requer_rotina

logger = logging.getLogger(__name__)

ITENS_POR_PAGINA = 20


def _parse(s):
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


@login_required(login_url='login')
@requer_rotina('lista_notas')
def lista_notas(request):
    """Lista de notas fiscais com filtro por periodo e tipo."""
    query = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    dias = request.GET.get('dias', '').strip()
    participante = request.GET.get('participante', '').strip()
    projeto = request.GET.get('projeto', '').strip()

    qs = NotaFiscal.objects.all()
    if query:
        qs = qs.filter(
            Q(numero__icontains=query)
            | Q(participante_nome__icontains=query)
            | Q(chave_acesso__icontains=query))
    if tipo:
        qs = qs.filter(tipo=tipo)
    if participante:
        qs = qs.filter(participante_nome__icontains=participante)
    if projeto:
        # NotaFiscal não tem campo projeto direto; busca pelo codigo_faktory
        qs = qs.filter(codigo_faktory__icontains=projeto)

    hoje = timezone.localdate()
    de = _parse(request.GET.get('de', ''))
    ate = _parse(request.GET.get('ate', ''))
    if dias and dias.isdigit():
        de = hoje - timedelta(days=int(dias))
        ate = hoje
    if de:
        qs = qs.filter(data_emissao__gte=de)
    if ate:
        qs = qs.filter(data_emissao__lte=ate)

    qs = qs.order_by('-data_emissao', '-id')
    paginator = Paginator(qs, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    agg = qs.aggregate(t=Sum('valor_total'), n=Count('id'))
    total = float(agg['t'] or 0)
    n = agg['n'] or 0

    # entradas x saidas no conjunto filtrado
    por_tipo = qs.values('tipo').annotate(
        n=Count('id'), t=Sum('valor_total')).order_by('-t')

    context = {
        'notas': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'tipo_atual': tipo,
        'participante': participante,
        'projeto': projeto,
        'de': de, 'ate': ate,
        'dias': dias,
        'kpi': {
            'notas': n,
            'total': round(total, 2),
            'media': round(total / n, 2) if n else 0,
        },
        'por_tipo': [
            {'nome': dict(NotaFiscal._meta.get_field('tipo').choices)
                     .get(x['tipo'], x['tipo']),
             'n': x['n'], 'total': float(x['t'] or 0)}
            for x in por_tipo
        ],
    }
    return render(request, 'core/fiscal/lista_notas.html', context)


@login_required(login_url='login')
@requer_rotina('lista_notas')
def detalhe_nota(request, nota_id):
    """Detalhe da nota com os itens."""
    nota = get_object_or_404(NotaFiscal, pk=nota_id)
    itens = nota.itens.all()
    context = {
        'nota': nota,
        'itens': itens,
        'total_itens': itens.count(),
        'valor_itens': round(sum(float(i.valor_total or 0) for i in itens), 2),
    }
    return render(request, 'core/fiscal/detalhe_nota.html', context)
