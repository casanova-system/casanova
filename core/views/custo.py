from core.models import Custo 
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.views.permissao import requer_rotina
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

ITENS_POR_PAGINA = 12

@login_required
@requer_rotina('lista_custo')
def lista_custo(request):
    query = request.GET.get('q', '')
    ordenar = request.GET.get('ordenar', '')

    if query:
        custo = Custo.objects.filter(
            Q(tipo__icontains=query) | Q(descricao__icontains=query)
        )
    else:
        custo = Custo.objects.all()

    if ordenar == 'tipo_asc' or ordenar == 'nome_asc':
        custo = custo.order_by('tipo')
    elif ordenar == 'tipo_desc' or ordenar == 'nome_desc':
        custo = custo.order_by('-tipo')
    elif ordenar == 'recentes' or ordenar == 'id_desc':
        custo = custo.order_by('-id')
    elif ordenar == 'antigos' or ordenar == 'id_asc':
        custo = custo.order_by('id')
    elif ordenar == 'valor':
        custo = custo.order_by('valor')
    else:
        custo = custo.order_by('-id')  

    paginator = Paginator(custo, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()

    context = {
        'custos': page_obj,
        'page_obj': page_obj,
        'querystring': querystring,
        'query': query,
        'ordenacao_atual': ordenar,
    }
    return render(request, 'core/custos/lista_custo.html', context)


@login_required(login_url='login')
@requer_rotina('lista_custo')
def cadastrar_custo(request):
    if request.method == "POST":
        descricao = request.POST.get("descricao")
        tipo = request.POST.get("tipo")  
        
        valor_raw = request.POST.get("valor", "0")
        try:
            valor_tratado = valor_raw.replace('.', '').replace(',', '.')
            valor = float(valor_tratado) if valor_tratado else 0.0
        except ValueError:
            valor = 0.0

        try:
            Custo.objects.create(
                descricao=descricao, 
                valor=valor, 
                tipo=tipo, 
                usuario_responsavel=request.user
            )
            messages.success(request, "Custo cadastrado com sucesso!")
            return redirect("lista_custo")
        except Exception as e:
            messages.error(request, f"Erro ao cadastrar custo: {e}")
            
    return render(request, "core/custos/form_custo.html")


@login_required(login_url='login')
@requer_rotina('lista_custo')
def editar_custo(request, pk):
    custo = get_object_or_404(Custo, pk=pk)
    if request.method == "POST":
        custo.descricao = request.POST.get("descricao")
        custo.tipo = request.POST.get("tipo")
        
        valor_raw = request.POST.get("valor", "0")
        try:
            valor_tratado = valor_raw.replace('.', '').replace(',', '.')
            custo.valor = float(valor_tratado) if valor_tratado else 0.0
        except ValueError:
            custo.valor = 0.0

        try:
            custo.save()
            messages.success(request, "Custo atualizado com sucesso!")
            return redirect("lista_custo")
        except Exception as e:
            messages.error(request, f"Erro ao atualizar custo: {e}")
            
    return render(request, "core/custos/form_custo.html", {"custo": custo})


@login_required(login_url='login')
@requer_rotina('lista_custo')
def detalhe_custo(request, pk):
    """Exibe os detalhes de um custo específico."""
    custo = get_object_or_404(Custo, pk=pk)
    return render(request, "core/custos/detalhe_custo.html", {"custo": custo})