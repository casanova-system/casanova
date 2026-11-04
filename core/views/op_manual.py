"""Lançamento manual de OP/Tipologia (sem depender da importação do Excel)."""
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from core.views.permissao import requer_rotina
from core.models import Obra, ObraOP, ObraOPItem, ObraOPComponente, ObraOPVidro


def _to_int(valor, padrao=0):
    """Converte string para int de forma segura."""
    if valor is None or valor == '':
        return padrao
    try:
        return int(valor)
    except (ValueError, TypeError):
        return padrao


def _to_decimal(valor, padrao=Decimal('0')):
    """Converte string para Decimal de forma segura."""
    if valor is None or valor == '':
        return padrao
    try:
        return Decimal(str(valor).replace(',', '.'))
    except (InvalidOperation, ValueError, TypeError):
        return padrao


def _validar_campos_obrigatorios(post):
    """Valida campos obrigatórios da OP. Retorna lista de erros."""
    erros = []

    # Obra (obrigatória - FK)
    obra_texto = post.get('obra_texto', '').strip()
    if not obra_texto:
        erros.append('OBRA é obrigatória (selecione ou digite).')

    # codigo_documento (identificador único da OP dentro da obra)
    codigo_documento = post.get('codigo_documento', '').strip() or post.get('codigo', '').strip()
    if not codigo_documento:
        erros.append('CÓDIGO DOCUMENTO (ex: J01) é obrigatório.')

    # codigo_esquadria (obrigatório no model)
    codigo_esquadria = post.get('codigo_esquadria', '').strip()
    if not codigo_esquadria:
        erros.append('CÓDIGO ESQUADRIA/TIPOLOGIA é obrigatório.')

    # descricao (obrigatório no model)
    descricao = post.get('descricao', '').strip()
    if not descricao:
        erros.append('DESCRIÇÃO é obrigatória.')

    # largura e altura (obrigatórios no model)
    largura = _to_int(post.get('largura'))
    if largura <= 0:
        erros.append('LARGURA deve ser maior que zero.')

    altura = _to_int(post.get('altura'))
    if altura <= 0:
        erros.append('ALTURA deve ser maior que zero.')

    # quantidade (padrão 1, mas deve ser > 0)
    quantidade = _to_int(post.get('quantidade'), 1)
    if quantidade <= 0:
        erros.append('QUANTIDADE deve ser maior que zero.')

    return erros, {
        'obra_texto': obra_texto,
        'codigo_documento': codigo_documento[:20],
        'codigo_esquadria': codigo_esquadria[:50],
        'descricao': descricao,
        'quantidade': quantidade,
        'largura': largura,
        'altura': altura,
        'tratamento': post.get('tratamento', '').strip()[:100],
        'vidro_descricao': post.get('vidro_descricao', '').strip()[:255],
        'vidro_localizacao': post.get('vidro_localizacao', '').strip()[:255],
        'itens_texto': post.get('itens', '').strip()[:255],
                'cliente': post.get('cliente', '').strip()[:255],
                'person_autovolume': post.get('person_autovolume', '').strip()[:255],
                'obra_nome': post.get('obra_nome', '').strip()[:255],
                'peso': _to_decimal(post.get('peso')),
        'area': _to_decimal(post.get('area')),
        'localizacao': post.get('localizacao', '').strip()[:255],
        'tipologia': post.get('tipologia', '').strip()[:255],
        'sistema': post.get('sistema', '').strip()[:100],
        'linha': post.get('linha', '').strip()[:100],
        'fabricante': post.get('fabricante', '').strip()[:100],
        'data_op': post.get('data_op') or None,
        'pausada_material': 'pausada_material' in post,
    }


def _obter_ou_criar_obra(obra_texto):
    """Busca obra por código ou cria nova."""
    if not obra_texto:
        return None
    try:
        # Extrai código do formato "CODIGO - Nome"
        codigo = obra_texto.split(' - ')[0].strip()
        obra = Obra.objects.filter(codigo=codigo).first()
        if obra:
            return obra
    except Exception:
        pass
    # Cria obra nova se não encontrou - usa apenas o código extraído
    codigo = obra_texto.split(' - ')[0].strip() if ' - ' in obra_texto else (obra_texto[:50] or 'MANUAL')
    return Obra.objects.create(
        codigo=codigo,
        nome=obra_texto
    )


def _salvar_perfis(op, post):
    """Salva perfis da OP. Retorna (sucesso, erros)."""
    erros = []
    codigos = post.getlist('perfil_codigo')
    for i, codigo in enumerate(codigos):
        if not (codigo or post.getlist('perfil_tamanho')[i] or '').strip():
            continue
        try:
            ObraOPItem.objects.create(
                op=op,
                posicao=i,
                codigo=(codigo or '').strip()[:50],
                tipo_perfil=post.getlist('perfil_tipo')[i] or 'OUTRO',
                orientacao=(post.getlist('perfil_orientacao')[i] or '').strip()[:10],
                corte=(post.getlist('perfil_corte')[i] or '').strip()[:20],
                tamanho=_to_int(post.getlist('perfil_tamanho')[i]),
                quantidade=_to_int(post.getlist('perfil_quantidade')[i], 1),
                peso=_to_decimal(post.getlist('perfil_peso')[i]),
                observacao=(post.getlist('perfil_obs')[i] or '').strip()[:255],
            )
        except Exception as e:
            erros.append(f'Perfil linha {i+1}: {e}')
    return len(erros) == 0, erros


