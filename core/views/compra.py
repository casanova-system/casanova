"""Compra — requisição, cotação e pedido ao fornecedor.

O ciclo completo:
    Estoque abaixo do mínimo ─┐
    OP precisa de material  ──┼─> REQUISIÇÃO ─> PEDIDO ─> ENTRADA no estoque
    Pedido manual           ──┘

A parte que fecha o ciclo com o estoque: quando o pedido é recebido, a entrada
é lançada no estoque automaticamente. Sem isso, o comprador recebe a nota e
alguém tem que lembrar de dar entrada — e o saldo fica errado.
"""
import logging
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import (Fornecedor, LocalEstoque, MovimentoEstoque,
                         PedidoCompra, PedidoCompraItem, ProdutoEstoque,
                         ProdutoFornecedor, RequisicaoCompra, RequisicaoCompraItem)
from core.views.permissao import requer_rotina

logger = logging.getLogger(__name__)

ITENS_POR_PAGINA = 15


def _dec(valor, padrao=Decimal('0')):
    if valor in (None, ''):
        return padrao
    s = str(valor).strip()
    try:
        return Decimal(s.replace('.', '').replace(',', '.') if ',' in s else s)
    except (InvalidOperation, ValueError):
        return padrao


def _sugestoes_minimo():
    """Produtos abaixo do mínimo que ainda não têm requisição aberta.

    É a sugestão automática de compra: o sistema aponta o que está faltando,
    em vez de depender de alguém perceber.
    """
    abertas = set(
        RequisicaoCompraItem.objects
        .filter(requisicao__status__in=['ABERTA', 'APROVADA', 'COTACAO', 'PEDIDO'])
        .values_list('produto_id', flat=True)
    )
    sugestoes = []
    for p in ProdutoEstoque.objects.filter(ativo=True).select_related('grupo'):
        if p.pk in abertas:
            continue
        if p.abaixo_minimo:
            sugestoes.append(p)
    return sugestoes


# ===========================================================================
# REQUISIÇÕES
# ===========================================================================

@login_required(login_url='login')
@requer_rotina('lista_compras')
def lista_requisicoes(request):
    """Lista de requisições com filtros e sugestões de compra."""
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    qs = RequisicaoCompra.objects.select_related(
        'solicitante', 'obra_op', 'aprovado_por')

    if query:
        qs = qs.filter(
            Q(numero__icontains=query)
            | Q(justificativa__icontains=query)
            | Q(obra_op__codigo_documento__icontains=query))
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    sugestoes = _sugestoes_minimo()

    context = {
        'requisicoes': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'status_atual': status,
        'status_opcoes': RequisicaoCompra._meta.get_field('status').choices,
        'sugestoes': sugestoes,
        'total_sugestoes': len(sugestoes),
        'kpi': {
            'abertas': RequisicaoCompra.objects.filter(status='ABERTA').count(),
            'aprovadas': RequisicaoCompra.objects.filter(status='APROVADA').count(),
            'pedidos': PedidoCompra.objects.exclude(status='CANCELADO').count(),
            'aguardando': PedidoCompra.objects.filter(
                status__in=['ENVIADO', 'PARCIAL']).count(),
        },
    }
    return render(request, 'core/compra/lista_requisicoes.html', context)


@login_required(login_url='login')
@requer_rotina('lista_compras')
def nova_requisicao(request):
    """Cria uma requisição escolhendo os materiais."""
    if request.method == 'POST':
        produtos_ids = request.POST.getlist('produtos')
        origem = request.POST.get('origem', 'MANUAL').strip()
        prioridade = request.POST.get('prioridade', 'NORMAL').strip()
        justificativa = request.POST.get('justificativa', '').strip()
        setor = request.POST.get('setor', '').strip()
        op_id = request.POST.get('obra_op', '').strip()
        data_nec = request.POST.get('data_necessaria', '').strip()

        if not produtos_ids:
            messages.error(request, 'Escolha pelo menos um material.')
            return redirect('nova_requisicao')

        with transaction.atomic():
            req = RequisicaoCompra(
                solicitante=request.user,
                origem=origem,
                prioridade=prioridade,
                justificativa=justificativa,
                setor=setor,
                obra_op_id=int(op_id) if op_id.isdigit() else None,
            )
            req.numero = req.gerar_numero()
            if data_nec:
                from datetime import datetime
                try:
                    req.data_necessaria = datetime.strptime(
                        data_nec, '%Y-%m-%d').date()
                except ValueError:
                    pass
            req.save()

            for pid in produtos_ids:
                if not str(pid).isdigit():
                    continue
                prod = ProdutoEstoque.objects.filter(pk=pid).first()
                if not prod:
                    continue
                # quantidade sugerida: o que falta para o minimo (ou 1)
                qtd = Decimal('1')
                if prod.estoque_minimo and prod.abaixo_minimo:
                    falta = Decimal(str(prod.estoque_minimo)) - Decimal(str(prod.saldo_total))
                    if falta > 0:
                        qtd = falta
                qtd_form = request.POST.get(f'qtd_{pid}', '').strip()
                if qtd_form:
                    qtd = _dec(qtd_form, qtd)
                RequisicaoCompraItem.objects.create(
                    requisicao=req, produto=prod, quantidade=qtd,
                    preco_estimado=prod.custo_ultima_compra or prod.custo_medio or 0,
                )

        logger.info('Requisição %s criada por %s (%d itens)',
                    req.numero, request.user.username, req.itens.count())
        messages.success(request, f'Requisição {req.numero} criada.')
        return redirect('detalhe_requisicao', requisicao_id=req.pk)

    # GET
    sugestoes = _sugestoes_minimo()
    context = {
        'sugestoes': sugestoes,
        'produtos': ProdutoEstoque.objects.filter(ativo=True)
                    .select_related('grupo').order_by('codigo'),
        'locais': LocalEstoque.objects.filter(ativo=True),
    }
    return render(request, 'core/compra/nova_requisicao.html', context)


