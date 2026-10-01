from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Sum
from django.shortcuts import render

from core.models import Obra
from core.views.permissao import requer_rotina

MESES_PT = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro',
}


@login_required(login_url='login')
@requer_rotina('relatorio_fretes_mes')
def relatorio_fretes_mes(request):
    """Relatório consolidado de fretes por período, com layout de impressão A4."""
    mes = request.GET.get('mes')
    ano = request.GET.get('ano')

    fretes = Obra.objects.select_related('veiculo', 'usuario').all()

    if mes:
        fretes = fretes.filter(data_emissao__month=mes)
    if ano:
        fretes = fretes.filter(data_emissao__year=ano)

    agregados = fretes.aggregate(
        total_custo=Sum('custo_total_deslocamento'),
        total_distancia=Sum('distancia_km'),
        total_peso=Sum('peso_total'),
        total_pecas=Sum('total_pecas'),
        total_m2=Sum('m2_total'),
        media_custo=Avg('custo_total_deslocamento'),
    )

    total_custo = agregados['total_custo'] or 0
    total_distancia = agregados['total_distancia'] or 0
    total_operacoes = fretes.count()
    media_custo = agregados['media_custo'] or 0

    # Rótulo do período selecionado
    if mes and ano:
        periodo_label = f'{MESES_PT.get(int(mes), mes)} / {ano}'
    elif ano:
        periodo_label = f'Ano {ano}'
    elif mes:
        periodo_label = MESES_PT.get(int(mes), mes)
    else:
        periodo_label = 'Todo o período'

    # Custo médio por quilômetro rodado
    custo_por_km = (float(total_custo) / float(total_distancia)) if total_distancia else 0

    context = {
        'fretes': fretes.order_by('-data_emissao', '-id'),
        'total_custo': total_custo,
        'total_distancia': total_distancia,
        'total_peso': agregados['total_peso'] or 0,
        'total_pecas': agregados['total_pecas'] or 0,
        'total_m2': agregados['total_m2'] or 0,
        'media_custo': media_custo,
        'custo_por_km': custo_por_km,
        'total_operacoes': total_operacoes,
        'periodo_label': periodo_label,
        'mes_selecionado': mes or '',
        'ano_selecionado': ano or '',
        'data_geracao': date.today(),
        'usuario_gerador': request.user.get_full_name() or request.user.username,
        'meses': MESES_PT,
    }
    return render(request, 'core/relatorios/relatorio_fretes_mes.html', context)