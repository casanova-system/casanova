"""Custo por OP — quanto cada ordem de produção custou de verdade.

Junta o que o sistema já sabe:

    MATERIAL      o que a OP consumiu do estoque
    MÃO DE OBRA   o tempo que ela passou em cada setor
    INDIRETO      energia, aluguel e supervisão rateados

O número que decide o preço é o CUSTO UNITÁRIO — quanto custou cada peça.
"""
import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.models import (CUSTO_HORA_SETOR_PADRAO, CustoOP, CustoOPMaterial,
                         CustoOPSetor, CustoSetor, LocalEstoque,
                         MovimentacaoOP, MovimentoEstoque, ObraOP,
                         ProdutoEstoque, RastreioOP, SetorProducao)
from core.views.permissao import requer_rotina

logger = logging.getLogger(__name__)

ITENS_POR_PAGINA = 15


# ===========================================================================
# O MOTOR DE CÁLCULO
# ===========================================================================

def calcular_custo_op(obra_op, usuario=None, valor_venda=None):
    """Calcula (ou recalcula) o custo de uma OP.

    Devolve o CustoOP gravado. Recalcular é seguro: apaga o detalhamento
    anterior e refaz — nunca soma duas vezes.
    """
    rastreio = RastreioOP.objects.filter(op_id=obra_op.pk).first()

    with transaction.atomic():
        custo, _ = CustoOP.objects.get_or_create(obra_op=obra_op)
        custo.rastreio = rastreio
        custo.calculado_por = usuario
        if valor_venda is not None:
            custo.valor_venda = valor_venda

        # limpa o detalhamento anterior (recalculo nao acumula)
        custo.setores.all().delete()
        custo.materiais.all().delete()

        # -----------------------------------------------------------------
        # 1. MATERIAL — o que a OP consumiu do estoque
        # -----------------------------------------------------------------
        total_material = Decimal('0')
        movimentos = MovimentoEstoque.objects.filter(
            obra_op=obra_op, tipo='SAIDA',
        ).select_related('produto')

        if movimentos.exists():
            for mov in movimentos:
                valor = mov.valor_total
                if not valor:
                    valor = (Decimal(str(mov.quantidade or 0))
                             * Decimal(str(mov.valor_unitario or 0)))
                CustoOPMaterial.objects.create(
                    custo_op=custo,
                    produto=mov.produto,
                    codigo=mov.produto.codigo if mov.produto else '',
                    descricao=mov.produto.descricao if mov.produto else '',
                    quantidade=mov.quantidade or 0,
                    unidade=mov.produto.unidade_efetiva if mov.produto else 'UN',
                    valor_unitario=mov.valor_unitario or 0,
                    custo=valor,
                )
                total_material += Decimal(str(valor or 0))
        else:
            # sem consumo lançado: estima pelos itens da própria OP.
            # Melhor uma estimativa explícita do que um custo zerado que
            # esconde o problema.
            total_material = _estimar_material(obra_op, custo)

        custo.custo_material = total_material

        # -----------------------------------------------------------------
        # 2. MÃO DE OBRA — o tempo que a OP passou em cada setor
        # -----------------------------------------------------------------
        total_horas = Decimal('0')
        total_mo = Decimal('0')
        total_ind = Decimal('0')

        movs = []
        if rastreio:
            movs = list(
                MovimentacaoOP.objects.filter(rastreio=rastreio)
                .order_by('data_entrada', 'data_hora')
            )

        # agrupa por setor: uma OP pode passar 2x pelo mesmo setor
        por_setor = {}
        for mv in movs:
            minutos = mv.tempo_no_setor
            if not minutos or minutos <= 0:
                continue
            chave = mv.setor
            if chave not in por_setor:
                por_setor[chave] = {
                    'nome': mv.setor_nome or chave,
                    'minutos': 0.0,
                    'qtd': 0,
                }
            por_setor[chave]['minutos'] += float(minutos)
            por_setor[chave]['qtd'] += int(mv.quantidade_produzida or 0)

        for setor, dados in por_setor.items():
            horas = Decimal(str(round(dados['minutos'] / 60, 4)))
            ch, ci = CustoSetor.custo_do_setor(setor)
            custo_h = Decimal(str(ch))
            custo_i = Decimal(str(ci))

            c_setor = (horas * custo_h).quantize(Decimal('0.01'))
            c_ind = (horas * custo_i).quantize(Decimal('0.01'))

            CustoOPSetor.objects.create(
                custo_op=custo,
                setor=setor,
                setor_nome=dados['nome'],
                minutos=Decimal(str(round(dados['minutos'], 2))),
                horas=horas,
                custo_hora=custo_h,
                custo=c_setor,
                quantidade_produzida=dados['qtd'],
            )
            total_horas += horas
            total_mo += c_setor
            total_ind += c_ind

        custo.horas_totais = total_horas
        custo.custo_mao_obra = total_mo
        custo.custo_indireto = total_ind

        # -----------------------------------------------------------------
        # 3. RESULTADO
        # -----------------------------------------------------------------
        custo.custo_total = (total_material + total_mo + total_ind)
        custo.quantidade = obra_op.quantidade or 1
        if custo.quantidade:
            custo.custo_unitario = (
                Decimal(str(custo.custo_total)) / Decimal(str(custo.quantidade))
            ).quantize(Decimal('0.01'))
        custo.save()

    logger.info('Custo da OP %s calculado: R$ %s (%s peças, R$ %s/peça)',
                obra_op.codigo_formatado, custo.custo_total,
                custo.quantidade, custo.custo_unitario)
    return custo