@login_required(login_url='login')
@requer_rotina('lista_compras')
def detalhe_requisicao(request, requisicao_id):
    """Detalhe da requisição: aprovar, editar itens, gerar pedido."""
    req = get_object_or_404(
        RequisicaoCompra.objects.select_related('solicitante', 'obra_op'),
        pk=requisicao_id)

    if request.method == 'POST':
        acao = request.POST.get('acao', '').strip()

        if acao == 'aprovar':
            if not req.pode_aprovar:
                messages.error(request, f'A requisição está "{req.status_nome}".')
            else:
                req.status = 'APROVADA'
                req.aprovado_por = request.user
                req.data_aprovacao = timezone.now()
                req.save(update_fields=['status', 'aprovado_por',
                                        'data_aprovacao', 'atualizado_em'])
                messages.success(request, f'Requisição {req.numero} aprovada.')
            return redirect('detalhe_requisicao', requisicao_id=req.pk)

        if acao == 'cancelar':
            req.status = 'CANCELADA'
            req.save(update_fields=['status', 'atualizado_em'])
            messages.success(request, f'Requisição {req.numero} cancelada.')
            return redirect('detalhe_requisicao', requisicao_id=req.pk)

        if acao == 'remover':
            if not req.pode_editar:
                messages.error(request, 'Esta requisição não pode mais ser alterada.')
            else:
                item_id = request.POST.get('item_id', '').strip()
                RequisicaoCompraItem.objects.filter(
                    pk=item_id, requisicao=req).delete()
                messages.success(request, 'Item removido.')
            return redirect('detalhe_requisicao', requisicao_id=req.pk)

        if acao == 'adicionar':
            if not req.pode_editar:
                messages.error(request, 'Esta requisição não pode mais ser alterada.')
                return redirect('detalhe_requisicao', requisicao_id=req.pk)
            pid = request.POST.get('produto', '').strip()
            qtd = _dec(request.POST.get('quantidade'))
            prod = ProdutoEstoque.objects.filter(pk=pid).first()
            if prod and qtd > 0:
                RequisicaoCompraItem.objects.create(
                    requisicao=req, produto=prod, quantidade=qtd,
                    preco_estimado=prod.custo_ultima_compra or prod.custo_medio or 0)
                messages.success(request, f'{prod.codigo} adicionado.')
            else:
                messages.error(request, 'Produto ou quantidade inválidos.')
            return redirect('detalhe_requisicao', requisicao_id=req.pk)

        if acao == 'gerar_pedido':
            fornecedor_id = request.POST.get('fornecedor', '').strip()
            fornecedor = Fornecedor.objects.filter(pk=fornecedor_id).first()
            if not fornecedor:
                messages.error(request, 'Escolha o fornecedor.')
                return redirect('detalhe_requisicao', requisicao_id=req.pk)

            local_id = request.POST.get('local_destino', '').strip()
            local = LocalEstoque.objects.filter(pk=local_id).first()

            with transaction.atomic():
                ped = PedidoCompra(
                    fornecedor=fornecedor,
                    requisicao=req,
                    condicao_pagamento=request.POST.get(
                        'condicao_pagamento', '').strip(),
                    data_pedido=timezone.localdate(),
                    comprador=request.user,
                    observacao=request.POST.get('observacao_pedido', '').strip(),
                )
                ped.numero = ped.gerar_numero()
                dias = fornecedor.prazo_entrega_dias
                if dias:
                    from datetime import timedelta
                    ped.previsao_entrega = timezone.localdate() + timedelta(days=dias)
                ped.save()

                for item in req.itens.all():
                    PedidoCompraItem.objects.create(
                        pedido=ped, produto=item.produto,
                        quantidade=item.quantidade,
                        preco_unitario=item.preco_estimado or 0,
                        local_destino=local,
                    )
                req.status = 'PEDIDO'
                req.save(update_fields=['status', 'atualizado_em'])

            logger.info('Pedido %s gerado da requisição %s por %s',
                        ped.numero, req.numero, request.user.username)
            messages.success(
                request,
                f'Pedido {ped.numero} gerado para {fornecedor.nome_curto}.')
            return redirect('detalhe_pedido', pedido_id=ped.pk)

    context = {
        'requisicao': req,
        'itens': req.itens.select_related('produto', 'produto__grupo'),
        'fornecedores': Fornecedor.objects.filter(ativo=True),
        'produtos': ProdutoEstoque.objects.filter(ativo=True)
                    .select_related('grupo').order_by('codigo'),
        'locais': LocalEstoque.objects.filter(ativo=True),
    }
    return render(request, 'core/compra/detalhe_requisicao.html', context)


