import json
from core.models import Obra
from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render


@login_required
def grafico_custo_frete(request):
  obras = Obra.objects.all().order_by('-id')

  obras_data = []
  for obra in obras:
    # Tratamento seguro para o cliente (se for string ou objeto)
    cliente_nome = 'Não informado'
    if hasattr(obra, 'cliente') and obra.cliente:
      if isinstance(obra.cliente, str):
        cliente_nome = obra.cliente
      elif hasattr(obra.cliente, 'nome'):
        cliente_nome = obra.cliente.nome
      else:
        cliente_nome = str(obra.cliente)

    # Tratamento seguro para o nome da obra
    nome_obra = (
        obra.nome_obra
        if hasattr(obra, 'nome_obra') and obra.nome_obra
        else str(obra)
    )

    obras_data.append({
        'nome': nome_obra,
        'cliente': cliente_nome,
        'custo_total_deslocamento': float(obra.custo_total_deslocamento or 0),
        'distancia': float(obra.distancia_km or 0),
    })

  context = {'obras_json': json.dumps(obras_data, cls=DjangoJSONEncoder)}
  return render(request, 'core/graficos/grafico_custo_frete.html', context)