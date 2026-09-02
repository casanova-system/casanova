from decimal import Decimal
import json
import math
import os
import shutil
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from ..models import ItemVidro, Obra, Veiculo
from ..services import calcular_precificacao_operacao, processar_excel_relatorio


@login_required(login_url='login')
def lista_obras(request):
    query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', '-id')
    
    sort_options = {
        'recentes': '-id',
        'antigos': 'id',
        'nome_asc': 'nome',
        'nome_desc': '-nome',
        'cliente_asc': 'cliente',
        'cliente_desc': '-cliente',
        'codigo_asc': 'codigo',
        'codigo_desc': '-codigo',
    }
    
    django_order = sort_options.get(sort_by, '-id')
    obras = Obra.objects.all()
    
    if query:
        obras = obras.filter(
            Q(codigo__icontains=query) | 
            Q(nome__icontains=query) | 
            Q(cliente__icontains=query)
        )
        
    obras = obras.order_by(django_order)
        
    return render(request, 'core/fretes/lista_frete.html', {
        "obras": obras, 
        "query": query, 
        "current_sort": sort_by
    })


@login_required(login_url='login')
def upload_pdf(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]
        try:
            obra, itens = processar_excel_relatorio(excel_file)
            
            request.session['temp_obra'] = {
                'codigo': obra.codigo,
                'nome': obra.nome,
                'cliente': obra.cliente,
                'total_pecas': obra.total_pecas,
                'm2_total': str(obra.m2_total),
                'peso_total': str(obra.peso_total),
                'distancia_km': 0.0,
                'custo_frete': '0.00',
                'custo_operacao': '0.00',
                'custo_total_deslocamento': '0.00',
            }
            request.session['temp_itens'] = [
                {
                    'codigo_item': i.codigo_item,
                    'descricao': i.descricao,
                    'quantidade': i.quantidade,
                    'm2_corte': str(i.m2_corte),
                    'peso_kg': str(i.peso_kg),
                } for i in itens
            ]
            return redirect("detalhe_obra_temp")
        except Exception as e:
            messages.error(request, str(e))
            return redirect("upload_pdf")

    return render(request, "core/fretes/upload_frete.html")


