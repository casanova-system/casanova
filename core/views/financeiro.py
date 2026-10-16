"""Financeiro — contas a pagar e a receber.

94.416 titulos a pagar e 11.108 a receber, importados do ERP com o valor
e o status reais. O valor pago veio da tabela de baixa, nao de estimativa.
"""
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from core.models import ContaPagar, ContaReceber
from core.views.permissao import requer_rotina

logger = logging.getLogger(__name__)

ITENS_POR_PAGINA = 20


def _filtro_comum(request, qs, campo_data):
    """Aplica busca, status e periodo — igual nas duas telas.

    Centralizar evita o bug classico de filtrar numa tela e esquecer na
    outra, fazendo os dois lados mostrarem numeros diferentes.
    """
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    situacao = request.GET.get('situacao', '').strip()
    dias = request.GET.get('dias', '').strip()

    hoje = timezone.localdate()
    if query:
        qs = qs.filter(
            Q(numero__icontains=query)
            | Q(parcela__icontains=query)
            | Q(observacao__icontains=query))
    if status:
        qs = qs.filter(status=status)

    # situacao e o filtro que o financeiro usa de verdade
    if situacao == 'vencido':
        qs = qs.filter(**{f'{campo_data}__lt': hoje}).exclude(
            status__in=['PAGO', 'RECEBIDO', 'CANCELADO'])
    elif situacao == 'hoje':
        qs = qs.filter(**{campo_data: hoje}).exclude(
            status__in=['PAGO', 'RECEBIDO', 'CANCELADO'])
    elif situacao == 'semana':
        qs = qs.filter(**{f'{campo_data}__range': [hoje, hoje + timedelta(days=7)]}
                       ).exclude(status__in=['PAGO', 'RECEBIDO', 'CANCELADO'])
    elif situacao == 'mes':
        qs = qs.filter(**{f'{campo_data}__range': [hoje, hoje + timedelta(days=30)]}
                       ).exclude(status__in=['PAGO', 'RECEBIDO', 'CANCELADO'])
    elif situacao == 'aberto':
        qs = qs.exclude(status__in=['PAGO', 'RECEBIDO', 'CANCELADO'])

    if dias and dias.isdigit():
        qs = qs.filter(**{f'{campo_data}__gte': hoje - timedelta(days=int(dias))})

    return qs, query, status, situacao


