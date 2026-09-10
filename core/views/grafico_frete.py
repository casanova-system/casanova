import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from core.models import Obra


@login_required(login_url='login')
def grafico_custo_frete(request):
    """
    View que serializa as obras em formato JSON limpo para consumo direto do Chart.js.
    """
    obras_qs = Obra.objects.all().order_by('-id')
    
    obras_lista = [
        {
            "nome": obra.nome,
            "custo_total_deslocamento": float(obra.custo_total_deslocamento)
        }
        for obra in obras_qs
    ]
    
    context = {
        "obras_json": json.dumps(obras_lista),
    }
    return render(request, "core/graficos/grafico_custo_frete.html", context)