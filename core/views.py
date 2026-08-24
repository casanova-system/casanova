from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from .models import Obra
from .services import processar_excel_relatorio, calcular_precificacao_operacao

def lista_obras(request):
    obras = Obra.objects.all().order_by('-id')
    return render(request, 'core/index.html', {'obras': obras})

def upload_pdf(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        # Chamada atualizada para o serviço do Excel
        obra, _ = processar_excel_relatorio(excel_file)
        return redirect('detalhe_obra', pk=obra.pk)
        
    return render(request, 'core/upload.html')

def detalhe_obra(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    itens = obra.itens.all()

    total_pecas = sum(item.quantidade for item in itens)
    m2_corte_total = sum(item.m2_corte for item in itens)
    peso_total = sum(item.peso_kg for item in itens)
    custo_total_materiais = sum(item.custo_total for item in itens)

    if request.method == 'POST':
        dist_str = request.POST.get('distancia_km', str(obra.distancia_km))
        try:
            dist_km = float(dist_str.replace(',', '.'))
        except ValueError:
            dist_km = float(obra.distancia_km)

        res = calcular_precificacao_operacao(dist_km, float(m2_corte_total))
        
        obra.distancia_km = dist_km
        obra.custo_frete = Decimal(str(res['custo_frete']))
        obra.custo_operacao = Decimal(str(res['custo_operacao']))
        obra.custo_total_deslocamento = Decimal(str(res['custo_total_deslocamento']))
        obra.save()

        return redirect('detalhe_obra', pk=obra.pk)

    custo_geral_obra = custo_total_materiais + obra.custo_total_deslocamento

    context = {
        'obra': obra,
        'itens': itens,
        'total_pecas': total_pecas,
        'm2_corte_total': m2_corte_total,
        'peso_total': peso_total,
        'custo_total_materiais': custo_total_materiais,
        'custo_geral_obra': custo_geral_obra
    }
    return render(request, 'core/detalhe.html', context)