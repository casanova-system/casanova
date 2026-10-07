"""Rastreio de Produção — acompanha a OP pelos setores via QR Code.

Fluxo padrão:
    Estoque → Separação → Corte → Usinagem → Mesa → (com vidro: Encaixilhamento) → Expedição

O operador escaneia o QR Code da OP em cada setor e o sistema
registra data, hora e usuário da passagem. A decisão "tem vidro?" acontece
na Mesa.

O leitor de QR Code funciona como teclado: digita o ID da OP e
pressiona Enter. A tela de escaneamento mantém o campo sempre focado.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
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

logger = logging.getLogger(__name__)

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

        # Busca dados da ObraOP
        obra_op = _buscar_obra_op_por_id(op_id)
        if obra_op:
            dados = {
                'NumeroDocumento': obra_op.codigo_documento or obra_op.codigo_esquadria,
                'ProjetoObra': obra_op.obra.codigo if obra_op.obra else '',
                'Produto': obra_op.descricao or '',
                'Variante': obra_op.codigo_esquadria or '',
            }
        else:
            dados = None
            try:
                dados = _buscar_op_por_id(op_id)
            except Exception:  # noqa: BLE001
                dados = None
        dados = dados or {}

        with transaction.atomic():
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

        logger.info(
            'Rastreio iniciado — OP %s pelo usuário %s no setor %s',
            op_id, request.user.username, setor_usuario.nome,
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
            logger.info(
                'Decisão de vidro — OP %s: %s (usuário %s)',
                op_id, 'SIM' if rastreio.tem_vidro else 'NÃO', request.user.username,
            )
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
    with transaction.atomic():
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

    logger.info(
        'OP %s avançou para %s (usuário %s)',
        op_id, setor_usuario.nome, request.user.username,
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

        # Busca dados da ObraOP
        obra_op = _buscar_obra_op_por_id(op_id)
        if obra_op:
            dados = {
                'NumeroDocumento': obra_op.codigo_documento or obra_op.codigo_esquadria,
                'ProjetoObra': obra_op.obra.codigo if obra_op.obra else '',
                'Produto': obra_op.descricao or '',
                'Variante': obra_op.codigo_esquadria or '',
            }
        else:
            dados = None
            try:
                dados = _buscar_op_por_id(op_id)
            except Exception:  # noqa: BLE001
                dados = None
        dados = dados or {}

        with transaction.atomic():
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

        logger.info(
            'Rastreio iniciado (manual) — OP %s pelo usuário %s no setor %s',
            op_id, request.user.username, primeiro.nome,
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
        logger.info(
            'Decisão de vidro (manual) — OP %s: %s (usuário %s)',
            op_id, 'SIM' if rastreio.tem_vidro else 'NÃO', request.user.username,
        )

    # --- Retroceder (correção) ---
    if acao == 'retroceder':
        anterior = _setor_anterior(rastreio.setor_atual, rastreio.tem_vidro)
        if not anterior:
            messages.warning(request, 'Não há setor anterior no fluxo.')
            return redirect('rastreio_op', op_id=op_id)

        with transaction.atomic():
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

        logger.info(
            'OP %s retornou para %s (usuário %s)',
            op_id, anterior.nome, request.user.username,
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
        with transaction.atomic():
            rastreio.status = 'CONCLUIDA'
            rastreio.save(update_fields=['status'])
        messages.success(request, 'OP concluída — chegou ao fim do fluxo.')
        return redirect('rastreio_op', op_id=op_id)

    with transaction.atomic():
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

    logger.info(
        'OP %s avançou para %s (usuário %s)',
        op_id, proximo.nome, request.user.username,
    )
    messages.success(request, f'OP avançou para {proximo.nome}.')
    return redirect('rastreio_op', op_id=op_id)


def _extrair_op_id_do_qr(codigo):
    """Extrai o ID da OP do conteúdo do QR Code ou do código digitado.

    Aceita:
    - JSON do QR Code (ex: {"id": 21, "op": "J01", ...})
    - ID numérico (ex: 21)
    - Código do documento (ex: J01, J02, etc.)
    """
    import json
    import re

    codigo = codigo.strip()

    # Tenta fazer parse do JSON
    try:
        dados = json.loads(codigo)
        if isinstance(dados, dict) and 'id' in dados:
            return int(dados['id'])
        if isinstance(dados, dict) and 'op' in dados:
            # Se tiver o campo 'op', tenta extrair números
            numeros = ''.join(ch for ch in str(dados['op']) if ch.isdigit())
            if numeros:
                return int(numeros)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Verifica se é um código de documento (ex: J01, J02, etc.)
    match = re.match(r'^([A-Za-z]+)(\d+)$', codigo)
    if match:
        # Busca ObraOP pelo código do documento
        from core.models import ObraOP
        obra_op = ObraOP.objects.filter(codigo_documento=codigo).first()
        if obra_op:
            return obra_op.pk

    # Fallback: extrai números do código (compatibilidade com ID numérico)
    numeros = ''.join(ch for ch in codigo if ch.isdigit())
    if numeros:
        return int(numeros)

    return None


def _buscar_obra_op_por_id(obra_op_id):
    """Busca uma ObraOP pelo ID."""
    from core.models import ObraOP
    return ObraOP.objects.filter(pk=obra_op_id).first()


@login_required(login_url='login')
@requer_rotina('producao')
def producao(request):
    """Tela de acompanhamento da OP na indústria.

    Permite escanear o QR Code ou digitar o ID da OP para visualizar
    o andamento da produção em tempo real.
    """
    codigo = request.GET.get('codigo', '').strip()
    erro = None
    rastreio = None
    dados = None
    info = None
    movimentacoes = []
    setor_atual = None
    proximo = None
    anterior = None
    precisa_decidir_vidro = False

    if codigo:
        op_id = _extrair_op_id_do_qr(codigo)
        if not op_id:
            erro = f'Código inválido: "{codigo}".'
        else:
            # Busca dados da ObraOP
            obra_op = _buscar_obra_op_por_id(op_id)
            if not obra_op:
                erro = f'OP {op_id} não encontrada.'
            else:
                dados = {
                    'NumeroDocumento': obra_op.codigo_documento or obra_op.codigo_esquadria,
                    'ProjetoObra': obra_op.obra.codigo if obra_op.obra else '',
                    'Produto': obra_op.descricao or '',
                    'Variante': obra_op.codigo_esquadria or '',
                }

                info = {
                    'op_numero': obra_op.codigo_documento or obra_op.codigo_esquadria,
                    'obra': obra_op.obra.codigo if obra_op.obra else '—',
                    'produto': obra_op.descricao or '—',
                    'variante': obra_op.codigo_esquadria or '—',
                }

                # Verifica se já existe rastreio
                rastreio = RastreioOP.objects.filter(op_id=op_id).first()
                if rastreio:
                    setor_atual = SetorProducao.objects.filter(codigo=rastreio.setor_atual).first()
                    proximo = _proximo_setor(rastreio.setor_atual, rastreio.tem_vidro)
                    anterior = _setor_anterior(rastreio.setor_atual, rastreio.tem_vidro)
                    movimentacoes = rastreio.movimentacoes.select_related('usuario').all()
                    precisa_decidir_vidro = bool(
                        rastreio.setor_atual == 'mesa' and rastreio.tem_vidro is None
                    )
                else:
                    # OP ainda não iniciada no rastreio
                    setor_atual = None
                    proximo = None
                    anterior = None
                    movimentacoes = []
                    precisa_decidir_vidro = False

    context = {
        'codigo': codigo,
        'erro': erro,
        'rastreio': rastreio,
        'dados': dados,
        'info': info,
        'setores': _setores_ativos(),
        'setor_atual': setor_atual,
        'proximo': proximo,
        'anterior': anterior,
        'movimentacoes': movimentacoes,
        'precisa_decidir_vidro': precisa_decidir_vidro,
    }
    return render(request, 'core/industria/producao.html', context)


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
        # Tenta extrair o ID do JSON do QR Code
        op_id = _extrair_op_id_do_qr(codigo)
        if not op_id:
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
                # Busca a ObraOP pelo ID do QR Code
                obra_op = _buscar_obra_op_por_id(op_id)
                if not obra_op:
                    erro = f'OP não encontrada para o ID {op_id}.'
                else:
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