@login_required(login_url='login')
def detalhe_obra_temp(request):
    temp_obra_data = request.session.get('temp_obra')
    temp_itens_data = request.session.get('temp_itens')

    if not temp_obra_data:
        return redirect("upload_pdf")

    calcular_cubagem_param = request.GET.get('calcular_cubagem') or request.POST.get('calcular_cubagem')
    faz_cubagem = True if calcular_cubagem_param == 'on' else False

    veiculos_cadastrados = Veiculo.objects.all()
    veiculo_id = request.GET.get('veiculo_id') or request.POST.get('veiculo_id')
    veiculo_selecionado = Veiculo.objects.filter(pk=veiculo_id).first() if veiculo_id else None

    m2_total_temp = float(temp_obra_data['m2_total'])
    # Cubagem calculada com base na área total (m²) e espessura média de 6 cm (0.06 metros)
    if veiculo_selecionado and faz_cubagem:
        cubagem_calc = round(m2_total_temp * 0.06, 4)
    else:
        cubagem_calc = 0.0

    viagens_calc = 1
    if veiculo_selecionado and faz_cubagem and getattr(veiculo_selecionado, 'capacidade_volumetrica', None):
        cap_v = float(veiculo_selecionado.capacidade_volumetrica)
        if cap_v > 0 and cubagem_calc > 0:
            viagens_calc = max(1, math.ceil(cubagem_calc / cap_v))

    if request.method == "POST" and request.POST.get("acao") == "salvar":
        try:
            disco = shutil.disk_usage("C:\\" if os.name == "nt" else "/")
            espaco_livre_mb = disco.free / (1024 * 1024)
            if espaco_livre_mb < 50:
                messages.error(request, "ERRO_ESPACO_INSUFICIENTE")
                return redirect("detalhe_obra_temp")
        except Exception:
            pass

        dist_str = request.POST.get("distancia_km")
        if not dist_str:
            dist_str = str(temp_obra_data['distancia_km'])
        try:
            dist_km = float(dist_str.replace(",", "."))
        except ValueError:
            dist_km = float(temp_obra_data['distancia_km'])

        res = calcular_precificacao_operacao(dist_km, m2_total_temp)
        
        f_frete = float(res["custo_frete"]) * viagens_calc
        f_operacao = float(res["custo_operacao"]) * viagens_calc
        f_total = f_frete + f_operacao

        obra = Obra(
            codigo=temp_obra_data['codigo'],
            nome=temp_obra_data['nome'],
            cliente=temp_obra_data['cliente'],
            total_pecas=temp_obra_data['total_pecas'],
            m2_total=Decimal(str(m2_total_temp)),
            peso_total=Decimal(temp_obra_data['peso_total']),
            distancia_km=dist_km,
            custo_frete=Decimal(str(f_frete)),
            custo_operacao=Decimal(str(f_operacao)),
            custo_total_deslocamento=Decimal(str(f_total)),
            usuario=request.user,
            veiculo=veiculo_selecionado,
        )
        obra.save()
        
        for i_data in temp_itens_data:
            item = ItemVidro(
                obra=obra,
                codigo_item=i_data['codigo_item'],
                descricao=i_data['descricao'],
                quantidade=i_data['quantidade'],
                m2_corte=Decimal(i_data['m2_corte']),
                peso_kg=Decimal(i_data['peso_kg']),
            )
            item.save()
        
        if 'temp_obra' in request.session:
            del request.session['temp_obra']
        if 'temp_itens' in request.session:
            del request.session['temp_itens']
            
        messages.success(request, "Obra salva com sucesso!")
        return redirect("lista_obras")

    dist_str = request.GET.get("distancia_km")
    if not dist_str:
        dist_str = str(temp_obra_data['distancia_km'])
    try:
        dist_km = float(dist_str.replace(",", "."))
    except ValueError:
        dist_km = float(temp_obra_data['distancia_km'])

    res = calcular_precificacao_operacao(dist_km, m2_total_temp)
    
    f_frete = float(res["custo_frete"]) * viagens_calc
    f_operacao = float(res["custo_operacao"]) * viagens_calc
    f_total = f_frete + f_operacao

    obra = Obra(
        codigo=temp_obra_data['codigo'],
        nome=temp_obra_data['nome'],
        cliente=temp_obra_data['cliente'],
        total_pecas=temp_obra_data['total_pecas'],
        m2_total=Decimal(str(m2_total_temp)),
        peso_total=Decimal(temp_obra_data['peso_total']),
        distancia_km=dist_km,
        custo_frete=Decimal(str(f_frete)),
        custo_operacao=Decimal(str(f_operacao)),
        custo_total_deslocamento=Decimal(str(f_total)),
    )
    
    itens = [
        ItemVidro(
            codigo_item=i['codigo_item'],
            descricao=i['descricao'],
            quantidade=i['quantidade'],
            m2_corte=Decimal(i['m2_corte']),
            peso_kg=Decimal(i['peso_kg']),
        ) for i in temp_itens_data
    ]

    total_pecas = obra.total_pecas
    m2_corte_total = obra.m2_total
    peso_total = obra.peso_total
    custo_total_materiais = Decimal("0.00")
    custo_geral_obra = custo_total_materiais + obra.custo_total_deslocamento

    m2_real = float(m2_corte_total) if float(m2_corte_total) > 0 else 1.0
    dias_trabalho = math.ceil(m2_real / 15.0) * viagens_calc

    cubagem_total = cubagem_calc
    peso_cubado = round(cubagem_total * 300, 2)
    peso_real_val = float(peso_total)
    requer_escolha_peso = bool(veiculo_selecionado) and (peso_cubado > peso_real_val)

    viagens_necessarias = viagens_calc

    parametros_calculo = {
        "media_hospedagem": 120.00,
        "media_gasolina": 5.89,
        "media_diesel": 6.19,
        "media_alimentacao": 50.00,
        "media_locomocao": 30.00,
    }

    context = {
        "obra": obra,
        "itens": itens,
        "total_pecas": total_pecas,
        "m2_corte_total": m2_corte_total,
        "peso_total": peso_total,
        "custo_total_materiais": custo_total_materiais,
        "custo_geral_obra": custo_geral_obra,
        "dias_trabalho": dias_trabalho,
        "parametros": parametros_calculo,
        "distancia_km": dist_km,
        "calcular_cubagem": "on" if faz_cubagem else "off",
        "cubagem_total": cubagem_total,
        "peso_cubado": peso_cubado,
        "requer_escolha_peso": requer_escolha_peso,
        "veiculos_cadastrados": veiculos_cadastrados,
        "veiculo_selecionado": veiculo_selecionado,
        "viagens_necessarias": viagens_necessarias,
        "is_temp": True,
        "is_read_only": False,
        "is_edit": False,
    }
    return render(request, "core/fretes/detalhe_frete.html", context)