# ===========================================================================
# PEDIDOS
# ===========================================================================

@login_required(login_url='login')
@requer_rotina('lista_compras')
def lista_pedidos(request):
    """Lista de pedidos de compra."""
    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()

    qs = PedidoCompra.objects.select_related('fornecedor', 'comprador', 'requisicao')

    if query:
        qs = qs.filter(
            Q(numero__icontains=query)
            | Q(fornecedor__razao_social__icontains=query)
            | Q(fornecedor__nome_fantasia__icontains=query))
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'pedidos': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'status_atual': status,
        'status_opcoes': PedidoCompra._meta.get_field('status').choices,
    }
    return render(request, 'core/compra/lista_pedidos.html', context)


@login_required(login_url='login')
@requer_rotina('lista_compras')
def detalhe_pedido(request, pedido_id):
    """Detalhe do pedido: editar, receber (dá entrada no estoque)."""
    ped = get_object_or_404(
        PedidoCompra.objects.select_related('fornecedor', 'comprador', 'requisicao'),
        pk=pedido_id)

    if request.method == 'POST':
        acao = request.POST.get('acao', '').strip()

        if acao == 'status':
            novo = request.POST.get('status', '').strip()
            if novo in dict(PedidoCompra._meta.get_field('status').choices):
                ped.status = novo
                ped.save(update_fields=['status', 'atualizado_em'])
                messages.success(request, f'Pedido {ped.numero}: {ped.status_nome}.')
            return redirect('detalhe_pedido', pedido_id=ped.pk)

        if acao == 'receber':
            # Recebe o pedido e DA ENTRADA NO ESTOQUE.
            # Este e o ponto que fecha o ciclo: o comprador recebe a nota e o
            # saldo sobe sozinho, ligado ao pedido.
            if not ped.pode_receber:
                messages.error(request, f'O pedido está "{ped.status_nome}".')
                return redirect('detalhe_pedido', pedido_id=ped.pk)

            local_padrao_id = request.POST.get('local_recebimento', '').strip()
            local_padrao = LocalEstoque.objects.filter(pk=local_padrao_id).first()

            recebidos = 0
            with transaction.atomic():
                for item in ped.itens.all():
                    qtd_form = request.POST.get(f'receber_{item.pk}', '').strip()
                    qtd = _dec(qtd_form)
                    if qtd <= 0:
                        continue
                    local = item.local_destino or local_padrao
                    if not local:
                        continue
                    mov = MovimentoEstoque.objects.create(
                        produto=item.produto,
                        local=local,
                        tipo='ENTRADA',
                        origem='COMPRA',
                        quantidade=qtd,
                        valor_unitario=item.preco_unitario,
                        valor_total=Decimal(str(qtd)) * Decimal(str(item.preco_unitario or 0)),
                        documento=ped.numero,
                        observacao=f'Recebimento do pedido {ped.numero}',
                        usuario=request.user,
                    )
                    mov.aplicar_no_saldo()
                    item.quantidade_recebida = (
                        Decimal(str(item.quantidade_recebida or 0)) + qtd)
                    item.save(update_fields=['quantidade_recebida'])

                    # atualiza custo do produto com o preco da compra
                    if item.preco_unitario:
                        item.produto.custo_ultima_compra = item.preco_unitario
                        item.produto.save(update_fields=['custo_ultima_compra'])
                    recebidos += 1

                # status do pedido conforme o que foi recebido
                tudo = all(i.recebido_completo for i in ped.itens.all())
                algo = any((i.quantidade_recebida or 0) > 0 for i in ped.itens.all())
                if tudo:
                    ped.status = 'RECEBIDO'
                    ped.data_recebimento = timezone.localdate()
                    ped.save(update_fields=['status', 'data_recebimento',
                                            'atualizado_em'])
                    # requisição de origem fica atendida
                    if ped.requisicao:
                        ped.requisicao.status = 'ATENDIDA'
                        ped.requisicao.save(update_fields=['status', 'atualizado_em'])
                elif algo:
                    ped.status = 'PARCIAL'
                    ped.save(update_fields=['status', 'atualizado_em'])

            if recebidos:
                logger.info('Pedido %s recebido por %s — %d item(ns)',
                            ped.numero, request.user.username, recebidos)
                messages.success(
                    request,
                    f'{recebidos} item(ns) recebido(s) e lançado(s) no estoque. '
                    f'Status: {ped.status_nome}.')
            else:
                messages.warning(request, 'Nenhuma quantidade informada.')
            return redirect('detalhe_pedido', pedido_id=ped.pk)

        if acao == 'editar':
            if not ped.pode_editar:
                messages.error(request, 'Este pedido não pode mais ser alterado.')
                return redirect('detalhe_pedido', pedido_id=ped.pk)
            ped.condicao_pagamento = request.POST.get('condicao_pagamento', '').strip()
            ped.observacao = request.POST.get('observacao', '').strip()
            ped.frete = _dec(request.POST.get('frete'))
            prev = request.POST.get('previsao_entrega', '').strip()
            campos = ['condicao_pagamento', 'observacao', 'frete', 'atualizado_em']
            if prev:
                from datetime import datetime
                try:
                    ped.previsao_entrega = datetime.strptime(prev, '%Y-%m-%d').date()
                    campos.append('previsao_entrega')
                except ValueError:
                    pass
            ped.save(update_fields=campos)
            messages.success(request, 'Pedido atualizado.')
            return redirect('detalhe_pedido', pedido_id=ped.pk)

    context = {
        'pedido': ped,
        'itens': ped.itens.select_related('produto', 'local_destino'),
        'locais': LocalEstoque.objects.filter(ativo=True),
        'pode_receber': ped.pode_receber,
    }
    return render(request, 'core/compra/detalhe_pedido.html', context)


