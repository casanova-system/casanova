from core.models import Veiculo
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render


@login_required
def lista_veiculos(request):
  query = request.GET.get('q', '')
  ordenar = request.GET.get('ordenar', '')

  if query:
    veiculos = Veiculo.objects.filter(
        Q(placa__icontains=query) | Q(marca_modelo__icontains=query)
    )
  else:
    veiculos = Veiculo.objects.all()

  if ordenar == 'recentes':
    veiculos = veiculos.order_by('-id')
  elif ordenar == 'antigos':
    veiculos = veiculos.order_by('id')
  elif ordenar == 'modelo_asc':
    veiculos = veiculos.order_by('marca_modelo')
  elif ordenar == 'modelo_desc':
    veiculos = veiculos.order_by('-marca_modelo')
  elif ordenar == 'placa_asc':
    veiculos = veiculos.order_by('placa')
  elif ordenar == 'placa_desc':
    veiculos = veiculos.order_by('-placa')
  else:
    veiculos = veiculos.order_by('-id')

  context = {'veiculos': veiculos, 'query': query}
  return render(request, 'veiculos/lista_veiculo.html', context)


@login_required
def cadastrar_veiculo(request):
  if request.method == 'POST':
    placa = request.POST.get('placa')
    chassi = request.POST.get('chassi')
    marca_modelo = request.POST.get('marca_modelo')
    ano_fabricacao = request.POST.get('ano_fabricacao')
    cor = request.POST.get('cor')
    tipo_combustivel = request.POST.get('tipo_combustivel')
    capacidade_volumetrica = request.POST.get('capacidade_volumetrica')
    consumo_combustivel = request.POST.get('consumo_combustivel')
    especificacao_tecnica = request.POST.get('especificacao_tecnica')
    ativo = True if request.POST.get('ativo') == 'on' else False

    # Validação rígida contra campos vazios no backend
    if not placa or not marca_modelo or not ano_fabricacao or not capacidade_volumetrica or not consumo_combustivel:
      messages.error(request, 'Preencha todos os campos obrigatórios marcados com asterisco (*).')
      return redirect('cadastrar_veiculo')

    if Veiculo.objects.filter(placa=placa.upper()).exists():
      messages.error(request, 'Já existe um veículo cadastrado com esta placa.')
      return redirect('cadastrar_veiculo')

    Veiculo.objects.create(
        placa=placa.upper(),
        chassi=chassi,
        marca_modelo=marca_modelo,
        ano_fabricacao=ano_fabricacao,
        cor=cor,
        tipo_combustivel=tipo_combustivel,
        capacidade_volumetrica=capacidade_volumetrica,
        consumo_combustivel=consumo_combustivel,
        especificacao_tecnica=especificacao_tecnica,
        ativo=ativo,
        usuario_responsavel=request.user,
    )
    messages.success(request, 'Veículo cadastrado com sucesso!')
    return redirect('lista_veiculos')

  return render(request, 'veiculos/cadastro_veiculo.html')


@login_required
def detalhe_veiculo(request, pk):
  veiculo = get_object_or_404(Veiculo, pk=pk)
  return render(request, 'veiculos/detalhe_veiculo.html', {'veiculo': veiculo})

@login_required
def editar_veiculo(request, pk):
    veiculo = get_object_or_404(Veiculo, pk=pk)

    if request.method == 'POST':
        placa = request.POST.get('placa')
        marca_modelo = request.POST.get('marca_modelo')
        ano_fabricacao = request.POST.get('ano_fabricacao')
        capacidade_volumetrica = request.POST.get('capacidade_volumetrica')
        consumo_combustivel = request.POST.get('consumo_combustivel')

        if (
            not placa
            or not marca_modelo
            or not ano_fabricacao
            or not capacidade_volumetrica
            or not consumo_combustivel
        ):
            messages.error(
                request,
                'Preencha todos os campos obrigatórios marcados com asterisco (*).',
            )
            return render(request, 'veiculos/form_veiculo.html', {'veiculo': veiculo})

        veiculo.placa = placa.upper()
        veiculo.chassi = request.POST.get('chassi')
        veiculo.marca_modelo = marca_modelo
        veiculo.ano_fabricacao = ano_fabricacao
        veiculo.cor = request.POST.get('cor')
        veiculo.tipo_combustivel = request.POST.get('tipo_combustivel')
        veiculo.capacidade_volumetrica = capacidade_volumetrica
        veiculo.consumo_combustivel = consumo_combustivel
        veiculo.especificacao_tecnica = request.POST.get('especificacao_tecnica')
        veiculo.ativo = True if request.POST.get('ativo') == 'on' else False
        veiculo.save()

        messages.success(request, 'Veículo atualizado com sucesso!')
        return redirect('lista_veiculos')

    return render(request, 'veiculos/form_veiculo.html', {'veiculo': veiculo})
@login_required
def excluir_veiculo(request, pk):
  veiculo = get_object_or_404(Veiculo, pk=pk)
  if request.method == 'POST':
    veiculo.delete()
    messages.success(request, 'Veículo excluído com sucesso!')
    return redirect('lista_veiculos')
  return redirect('lista_veiculos')

  