@login_required(login_url='login')
def detalhe_obra(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    itens = obra.itens.all()

    total_pecas = sum(item.quantidade for item in itens)
    m2_corte_total = sum(item.m2_corte for item in itens)
    peso_total = sum(item.peso_kg for item in itens)
    custo_total_materiais = sum(item.custo_total for item in itens)

    calcular_cubagem_param = request.GET.get('calcular_cubagem')
    faz_cubagem = True if calcular_cubagem_param == 'on' else getattr(obra, 'calcular_cubagem', False)

    veiculos_cadastrados = Veiculo.objects.all()
    veiculo_selecionado = getattr(obra, 'veiculo', None)
    
    if veiculo_selecionado and faz_cubagem:
        cubagem_total = round(float(m2_corte_total) * 0.06, 4)
    else:
        cubagem_total = 0.0

    peso_cubado = round(cubagem_total * 300, 2)
    peso_real_val = float(peso_total)
    requer_escolha_peso = bool(veiculo_selecionado) and (peso_cubado > peso_real_val)

    viagens_necessarias = 1
    if veiculo_selecionado and faz_cubagem and getattr(veiculo_selecionado, 'capacidade_volumetrica', None):
        cap = float(veiculo_selecionado.capacidade_volumetrica)
        if cap > 0 and cubagem_total > 0:
            viagens_necessarias = math.ceil(cubagem_total / cap)
            viagens_necessarias = max(1, viagens_necessarias)

    custo_geral_obra = custo_total_materiais + obra.custo_total_deslocamento

    m2_real = float(m2_corte_total) if float(m2_corte_total) > 0 else 1.0
    dias_trabalho = math.ceil(m2_real / 15.0) * viagens_necessarias

    parametros_calculo = {
        "media_hospedagem": 120.00,
        "media_gasolina": 5.89,
        "media_diesel": 6.19,
        "media_alimentacao": 50.00,
        "media_locomocao": 30.00,
    }

    context = {
        "obra": obra,
        "itens": itens,
        "total_pecas": total_pecas,
        "m2_corte_total": m2_corte_total,
        "peso_total": peso_total,
        "custo_total_materiais": custo_total_materiais,
        "custo_geral_obra": custo_geral_obra,
        "dias_trabalho": dias_trabalho,
        "parametros": parametros_calculo,
        "distancia_km": float(obra.distancia_km),
        "calcular_cubagem": "on" if faz_cubagem else "off",
        "cubagem_total": cubagem_total,
        "peso_cubado": peso_cubado,
        "requer_escolha_peso": requer_escolha_peso,
        "veiculos_cadastrados": veiculos_cadastrados,
        "veiculo_selecionado": veiculo_selecionado,
        "viagens_necessarias": viagens_necessarias,
        "is_temp": False,
        "is_read_only": True,
        "is_edit": False,
    }
    return render(request, "core/fretes/detalhe_frete.html", context)


@login_required(login_url='login')
def editar_obra(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    itens = obra.itens.all()

    total_pecas = sum(item.quantidade for item in itens)
    m2_corte_total = sum(item.m2_corte for item in itens)
    peso_total = sum(item.peso_kg for item in itens)
    custo_total_materiais = sum(item.custo_total for item in itens)

    calcular_cubagem_param = request.GET.get('calcular_cubagem') or request.POST.get('calcular_cubagem')
    faz_cubagem = True if calcular_cubagem_param == 'on' else getattr(obra, 'calcular_cubagem', False)

    veiculos_cadastrados = Veiculo.objects.all()
    veiculo_id = request.GET.get('veiculo_id') or request.POST.get('veiculo_id')
    veiculo_selecionado = Veiculo.objects.filter(pk=veiculo_id).first() if veiculo_id else getattr(obra, 'veiculo', None)

    if veiculo_selecionado and faz_cubagem:
        cubagem_total_ed = round(float(m2_corte_total) * 0.06, 4)
    else:
        cubagem_total_ed = 0.0

    viagens_nec_ed = 1
    if veiculo_selecionado and faz_cubagem and getattr(veiculo_selecionado, 'capacidade_volumetrica', None):
        cap_v_ed = float(veiculo_selecionado.capacidade_volumetrica)
        if cap_v_ed > 0 and cubagem_total_ed > 0:
            viagens_nec_ed = max(1, math.ceil(cubagem_total_ed / cap_v_ed))

    if request.method == "POST" and request.POST.get("acao") == "salvar":
        try:
            disco = shutil.disk_usage("C:\\" if os.name == "nt" else "/")
            espaco_livre_mb = disco.free / (1024 * 1024)
            if espaco_livre_mb < 50:
                messages.error(request, "ERRO_ESPACO_INSUFICIENTE")
                return redirect("editar_obra", pk=obra.pk)
        except Exception:
            pass

        dist_str = request.POST.get("distancia_km")
        if not dist_str:
            dist_str = str(obra.distancia_km)
        try:
            dist_km = float(dist_str.replace(",", "."))
        except ValueError:
            dist_km = float(obra.distancia_km)

        res = calcular_precificacao_operacao(dist_km, float(m2_corte_total))
        f_frete = float(res["custo_frete"]) * viagens_nec_ed
        f_operacao = float(res["custo_operacao"]) * viagens_nec_ed
        f_total = f_frete + f_operacao

        obra.distancia_km = dist_km
        obra.custo_frete = Decimal(str(f_frete))
        obra.custo_operacao = Decimal(str(f_operacao))
        obra.custo_total_deslocamento = Decimal(str(f_total))
        obra.usuario = request.user
        
        if veiculo_selecionado:
            obra.veiculo = veiculo_selecionado
        else:
            obra.veiculo = None

        obra.save()

        messages.success(request, "Obra atualizada com sucesso!")
        return redirect("lista_obras")

    dist_str = request.GET.get("distancia_km")
    if not dist_str:
        dist_str = str(obra.distancia_km)
    try:
        dist_km = float(dist_str.replace(",", "."))
    except ValueError:
        dist_km = float(obra.distancia_km)

    res = calcular_precificacao_operacao(dist_km, float(m2_corte_total))
    f_frete = float(res["custo_frete"]) * viagens_nec_ed
    f_operacao = float(res["custo_operacao"]) * viagens_nec_ed
    f_total = f_frete + f_operacao

    obra.distancia_km = dist_km
    obra.custo_frete = Decimal(str(f_frete))
    obra.custo_operacao = Decimal(str(f_operacao))
    obra.custo_total_deslocamento = Decimal(str(f_total))

    custo_geral_obra = custo_total_materiais + obra.custo_total_deslocamento

    m2_real = float(m2_corte_total) if float(m2_corte_total) > 0 else 1.0
    dias_trabalho = math.ceil(m2_real / 15.0) * viagens_nec_ed

    cubagem_total = cubagem_total_ed
    peso_cubado = round(cubagem_total * 300, 2)
    peso_real_val = float(peso_total)
    requer_escolha_peso = bool(veiculo_selecionado) and (peso_cubado > peso_real_val)
    viagens_necessarias = viagens_nec_ed

    parametros_calculo = {
        "media_hospedagem": 453.00,
        "media_gasolina": 7.99,
        "media_diesel": 7.55,
        "media_alimentacao": 50.00,
        "media_locomocao": 50.00,
    }

    context = {
        "obra": obra,
        "itens": itens,
        "total_pecas": total_pecas,
        "m2_corte_total": m2_corte_total,
        "peso_total": peso_total,
        "custo_total_materiais": custo_total_materiais,
        "custo_geral_obra": custo_geral_obra,
        "dias_trabalho": dias_trabalho,
        "parametros": parametros_calculo,
        "distancia_km": dist_km,
        "calcular_cubagem": "on" if faz_cubagem else "off",
        "cubagem_total": cubagem_total,
        "peso_cubado": peso_cubado,
        "requer_escolha_peso": requer_escolha_peso,
        "veiculos_cadastrados": veiculos_cadastrados,
        "veiculo_selecionado": veiculo_selecionado,
        "viagens_necessarias": viagens_necessarias,
        "is_temp": False,
        "is_read_only": False,
        "is_edit": True,
    }
    return render(request, "core/fretes/detalhe_frete.html", context)


@login_required(login_url='login')
def excluir_obra(request, pk):
    obra = get_object_or_404(Obra, pk=pk)
    obra.delete()
    messages.success(request, "Registro excluído com sucesso!")
    return redirect("lista_obras")