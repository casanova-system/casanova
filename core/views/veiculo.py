from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.models import Veiculo

@login_required
def lista_veiculos(request):
    query = request.GET.get('q', '')
    if query:
        veiculos = Veiculo.objects.filter(placa__icontains=query) | Veiculo.objects.filter(marca_modelo__icontains=query)
    else:
        veiculos = Veiculo.objects.all().order_by('-id')
    
    context = {
        'veiculos': veiculos,
        'query': query
    }
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
        especificacao_tecnica = request.POST.get('especificacao_tecnica')
        ativo = True if request.POST.get('ativo') == 'on' else False

        if Veiculo.objects.filter(placa=placa).exists():
            messages.error(request, 'Já existe um veículo cadastrado com esta placa.')
            return redirect('cadastrar_veiculo')

        Veiculo.objects.create(
            placa=placa.upper() if placa else '',
            chassi=chassi,
            marca_modelo=marca_modelo,
            ano_fabricacao=ano_fabricacao or 2026,
            cor=cor,
            tipo_combustivel=tipo_combustivel,
            especificacao_tecnica=especificacao_tecnica,
            ativo=ativo,
            usuario_responsavel=request.user
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
        veiculo.placa = request.POST.get('placa').upper() if request.POST.get('placa') else ''
        veiculo.chassi = request.POST.get('chassi')
        veiculo.marca_modelo = request.POST.get('marca_modelo')
        veiculo.ano_fabricacao = request.POST.get('ano_fabricacao')
        veiculo.cor = request.POST.get('cor')
        veiculo.tipo_combustivel = request.POST.get('tipo_combustivel')
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