def _salvar_componentes(op, post):
    """Salva componentes da OP. Retorna (sucesso, erros)."""
    erros = []
    ccodigos = post.getlist('comp_codigo')
    for i, codigo in enumerate(ccodigos):
        if not (codigo or post.getlist('comp_descricao')[i] or '').strip():
            continue
        try:
            ObraOPComponente.objects.create(
                op=op,
                posicao=i,
                codigo=(codigo or '').strip()[:50],
                descricao=post.getlist('comp_descricao')[i] or '',
                aplicacao=(post.getlist('comp_aplicacao')[i] or '').strip()[:50],
                quantidade=_to_int(post.getlist('comp_quantidade')[i], 1),
                unidade=(post.getlist('comp_unidade')[i] or '').strip()[:10],
                observacao=(post.getlist('comp_obs')[i] or '').strip()[:255],
            )
        except Exception as e:
            erros.append(f'Componente linha {i+1}: {e}')
    return len(erros) == 0, erros


def _salvar_vidros(op, post):
    """Salva vidros da OP. Retorna (sucesso, erros)."""
    erros = []
    vdescs = post.getlist('vidro_descricao_item')
    for i, desc in enumerate(vdescs):
        if not (desc or post.getlist('vidro_largura')[i] or '').strip():
            continue
        try:
            ObraOPVidro.objects.create(
                op=op,
                posicao=i,
                codigo=(post.getlist('vidro_codigo')[i] or '').strip()[:50],
                descricao=desc or '',
                cor=(post.getlist('vidro_cor')[i] or '').strip()[:100],
                quantidade=_to_int(post.getlist('vidro_quantidade')[i], 1),
                largura=_to_int(post.getlist('vidro_largura')[i]),
                altura=_to_int(post.getlist('vidro_altura')[i]),
                observacao=(post.getlist('vidro_obs')[i] or '').strip()[:255],
            )
        except Exception as e:
            erros.append(f'Vidro linha {i+1}: {e}')
    return len(erros) == 0, erros


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def nova_op_manual(request):
    obras = Obra.objects.all().order_by('codigo')

    if request.method == 'POST':
        # 1. Valida campos obrigatórios
        erros, dados = _validar_campos_obrigatorios(request.POST)
        if erros:
            for e in erros:
                messages.error(request, e)
            context = {'obras': obras, 'tipos_perfil': ObraOPItem.TIPO_PERFIL_CHOICES, 'form_data': request.POST}
            return render(request, 'core/industria/nova_op_manual.html', context)

        # 2. Busca ou cria obra
        obra = _obter_ou_criar_obra(dados['obra_texto'])
        if not obra:
            messages.error(request, 'Não foi possível identificar/criar a obra.')
            context = {'obras': obras, 'tipos_perfil': ObraOPItem.TIPO_PERFIL_CHOICES, 'form_data': request.POST}
            return render(request, 'core/industria/nova_op_manual.html', context)

        # 3. Verifica duplicidade (unique_together = obra + codigo_documento)
        if ObraOP.objects.filter(obra=obra, codigo_documento=dados['codigo_documento']).exists():
            messages.error(request, f'Já existe uma OP com o documento "{dados["codigo_documento"]}" para esta obra.')
            context = {'obras': obras, 'tipos_perfil': ObraOPItem.TIPO_PERFIL_CHOICES, 'form_data': request.POST}
            return render(request, 'core/industria/nova_op_manual.html', context)

        # 4. Cria OP
        try:
            # Remove obra_texto que não é campo do model
            dados_op = {k: v for k, v in dados.items() if k != 'obra_texto'}
            op = ObraOP.objects.create(obra=obra, **dados_op)
        except Exception as e:
            messages.error(request, f'Erro ao salvar OP: {e}')
            context = {'obras': obras, 'tipos_perfil': ObraOPItem.TIPO_PERFIL_CHOICES, 'form_data': request.POST}
            return render(request, 'core/industria/nova_op_manual.html', context)

        # 5. Salva perfis, componentes, vidros (erros não impedem a OP principal)
        ok_perfis, erros_perfis = _salvar_perfis(op, request.POST)
        ok_comps, erros_comps = _salvar_componentes(op, request.POST)
        ok_vidros, erros_vidros = _salvar_vidros(op, request.POST)

        for e in erros_perfis + erros_comps + erros_vidros:
            messages.warning(request, e)

        messages.success(request, f'OP {op.codigo_formatado} lançada manualmente.')
        return redirect('detalhe_obra_op', obra_op_id=op.pk)

    context = {'obras': obras, 'tipos_perfil': ObraOPItem.TIPO_PERFIL_CHOICES}
    return render(request, 'core/industria/nova_op_manual.html', context)


@login_required(login_url='login')
@requer_rotina('lista_ordem_producao')
def editar_op_manual(request, obra_op_id):
    op = ObraOP.objects.filter(pk=obra_op_id).first()
    if not op:
        messages.error(request, 'OP não encontrada.')
        return redirect('lista_ordem_producao')

    if request.method == 'POST':
        # Validação básica (sem codigo_documento que é PK)
        erros, dados = _validar_campos_obrigatorios(request.POST)
        if erros:
            for e in erros:
                messages.error(request, e)
            return render(request, 'core/industria/editar_op_manual.html', {'op': op, 'form_data': request.POST})

        try:
            for campo, valor in dados.items():
                if campo != 'codigo_documento':  # Não altera PK
                    setattr(op, campo, valor)
            op.save()
            messages.success(request, 'OP atualizada.')
        except Exception as e:
            messages.error(request, f'Erro ao atualizar: {e}')
        return redirect('lista_ordem_producao')

    return render(request, 'core/industria/editar_op_manual.html', {'op': op})