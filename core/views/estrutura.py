"""Estrutura — a composicao de cada produto.

13.342 estruturas com 13.383 componentes, do ERP.

Por que isto importa: a estrutura diz QUAIS perfis, vidros e componentes uma
esquadria leva. E o que permite explodir a OP — sabendo a esquadria, sabe-se
o material necessario. Sem ela, o custo da OP depende de alguem lancar o
consumo a mao.
"""
import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from core.models import EstruturaComponente, EstruturaProduto
from core.views.permissao import requer_rotina

logger = logging.getLogger(__name__)

ITENS_POR_PAGINA = 20


@login_required(login_url='login')
@requer_rotina('lista_estruturas')
def lista_estruturas(request):
    """Lista de estruturas de produto."""
    query = request.GET.get('q', '').strip()
    qs = EstruturaProduto.objects.all()
    if query:
        qs = qs.filter(
            Q(produto_codigo__icontains=query)
            | Q(produto_descricao__icontains=query))
    qs = qs.annotate(n_comp=Count('componentes')).order_by('produto_codigo')

    paginator = Paginator(qs, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'estruturas': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'kpi': {
            'estruturas': EstruturaProduto.objects.count(),
            'componentes': EstruturaComponente.objects.count(),
        },
    }
    return render(request, 'core/estrutura/lista_estruturas.html', context)


@login_required(login_url='login')
@requer_rotina('lista_estruturas')
def detalhe_estrutura(request, estrutura_id):
    """Detalhe: o que este produto leva."""
    estrutura = get_object_or_404(EstruturaProduto, pk=estrutura_id)
    componentes = estrutura.componentes.all()

    # o produto da estrutura no estoque, quando o codigo casa
    from core.models import ProdutoEstoque
    prod = ProdutoEstoque.objects.filter(
        codigo__iexact=estrutura.produto_codigo).first()

    # custo estimado: soma componente x custo do produto no estoque
    itens = []
    total = 0.0
    for c in componentes:
        p = ProdutoEstoque.objects.filter(
            codigo__iexact=c.componente_codigo).first()
        custo = float(p.custo_medio or 0) if p else 0.0
        sub = round(float(c.quantidade or 0) * custo, 4)
        total += sub
        itens.append({'comp': c, 'produto': p, 'custo_unit': custo, 'subtotal': sub})

    context = {
        'estrutura': estrutura,
        'itens': itens,
        'produto': prod,
        'total_componentes': len(itens),
        'custo_estimado': round(total, 2),
        'sem_custo': len([i for i in itens if i['custo_unit'] == 0]),
    }
    return render(request, 'core/estrutura/detalhe_estrutura.html', context)
