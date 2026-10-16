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
from django.utils import timezone
from django.db.models import Avg, Count, Q, F, ExpressionWrapper, DurationField
from datetime import timedelta
from core.views.ordem_producao import _buscar_op_por_id
from core.views.permissao import requer_rotina
from core.producao import calcular_minutos_producao

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


def _pode_registrar(user):
    """Quem pode registrar movimentação na tela de Produção.

    O operador de chão de fábrica (peão) tem um setor de produção vinculado no
    perfil — é ele quem bipa a peça. Gerência e superusuário também podem.
    """
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfil', None)
    if not perfil:
        return False
    if perfil.nivel_acesso == 'GERENCIA':
        return True
    return bool(perfil.setor_producao_id)


ICONES_SETOR = {
    'estoque': 'fa-warehouse',
    'separacao': 'fa-boxes-stacked',
    'corte': 'fa-scissors',
    'usinagem': 'fa-gears',
    'mesa': 'fa-table-cells',
    'encaixilhamento': 'fa-border-all',
    'expedicao': 'fa-truck',
}


def _minutos_para_texto(minutos):
    """Formata minutos para '2h 30min' / '45min'. Usado nos gráficos."""
    if not minutos or minutos <= 0:
        return '—'
    if minutos < 60:
        return f'{int(round(minutos))}min'
    horas = int(minutos // 60)
    mins = int(round(minutos % 60))
    return f'{horas}h {mins}min' if mins else f'{horas}h'


def _tem_filtro_ativo(get_params):
    """True se algum filtro está aplicado (para destacar a barra na tela)."""
    return any(
        (get_params.get(chave) or '').strip()
        for chave in ('q', 'setor', 'status', 'vidro', 'obra')
    )


def _filtrar_rastreios(queryset, get_params):
    """Aplica os filtros da barra sobre um queryset de RastreioOP.

    Fonte única de verdade: a mesma função alimenta KPIs, os três gráficos e a
    tabela. Antes cada bloco montava seu próprio queryset e os gráficos ficavam
    presos ao banco inteiro — filtrar por setor não mudava nada neles.
    """
    q = (get_params.get('q') or '').strip()
    setor = (get_params.get('setor') or '').strip()
    status = (get_params.get('status') or '').strip()
    vidro = (get_params.get('vidro') or '').strip()
    obra = (get_params.get('obra') or '').strip()

    if q:
        queryset = queryset.filter(
            Q(op_numero__icontains=q)
            | Q(obra__icontains=q)
            | Q(produto__icontains=q)
            | Q(variante__icontains=q)
        )
    if setor:
        queryset = queryset.filter(setor_atual=setor)
    if status:
        queryset = queryset.filter(status=status)
    if vidro == 'sim':
        queryset = queryset.filter(tem_vidro=True)
    elif vidro == 'nao':
        queryset = queryset.filter(tem_vidro=False)
    elif vidro == 'a_definir':
        queryset = queryset.filter(tem_vidro__isnull=True)
    if obra:
        queryset = queryset.filter(obra=obra)

    return queryset


def _montar_fluxo(rastreio):
    """Monta a trilha do fluxo produtivo com o estado de cada setor.

    Devolve uma lista de dicts (codigo, nome, icone, estado, tempo) pronta para
    o template — evita lógica condicional pesada dentro do HTML.
    estado: 'concluido' | 'atual' | 'pendente'
    """
    setores = _setores_ativos()
    tem_vidro = rastreio.tem_vidro if rastreio else None

    # Setores que fazem parte do fluxo desta OP (pula Encaixilhamento sem vidro)
    ativos = [
        s for s in setores
        if not (s.requer_vidro and tem_vidro is False)
    ]
    codigos = [s.codigo for s in ativos]
    atual = rastreio.setor_atual if rastreio else ''
    idx_atual = codigos.index(atual) if atual in codigos else -1

    fluxo = []
    for pos, setor in enumerate(ativos):
        tempo = rastreio.tempo_no_setor_formatado(setor.codigo) if rastreio else '—'
        if not rastreio:
            estado = 'pendente'
        elif rastreio.concluida:
            estado = 'concluido'
        elif setor.codigo == atual:
            estado = 'atual'
        elif idx_atual >= 0 and pos < idx_atual:
            estado = 'concluido'
        else:
            estado = 'pendente'
        fluxo.append({
            'codigo': setor.codigo,
            'nome': setor.nome,
            'icone': ICONES_SETOR.get(setor.codigo, 'fa-industry'),
            'estado': estado,
            'tempo': tempo if tempo != '—' else '',
        })
    return fluxo


def _limite_quantidade(rastreio):
    """Quantidade maxima que a OP comporta (None = sem limite conhecido)."""
    total = getattr(rastreio, 'quantidade_total', None)
    return total if total else None


def _validar_quantidade(rastreio, qtd):
    """Confere a quantidade informada contra o total da OP.

    O operador nao pode informar que produziu mais pecas do que a OP pede.
    Um erro de digitacao (55 em vez de 5) liberava o setor com um numero
    impossivel e o rastreio ficava com quantidade maior que a OP inteira.

    Retorna a mensagem de erro, ou None se estiver dentro do limite.
    """
    if qtd is None:
        return None
    limite = _limite_quantidade(rastreio)
    if limite and qtd > limite:
        plural = 'pecas' if limite != 1 else 'peca'
        return (
            f'Quantidade maior que a OP: ela pede {limite} {plural} '
            f'e voce informou {qtd}. Corrija para no maximo {limite}.'
        )
    return None


def _registrar_por_setor(request, op_id, setor_usuario, vidro='', observacao_saida='',
                         quantidade_produzida=None, pedir_quantidade=True):
    """Registra automaticamente a passagem da OP pelo setor do usuário.

    Lógica de DUPLO BIP:
    - 1º bip (entrada): operador do setor bipa para iniciar o trabalho
    - 2º bip (saída): operador do setor bipa novamente para finalizar e liberar
    - O próximo setor só pode receber após o setor anterior ter bipado a saída

    Retorna (erro, resultado, precisa_vidro):
      - erro: mensagem de erro (ou None)
      - resultado: dict com dados do registro (ou None)
      - precisa_vidro: True se o setor Mesa precisa decidir sobre vidro

    `pedir_quantidade`:
      - True (padrão)  — no 2º bip sem quantidade, devolve o formulário para o
        operador informar quantas peças produziu (tela "Escanear OP").
      - False          — no 2º bip libera o setor direto, sem perguntar nada
        (tela "Produção", onde a quantidade não é coletada).
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

        # Busca quantidade total da OP na ObraOP
        quantidade_total = None
        if obra_op:
            quantidade_total = obra_op.quantidade

        with transaction.atomic():
            rastreio = RastreioOP.objects.create(
                op_id=op_id,
                op_numero=dados.get('NumeroDocumento') or '',
                obra=dados.get('ProjetoObra') or '',
                produto=dados.get('Produto') or '',
                variante=dados.get('Variante') or '',
                setor_atual=codigo_setor,
                status='EM_PRODUCAO',
                aguardando_saida=False,
                quantidade_total=quantidade_total,
            )
            MovimentacaoOP.objects.create(
                rastreio=rastreio,
                setor=codigo_setor,
                setor_nome=setor_usuario.nome,
                usuario_entrada=request.user,
                observacao_entrada='Início do rastreio',
                data_entrada=timezone.now(),
            )

        logger.info(
            'Rastreio iniciado — OP %s pelo usuário %s no setor %s (1º bip)',
            op_id, request.user.username, setor_usuario.nome,
        )
        return (None, {'rastreio': rastreio, 'setor': setor_usuario, 'iniciou': True, 'bip': 'entrada'}, False)

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

    # --- OP está no MESMO setor do usuário: verificar se é 1º ou 2º bip ---
    if rastreio.setor_atual == codigo_setor:
        # Se já bipou a entrada e NÃO bipou a saída → este é o 2º bip (saída)
        if not rastreio.aguardando_saida:
            # Sem a quantidade informada: na tela de Produção a saída é
            # registrada direto (a quantidade não é coletada lá). Na tela
            # "Escanear OP" devolve o formulário, como antes.
            if quantidade_produzida is None and pedir_quantidade:
                return (
                    None,
                    {'rastreio': rastreio, 'setor': setor_usuario,
                     'iniciou': False, 'bip': 'entrada', 'precisa_quantidade': True},
                    False,
                )

            # Nao deixa informar mais pecas do que a OP pede
            erro_qtd = _validar_quantidade(rastreio, quantidade_produzida)
            if erro_qtd:
                return (erro_qtd, None, False)

            with transaction.atomic():
                update_fields = {
                    'data_saida': timezone.now(),
                    'usuario_saida': request.user,
                    'observacao_saida': observacao_saida,
                }
                if quantidade_produzida is not None:
                    update_fields['quantidade_produzida'] = quantidade_produzida

                MovimentacaoOP.objects.filter(
                    rastreio=rastreio,
                    setor=codigo_setor,
                    data_saida__isnull=True,
                ).update(**update_fields)

                rastreio.aguardando_saida = True
                rastreio.save(update_fields=['aguardando_saida'])

            logger.info(
                'OP %s liberada do setor %s (2º bip) — usuário %s',
                op_id, setor_usuario.nome, request.user.username,
            )
            return (
                None,
                {'rastreio': rastreio, 'setor': setor_usuario, 'iniciou': False, 'bip': 'saida'},
                False,
            )
        else:
            # Já bipou a saída, está aguardando o próximo setor receber
            return (
                f'A OP já foi liberada do setor de {setor_usuario.nome}. '
                f'Aguardando o próximo setor receber.',
                None,
                False,
            )

    # --- OP está em outro setor: verificar se pode receber ---
    # O setor atual já bipou a saída? Se não, o próximo setor não pode receber
    if not rastreio.aguardando_saida:
        return (
            f'A OP ainda está em {rastreio.setor_atual_nome}. '
            f'O operador precisa bipar a saída antes de liberar para o próximo setor.',
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

    # --- Receber no próximo setor (1º bip) ---
    with transaction.atomic():
        rastreio.setor_atual = codigo_setor
        rastreio.aguardando_saida = False
        # Se não há próximo setor, a OP é concluída ao chegar no último
        if _proximo_setor(codigo_setor, rastreio.tem_vidro) is None:
            rastreio.status = 'CONCLUIDA'
        else:
            rastreio.status = 'EM_PRODUCAO'
        rastreio.save(update_fields=['setor_atual', 'aguardando_saida', 'status'])
        MovimentacaoOP.objects.create(
            rastreio=rastreio,
            setor=codigo_setor,
            setor_nome=setor_usuario.nome,
            usuario_entrada=request.user,
            observacao_entrada='Recebimento no setor',
            data_entrada=timezone.now(),
        )

    logger.info(
        'OP %s recebida no setor %s (1º bip) — usuário %s',
        op_id, setor_usuario.nome, request.user.username,
    )

    # Se acabou de chegar na Mesa, pergunta sobre o vidro imediatamente
    if codigo_setor == 'mesa' and rastreio.tem_vidro is None:
        return (None, None, True)

    return (None, {'rastreio': rastreio, 'setor': setor_usuario, 'iniciou': False, 'bip': 'entrada'}, False)

@login_required(login_url='login')
@requer_rotina('rastreio_producao')
def rastreio_producao(request):
    """Painel com todas as OPs em rastreio.

    Filtros: a barra de filtros alimenta TUDO — KPIs, os três gráficos e a
    tabela. Antes os gráficos eram calculados sobre o banco inteiro, então
    filtrar não mudava nada neles.

    Cada gráfico ainda tem seus próprios controles (métrica, agrupamento,
    janela de dias), resolvidos no navegador para trocar sem recarregar.
    """
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

    setores = _setores_ativos()

    # ------------------------------------------------------------------
    # Base: todos os rastreios. Os filtros abaixo reduzem este conjunto e o
    # resultado alimenta KPIs, gráficos e tabela (antes só a tabela).
    # ------------------------------------------------------------------
    rastreios = _filtrar_rastreios(RastreioOP.objects.all(), request.GET)

    paginator = Paginator(rastreios, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)

    # ------------------------------------------------------------------
    # KPIs — calculados sobre o conjunto filtrado
    # ------------------------------------------------------------------
    rastreios_ativos = rastreios.filter(status='EM_PRODUCAO')
    rastreios_concluidos = rastreios.filter(status='CONCLUIDA')

    ops_sem_problema = ops_atencao = ops_critico = 0
    for r in rastreios_ativos:
        if r.status_tempo == 'CRITICO':
            ops_critico += 1
        elif r.status_tempo == 'ATENCAO':
            ops_atencao += 1
        else:
            ops_sem_problema += 1

    # ------------------------------------------------------------------
    # Gráfico 1 — Tempo por setor (média e total, em horário útil)
    #
    # Usa `calcular_minutos_producao`, o mesmo cálculo do resto do sistema:
    # conta só o horário de fábrica (7h-11h, 12h12-17h; sexta até 16h) e
    # ignora noites, almoço e fins de semana. Antes o gráfico subtraía os
    # timestamps direto, então uma OP que ficou das 17h de sexta às 7h de
    # segunda aparecia com ~3.800 min de "trabalho" que nunca existiu.
    # ------------------------------------------------------------------
    movimentacoes = MovimentacaoOP.objects.filter(
        rastreio__in=rastreios,
        data_entrada__isnull=False,
    )
    movs_por_setor = {}
    for mov in movimentacoes.only('setor', 'data_entrada', 'data_saida'):
        minutos = calcular_minutos_producao(mov.data_entrada, mov.data_saida)
        if minutos <= 0:
            continue
        acumulado = movs_por_setor.setdefault(mov.setor, {'soma': 0.0, 'n': 0})
        acumulado['soma'] += minutos
        acumulado['n'] += 1

    tempo_setores_medio = []
    tempo_setores_total = []
    for setor in setores:
        dados = movs_por_setor.get(setor.codigo)
        if dados:
            media = dados['soma'] / dados['n']
            total = dados['soma']
        else:
            media = total = 0
        tempo_setores_medio.append({
            'nome': setor.nome,
            'valor': round(media, 1),
            'texto': _minutos_para_texto(media),
        })
        tempo_setores_total.append({
            'nome': setor.nome,
            'valor': round(total, 1),
            'texto': _minutos_para_texto(total),
        })

    # ------------------------------------------------------------------
    # Gráfico 2 — Distribuição (por setor atual, status ou vidro)
    # ------------------------------------------------------------------
    def _distribuicao(rotulos):
        """Conta o conjunto filtrado para cada rótulo e descarta os zeros."""
        itens = []
        for chave, nome in rotulos:
            if chave is None:
                qtd = rastreios.filter(tem_vidro__isnull=True).count()
            elif chave in ('SIM', 'NAO'):
                qtd = rastreios.filter(tem_vidro=(chave == 'SIM')).count()
            elif chave in ('EM_PRODUCAO', 'CONCLUIDA'):
                qtd = rastreios.filter(status=chave).count()
            else:
                qtd = rastreios.filter(setor_atual=chave).count()
            if qtd:
                itens.append({'nome': nome, 'quantidade': qtd})
        return itens

    dist_setor = _distribuicao([(s.codigo, s.nome) for s in setores])
    dist_status = _distribuicao([
        ('EM_PRODUCAO', 'Em Produção'),
        ('CONCLUIDA', 'Concluída'),
    ])
    dist_vidro = _distribuicao([
        ('SIM', 'Com vidro'),
        ('NAO', 'Sem vidro'),
        (None, 'A definir'),
    ])

    # ------------------------------------------------------------------
    # Gráfico 3 — Concluídas por dia (janelas de 7, 30 e 90 dias)
    # ------------------------------------------------------------------
    def _concluidas_por_dia(dias):
        from datetime import date, timedelta as _td
        hoje = date.today()
        # Uma consulta só: agrupa por dia e depois preenche os vazios.
        contagem = (
            rastreios_concluidos
            .filter(atualizado_em__date__gte=hoje - _td(days=dias - 1))
            .values_list('atualizado_em__date', flat=True)
        )
        por_dia = {}
        for d in contagem:
            por_dia[d] = por_dia.get(d, 0) + 1
        serie = []
        for i in range(dias - 1, -1, -1):
            dia = hoje - _td(days=i)
            serie.append({
                'dia': dia.strftime('%d/%m'),
                'quantidade': por_dia.get(dia, 0),
            })
        return serie

    # ------------------------------------------------------------------
    # Opções de filtro (obras existentes, período selecionado)
    # ------------------------------------------------------------------
    obras = list(
        RastreioOP.objects.exclude(obra='')
        .values_list('obra', flat=True)
        .distinct()
        .order_by('obra')
    )

    context = {
        'page_obj': page_obj,
        'rastreios': page_obj.object_list,
        'setores': setores,
        'obras': obras,
        'filtros': request.GET,
        'querystring': params.urlencode(),
        'tem_filtro_ativo': _tem_filtro_ativo(request.GET),
        'kpis': {
            'total_ativas': rastreios_ativos.count(),
            'total_concluidas': rastreios_concluidos.count(),
            'sem_problema': ops_sem_problema,
            'atencao': ops_atencao,
            'critico': ops_critico,
        },
        'tempo_setores_medio': tempo_setores_medio,
        'tempo_setores_total': tempo_setores_total,
        'dist_setor': dist_setor,
        'dist_status': dist_status,
        'dist_vidro': dist_vidro,
        'concluidas_7': _concluidas_por_dia(7),
        'concluidas_30': _concluidas_por_dia(30),
        'concluidas_90': _concluidas_por_dia(90),
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
        rastreio.movimentacoes.select_related('usuario_entrada', 'usuario_saida').all() if rastreio else []
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
        'fluxo': _montar_fluxo(rastreio),
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
    """Registra a passagem da OP por um setor (iniciar, saída, avançar, retroceder).

    Lógica de DUPLO BIP:
    - iniciar: cria o rastreio (1º bip no Estoque)
    - saída: operador bipa para finalizar e liberar o setor (2º bip)
    - avançar: próximo setor bipa para receber (1º bip no próximo setor)
    - retroceder: volta para setor anterior (correção)
    """
    if request.method != 'POST':
        return redirect('rastreio_op', op_id=op_id)

    if not _garantir_setores():
        messages.error(request, MSG_MIGRATION)
        return redirect('rastreio_op', op_id=op_id)

    acao = request.POST.get('acao', '').strip()
    # Observação de saída/B.O. — apenas quando o operário finaliza o trabalho
    observacao_saida = request.POST.get('observacao', '').strip()
    # Quantidade produzida no setor (informada pelo operário no 2º bip)
    quantidade_produzida = request.POST.get('quantidade_produzida', '').strip()

    rastreio = RastreioOP.objects.filter(op_id=op_id).first()

    # --- Iniciar rastreio (primeiro scan, no Estoque) ---
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

        # Busca quantidade total da OP na ObraOP
        quantidade_total = None
        if obra_op:
            quantidade_total = obra_op.quantidade

        with transaction.atomic():
            rastreio = RastreioOP.objects.create(
                op_id=op_id,
                op_numero=dados.get('NumeroDocumento') or '',
                obra=dados.get('ProjetoObra') or '',
                produto=dados.get('Produto') or '',
                variante=dados.get('Variante') or '',
                setor_atual=primeiro.codigo,
                status='EM_PRODUCAO',
                aguardando_saida=False,
                quantidade_total=quantidade_total,
            )
            MovimentacaoOP.objects.create(
                rastreio=rastreio,
                setor=primeiro.codigo,
                setor_nome=primeiro.nome,
                usuario_entrada=request.user,
                observacao_entrada='Início do rastreio',
                data_entrada=timezone.now(),
            )

        logger.info(
            'Rastreio iniciado (manual) — OP %s pelo usuário %s no setor %s',
            op_id, request.user.username, primeiro.nome,
        )
        messages.success(request, f'Rastreio iniciado em {primeiro.nome} (1º bip).')
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

    # --- Saída do setor (2º bip) ---
    if acao == 'saida':
        if rastreio.aguardando_saida:
            messages.warning(request, 'A OP já foi liberada deste setor.')
            return redirect('rastreio_op', op_id=op_id)

        # Validar quantidade produzida (opcional, mas recomendada)
        qtd_produzida = None
        if quantidade_produzida:
            try:
                qtd_produzida = int(quantidade_produzida)
                if qtd_produzida < 0:
                    raise ValueError
            except ValueError:
                messages.error(request, 'Quantidade produzida inválida.')
                return redirect('rastreio_op', op_id=op_id)

        with transaction.atomic():
            MovimentacaoOP.objects.filter(
                rastreio=rastreio,
                setor=rastreio.setor_atual,
                data_saida__isnull=True,
            ).update(
                data_saida=timezone.now(),
                quantidade_produzida=qtd_produzida,
            )

            rastreio.aguardando_saida = True
            rastreio.save(update_fields=['aguardando_saida'])

        logger.info(
            'OP %s liberada do setor %s (2º bip) — usuário %s, qtd: %s',
            op_id, rastreio.setor_atual_nome, request.user.username,
            qtd_produzida if qtd_produzida else 'N/A',
        )
        if qtd_produzida is not None:
            messages.success(
                request,
                f'OP liberada do setor {rastreio.setor_atual_nome} (2º bip). '
                f'Produzidas: {qtd_produzida} de {rastreio.quantidade_total or "?"} peças.',
            )
        else:
            messages.success(request, f'OP liberada do setor {rastreio.setor_atual_nome} (2º bip).')
        return redirect('rastreio_op', op_id=op_id)

    # --- Retroceder (correção) ---
    if acao == 'retroceder':
        anterior = _setor_anterior(rastreio.setor_atual, rastreio.tem_vidro)
        if not anterior:
            messages.warning(request, 'Não há setor anterior no fluxo.')
            return redirect('rastreio_op', op_id=op_id)

        with transaction.atomic():
            rastreio.setor_atual = anterior.codigo
            rastreio.status = 'EM_PRODUCAO'
            rastreio.aguardando_saida = False
            rastreio.save(update_fields=['setor_atual', 'status', 'aguardando_saida'])
            MovimentacaoOP.objects.create(
                rastreio=rastreio,
                setor=anterior.codigo,
                setor_nome=anterior.nome,
                usuario_entrada=request.user,
                observacao_entrada='Retorno (correção)',
                data_entrada=timezone.now(),
            )

        logger.info(
            'OP %s retornou para %s (usuário %s)',
            op_id, anterior.nome, request.user.username,
        )
        messages.success(request, f'OP retornada para {anterior.nome}.')
        return redirect('rastreio_op', op_id=op_id)

    # --- Avançar (1º bip no próximo setor) ---
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

    # Verifica se o setor atual já bipou a saída
    if not rastreio.aguardando_saida:
        messages.warning(
            request,
            f'A OP ainda está em {rastreio.setor_atual_nome}. '
            f'Bipe a saída antes de avançar.',
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
        rastreio.aguardando_saida = False
        rastreio.save(update_fields=['setor_atual', 'status', 'aguardando_saida'])
        MovimentacaoOP.objects.create(
            rastreio=rastreio,
            setor=proximo.codigo,
            setor_nome=proximo.nome,
            usuario_entrada=request.user,
            observacao_entrada='Recebimento no setor',
            data_entrada=timezone.now(),
        )

    logger.info(
        'OP %s recebida no setor %s (1º bip) — usuário %s',
        op_id, proximo.nome, request.user.username,
    )
    messages.success(request, f'OP recebida no setor {proximo.nome} (1º bip).')
    return redirect('rastreio_op', op_id=op_id)

def _explicar_codigo_nao_encontrado(codigo):
    """Explica por que o codigo nao achou a OP — sem culpar o codigo.

    Caso importante: a OP pode estar no RASTREIO mas ter o cadastro removido.
    RastreioOP.op_id e um inteiro solto (nao e ForeignKey), entao excluir a
    ObraOP nao apaga o rastreio: sobra um rastreio orfao. O operador ve a OP
    listada no rastreio e recebe "codigo nao reconhecido" — confuso, porque a
    OP existe na tela.

    Aqui a mensagem diz o que realmente aconteceu.
    """
    import re

    from core.models import RastreioOP

    codigo = (codigo or '').strip()
    if not codigo:
        return 'Código não reconhecido.'

    # Tenta achar um rastreio cujo codigo case com o que foi lido
    alvo = None
    m = re.match(r'^(.+?)[^A-Za-z0-9_]+([A-Za-z]\d+)$', codigo)
    if m:
        obra_cod, doc = m.group(1).strip(), m.group(2).strip()
        alvo = (
            RastreioOP.objects.filter(obra__iexact=obra_cod,
                                      op_numero__iexact=doc).first()
            or RastreioOP.objects.filter(op_numero__iexact=doc).first()
        )
    if not alvo and re.match(r'^[A-Za-z]+\d+$', codigo):
        alvo = RastreioOP.objects.filter(op_numero__iexact=codigo).first()
    if not alvo and codigo.isdigit():
        alvo = RastreioOP.objects.filter(op_id=int(codigo)).first()

    if alvo:
        return (
            f'A OP {alvo.op_numero} (obra {alvo.obra}) está no rastreio, no '
            f'setor de {alvo.setor_atual_nome}, mas o cadastro dela foi '
            f'removido da Ordem de Produção. Por isso o código não encontra a '
            f'OP. Peça ao responsável para reimportar a OP.'
        )

    return f'Código não reconhecido: "{codigo}".'


def _achar_por_obra_e_doc(obra_cod, doc):
    """Procura a OP casando obra + documento, com tolerancia de caixa."""
    from core.models import ObraOP

    if not doc:
        return None
    return (
        ObraOP.objects.filter(
            obra__codigo=obra_cod, codigo_documento__iexact=doc
        ).first()
        or ObraOP.objects.filter(
            obra__codigo__iexact=obra_cod, codigo_documento__iexact=doc
        ).first()
    )


def _extrair_op_id_do_qr(codigo):
    """Extrai o pk da ObraOP a partir do que o leitor enviou.

    Formatos aceitos, na ordem em que são tentados:
      1. JSON do QR Code      — {"id": 21, "op": "44-J01", ...}
      2. OBRA + separador + DOCUMENTO — "26-0053-02_PROD-J01"
      3. J01                  — só o documento (etiquetas antigas)
      4. 21                   — só o ID numérico (etiquetas antigas)

    TOLERÂNCIA DE SEPARADOR (importante):
    O leitor laser emula teclado, então o caractere separador depende do layout
    do teclado dele. Na prática o '|' chega como '}' (visto em produção:
    '?codigo=26-0053-02_PROD%7DJ01'). Por isso o parser aceita QUALQUER
    separador não-alfanumérico e também o caso sem separador nenhum — assim a
    etiqueta continua sendo lida mesmo que o leitor troque o caractere.
    """
    import json
    import re

    from core.models import ObraOP

    codigo = (codigo or '').strip()
    if not codigo:
        return None

    # --- 1. JSON do QR Code ---
    try:
        dados = json.loads(codigo)
        if isinstance(dados, dict):
            if 'id' in dados:
                try:
                    return int(dados['id'])
                except (TypeError, ValueError):
                    pass
            # 'op' vem como '44-J01' (pk-documento): o pk é o número ANTES do
            # hífen. Pegar todos os dígitos daria '4401' e apontaria errado.
            m = re.match(r'^(\d+)', str(dados.get('op') or ''))
            if m:
                return int(m.group(1))
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # --- 2. OBRA + separador + DOCUMENTO ---
    # Qualquer caractere que não seja letra/dígito/hífen/underscore conta como
    # separador (pega '|', '}', '/', '!', espaço, etc).
    m = re.match(r'^(.+?)[^A-Za-z0-9_]+([A-Za-z]\d+)$', codigo)
    if m:
        obra_op = _achar_por_obra_e_doc(m.group(1).strip(), m.group(2).strip())
        if obra_op:
            return obra_op.pk

    # Sem separador (o leitor pode ter engolido o caractere): o documento é o
    # bloco 'J01'/'P03' no fim. Pega o ÚLTIMO hífen como divisória.
    m = re.match(r'^(.+)-([A-Za-z]\d+)$', codigo)
    if m:
        obra_op = _achar_por_obra_e_doc(m.group(1).strip(), m.group(2).strip())
        if obra_op:
            return obra_op.pk

    # Separador totalmente engolido pelo leitor: '26-0053-02_PRODJ01'.
    # O documento é sempre letra(s)+dígito(s) no fim; tenta achar a divisória
    # que casa com uma OP existente, do fim para o começo.
    for i in range(len(codigo) - 2, 0, -1):
        prefixo, sufixo = codigo[:i], codigo[i:]
        if re.match(r'^[A-Za-z]+\d+$', sufixo):
            obra_op = _achar_por_obra_e_doc(prefixo.strip(), sufixo.strip())
            if obra_op:
                return obra_op.pk

    # --- 3. Só o documento (ex.: J01) ---
    if re.match(r'^[A-Za-z]+\d+$', codigo):
        obra_op = (
            ObraOP.objects.filter(codigo_documento__iexact=codigo).first()
            or ObraOP.objects.filter(codigo_esquadria__iexact=codigo).first()
        )
        if obra_op:
            return obra_op.pk

    # --- 4. Só o ID numérico ---
    if codigo.isdigit():
        return int(codigo)

    return None


def _buscar_obra_op_por_id(obra_op_id):
    """Busca uma ObraOP pelo ID."""
    from core.models import ObraOP
    return ObraOP.objects.filter(pk=obra_op_id).first()


@login_required(login_url='login')
@requer_rotina('producao')
def producao(request):
    """Tela de Produção — o operador de chão de fábrica só faz uma coisa:

    Bipa (ou digita) o código da OP. O sistema decide sozinho se é a entrada
    no setor ou a liberação para o próximo — ciclo de duplo bip, sem digitar
    quantidade (a quantidade não é coletada nesta tela).

    O foco nunca sai do campo de leitura: o leitor de código de barras digita
    como teclado e manda Enter sozinho, então o ciclo inteiro é feito sem mouse.
    """
    if not _garantir_setores():
        messages.error(request, MSG_MIGRATION)

    # ---------------------------------------------------------------
    # POST — 2º bip: finaliza o trabalho informando a quantidade produzida
    # ---------------------------------------------------------------
    if request.method == 'POST':
        return _producao_finalizar(request)

    # ---------------------------------------------------------------
    # GET — leitura do código (1º bip de entrada / troca de setor)
    # ---------------------------------------------------------------
    codigo = request.GET.get('codigo', '').strip()
    vidro = request.GET.get('vidro', '').strip()
    setor_param = request.GET.get('setor', '').strip()

    erro = None
    resultado = None
    precisa_vidro = False
    op_id_pendente = None

    if codigo:
        op_id = _extrair_op_id_do_qr(codigo)
        if not op_id:
            erro = _explicar_codigo_nao_encontrado(codigo)
        elif not _pode_registrar(request.user):
            erro = (
                'Seu usuário não está liberado para registrar produção. '
                'Peça ao administrador para vincular um setor ao seu perfil.'
            )
        else:
            setor_usuario = _setor_do_usuario(request.user, setor_param)
            if not setor_usuario:
                erro = 'Sem setor vinculado ao seu perfil.'
            else:
                obra_op = _buscar_obra_op_por_id(op_id)
                if not obra_op:
                    erro = 'OP não encontrada.'
                else:
                    erro, resultado, precisa_vidro = _registrar_por_setor(
                        request, op_id, setor_usuario, vidro,
                        pedir_quantidade=False,
                    )
                    if precisa_vidro:
                        op_id_pendente = op_id

    context = {
        'codigo': codigo,
        'erro': erro,
        'resultado': resultado,
        'precisa_vidro': precisa_vidro,
        'op_id_pendente': op_id_pendente,
        'setor_param': setor_param,
        'setor_usuario': _setor_do_usuario(request.user, setor_param),
        'pode_registrar': _pode_registrar(request.user),
    }
    return render(request, 'core/industria/producao.html', context)


def _producao_finalizar(request):
    """Finaliza o trabalho do setor (2º bip) a partir da tela de Produção.

    Diferente de `registrar_movimentacao`, esta view NÃO manda o operador para
    a tela de rastreio (que é a visão do gestor) — ela volta para a própria
    tela de Produção, pronta para a próxima leitura.
    """
    setor_param = request.POST.get('setor', '').strip()
    op_id = request.POST.get('op_id', '').strip()
    quantidade = request.POST.get('quantidade_produzida', '').strip()
    observacao = request.POST.get('observacao', '').strip()

    context = {
        'codigo': '',
        'erro': None,
        'resultado': None,
        'precisa_vidro': False,
        'op_id_pendente': None,
        'setor_param': setor_param,
        'setor_usuario': _setor_do_usuario(request.user, setor_param),
        'pode_registrar': _pode_registrar(request.user),
    }

    if not _pode_registrar(request.user):
        context['erro'] = 'Seu usuário não está liberado para registrar produção.'
        return render(request, 'core/industria/producao.html', context)

    try:
        op_id_int = int(op_id)
    except (TypeError, ValueError):
        context['erro'] = 'OP inválida.'
        return render(request, 'core/industria/producao.html', context)

    rastreio = RastreioOP.objects.filter(op_id=op_id_int).first()
    if not rastreio:
        context['erro'] = 'Rastreio não encontrado. Bipe a OP novamente.'
        return render(request, 'core/industria/producao.html', context)

    if rastreio.aguardando_saida:
        context['erro'] = (
            f'A OP já foi liberada do setor de {rastreio.setor_atual_nome}. '
            f'Bipe a próxima peça.'
        )
        return render(request, 'core/industria/producao.html', context)

    # Quantidade produzida — OPCIONAL nesta tela (não é mais coletada).
    # O campo continua aceito para não quebrar chamadas antigas, e se vier
    # algum valor ele ainda é validado contra o total da OP.
    qtd = None
    if quantidade:
        try:
            qtd = int(quantidade)
            if qtd < 0:
                raise ValueError
        except ValueError:
            context['erro'] = 'Quantidade inválida. Informe apenas números.'
            context['resultado'] = {
                'rastreio': rastreio,
                'bip': 'entrada',
                'setor': context['setor_usuario'],
            }
            return render(request, 'core/industria/producao.html', context)

        # Nao deixa informar mais pecas do que a OP pede
        erro_qtd = _validar_quantidade(rastreio, qtd)
        if erro_qtd:
            context['erro'] = erro_qtd
            context['resultado'] = {
                'rastreio': rastreio,
                'bip': 'entrada',
                'setor': context['setor_usuario'],
            }
            return render(request, 'core/industria/producao.html', context)

    with transaction.atomic():
        MovimentacaoOP.objects.filter(
            rastreio=rastreio,
            setor=rastreio.setor_atual,
            data_saida__isnull=True,
        ).update(
            data_saida=timezone.now(),
            usuario_saida=request.user,
            observacao_saida=observacao,
            quantidade_produzida=qtd,
        )
        rastreio.aguardando_saida = True
        rastreio.save(update_fields=['aguardando_saida'])

    logger.info(
        'Produção: OP %s liberada do setor %s — usuário %s, qtd %s',
        op_id_int, rastreio.setor_atual_nome, request.user.username, qtd,
    )

    context['resultado'] = {
        'rastreio': rastreio,
        'bip': 'saida',
        'setor': context['setor_usuario'],
        'quantidade_produzida': qtd,
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
    quantidade_produzida = request.GET.get('quantidade_produzida', '').strip()
    erro = None
    resultado = None
    precisa_vidro = False
    op_id_pendente = None

    if codigo:
        # Tenta extrair o ID do JSON do QR Code
        op_id = _extrair_op_id_do_qr(codigo)
        if not op_id:
            erro = _explicar_codigo_nao_encontrado(codigo)
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
                    # Converte quantidade para int se fornecida
                    qtd = None
                    if quantidade_produzida:
                        try:
                            qtd = int(quantidade_produzida)
                            if qtd < 0:
                                raise ValueError
                        except ValueError:
                            erro = 'Quantidade produzida inválida.'
                    if not erro:
                        erro, resultado, precisa_vidro = _registrar_por_setor(
                            request, op_id, setor_usuario, vidro, quantidade_produzida=qtd
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