@login_required(login_url='login')
@requer_rotina('lista_compras')
def lista_fornecedores(request):
    """Cadastro de fornecedores."""
    query = request.GET.get('q', '').strip()
    qs = Fornecedor.objects.filter(ativo=True)
    if query:
        qs = qs.filter(
            Q(razao_social__icontains=query) | Q(nome_fantasia__icontains=query)
            | Q(cnpj__icontains=query) | Q(cidade__icontains=query))
    qs = qs.order_by('razao_social')

    paginator = Paginator(qs, ITENS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'fornecedores': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
    }
    return render(request, 'core/compra/lista_fornecedores.html', context)


@login_required(login_url='login')
@requer_rotina('lista_compras')
def novo_fornecedor(request):
    """Cadastra um fornecedor."""
    if request.method == 'POST':
        razao = request.POST.get('razao_social', '').strip()
        if not razao:
            messages.error(request, 'A razão social é obrigatória.')
            return redirect('novo_fornecedor')

        f = Fornecedor.objects.create(
            razao_social=razao,
            nome_fantasia=request.POST.get('nome_fantasia', '').strip(),
            cnpj=request.POST.get('cnpj', '').strip(),
            inscricao_estadual=request.POST.get('inscricao_estadual', '').strip(),
            contato=request.POST.get('contato', '').strip(),
            telefone=request.POST.get('telefone', '').strip(),
            email=request.POST.get('email', '').strip(),
            endereco=request.POST.get('endereco', '').strip(),
            cidade=request.POST.get('cidade', '').strip(),
            uf=request.POST.get('uf', '').strip().upper()[:2],
            prazo_entrega_dias=(int(request.POST['prazo_entrega_dias'])
                                if request.POST.get('prazo_entrega_dias', '').strip().isdigit()
                                else None),
            observacao=request.POST.get('observacao', '').strip(),
        )
        logger.info('Fornecedor %s cadastrado por %s', f, request.user.username)
        messages.success(request, f'Fornecedor {f.nome_curto} cadastrado.')
        return redirect('lista_fornecedores')

    return render(request, 'core/compra/novo_fornecedor.html', {})