def _estimar_material(obra_op, custo):
    """Estima o material da OP pelos itens dela, quando não há consumo lançado.

    Casa o código do item (perfil/vidro/componente) com o cadastro de produto
    do estoque. O que não casa entra como "não cadastrado" — assim o custo
    nunca mente por omissão: ele mostra que falta cadastro.
    """
    total = Decimal('0')

    def buscar(codigo):
        if not codigo:
            return None
        return (ProdutoEstoque.objects.filter(codigo__iexact=codigo.strip()).first()
                or ProdutoEstoque.objects.filter(
                    codigo__icontains=codigo.strip()[:20]).first())

    # perfis
    for it in obra_op.itens.all():
        prod = buscar(it.codigo)
        qtd = Decimal(str(it.quantidade or 0))
        if it.peso:
            qtd = Decimal(str(it.peso or 0))
        if qtd <= 0:
            continue
        vu = Decimal(str((prod.custo_medio or prod.custo_ultima_compra or 0)
                         if prod else 0))
        valor = (qtd * vu).quantize(Decimal('0.01'))
        CustoOPMaterial.objects.create(
            custo_op=custo, produto=prod,
            codigo=it.codigo or '', descricao=f'{it.tipo_perfil or "Perfil"}',
            quantidade=qtd, unidade='KG' if it.peso else 'UN',
            valor_unitario=vu, custo=valor,
        )
        total += valor

    # vidros
    for v in obra_op.vidros.all():
        prod = buscar(v.codigo)
        qtd = Decimal(str(v.quantidade or 0))
        vu = Decimal(str((prod.custo_medio or prod.custo_ultima_compra or 0)
                         if prod else 0))
        valor = (qtd * vu).quantize(Decimal('0.01'))
        CustoOPMaterial.objects.create(
            custo_op=custo, produto=prod,
            codigo=v.codigo or '', descricao=f'Vidro {v.descricao or ""}'.strip(),
            quantidade=qtd, unidade='UN',
            valor_unitario=vu, custo=valor,
        )
        total += valor

    # componentes
    for cp in obra_op.componentes.all():
        prod = buscar(cp.codigo)
        qtd = Decimal(str(cp.quantidade or 0))
        vu = Decimal(str((prod.custo_medio or prod.custo_ultima_compra or 0)
                         if prod else 0))
        valor = (qtd * vu).quantize(Decimal('0.01'))
        CustoOPMaterial.objects.create(
            custo_op=custo, produto=prod,
            codigo=cp.codigo or '', descricao=cp.descricao or 'Componente',
            quantidade=qtd, unidade=cp.unidade or 'UN',
            valor_unitario=vu, custo=valor,
        )
        total += valor

    return total