@login_required(login_url='login')
@requer_rotina('lista_contas_pagar')
def lista_contas_pagar(request):
    """Contas a pagar com foco no que esta vencido."""
    hoje = timezone.localdate()
    qs = ContaPagar.objects.select_related('fornecedor')
    qs, query, status, situacao = _filtro_comum(request, qs, 'data_vencimento')
    qs = qs.order_by('data_vencimento', 'id')

    paginator = Paginator(qs, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    # KPIs sobre o CONJUNTO FILTRADO (o numero tem que casar com a lista)
    agg = qs.aggregate(t=Sum('valor'), n=Count('id'))
    total = float(agg['t'] or 0)
    n = agg['n'] or 0

    base = ContaPagar.objects.all()
    abertas = base.exclude(status__in=['PAGO', 'CANCELADO'])
    vencidas = abertas.filter(data_vencimento__lt=hoje)

    # fluxo: quanto vence nos proximos 7 dias
    semana = abertas.filter(
        data_vencimento__range=[hoje, hoje + timedelta(days=7)])

    context = {
        'contas': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'status_atual': status,
        'situacao': situacao,
        'status_opcoes': ContaPagar._meta.get_field('status').choices,
        'kpi': {
            'filtrado_n': n,
            'filtrado_total': round(total, 2),
            'aberto': round(float(abertas.aggregate(
                t=Sum('valor'))['t'] or 0), 2),
            'aberto_n': abertas.count(),
            'vencido': round(float(vencidas.aggregate(
                t=Sum('valor'))['t'] or 0), 2),
            'vencido_n': vencidas.count(),
            'semana': round(float(semana.aggregate(
                t=Sum('valor'))['t'] or 0), 2),
            'semana_n': semana.count(),
        },
        'hoje': hoje,
    }
    return render(request, 'core/financeiro/lista_contas_pagar.html', context)


@login_required(login_url='login')
@requer_rotina('lista_contas_receber')
def lista_contas_receber(request):
    """Contas a receber."""
    hoje = timezone.localdate()
    qs = ContaReceber.objects.all()
    qs, query, status, situacao = _filtro_comum(request, qs, 'data_vencimento')
    qs = qs.order_by('data_vencimento', 'id')

    paginator = Paginator(qs, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    agg = qs.aggregate(t=Sum('valor'), n=Count('id'))
    total = float(agg['t'] or 0)
    n = agg['n'] or 0

    base = ContaReceber.objects.all()
    abertas = base.exclude(status__in=['RECEBIDO', 'CANCELADO'])
    vencidas = abertas.filter(data_vencimento__lt=hoje)
    semana = abertas.filter(
        data_vencimento__range=[hoje, hoje + timedelta(days=7)])

    context = {
        'contas': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'status_atual': status,
        'situacao': situacao,
        'status_opcoes': ContaReceber._meta.get_field('status').choices,
        'kpi': {
            'filtrado_n': n,
            'filtrado_total': round(total, 2),
            'aberto': round(float(abertas.aggregate(
                t=Sum('valor'))['t'] or 0), 2),
            'aberto_n': abertas.count(),
            'vencido': round(float(vencidas.aggregate(
                t=Sum('valor'))['t'] or 0), 2),
            'vencido_n': vencidas.count(),
            'semana': round(float(semana.aggregate(
                t=Sum('valor'))['t'] or 0), 2),
            'semana_n': semana.count(),
        },
        'hoje': hoje,
    }
    return render(request, 'core/financeiro/lista_contas_receber.html', context)


@login_required(login_url='login')
@requer_rotina('lista_contas_pagar')
def painel_financeiro(request):
    """Painel: o retrato do dinheiro da fabrica.

    Junta a pagar e a receber numa tela so — e a pergunta que o dono faz:
    'como estou?'
    """
    hoje = timezone.localdate()

    pagar = ContaPagar.objects.exclude(status__in=['PAGO', 'CANCELADO'])
    receber = ContaReceber.objects.exclude(status__in=['RECEBIDO', 'CANCELADO'])

    def tot(qs):
        return round(float(qs.aggregate(t=Sum('valor'))['t'] or 0), 2)

    # aging: quanto esta em cada faixa de atraso
    faixas = [
        ('A vencer', None, 0),
        ('Vence hoje', 0, 0),
        ('1 a 30 dias', -30, -1),
        ('31 a 60 dias', -60, -31),
        ('61 a 90 dias', -90, -61),
        ('Mais de 90', None, -91),
    ]

    def aging(qs, campo='data_vencimento'):
        linhas = []
        for nome, de, ate in faixas:
            f = qs
            if nome == 'A vencer':
                f = qs.filter(**{f'{campo}__gt': hoje})
            elif nome == 'Vence hoje':
                f = qs.filter(**{campo: hoje})
            elif nome == 'Mais de 90':
                f = qs.filter(**{f'{campo}__lt': hoje + timedelta(days=ate)})
            else:
                f = qs.filter(**{
                    f'{campo}__range': [hoje + timedelta(days=de),
                                        hoje + timedelta(days=ate)]})
            linhas.append({
                'nome': nome,
                'n': f.count(),
                'total': tot(f),
            })
        return linhas

    context = {
        'hoje': hoje,
        'pagar': {
            'aberto': tot(pagar),
            'n': pagar.count(),
            'vencido': tot(pagar.filter(data_vencimento__lt=hoje)),
            'vencido_n': pagar.filter(data_vencimento__lt=hoje).count(),
            'semana': tot(pagar.filter(data_vencimento__range=[
                hoje, hoje + timedelta(days=7)])),
        },
        'receber': {
            'aberto': tot(receber),
            'n': receber.count(),
            'vencido': tot(receber.filter(data_vencimento__lt=hoje)),
            'vencido_n': receber.filter(data_vencimento__lt=hoje).count(),
            'semana': tot(receber.filter(data_vencimento__range=[
                hoje, hoje + timedelta(days=7)])),
        },
        'aging_pagar': aging(pagar),
        'aging_receber': aging(receber),
    }
    context['saldo'] = round(context['receber']['aberto']
                             - context['pagar']['aberto'], 2)
    return render(request, 'core/financeiro/painel.html', context)
