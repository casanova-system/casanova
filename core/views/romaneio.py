"""Romaneio de Carga — agrupa as OPs que saem juntas numa entrega.

A Expedicao e o setor final do fluxo de producao. O romaneio pega as OPs que
ja chegaram la e monta a carga: veiculo, motorista, destino e o que vai.

Regra que o sistema garante (e a planilha nao garantia):
    So entra OP que JA CHEGOU na Expedicao. Se a peca ainda esta na fabrica,
    ela nao aparece na lista de disponiveis — assim a carga nao sai incompleta.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import ObraOP, Obra, RastreioOP, Romaneio, RomaneioItem, Veiculo
from core.views.permissao import requer_rotina

logger = logging.getLogger(__name__)

ITENS_POR_PAGINA = 12
MSG_MIGRATION = (
    'A rotina de romaneio ainda não foi instalada neste servidor. '
    'Peça ao administrador para rodar as migrações.'
)

SETOR_EXPEDICAO = 'expedicao'


def _ops_disponiveis(romaneio=None):
    """OPs que podem entrar no romaneio.

    Criterio: o rastreio existe E o setor atual e a Expedicao (a peca ja saiu
    da fabrica). OPs que ja estao em outro romaneio nao aparecem — evita a
    mesma peca sair em duas cargas.
    """
    ja_em_romaneio = set(
        RomaneioItem.objects
        .exclude(romaneio__status='CANCELADO')
        .values_list('obra_op_id', flat=True)
    )
    if romaneio:
        # As que ja estao NESTE romaneio continuam disponiveis para ele
        ja_em_romaneio -= set(
            romaneio.itens.values_list('obra_op_id', flat=True)
        )

    ids_na_expedicao = list(
        RastreioOP.objects
        .filter(setor_atual=SETOR_EXPEDICAO)
        .values_list('op_id', flat=True)
    )

    qs = (
        ObraOP.objects
        .filter(pk__in=ids_na_expedicao)
        .exclude(pk__in=ja_em_romaneio)
        .select_related('obra')
        .order_by('obra__codigo', 'codigo_documento')
    )
    return qs


@login_required(login_url='login')
@requer_rotina('lista_romaneios')
def lista_romaneios(request):
    """Lista os romaneios com filtro por status e busca."""
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    romaneios = Romaneio.objects.select_related('obra', 'veiculo', 'criado_por')

    if query:
        romaneios = romaneios.filter(
            Q(numero__icontains=query)
            | Q(obra__codigo__icontains=query)
            | Q(obra__nome__icontains=query)
            | Q(motorista__icontains=query)
            | Q(veiculo__placa__icontains=query)
        )
    if status:
        romaneios = romaneios.filter(status=status)

    paginator = Paginator(romaneios, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)

    # Contadores para os cards
    contagem = {
        'abertos': Romaneio.objects.filter(status='ABERTO').count(),
        'em_carga': Romaneio.objects.filter(status='EM_CARGA').count(),
        'saiu': Romaneio.objects.filter(status='SAIU').count(),
        'entregue': Romaneio.objects.filter(status='ENTREGUE').count(),
    }

    context = {
        'romaneios': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'status_atual': status,
        'status_opcoes': Romaneio._meta.get_field('status').choices,
        'contagem': contagem,
        'disponiveis': _ops_disponiveis().count(),
    }
    return render(request, 'core/romaneio/lista_romaneio.html', context)


@login_required(login_url='login')
@requer_rotina('lista_romaneios')
def novo_romaneio(request):
    """Cria um romaneio escolhendo as OPs que ja estao na Expedicao."""
    if request.method == 'POST':
        obra_id = request.POST.get('obra', '').strip()
        veiculo_id = request.POST.get('veiculo', '').strip()
        motorista = request.POST.get('motorista', '').strip()
        distancia = request.POST.get('distancia_km', '').strip().replace(',', '.')
        endereco = request.POST.get('endereco_entrega', '').strip()
        observacao = request.POST.get('observacao', '').strip()
        ops_ids = request.POST.getlist('ops')

        erros = []
        if not obra_id:
            erros.append('Escolha a obra de destino.')
        if not ops_ids:
            erros.append('Escolha pelo menos uma OP para a carga.')

        if erros:
            for e in erros:
                messages.error(request, e)
            return redirect('novo_romaneio')

        obra = get_object_or_404(Obra, pk=obra_id)
        veiculo = Veiculo.objects.filter(pk=veiculo_id).first() if veiculo_id else None

        # Confere de novo no servidor: a OP tem de estar na Expedicao.
        # O HTML marca so as disponiveis, mas o POST pode vir alterado.
        disponiveis = set(_ops_disponiveis().values_list('pk', flat=True))
        escolhidas = [int(i) for i in ops_ids if str(i).isdigit()]
        invalidas = [i for i in escolhidas if i not in disponiveis]
        if invalidas:
            messages.error(
                request,
                'Alguma OP escolhida ainda não chegou na Expedição ou já está '
                'em outro romaneio. A carga não foi criada.',
            )
            return redirect('novo_romaneio')

        with transaction.atomic():
            romaneio = Romaneio(
                obra=obra,
                veiculo=veiculo,
                motorista=motorista,
                endereco_entrega=endereco or (obra.cliente or ''),
                observacao=observacao,
                criado_por=request.user,
            )
            romaneio.numero = romaneio.gerar_numero()
            if distancia:
                try:
                    romaneio.distancia_km = distancia
                except (ValueError, TypeError):
                    pass
            elif obra.distancia_km:
                romaneio.distancia_km = obra.distancia_km
            romaneio.save()

            for op in ObraOP.objects.filter(pk__in=escolhidas):
                RomaneioItem.objects.create(
                    romaneio=romaneio,
                    obra_op=op,
                    quantidade=op.quantidade or 1,
                )

        logger.info(
            'Romaneio %s criado por %s — obra %s, %d OP(s)',
            romaneio.numero, request.user.username, obra.codigo, len(escolhidas),
        )
        messages.success(
            request,
            f'Romaneio {romaneio.numero} criado com {len(escolhidas)} OP(s).',
        )
        return redirect('detalhe_romaneio', romaneio_id=romaneio.pk)

    # GET: formulario
    obra_id = request.GET.get('obra', '').strip()
    disponiveis = _ops_disponiveis()
    if obra_id:
        disponiveis = disponiveis.filter(obra_id=obra_id)

    context = {
        'obras': Obra.objects.order_by('codigo'),
        'veiculos': Veiculo.objects.filter(ativo=True).order_by('placa'),
        'disponiveis': disponiveis.select_related('obra'),
        'total_disponivel': _ops_disponiveis().count(),
        'obra_selecionada': obra_id,
    }
    return render(request, 'core/romaneio/novo_romaneio.html', context)


@login_required(login_url='login')
@requer_rotina('lista_romaneios')
def detalhe_romaneio(request, romaneio_id):
    """Detalhe do romaneio: itens, status, conferencia."""
    romaneio = get_object_or_404(
        Romaneio.objects.select_related('obra', 'veiculo', 'criado_por'),
        pk=romaneio_id,
    )

    if request.method == 'POST':
        acao = request.POST.get('acao', '').strip()

        if not romaneio.pode_editar and acao in ('adicionar', 'remover'):
            messages.error(
                request,
                f'O romaneio está "{romaneio.status_nome}" e não pode mais '
                f'ser alterado.',
            )
            return redirect('detalhe_romaneio', romaneio_id=romaneio.pk)

        if acao == 'adicionar':
            ids = [int(i) for i in request.POST.getlist('ops') if str(i).isdigit()]
            disponiveis = set(_ops_disponiveis(romaneio).values_list('pk', flat=True))
            validas = [i for i in ids if i in disponiveis]
            with transaction.atomic():
                for op in ObraOP.objects.filter(pk__in=validas):
                    RomaneioItem.objects.get_or_create(
                        romaneio=romaneio, obra_op=op,
                        defaults={'quantidade': op.quantidade or 1},
                    )
            if validas:
                messages.success(request, f'{len(validas)} OP(s) adicionada(s).')
            else:
                messages.warning(request, 'Nenhuma OP válida para adicionar.')
            return redirect('detalhe_romaneio', romaneio_id=romaneio.pk)

        if acao == 'remover':
            item_id = request.POST.get('item_id', '').strip()
            item = RomaneioItem.objects.filter(pk=item_id, romaneio=romaneio).first()
            if item:
                item.delete()
                messages.success(request, 'OP removida do romaneio.')
            return redirect('detalhe_romaneio', romaneio_id=romaneio.pk)

        if acao == 'conferir':
            item_id = request.POST.get('item_id', '').strip()
            item = RomaneioItem.objects.filter(pk=item_id, romaneio=romaneio).first()
            if item:
                item.conferido = not item.conferido
                item.save(update_fields=['conferido'])
            return redirect('detalhe_romaneio', romaneio_id=romaneio.pk)

        if acao == 'status':
            novo = request.POST.get('status', '').strip()
            validos = dict(Romaneio.STATUS_ROMANEIO) if hasattr(Romaneio, 'STATUS_ROMANEIO') else None
            from core.models import STATUS_ROMANEIO
            if novo in dict(STATUS_ROMANEIO):
                romaneio.status = novo
                campos = ['status']
                if novo == 'SAIU' and not romaneio.data_saida:
                    romaneio.data_saida = timezone.now()
                    campos.append('data_saida')
                if novo == 'ENTREGUE' and not romaneio.data_entrega:
                    romaneio.data_entrega = timezone.now()
                    campos.append('data_entrega')
                    recebido = request.POST.get('recebido_por', '').strip()
                    if recebido:
                        romaneio.recebido_por = recebido
                        campos.append('recebido_por')
                romaneio.save(update_fields=campos)
                messages.success(
                    request, f'Romaneio {romaneio.numero}: {romaneio.status_nome}.',
                )
            return redirect('detalhe_romaneio', romaneio_id=romaneio.pk)

        if acao == 'editar':
            romaneio.motorista = request.POST.get('motorista', '').strip()
            romaneio.endereco_entrega = request.POST.get('endereco_entrega', '').strip()
            romaneio.observacao = request.POST.get('observacao', '').strip()
            dist = request.POST.get('distancia_km', '').strip().replace(',', '.')
            campos = ['motorista', 'endereco_entrega', 'observacao']
            if dist:
                try:
                    romaneio.distancia_km = dist
                    campos.append('distancia_km')
                except (ValueError, TypeError):
                    pass
            veiculo_id = request.POST.get('veiculo', '').strip()
            if veiculo_id:
                romaneio.veiculo = Veiculo.objects.filter(pk=veiculo_id).first()
                campos.append('veiculo')
            romaneio.save(update_fields=campos)
            messages.success(request, 'Romaneio atualizado.')
            return redirect('detalhe_romaneio', romaneio_id=romaneio.pk)

    from core.models import STATUS_ROMANEIO
    context = {
        'romaneio': romaneio,
        'itens': romaneio.itens.select_related('obra_op', 'obra_op__obra'),
        'disponiveis': _ops_disponiveis(romaneio).select_related('obra'),
        'veiculos': Veiculo.objects.filter(ativo=True).order_by('placa'),
        'status_opcoes': STATUS_ROMANEIO,
    }
    return render(request, 'core/romaneio/detalhe_romaneio.html', context)


@login_required(login_url='login')
@requer_rotina('lista_romaneios')
def imprimir_romaneio(request, romaneio_id):
    """Romaneio em folha A4 para o motorista levar e colher assinatura."""
    romaneio = get_object_or_404(
        Romaneio.objects.select_related('obra', 'veiculo', 'criado_por'),
        pk=romaneio_id,
    )
    context = {
        'romaneio': romaneio,
        'itens': romaneio.itens.select_related('obra_op', 'obra_op__obra'),
        'gerado_em': timezone.now(),
    }
    return render(request, 'core/romaneio/imprimir_romaneio.html', context)


@login_required(login_url='login')
@requer_rotina('lista_romaneios')
def excluir_romaneio(request, romaneio_id):
    """Exclui um romaneio (so se ainda nao saiu)."""
    romaneio = get_object_or_404(Romaneio, pk=romaneio_id)
    if request.method != 'POST':
        return redirect('detalhe_romaneio', romaneio_id=romaneio.pk)

    if not romaneio.pode_editar:
        messages.error(
            request,
            f'O romaneio {romaneio.numero} já saiu para entrega e não pode '
            f'ser excluído.',
        )
        return redirect('detalhe_romaneio', romaneio_id=romaneio.pk)

    numero = romaneio.numero
    romaneio.delete()
    logger.info('Romaneio %s excluído por %s', numero, request.user.username)
    messages.success(request, f'Romaneio {numero} excluído.')
    return redirect('lista_romaneios')