# ===========================================================================
# TELAS
# ===========================================================================

@login_required(login_url='login')
@requer_rotina('lista_custos')
def lista_custos(request):
    """Lista de OPs com o custo de cada uma."""
    query = request.GET.get('q', '').strip()
    filtro = request.GET.get('filtro', '').strip()

    qs = CustoOP.objects.select_related('obra_op', 'obra_op__obra')

    if query:
        qs = qs.filter(
            Q(obra_op__codigo_documento__icontains=query)
            | Q(obra_op__codigo_esquadria__icontains=query)
            | Q(obra_op__descricao__icontains=query)
            | Q(obra_op__obra__nome__icontains=query))
    if filtro == 'prejuizo':
        qs = [c for c in qs if c.prejuizo]
        qs = qs
    elif filtro == 'sem_custo':
        qs = qs.filter(custo_total=0)

    if isinstance(qs, list):
        page_obj = Paginator(qs, ITENS_POR_PAGINA).get_page(request.GET.get('page'))
    else:
        page_obj = Paginator(qs, ITENS_POR_PAGINA).get_page(request.GET.get('page'))

    # KPIs
    todos = CustoOP.objects.all()
    tot_custo = sum(float(c.custo_total or 0) for c in todos)
    tot_mo = sum(float(c.custo_mao_obra or 0) for c in todos)
    tot_mat = sum(float(c.custo_material or 0) for c in todos)
    tot_horas = sum(float(c.horas_totais or 0) for c in todos)
    com_venda = [c for c in todos if c.valor_venda and float(c.valor_venda) > 0]

    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'custos': page_obj,
        'page_obj': page_obj,
        'querystring': params.urlencode(),
        'query': query,
        'filtro': filtro,
        'kpi': {
            'ops': todos.count(),
            'custo_total': round(tot_custo, 2),
            'material': round(tot_mat, 2),
            'mao_obra': round(tot_mo, 2),
            'horas': round(tot_horas, 1),
            'prejuizo': len([c for c in todos if c.prejuizo]),
            'com_venda': len(com_venda),
        },
    }
    return render(request, 'core/custos/lista_custos.html', context)


@login_required(login_url='login')
@requer_rotina('lista_custos')
def detalhe_custo_producao(request, custo_id):
    """Detalhe do custo: composição, setores e materiais."""
    custo = get_object_or_404(
        CustoOP.objects.select_related('obra_op', 'obra_op__obra', 'rastreio'),
        pk=custo_id)

    if request.method == 'POST':
        acao = request.POST.get('acao', '').strip()

        if acao == 'recalcular':
            valor = request.POST.get('valor_venda', '').strip()
            vv = None
            if valor:
                try:
                    vv = Decimal(valor.replace('.', '').replace(',', '.')
                                 if ',' in valor else valor)
                except Exception:
                    vv = None
            c = calcular_custo_op(custo.obra_op, request.user, vv)
            messages.success(
                request,
                f'Custo recalculado: R$ {c.custo_total} '
                f'(R$ {c.custo_unitario} por peça).')
            return redirect('detalhe_custo_producao', custo_id=c.pk)

        if acao == 'venda':
            valor = request.POST.get('valor_venda', '').strip()
            try:
                custo.valor_venda = Decimal(
                    valor.replace('.', '').replace(',', '.') if ',' in valor else valor)
                custo.save(update_fields=['valor_venda', 'calculado_em'])
                messages.success(request, f'Valor de venda definido: R$ {custo.valor_venda}.')
            except Exception:
                messages.error(request, 'Valor inválido.')
            return redirect('detalhe_custo_producao', custo_id=custo.pk)

    context = {
        'custo': custo,
        'obra_op': custo.obra_op,
        'setores': custo.setores.all(),
        'materiais': custo.materiais.all(),
        'composicao': custo.composicao,
        'movimentacoes': (MovimentacaoOP.objects.filter(rastreio=custo.rastreio)
                          if custo.rastreio else MovimentacaoOP.objects.none()),
    }
    return render(request, 'core/custos/detalhe_custo.html', context)


