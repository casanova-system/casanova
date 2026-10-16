"""Funcionarios — quem trabalha na fabrica.

414 funcionarios do ERP, 109 com valor/hora. O valor/hora e o que permite
calcular o custo de mao de obra por OP com o valor REAL da fabrica, em vez
de um chute.
"""
import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Funcionario
from core.views.permissao import requer_rotina

logger = logging.getLogger(__name__)

ITENS_POR_PAGINA = 20


@login_required(login_url='login')
@requer_rotina('lista_funcionarios')
def lista_funcionarios(request):
    """Lista de funcionarios com o valor/hora."""
    query = request.GET.get('q', '').strip()
    setor = request.GET.get('setor', '').strip()
    filtro = request.GET.get('filtro', '').strip()

    qs = Funcionario.objects.all()
    if query:
        qs = qs.filter(
            Q(nome__icontains=query) | Q(cargo__icontains=query)
            | Q(cpf__icontains=query))
    if setor:
        qs = qs.filter(setor=setor)
    if filtro == 'sem_hora':
        qs = qs.filter(valor_hora=0)
    elif filtro == 'com_hora':
        qs = qs.filter(valor_hora__gt=0)
    elif filtro == 'inativo':
        qs = qs.filter(ativo=False)
    else:
        qs = qs.filter(ativo=True)

    qs = qs.order_by('nome')
    paginator = Paginator(qs, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    # setores existentes (para o filtro)
    setores = (Funcionario.objects.exclude(setor='')
               .values_list('setor', flat=True).distinct().order_by('setor'))

    base = Funcionario.objects.filter(ativo=True)
    com_hora = base.filter(valor_hora__gt=0)

    context = {
        'funcionarios': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'setor_atual': setor,
        'filtro': filtro,
        'setores': setores,
        'kpi': {
            'total': base.count(),
            'com_hora': com_hora.count(),
            'sem_hora': base.filter(valor_hora=0).count(),
            'media_hora': round(float(com_hora.aggregate(
                m=Avg('valor_hora'))['m'] or 0), 2),
            'folha_hora': round(float(com_hora.aggregate(
                t=Sum('valor_hora'))['t'] or 0), 2),
        },
    }
    return render(request, 'core/pessoas/lista_funcionarios.html', context)


@login_required(login_url='login')
@requer_rotina('lista_funcionarios')
def editar_funcionario(request, func_id):
    """Edita o funcionario (principalmente o valor/hora).

    O valor/hora e o dado que mais precisa de ajuste: veio do ERP e muda
    com dissidio e promocao.
    """
    f = get_object_or_404(Funcionario, pk=func_id)

    if request.method == 'POST':
        from decimal import Decimal, InvalidOperation
        f.nome = request.POST.get('nome', f.nome).strip()[:200]
        f.setor = request.POST.get('setor', '').strip()[:80]
        f.cargo = request.POST.get('cargo', '').strip()[:120]
        f.telefone = request.POST.get('telefone', '').strip()[:40]
        f.ativo = request.POST.get('ativo') == 'on'
        vh = request.POST.get('valor_hora', '').strip()
        if vh:
            try:
                f.valor_hora = Decimal(vh.replace('.', '').replace(',', '.')
                                       if ',' in vh else vh)
            except (InvalidOperation, ValueError):
                pass
        f.save()
        from django.contrib import messages
        messages.success(request, f'{f.nome} atualizado.')
        return redirect('lista_funcionarios')

    context = {'funcionario': f}
    return render(request, 'core/pessoas/editar_funcionario.html', context)


@login_required(login_url='login')
@requer_rotina('lista_funcionarios')
def funcionarios_por_setor(request):
    """Resumo por setor — a base para o custo/hora do setor.

    Aqui o gestor ve a media real de cada setor e usa isso para ajustar o
    CustoSetor, que e o que o calculo de custo da OP usa.
    """
    from core.models import CustoSetor

    setores = []
    for s in (Funcionario.objects.filter(ativo=True)
              .exclude(setor='').values_list('setor', flat=True)
              .distinct().order_by('setor')):
        funcs = Funcionario.objects.filter(setor=s, ativo=True)
        com = funcs.filter(valor_hora__gt=0)
        media = round(float(com.aggregate(m=Avg('valor_hora'))['m'] or 0), 2)
        setores.append({
            'nome': s,
            'total': funcs.count(),
            'com_hora': com.count(),
            'media': media,
            'maior': round(float(com.order_by('-valor_hora')
                                 .values_list('valor_hora', flat=True).first() or 0), 2),
            'menor': round(float(com.order_by('valor_hora')
                                 .values_list('valor_hora', flat=True).first() or 0), 2),
        })

    context = {'setores': setores, 'total_setores': len(setores)}
    return render(request, 'core/pessoas/por_setor.html', context)
