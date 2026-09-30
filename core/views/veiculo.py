from core.models import Veiculo
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.views.permissao import requer_rotina
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

ITENS_POR_PAGINA = 12


@login_required
@requer_rotina('lista_veiculos')
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

    paginator = Paginator(veiculos, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Querystring preservando filtros (sem o parâmetro page)
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()

    context = {
        'veiculos': page_obj,
        'page_obj': page_obj,
        'querystring': querystring,
        'query': query,
        'ordenacao_atual': ordenar,
    }
    return render(request, 'core/veiculos/lista_veiculo.html', context)


@login_required
@requer_rotina('lista_veiculos')
def cadastrar_veiculo(request):
    if request.method == 'POST':
        placa = request.POST.get('placa')
        chassi = request.POST.get('chassi') or None
        marca_modelo = request.POST.get('marca_modelo')
        ano_fabricacao = request.POST.get('ano_fabricacao')
        cor = request.POST.get('cor') or None
        tipo_combustivel = request.POST.get('tipo_combustivel') or None
        
        # Captura de todos os campos numéricos e dimensões com substituição de vírgula por ponto
        litros_tanque = request.POST.get('litros_tanque', '').replace(',', '.')
        comprimento_bau = request.POST.get('comprimento_bau', '').replace(',', '.')
        largura_bau = request.POST.get('largura_bau', '').replace(',', '.')
        altura_bau = request.POST.get('altura_bau', '').replace(',', '.')
        
        capacidade_volumetrica = request.POST.get('capacidade_volumetrica', '').replace(',', '.')
        consumo_combustivel = request.POST.get('consumo_combustivel', '').replace(',', '.')
        especificacao_tecnica = request.POST.get('especificacao_tecnica') or None
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
            ano_fabricacao=int(ano_fabricacao) if ano_fabricacao else None,
            cor=cor,
            tipo_combustivel=tipo_combustivel,
            litros_tanque=float(litros_tanque) if litros_tanque else None,
            comprimento_bau=float(comprimento_bau) if comprimento_bau else None,
            largura_bau=float(largura_bau) if largura_bau else None,
            altura_bau=float(altura_bau) if altura_bau else None,
            capacidade_volumetrica=float(capacidade_volumetrica) if capacidade_volumetrica else None,
            consumo_combustivel=float(consumo_combustivel) if consumo_combustivel else None,
            especificacao_tecnica=especificacao_tecnica,
            ativo=ativo,
            usuario_responsavel=request.user,
        )
        messages.success(request, 'Veículo cadastrado com sucesso!')
        return redirect('lista_veiculos')

    return render(request, 'core/veiculos/cadastro_veiculo.html')


@login_required
@requer_rotina('lista_veiculos')
def detalhe_veiculo(request, pk):
    veiculo = get_object_or_404(Veiculo, pk=pk)
    return render(request, 'core/veiculos/detalhe_veiculo.html', {'veiculo': veiculo})


@login_required
@requer_rotina('lista_veiculos')
def editar_veiculo(request, pk):
    veiculo = get_object_or_404(Veiculo, pk=pk)

    if request.method == 'POST':
        placa = request.POST.get('placa')
        marca_modelo = request.POST.get('marca_modelo')
        ano_fabricacao = request.POST.get('ano_fabricacao')
        capacidade_volumetrica = request.POST.get('capacidade_volumetrica', '').replace(',', '.')
        consumo_combustivel = request.POST.get('consumo_combustivel', '').replace(',', '.')
        
        # Capturando litros do tanque e as dimensões do baú na edição com tratamento de vírgula
        litros_tanque = request.POST.get('litros_tanque', '').replace(',', '.')
        comprimento_bau = request.POST.get('comprimento_bau', '').replace(',', '.')
        largura_bau = request.POST.get('largura_bau', '').replace(',', '.')
        altura_bau = request.POST.get('altura_bau', '').replace(',', '.')

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
            return render(request, 'core/veiculos/form_veiculo.html', {'veiculo': veiculo})

        veiculo.placa = placa.upper()
        veiculo.chassi = request.POST.get('chassi') or None
        veiculo.marca_modelo = marca_modelo
        veiculo.ano_fabricacao = int(ano_fabricacao) if ano_fabricacao else None
        veiculo.cor = request.POST.get('cor') or None
        veiculo.tipo_combustivel = request.POST.get('tipo_combustivel') or None
        
        # Atribuição com conversão segura para tipos numéricos
        veiculo.litros_tanque = float(litros_tanque) if litros_tanque else None
        veiculo.comprimento_bau = float(comprimento_bau) if comprimento_bau else None
        veiculo.largura_bau = float(largura_bau) if largura_bau else None
        veiculo.altura_bau = float(altura_bau) if altura_bau else None
        
        veiculo.capacidade_volumetrica = float(capacidade_volumetrica) if capacidade_volumetrica else None
        veiculo.consumo_combustivel = float(consumo_combustivel) if consumo_combustivel else None
        veiculo.especificacao_tecnica = request.POST.get('especificacao_tecnica') or None
        veiculo.ativo = True if request.POST.get('ativo') == 'on' else False
        veiculo.save()

        messages.success(request, 'Veículo atualizado com sucesso!')
        return redirect('lista_veiculos')

    return render(request, 'core/veiculos/form_veiculo.html', {'veiculo': veiculo})


@login_required
@requer_rotina('lista_veiculos')
def excluir_veiculo(request, pk):
    veiculo = get_object_or_404(Veiculo, pk=pk)
    if request.method == 'POST':
        veiculo.delete()
        messages.success(request, 'Veículo excluído com sucesso!')
        return redirect('lista_veiculos')
    return redirect('lista_veiculos')