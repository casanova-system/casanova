"""Acompanhamento de Mesa — produção por mesa (1-7) com gráficos por dia/semana/mês."""
from datetime import date, timedelta
from collections import defaultdict
from django.contrib import messages
from django.db.models import Count, Sum, Q, F
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from core.models import MovimentacaoOP, ObraOP
from core.views.permissao import requer_rotina
from core.views.rastreio import _garantir_setores, MSG_MIGRATION


@login_required(login_url='login')
@requer_rotina('producao')
def acompanhamento_mesa(request):
    """Dashboard de produção por mesa (1 a 7)."""
    if not _garantir_setores():
        messages.error(request, MSG_MIGRATION)
        return render(request, 'core/industria/acompanhamento_mesa.html', {
            'mesas': range(1, 8),
            'migration_pendente': True,
        })

    # Parâmetros de filtro
    dias = int(request.GET.get('dias', 7))
    mesa_filtro = request.GET.get('mesa', '')

    # Data base
    hoje = timezone.localdate()
    data_inicio = hoje - timedelta(days=dias - 1)

    # Query base: movimentações de saída no setor mesa com mesa definida
    movs = MovimentacaoOP.objects.filter(
        setor='mesa',
        data_saida__date__gte=data_inicio,
        data_saida__date__lte=hoje,
        mesa__isnull=False,
    ).select_related('rastreio')

    if mesa_filtro:
        movs = movs.filter(mesa=int(mesa_filtro))

    # Agregar por mesa e dia
    from collections import defaultdict
    dados_por_mesa_dia = defaultdict(lambda: defaultdict(int))
    dados_por_mesa_total = defaultdict(int)

    for mov in movs:
        dia = mov.data_saida.date()
        m = mov.mesa
        qtd = mov.quantidade_produzida or 0
        dados_por_mesa_dia[m][dia] += qtd
        dados_por_mesa_total[m] += qtd

    # Série para gráfico de linhas (últimos N dias)
    series = {}
    for m in range(1, 8):
        series[m] = []
        for i in range(dias - 1, -1, -1):
            dia = hoje - timedelta(days=i)
            series[m].append({
                'dia': dia.strftime('%d/%m'),
                'qtd': dados_por_mesa_dia[m].get(dia, 0),
            })

    # Resumo semanal e mensal
    semana_inicio = hoje - timedelta(days=hoje.weekday())
    mes_inicio = hoje.replace(day=1)

    semanal = {}
    mensal = {}
    for m in range(1, 8):
        semanal[m] = sum(
            q for dia, q in dados_por_mesa_dia[m].items()
            if dia >= semana_inicio
        )
        mensal[m] = sum(
            q for dia, q in dados_por_mesa_dia[m].items()
            if dia >= mes_inicio
        )

    # KPIs
    total_geral = sum(dados_por_mesa_total.values())
    melhor_mesa = max(dados_por_mesa_total.items(), key=lambda x: x[1], default=(None, 0))

    context = {
        'mesas': range(1, 8),
        'dias': dias,
        'mesa_filtro': mesa_filtro,
        'series': series,
        'totais': dados_por_mesa_total,
        'semanal': semanal,
        'mensal': mensal,
        'kpis': {
            'total_geral': total_geral,
            'melhor_mesa': melhor_mesa[0],
            'melhor_qtd': melhor_mesa[1],
        },
        'hoje': hoje,
    }
    return render(request, 'core/industria/acompanhamento_mesa.html', context)