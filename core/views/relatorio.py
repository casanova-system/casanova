from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg
from core.models import Obra
from core.views.permissao import requer_rotina

@login_required(login_url='login')
@requer_rotina('relatorio_fretes_mes')
def relatorio_fretes_mes(request):
    mes = request.GET.get('mes')
    ano = request.GET.get('ano')

    fretes = Obra.objects.all()

    # Usando 'data_emissao' conforme os campos do model
    if mes:
        fretes = fretes.filter(data_emissao__month=mes)
    if ano:
        fretes = fretes.filter(data_emissao__year=ano)

    total_custo = fretes.aggregate(Sum('custo_total_deslocamento'))['custo_total_deslocamento__sum'] or 0

    # Usando 'distancia_km' em vez de 'distancia'
    total_distancia = fretes.aggregate(Sum('distancia_km'))['distancia_km__sum'] or 0

    media_custo = fretes.aggregate(Avg('custo_total_deslocamento'))['custo_total_deslocamento__avg'] or 0
    total_operacoes = fretes.count()

    context = {
        'fretes': fretes.order_by('-data_emissao', '-id'),
        'total_custo': total_custo,
        'total_distancia': total_distancia,
        'media_custo': media_custo,
        'total_operacoes': total_operacoes,
    }
    return render(request, 'core/relatorios/relatorio_fretes_mes.html', context)