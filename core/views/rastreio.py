"""Rastreio de Produção — acompanha a OP pelos setores via QR Code.

Fluxo padrão:
    Separação → Usinagem → Mesa → (com vidro: Encaixilhamento) → Expedição

O operador escaneia o QR Code da OP em cada setor e o sistema registra
data, hora e usuário da passagem. A decisão "tem vidro?" acontece na Mesa.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render

from core.models import (
    MovimentacaoOP,
    RastreioOP,
    SetorProducao,
    garantir_setores_padrao,
)
from core.views.ordem_producao import _buscar_op_por_id
from core.views.permissao import requer_rotina

ITENS_POR_PAGINA = 12


def _setores_ativos():
    """Lista os setores ativos na ordem do fluxo."""
    return list(SetorProducao.objects.filter(ativo=True).order_by('ordem'))


def _proximo_setor(codigo_atual, tem_vidro):
    """Retorna o próximo setor do fluxo (pulando Encaixilhamento se não tiver vidro)."""
    setores = _setores_ativos()
    codigos = [s.codigo for s in setores]
    if codigo_atual not in codigos:
        return setores[0] if setores else None
    idx = codigos.index(codigo_atual)
    for prox in setores[idx + 1:]:
        if prox.requer_vidro and tem_vidro is False:
            continue
        return prox
    return None


def _setor_anterior(codigo_atual, tem_vidro):
    """Retorna o setor anterior do fluxo (para correções)."""
    setores = _setores_ativos()
    codigos = [s.codigo for s in setores]
    if codigo_atual not in codigos:
        return None
    idx = codigos.index(codigo_atual)
    for ant in reversed(setores[:idx]):
        if ant.requer_vidro and tem_vidro is False:
            continue
        return ant
    return None


@login_required(login_url='login')
@requer_rotina('rastreio_producao')
def rastreio_producao(request):
    """Painel com todas as OPs em rastreio."""
    garantir_setores_padrao()

    q = request.GET.get('q', '').strip()
    setor = request.GET.get('setor', '').strip()
    status = request.GET.get('status', '').strip()

    rastreios = RastreioOP.objects.all()
    if q:
        rastreios = rastreios.filter(
            Q(op_numero__icontains=q)
            | Q(obra__icontains=q)
            | Q(produto__icontains=q)
        )
    if setor:
        rastreios = rastreios.filter(setor_atual=setor)
    if status:
        rastreios = rastreios.filter(status=status)

    paginator = Paginator(rastreios, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'page_obj': page_obj,
        'rastreios': page_obj.object_list,
        'setores': _setores_ativos(),
        'filtros': request.GET,
        'querystring': params.urlencode(),
    }
    return render(request, 'core/industria/rastreio_producao.html', context)


@login_required(login_url='login')
@requer_rotina('rastreio_producao')
def rastreio_op(request, op_id):
    """Tela de rastreio de uma OP (aberta ao escanear o QR Code)."""
    garantir_setores_padrao()

    rastreio = RastreioOP.objects.filter(op_id=op_id).first()

    dados = None
    erro_conexao = None
    try:
        dados = _buscar_op_por_id(op_id)
    except Exception as exc:  # noqa: BLE001
        erro_conexao = str(exc)

    setor_atual = None
    proximo = None
    anterior = None
    if rastreio:
        setor_atual = SetorProducao.objects.filter(codigo=rastreio.setor_atual).first()
        proximo = _proximo_setor(rastreio.setor_atual, rastreio.tem_vidro)
        anterior = _setor_anterior(rastreio.setor_atual, rastreio.tem_vidro)

    movimentacoes = (
        rastreio.movimentacoes.select_related('usuario').all() if rastreio else []
    )

    # Dados exibidos no cabeçalho (prioriza o rastreio local; completa com o ERP)
    dados = dados or {}
    info = {
        'op_numero': (rastreio.op_numero if rastreio else '') or dados.get('NumeroDocumento') or str(op_id),
        'obra': (rastreio.obra if rastreio else '') or dados.get('ProjetoObra') or '—',
        'produto': (rastreio.produto if rastreio else '') or dados.get('Produto') or '—',
        'variante': (rastreio.variante if rastreio else '') or dados.get('Variante') or '—',
    }

    context = {
        'op_id': op_id,
        'rastreio': rastreio,
        'dados': dados,
        'info': info,
        'erro_conexao': erro_conexao,
        'setores': _setores_ativos(),
        'setor_atual': setor_atual,
        'proximo': proximo,
        'anterior': anterior,
        'movimentacoes': movimentacoes,
        'precisa_decidir_vidro': bool(
            rastreio
            and rastreio.setor_atual == 'mesa'
            and rastreio.tem_vidro is None
        ),
    }
    return render(request, 'core/industria/rastreio_op.html', context)


@login_required(login_url='login')
@requer_rotina('rastreio_producao')
def registrar_movimentacao(request, op_id):
    """Registra a passagem da OP por um setor (iniciar, avançar, retroceder)."""
    if request.method != 'POST':
        return redirect('rastreio_op', op_id=op_id)

    garantir_setores_padrao()
    acao = request.POST.get('acao', '').strip()
    observacao = request.POST.get('observacao', '').strip()

    rastreio = RastreioOP.objects.filter(op_id=op_id).first()

    # --- Iniciar rastreio (primeiro scan, na Separação) ---
    if acao == 'iniciar':
        if rastreio:
            messages.info(request, 'Esta OP já possui rastreio iniciado.')
            return redirect('rastreio_op', op_id=op_id)

        setores = _setores_ativos()
        if not setores:
            messages.error(request, 'Nenhum setor de produção configurado.')
            return redirect('rastreio_op', op_id=op_id)
        primeiro = setores[0]

        dados = None
        try:
            dados = _buscar_op_por_id(op_id)
        except Exception:  # noqa: BLE001
            dados = None
        dados = dados or {}

        rastreio = RastreioOP.objects.create(
            op_id=op_id,
            op_numero=dados.get('NumeroDocumento') or '',
            obra=dados.get('ProjetoObra') or '',
            produto=dados.get('Produto') or '',
            variante=dados.get('Variante') or '',
            setor_atual=primeiro.codigo,
            status='EM_PRODUCAO',
        )
        MovimentacaoOP.objects.create(
            rastreio=rastreio,
            setor=primeiro.codigo,
            setor_nome=primeiro.nome,
            usuario=request.user,
            observacao=observacao,
        )
        messages.success(request, f'Rastreio iniciado em {primeiro.nome}.')
        return redirect('rastreio_op', op_id=op_id)

    if not rastreio:
        messages.error(request, 'Rastreio não encontrado. Inicie o rastreio primeiro.')
        return redirect('rastreio_op', op_id=op_id)

    # --- Decisão de vidro (na Mesa) ---
    if acao in ('vidro_sim', 'vidro_nao'):
        rastreio.tem_vidro = (acao == 'vidro_sim')
        rastreio.save(update_fields=['tem_vidro'])

    # --- Retroceder (correção) ---
    if acao == 'retroceder':
        anterior = _setor_anterior(rastreio.setor_atual, rastreio.tem_vidro)
        if not anterior:
            messages.warning(request, 'Não há setor anterior no fluxo.')
            return redirect('rastreio_op', op_id=op_id)
        rastreio.setor_atual = anterior.codigo
        rastreio.status = 'EM_PRODUCAO'
        rastreio.save(update_fields=['setor_atual', 'status'])
        MovimentacaoOP.objects.create(
            rastreio=rastreio,
            setor=anterior.codigo,
            setor_nome=anterior.nome,
            usuario=request.user,
            observacao=observacao or 'Retorno (correção)',
        )
        messages.success(request, f'OP retornada para {anterior.nome}.')
        return redirect('rastreio_op', op_id=op_id)

    # --- Avançar ---
    if (
        rastreio.setor_atual == 'mesa'
        and rastreio.tem_vidro is None
        and acao == 'avancar'
    ):
        messages.warning(
            request,
            'Informe se a OP tem vidro antes de avançar da Mesa.',
        )
        return redirect('rastreio_op', op_id=op_id)

    proximo = _proximo_setor(rastreio.setor_atual, rastreio.tem_vidro)
    if not proximo:
        rastreio.status = 'CONCLUIDA'
        rastreio.save(update_fields=['status'])
        messages.success(request, 'OP concluída — chegou ao fim do fluxo.')
        return redirect('rastreio_op', op_id=op_id)

    rastreio.setor_atual = proximo.codigo
    rastreio.status = 'EM_PRODUCAO'
    rastreio.save(update_fields=['setor_atual', 'status'])
    MovimentacaoOP.objects.create(
        rastreio=rastreio,
        setor=proximo.codigo,
        setor_nome=proximo.nome,
        usuario=request.user,
        observacao=observacao,
    )
    messages.success(request, f'OP avançou para {proximo.nome}.')
    return redirect('rastreio_op', op_id=op_id)