@login_required(login_url='login')
@requer_rotina('lista_custos')
def calcular_op(request, op_id):
    """Calcula o custo de uma OP direto da lista de OPs."""
    op = get_object_or_404(ObraOP, pk=op_id)
    c = calcular_custo_op(op, request.user)
    messages.success(
        request,
        f'Custo da OP {op.codigo_formatado}: R$ {c.custo_total} '
        f'({c.quantidade} peça(s) — R$ {c.custo_unitario}/peça).')
    return redirect('detalhe_custo_producao', custo_id=c.pk)


@login_required(login_url='login')
@requer_rotina('lista_custos')
def custos_setores(request):
    """Custo por hora de cada setor — a base do cálculo."""
    if request.method == 'POST':
        setor = request.POST.get('setor', '').strip()
        if setor:
            obj, _ = CustoSetor.objects.get_or_create(setor=setor)
            obj.nome = request.POST.get('nome', '').strip() or obj.nome
            try:
                obj.custo_hora = Decimal(
                    request.POST.get('custo_hora', '0').replace(',', '.') or '0')
                obj.custo_hora_indireto = Decimal(
                    request.POST.get('custo_hora_indireto', '0').replace(',', '.') or '0')
            except Exception:
                messages.error(request, 'Valor inválido.')
                return redirect('custos_setores')
            obj.save()
            messages.success(
                request,
                f'{obj.nome or obj.setor}: R$ {obj.custo_hora}/h '
                f'+ R$ {obj.custo_hora_indireto}/h indireto.')
        return redirect('custos_setores')

    # mostra todos os setores da produção, cadastrados ou não
    setores = []
    for s in SetorProducao.objects.filter(ativo=True).order_by('ordem'):
        c = CustoSetor.objects.filter(setor=s.codigo).first()
        ch, ci = CustoSetor.custo_do_setor(s.codigo)
        setores.append({
            'codigo': s.codigo, 'nome': s.nome, 'cadastrado': c is not None,
            'custo_hora': float(c.custo_hora) if c else ch,
            'custo_hora_indireto': float(c.custo_hora_indireto) if c else ci,
            'id': c.pk if c else None,
        })

    tot = sum(s['custo_hora'] + s['custo_hora_indireto'] for s in setores)
    context = {
        'setores': setores,
        'media_hora': round(tot / len(setores), 2) if setores else 0,
        'total_setores': len(setores),
        'cadastrados': len([s for s in setores if s['cadastrado']]),
    }
    return render(request, 'core/custos/custos_setores.html', context)


@login_required(login_url='login')
@requer_rotina('lista_custos')
def recalcular_todos(request):
    """Recalcula o custo de todas as OPs que têm rastreio.

    Serve depois de ajustar o custo/hora: um clique atualiza a fábrica inteira
    em vez de recalcular OP por OP.
    """
    if request.method == 'POST':
        ops = ObraOP.objects.filter(
            pk__in=RastreioOP.objects.values_list('op_id', flat=True))
        n = 0
        for op in ops:
            try:
                calcular_custo_op(op, request.user)
                n += 1
            except Exception as e:
                logger.warning('Falha ao calcular custo da OP %s: %s', op.pk, e)
        messages.success(request, f'{n} OP(s) recalculada(s).')
    return redirect('lista_custos')
