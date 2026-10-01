"""Rastreio de Produção — acompanha a OP pelos setores via código de barras.

Fluxo padrão:
    Separação → Usinagem → Mesa → (com vidro: Encaixilhamento) → Expedição

O operador escaneia o código de barras da OP em cada setor e o sistema
registra data, hora e usuário da passagem. A decisão "tem vidro?" acontece
na Mesa.

O leitor de código de barras funciona como teclado: digita o ID da OP e
pressiona Enter. A tela de escaneamento mantém o campo sempre focado.
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

MSG_MIGRATION = (
    'A rotina de rastreio ainda não foi instalada neste servidor. '
    'Execute "python manage.py migrate" para criar as tabelas.'
)


def _garantir_setores():
    """Garante os setores padrão sem quebrar a página se a migration não rodou.

    Retorna True se a tabela existe; False caso contrário (deploy sem migrate).
    """
    try:
        garantir_setores_padrao()
        return True
    except Exception:  # noqa: BLE001 — tabela ausente (migration pendente)
        return False


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


def _setor_do_usuario(user, setor_param=''):
    """Retorna o SetorProducao do usuário.

    Superusuário pode informar `setor_param` (código) para agir como um setor.
    """
    if user.is_superuser and setor_param:
        return SetorProducao.objects.filter(codigo=setor_param).first()
    perfil = getattr(user, 'perfil', None)
    if perfil and perfil.setor_producao_id:
        return perfil.setor_producao
    return None


def _pode_gerenciar(user):
    """Só gerência (ou superusuário) pode registrar movimentações."""
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfil', None)
    return bool(perfil and perfil.nivel_acesso == 'GERENCIA')


def _registrar_por_setor(request, op_id, setor_usuario, vidro=''):
    """Registra automaticamente a passagem da OP pelo setor do usuário.

    Retorna (erro, resultado, precisa_vidro):
      - erro: mensagem de erro (ou None)
      - resultado: dict com dados do registro (ou None)
      - precisa_vidro: True se o setor Mesa precisa decidir sobre vidro
    """
    rastreio = RastreioOP.objects.filter(op_id=op_id).first()
    codigo_setor = setor_usuario.codigo

    # --- OP ainda não iniciada: só o Estoque pode iniciar ---
    if not rastreio:
        primeiro = _setores_ativos()[0] if _setores_ativos() else None
        if not primeiro or codigo_setor != primeiro.codigo:
            return (
                f'A OP ainda não foi iniciada. Ela precisa ser lida primeiro '
                f'pelo setor de {primeiro.nome if primeiro else "Estoque"}.',
                None,
                False,
            )

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
            setor_atual=codigo_setor,
            status='EM_PRODUCAO',
        )
        MovimentacaoOP.objects.create(
            rastreio=rastreio,
            setor=codigo_setor,
            setor_nome=setor_usuario.nome,
            usuario=request.user,
            observacao='Início do rastreio',
        )
        return (None, {'rastreio': rastreio, 'setor': setor_usuario, 'iniciou': True}, False)

    # --- OP já concluída ---
    if rastreio.concluida:
        return ('Esta OP já foi concluída e não pode receber novas leituras.', None, False)

    # --- Decisão de vidro pendente (OP parada na Mesa) ---
    if rastreio.setor_atual == 'mesa' and rastreio.tem_vidro is None:
        if vidro in ('sim', 'nao'):
            rastreio.tem_vidro = (vidro == 'sim')
            rastreio.save(update_fields=['tem_vidro'])
            return (
                None,
                {'rastreio': rastreio, 'setor': setor_usuario, 'iniciou': False,
                 'decisao_vidro': rastreio.tem_vidro},
                False,
            )
        # Ainda não decidiu: pergunta antes de qualquer avanço
        return (None, None, True)

    # --- Já está neste setor ---
    if rastreio.setor_atual == codigo_setor:
        return (
            f'A OP já está registrada no setor de {setor_usuario.nome}.',
            None,
            False,
        )

    # --- Valida se é o próximo setor esperado ---
    proximo = _proximo_setor(rastreio.setor_atual, rastreio.tem_vidro)
    if not proximo:
        return ('Não há próximo setor no fluxo.', None, False)

    if proximo.codigo != codigo_setor:
        return (
            f'Fora de ordem. A OP está em {rastreio.setor_atual_nome} e o próximo '
            f'setor é {proximo.nome}. O setor de {setor_usuario.nome} só pode ler '
            f'após essa etapa.',
            None,
            False,
        )

    # --- Avança ---
    rastreio.setor_atual = codigo_setor
    # Se não há próximo setor, a OP é concluída ao chegar no último
    if _proximo_setor(codigo_setor, rastreio.tem_vidro) is None:
        rastreio.status = 'CONCLUIDA'
    else:
        rastreio.status = 'EM_PRODUCAO'
    rastreio.save(update_fields=['setor_atual', 'status'])
    MovimentacaoOP.objects.create(
        rastreio=rastreio,
        setor=codigo_setor,
        setor_nome=setor_usuario.nome,
        usuario=request.user,
    )

    # Se acabou de chegar na Mesa, pergunta sobre o vidro imediatamente
    if codigo_setor == 'mesa' and rastreio.tem_vidro is None:
        return (None, None, True)

    return (None, {'rastreio': rastreio, 'setor': setor_usuario, 'iniciou': False}, False)


@login_required(login_url='login')
@requer_rotina('rastreio_producao')
def rastreio_producao(request):
    """Painel com todas as OPs em rastreio."""
    if not _garantir_setores():
        messages.error(request, MSG_MIGRATION)
        return render(request, 'core/industria/rastreio_producao.html', {
            'page_obj': None,
            'rastreios': [],
            'setores': [],
            'filtros': request.GET,
            'querystring': '',
            'migration_pendente': True,
        })

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
    """Tela de rastreio de uma OP (aberta ao escanear o código de barras)."""
    if not _garantir_setores():
        messages.error(request, MSG_MIGRATION)
        return render(request, 'core/industria/rastreio_op.html', {
            'op_id': op_id,
            'rastreio': None,
            'dados': {},
            'info': {
                'op_numero': str(op_id),
                'obra': '—',
                'produto': '—',
                'variante': '—',
            },
            'erro_conexao': None,
            'setores': [],
            'setor_atual': None,
            'proximo': None,
            'anterior': None,
            'movimentacoes': [],
            'precisa_decidir_vidro': False,
            'migration_pendente': True,
        })

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

    if not _garantir_setores():
        messages.error(request, MSG_MIGRATION)
        return redirect('rastreio_op', op_id=op_id)

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


@login_required(login_url='login')
@requer_rotina('rastreio_producao')
def escanear(request):
    """Tela de escaneamento: o leitor digita o ID da OP e pressiona Enter.

    O registro é AUTOMÁTICO: o setor do usuário logado define a etapa.
    - Só gerência (ou superusuário) pode registrar.
    - O Estoque inicia o rastreio.
    - Cada setor só avança se for o próximo do fluxo.
    - Na Mesa, se ainda não decidiu sobre vidro, pergunta antes de avançar.
    """
    if not _garantir_setores():
        messages.error(request, MSG_MIGRATION)

    codigo = request.GET.get('codigo', '').strip()
    vidro = request.GET.get('vidro', '').strip()
    setor_param = request.GET.get('setor', '').strip()
    erro = None
    resultado = None
    precisa_vidro = False
    op_id_pendente = None

    if codigo:
        numeros = ''.join(ch for ch in codigo if ch.isdigit())
        if not numeros:
            erro = f'Código inválido: "{codigo}".'
        elif not _pode_gerenciar(request.user):
            erro = (
                'Apenas usuários de nível Gerência podem registrar a '
                'movimentação da OP.'
            )
        else:
            setor_usuario = _setor_do_usuario(request.user, setor_param)
            if not setor_usuario:
                erro = (
                    'Seu usuário não está vinculado a um setor de produção. '
                    'Peça ao administrador para definir o setor no seu perfil.'
                )
            else:
                op_id = int(numeros)
                erro, resultado, precisa_vidro = _registrar_por_setor(
                    request, op_id, setor_usuario, vidro
                )
                if precisa_vidro:
                    op_id_pendente = op_id

    context = {
        'codigo': codigo,
        'erro': erro,
        'resultado': resultado,
        'precisa_vidro': precisa_vidro,
        'op_id_pendente': op_id_pendente,
        'setor_usuario': _setor_do_usuario(request.user, setor_param),
        'pode_gerenciar': _pode_gerenciar(request.user),
        'setores': _setores_ativos(),
        'setor_param': setor_param,
    }
    return render(request, 'core/industria/escanear.html', context)
